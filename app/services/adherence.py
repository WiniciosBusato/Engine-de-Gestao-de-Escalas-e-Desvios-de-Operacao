from datetime import datetime, time
from typing import Optional, Tuple, Union
from sqlalchemy.orm import Session
from app.models import models
from datetime import date, timedelta


def _to_time(val: Union[time, str, None]) -> Optional[time]:
    """Garante a conversão para objeto time para comparação correta."""
    if val is None:
        return None
    if isinstance(val, time):
        return val
    if isinstance(val, str):
        # Converte strings no formato HH:MM:SS ou HH:MM
        parts = val.strip().split(":")
        if len(parts) >= 2:
            return time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
    return None

def _is_between(target_time: time, start_val: Union[time, str, None], end_val: Union[time, str, None]) -> bool:
    start = _to_time(start_val)
    end = _to_time(end_val)
    if not start or not end:
        return False
    return start <= target_time <= end

def get_expected_status(schedule: models.PlannedSchedule, current_time: time) -> models.AgentStatus:
    # Pausa 1
    if _is_between(current_time, schedule.break_1_start, schedule.break_1_end):
        return models.AgentStatus.BREAK
    
    # Refeição
    if _is_between(current_time, schedule.meal_start, schedule.meal_end):
        return models.AgentStatus.BREAK
    
    # Pausa 2
    if _is_between(current_time, schedule.break_2_start, schedule.break_2_end):
        return models.AgentStatus.BREAK
    
    # Turno
    if _is_between(current_time, schedule.shift_start, schedule.shift_end):
        return models.AgentStatus.AVAILABLE
    
    return models.AgentStatus.OFFLINE

def check_adherence(
    db: Session, 
    agent_id: int, 
    current_status: models.AgentStatus, 
    check_time: Optional[datetime] = None
) -> Tuple[bool, models.AgentStatus, str]:
    if check_time is None:
        check_time = datetime.now()

    today_date = check_time.date()
    today_str = today_date.strftime("%Y-%m-%d")
    current_time_val = check_time.time()

    # Busca todas as escalas do agente e filtra em memória para contornar limitações de tipo no SQLite
    schedules = (
        db.query(models.PlannedSchedule)
        .filter(models.PlannedSchedule.agent_id == agent_id)
        .all()
    )

    schedule = None
    for s in schedules:
        s_date = s.date.strftime("%Y-%m-%d") if hasattr(s.date, "strftime") else str(s.date)
        if s_date == today_str:
            schedule = s
            break

    if not schedule:
        return False, models.AgentStatus.OFFLINE, "Nenhuma escala planejada encontrada para hoje."

    expected_status = get_expected_status(schedule, current_time_val)

    if expected_status == models.AgentStatus.AVAILABLE:
        is_adherent = current_status in [models.AgentStatus.AVAILABLE, models.AgentStatus.ON_CALL]
    else:
        is_adherent = current_status == expected_status

    if is_adherent:
        message = "Em conformidade com a escala planejada."
    else:
        message = (
            f"Desvio detectado: Operador está '{current_status.value}', "
            f"mas o esperado para {current_time_val.strftime('%H:%M')} é '{expected_status.value}'."
        )

    return is_adherent, expected_status, message

def calculate_daily_adherence(
    db: Session,
    agent_id: int,
    target_date: date
) -> Optional[dict]:
    # 1. Busca a escala do agente comparando em memória/string para o SQLite
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

    #2- Resgata todos os logs de status gerados pelo operador na data
    day_start = datetime.combine(target_date, time.min)
    day_end = datetime.combine(target_date, time.max)

    logs = (
        db.query(models.StatusLog)
        .filter(
            models.StatusLog.agent_id == agent_id,
            models.StatusLog.timestamp >= day_start,
            models.StatusLog.timestamp <= day_end
        )
        .order_by(models.StatusLog.timestamp.asc())
        .all()
    )

    #3- Mapeia os intervalos planejados que demandas conformidade
    planned_blocks = []

    def add_block(name, start, end, expected):
        s = _to_time(start)
        e = _to_time(end)
        if s and e:
            dt_start = datetime.combine(target_date, s)
            dt_end = datetime.combine(target_date, e)
            planned_blocks.append({
                "name": name,
                "start": dt_start,
                "end": dt_end,
                "expected": expected,
                "total_seconds": int((dt_end - dt_start).total_seconds())
            })
    #bloco de Jornada Total (atendimento)
    add_block("Turno Geral", schedule.shift_start, schedule.shift_end, [models.AgentStatus.AVAILABLE, models.AgentStatus.ON_CALL])
    #pausas e refeição
    add_block("Pausa 1", schedule.break_1_start, schedule.break_1_end, [models.AgentStatus.BREAK])
    add_block("Refeição", schedule.meal_start, schedule.meal_end, [models.AgentStatus.BREAK])
    add_block("Pausa 2", schedule.break_2_start, schedule.break_2_end, [models.AgentStatus.BREAK])

    #4- Compara logs e acumula tempo aderente por falta de intervalo
    block_details = []
    total_planned = 0
    total_adherent = 0

    for block in planned_blocks:
        adherent_sec = 0
        for log in logs:
            if not log.duration_seconds or log.duration_seconds <= 0:
                continue

            log_start = log.timestamp
            log_end = log_start + timedelta(seconds=log.duration_seconds)

            #calcula a sobreposição entre o log do operador e a janela planejada
            overlap_start = max(log_start, block["start"])
            overlap_end = min(log_end, block["end"])

            if overlap_start < overlap_end:
                overlap_sec = int((overlap_end - overlap_start).total_seconds())
                if log.status in block["expected"]:
                    adherent_sec += overlap_sec

        #limita para não exceder o planejamento
        adherent_sec = min(adherent_sec, block["total_seconds"])
        rate = round((adherent_sec / block["total_seconds"] * 100), 2) if block["total_seconds"] > 0 else 0.0

        block_details.append({
            "interval_type": block["name"],
            "planned_start": block["start"].strftime("%H:%M:%S"),
            "planned_end": block["end"].strftime("%H:%M:%S"),
            "planned_seconds": block["total_seconds"],
            "adherent_seconds": adherent_sec,
            "adherence_rate": rate
        })

        total_planned += block["total_seconds"]
        total_adherent += adherent_sec

    overall_rate = round((total_adherent / total_planned * 100), 2) if total_planned > 0 else 0.0

    return {
        "total_planned_seconds": total_planned,
        "total_adherent_seconds": total_adherent,
        "overall_adherence_rate": overall_rate,
        "intervals": block_details
    }