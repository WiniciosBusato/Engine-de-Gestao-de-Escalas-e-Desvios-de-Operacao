from datetime import date, datetime, time
from typing import List, Optional
from pydantic import BaseModel
from app.models.models import AgentStatus

# --- AGENT SCHEMAS ---
class AgentBase(BaseModel):
    name: str
    skill_group: str

class AgentCreate(AgentBase):
    pass

class AgentResponse(AgentBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# --- SCHEDULE SCHEMAS ---
class PlannedScheduleBase(BaseModel):
    agent_id: int
    date: date
    shift_start: time
    shift_end: time
    meal_start: Optional[time] = None
    meal_end: Optional[time] = None
    break_1_start: Optional[time] = None
    break_1_end: Optional[time] = None
    break_2_start: Optional[time] = None
    break_2_end: Optional[time] = None

class PlannedScheduleCreate(PlannedScheduleBase):
    pass

class PlannedScheduleResponse(PlannedScheduleBase):
    id: int

    class Config:
        from_attributes = True

# --- STATUS SCHEMAS ---
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

# --- ADHERENCE SCHEMAS ---
class AdherenceCheckResponse(BaseModel):
    agent_id: int
    current_status: AgentStatus
    expected_status: AgentStatus
    is_adherent: bool
    message: str
    checked_at: datetime

# --- OVERVIEW SCHEMAS ---
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

# --- DAILY ADHERENCE SCHEMAS ---
class DailyAdherenceDetail(BaseModel):
    interval_type: str
    planned_start: str
    planned_end: str
    planned_seconds: int
    adherent_seconds: int
    adherence_rate: float

class DailyAdherenceResponse(BaseModel):
    agent_id: int
    agent_name: str
    date: date
    total_planned_seconds: int
    total_adherent_seconds: int
    overall_adherence_rate: float
    intervals: List[DailyAdherenceDetail]