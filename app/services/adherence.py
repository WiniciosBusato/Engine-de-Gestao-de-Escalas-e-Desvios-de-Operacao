from datetime import datetime, time, date
from typing import Optional
from sqlalchemy.orm import Session
from app.models import models


def _to_time(val) -> Optional[time]:
    """Converte string 'HH:MM:SS' para objeto time, se necessário."""
    if val is None:
        return None
    if isinstance(val, time):
        return val
    if isinstance(val, str):
        parts = val.split(":")
        return time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
    return None


def check_adherence(
    db: Session, 
    agent_id: int, 
    check_time: Optional[datetime] = None,
    grace_period_minutes: int = 3
) -> dict:
    check_time = check_time or datetime.now()
    check_t = check_time.time()
    target_str = check_time.date().strftime("%Y-%m-%d")

    # 1. Recupera a escala do agente de forma compatível com SQLite (string/date)
    schedules = (
        db.query(models.PlannedSchedule)
        .filter(models.PlannedSchedule.agent_id == agent_id)
        .all()
    )
    schedule = None
    for s in schedules:
        s_date = s.date.strftime("%Y-%m-%d") if hasattr(s.date, "strftime") else str(s.date)
        if s_date == target_str:
            schedule = s
            break

    if not schedule:
        return {
            "agent_id": agent_id,
            "current_status": models.AgentStatus.OFFLINE,
            "expected_status": models.AgentStatus.OFFLINE,
            "is_adherent": False,
            "in_grace_period": False,
            "message": "Nenhuma escala planejada encontrada para hoje.",
            "checked_at": check_time
        }

    # 2. Resgata o último status registrado do agente
    last_log = (
        db.query(models.StatusLog)
        .filter(models.StatusLog.agent_id == agent_id)
        .order_by(models.StatusLog.timestamp.desc())
        .first()
    )
    current_status = last_log.status if last_log else models.AgentStatus.OFFLINE

    # 3. Mapeia os horários dos blocos planejados
    s_start = _to_time(schedule.shift_start)
    s_end = _to_time(schedule.shift_end)
    b1_start = _to_time(schedule.break_1_start)
    b1_end = _to_time(schedule.break_1_end)
    meal_start = _to_time(schedule.meal_start)
    meal_end = _to_time(schedule.meal_end)
    b2_start = _to_time(schedule.break_2_start)
    b2_end = _to_time(schedule.break_2_end)

    expected_status = models.AgentStatus.OFFLINE
    previous_expected = models.AgentStatus.OFFLINE
    transition_time: Optional[datetime] = None

    def to_dt(t_val):
        return datetime.combine(check_time.date(), t_val) if t_val else None

    # Identifica o status esperado e o horário da transição
    if b1_start and b1_end and b1_start <= check_t < b1_end:
        expected_status = models.AgentStatus.BREAK
        previous_expected = models.AgentStatus.AVAILABLE
        transition_time = to_dt(b1_start)
    elif meal_start and meal_end and meal_start <= check_t < meal_end:
        expected_status = models.AgentStatus.BREAK
        previous_expected = models.AgentStatus.AVAILABLE
        transition_time = to_dt(meal_start)
    elif b2_start and b2_end and b2_start <= check_t < b2_end:
        expected_status = models.AgentStatus.BREAK
        previous_expected = models.AgentStatus.AVAILABLE
        transition_time = to_dt(b2_start)
    elif s_start and s_end and s_start <= check_t < s_end:
        expected_status = models.AgentStatus.AVAILABLE
        if b1_end and check_t >= b1_end and (to_dt(check_t) - to_dt(b1_end)).total_seconds() <= grace_period_minutes * 60:
            previous_expected = models.AgentStatus.BREAK
            transition_time = to_dt(b1_end)
        elif meal_end and check_t >= meal_end and (to_dt(check_t) - to_dt(meal_end)).total_seconds() <= grace_period_minutes * 60:
            previous_expected = models.AgentStatus.BREAK
            transition_time = to_dt(meal_end)
        elif b2_end and check_t >= b2_end and (to_dt(check_t) - to_dt(b2_end)).total_seconds() <= grace_period_minutes * 60:
            previous_expected = models.AgentStatus.BREAK
            transition_time = to_dt(b2_end)
        else:
            previous_expected = models.AgentStatus.OFFLINE
            transition_time = to_dt(s_start)

    # 4. Avaliação de conformidade direta
    if expected_status == models.AgentStatus.AVAILABLE:
        is_adherent = current_status in [models.AgentStatus.AVAILABLE, models.AgentStatus.ON_CALL]
    else:
        is_adherent = (current_status == expected_status)

    # 5. Aplicação da Margem de Tolerância (Grace Period)
    in_grace_period = False
    if not is_adherent and transition_time:
        diff_seconds = (check_time - transition_time).total_seconds()
        
        if 0 <= diff_seconds <= (grace_period_minutes * 60):
            if (previous_expected == models.AgentStatus.AVAILABLE and current_status in [models.AgentStatus.AVAILABLE, models.AgentStatus.ON_CALL]) or \
               (previous_expected == current_status):
                is_adherent = True
                in_grace_period = True

    # Definição da mensagem descritiva
    if in_grace_period:
        message = f"Operador em tolerância ({grace_period_minutes} min) na transição de status."
    elif is_adherent:
        message = "Operador em conformidade com a escala planejada."
    else:
        message = f"Desvio detectado! Esperado: {expected_status.value}, Atual: {current_status.value}."

    return {
        "agent_id": agent_id,
        "current_status": current_status,
        "expected_status": expected_status,
        "is_adherent": is_adherent,
        "in_grace_period": in_grace_period,
        "message": message,
        "checked_at": check_time
    }


