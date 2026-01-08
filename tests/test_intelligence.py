import pytest
from unittest.mock import patch
from decimal import Decimal
from app.services.ledger import LedgerEngine
from app.services.intelligence import FinancialIntelligence
from app.models import Account

def test_benford_law_detection(session):
    """
    Tests the Forensic Capability:
    Can the system distinguish between 'Natural' financial data and 'Artificial' (Random) data?
    """
    ledger = LedgerEngine(session)
    intel = FinancialIntelligence(session)
    
    # Setup Account (Debit) and Counterparty (Credit) with matching currency
    acc = Account(name="Suspect Account", type="ASSET", country_code="US", currency="USD")
    counterparty = Account(name="US Vendor", type="REVENUE", country_code="US", currency="USD")
    session.add(acc)
    session.add(counterparty)
    session.commit()
    session.refresh(acc)
    session.refresh(counterparty)
    
    # 1. FRAUD SIMULATION (Artificial Data)
    # *Amateur fraudsters often use uniform random numbers or repetitive amounts.
    # Injecting a lot of 5-9s to break Benford's law.
    # We patch analyze_transaction to prevent Z-Score from blocking our "fake" data injection.
    with patch.object(FinancialIntelligence, 'analyze_transaction', return_value={"status": "SAFE", "message": "Test Override"}):
        for i in range(40):
            # Amounts 50-99. Leading digits will be 5,6,7,8,9.
            # Benford expects ~30% for digit 1, but we have 0%.
            amt = Decimal(50 + (i % 50)) 
            ledger.record_transaction(debit_id=acc.id, credit_id=counterparty.id, amount=amt, desc=f"Fake Tx {i}")

    result = intel.audit_benford_compliance(acc.id)
    
    # Should trigger FRAUD_RISK. Digit 1 is missing.
    assert result["status"] == "FRAUD_RISK"
    assert "Benford Violation" in result["message"]

    # 2. NATURAL SIMULATION (Benford Compliant)
    # Reset with a clean account.
    acc_clean = Account(name="Clean Account", type="ASSET", country_code="US", currency="USD")
    session.add(acc_clean)
    session.commit()
    session.refresh(acc_clean)

    # Inject natural logarithmic distribution (lots of small numbers, few big ones).
    # Digit 1 should appear ~30% of the time.
    with patch.object(FinancialIntelligence, 'analyze_transaction', return_value={"status": "SAFE", "message": "Test Override"}):
        # Create a Benford-compliant distribution (Total 50 items)
        # Digit: Count -> 1:15 (30%), 2:9 (18%), 3:6 (12%), 4:5 (10%), etc.
        distribution = [(1, 15), (2, 9), (3, 6), (4, 5), (5, 4), (6, 3), (7, 3), (8, 3), (9, 2)]
        for digit, count in distribution:
            for _ in range(count):
                ledger.record_transaction(debit_id=acc_clean.id, credit_id=counterparty.id, amount=Decimal(f"{digit}0.00"), desc=f"Natural Tx {digit}")

    result_clean = intel.audit_benford_compliance(acc_clean.id)
    assert result_clean["status"] == "PASS"