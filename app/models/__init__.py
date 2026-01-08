from typing import Optional
from enum import Enum
from datetime import datetime
from sqlmodel import Field, SQLModel, create_engine, AutoString
import hashlib, json
from decimal import Decimal
from app.models.encryption import EncryptionKey # Import model baru

from app.core.i18n import SupportedCountry, SupportedCurrency

class AccountStatus(str, Enum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"       # Hard block (Fraud detected)
    SUSPENDED = "SUSPENDED" # Soft block (Admin review needed)
    CLOSED = "CLOSED"

# Standard chart of accounts (Cash, Revenue, Equity, etc.)
class Account(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    type: str  # ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE
    country_code: str = Field(description="ISO 3166-1 alpha-2 country code") # Could use i18n as enum. But for now, keep it simple
    currency: str # Could use i18n as enum. But for now, keep it simple
    iban: Optional[str] = Field(default=None, unique=True, index=True) # Real-world identifier
    status: AccountStatus = Field(default=AccountStatus.ACTIVE, sa_type=AutoString) # Compliance Status
    risk_score: str = Field(default="LOW") # LOW, MEDIUM, HIGH, CRITICAL

    # Fields for Financial Intelligence pre-calculation
    total_transactions: int = Field(default=0, ge=0)
    total_amount: Decimal = Field(default=Decimal("0.0"), ge=0)
    avg_transaction_amount: float = Field(default=0.0, ge=0)
    std_dev_transaction_amount: float = Field(default=0.0, ge=0)

# The immutable journal. Entries lock each other via hash chains.
class JournalEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Double Entry Basics
    debit_account_id: int = Field(foreign_key="account.id")
    credit_account_id: int = Field(foreign_key="account.id")
    amount: Decimal = Field(default=0, decimal_places=2)
    description: str
    encryption_key_id: Optional[int] = Field(default=None, foreign_key="encryptionkey.id") # Reference to the encryption key for shredding
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # THE IRON-VAULT SECURITY FEATURES
    previous_hash: str # Hash of the previous entry (creates the chain)
    hash: str          # Current entry hash (includes prev_hash)

    def calculate_hash(self) -> str:
        # Using a dict to ensure consistent ordering for hashing
        payload = {
            "debit": self.debit_account_id,
            "credit": self.credit_account_id,
            "amount": str(self.amount), # Decimal -> string to avoid float precision issues during hashing
            "description": self.description,
            "timestamp": str(self.timestamp),
            "prev_hash": self.previous_hash
        }
        # Sort keys to ensure deterministic hashing
        dump = json.dumps(payload, sort_keys=True).encode()
        return hashlib.sha256(dump).hexdigest()

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, min_length=3, max_length=50)
    hashed_password: str
    full_name: Optional[str] = Field(default=None, max_length=100)