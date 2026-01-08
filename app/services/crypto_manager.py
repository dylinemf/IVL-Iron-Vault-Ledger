from cryptography.fernet import Fernet
from sqlmodel import Session
from app.models.encryption import EncryptionKey
from app.core.config import settings

class CryptoManager:
    def __init__(self, session: Session):
        self.session = session
        self.master_key = settings.ENCRYPTION_KEY

    def create_key(self) -> EncryptionKey:
        # 1. Generate a fresh key for this specific transaction.
        new_key = Fernet.generate_key()
        
        # 2. Wrap (encrypt) this new key with the Master Key for DB storage.
        master_fernet = Fernet(self.master_key)
        encrypted_key_data = master_fernet.encrypt(new_key).decode()
        
        # 3. Persist to DB.
        key_entry = EncryptionKey(key_data=encrypted_key_data)
        self.session.add(key_entry)
        self.session.flush()
        self.session.refresh(key_entry)
        return key_entry

    def encrypt_text(self, text: str, key_entry: EncryptionKey) -> str:
        # 1. Unwrap the key.
        master_fernet = Fernet(self.master_key)
        raw_key = master_fernet.decrypt(key_entry.key_data.encode())
        
        # 2. Use the unwrapped key to encrypt the actual data.
        f = Fernet(raw_key)
        return f.encrypt(text.encode()).decode()

    def shred_key(self, key_id: int):
        # THE SHREDDER: Nuke the key from the DB.
        # Data encrypted with this key is now permanently lost.
        key = self.session.get(EncryptionKey, key_id)
        if key:
            self.session.delete(key)
            self.session.commit()