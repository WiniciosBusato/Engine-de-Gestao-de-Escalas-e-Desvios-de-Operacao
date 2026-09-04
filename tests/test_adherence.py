import sys
from pathlib import Path
from datetime import datetime, date, time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Garante que a raiz do projeto esteja no sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import get_db
from app.models.models import Base, Agent, StatusLog, PlannedSchedule, AgentStatus
from app.main import app

# Configuração com StaticPool para manter o SQLite em memória persistente entre conexões
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Cria o schema completo antes de cada teste e remove no encerramento."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Substitui o get_db do FastAPI pela sessão de teste."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_agent_offline_outside_schedule_is_adherent(client, db_session):
    """
    Testa se um operador com status Offline fora de qualquer escala planejada
    é considerado aderente (100% no dashboard em tempo real).
    """
    # 1. Cria o agente
    agent = Agent(name="Operador Teste Unitario", email="teste@wfm.com")
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)

    # 2. Registra o status Offline
    log = StatusLog(
        agent_id=agent.id,
        status=AgentStatus.OFFLINE,
        timestamp=datetime(2026, 9, 4, 8, 0, 0)
    )
    db_session.add(log)
    db_session.commit()

    # 3. Consulta o endpoint
    response = client.get("/status/adherence/realtime/team")
    assert response.status_code == 200

    data = response.json()
    assert data["total_agents"] == 1
    assert data["adherent_count"] == 1
    assert data["adherence_rate"] == 100.0

    member = data["members"][0]
    assert member["agent_id"] == agent.id
    assert member["current_status"] == "Offline"
    assert member["expected_status"] == "Offline"
    assert member["is_adherent"] is True


def test_grace_period_forgives_short_transition_delay(client, db_session):
    """
    Testa se o atraso de 2 minutos na transição é perdoado com tolerância de 3 minutos.
    """
    agent = Agent(name="Operador Pausa", email="pausa@wfm.com")
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)

    test_date = date(2026, 9, 2)

    schedule = PlannedSchedule(
        agent_id=agent.id,
        date=test_date,
        shift_start=time(8, 0),
        shift_end=time(17, 0),
        break_1_start=time(10, 0),
        break_1_end=time(10, 15),
        meal_start=time(12, 0),
        meal_end=time(13, 0),
        break_2_start=time(15, 0),
        break_2_end=time(15, 15)
    )
    db_session.add(schedule)

    log1 = StatusLog(agent_id=agent.id, status=AgentStatus.AVAILABLE, timestamp=datetime(2026, 9, 2, 8, 0, 0))
    log2 = StatusLog(agent_id=agent.id, status=AgentStatus.BREAK, timestamp=datetime(2026, 9, 2, 10, 2, 0))
    log3 = StatusLog(agent_id=agent.id, status=AgentStatus.AVAILABLE, timestamp=datetime(2026, 9, 2, 10, 15, 0))
    log4 = StatusLog(agent_id=agent.id, status=AgentStatus.OFFLINE, timestamp=datetime(2026, 9, 2, 17, 0, 0))
    db_session.add_all([log1, log2, log3, log4])
    db_session.commit()

    # Sem tolerância
    res_zero = client.get(f"/status/adherence/{agent.id}/infractions?target_date=2026-09-02&grace_period_minutes=0")
    assert res_zero.status_code == 200
    assert res_zero.json()["total_infractions_count"] >= 1

    # Com tolerância de 3 minutos
    res_grace = client.get(f"/status/adherence/{agent.id}/infractions?target_date=2026-09-02&grace_period_minutes=3")
    assert res_grace.status_code == 200
    infractions = res_grace.json()["infractions"]

    break_infractions = [i for i in infractions if i["interval_name"] == "Pausa 1"]
    assert len(break_infractions) == 0