# Pydantic Schemas for API validation
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class UserRoleEnum(str, Enum):
    CREATOR = "creator"
    BUSINESS = "business"
    ADMIN = "admin"


class GigStatusEnum(str, Enum):
    OPEN = "open"
    FUNDED = "funded"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


# ============ AUTH SCHEMAS ============

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    role: UserRoleEnum = UserRoleEnum.CREATOR


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    role: UserRoleEnum


class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None
    role: Optional[UserRoleEnum] = None


# ============ USER SCHEMAS ============

class SocialLinks(BaseModel):
    instagram: Optional[str] = None
    twitter: Optional[str] = None
    youtube: Optional[str] = None
    linkedin: Optional[str] = None
    website: Optional[str] = None
    other: Optional[str] = None


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRoleEnum
    bio: Optional[str] = None
    niche: Optional[str] = None
    avatar_url: Optional[str] = None
    social_links: Optional[Dict[str, str]] = None
    is_verified: bool = False
    has_gold_badge: bool = False


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    bio: Optional[str] = None
    niche: Optional[str] = None
    avatar_url: Optional[str] = None
    social_links: Optional[Dict[str, str]] = None


class UserResponse(UserBase):
    id: int
    is_featured: bool = False
    total_earnings: float = 0.0
    total_spent: float = 0.0
    gigs_completed: int = 0
    avg_rating: float = 0.0
    is_active: bool = True
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserWithWallet(UserResponse):
    wallet: Optional["WalletResponse"] = None


# ============ WALLET SCHEMAS ============

class WalletBase(BaseModel):
    available_balance: float = 0.0
    locked_balance: float = 0.0
    pending_balance: float = 0.0
    currency: str = "NGN"


class WalletResponse(WalletBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DepositRequest(BaseModel):
    amount: float = Field(..., gt=0)
    email: EmailStr


class DepositResponse(BaseModel):
    deposit_id: int
    amount: float
    paystack_reference: str
    authorization_url: str
    status: str


class WithdrawalRequest(BaseModel):
    amount: float = Field(..., gt=0)
    bank_account_number: str
    bank_code: str
    account_name: str


class WithdrawalResponse(BaseModel):
    withdrawal_id: int
    amount: float
    status: str
    message: str


# ============ GIG SCHEMAS ============

class GigBase(BaseModel):
    title: str
    description: str
    budget: float = Field(..., gt=0)
    deadline: Optional[datetime] = None


class GigCreate(GigBase):
    pass


class GigUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    budget: Optional[float] = Field(None, gt=0)
    deadline: Optional[datetime] = None
    status: Optional[GigStatusEnum] = None


class PoWSubmission(BaseModel):
    file_url: str
    file_type: str  # image, video, document, url


class GigResponse(GigBase):
    id: int
    status: GigStatusEnum
    business_id: int
    creator_id: Optional[int] = None
    platform_fee: float = 0.0
    creator_share: float = 0.0
    pow_file_url: Optional[str] = None
    pow_file_type: Optional[str] = None
    pow_submitted_at: Optional[datetime] = None
    pow_auto_release_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class GigDetailResponse(GigResponse):
    business: Optional[UserResponse] = None
    creator: Optional[UserResponse] = None


# ============ MESSAGE SCHEMAS ============

class MessageBase(BaseModel):
    content: str
    message_type: str = "text"


class MessageCreate(MessageBase):
    gig_id: int
    recipient_id: int
    attachment_url: Optional[str] = None
    attachment_type: Optional[str] = None


class MessageResponse(MessageBase):
    id: int
    gig_id: int
    sender_id: int
    recipient_id: int
    attachment_url: Optional[str] = None
    attachment_type: Optional[str] = None
    is_read: bool = False
    sent_at: datetime
    
    class Config:
        from_attributes = True


class ChatHistory(BaseModel):
    messages: List[MessageResponse]
    gig_id: int
    participants: List[UserResponse]


# ============ NOTIFICATION SCHEMAS ============

class NotificationBase(BaseModel):
    title: str
    message: str
    notification_type: str = "info"


class NotificationCreate(NotificationBase):
    related_gig_id: Optional[int] = None
    related_user_id: Optional[int] = None


class NotificationResponse(NotificationBase):
    id: int
    user_id: int
    related_gig_id: Optional[int] = None
    related_user_id: Optional[int] = None
    is_read: bool = False
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============ DISPUTE SCHEMAS ============

class DisputeBase(BaseModel):
    reason: str


class DisputeCreate(DisputeBase):
    gig_id: int


class DisputeResolution(BaseModel):
    resolution_type: str  # force_release, full_refund, partial_split
    admin_notes: str
    resolution_amount_creator: Optional[float] = None
    resolution_amount_business: Optional[float] = None


class DisputeResponse(DisputeBase):
    id: int
    gig_id: int
    created_by_id: int
    status: str
    admin_notes: Optional[str] = None
    resolution_type: Optional[str] = None
    resolution_amount_creator: Optional[float] = None
    resolution_amount_business: Optional[float] = None
    resolved_by_id: Optional[int] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ============ ANALYTICS SCHEMAS ============

class AnalyticsResponse(BaseModel):
    user_id: int
    total_earnings: float
    total_spent: float
    gigs_completed: int
    gigs_in_progress: int
    avg_rating: float
    recent_transactions: List[Dict[str, Any]]
    earnings_history: List[Dict[str, Any]]


# ============ LEADERBOARD SCHEMAS ============

class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    full_name: str
    niche: Optional[str] = None
    total_earnings: float
    gigs_completed: int
    avg_rating: float
    is_verified: bool
    has_gold_badge: bool
    avatar_url: Optional[str] = None


class LeaderboardResponse(BaseModel):
    top_earners: List[LeaderboardEntry]
    total_creators: int
    last_updated: datetime


# ============ VERIFICATION SCHEMAS ============

class VerificationRequest(BaseModel):
    social_platform: str  # instagram, twitter, etc.
    username: str
    profile_url: str


class VerificationResponse(BaseModel):
    is_verified: bool
    message: str
    has_gold_badge: bool


# Update forward references
UserWithWallet.model_rebuild()
