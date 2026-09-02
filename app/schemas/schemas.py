from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, time, date
from app.models.models import AgentStatus

#--- SCHEMAS PARA AGENT ---
class AgentBase(BaseModel):
    name: str
    email: EmailStr
    skill_group: Optional[str] = None

class AgentCreate(AgentBase):
    pass #Para criar, precisamos apenas dos dados base

class AgentResponse(AgentBase):
    id: int

    class Config:
        from_attributes = True #Permite que o Pydantic leia objetos do SQLAlchemy do SQLAlchemy

# --- SCHEMAS PARA STATUS LOG ---
class StatusLogBase(BaseModel):
    agent_id: int
    status: AgentStatus

class StatusLogCreate(StatusLogBase):
    pass

class StatusLogResponse(StatusLogBase):
    id: int
    timestamp: datetime
    duration_seconds: Optional[int] = None

    class Config:
        from_attributes = True

# --- SCHEMAS PARA PLANNED SCHEDULE ---
class PlannedScheduleBase(BaseModel):
    agent_id: int
    date: date
    shift_start: time
    shift_end: time
    break_1_start: Optional[time] = None
    break_1_end: Optional[time] = None
    meal_start: Optional[time] = None
    meal_end: Optional[time] = None
    break_2_start: Optional[time] = None
    break_2_end: Optional[time] = None

class PlannedScheduleCreate(PlannedScheduleBase):
    pass

class PlannedScheduleResponse(PlannedScheduleBase):
    id: int

    class Config:
        from_attributes = True

class StatusLogCreate(BaseModel):
    agent_id: int
    status: AgentStatus
    timestamp: Optional[datetime] = None

class StatusLogResponse(BaseModel):
    id: int
    agent_id: int
    status: AgentStatus
    timestamp: datetime
    duration_seconds: Optional[int] = None

class Config:
    from_attributes = True

class AdherenceCheckResponse(BaseModel):
    agent_id: int
    current_status: AgentStatus
    expected_status: AgentStatus
    is_adherent: bool
    message: str
    checked_at: datetime

class AgentOverviewItem(BaseModel):
    agent_id: int
    agent_name: str
    skill_group: str
    current_status: AgentStatus
    expected_status: AgentStatus
    is_adherent: bool
    message: str

class AdherenceOverviewResponse(BaseModel):
    total_agents: int
    adherent_count: int
    non_adherent_count: int
    adherence_rate: float
    timestamp: datetime
    agents: List[AgentOverviewItem]