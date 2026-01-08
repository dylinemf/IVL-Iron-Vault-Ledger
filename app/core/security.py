from cryptography.fernet import Fernet
from passlib.context import CryptContext
from app.core.config import settings

# For password hashing
pwd_context = CryptContext(schemes=["sha256_crypt"])

# The key is now loaded from config, which gets it from an environment variable or .env file
cipher_suite = Fernet(settings.ENCRYPTION_KEY.encode())

# Function to hash a password
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# Function to verify a password
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def encrypt_data(data: str) -> str:
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(token: str) -> str:
    return cipher_suite.decrypt(token.encode()).decode()