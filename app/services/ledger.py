import logging
import numpy as np
from sqlmodel import Session, select, SQLModel
from app.models import JournalEntry, Account, AccountStatus
from typing import Optional
from decimal import Decimal
from app.services.intelligence import FinancialIntelligence
from app.services.crypto_manager import CryptoManager

logger = logging.getLogger(__name__)

def _update_account_intelligence_fields(session: Session, account: Account, new_transaction_amount: Decimal):
    # Retrieve current statistics
    old_total_transactions = account.total_transactions
    old_avg_transaction_amount = account.avg_transaction_amount
    old_std_dev_transaction_amount = account.std_dev_transaction_amount

    # Update total transactions and total amount
    account.total_transactions += 1
    account.total_amount += new_transaction_amount

    # Calculate new average
    # Convert Decimal to float for statistical analysis (stats don't need infinite precision)
    new_avg_transaction_amount = float(account.total_amount) / account.total_transactions

    # Calculate old sum of squares (if not the first transaction)
    old_sum_sq = (old_std_dev_transaction_amount**2 + old_avg_transaction_amount**2) * old_total_transactions if old_total_transactions > 0 else 0.0

    # Add the square of the new transaction amount
    new_sum_sq = old_sum_sq + (float(new_transaction_amount)**2)

    # Calculate new variance
    new_variance = (new_sum_sq / account.total_transactions) - (new_avg_transaction_amount**2)
    new_std_dev_transaction_amount = float(np.sqrt(max(0.0, new_variance))) # ensure non-negative variance

    account.avg_transaction_amount = new_avg_transaction_amount
    account.std_dev_transaction_amount = new_std_dev_transaction_amount

    session.add(account)


class LedgerEngine:
    def __init__(self, session: Session):
        self.session = session

    def get_last_entry(self) -> Optional[JournalEntry]:
        # Grab the last entry to link the hash chain.
        statement = select(JournalEntry).order_by(JournalEntry.id.desc()).limit(1)
        return self.session.exec(statement).first()

    def record_transaction(self, debit_id: int, credit_id: int, amount: Decimal, desc: str):
        # Ensure amount is Decimal (handle floats from Pydantic/JSON inputs)
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        # 1. Double Entry Validation (Sanity Check)
        if amount <= 0:
            logger.warning("Attempted to record transaction with non-positive amount", extra={"extra_fields": {"amount": amount}})
            raise ValueError("Amount must be positive")
        
        # Fetch accounts (optimistically, assuming they exist)
        debit_account = self.session.get(Account, debit_id)
        credit_account = self.session.get(Account, credit_id)

        if not debit_account or not credit_account:
            logger.error("One or both accounts not found", extra={"extra_fields": {"debit_id": debit_id, "credit_id": credit_id}})
            raise ValueError("Debit or Credit account not found.")

        # 0. Compliance Check (Account Status)
        if debit_account.status != AccountStatus.ACTIVE or credit_account.status != AccountStatus.ACTIVE:
            logger.warning("Transaction blocked: Account is FROZEN or SUSPENDED")
            raise ValueError("Transaction rejected: One of the accounts is frozen due to compliance/risk issues.")

        # Strict Currency Guardrails
        if debit_account.currency != credit_account.currency:
            logger.error("Currency mismatch detected", extra={"extra_fields": {"debit_currency": debit_account.currency, "credit_currency": credit_account.currency}})
            raise ValueError(f"Currency mismatch: Cannot transfer {debit_account.currency} to {credit_account.currency} directly.")

        # 1A. AI Risk Check
        # Check for anomalies before recording.
        intel = FinancialIntelligence(self.session)
        risk_analysis = intel.analyze_transaction(amount, debit_id)
        
        if risk_analysis["status"] == "CRITICAL_ANOMALY":
            logger.warning("Transaction BLOCKED by AI Risk Engine", extra={"extra_fields": risk_analysis})
            raise ValueError(f"Risk Alert: {risk_analysis['message']}")

        # 2. Get Last Hash (The Chain)
        last_entry = self.get_last_entry()
        prev_hash = last_entry.hash if last_entry else "GENESIS_BLOCK_HASH"
        
        # 3. Crypto-Shredding Setup
        # Generate a unique key for this transaction.
        crypto_mgr = CryptoManager(self.session)
        key_entry = crypto_mgr.create_key()
        encrypted_desc = crypto_mgr.encrypt_text(desc, key_entry)

        new_entry = JournalEntry(
            debit_account_id=debit_id,
            credit_account_id=credit_id,
            amount=amount,
            description=encrypted_desc, # Use the shreddable (encrypted) description
            encryption_key_id=key_entry.id,
            previous_hash=prev_hash,
            hash="" # To be calculated below after the object instantiated
        )
        
        # 4. Calculate Hash (Self-Sealing)
        new_entry.hash = new_entry.calculate_hash()
        
        # 5. Save to DB
        self.session.add(new_entry)

        # 6. Update intelligence fields for affected accounts
        _update_account_intelligence_fields(self.session, debit_account, amount)
        _update_account_intelligence_fields(self.session, credit_account, amount)
        
        self.session.flush()
        self.session.refresh(new_entry)
        
        logger.info("Transaction recorded successfully", extra={"extra_fields": {"entry_id": new_entry.id, "amount": new_entry.amount}})
        return new_entry

    def verify_integrity(self) -> bool:
        # Audit Function: Check for tampering.
        entries = self.session.exec(select(JournalEntry).order_by(JournalEntry.id)).all()
        
        temp_prev_hash = "GENESIS_BLOCK_HASH"
        
        for entry in entries:
            # 1. Verify chain continuity (prev_hash links).
            if entry.previous_hash != temp_prev_hash:
                logger.warning("TAMPER DETECTED: Chain Broken!", extra={"extra_fields": {"entry_id": entry.id, "expected_prev_hash": temp_prev_hash, "actual_prev_hash": entry.previous_hash}})
                return False
            
            # 2. Verify data integrity (re-hash and compare).
            calculated = entry.calculate_hash()
            if calculated != entry.hash:
                logger.warning("TAMPER DETECTED: Data altered!", extra={"extra_fields": {"entry_id": entry.id, "stored_hash": entry.hash, "calculated_hash": calculated}})
                return False
            
            temp_prev_hash = entry.hash
            
        logger.info("Integrity Verified: The Ledger is Clean.")
        return True