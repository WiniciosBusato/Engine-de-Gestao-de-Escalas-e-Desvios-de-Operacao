import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from datetime import datetime, date, time
from app.core.database import SessionLocal
from app.models import models

def popular_banco():
    db = SessionLocal()
    try:
        print("Iniciando carga de dados em massa...")

        # 1. Agentes utilizando skill_group
        nomes = [
            ("Carlos Eduardo", "carlos.eduardo@empresa.com", "Suporte N1"),
            ("Mariana Souza", "mariana.souza@empresa.com", "Suporte N1"),
            ("Felipe Santos", "felipe.santos@empresa.com", "Suporte N2"),
            ("Beatriz Lima", "beatriz.lima@empresa.com", "Suporte N2"),
            ("Rodrigo Martins", "rodrigo.martins@empresa.com", "Backoffice"),
            ("Juliana Paes", "juliana.paes@empresa.com", "Backoffice"),
            ("Gabriel Costa", "gabriel.costa@empresa.com", "Retenção"),
            ("Fernanda Rocha", "fernanda.rocha@empresa.com", "Retenção"),
            ("Lucas Oliveira", "lucas.oliveira@empresa.com", "Suporte N1"),
            ("Camila Ribeiro", "camila.ribeiro@empresa.com", "Suporte N2"),
        ]

        agentes_criados = []
        for nome, email, skill in nomes:
            agente = db.query(models.Agent).filter(models.Agent.email == email).first()
            if not agente:
                agente = models.Agent(name=nome, email=email, skill_group=skill)
                db.add(agente)
                db.flush()
            agentes_criados.append(agente)

        db.commit()
        print(f"Total de {len(agentes_criados)} agentes processados.")

        # 2. Escalas alinhadas com as colunas reais do modelo PlannedSchedule
        hoje = datetime.combine(date.today(), time.min)

        turnos = [
            {
                "shift_start": time(8, 0),
                "shift_end": time(14, 0),
                "break_1_start": time(10, 0),
                "break_1_end": time(10, 15),
                "meal_start": time(12, 0),
                "meal_end": time(12, 30),
                "break_2_start": time(13, 30),
                "break_2_end": time(13, 45)
            },
            {
                "shift_start": time(14, 0),
                "shift_end": time(20, 0),
                "break_1_start": time(16, 0),
                "break_1_end": time(16, 15),
                "meal_start": time(18, 0),
                "meal_end": time(18, 30),
                "break_2_start": time(19, 30),
                "break_2_end": time(19, 45)
            }
        ]

        escalas_criadas = 0
        for idx, agente in enumerate(agentes_criados):
            escala_existente = db.query(models.PlannedSchedule).filter(
                models.PlannedSchedule.agent_id == agente.id,
                models.PlannedSchedule.date == hoje
            ).first()

            if not escala_existente:
                t = turnos[idx % len(turnos)]
                escala = models.PlannedSchedule(
                    agent_id=agente.id,
                    date=hoje,
                    shift_start=t["shift_start"],
                    shift_end=t["shift_end"],
                    break_1_start=t["break_1_start"],
                    break_1_end=t["break_1_end"],
                    meal_start=t["meal_start"],
                    meal_end=t["meal_end"],
                    break_2_start=t["break_2_start"],
                    break_2_end=t["break_2_end"]
                )
                db.add(escala)
                escalas_criadas += 1

        db.commit()
        print(f"Total de {escalas_criadas} escalas diárias cadastradas.")

        # 3. StatusLogs utilizando o Enum AgentStatus
        logs_criados = 0
        for idx, agente in enumerate(agentes_criados):
            status_enum = models.AgentStatus.AVAILABLE if idx % 2 == 0 else models.AgentStatus.BREAK
            log = models.StatusLog(
                agent_id=agente.id,
                status=status_enum,
                timestamp=datetime.utcnow()
            )
            db.add(log)
            logs_criados += 1

        db.commit()
        print(f"Total de {logs_criados} logs de status gerados.")
        print("Carga de dados concluída com sucesso!")

    except Exception as e:
        db.rollback()
        print(f"Erro ao popular dados: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    popular_banco()
