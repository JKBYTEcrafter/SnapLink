import logging
import random
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import PasswordResetOTP, User
from app.schemas.auth import UserCreate, UserLogin, ForgotPasswordRequest, ResetPasswordRequest
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


async def create_password_reset_otp(db: AsyncSession, payload: ForgotPasswordRequest) -> str:
    """Generate and store a 6-digit OTP for password reset."""
    # Verify user exists
    user = await db.scalar(select(User).where(User.email == payload.email))
    if not user:
        # For security, we might not want to disclose user existence, 
        # but in this case, we'll follow user's request for feedback.
        raise ValueError("If an account exists for this email, an OTP has been generated.")

    otp = "".join(random.choices(string.digits, k=6))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    otp_record = PasswordResetOTP(
        email=payload.email,
        otp_code=otp,
        expires_at=expires_at
    )
    db.add(otp_record)
    await db.commit()

    # MOCK EMAIL: Print to console
    print("\n" + "="*50)
    print(f"📧 [MOCK EMAIL] To: {payload.email}")
    print(f"🔑 Your SnapLink Password Reset OTP is: {otp}")
    print(f"⏰ This code expires in 15 minutes.")
    print("="*50 + "\n")

    return otp


async def reset_password_with_otp(db: AsyncSession, payload: ResetPasswordRequest):
    """Validate OTP and update user password."""
    # Get the latest unused OTP for this email
    stmt = (
        select(PasswordResetOTP)
        .where(PasswordResetOTP.email == payload.email)
        .where(PasswordResetOTP.otp_code == payload.otp_code)
        .where(PasswordResetOTP.is_used == 0)
        .order_by(PasswordResetOTP.expires_at.desc())
        .limit(1)
    )
    otp_record = await db.scalar(stmt)

    if not otp_record:
        raise ValueError("Invalid or expired OTP.")

    if datetime.now(timezone.utc) > otp_record.expires_at:
        raise ValueError("OTP has expired.")

    # Update user password
    user = await db.scalar(select(User).where(User.email == payload.email))
    if not user:
        raise ValueError("User not found.")

    user.password_hash = get_password_hash(payload.new_password)
    otp_record.is_used = 1
    
    await db.commit()
    return True
