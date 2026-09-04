from datetime import datetime, time, date, timedelta
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
    grace_period_minutes: int = 0
) -> Optional[dict]:
    """
    Verifica a aderencia em tempo real do agente cruzando a escala planejada
    com o ultimo status registrado, considerando o periodo de tolerancia (grace period).
    """
    check_dt = check_time or datetime.now()
    check_date = check_dt.date()
    target_str = check_date.strftime("%Y-%m-%d")

    # 1. Busca o status atual do operador PRIMEIRO para definir current_status
    last_log = (
        db.query(models.StatusLog)
        .filter(
            models.StatusLog.agent_id == agent_id,
            models.StatusLog.timestamp <= check_dt
        )
        .order_by(models.StatusLog.timestamp.desc())
        .first()
    )
    current_status = last_log.status if last_log else models.AgentStatus.OFFLINE

    # 2. Busca a escala do agente para o dia
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

    # 3. Se nao houver escala, o operador e aderente apenas se estiver Offline
    if not schedule:
        return {
            "agent_id": agent_id,
            "check_time": check_dt,
            "current_status": current_status,
            "expected_status": models.AgentStatus.OFFLINE,
            "current_interval_name": None,
            "is_adherent": current_status == models.AgentStatus.OFFLINE,
            "in_grace_period": False
        }

    # 4. Mapeia os intervalos planejados do dia
    def make_interval(name, start_t, end_t, exp_status):
        if not start_t or not end_t:
            return None
        st = _to_time(start_t)
        et = _to_time(end_t)
        if not st or not et:
            return None
        return {
            "name": name,
            "start": datetime.combine(check_date, st),
            "end": datetime.combine(check_date, et),
            "expected_status": exp_status
        }

    intervals = [
        make_interval("Pausa 1", schedule.break_1_start, schedule.break_1_end, models.AgentStatus.BREAK),
        make_interval("Refeicao", schedule.meal_start, schedule.meal_end, models.AgentStatus.BREAK),
        make_interval("Pausa 2", schedule.break_2_start, schedule.break_2_end, models.AgentStatus.BREAK),
        make_interval("Turno de Atendimento", schedule.shift_start, schedule.shift_end, models.AgentStatus.AVAILABLE),
    ]
    intervals = [i for i in intervals if i is not None]

    active_interval = None
    for interval in intervals:
        if interval["start"] <= check_dt <= interval["end"]:
            active_interval = interval
            break

    if active_interval:
        expected_status = active_interval["expected_status"]
        current_interval_name = active_interval["name"]
        interval_start = active_interval["start"]
    else:
        expected_status = models.AgentStatus.OFFLINE
        current_interval_name = None
        interval_start = None

    # 5. Avaliacao de conformidade (Aderencia)
    if expected_status == models.AgentStatus.AVAILABLE:
        is_adherent = current_status in [models.AgentStatus.AVAILABLE, models.AgentStatus.ON_CALL]
    elif expected_status == models.AgentStatus.BREAK:
        is_adherent = (current_status == models.AgentStatus.BREAK)
    elif expected_status == models.AgentStatus.OFFLINE:
        is_adherent = (current_status == models.AgentStatus.OFFLINE)
    else:
        is_adherent = (current_status == expected_status)

    # 6. Avaliacao do Grace Period (Tolerancia na virada de bloco)
    in_grace_period = False
    if not is_adherent and interval_start and grace_period_minutes > 0:
        grace_limit = interval_start + timedelta(minutes=grace_period_minutes)
        if check_dt <= grace_limit:
            in_grace_period = True
            is_adherent = True

    return {
        "agent_id": agent_id,
        "check_time": check_dt,
        "current_status": current_status,
        "expected_status": expected_status,
        "current_interval_name": current_interval_name,
        "is_adherent": is_adherent,
        "in_grace_period": in_grace_period
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
    target_date: date,
    grace_period_minutes: int = 0
) -> Optional[dict]:
    """
    Identifica e lista todos os eventos/janelas de tempo em que o operador
    esteve em não conformidade com a escala planejada ao longo do dia,
    respitando a margem de tolerancia configurada.
    """
    target_str = target_date.strftime("%Y-%m-%d") if hasattr(target_date, "strftime") else str(target_date)

    # 1. Busca a escala do agente
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

    # 2. Reconstitui a linha do tempo de status reais do dia
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

    # 3. Mapeia os blocos planejados
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
    grace_delta = timedelta(minutes=grace_period_minutes)

    # 4. Avalia as colisões e identifica desvios
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

                # Se não for aderente, gera registro de infração
                if not is_match:
                    is_at_transtion_start = (overlap_start == b_start)
                    overlap_duration = overlap_end - overlap_start

                    if grace_period_minutes > 0 and is_at_transtion_start:
                        if overlap_duration <= grace_delta:
                            continue
                        else:
                            overlap_start = overlap_start + grace_delta

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

def get_team_realtime_dashboard(
        db: Session,
        grace_period_minutes: int = 0
) -> dict:
    """
    Gera a visão consolidada de aderencia de toda a equipe em tempo real.
    """
    now = datetime.now()
    agents= db.query(models.Agent).all()

    members = []
    adherent_count = 0

    for agent in agents:
        #1- Checa a aderencia em tempo real do operador
        adh_info = check_adherence(
            db=db,
            agent_id=agent.id,
            check_time=now,
            grace_period_minutes=grace_period_minutes
        )

        #2- Busca o ultimo log para calcular o tempo no status atual
        last_log = (
            db.query(models.StatusLog)
            .filter(models.StatusLog.agent_id == agent.id)
            .order_by(models.StatusLog.timestamp.desc())
            .first()
        )

        duration_sec = 0
        formatted_dur = "00:00:00"
        status_since = None

        if last_log:
            status_since = last_log.timestamp
            diff = now - status_since
            duration_sec = max(0, int(diff.total_seconds()))
            mins, secs= divmod(duration_sec, 60)
            hours, mins = divmod(mins, 60)
            formatted_dur = f"{hours:02d}:{mins:02d}:{secs:02d}"

        is_adherent = adh_info.get("is_adherent",False) if adh_info else False
        if is_adherent:
            adherent_count += 1

        members.append({
            "agent_id": agent.id,
            "agent_name": agent.name,
            "current_status": adh_info.get("current_status") if adh_info else models.AgentStatus.OFFLINE,
            "expected_status": adh_info.get("expected_status") if adh_info else None,
            "current_interval_name": adh_info.get("current_interval_name") if adh_info else None,
            "is_adherent": is_adherent,
            "in_grace_period": adh_info.get("in_grace_period", False) if adh_info else False,
            "status_since": status_since,
            "duration_in_status_seconds": duration_sec,
            "duration_in_status_formatted": formatted_dur 
        })

    total_agents = len(agents)
    adherence_rate = round((adherent_count / total_agents * 100), 2) if total_agents > 0 else 0.0

    return {
       "timestamp": now,
        "total_agents": total_agents,
        "adherent_count": adherent_count,
        "non_adherent_count": total_agents - adherent_count,
        "adherence_rate": adherence_rate,
        "members": members 
    }