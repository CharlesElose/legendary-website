# Authentication and User Management Service
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
import random
import string

from ..models.models import User, UserRole, Wallet, Gig, GigStatus
from ..schemas.schemas import UserCreate, UserUpdate
from ..core.security import get_password_hash, verify_password, create_access_token, create_refresh_token
from ..core.config import settings


class AuthService:
    """Service for authentication and user management"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def register_user(self, user_data: UserCreate) -> User:
        """Register a new user"""
        # Check if email already exists
        existing_user = self.db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise ValueError("Email already registered")
        
        # Create user
        hashed_password = get_password_hash(user_data.password)
        db_user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            role=user_data.role,
        )
        
        self.db.add(db_user)
        self.db.flush()  # Get the user ID
        
        # Create wallet for the user
        wallet = Wallet(user_id=db_user.id)
        self.db.add(wallet)
        self.db.commit()
        self.db.refresh(db_user)
        
        return db_user
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        return user
    
    def create_tokens(self, user: User) -> dict:
        """Create access and refresh tokens for user"""
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email, "role": user.role.value}
        )
        refresh_token = create_refresh_token(
            data={"sub": str(user.id), "email": user.email, "role": user.role.value}
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": user.id,
            "role": user.role
        }
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return self.db.query(User).filter(User.email == email).first()
    
    def update_user_profile(self, user_id: int, update_data: UserUpdate) -> User:
        """Update user profile"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(user, field, value)
        
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def generate_verification_code(self) -> str:
        """Generate unique verification code"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    def request_verification(self, user_id: int, social_platform: str, username: str, profile_url: str) -> str:
        """Request account verification"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        verification_code = self.generate_verification_code()
        user.verification_code = verification_code
        
        # In production, this would scrape the social bio and check for the code
        # For now, we'll simulate the process
        # TODO: Implement actual social media scraping
        
        self.db.commit()
        
        return verification_code
    
    def complete_verification(self, user_id: int, code: str) -> bool:
        """Complete verification if code matches"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        
        if user.verification_code == code:
            user.is_verified = True
            user.has_gold_badge = True
            user.verification_code = None
            self.db.commit()
            return True
        
        return False
    
    def set_featured_status(self, user_id: int, is_featured: bool, expires_days: int = 7) -> User:
        """Set featured status for creator spotlight"""
        from datetime import datetime, timedelta
        
        user = self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        user.is_featured = is_featured
        if is_featured:
            user.featured_expires_at = datetime.utcnow() + timedelta(days=expires_days)
        else:
            user.featured_expires_at = None
        
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def get_verified_creators(self, limit: int = 20, shuffle: bool = True) -> List[User]:
        """Get verified creators with fair shuffle algorithm"""
        query = self.db.query(User).filter(
            User.role == UserRole.CREATOR,
            User.is_verified == True,
            User.is_active == True
        )
        
        # Add featured creators first
        featured = query.filter(User.is_featured == True).all()
        
        # Get remaining verified creators
        others = query.filter(User.is_featured == False).all()
        
        if shuffle:
            random.shuffle(others)
        
        # Combine: featured first, then shuffled others
        result = featured + others
        
        return result[:limit]
    
    def get_leaderboard(self, limit: int = 10) -> List[User]:
        """Get top earners leaderboard"""
        return self.db.query(User).filter(
            User.role == UserRole.CREATOR,
            User.is_active == True
        ).order_by(User.total_earnings.desc()).limit(limit).all()
    
    def get_user_analytics(self, user_id: int) -> dict:
        """Get analytics for a user"""
        user = self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Count gigs
        if user.role == UserRole.CREATOR:
            gigs_completed = self.db.query(Gig).filter(
                Gig.creator_id == user_id,
                Gig.status == GigStatus.APPROVED
            ).count()
            
            gigs_in_progress = self.db.query(Gig).filter(
                Gig.creator_id == user_id,
                Gig.status.in_([GigStatus.IN_PROGRESS, GigStatus.SUBMITTED])
            ).count()
        else:
            gigs_completed = self.db.query(Gig).filter(
                Gig.business_id == user_id,
                Gig.status == GigStatus.APPROVED
            ).count()
            
            gigs_in_progress = self.db.query(Gig).filter(
                Gig.business_id == user_id,
                Gig.status.in_([GigStatus.IN_PROGRESS, GigStatus.SUBMITTED])
            ).count()
        
        return {
            "user_id": user.id,
            "total_earnings": user.total_earnings,
            "total_spent": user.total_spent,
            "gigs_completed": gigs_completed,
            "gigs_in_progress": gigs_in_progress,
            "avg_rating": user.avg_rating,
        }
