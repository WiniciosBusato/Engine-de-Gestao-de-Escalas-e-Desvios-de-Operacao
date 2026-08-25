from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import date
from app.core.database import get_db
from app.models import models
from app.schemas import schemas

router = APIRouter(prefix="/schedules", tags=["Schedules"])

@router.post("/", response_model=schemas.PlannedScheduleResponse)
def create_schedule(schedule: schemas.PlannedScheduleCreate, db: Session = Depends(get_db)):
    #1- Valida se o agente realmente existe antes de criar a escala
    agent = db.query(models.Agent).filter(models.Agent.id == schedule.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    #2- Cria o registro da escala
    db_schedule = models.PlannedSchedule(**schedule.model_dump())
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)

    return db_schedule

@router.get("/agent/{agent_id}", response_model=List[schemas.PlannedScheduleResponse])
def get_schedules_by_agent(agent_id: int, db: Session = Depends(get_db)):
    #Busca todas as escalas de um operador especifico
    schedules = db.query(models.PlannedSchedule).filter(models.PlannedSchedule.agent_id == agent_id).all()
    return schedules