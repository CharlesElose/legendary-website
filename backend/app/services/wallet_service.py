# Wallet and Payment Service
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime
import httpx

from ..models.models import User, Wallet, Gig, GigStatus, Deposit, Withdrawal, Dispute
from ..core.config import settings


class WalletService:
    """Service for wallet management and payments"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_wallet(self, user_id: int) -> Optional[Wallet]:
        """Get wallet for a user"""
        return self.db.query(Wallet).filter(Wallet.user_id == user_id).first()
    
    def get_total_balance(self, user_id: int) -> Dict[str, float]:
        """Get total balance breakdown for a user"""
        wallet = self.get_wallet(user_id)
        if not wallet:
            return {"available": 0.0, "locked": 0.0, "pending": 0.0, "total": 0.0}
        
        return {
            "available": wallet.available_balance,
            "locked": wallet.locked_balance,
            "pending": wallet.pending_balance,
            "total": wallet.available_balance + wallet.locked_balance + wallet.pending_balance
        }
    
    def add_funds(self, user_id: int, amount: float) -> Wallet:
        """Add funds to user's available balance"""
        wallet = self.get_wallet(user_id)
        if not wallet:
            raise ValueError("Wallet not found")
        
        wallet.available_balance += amount
        self.db.commit()
        self.db.refresh(wallet)
        return wallet
    
    def lock_funds(self, user_id: int, amount: float) -> Wallet:
        """Lock funds in escrow (for gig funding)"""
        wallet = self.get_wallet(user_id)
        if not wallet:
            raise ValueError("Wallet not found")
        
        if wallet.available_balance < amount:
            raise ValueError("Insufficient funds")
        
        wallet.available_balance -= amount
        wallet.locked_balance += amount
        self.db.commit()
        self.db.refresh(wallet)
        return wallet
    
    def release_funds(self, creator_id: int, amount: float, platform_fee_percent: float = 15.0) -> Wallet:
        """Release funds from escrow to creator (after gig completion)"""
        creator_wallet = self.get_wallet(creator_id)
        if not creator_wallet:
            raise ValueError("Creator wallet not found")
        
        # Calculate split
        platform_fee = amount * (platform_fee_percent / 100)
        creator_share = amount - platform_fee
        
        # Release from locked to creator's available balance
        creator_wallet.locked_balance -= amount
        creator_wallet.available_balance += creator_share
        creator_wallet.pending_balance += platform_fee  # Platform fee goes to pending
        
        # Update user's total earnings
        creator = self.db.query(User).filter(User.id == creator_id).first()
        if creator:
            creator.total_earnings += creator_share
        
        self.db.commit()
        self.db.refresh(creator_wallet)
        return creator_wallet
    
    def refund_funds(self, business_id: int, amount: float) -> Wallet:
        """Refund funds back to business (cancelled/disputed gig)"""
        business_wallet = self.get_wallet(business_id)
        if not business_wallet:
            raise ValueError("Business wallet not found")
        
        wallet.locked_balance -= amount
        business_wallet.available_balance += amount
        
        self.db.commit()
        self.db.refresh(business_wallet)
        return business_wallet
    
    def withdraw_funds(self, user_id: int, amount: float, bank_account_number: str, 
                       bank_code: str, account_name: str) -> Withdrawal:
        """Initiate withdrawal from creator wallet"""
        wallet = self.get_wallet(user_id)
        if not wallet:
            raise ValueError("Wallet not found")
        
        if wallet.available_balance < amount:
            raise ValueError("Insufficient available balance")
        
        # Deduct from available balance
        wallet.available_balance -= amount
        
        # Create withdrawal record
        withdrawal = Withdrawal(
            user_id=user_id,
            amount=amount,
            bank_account_number=bank_account_number,
            bank_code=bank_code,
            account_name=account_name,
            status="pending"
        )
        
        self.db.add(withdrawal)
        self.db.commit()
        self.db.refresh(withdrawal)
        
        return withdrawal
    
    def process_paystack_deposit(self, user_id: int, amount: float, 
                                  paystack_reference: str, status: str = "completed") -> Deposit:
        """Record a Paystack deposit"""
        deposit = Deposit(
            user_id=user_id,
            amount=amount,
            paystack_reference=paystack_reference,
            status=status
        )
        
        self.db.add(deposit)
        
        if status == "completed":
            # Add funds to wallet
            self.add_funds(user_id, amount)
            
            # Update user's total spent if business
            user = self.db.query(User).filter(User.id == user_id).first()
            if user and user.role.value == "business":
                user.total_spent += amount
        
        self.db.commit()
        self.db.refresh(deposit)
        return deposit
    
    async def initialize_paystack_deposit(self, email: str, amount: float) -> Dict[str, Any]:
        """Initialize deposit with Paystack API"""
        url = f"{settings.PAYSTACK_BASE_URL}/transaction/initialize"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "email": email,
            "amount": int(amount * 100),  # Paystack uses kobo
            "currency": "NGN"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)
            result = response.json()
            
            if result.get("status"):
                return {
                    "authorization_url": result["data"]["authorization_url"],
                    "access_code": result["data"]["access_code"],
                    "reference": result["data"]["reference"]
                }
            else:
                raise ValueError(result.get("message", "Paystack initialization failed"))
    
    async def verify_paystack_transaction(self, reference: str) -> Dict[str, Any]:
        """Verify Paystack transaction"""
        url = f"{settings.PAYSTACK_BASE_URL}/transaction/verify/{reference}"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            result = response.json()
            
            return result
    
    async def process_paystack_transfer(self, withdrawal: Withdrawal) -> bool:
        """Process withdrawal via Paystack transfer"""
        url = f"{settings.PAYSTACK_BASE_URL}/transfer"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "source": "balance",
            "amount": int(withdrawal.amount * 100),  # Convert to kobo
            "recipient": withdrawal.paystack_transfer_code or "",
            "reason": "Creator withdrawal from Creatio"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)
            result = response.json()
            
            if result.get("status"):
                withdrawal.status = "processing"
                self.db.commit()
                return True
            else:
                return False
    
    def fund_gig_escrow(self, business_id: int, gig_id: int, amount: float) -> Gig:
        """Fund a gig's escrow (lock funds)"""
        gig = self.db.query(Gig).filter(Gig.id == gig_id).first()
        if not gig:
            raise ValueError("Gig not found")
        
        if gig.business_id != business_id:
            raise ValueError("Not authorized to fund this gig")
        
        # Lock funds
        self.lock_funds(business_id, amount)
        
        # Update gig status
        gig.status = GigStatus.FUNDED
        gig.platform_fee = amount * (settings.PLATFORM_COMMISSION_PERCENT / 100)
        gig.creator_share = amount * (settings.CREATOR_SHARE_PERCENT / 100)
        
        self.db.commit()
        self.db.refresh(gig)
        return gig
    
    def release_gig_escrow(self, gig_id: int) -> Gig:
        """Release gig escrow to creator"""
        gig = self.db.query(Gig).filter(Gig.id == gig_id).first()
        if not gig:
            raise ValueError("Gig not found")
        
        if not gig.creator_id:
            raise ValueError("No creator assigned to this gig")
        
        # Release funds to creator
        self.release_funds(gig.creator_id, gig.budget, settings.PLATFORM_COMMISSION_PERCENT)
        
        # Update gig status
        gig.status = GigStatus.APPROVED
        gig.completed_at = datetime.utcnow()
        
        # Update creator's gigs completed
        creator = self.db.query(User).filter(User.id == gig.creator_id).first()
        if creator:
            creator.gigs_completed += 1
        
        self.db.commit()
        self.db.refresh(gig)
        return gig
    
    def freeze_escrow_for_dispute(self, gig_id: int) -> Gig:
        """Freeze escrow when dispute is raised"""
        gig = self.db.query(Gig).filter(Gig.id == gig_id).first()
        if not gig:
            raise ValueError("Gig not found")
        
        # Funds remain locked, just mark as disputed
        gig.status = GigStatus.DISPUTED
        
        self.db.commit()
        self.db.refresh(gig)
        return gig
    
    def resolve_dispute(self, gig_id: int, resolution_type: str, 
                        creator_amount: Optional[float] = None,
                        business_amount: Optional[float] = None) -> Gig:
        """Resolve dispute and distribute funds"""
        gig = self.db.query(Gig).filter(Gig.id == gig_id).first()
        if not gig:
            raise ValueError("Gig not found")
        
        if not gig.creator_id:
            raise ValueError("No creator assigned to this gig")
        
        # Get wallets
        creator_wallet = self.get_wallet(gig.creator_id)
        business_wallet = self.get_wallet(gig.business_id)
        
        if not creator_wallet or not business_wallet:
            raise ValueError("Wallet not found")
        
        locked_amount = gig.budget  # The locked amount in escrow
        
        if resolution_type == "force_release":
            # Full amount to creator
            self.release_funds(gig.creator_id, locked_amount, settings.PLATFORM_COMMISSION_PERCENT)
        elif resolution_type == "full_refund":
            # Full refund to business
            business_wallet.locked_balance -= locked_amount
            business_wallet.available_balance += locked_amount
        elif resolution_type == "partial_split":
            # Split according to admin decision
            if creator_amount:
                creator_wallet.locked_balance -= creator_amount
                creator_wallet.available_balance += creator_amount
            if business_amount:
                business_wallet.locked_balance -= business_amount
                business_wallet.available_balance += business_amount
        
        gig.status = GigStatus.RESOLVED if resolution_type != "force_release" else GigStatus.APPROVED
        
        self.db.commit()
        self.db.refresh(gig)
        return gig
