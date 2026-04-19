import datetime
import os
from typing import Optional

import jwt
from fastapi import Request
from passlib.context import CryptContext

# In a real app, this should be in .env and config.py
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key-for-dev-only")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

import hashlib
import bcrypt


def _pre_hash(password: str) -> str:
    """SHA-256 pre-hash so any password length works with bcrypt's 72-byte limit."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pre = _pre_hash(plain_password).encode("utf-8")
    return bcrypt.checkpw(pre, hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    pre = _pre_hash(password).encode("utf-8")
    hashed = bcrypt.hashpw(pre, bcrypt.gensalt())
    return hashed.decode("utf-8")


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user_optional(request: Request) -> Optional[int]:
    """Dependencies to read auth header and return user_id if valid."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[int] = payload.get("sub")
        if user_id is None:
            return None
        return int(user_id)
    except Exception:
        return None