def calculate_daily_adherence(
    db: Session,
    agent_id: int,
    target_date: date
) -> Optional[dict]:
    # 1. Busca a escala do agente
    target_str = target_date.strftime("%Y-%m-%d") if hasattr(target_date, "strftime") else str(target_date)

    schedules = (
        db.query(models.PlannedSchedule)
        .filter(models.PlannedSchedule.agent_id == agent_id)
        .all()
    )

    schedule = None
    for s in schedules:
        s_date = s.date.strftime("%Y-%m-%d") if hasattr(s.date, "strftime") else str(s.date)
        if s_date == target_str:
            schedule = s
            break

    if not schedule:
        return None

    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    agent_name = agent.name if agent else f"Agent {agent_id}"

    # 2. Busca e monta a lista de logs do dia
    start_of_day = datetime.combine(target_date, time.min)
    end_of_day = datetime.combine(target_date, time.max)

    logs = (
        db.query(models.StatusLog)
        .filter(
            models.StatusLog.agent_id == agent_id,
            models.StatusLog.timestamp >= start_of_day,
            models.StatusLog.timestamp <= end_of_day
        )
        .order_by(models.StatusLog.timestamp.asc())
        .all()
    )

    # Identifica o último log anterior ao dia para continuidade de status
    prior_log = (
        db.query(models.StatusLog)
        .filter(
            models.StatusLog.agent_id == agent_id,
            models.StatusLog.timestamp < start_of_day
        )
        .order_by(models.StatusLog.timestamp.desc())
        .first()
    )
    initial_status = prior_log.status if prior_log else models.AgentStatus.OFFLINE

    log_intervals = []
    current_time_marker = start_of_day
    current_state = initial_status

    for log in logs:
        if log.timestamp > current_time_marker:
            log_intervals.append({
                "start": current_time_marker,
                "end": log.timestamp,
                "status": current_state
            })
        current_time_marker = log.timestamp
        current_state = log.status

    if current_time_marker < end_of_day:
        log_intervals.append({
            "start": current_time_marker,
            "end": end_of_day,
            "status": current_state
        })

    # 3. Define os blocos planejados
    def make_interval(name, start_t, end_t, expected_stat):
        if not start_t or not end_t:
            return None
        st = _to_time(start_t)
        et = _to_time(end_t)
        if not st or not et:
            return None
        dt_start = datetime.combine(target_date, st)
        dt_end = datetime.combine(target_date, et)
        return {
            "name": name,
            "start": dt_start,
            "end": dt_end,
            "expected_status": expected_stat,
            "planned_seconds": int((dt_end - dt_start).total_seconds()),
            "adherent_seconds": 0
        }

    planned_blocks = [
        make_interval("Turno Geral", schedule.shift_start, schedule.shift_end, models.AgentStatus.AVAILABLE),
        make_interval("Pausa 1", schedule.break_1_start, schedule.break_1_end, models.AgentStatus.BREAK),
        make_interval("Refeição", schedule.meal_start, schedule.meal_end, models.AgentStatus.BREAK),
        make_interval("Pausa 2", schedule.break_2_start, schedule.break_2_end, models.AgentStatus.BREAK),
    ]
    planned_blocks = [b for b in planned_blocks if b is not None]

    # 4. Cálculo de sobreposição entre logs reais e intervalos planejados
    for block in planned_blocks:
        b_start = block["start"]
        b_end = block["end"]
        exp_status = block["expected_status"]

        for l_int in log_intervals:
            overlap_start = max(b_start, l_int["start"])
            overlap_end = min(b_end, l_int["end"])

            if overlap_start < overlap_end:
                is_match = False
                if exp_status == models.AgentStatus.AVAILABLE:
                    is_match = l_int["status"] in [models.AgentStatus.AVAILABLE, models.AgentStatus.ON_CALL]
                else:
                    is_match = (l_int["status"] == exp_status)

                if is_match:
                    block["adherent_seconds"] += int((overlap_end - overlap_start).total_seconds())

    # 5. Consolidação dos resultados
    total_planned = sum(b["planned_seconds"] for b in planned_blocks)
    total_adherent = sum(b["adherent_seconds"] for b in planned_blocks)
    overall_rate = round((total_adherent / total_planned * 100), 2) if total_planned > 0 else 0.0

    intervals_detail = []
    for b in planned_blocks:
        rate = round((b["adherent_seconds"] / b["planned_seconds"] * 100), 2) if b["planned_seconds"] > 0 else 0.0
        intervals_detail.append({
            "interval_type": b["name"],
            "planned_start": b["start"].strftime("%H:%M:%S"),
            "planned_end": b["end"].strftime("%H:%M:%S"),
            "planned_seconds": b["planned_seconds"],
            "adherent_seconds": b["adherent_seconds"],
            "adherence_rate": rate
        })

    return {
        "agent_id": agent_id,
        "agent_name": agent_name,
        "date": target_date,
        "total_planned_seconds": total_planned,
        "total_adherent_seconds": total_adherent,
        "overall_adherence_rate": overall_rate,
        "intervals": intervals_detail
    }

