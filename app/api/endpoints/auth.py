from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.models import User
from app.schemas.auth import UserCreate, UserResponse, Token

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def resgister_user(user_in: UserCreate, db: Session = Depends(get_db)):
    """Registra um novo usuario no sistema (Agente, Supervisor ou ADMin)"""
    user_exists = db.query(User).filter((User.username == user_in.username) | (User.email == user_in.email)).first()
    if user_exists:
        raise HTTPException(status_code=400, detail="Usuario ou email já cadastrado.")

    new_user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
        agent_id=user_in.agent_id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Converte explicitamente o Enum para string antes de gerar o token
    user_role_str = user.role.value if hasattr(user.role, "value") else str(user.role)

    access_token = create_access_token(
        subject=user.username,
        role=user_role_str,
        agent_id=user.agent_id
    )
    return {"access_token": access_token, "token_type": "bearer"}