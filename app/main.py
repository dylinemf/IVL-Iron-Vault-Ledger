from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from app.api.v1.api import api_router
from app.core.logging_config import setup_logging
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager to handle application startup and shutdown events.
    """
    setup_logging()
    logger.info("Logging has been configured.")
    logger.info("Application startup complete.")
    yield
    logger.info("Application shutting down.")

app = FastAPI(title="Iron-Vault Ledger API", lifespan=lifespan)

# 1. Custom Handler for HTTP Exceptions (404, 401, 403, etc.)
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.detail,
            "data": None
        }
    )

# Custom exception handler for ValueError
@app.exception_handler(ValueError)
async def value_error_exception_handler(request: Request, exc: ValueError):
    logger.warning("ValueError occurred", extra={"extra_fields": {"error": str(exc), "path": request.url.path}})
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "status": "error",
            "message": str(exc),
            "data": None
        },
    )

# Generic exception handler for all other exceptions
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception occurred", extra={"extra_fields": {"error": str(exc), "path": request.url.path}}, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "An unexpected error occurred. Please try again later.",
            "data": None # Don't leak stack trace to user
        },
    )


app.include_router(api_router, prefix="/api/v1")
