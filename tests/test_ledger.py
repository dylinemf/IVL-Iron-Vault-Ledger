from sqlmodel import select
from app.services.ledger import LedgerEngine
from app.models import JournalEntry, Account
from app.db.utils import managed_transaction
import pytest
from decimal import Decimal

def test_record_transaction(session):
    """
    Tests that a simple transaction is recorded correctly.
    """
    ledger = LedgerEngine(session)
    with managed_transaction(session):
        entry = ledger.record_transaction(debit_id=1, credit_id=2, amount=Decimal("100.00"), desc="Test Payment")
    
    assert entry.id is not None
    assert entry.amount == Decimal("100.00")
    assert entry.debit_account_id == 1
    
    last_entry = ledger.get_last_entry()
    assert entry.hash == last_entry.hash


def test_verify_integrity_clean(session):
    """
    Tests that the integrity verification passes on an unaltered chain.
    """
    ledger = LedgerEngine(session)
    with managed_transaction(session):
        ledger.record_transaction(debit_id=1, credit_id=2, amount=Decimal("100.00"), desc="First Payment")
        ledger.record_transaction(debit_id=1, credit_id=2, amount=Decimal("50.00"), desc="Second Payment")

    assert ledger.verify_integrity() is True

def test_verify_integrity_fails_on_tamper(session):
    """
    Tests that integrity verification FAILS if a description is altered
    after the fact. This confirms the hashing integrity fix is working.
    """
    ledger = LedgerEngine(session)
    with managed_transaction(session):
        entry = ledger.record_transaction(debit_id=1, credit_id=2, amount=Decimal("100.00"), desc="Original Description")
    
    # Manually tamper with the data in the database
    entry.description = "Tampered Description"
    with managed_transaction(session):
        session.add(entry)

    # Verification should now fail because the description changed but the hash did not
    assert ledger.verify_integrity() is False

def test_verify_integrity_fails_on_chain_break(session):
    """
    Tests that integrity verification FAILS if a previous_hash link is broken.
    """
    ledger = LedgerEngine(session)
    with managed_transaction(session):
        entry1 = ledger.record_transaction(debit_id=1, credit_id=2, amount=Decimal("100.00"), desc="First")
        entry2 = ledger.record_transaction(debit_id=1, credit_id=2, amount=Decimal("50.00"), desc="Second")

    # Tamper with the chain
    entry2.previous_hash = "TAMPERED_HASH"
    with managed_transaction(session):
        session.add(entry2)

    assert ledger.verify_integrity() is False

def test_transaction_fails_on_currency_mismatch(session):
    """
    Tests that the system prevents transfers between different currencies.
    """
    ledger = LedgerEngine(session)
    
    # Create a USD Account (Default accounts in conftest are CHF and EUR)
    usd_account = Account(name="US Dollar Reserve", type="ASSET", country_code="US", currency="USD")
    with managed_transaction(session):
        session.add(usd_account)
    
    # Attempt to transfer from CHF (id=1) to USD
    with pytest.raises(ValueError, match="Currency mismatch"):
        with managed_transaction(session):
            ledger.record_transaction(debit_id=1, credit_id=usd_account.id, amount=Decimal("100.00"), desc="Illegal FX Transfer")

def test_transaction_blocked_by_ai_anomaly(session):
    """
    Tests that the Financial Intelligence layer actively BLOCKS transactions
    that deviate significantly from the account's history (Z-Score > 3).
    """
    ledger = LedgerEngine(session)
    
    # Use the EUR accounts (3 and 4) for this test to avoid conflicts
    # 1. Training Phase: Feed it some normal transactions.
    # Mean ~50, low variance.
    with managed_transaction(session):
        for _ in range(10):
            ledger.record_transaction(debit_id=3, credit_id=4, amount=Decimal("50.00"), desc="Normal Tx")
            ledger.record_transaction(debit_id=3, credit_id=4, amount=Decimal("45.00"), desc="Normal Tx")
            ledger.record_transaction(debit_id=3, credit_id=4, amount=Decimal("55.00"), desc="Normal Tx")

    # 2. Attack Phase: Try a massive transaction (e.g., 5000.00).
    # This is definitely > 3 sigma from the mean.
    with pytest.raises(ValueError, match="Risk Alert"):
        with managed_transaction(session):
            ledger.record_transaction(debit_id=3, credit_id=4, amount=Decimal("5000.00"), desc="Fat Finger Error")
