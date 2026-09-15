from datetime import datetime, timedelta, timezone
from typing import Optional, Any
import bcrypt
import jwt

# Configurações do JWT
SECRET_KEY = "sua_chave_secreta_super_segura_mude_em_producao"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 horas


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto confere com o hash salvo."""
    pwd_bytes = plain_password[:72].encode("utf-8")
    hash_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(pwd_bytes, hash_bytes)


def get_password_hash(password: str) -> str:
    """Gera o hash seguro da senha com bcrypt nativo."""
    pwd_bytes = password[:72].encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def create_access_token(
    subject: Any,
    role: str,
    agent_id: Optional[int] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Gera o token JWT assinado."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {
        "sub": str(subject),
        "role": role,
        "agent_id": agent_id,
        "exp": expire,
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)