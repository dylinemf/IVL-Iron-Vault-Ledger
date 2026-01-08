import sys
import os

# Add project root to sys.path to allow importing 'app' module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from app.db.session import engine
from app.models import Account

def seed_accounts():
    print("Initializing database seed...")
    
    with Session(engine) as session:
        # Check if accounts already exist to prevent duplicates
        existing_account = session.exec(select(Account)).first()
        if existing_account:
            print("Warning: Accounts already exist in the database. Seeding skipped.")
            return

        # Standard accounts to be created
        accounts = [
            # Switzerland (CHF)
            Account(name="Swiss Cash Wallet", type="asset", country_code="CH", currency="CHF", iban="CH9300700111111111111", total_transactions=0, total_amount=0, avg_transaction_amount=0, std_dev_transaction_amount=0),
            Account(name="Swiss Product Sales", type="revenue", country_code="CH", currency="CHF", iban="CH9300700333333333333", total_transactions=0, total_amount=0, avg_transaction_amount=0, std_dev_transaction_amount=0),
            
            # Germany (EUR)
            Account(name="German Bank Account", type="asset", country_code="DE", currency="EUR", iban="DE89370400440532013000", total_transactions=0, total_amount=0, avg_transaction_amount=0, std_dev_transaction_amount=0),
            Account(name="German Product Sales", type="revenue", country_code="DE", currency="EUR", iban="DE89370400440532013001", total_transactions=0, total_amount=0, avg_transaction_amount=0, std_dev_transaction_amount=0),

            # France (EUR)
            Account(name="French Bank Account", type="asset", country_code="FR", currency="EUR", iban="FR7630006000011234567890189", total_transactions=0, total_amount=0, avg_transaction_amount=0, std_dev_transaction_amount=0),
            Account(name="French Operational Expense", type="expense", country_code="FR", currency="EUR", iban="FR7630006000011234567890190", total_transactions=0, total_amount=0, avg_transaction_amount=0, std_dev_transaction_amount=0),

            # Austria (EUR)
            Account(name="Austrian Bank Account", type="asset", country_code="AT", currency="EUR", iban="AT611904400234573201", total_transactions=0, total_amount=0, avg_transaction_amount=0, std_dev_transaction_amount=0),
        ]

        for acc in accounts:
            session.add(acc)
        
        session.commit()

        # Refresh to get IDs
        for acc in accounts:
            session.refresh(acc)
        
        print("Seeding complete. Accounts created:")
        print("-" * 50)
        for acc in accounts:
            print(f"ID: {acc.id:<3} | IBAN: {acc.iban:<30} | Name: {acc.name:<25} | Country: {acc.country_code:<3} | Currency: {acc.currency}")
        print("-" * 50)

        # Dynamic Cheat Sheet for Testing
        print("\n[TESTING CHEAT SHEET]")
        print("1. To record INCOME in CHF (e.g., Swiss Sales):")
        print(f"   -> debit_id:  {accounts[0].id} ({accounts[0].name})")
        print(f"   -> credit_id: {accounts[1].id} ({accounts[1].name})")
        print("\n2. To record INCOME in EUR (e.g., German Sales):")
        print(f"   -> debit_id:  {accounts[2].id} ({accounts[2].name})")
        print(f"   -> credit_id: {accounts[3].id} ({accounts[3].name})")
        print("\n3. To record EXPENSE in EUR (e.g., French Bill Payment):")
        print(f"   -> debit_id:  {accounts[5].id} ({accounts[5].name})")
        print(f"   -> credit_id: {accounts[4].id} ({accounts[4].name})")
        print("\n4. To record a Transfer between EUR accounts (DE to AT):")
        print(f"   -> debit_id:  {accounts[6].id} ({accounts[6].name})")
        print(f"   -> credit_id: {accounts[2].id} ({accounts[2].name})")

if __name__ == "__main__":
    seed_accounts()
