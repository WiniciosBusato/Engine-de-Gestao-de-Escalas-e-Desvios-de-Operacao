from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models import models
from app.schemas import schemas

# O APIRounter organiza os endpoints
router = APIRouter(prefix="/agents", tags=["Agents"])

@router.post("/", response_model=schemas.AgentResponse)
def create_agent(agent: schemas.AgentCreate, db: Session = Depends(get_db)):
    #Desempacota os dados do Pydantic e cria a entidade do banco
    db_agent = models.Agent(**agent.model_dump())

    #equivale ao .save() de um Repository
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent) #atualiza o objeto com o ID gerado pelo banco

    return db_agent

@router.get("/", response_model=List[schemas.AgentResponse])
def list_agents(db: Session = Depends(get_db)):
    #equivale ao .findAll()
    agents = db.query(models.Agent).all()
    return agents