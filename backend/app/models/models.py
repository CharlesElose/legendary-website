# Database Models for Creatio Marketplace
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from ..core.database import Base


class UserRole(str, enum.Enum):
    CREATOR = "creator"
    BUSINESS = "business"
    ADMIN = "admin"


class GigStatus(str, enum.Enum):
    """Advanced Gig Lifecycle State Machine"""
    OPEN = "open"  # Gig created, waiting for funding
    FUNDED = "funded"  # Escrow locked
    IN_PROGRESS = "in_progress"  # Work started
    SUBMITTED = "submitted"  # PoW uploaded, awaiting approval
    APPROVED = "approved"  # Funds released to creator
    DISPUTED = "disputed"  # Dispute raised, escrow frozen
    CANCELLED = "cancelled"  # Gig cancelled
    REFUNDED = "refunded"  # Funds returned to business


class WalletStatus(str, enum.Enum):
    AVAILABLE = "available"
    LOCKED = "locked"
    PENDING = "pending"


class User(Base):
    """User model for both Creators and Businesses"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.CREATOR)
    
    # Profile fields
    bio = Column(Text, nullable=True)
    niche = Column(String(100), nullable=True)  # Creator's specialty
    avatar_url = Column(String(500), nullable=True)
    
    # Social links (stored as JSON)
    social_links = Column(JSON, nullable=True)  # {instagram, twitter, youtube, etc.}
    
    # Verification
    is_verified = Column(Boolean, default=False)
    verification_code = Column(String(50), nullable=True)
    has_gold_badge = Column(Boolean, default=False)
    
    # Featured status (Spotlight)
    is_featured = Column(Boolean, default=False)
    featured_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Analytics
    total_earnings = Column(Float, default=0.0)
    total_spent = Column(Float, default=0.0)
    gigs_completed = Column(Integer, default=0)
    avg_rating = Column(Float, default=0.0)
    
    # Account status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    wallet = relationship("Wallet", back_populates="user", uselist=False, cascade="all, delete-orphan")
    gigs_posted = relationship("Gig", foreign_keys="Gig.business_id", back_populates="business")
    gigs_accepted = relationship("Gig", foreign_keys="Gig.creator_id", back_populates="creator")
    messages_sent = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    messages_received = relationship("Message", foreign_keys="Message.recipient_id", back_populates="recipient")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    disputes_created = relationship("Dispute", foreign_keys="Dispute.created_by_id", back_populates="created_by")
    deposits = relationship("Deposit", back_populates="user", cascade="all, delete-orphan")
    withdrawals = relationship("Withdrawal", back_populates="user", cascade="all, delete-orphan")


class Wallet(Base):
    """Centralized wallet ledger tracking balances"""
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # Balance tracking in Naira
    available_balance = Column(Float, default=0.0)  # Available for use
    locked_balance = Column(Float, default=0.0)  # Locked in escrow
    pending_balance = Column(Float, default=0.0)  # Pending withdrawal/approval
    
    currency = Column(String(3), default="NGN")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="wallet")


class Gig(Base):
    """Gig/Project model with advanced lifecycle"""
    __tablename__ = "gigs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    
    # Pricing
    budget = Column(Float, nullable=False)
    platform_fee = Column(Float, default=0.0)  # 15% of budget
    creator_share = Column(Float, default=0.0)  # 85% of budget
    
    # Lifecycle
    status = Column(Enum(GigStatus), default=GigStatus.OPEN)
    
    # Parties
    business_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Proof of Work
    pow_file_url = Column(String(500), nullable=True)
    pow_file_type = Column(String(50), nullable=True)  # image, video, document, url
    pow_submitted_at = Column(DateTime(timezone=True), nullable=True)
    pow_auto_release_date = Column(DateTime(timezone=True), nullable=True)
    
    # Timeline
    deadline = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    business = relationship("User", foreign_keys=[business_id], back_populates="gigs_posted")
    creator = relationship("User", foreign_keys=[creator_id], back_populates="gigs_accepted")
    messages = relationship("Message", back_populates="gig", cascade="all, delete-orphan")
    dispute = relationship("Dispute", back_populates="gig", uselist=False, cascade="all, delete-orphan")


class Message(Base):
    """Messaging system for business-creator communication"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    gig_id = Column(Integer, ForeignKey("gigs.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    content = Column(Text, nullable=False)
    message_type = Column(String(50), default="text")  # text, pitch, file
    
    # For file attachments
    attachment_url = Column(String(500), nullable=True)
    attachment_type = Column(String(50), nullable=True)
    
    is_read = Column(Boolean, default=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    gig = relationship("Gig", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id], back_populates="messages_sent")
    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="messages_received")


class Notification(Base):
    """In-app notification system"""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), default="info")  # info, warning, success, error
    
    # Related entities
    related_gig_id = Column(Integer, ForeignKey("gigs.id"), nullable=True)
    related_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="notifications")


class Dispute(Base):
    """Dispute resolution system"""
    __tablename__ = "disputes"

    id = Column(Integer, primary_key=True, index=True)
    gig_id = Column(Integer, ForeignKey("gigs.id"), unique=True, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    reason = Column(Text, nullable=False)
    status = Column(String(50), default="pending")  # pending, under_review, resolved
    
    # Admin resolution
    admin_notes = Column(Text, nullable=True)
    resolution_type = Column(String(50), nullable=True)  # force_release, full_refund, partial_split
    resolution_amount_creator = Column(Float, nullable=True)  # Amount to creator
    resolution_amount_business = Column(Float, nullable=True)  # Amount to business
    
    resolved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Admin who resolved
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    gig = relationship("Gig", back_populates="dispute")
    created_by = relationship("User", foreign_keys=[created_by_id], back_populates="disputes_created")


class Deposit(Base):
    """Track deposits into wallet via Paystack"""
    __tablename__ = "deposits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    amount = Column(Float, nullable=False)
    paystack_reference = Column(String(100), unique=True, nullable=False)
    status = Column(String(50), default="pending")  # pending, completed, failed
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="deposits")


class Withdrawal(Base):
    """Track withdrawals from creator wallet"""
    __tablename__ = "withdrawals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    amount = Column(Float, nullable=False)
    bank_account_number = Column(String(20), nullable=False)
    bank_code = Column(String(20), nullable=False)
    account_name = Column(String(100), nullable=False)
    
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    paystack_transfer_code = Column(String(100), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="withdrawals")
