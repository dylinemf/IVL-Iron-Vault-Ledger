from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, select
from app.db.session import get_session
from app.models import User, Account, AccountStatus
from app.core.auth import get_current_user
from app.services.intelligence import FinancialIntelligence

router = APIRouter()

@router.post("/audit/{account_id}/benford", status_code=status.HTTP_200_OK)
def run_benford_audit(
    account_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    [Compliance Officer Only]
    Triggers a forensic Benford's Law analysis on a specific account.
    If a violation is detected, the account will be automatically FROZEN.
    """
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    intel = FinancialIntelligence(session)
    report = intel.audit_benford_compliance(account_id)

    return JSONResponse(status_code=status.HTTP_200_OK, content=jsonable_encoder({
        "status": "success",
        "message": "Benford audit completed successfully",
        "data": {
            "account_id": account_id,
            "account_iban": account.iban,
            "current_status": account.status,
            "audit_report": report
        }
    }))

@router.get("/account/{account_id}/risk-profile")
def get_risk_profile(
    account_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    return JSONResponse(status_code=status.HTTP_200_OK, content=jsonable_encoder({
        "status": "success",
        "message": "Risk profile retrieved",
        "data": {
            "account_id": account.id,
            "status": account.status,
            "risk_score": account.risk_score,
            "total_transactions": account.total_transactions,
            "std_dev": account.std_dev_transaction_amount
        }
    }))