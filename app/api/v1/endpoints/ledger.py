from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Header, UploadFile, File
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from app.schemas import TransactionRequest
from app.services.ledger import LedgerEngine
from app.services.intelligence import FinancialIntelligence
from app.services.iso_parser import ISO20022Parser
from app.db.session import get_session
from app.core.redis_client import get_redis_client
from app.core.auth import get_current_user
from app.models import User, Account
from app.db.utils import managed_transaction
import json
import redis
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Idempotency key expiry time (e.g., 24 hours)
IDEMPOTENCY_EXPIRY_SECONDS = 60 * 60 * 24 

@router.post("/transaction/", status_code=status.HTTP_202_ACCEPTED) # Changed to 202 Accepted for async processing
async def create_transaction(
    tx: TransactionRequest, 
    background_tasks: BackgroundTasks,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    session: Session = Depends(get_session),
    redis_client: redis.Redis = Depends(get_redis_client),
    current_user: User = Depends(get_current_user) # Add authentication dependency
):
    # Log the user action for audit trails (Now current_user is USED)
    logger.info(f"User '{current_user.username}' initiating transaction with Idempotency-Key: {idempotency_key}")

    # Check Redis for existing idempotency key
    idempotency_status = redis_client.get(f"idempotency:{idempotency_key}:status")
    idempotency_response = redis_client.get(f"idempotency:{idempotency_key}:response")

    # Debugging print statements
    print(f"DEBUG: Idempotency Check - Key: {idempotency_key}")
    print(f"DEBUG: Idempotency Check - Status: {idempotency_status}")
    print(f"DEBUG: Idempotency Check - Response: {idempotency_response}")

    if idempotency_status == "completed" and idempotency_response:
        # THIS BLOCK IS NOW EXPLICITLY RETURNING 200 OK
        print(f"DEBUG: Idempotency HIT - Returning stored response for key: {idempotency_key}")
        
        # Load cached response and modify message to indicate replay
        cached_data = json.loads(idempotency_response)
        cached_data["message"] = "Transaction already processed (Returned from Idempotency Cache). Use a new Key for a new transaction."
        if "data" in cached_data and isinstance(cached_data["data"], dict):
            cached_data["data"]["is_idempotent_replay"] = True
            
        return JSONResponse(content=cached_data, status_code=status.HTTP_200_OK)
    elif idempotency_status == "processing":
        # Operation is already ongoing
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail="Transaction with this Idempotency-Key is already being processed."
        )

    # Mark as processing
    redis_client.set(f"idempotency:{idempotency_key}:status", "processing", ex=IDEMPOTENCY_EXPIRY_SECONDS)

    # Core transaction logic
    try:
        with managed_transaction(session) as tx_session:
            intel = FinancialIntelligence(tx_session)
            analysis = intel.analyze_transaction(tx.amount, tx.debit_id)
            
            ledger = LedgerEngine(tx_session)
            entry = ledger.record_transaction(tx.debit_id, tx.credit_id, tx.amount, tx.description)
            
            response_data = {
                "status": "success",
                "message": "Transaction processed successfully",
                "data": {
                    "transaction_details": {
                        "id": entry.id,
                        "hash": entry.hash[:12] + "..."
                    },
                    "intelligence_report": analysis
                }
            }
            status_code = status.HTTP_200_OK # Indicate success for the operation itself
        
    except HTTPException as e:
        # Catch FastAPI's HTTPExceptions
        response_data = {
            "status": "error",
            "message": e.detail
        }
        status_code = e.status_code
    except Exception as e:
        # Catch any other unexpected errors
        logger.error("Unexpected error during transaction processing", exc_info=True)
        response_data = {
            "status": "error",
            "message": str(e)
        }
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    
    # Store the result in Redis using a background task
    background_tasks.add_task(
        redis_client.set, 
        f"idempotency:{idempotency_key}:response", 
        json.dumps(response_data), 
        ex=IDEMPOTENCY_EXPIRY_SECONDS
    )
    background_tasks.add_task(
        redis_client.set, 
        f"idempotency:{idempotency_key}:status", 
        "completed", 
        ex=IDEMPOTENCY_EXPIRY_SECONDS
    )

    # For the initial request, return 202 Accepted, indicating processing has started
    # If the actual processing completed successfully, the response data is included.
    # If it failed, a generic message might be returned while the full error is stored in Redis
    # and returned on subsequent requests.
    
    # Use JSONResponse instead of raising HTTPException so BackgroundTasks still run
    return JSONResponse(content=response_data, status_code=status_code, background=background_tasks)


@router.post("/transaction/import-xml", status_code=status.HTTP_201_CREATED)
async def import_xml_transaction(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Parses an ISO 20022 XML file (pacs.008) and records the transaction.
    Maps IBANs from the XML to internal Account IDs.
    """
    try:
        # 1. Read and Parse XML
        content = await file.read()
        xml_str = content.decode("utf-8")
        
        parser = ISO20022Parser()
        data = parser.parse_credit_transfer(xml_str)
        
        # 2. Resolve IBANs to Account IDs
        debtor_iban = data["debtor_iban"]
        creditor_iban = data["creditor_iban"]
        
        debit_account = session.exec(select(Account).where(Account.iban == debtor_iban)).first()
        credit_account = session.exec(select(Account).where(Account.iban == creditor_iban)).first()
        
        if not debit_account:
            raise HTTPException(status_code=400, detail=f"Debtor IBAN not found in system: {debtor_iban}")
        if not credit_account:
            raise HTTPException(status_code=400, detail=f"Creditor IBAN not found in system: {creditor_iban}")
            
        # 3. Record Transaction via Ledger Engine
        ledger = LedgerEngine(session)
        entry = ledger.record_transaction(
            debit_id=debit_account.id, 
            credit_id=credit_account.id, 
            amount=data["amount"], 
            desc=f"{data['description']} (Ref: {data['transaction_ref']})"
        )
        
        session.commit()
        session.refresh(entry)
        
        return {
            "status": "success",
            "message": "ISO 20022 Payment Processed",
            "data": {
                "transaction_id": entry.id,
                "amount": entry.amount,
                "currency": data["currency"]
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("XML Import Failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error during XML processing")


@router.get("/audit/verify")
def verify_ledger(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user) # Add authentication dependency
):
    logger.info(f"Integrity check requested by user: {current_user.username}")
    ledger = LedgerEngine(session)
    is_valid = ledger.verify_integrity()
    if is_valid:
        return {
            "status": "success", 
            "message": "All hashes match.", 
            "data": {"integrity_status": "SECURE"}
        }
    else:
        return {
            "status": "error", 
            "message": "Tampering detected in the database!", 
            "data": {"integrity_status": "CORRUPTED"}
        }
