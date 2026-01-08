from pydantic_settings import BaseSettings, SettingsConfigDict
from cryptography.fernet import Fernet

class Settings(BaseSettings):
    # SECRET_KEY for JWT. In production, this should be a long, randomly generated string
    # and MUST NOT be generated on the fly. Loaded from environment or .env file.
    # For production, consider using a dedicated secret management system
    # (e.g., HashiCorp Vault, AWS Secrets Manager) and inject into environment variables.
    SECRET_KEY: str # No default. Fails if missing. Ensures persistence across restarts.
    ENCRYPTION_KEY: str # Dedicated key for Fernet encryption (must be 32 url-safe base64-encoded bytes)
    
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ironvault" # Default to Postgres (Local)
    REDIS_URL: str = "redis://localhost:6379/0" # Redis connection string

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30 minutes for JWT token expiry
    ALGORITHM: str = "HS256" # Algorithm for JWT signing

    # Configure Pydantic Settings to load from .env file for local development.
    # For production, environment variables take precedence.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
