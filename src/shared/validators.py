"""Validation utilities for the expense tracker application."""

import re
from typing import Any, Dict, List, Optional
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .exceptions import ValidationError


# Expense categories
VALID_CATEGORIES = [
    "Food & Dining",
    "Transportation",
    "Shopping",
    "Entertainment",
    "Utilities",
    "Healthcare",
    "Travel",
    "Education",
    "Groceries",
    "Other"
]

# Budget periods
VALID_PERIODS = ["weekly", "monthly"]


def validate_email(email: str) -> str:
    """
    Validate email format.

    Args:
        email: Email address to validate

    Returns:
        Validated email

    Raises:
        ValidationError: If email is invalid
    """
    if not email:
        raise ValidationError("Email is required")

    email = email.strip().lower()
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if not re.match(pattern, email):
        raise ValidationError("Invalid email format")

    return email


def validate_password(password: str) -> str:
    """
    Validate password strength.

    Args:
        password: Password to validate

    Returns:
        Validated password

    Raises:
        ValidationError: If password is invalid
    """
    if not password:
        raise ValidationError("Password is required")

    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long")

    if not re.search(r'[A-Z]', password):
        raise ValidationError("Password must contain at least one uppercase letter")

    if not re.search(r'[a-z]', password):
        raise ValidationError("Password must contain at least one lowercase letter")

    if not re.search(r'\d', password):
        raise ValidationError("Password must contain at least one number")

    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValidationError("Password must contain at least one special character")

    return password


def validate_amount(amount: Any) -> Decimal:
    """
    Validate monetary amount.

    Args:
        amount: Amount to validate

    Returns:
        Validated amount as Decimal

    Raises:
        ValidationError: If amount is invalid
    """
    if amount is None:
        raise ValidationError("Amount is required")

    try:
        decimal_amount = Decimal(str(amount))
    except (InvalidOperation, ValueError):
        raise ValidationError("Invalid amount format")

    if decimal_amount <= 0:
        raise ValidationError("Amount must be greater than 0")

    if decimal_amount > Decimal('999999.99'):
        raise ValidationError("Amount is too large")

    # Ensure at most 2 decimal places
    if decimal_amount.as_tuple().exponent < -2:
        raise ValidationError("Amount can have at most 2 decimal places")

    return decimal_amount


def validate_date(date_str: str) -> str:
    """
    Validate date format (ISO 8601: YYYY-MM-DD).

    Args:
        date_str: Date string to validate

    Returns:
        Validated date string

    Raises:
        ValidationError: If date is invalid
    """
    if not date_str:
        raise ValidationError("Date is required")

    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return date_str
    except ValueError:
        raise ValidationError("Invalid date format. Use YYYY-MM-DD")


def validate_category(category: str) -> str:
    """
    Validate expense category.

    Args:
        category: Category to validate

    Returns:
        Validated category

    Raises:
        ValidationError: If category is invalid
    """
    if not category:
        raise ValidationError("Category is required")

    if category not in VALID_CATEGORIES:
        raise ValidationError(
            f"Invalid category. Must be one of: {', '.join(VALID_CATEGORIES)}"
        )

    return category


def validate_period(period: str) -> str:
    """
    Validate budget period.

    Args:
        period: Period to validate

    Returns:
        Validated period

    Raises:
        ValidationError: If period is invalid
    """
    if not period:
        raise ValidationError("Period is required")

    period = period.lower()

    if period not in VALID_PERIODS:
        raise ValidationError(
            f"Invalid period. Must be one of: {', '.join(VALID_PERIODS)}"
        )

    return period


def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> None:
    """
    Validate that required fields are present in data.

    Args:
        data: Data dictionary to validate
        required_fields: List of required field names

    Raises:
        ValidationError: If any required field is missing
    """
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]

    if missing_fields:
        raise ValidationError(
            f"Missing required fields: {', '.join(missing_fields)}"
        )


def validate_file_extension(filename: str, allowed_extensions: List[str]) -> str:
    """
    Validate file extension.

    Args:
        filename: Filename to validate
        allowed_extensions: List of allowed extensions (e.g., ['.jpg', '.png'])

    Returns:
        Validated filename

    Raises:
        ValidationError: If file extension is not allowed
    """
    if not filename:
        raise ValidationError("Filename is required")

    extension = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''

    if not extension or f'.{extension}' not in [ext.lower() for ext in allowed_extensions]:
        raise ValidationError(
            f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
        )

    return filename


def validate_file_size(size_bytes: int, max_size_mb: int = 5) -> int:
    """
    Validate file size.

    Args:
        size_bytes: File size in bytes
        max_size_mb: Maximum allowed size in MB (default: 5MB)

    Returns:
        Validated size

    Raises:
        ValidationError: If file size exceeds limit
    """
    max_size_bytes = max_size_mb * 1024 * 1024

    if size_bytes > max_size_bytes:
        raise ValidationError(f"File size exceeds {max_size_mb}MB limit")

    return size_bytes


def validate_base64_image(base64_string: str) -> str:
    """
    Validate base64-encoded image.

    Args:
        base64_string: Base64-encoded string

    Returns:
        Validated base64 string

    Raises:
        ValidationError: If base64 string is invalid
    """
    if not base64_string:
        raise ValidationError("Image data is required")

    # Remove data URI prefix if present
    if ',' in base64_string:
        header, base64_string = base64_string.split(',', 1)
        # Validate it's an image
        if not header.startswith('data:image/'):
            raise ValidationError("Invalid image format")

    # Validate base64 format
    try:
        import base64
        base64.b64decode(base64_string, validate=True)
        return base64_string
    except Exception:
        raise ValidationError("Invalid base64 encoding")


def validate_threshold(threshold: Any) -> int:
    """
    Validate alert threshold percentage.

    Args:
        threshold: Threshold value to validate

    Returns:
        Validated threshold

    Raises:
        ValidationError: If threshold is invalid
    """
    try:
        threshold = int(threshold)
    except (ValueError, TypeError):
        raise ValidationError("Threshold must be an integer")

    if threshold < 0 or threshold > 100:
        raise ValidationError("Threshold must be between 0 and 100")

    return threshold


def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize string input by removing dangerous characters.

    Args:
        value: String to sanitize
        max_length: Optional maximum length

    Returns:
        Sanitized string

    Raises:
        ValidationError: If string is invalid
    """
    if not isinstance(value, str):
        raise ValidationError("Value must be a string")

    # Remove leading/trailing whitespace
    value = value.strip()

    if max_length and len(value) > max_length:
        raise ValidationError(f"Value exceeds maximum length of {max_length}")

    return value
