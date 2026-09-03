import io
import csv
from datetime import date
from sqlalchemy.orm import Session
from app.models import models
from app.services.adherence import calculate_daily_adherence

def generate_daily_adherence_csv(db: Session, target_date: date) -> io.StringIO:
    """Gera um arquivo CSV contendo os dados de aderência consolidada do dia."""
    output = io.StringIO()
    # Adiciona o BOM UTF-8 (\ufeff) para correta exibição de caracteres com acentuação no Excel
    output.write("\ufeff")
    
    writer = csv.writer(output, delimiter=";")
    
    # Cabeçalho do relatório
    writer.writerow([
        "ID Agente",
        "Nome",
        "Grupo / Skill",
        "Data",
        "Intervalo",
        "Início Previsto",
        "Fim Previsto",
        "Segundos Planejados",
        "Segundos Aderentes",
        "Aderência (%)",
        "Aderência Total Diária (%)"
    ])

    agents = db.query(models.Agent).all()

    for agent in agents:
        result = calculate_daily_adherence(db=db, agent_id=agent.id, target_date=target_date)
        
        if not result:
            # Agente sem escala cadastrada para a data solicitada
            writer.writerow([
                agent.id,
                agent.name,
                agent.skill_group,
                target_date.strftime("%Y-%m-%d"),
                "Sem escala cadastrada",
                "-",
                "-",
                0,
                0,
                "0.00%",
                "0.00%"
            ])
            continue

        overall_rate = result["overall_adherence_rate"]

        for interval in result["intervals"]:
            writer.writerow([
                agent.id,
                agent.name,
                agent.skill_group,
                target_date.strftime("%Y-%m-%d"),
                interval["interval_type"],
                interval["planned_start"],
                interval["planned_end"],
                interval["planned_seconds"],
                interval["adherent_seconds"],
                f"{interval['adherence_rate']:.2f}%",
                f"{overall_rate:.2f}%"
            ])

    output.seek(0)
    return output