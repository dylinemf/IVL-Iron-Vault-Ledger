import pytest
from unittest.mock import patch, MagicMock
from sqlmodel import Session, select
from decimal import Decimal

from app.services.ledger import LedgerEngine, _update_account_intelligence_fields
from app.models import Account, JournalEntry
from app.db.utils import managed_transaction

pytestmark = pytest.mark.anyio

@pytest.fixture(name="test_accounts")
def create_test_accounts(session: Session):
    """Fixture to create a pair of accounts for testing transactions."""
    account1 = Account(name="Debit Test Account", type="ASSET", country_code="US", currency="USD", total_transactions=0, total_amount=Decimal("0.0"), avg_transaction_amount=0.0, std_dev_transaction_amount=0.0)
    account2 = Account(name="Credit Test Account", type="ASSET", country_code="US", currency="USD", total_transactions=0, total_amount=Decimal("0.0"), avg_transaction_amount=0.0, std_dev_transaction_amount=0.0)
    
    with managed_transaction(session) as tx_session:
        tx_session.add(account1)
        tx_session.add(account2)
    
    # The managed_transaction commits, so the objects will have IDs.
    return account1, account2

def test_transaction_rollback_on_failure(session: Session, test_accounts):
    """
    Verify that a transaction is fully rolled back if an error occurs
    partway through the process.
    """
    debit_account, credit_account = test_accounts
    initial_debit_tx_count = debit_account.total_transactions
    initial_credit_tx_count = credit_account.total_transactions
    initial_journal_count = session.exec(select(JournalEntry)).all()

    # This mock will raise an exception ONLY on the second call,
    # simulating a failure when updating the credit account's intelligence fields.
    mock_update_intel = MagicMock(side_effect=[None, ValueError("Simulated failure on credit account update")])

    # Patch the function directly where it's defined.
    with patch('app.services.ledger._update_account_intelligence_fields', new=mock_update_intel):
        # Use the managed_transaction context manager to wrap the operation
        with pytest.raises(ValueError, match="Simulated failure on credit account update"):
            with managed_transaction(session) as tx_session:
                ledger = LedgerEngine(tx_session)
                ledger.record_transaction(
                    debit_id=debit_account.id,
                    credit_id=credit_account.id,
                    amount=Decimal("100.00"),
                    desc="Test transaction that should fail"
                )

    # --- VERIFICATION ---
    # 1. Verify no new journal entry was created.
    final_journal_count = session.exec(select(JournalEntry)).all()
    assert len(final_journal_count) == len(initial_journal_count)

    # 2. Re-fetch accounts from the DB to get their post-rollback state.
    db_debit_account = session.get(Account, debit_account.id)
    db_credit_account = session.get(Account, credit_account.id)

    # 3. Verify that the account states have NOT changed.
    assert db_debit_account.total_transactions == initial_debit_tx_count
    assert db_credit_account.total_transactions == initial_credit_tx_count
    assert db_debit_account.total_amount == Decimal("0.0")
    assert db_credit_account.total_amount == Decimal("0.0")

    # 4. Verify the mock was called for the debit account before the failure.
    assert mock_update_intel.call_count == 2
