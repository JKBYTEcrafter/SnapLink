import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request

from app.database.database import get_db
from app.schemas.auth import ForgotPasswordRequest, ResetPasswordRequest, TokenResponse, UserCreate, UserLogin, UserProfile
from app.services import auth_service
from app.utils.security import create_access_token, get_current_user_optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/signup", response_model=UserProfile, status_code=status.HTTP_201_CREATED)
async def signup(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> UserProfile:
    """Create a new user."""
    try:
        user = await auth_service.create_user(db, payload)
        return UserProfile(id=user.id, email=user.email)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )

@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Authenticate and get a token."""
    try:
        user = await auth_service.authenticate_user(db, payload)
        access_token = create_access_token(data={"sub": str(user.id)})
        return TokenResponse(access_token=access_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc)
        )

@router.get("/me", response_model=UserProfile)
async def get_me(request: Request, db: AsyncSession = Depends(get_db)) -> UserProfile:
    """Get current user profile."""
    user_id = get_current_user_optional(request)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated."
        )
    user = await auth_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserProfile(id=user.id, email=user.email)

@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Request a password reset OTP."""
    try:
        await auth_service.create_password_reset_otp(db, payload)
        return {"message": "If an account exists, an OTP has been sent."}
    except ValueError as exc:
        # We disclose errors here to help the user test the mock flow easily
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Reset password using the OTP."""
    try:
        await auth_service.reset_password_with_otp(db, payload)
        return {"message": "Password has been updated successfully."}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
