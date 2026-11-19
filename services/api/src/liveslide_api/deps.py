import hmac

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .config import API_SERVICE_KEY
from .db import get_db
from .models import User
from .security import decode_token


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, detail={"code": "unauthorized", "message": "Bearer token required"})
    try:
        claims = decode_token(authorization[7:])
    except ValueError:
        raise HTTPException(401, detail={"code": "unauthorized", "message": "Invalid or expired token"})
    user = db.get(User, claims["sub"])
    if not user:
        raise HTTPException(401, detail={"code": "unauthorized", "message": "User not found"})
    return user


def require_role(*roles: str):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, detail={"code": "forbidden", "message": "This role cannot perform this action"})
        return user
    return dependency


def require_service_key(x_service_key: str | None = Header(default=None)):
    if not x_service_key or not hmac.compare_digest(x_service_key, API_SERVICE_KEY):
        raise HTTPException(403, detail={"code": "service_key_required", "message": "Valid X-Service-Key required"})
