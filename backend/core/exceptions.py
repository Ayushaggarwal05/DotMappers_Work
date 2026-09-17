from typing import Any, Optional, Dict
from fastapi import Request, status
from fastapi.responses import JSONResponse
from backend.core.logging import logger

class AppException(Exception):
    """Base application exception."""
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppException):
    """Resource not found exception."""
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=status.HTTP_404_NOT_FOUND, details=details)


class DatasetNotFoundError(AppException):
    """Dataset file not found exception."""
    def __init__(self, dataset_path: str):
        super().__init__(
            message=f"Dataset file not found at path: {dataset_path}",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"dataset_path": dataset_path}
        )


class DataValidationError(AppException):
    """Data validation failure exception."""
    def __init__(self, message: str = "Validation error", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, details=details)


class IngestionError(AppException):
    """Dataset ingestion error."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, details=details)


class DatabaseError(AppException):
    """Database operation failure."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, details=details)


class QueryExecutionError(AppException):
    """Analytics/query execution error."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, status_code=status.HTTP_400_BAD_REQUEST, details=details)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """FastAPI global exception handler for custom AppException."""
    logger.error(
        f"Application error on {request.method} {request.url.path}: {exc.message} | Details: {exc.details}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "type": exc.__class__.__name__,
                "message": exc.message,
                "details": exc.details
            }
        }
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """FastAPI handler for uncaught unexpected exceptions."""
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "type": "InternalServerError",
                "message": "An unexpected server error occurred."
            }
        }
    )
