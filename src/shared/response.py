"""Response utilities for Lambda functions."""

import json
from typing import Any, Dict, Optional
from datetime import datetime, date
from decimal import Decimal


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for Decimal and datetime objects."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def success_response(
    data: Any = None,
    message: Optional[str] = None,
    status_code: int = 200,
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Create a standardized success response.

    Args:
        data: Response data
        message: Optional success message
        status_code: HTTP status code (default: 200)
        headers: Optional additional headers

    Returns:
        Lambda proxy response dictionary
    """
    body = {
        "success": True,
        "data": data
    }

    if message:
        body["message"] = message

    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS"
    }

    if headers:
        default_headers.update(headers)

    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": json.dumps(body, cls=DecimalEncoder)
    }


def error_response(
    message: str,
    status_code: int = 500,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response.

    Args:
        message: Error message
        status_code: HTTP status code (default: 500)
        error_code: Optional error code
        details: Optional error details
        headers: Optional additional headers

    Returns:
        Lambda proxy response dictionary
    """
    body = {
        "success": False,
        "error": {
            "message": message,
            "code": error_code or f"ERROR_{status_code}"
        }
    }

    if details:
        body["error"]["details"] = details

    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS"
    }

    if headers:
        default_headers.update(headers)

    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": json.dumps(body, cls=DecimalEncoder)
    }


def validation_error_response(
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create a validation error response."""
    return error_response(
        message=message,
        status_code=400,
        error_code="VALIDATION_ERROR",
        details=details
    )


def not_found_response(message: str = "Resource not found") -> Dict[str, Any]:
    """Create a not found error response."""
    return error_response(
        message=message,
        status_code=404,
        error_code="NOT_FOUND"
    )


def unauthorized_response(message: str = "Unauthorized") -> Dict[str, Any]:
    """Create an unauthorized error response."""
    return error_response(
        message=message,
        status_code=401,
        error_code="UNAUTHORIZED"
    )


def forbidden_response(message: str = "Forbidden") -> Dict[str, Any]:
    """Create a forbidden error response."""
    return error_response(
        message=message,
        status_code=403,
        error_code="FORBIDDEN"
    )
