import io
import csv
from datetime import date
from sqlalchemy.orm import Session
from app.models import models
from app.services.adherence import calculate_daily_adherence

def generate_daily_adherence_csv(db: Session, target_date: date) -> io.StringIO:
    """Gera um arquivo CSV contendo os dados de aderência consolidada do dia."""
    output = io.StringIO()
    #Adiciona o BOM UTF-8 (\ufeff) para que acentuações abram corretamente direto no Excel
    output.write("\ufeff")

    writer = csv.writer(output, delimiter=";")

    #Cabeçalho do relatório
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