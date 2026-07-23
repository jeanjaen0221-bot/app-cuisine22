from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from ..database import get_session
from ..models import User, UserCredentials, UserRead
from ..security import create_access_token, decode_access_token, hash_password, normalize_email, validate_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


def serialize_user(user: User) -> UserRead:
    return UserRead(id=user.id, email=user.email)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme), session: Session = Depends(get_session)) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentification requise.")
    try:
        user_id = uuid.UUID(decode_access_token(credentials.credentials))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalide ou expirée.")
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalide ou expirée.")
    return user


@router.get("/status")
def auth_status(session: Session = Depends(get_session)):
    return {"setup_required": session.exec(select(User.id).limit(1)).first() is None}


@router.post("/setup", status_code=status.HTTP_201_CREATED)
def setup_account(credentials: UserCredentials, session: Session = Depends(get_session)):
    if session.exec(select(User.id).limit(1)).first() is not None:
        raise HTTPException(status_code=409, detail="Un compte existe déjà.")
    email = normalize_email(credentials.email)
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Adresse e-mail invalide.")
    validate_password(credentials.password)
    user = User(email=email, password_hash=hash_password(credentials.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"access_token": create_access_token(str(user.id)), "token_type": "bearer", "user": serialize_user(user)}


@router.post("/login")
def login(credentials: UserCredentials, session: Session = Depends(get_session)):
    email = normalize_email(credentials.email)
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Adresse e-mail ou mot de passe incorrect.")
    user.last_login_at = datetime.utcnow()
    session.add(user)
    session.commit()
    return {"access_token": create_access_token(str(user.id)), "token_type": "bearer", "user": serialize_user(user)}


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(current_user)):
    return serialize_user(user)
