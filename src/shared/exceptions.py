"""Custom exceptions for the expense tracker application."""


class ExpenseTrackerException(Exception):
    """Base exception for all expense tracker errors."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(ExpenseTrackerException):
    """Raised when input validation fails."""

    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class AuthenticationError(ExpenseTrackerException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class AuthorizationError(ExpenseTrackerException):
    """Raised when user is not authorized."""

    def __init__(self, message: str = "Not authorized"):
        super().__init__(message, status_code=403)


class NotFoundError(ExpenseTrackerException):
    """Raised when a resource is not found."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class ConflictError(ExpenseTrackerException):
    """Raised when there's a conflict (e.g., duplicate resource)."""

    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message, status_code=409)


class OCRProcessingError(ExpenseTrackerException):
    """Raised when OCR processing fails."""

    def __init__(self, message: str = "OCR processing failed"):
        super().__init__(message, status_code=500)


class StorageError(ExpenseTrackerException):
    """Raised when storage operations fail."""

    def __init__(self, message: str = "Storage operation failed"):
        super().__init__(message, status_code=500)


class DatabaseError(ExpenseTrackerException):
    """Raised when database operations fail."""

    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message, status_code=500)
