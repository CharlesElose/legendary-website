# Analytics and Leaderboard Routes
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime

from ..core.database import get_db
from ..schemas.schemas import AnalyticsResponse, LeaderboardResponse, LeaderboardEntry, UserResponse
from ..services.auth_service import AuthService
from ..models.models import User, UserRole, Gig, GigStatus, Wallet, Deposit, Withdrawal
from .auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/my-analytics", response_model=AnalyticsResponse)
def get_my_analytics(
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's analytics"""
    auth_service = AuthService(db)
    
    try:
        analytics = auth_service.get_user_analytics(current_user.id)
        
        # Get recent transactions
        recent_transactions = []
        
        # Deposits
        deposits = db.query(Deposit).filter(
            Deposit.user_id == current_user.id
        ).order_by(Deposit.created_at.desc()).limit(5).all()
        
        for d in deposits:
            recent_transactions.append({
                "type": "deposit",
                "amount": d.amount,
                "status": d.status,
                "date": d.created_at
            })
        
        # Withdrawals
        withdrawals = db.query(Withdrawal).filter(
            Withdrawal.user_id == current_user.id
        ).order_by(Withdrawal.created_at.desc()).limit(5).all()
        
        for w in withdrawals:
            recent_transactions.append({
                "type": "withdrawal",
                "amount": -w.amount,
                "status": w.status,
                "date": w.created_at
            })
        
        # Sort by date
        recent_transactions.sort(key=lambda x: x["date"], reverse=True)
        
        # Earnings history (simplified)
        earnings_history = []
        gigs = db.query(Gig).filter(
            Gig.creator_id == current_user.id,
            Gig.status == GigStatus.APPROVED
        ).order_by(Gig.completed_at.desc()).limit(10).all()
        
        for gig in gigs:
            earnings_history.append({
                "gig_title": gig.title,
                "amount": gig.creator_share,
                "date": gig.completed_at
            })
        
        return AnalyticsResponse(
            user_id=current_user.id,
            total_earnings=analytics["total_earnings"],
            total_spent=analytics["total_spent"],
            gigs_completed=analytics["gigs_completed"],
            gigs_in_progress=analytics["gigs_in_progress"],
            avg_rating=analytics["avg_rating"],
            recent_transactions=recent_transactions[:10],
            earnings_history=earnings_history
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/leaderboard", response_model=LeaderboardResponse)
def get_leaderboard(
    limit: int = 10,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get top earners leaderboard"""
    auth_service = AuthService(db)
    
    top_creators = auth_service.get_leaderboard(limit=limit)
    
    leaderboard_entries = []
    for rank, creator in enumerate(top_creators, 1):
        entry = LeaderboardEntry(
            rank=rank,
            user_id=creator.id,
            full_name=creator.full_name,
            niche=creator.niche,
            total_earnings=creator.total_earnings,
            gigs_completed=creator.gigs_completed,
            avg_rating=creator.avg_rating,
            is_verified=creator.is_verified,
            has_gold_badge=creator.has_gold_badge,
            avatar_url=creator.avatar_url
        )
        leaderboard_entries.append(entry)
    
    # Count total creators
    total_creators = db.query(User).filter(
        User.role == UserRole.CREATOR,
        User.is_active == True
    ).count()
    
    return LeaderboardResponse(
        top_earners=leaderboard_entries,
        total_creators=total_creators,
        last_updated=datetime.utcnow()
    )


@router.get("/creators", response_model=List[dict])
def get_verified_creators(
    limit: int = 20,
    shuffle: bool = True,
    niche: str = None,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get verified creators with fair shuffle algorithm"""
    auth_service = AuthService(db)
    
    creators = auth_service.get_verified_creators(limit=limit, shuffle=shuffle)
    
    result = []
    for creator in creators:
        if niche and creator.niche != niche:
            continue
        
        result.append({
            "id": creator.id,
            "full_name": creator.full_name,
            "niche": creator.niche,
            "bio": creator.bio,
            "is_verified": creator.is_verified,
            "has_gold_badge": creator.has_gold_badge,
            "is_featured": creator.is_featured,
            "total_earnings": creator.total_earnings,
            "gigs_completed": creator.gigs_completed,
            "avg_rating": creator.avg_rating,
            "avatar_url": creator.avatar_url,
            "social_links": creator.social_links
        })
    
    return result


@router.get("/marketplace-stats")
def get_marketplace_stats(
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get overall marketplace statistics"""
    # Total creators
    total_creators = db.query(User).filter(
        User.role == UserRole.CREATOR,
        User.is_active == True
    ).count()
    
    # Total businesses
    total_businesses = db.query(User).filter(
        User.role == UserRole.BUSINESS,
        User.is_active == True
    ).count()
    
    # Verified creators
    verified_creators = db.query(User).filter(
        User.role == UserRole.CREATOR,
        User.is_verified == True,
        User.is_active == True
    ).count()
    
    # Active gigs
    active_gigs = db.query(Gig).filter(
        Gig.status.in_([GigStatus.OPEN, GigStatus.FUNDED, GigStatus.IN_PROGRESS])
    ).count()
    
    # Completed gigs
    completed_gigs = db.query(Gig).filter(
        Gig.status == GigStatus.APPROVED
    ).count()
    
    # Total volume (sum of all completed gig budgets)
    total_volume = db.query(Gig.budget).filter(
        Gig.status == GigStatus.APPROVED
    ).all()
    total_volume = sum([g[0] for g in total_volume]) if total_volume else 0.0
    
    return {
        "total_creators": total_creators,
        "total_businesses": total_businesses,
        "verified_creators": verified_creators,
        "active_gigs": active_gigs,
        "completed_gigs": completed_gigs,
        "total_volume_ngn": total_volume,
        "platform_fees_earned": total_volume * 0.15  # 15% platform fee
    }
