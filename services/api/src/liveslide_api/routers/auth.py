from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import User
from ..schemas import LoginRequest
from ..security import check_password, create_token
from ..services.audit import write_audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "role": user.role,
            "display_name": user.display_name}


@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    ok = bool(user and check_password(request.password, user.password_hash))
    write_audit(db, request.email, "login_success" if ok else "login_failure",
                "user", user.id if user else request.email, {})
    db.commit()
    if not ok:
        raise HTTPException(401, detail={"code": "invalid_credentials", "message": "Email or password is incorrect"})
    return {"access_token": create_token(user.id, user.role), "token_type": "bearer",
            "role": user.role, "display_name": user.display_name}
