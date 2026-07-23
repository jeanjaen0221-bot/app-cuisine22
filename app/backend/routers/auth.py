from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from ..database import get_session
from ..models import User, UserCreate, UserCredentials, UserRead, UserUpdate
from ..security import create_access_token, decode_access_token, hash_password, normalize_email, validate_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


def serialize_user(user: User) -> UserRead:
    # NULL can exist only on a legacy owner account during migration; preserve
    # its administrative access rather than accidentally hiding its menu.
    return UserRead(id=user.id, email=user.email, role=user.role or "admin", permissions=[item for item in (user.permissions or "").split(",") if item])


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


def require_admin(user: User = Depends(current_user)) -> User:
    if (user.role or "admin") != "admin":
        raise HTTPException(status_code=403, detail="Accès administrateur requis.")
    return user


def clean_permissions(permissions: list[str]) -> str:
    allowed = {"dashboard", "reservations", "rooftop", "floorplan", "menu", "orders", "suppliers", "billing", "incidents", "settings", "users"}
    return ",".join(sorted({item for item in permissions if item in allowed}))


@router.get("/users", response_model=list[UserRead])
def list_users(session: Session = Depends(get_session), _: User = Depends(require_admin)):
    return [serialize_user(user) for user in session.exec(select(User).order_by(User.created_at)).all()]


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, session: Session = Depends(get_session), _: User = Depends(require_admin)):
    email = normalize_email(payload.email)
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Adresse e-mail invalide.")
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status_code=409, detail="Cette adresse e-mail est déjà utilisée.")
    validate_password(payload.password)
    role = "admin" if payload.role == "admin" else "member"
    user = User(email=email, password_hash=hash_password(payload.password), role=role, permissions=clean_permissions(payload.permissions))
    session.add(user); session.commit(); session.refresh(user)
    return serialize_user(user)


@router.put("/users/{user_id}", response_model=UserRead)
def update_user(user_id: uuid.UUID, payload: UserUpdate, session: Session = Depends(get_session), admin: User = Depends(require_admin)):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    if payload.role is not None:
        if user.id == admin.id and payload.role != "admin":
            raise HTTPException(status_code=422, detail="Vous ne pouvez pas retirer votre propre accès administrateur.")
        user.role = "admin" if payload.role == "admin" else "member"
    if payload.permissions is not None: user.permissions = clean_permissions(payload.permissions)
    if payload.password is not None: validate_password(payload.password); user.password_hash = hash_password(payload.password)
    session.add(user); session.commit(); session.refresh(user)
    return serialize_user(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: uuid.UUID, session: Session = Depends(get_session), admin: User = Depends(require_admin)):
    if user_id == admin.id:
        raise HTTPException(status_code=422, detail="Vous ne pouvez pas supprimer votre propre compte.")
    user = session.get(User, user_id)
    if user is None: raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    if user.role == "admin" and len(session.exec(select(User).where(User.role == "admin")).all()) <= 1:
        raise HTTPException(status_code=422, detail="Au moins un administrateur doit être conservé.")
    session.delete(user); session.commit()
