import csv
import io
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.reports import generate_daily_adherence_csv

from app.core.database import get_db
from app.models import models
from app.services.adherence import get_agent_infractions

router = APIRouter(prefix="/reports", tags=["Reports & Exports"])

@router.get("/adherence/daily/csv")
def export_daily_adherence_csv(
    report_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    target_date = report_date or date.today()
    csv_file = generate_daily_adherence_csv(db=db, target_date=target_date)

    filename = f"aderencia_diaria_{target_date.strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        iter([csv_file.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/adherence/infractions/csv")
def export_infractions_csv(
    target_date: Optional[date] = None,
    agent_id: Optional[int] = None,
    grace_period_minutes: int = 0,
    db: Session = Depends(get_db)
):
    query_date = target_date or date.today()

    #1- Determina quais agentes processar
    if agent_id:
        agents = db.query(models.Agent).filter(models.Agent.id == agent_id).all()
        if not agents:
            raise HTTPException(status_code=404, detail=f"Agente {agent_id} nao encontrado.")
        else:
            agents = db.query(models.Agent).all()

        #2- Configura buffer em memória para o CSV
        output = io.StringIO()
        output.write("\ufeff")
        writer = csv.writer(output, delimiter=";")

        #Cabeçalho do CSV
        writer.writerow([
        "Agent ID",
        "Nome do Operador",
        "Data",
        "Bloco Planejado",
        "Status Esperado",
        "Status Realizado",
        "Inicio do Desvio",
        "Fim do Desvio",
        "Duracao (segundos)",
        "Duracao Formatada"
        ])

        total_rows = 0

        #3- Itera sobre os agentes e extrai as informações
        for agent in agents:
            infractions_data = get_agent_infractions(db=db, agent_id=agent_id, target_date=query_date, grace_period_minutes=grace_period_minutes)
            if not infractions_data or not infractions_data.get("infractions"):
                continue

            for item in infractions_data["infractions"]:
                writer.writerow([
                agent.name,
                query_date.strftime("%Y-%m-%d"),
                item["interval_name"],
                item["expected_status"].value if hasattr(item["expected_status"], "value") else str(item["expected_status"]),
                item["actual_status"].value if hasattr(item["actual_status"], "value") else str(item["actual_status"]),
                item["start_time"].strftime("%H:%M:%S"),
                item["end_time"].strftime("%H:%M:%S"),
                item["duration_seconds"],
                item["duration_formatted"]
                ])
                total_rows += 1

        output.seek(0)
        filename = f"infracoes_{query_date.strftime('%Y%m%d')}.csv"
        if agent_id:
            filename = f"infracoes_agente_{agent_id}_{query_date.strftime('%Y%m%d')}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )