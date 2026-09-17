import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture(scope="module")
def auth_token():
    """Obtém o token JWT com as credenciais do supervisor."""
    response = client.post(
        "/auth/token",
        data={"username": "supervisor2", "password": "senha_segura_123"}
    )
    assert response.status_code == 200, f"Falha no login: {response.text}"
    token = response.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}

def test_login_invalido():
    """Valida rejeição de credenciais incorretas (401)."""
    response = client.post(
        "/auth/token",
        data={"username": "supervisor2", "password": "senha_errada"}
    )
    assert response.status_code == 401

def test_registrar_status(auth_token):
    """Valida criação de log de status pelo agente."""
    payload = {
        "agent_id": 1,
        "status": "Break",
        "timestamp": "2026-09-15T08:15:00"
    }
    response = client.post("/status/", json=payload, headers=auth_token)
    assert response.status_code in (200, 201)

def test_calculo_desvio_aderencia(auth_token):
    """Valida se o motor identifica o agente fora de escala."""
    params = {
        "check_time": "2026-09-15T08:15:00",
        "grace_period_minutes": 0
    }
    response = client.get("/status/adherence/1", params=params, headers=auth_token)
    assert response.status_code == 200
    data = response.json()
    assert data["is_adherent"] is False
    assert data["current_status"] == "Break"
    assert data["expected_status"] == "Available"

def test_dashboard_equipe(auth_token):
    """Valida acesso ao dashboard de equipe."""
    response = client.get("/status/adherence/realtime/team", headers=auth_token)
    assert response.status_code == 200
    data = response.json()
    assert "adherent_count" in data
    assert "members" in data

def test_rota_diaria_protegida_sem_token():
    """Valida que o relatório diário rejeita requisição sem token (401)."""
    response = client.get("/status/adherence/daily/1?report_date=2026-09-15")
    assert response.status_code == 401

def test_rota_diaria_com_token(auth_token):
    """Valida cálculo consolidado diário com usuário autenticado (200)."""
    response = client.get("/status/adherence/daily/1?report_date=2026-09-15", headers=auth_token)
    assert response.status_code == 200
    data = response.json()
    assert data["agent_id"] == 1
    assert "total_planned_seconds" in data
    assert "overall_adherence_rate" in data

def test_exportacao_relatorio_csv(auth_token):
    """Valida o download do CSV do relatório de aderência diário."""
    response = client.get(
        "/status/adherence/daily/1/export/csv?report_date=2026-09-15",
        headers=auth_token
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    assert "ID Agente" in response.text
    assert "João Silva" in response.text

def test_exportacao_relatorio_excel(auth_token):
    """Valida o download do relatório em formato XLSX."""
    response = client.get(
        "/status/adherence/daily/1/export/excel?report_date=2026-09-15",
        headers=auth_token
    )
    assert response.status_code == 200
    assert "spreadsheetml.sheet" in response.headers.get("content-type", "")
    assert len(response.content) > 0
