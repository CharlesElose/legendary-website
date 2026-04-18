# Wallet Routes - Deposits, Withdrawals, and Balance Management
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..core.database import get_db
from ..schemas.schemas import (
    WalletResponse, DepositRequest, DepositResponse, 
    WithdrawalRequest, WithdrawalResponse, UserResponse
)
from ..services.wallet_service import WalletService
from ..models.models import Wallet, Deposit, Withdrawal
from ..schemas.schemas import UserRoleEnum
from .auth import get_current_user

router = APIRouter(prefix="/wallet", tags=["Wallet"])


@router.get("/balance", response_model=dict)
def get_balance(
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current wallet balance"""
    wallet_service = WalletService(db)
    balance = wallet_service.get_total_balance(current_user.id)
    
    return {
        "user_id": current_user.id,
        "balances": balance,
        "currency": "NGN"
    }


@router.get("/", response_model=WalletResponse)
def get_wallet(
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get wallet details"""
    wallet_service = WalletService(db)
    wallet = wallet_service.get_wallet(current_user.id)
    
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    return wallet


@router.post("/deposit/initialize", response_model=DepositResponse)
async def initialize_deposit(
    deposit_data: DepositRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Initialize a deposit via Paystack"""
    wallet_service = WalletService(db)
    
    try:
        result = await wallet_service.initialize_paystack_deposit(
            deposit_data.email,
            deposit_data.amount
        )
        
        # Create pending deposit record
        deposit = wallet_service.process_paystack_deposit(
            current_user.id,
            deposit_data.amount,
            result["reference"],
            status="pending"
        )
        
        return DepositResponse(
            deposit_id=deposit.id,
            amount=deposit_data.amount,
            paystack_reference=result["reference"],
            authorization_url=result["authorization_url"],
            status="pending"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/deposit/verify/{reference}")
async def verify_deposit(
    reference: str,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verify a Paystack deposit"""
    wallet_service = WalletService(db)
    
    try:
        result = await wallet_service.verify_paystack_transaction(reference)
        
        if result.get("status") and result["data"]["status"] == "success":
            # Update deposit record
            deposit = db.query(Deposit).filter(
                Deposit.paystack_reference == reference
            ).first()
            
            if deposit:
                deposit.status = "completed"
                wallet_service.add_funds(current_user.id, deposit.amount)
                
                return {"message": "Deposit successful", "amount": deposit.amount}
        
        raise HTTPException(status_code=400, detail="Payment verification failed")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/withdraw", response_model=WithdrawalResponse)
def request_withdrawal(
    withdrawal_data: WithdrawalRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Request withdrawal from wallet"""
    if current_user.role != UserRoleEnum.CREATOR:
        raise HTTPException(status_code=403, detail="Only creators can withdraw funds")
    
    wallet_service = WalletService(db)
    
    try:
        withdrawal = wallet_service.withdraw_funds(
            current_user.id,
            withdrawal_data.amount,
            withdrawal_data.bank_account_number,
            withdrawal_data.bank_code,
            withdrawal_data.account_name
        )
        
        return WithdrawalResponse(
            withdrawal_id=withdrawal.id,
            amount=withdrawal.amount,
            status=withdrawal.status,
            message="Withdrawal request submitted successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/deposits", response_model=List[dict])
def get_deposit_history(
    skip: int = 0,
    limit: int = 20,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get deposit history"""
    deposits = db.query(Deposit).filter(
        Deposit.user_id == current_user.id
    ).order_by(Deposit.created_at.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": d.id,
            "amount": d.amount,
            "reference": d.paystack_reference,
            "status": d.status,
            "created_at": d.created_at
        }
        for d in deposits
    ]


@router.get("/withdrawals", response_model=List[dict])
def get_withdrawal_history(
    skip: int = 0,
    limit: int = 20,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get withdrawal history"""
    withdrawals = db.query(Withdrawal).filter(
        Withdrawal.user_id == current_user.id
    ).order_by(Withdrawal.created_at.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": w.id,
            "amount": w.amount,
            "bank_account": f"****{w.bank_account_number[-4:]}",
            "account_name": w.account_name,
            "status": w.status,
            "created_at": w.created_at,
            "processed_at": w.processed_at
        }
        for w in withdrawals
    ]