def get_agent_infractions(
    db: Session,
    agent_id: int,
    target_date: date 
) -> Optional[dict]:
    """
    Identifica e lista todos os eventos/janelas de tempo em que o operador
    esteve em não conformidade com a escala planejada ao longo do dia
    """

    target_str = target_date.strftime("%Y-%m-%d") if hasattr(target_date, "strftime") else str(target_date)

    #1- Busca a escala do agente
    schedules = (
        db.query(models.PlannedSchedule)
        .filter(models.PlannedSchedule.agent_id == agent_id)
        .all()
    )
    schedule = None
    for s in schedules:
        s_date = s.date.strftime("%Y-%m-%d") if hasattr(s.date,"strftime") else str(s.date)
        if s_date == target_str:
            schedule = s
            break

    if not schedule:
        return None

    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    agent_name = agent.name if agent else f"Agent {agent_id}"

    #2- Reconstroi a linha do tempo de status reais do dia
    start_of_day = datetime.combine(target_date, time.min)
    end_of_day = datetime.combine(target_date, time.max)

    logs = (
        db.query(models.StatusLog)
        .filter(
            models.StatusLog.agent_id == agent_id,
            models.StatusLog.timestamp >= start_of_day
            models.StatusLog.timestamp <= end_of_day
        )
        .order_by(models.StatusLog.timestamp.asc())
        .all()
    )

    prior_log = (
        db.query(models.StatusLog)
        .filter(
            models.StatusLog.agent_id == agent_id,
            models.StatusLog.timestamp < start_of_day
        )
        .order_by(models.StatusLog.timestamp.desc())
        .first()
    )
    initial_status = prior_log.status if prior_log else models.AgentStatus.OFFLINE

    log_intervals = []
    current_time_marker = start_of_day
    current_state = initial_status

    for log in logs:
        if log.timestamp > current_time_marker:
            log_intervals.append({
                "start": current_time_marker,
                "end": log.timestamp,
                "status": current_state
            })
        current_time_marker = log.timestamp
        current_state = log.status

    if current_time_marker < end_of_day:
        log_intervals.append({
                "start": current_time_marker,
                "end": end_of_day,
                "status": current_state
        })

    #3- mapeia os blocos planejados
    def make_interval(name, start_t, end_t, exp_status):
        if not start_t or not end_t:
            return None
        st = _to_time(start_t)
        et = _to_time(end_t)
        if not st or not et:
            return None
        return {
            "name": name,
            "start": datetime.combine(target_date, st),
            "end": datetime.combine(target_date, et),
            "expected_status": exp_status
        }

    planned_blocks = [
        make_interval("Pausa 1", schedule.break_1_start, schedule.break_1_end, models.AgentStatus.BREAK),
        make_interval("Refeição", schedule.meal_start, schedule.meal_end, models.AgentStatus.BREAK),
        make_interval("Pausa 2", schedule.break_2_start, schedule.break_2_end, models.AgentStatus.BREAK),
        make_interval("Turno de Atendimento", schedule.shift_start, schedule.shift_end, models.AgentStatus.AVAILABLE),
    ]
    planned_blocks = [b for b in planned_blocks if b is not None]

    infractions = []
    total_infraction_seconds = 0

    #4- Avalia as colisões e identifica desvios
    for block in planned_blocks:
        b_start = block["start"]
        b_end = block["end"]
        exp_status = block["expected_status"]

        for l_int in log_intervals:
            overlap_start = max(b_start, l_int["start"])
            overlap_end = min(b_end, l_int["end"])

            if overlap_start < overlap_end:
                is_match = False
                if exp_status == models.AgentStatus.AVAILABLE:
                    is_match = l_int["status"] in [models.AgentStatus.AVAILABLE, models.AgentStatus.ON_CALL]
                else:
                    is_match = (l_int["status"] == exp_status)

                #Se não for aderente, gera registro de infração
                if not is_match:
                    dur_sec = int((overlap_end - overlap_start).total_seconds())
                    if dur_sec > 0:
                        total_infraction_seconds += dur_sec
                        mins, secs = divmod(dur_sec, 60)
                        hours, mins = divmod(mins, 60)
                        formatted_dur = f"{hours:02d}:{mins:02d}:{secs:02d}"

                        infractions.append({
                            "interval_name": block["name"],
                            "expected_status": exp_status,
                            "actual_status": l_int["status"],
                            "start_time": overlap_start,
                            "end_time": overlap_end,
                            "duration_seconds": dur_sec,
                            "duration_formatted": formatted_dur
                        })
    return {
        "agent_id": agent_id,
        "agent_name": agent_name,
        "date": target_date,
        "total_infractions_count": len(infractions),
        "total_infraction_seconds": total_infraction_seconds,
        "infractions": infractions    
    }