import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

import models
from database import get_db

SECRET_KEY = os.getenv("SECRET_KEY", "sellora-dev-secret-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(slug: str) -> str:
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": slug, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_shop(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> models.Shop:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "لطفاً وارد شوید")
    token = authorization[7:]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        slug = payload.get("sub")
        if not slug:
            raise HTTPException(401, "توکن نامعتبر")
    except jwt.PyJWTError:
        raise HTTPException(401, "توکن منقضی شده یا نامعتبر")
    shop = db.query(models.Shop).filter(models.Shop.slug == slug).first()
    if not shop:
        raise HTTPException(401, "فروشگاه پیدا نشد")
    return shop