import numpy as np
from sqlmodel import select, Session
from app.models import Account, JournalEntry, AccountStatus
from decimal import Decimal
import math
from typing import List, Dict

class FinancialIntelligence:
    def __init__(self, session: Session):
        self.session = session

    def analyze_transaction(self, amount: Decimal, debit_id: int):
        # Fetch the debit account to get pre-calculated statistics
        account = self.session.exec(select(Account).where(Account.id == debit_id)).first()
        
        if not account:
            return {
                "z_score": 0.0,
                "status": "ERROR",
                "message": "Debit account not found for analysis."
            }

        # Not enough data points to build a reliable profile yet.
        # We use total_transactions from the account itself now
        if account.total_transactions < 3 or account.std_dev_transaction_amount == 0:
            return {
                "z_score": 0.0,
                "status": "LEARNING",
                "message": "Need more data to build behavioral profile or standard deviation is zero."
            }

        mean = account.avg_transaction_amount
        std_dev = account.std_dev_transaction_amount

        # Calculate Z-Score (distance from mean in sigmas)
        z_score = abs(float(amount) - mean) / std_dev 
        
        # Intelligence Decision
        if z_score > 3.0:
            status = "CRITICAL_ANOMALY"
            msg = f"Alert: This is {z_score:.2f} sigma away from average! Possible fraud or fat-finger error."
        elif z_score > 2.0:
            status = "WARNING"
            msg = "Caution: Unusual transaction size detected."
        else:
            status = "NORMAL"
            msg = "Transaction within normal behavioral bounds."

        return {
            "z_score": round(float(z_score), 2),
            "status": status,
            "message": msg
        }

    def audit_benford_compliance(self, account_id: int, limit: int = 100) -> Dict:
        """
        Performs a Benford's Law analysis on transaction data.
        Checks if the leading digits of the account's transactions follow the 
        natural distribution expected in genuine financial data.
        
        Useful for detecting:
        1. Artificial data generation (Money Laundering)
        2. Manual accounting manipulation
        """
        # 1. Fetch recent transaction amounts
        statement = select(JournalEntry.amount).where(
            JournalEntry.debit_account_id == account_id
        ).limit(limit)
        amounts = self.session.exec(statement).all()

        if len(amounts) < 30:
            return {"status": "SKIPPED", "reason": "Insufficient data for Benford analysis (min 30)"}

        # 2. Extract Leading Digits (1-9)
        leading_counts = {d: 0 for d in range(1, 10)}
        total_count = 0
        
        for amt in amounts:
            if amt <= 0: continue
            # Get the leading digit (e.g., 500 -> 5, 0.04 -> 4)
            first_digit = int(str(float(amt)).replace('.', '').lstrip('0')[0])
            leading_counts[first_digit] += 1
            total_count += 1

        if total_count == 0:
            return {"status": "SKIPPED", "reason": "No positive amounts found"}

        # 3. Compare with Benford's Expected Frequencies
        # Benford: P(d) = log10(1 + 1/d)
        benford_probs = {d: math.log10(1 + 1/d) for d in range(1, 10)}
        
        # Chi-Square like simple deviation check
        max_deviation = 0.0
        suspicious_digit = -1

        for d in range(1, 10):
            actual_prob = leading_counts[d] / total_count
            expected_prob = benford_probs[d]
            deviation = abs(actual_prob - expected_prob)
            
            if deviation > max_deviation:
                max_deviation = deviation
                suspicious_digit = d

        # Threshold: Deviation > 0.15 (15%) is highly suspicious in Benford terms
        if max_deviation > 0.15:
            # COMPLIANCE ACTION:
            # If fraud is statistically probable, freeze the account immediately.
            account = self.session.get(Account, account_id)
            if account and account.status == AccountStatus.ACTIVE:
                account.status = AccountStatus.FROZEN
                account.risk_score = "CRITICAL"
                self.session.add(account)
                self.session.commit()
                self.session.refresh(account)

            return {
                "status": "FRAUD_RISK",
                "risk_level": "HIGH",
                "message": f"Benford Violation! Digit {suspicious_digit} appears {leading_counts[suspicious_digit]/total_count:.1%} of time. Account has been FROZEN."
            }
        
        return {
            "status": "PASS",
            "risk_level": "LOW",
            "message": "Transaction distribution adheres to Benford's Law."
        }