from fastapi import FastAPI
from app.core.database import engine
from app.models.models import Base
from app.api import agents

#Cria as tabelas no banco de dados caso elas não existam
Base.metadata.create_all(bind=engine)

#Instancia principal da aplicação FastAPI
app = FastAPI(
    title="WFM Engine API",
    description="Engine de Gestão de Escalas e Desvios de Operação para Control Desk",
    version="1.0.0"
)

#Adiciona as rotas de agentes na aplicação
app.include_router(agents.router)

#Endpoint raiz só para teste de APi
@app.get("/")
def read_root():
    return{"message": "WFM Engine API está rodando!"}