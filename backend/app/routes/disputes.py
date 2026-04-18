# Dispute Routes - Dispute Resolution System
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..core.database import get_db
from ..schemas.schemas import DisputeCreate, DisputeResponse, DisputeResolution, UserResponse
from ..services.wallet_service import WalletService
from ..services.auth_service import AuthService
from ..models.models import Dispute, Gig, GigStatus, User, Message, Notification
from ..schemas.schemas import UserRoleEnum
from .auth import get_current_user

router = APIRouter(prefix="/disputes", tags=["Disputes"])


@router.post("/", response_model=DisputeResponse)
def create_dispute(
    dispute_data: DisputeCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new dispute"""
    gig = db.query(Gig).filter(Gig.id == dispute_data.gig_id).first()
    if not gig:
        raise HTTPException(status_code=404, detail="Gig not found")
    
    # Check if user is part of the gig
    if gig.business_id != current_user.id and gig.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to dispute this gig")
    
    # Check gig status - can only dispute if SUBMITTED or IN_PROGRESS
    if gig.status not in [GigStatus.SUBMITTED, GigStatus.IN_PROGRESS]:
        raise HTTPException(
            status_code=400, 
            detail="Can only dispute gigs that are SUBMITTED or IN_PROGRESS"
        )
    
    # Create dispute
    dispute = Dispute(
        gig_id=gig.id,
        created_by_id=current_user.id,
        reason=dispute_data.reason,
        status="pending"
    )
    
    db.add(dispute)
    
    # Freeze escrow
    wallet_service = WalletService(db)
    wallet_service.freeze_escrow_for_dispute(gig.id)
    
    # Notify admin (create notification for all admins)
    admins = db.query(User).filter(User.role == UserRoleEnum.ADMIN).all()
    for admin in admins:
        notification = Notification(
            user_id=admin.id,
            title="New Dispute Created",
            message=f"Dispute raised for gig: {gig.title} by {current_user.full_name}",
            notification_type="warning",
            related_gig_id=gig.id,
            related_user_id=current_user.id
        )
        db.add(notification)
    
    db.commit()
    db.refresh(dispute)
    
    return dispute


@router.get("/", response_model=List[DisputeResponse])
def list_disputes(
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List disputes (filtered by role)"""
    query = db.query(Dispute)
    
    if current_user.role == UserRoleEnum.ADMIN:
        # Admin sees all disputes
        if status_filter:
            query = query.filter(Dispute.status == status_filter)
    else:
        # Users see only their disputes
        query = query.filter(Dispute.created_by_id == current_user.id)
    
    disputes = query.offset(skip).limit(limit).all()
    return disputes


@router.get("/{dispute_id}", response_model=DisputeResponse)
def get_dispute(
    dispute_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get dispute details with chat history and PoW"""
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    
    # Check permission
    gig = db.query(Gig).filter(Gig.id == dispute.gig_id).first()
    if not gig:
        raise HTTPException(status_code=404, detail="Gig not found")
    
    if current_user.role != UserRoleEnum.ADMIN:
        if gig.business_id != current_user.id and gig.creator_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
    
    # Get chat history for admin ticket
    messages = db.query(Message).filter(
        Message.gig_id == dispute.gig_id
    ).order_by(Message.sent_at.asc()).all()
    
    result = DisputeResponse(
        id=dispute.id,
        gig_id=dispute.gig_id,
        created_by_id=dispute.created_by_id,
        reason=dispute.reason,
        status=dispute.status,
        admin_notes=dispute.admin_notes,
        resolution_type=dispute.resolution_type,
        resolution_amount_creator=dispute.resolution_amount_creator,
        resolution_amount_business=dispute.resolution_amount_business,
        resolved_by_id=dispute.resolved_by_id,
        resolved_at=dispute.resolved_at,
        created_at=dispute.created_at,
        updated_at=dispute.updated_at
    )
    
    # Attach chat history and PoW info for display
    return {
        "dispute": result,
        "chat_history": messages,
        "pow_file_url": gig.pow_file_url,
        "pow_file_type": gig.pow_file_type,
        "gig_details": {
            "title": gig.title,
            "budget": gig.budget,
            "status": gig.status
        }
    }


@router.post("/{dispute_id}/resolve")
def resolve_dispute(
    dispute_id: int,
    resolution: DisputeResolution,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resolve a dispute (Admin only)"""
    if current_user.role != UserRoleEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Only admins can resolve disputes")
    
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    
    if dispute.status == "resolved":
        raise HTTPException(status_code=400, detail="Dispute already resolved")
    
    gig = db.query(Gig).filter(Gig.id == dispute.gig_id).first()
    if not gig:
        raise HTTPException(status_code=404, detail="Gig not found")
    
    # Validate resolution amounts for partial split
    if resolution.resolution_type == "partial_split":
        if not resolution.resolution_amount_creator or not resolution.resolution_amount_business:
            raise HTTPException(
                status_code=400, 
                detail="Both creator and business amounts required for partial split"
            )
        total = resolution.resolution_amount_creator + resolution.resolution_amount_business
        if abs(total - gig.budget) > 0.01:
            raise HTTPException(
                status_code=400, 
                detail="Resolution amounts must equal gig budget"
            )
    
    # Resolve dispute
    wallet_service = WalletService(db)
    
    try:
        wallet_service.resolve_dispute(
            gig_id=gig.id,
            resolution_type=resolution.resolution_type,
            creator_amount=resolution.resolution_amount_creator,
            business_amount=resolution.resolution_amount_business
        )
        
        # Update dispute record
        dispute.status = "resolved"
        dispute.admin_notes = resolution.admin_notes
        dispute.resolution_type = resolution.resolution_type
        dispute.resolution_amount_creator = resolution.resolution_amount_creator
        dispute.resolution_amount_business = resolution.resolution_amount_business
        dispute.resolved_by_id = current_user.id
        dispute.resolved_at = datetime.utcnow()
        
        # Notify parties
        notifications = [
            Notification(
                user_id=gig.business_id,
                title="Dispute Resolved",
                message=f"Your dispute has been resolved: {resolution.admin_notes}",
                notification_type="info",
                related_gig_id=gig.id
            ),
            Notification(
                user_id=gig.creator_id,
                title="Dispute Resolved",
                message=f"The dispute has been resolved: {resolution.admin_notes}",
                notification_type="info",
                related_gig_id=gig.id
            )
        ]
        
        for notification in notifications:
            db.add(notification)
        
        db.commit()
        
        return {"message": "Dispute resolved successfully", "dispute_id": dispute_id}
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
