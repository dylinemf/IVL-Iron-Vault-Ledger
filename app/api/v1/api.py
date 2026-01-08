from fastapi import APIRouter
from app.api.v1.endpoints import ledger, auth, intelligence

api_router = APIRouter()
api_router.include_router(ledger.router, prefix="/ledger", tags=["ledger"])
api_router.include_router(auth.auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(intelligence.router, prefix="/intelligence", tags=["intelligence"])
