from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.models import models
from app.schemas import schemas
from app.services.adherence import check_adherence

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

@router.get("/adherence/{agent_id}", response_model=schemas.AdherenceCheckResponse)
def get_agent_adherence(agent_id: int, db: Session = Depends(get_db)):
    latest_status_log = (
        db.query(models.StatusLog)
        .filter(models.StatusLog.agent_id == agent_id)
        .order_by(models.StatusLog.timestamp.desc())
        .first()
    )

    current_status = latest_status_log.status if latest_status_log else models.AgentStatus.OFFLINE
    now = datetime.now()

    is_adherent, expected, message = check_adherence(
        db=db, 
        agent_id=agent_id, 
        current_status=current_status, 
        check_time=now
    )

    return schemas.AdherenceCheckResponse(
        agent_id=agent_id,
        current_status=current_status,
        expected_status=expected,
        is_adherent=is_adherent,
        message=message,
        checked_at=now
    )