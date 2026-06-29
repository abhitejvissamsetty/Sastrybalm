from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.utils.security import verify_password


def authenticate_user(db: Session, login: str, password: str) -> Optional[User]:
    """Accept username, email, or phone number as the login identifier."""
    user = (
        db.query(User)
        .filter((User.username == login) | (User.email == login) | (User.phone == login))
        .first()
    )
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

