from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import Optional
from app.core.database import get_db
from app.models import models
from app.schemas import schemas
from app.services.adherence import check_adherence, calculate_daily_adherence

# A variável que o main.py está procurando:
router = APIRouter(prefix="/status", tags=["Status & Adherence"])

@router.post("/", response_model=schemas.StatusLogResponse)
def log_agent_status(payload: schemas.StatusLogCreate, db: Session = Depends(get_db)):
    # 1. Confere se o agente existe
    agent = db.query(models.Agent).filter(models.Agent.id == payload.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")

    now = payload.timestamp or datetime.now()

    # 2. Busca o último status aberto do agente para fechar a duração
    last_log = (
        db.query(models.StatusLog)
        .filter(models.StatusLog.agent_id == payload.agent_id, models.StatusLog.duration_seconds.is_(None))
        .order_by(models.StatusLog.timestamp.desc())
        .first()
    )

    if last_log:
        elapsed = int((now - last_log.timestamp).total_seconds())
        last_log.duration_seconds = max(elapsed, 0)
        db.add(last_log)

    # 3. Cria o novo registro de status
    new_log = models.StatusLog(
        agent_id=payload.agent_id,
        status=payload.status,
        timestamp=now
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)

    return new_log

@router.get("/adherence/overview", response_model=schemas.AdherenceOverviewResponse)
def get_adherence_overview(
    check_time: Optional[datetime] = None,
    grace_period_minutes: int = 3,
    db: Session = Depends(get_db)
):
    agents = db.query(models.Agent).all()
    now = datetime.now()

    overview_items = []
    adherent_count = 0

    for agent in agents:
        #busca o ultimo status registrado para o operador
        latest_log = (
            db.query(models.StatusLog)
            .filter(models.StatusLog.agent_id == agent.id)
            .order_by(models.StatusLog.timestamp.desc())
            .first()
        )
        current_status = latest_log.status if latest_log else models.AgentStatus.OFFLINE

        #execute a regra de negocio de aderencia
        is_adherent, expected_status, message = check_adherence(
            db=db,
            agent_id=agent.id,
            current_status=current_status,
            check_time=now
        )

        if is_adherent:
            adherent_count += 1

        overview_items.append(
            schemas.AgentOverviewItem(
                agent_id=agent.id,
                agent_name=agent.name,
                skill_group=agent.skill_group,
                current_status=current_status,
                expected_status=expected_status,
                is_adherent=is_adherent,
                message=message
            )
        )

    total_agents = len(agents)
    rate = round((adherent_count / total_agents* 100), 2) if total_agents > 0 else 0.0

    return schemas.AdherenceOverviewResponse(
        total_agents=total_agents,
        adherent_count=adherent_count,
        non_adherent_count=total_agents - adherent_count,
        adherence_rate=rate,
        timestamp=now,
        agents=overview_items
    )


@router.get("/adherence/daily/{agent_id}", response_model=schemas.DailyAdherenceResponse)
def get_daily_adherence(
    agent_id: int,
    report_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
    target_date = report_date or date.today()
    result = calculate_daily_adherence(db=db, agent_id=agent_id, target_date=target_date)

    if not result:
        raise HTTPException(status_code=404, detail=f"Escala não encontrada para a data {target_date}")

    return schemas.DailyAdherenceResponse(
        agent_id=agent.id,
        agent_name=agent.name,
        date=target_date,
        total_planned_seconds=result["total_planned_seconds"],
        total_adherent_seconds=result["total_adherent_seconds"],
        overall_adherence_rate=result["overall_adherence_rate"],
        intervals=[schemas.DailyAdherenceDetail(**item) for item in result["intervals"]]
    )


@router.get("/adherence/{agent_id}", response_model=schemas.AdherenceCheckResponse)
def get_agent_adherence(
    agent_id: int,
    check_time: Optional[datetime] = None,
    grace_period_minutes: int = 3,
    db: Session = Depends(get_db)
):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")

    result = check_adherence(
        db=db,
        agent_id=agent_id,
        check_time=check_time,
        grace_period_minutes=grace_period_minutes
    )
    return result