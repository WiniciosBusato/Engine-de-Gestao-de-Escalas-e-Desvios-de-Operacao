from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Time, Enum
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import enum

# Essa é a variável que o Python estava sentindo falta!
Base = declarative_base()

# Enum para padronizar os status da operação
class AgentStatus(enum.Enum):
    AVAILABLE = "Available"
    ON_CALL = "On_Call"
    BREAK = "Break"
    BATHROOM = "Bathroom"
    TRAINING = "Training"
    OFFLINE = "Offline"

class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    skill_group = Column(String) # Ex: Nível 1, Retenção, Suporte Técnico

    # Relacionamentos
    schedules = relationship("PlannedSchedule", back_populates="agent")
    status_logs = relationship("StatusLog", back_populates="agent")

class PlannedSchedule(Base):
    __tablename__ = "planned_schedules"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    date = Column(DateTime, nullable=False) # Data da escala
    shift_start = Column(Time, nullable=False)
    shift_end = Column(Time, nullable=False)
    break_1_start = Column(Time) # Pausa 1
    break_1_end = Column(Time)
    meal_start = Column(Time)    # Almoço/Janta
    meal_end = Column(Time)
    break_2_start = Column(Time) # Pausa 2
    break_2_end = Column(Time)

    agent = relationship("Agent", back_populates="schedules")

class StatusLog(Base):
    __tablename__ = "status_logs"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    status = Column(Enum(AgentStatus), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    duration_seconds = Column(Integer, nullable=True) # Preenchido quando o status mudar

    agent = relationship("Agent", back_populates="status_logs")