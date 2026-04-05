import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.schemas.auth import UserCreate, UserLogin
from app.utils.security import get_password_hash, verify_password

logger = logging.getLogger(__name__)

async def create_user(db: AsyncSession, payload: UserCreate) -> User:
    """Create a new user."""
    # Check if user exists
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise ValueError("A user with this email already exists.")

    hashed = get_password_hash(payload.password)
    user = User(email=payload.email, password_hash=hashed)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def authenticate_user(db: AsyncSession, payload: UserLogin) -> User:
    """Authenticate and return the user."""
    user = await db.scalar(select(User).where(User.email == payload.email))
    if not user:
        raise ValueError("Invalid email or password.")
    if not verify_password(payload.password, user.password_hash):
        raise ValueError("Invalid email or password.")
    return user

async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """Get a user by ID."""
    return await db.scalar(select(User).where(User.id == user_id))
