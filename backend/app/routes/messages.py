# Messages Routes - Messaging Platform
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..core.database import get_db
from ..schemas.schemas import MessageCreate, MessageResponse, ChatHistory, UserResponse
from ..services.auth_service import AuthService
from ..models.models import Message, Gig, User, Notification
from ..schemas.schemas import UserRoleEnum
from .auth import get_current_user

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.post("/", response_model=MessageResponse)
def send_message(
    message_data: MessageCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a message in a gig chat"""
    # Verify gig exists and user is part of it
    gig = db.query(Gig).filter(Gig.id == message_data.gig_id).first()
    if not gig:
        raise HTTPException(status_code=404, detail="Gig not found")
    
    if gig.business_id != current_user.id and gig.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to message in this gig")
    
    # Create message
    message = Message(
        gig_id=message_data.gig_id,
        sender_id=current_user.id,
        recipient_id=message_data.recipient_id,
        content=message_data.content,
        message_type=message_data.message_type,
        attachment_url=message_data.attachment_url,
        attachment_type=message_data.attachment_type
    )
    
    db.add(message)
    
    # Create notification for recipient
    notification = Notification(
        user_id=message_data.recipient_id,
        title="New Message",
        message=f"You have a new message in gig: {gig.title}",
        notification_type="info",
        related_gig_id=gig.id,
        related_user_id=current_user.id
    )
    db.add(notification)
    
    db.commit()
    db.refresh(message)
    
    return message


@router.get("/gig/{gig_id}", response_model=ChatHistory)
def get_chat_history(
    gig_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get chat history for a gig"""
    gig = db.query(Gig).filter(Gig.id == gig_id).first()
    if not gig:
        raise HTTPException(status_code=404, detail="Gig not found")
    
    if gig.business_id != current_user.id and gig.creator_id != current_user.id:
        if current_user.role != UserRoleEnum.ADMIN:
            raise HTTPException(status_code=403, detail="Not authorized to view this chat")
    
    # Get messages
    messages = db.query(Message).filter(
        Message.gig_id == gig_id
    ).order_by(Message.sent_at.asc()).all()
    
    # Mark messages as read
    for msg in messages:
        if msg.recipient_id == current_user.id:
            msg.is_read = True
    
    db.commit()
    
    # Get participants
    participants = []
    business = db.query(User).filter(User.id == gig.business_id).first()
    if business:
        participants.append(business)
    if gig.creator_id:
        creator = db.query(User).filter(User.id == gig.creator_id).first()
        if creator:
            participants.append(creator)
    
    return ChatHistory(
        messages=messages,
        gig_id=gig_id,
        participants=participants
    )


@router.get("/inbox", response_model=List[dict])
def get_inbox(
    skip: int = 0,
    limit: int = 20,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's inbox with latest messages from each conversation"""
    # Get all gigs user is involved in
    gigs = db.query(Gig).filter(
        (Gig.business_id == current_user.id) | (Gig.creator_id == current_user.id)
    ).all()
    
    inbox = []
    for gig in gigs:
        # Get latest message
        latest_message = db.query(Message).filter(
            Message.gig_id == gig.id
        ).order_by(Message.sent_at.desc()).first()
        
        if latest_message:
            # Get other participant
            other_id = gig.creator_id if gig.business_id == current_user.id else gig.business_id
            other_user = db.query(User).filter(User.id == other_id).first()
            
            # Count unread
            unread_count = db.query(Message).filter(
                Message.gig_id == gig.id,
                Message.recipient_id == current_user.id,
                Message.is_read == False
            ).count()
            
            inbox.append({
                "gig_id": gig.id,
                "gig_title": gig.title,
                "latest_message": latest_message,
                "other_participant": other_user,
                "unread_count": unread_count
            })
    
    # Sort by latest message
    inbox.sort(key=lambda x: x["latest_message"].sent_at, reverse=True)
    
    return inbox[skip:skip + limit]


@router.post("/{message_id}/read")
def mark_as_read(
    message_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a message as read"""
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if message.recipient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    message.is_read = True
    db.commit()
    
    return {"message": "Message marked as read"}


@router.post("/pitch/{gig_id}")
def submit_pitch(
    gig_id: int,
    content: str,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit a pitch/deal proposal to a business"""
    if current_user.role != UserRoleEnum.CREATOR:
        raise HTTPException(status_code=403, detail="Only creators can submit pitches")
    
    gig = db.query(Gig).filter(Gig.id == gig_id).first()
    if not gig:
        raise HTTPException(status_code=404, detail="Gig not found")
    
    # Create pitch message
    message = Message(
        gig_id=gig_id,
        sender_id=current_user.id,
        recipient_id=gig.business_id,
        content=content,
        message_type="pitch"
    )
    
    db.add(message)
    
    # Create notification
    notification = Notification(
        user_id=gig.business_id,
        title="New Pitch Received",
        message=f"{current_user.full_name} has submitted a pitch for your gig",
        notification_type="info",
        related_gig_id=gig_id,
        related_user_id=current_user.id
    )
    db.add(notification)
    
    db.commit()
    db.refresh(message)
    
    return {"message": "Pitch submitted successfully", "pitch": message}
