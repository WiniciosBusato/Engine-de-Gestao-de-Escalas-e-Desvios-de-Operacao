from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Trocamos para o SQLite local. Ele vai criar um arquivo wfm_engine.db na raiz do projeto.
SQLALCHEMY_DATABASE_URL = "sqlite:///./wfm_engine.db"

# O SQLite exige esse connect_args para funcionar bem com as requisições do FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()