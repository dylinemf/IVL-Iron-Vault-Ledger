import pytest
from unittest.mock import patch
from sqlalchemy.exc import OperationalError
from app.services.ledger import LedgerEngine
from app.models import JournalEntry
from decimal import Decimal
from sqlmodel import select

def test_transaction_rollback_on_db_failure(session):
    """
    CHAOS TEST: Simulates a database connection failure exactly when 
    the system tries to commit the transaction.
    
    Objective: Prove 'Atomicity'. Either everything is saved, or nothing is.
    We don't want a transaction where the hash is calculated but data isn't saved,
    or partial updates to account balances without the journal entry.
    """
    ledger = LedgerEngine(session)
    
    # 1. Snapshot initial state.
    initial_entries = session.exec(select(JournalEntry)).all()
    assert len(initial_entries) == 0

    # 2. Monkeypatch session.commit to simulate a crash.
    # Simulating OperationalError (e.g., network cable pulled).
    with patch.object(session, 'commit', side_effect=OperationalError("Connection terminated", {}, None)):
        
        # 3. Attempt transaction.
        with pytest.raises(OperationalError):
            ledger.record_transaction(
                debit_id=1, 
                credit_id=2, 
                amount=Decimal("500.00"), 
                desc="Doom Transaction"
            )
            session.commit() # Trigger the patched commit to raise OperationalError

    # 4. Verify: Ensure NO data hit the DB.
    # Commit failed, so rollback should have happened.
    session.rollback() # Clean up session state after exception
    
    final_entries = session.exec(select(JournalEntry)).all()
    assert len(final_entries) == 0, "Chaos Test Failed: Data was inserted despite DB crash!"

    # 5. Verify: Account balances/stats must be untouched (No ghost money).
    # Refresh account from DB.
    from app.models import Account
    acc1 = session.get(Account, 1)
    
    # Total amount should still be 0, not 500.
    assert acc1.total_amount == Decimal("0.0")
    assert acc1.total_transactions == 0