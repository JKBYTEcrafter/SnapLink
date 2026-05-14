import logging
import random
import string
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.models import PasswordResetOTPDoc, UserDoc, doc_to_otp, doc_to_user
from app.schemas.auth import ForgotPasswordRequest, ResetPasswordRequest, UserCreate, UserLogin
from app.utils.id_generator import generate_id
from app.utils.security import get_password_hash, verify_password

logger = logging.getLogger(__name__)


async def create_user(db: AsyncIOMotorDatabase, payload: UserCreate) -> UserDoc:
    """Create a new user."""
    existing = await db.users.find_one({"email": payload.email})
    if existing:
        raise ValueError("A user with this email already exists.")

    user_id = generate_id()
    hashed = get_password_hash(payload.password)
    doc = {
        "_id": user_id,
        "email": payload.email,
        "password_hash": hashed,
        "created_at": datetime.now(tz=timezone.utc),
    }
    await db.users.insert_one(doc)
    return doc_to_user(doc)


async def authenticate_user(db: AsyncIOMotorDatabase, payload: UserLogin) -> UserDoc:
    """Authenticate and return the user."""
    doc = await db.users.find_one({"email": payload.email})
    if not doc:
        raise ValueError("Invalid email or password.")
    if not verify_password(payload.password, doc["password_hash"]):
        raise ValueError("Invalid email or password.")
    return doc_to_user(doc)


async def get_user_by_id(db: AsyncIOMotorDatabase, user_id: int) -> UserDoc | None:
    """Get a user by ID."""
    doc = await db.users.find_one({"_id": user_id})
    if doc is None:
        return None
    return doc_to_user(doc)


async def create_password_reset_otp(
    db: AsyncIOMotorDatabase, payload: ForgotPasswordRequest
) -> str:
    """Generate and store a 6-digit OTP for password reset."""
    user = await db.users.find_one({"email": payload.email})
    if not user:
        raise ValueError("If an account exists for this email, an OTP has been generated.")

    otp = "".join(random.choices(string.digits, k=6))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    await db.password_reset_otps.insert_one({
        "email": payload.email,
        "otp_code": otp,
        "expires_at": expires_at,
        "is_used": 0,
    })

    # MOCK EMAIL: Print to console
    print("\n" + "=" * 50)
    print(f"📧 [MOCK EMAIL] To: {payload.email}")
    print(f"🔑 Your SnapLink Password Reset OTP is: {otp}")
    print(f"⏰ This code expires in 15 minutes.")
    print("=" * 50 + "\n")

    return otp


async def reset_password_with_otp(
    db: AsyncIOMotorDatabase, payload: ResetPasswordRequest
) -> bool:
    """Validate OTP and update user password."""
    now = datetime.now(timezone.utc)

    otp_doc = await db.password_reset_otps.find_one({
        "email": payload.email,
        "otp_code": payload.otp_code,
        "is_used": 0,
        "expires_at": {"$gt": now},
    })

    if not otp_doc:
        raise ValueError("Invalid or expired OTP.")

    user = await db.users.find_one({"email": payload.email})
    if not user:
        raise ValueError("User not found.")

    # Update password and mark OTP as used
    from bson import ObjectId
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": get_password_hash(payload.new_password)}},
    )
    await db.password_reset_otps.update_one(
        {"_id": otp_doc["_id"]},
        {"$set": {"is_used": 1}},
    )
    return True
