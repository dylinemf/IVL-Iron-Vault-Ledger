from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime

class EncryptionKey(SQLModel, table=True):
    """
    Stores encryption keys separately.
    Crypto-Shredding: Delete this row -> JournalEntry description becomes unreadable garbage.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    key_data: str # Fernet key wrapped (encrypted) with the Master Key.
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
