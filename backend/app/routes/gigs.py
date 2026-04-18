# Gig Routes - Marketplace and Gig Lifecycle Management
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import os
import uuid

from ..core.database import get_db
from ..core.config import settings
from ..schemas.schemas import (
    GigCreate, GigUpdate, GigResponse, GigDetailResponse, PoWSubmission,
    GigStatusEnum, UserResponse
)
from ..services.auth_service import AuthService
from ..services.wallet_service import WalletService
from ..models.models import Gig, GigStatus, User, UserRole, Message, Dispute
from .auth import get_current_user

router = APIRouter(prefix="/gigs", tags=["Gigs"])


@router.post("/", response_model=GigResponse, status_code=status.HTTP_201_CREATED)
def create_gig(
    gig_data: GigCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new gig (Business only)"""
    if current_user.role != UserRoleEnum.BUSINESS:
        raise HTTPException(status_code=403, detail="Only businesses can create gigs")
    
    gig = Gig(
        title=gig_data.title,
        description=gig_data.description,
        budget=gig_data.budget,
        deadline=gig_data.deadline,
        business_id=current_user.id,
        status=GigStatus.OPEN
    )
    
    db.add(gig)
    db.commit()
    db.refresh(gig)
    
    return gig


@router.get("/", response_model=List[GigResponse])
def list_gigs(
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[GigStatusEnum] = None,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all gigs with optional filtering"""
    query = db.query(Gig)
    
    if status_filter:
        query = query.filter(Gig.status == status_filter)
    
    # For creators, show open gigs; for businesses, show their gigs
    if current_user.role == UserRoleEnum.CREATOR:
        query = query.filter(Gig.status == GigStatus.OPEN)
    else:
        query = query.filter(Gig.business_id == current_user.id)
    
    gigs = query.offset(skip).limit(limit).all()
    return gigs


@router.get("/marketplace", response_model=List[GigResponse])
def marketplace_gigs(
    skip: int = 0,
    limit: int = 20,
    niche: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get marketplace gigs with fair shuffle for verified creators"""
    auth_service = AuthService(db)
    
    # Get verified creators with shuffle
    verified_creators = auth_service.get_verified_creators(limit=50, shuffle=True)
    creator_ids = [c.id for c in verified_creators]
    
    query = db.query(Gig).filter(
        Gig.status == GigStatus.OPEN,
        Gig.creator_id.in_(creator_ids) if creator_ids else True
    )
    
    if niche:
        # Filter by creator niche
        creator_ids_with_niche = db.query(User.id).filter(
            User.role == UserRole.CREATOR,
            User.niche == niche,
            User.is_verified == True
        ).all()
        creator_ids_with_niche = [c[0] for c in creator_ids_with_niche]
        if creator_ids_with_niche:
            query = query.filter(Gig.creator_id.in_(creator_ids_with_niche))
    
    gigs = query.offset(skip).limit(limit).all()
    return gigs


@router.get("/{gig_id}", response_model=GigDetailResponse)
def get_gig(
    gig_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get gig details"""
    gig = db.query(Gig).filter(Gig.id == gig_id).first()
    if not gig:
        raise HTTPException(status_code=404, detail="Gig not found")
    
    # Check permission
    if gig.business_id != current_user.id and gig.creator_id != current_user.id:
        if current_user.role != UserRoleEnum.ADMIN:
            raise HTTPException(status_code=403, detail="Not authorized to view this gig")
    
    return gig


@router.post("/{gig_id}/fund", response_model=GigResponse)
def fund_gig(
    gig_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fund a gig (lock escrow)"""
    if current_user.role != UserRoleEnum.BUSINESS:
        raise HTTPException(status_code=403, detail="Only businesses can fund gigs")
    
    gig = db.query(Gig).filter(Gig.id == gig_id).first()
    if not gig:
        raise HTTPException(status_code=404, detail="Gig not found")
    
    if gig.business_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to fund this gig")
    
    if gig.status != GigStatus.OPEN:
        raise HTTPException(status_code=400, detail="Gig must be in OPEN status")
    
    wallet_service = WalletService(db)
    
    try:
        gig = wallet_service.fund_gig_escrow(current_user.id, gig_id, gig.budget)
        return gig
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{gig_id}/accept", response_model=GigResponse)
def accept_gig(
    gig_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accept a gig as a creator"""
    if current_user.role != UserRoleEnum.CREATOR:
        raise HTTPException(status_code=403, detail="Only creators can accept gigs")
    
    gig = db.query(Gig).filter(Gig.id == gig_id).first()
    if not gig:
        raise HTTPException(status_code=404, detail="Gig not found")
    
    if gig.status != GigStatus.FUNDED:
        raise HTTPException(status_code=400, detail="Gig must be funded first")
    
    gig.creator_id = current_user.id
    gig.status = GigStatus.IN_PROGRESS
    
    db.commit()
    db.refresh(gig)
    
    return gig


@router.post("/{gig_id}/submit-pow")
def submit_pow(
    gig_id: int,
    file_url: str = Form(...),
    file_type: str = Form(...),
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit Proof of Work (PoW)"""
    if current_user.role != UserRoleEnum.CREATOR:
        raise HTTPException(status_code=403, detail="Only creators can submit PoW")
    
    gig = db.query(Gig).filter(Gig.id == gig_id).first()
    if not gig:
        raise HTTPException(status_code=404, detail="Gig not found")
    
    if gig.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not assigned to this gig")
    
    if gig.status != GigStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Gig must be in progress")
    
    # Update gig with PoW
    gig.pow_file_url = file_url
    gig.pow_file_type = file_type
    gig.pow_submitted_at = datetime.utcnow()
    gig.pow_auto_release_date = datetime.utcnow() + timedelta(days=settings.POW_AUTO_RELEASE_DAYS)
    gig.status = GigStatus.SUBMITTED
    
    db.commit()
    db.refresh(gig)
    
    return {"message": "Proof of Work submitted successfully", "gig": gig}


@router.post("/{gig_id}/approve", response_model=GigResponse)
def approve_gig(
    gig_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Approve gig and release funds to creator"""
    if current_user.role != UserRoleEnum.BUSINESS:
        raise HTTPException(status_code=403, detail="Only businesses can approve gigs")
    
    gig = db.query(Gig).filter(Gig.id == gig_id).first()
    if not gig:
        raise HTTPException(status_code=404, detail="Gig not found")
    
    if gig.business_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if gig.status != GigStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="Gig must be submitted")
    
    wallet_service = WalletService(db)
    
    try:
        gig = wallet_service.release_gig_escrow(gig_id)
        return gig
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{gig_id}", response_model=GigResponse)
def update_gig(
    gig_id: int,
    gig_data: GigUpdate,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update gig details"""
    gig = db.query(Gig).filter(Gig.id == gig_id).first()
    if not gig:
        raise HTTPException(status_code=404, detail="Gig not found")
    
    if gig.business_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    update_data = gig_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(gig, field, value)
    
    db.commit()
    db.refresh(gig)
    
    return gig
