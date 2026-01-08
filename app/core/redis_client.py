import redis
from app.core.config import settings

# Initialize Redis client
# Decode responses to get strings instead of bytes
redis_client = redis.StrictRedis.from_url(settings.REDIS_URL, decode_responses=True)

def get_redis_client():
    """Dependency for FastAPI to get a Redis client instance."""
    return redis_client
