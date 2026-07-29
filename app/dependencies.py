from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.models.user import User, UserRole
from app.utils.security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Web (session-based) ────────────────────────────────────────────────────────

def get_current_web_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.query(User).options(
        joinedload(User.module_access),
        joinedload(User.geography),
    ).filter(User.id == user_id, User.is_active == True).first()
    if user:
        request.state.audit_user_id = user.id
        request.state.audit_user_role = user.role.value
    return user


def require_web_auth(user: Optional[User] = Depends(get_current_web_user)) -> User:
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_web_roles(*roles: UserRole):
    def checker(current_user: User = Depends(require_web_auth)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return checker


# ── Mobile API (JWT Bearer) ────────────────────────────────────────────────────

def get_current_api_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    user = db.query(User).options(
        joinedload(User.geography),
    ).filter(User.id == int(user_id), User.is_active == True).first()
    if not user or payload.get("ver") != user.token_version:
        return None
    request.state.audit_user_id = user.id
    request.state.audit_user_role = user.role.value
    return user


def require_api_auth(user: Optional[User] = Depends(get_current_api_user)) -> User:
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


def require_api_roles(*roles: UserRole):
    def checker(current_user: User = Depends(require_api_auth)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return checker


def require_restricted_module_web_access(current_user: User = Depends(require_web_auth)) -> User:
    if not current_user.can_access_restricted_modules:
        raise HTTPException(
            status_code=403,
            detail="Access restricted: Beat creation, Expenses, Timesheets, and Material Requests require Admin or Territory Manager role with assigned Geography >= Region."
        )
    return current_user


def require_restricted_module_api_access(current_user: User = Depends(require_api_auth)) -> User:
    if not current_user.can_access_restricted_modules:
        raise HTTPException(
            status_code=403,
            detail="Access restricted: Beat creation, Expenses, Timesheets, and Material Requests require Admin or Territory Manager role with assigned Geography >= Region."
        )
    return current_user
