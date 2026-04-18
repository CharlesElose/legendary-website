# Authentication Routes
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional

from ..core.database import get_db
from ..core.security import decode_token
from ..schemas.schemas import (
    UserCreate, UserLogin, Token, UserResponse, UserUpdate, 
    VerificationRequest, VerificationResponse, UserRoleEnum
)
from ..services.auth_service import AuthService
from ..models.models import UserRole

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Get current authenticated user"""
    payload = decode_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = int(payload["sub"])
    auth_service = AuthService(db)
    user = auth_service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    auth_service = AuthService(db)
    
    try:
        user = auth_service.register_user(user_data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login and get access token"""
    auth_service = AuthService(db)
    
    user = auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    tokens = auth_service.create_tokens(user)
    return tokens


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: UserResponse = Depends(get_current_user)):
    """Get current user information"""
    return current_user


@router.put("/profile", response_model=UserResponse)
def update_profile(
    profile_data: UserUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user profile"""
    auth_service = AuthService(db)
    
    try:
        user = auth_service.update_user_profile(current_user.id, profile_data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verification/request", response_model=dict)
def request_verification(
    verification_data: VerificationRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Request account verification"""
    auth_service = AuthService(db)
    
    try:
        code = auth_service.request_verification(
            current_user.id,
            verification_data.social_platform,
            verification_data.username,
            verification_data.profile_url
        )
        return {
            "message": "Verification code generated. Add this code to your social media bio.",
            "verification_code": code
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verification/complete", response_model=VerificationResponse)
def complete_verification(
    code: str,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Complete verification with code"""
    auth_service = AuthService(db)
    
    success = auth_service.complete_verification(current_user.id, code)
    
    if success:
        return VerificationResponse(
            is_verified=True,
            message="Congratulations! Your account has been verified with a gold badge.",
            has_gold_badge=True
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid verification code")


@router.post("/logout")
def logout(current_user: UserResponse = Depends(get_current_user)):
    """Logout (client should delete token)"""
    return {"message": "Successfully logged out"}
