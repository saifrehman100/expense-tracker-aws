"""Lambda handler for receipt operations."""

import json
import os
import logging
from typing import Dict, Any
import sys

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success_response, error_response, validation_error_response, not_found_response
from shared.validators import validate_required_fields
from shared.exceptions import ExpenseTrackerException, ValidationError
from receipts.upload import ReceiptUploadService

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize service
upload_service = ReceiptUploadService()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for receipt operations.

    Handles:
    - POST /receipts/upload - Upload receipt
    - GET /receipts - List receipts
    - GET /receipts/{id} - Get receipt details
    - DELETE /receipts/{id} - Delete receipt

    Args:
        event: Lambda event
        context: Lambda context

    Returns:
        API Gateway response
    """
    try:
        # Log request
        logger.info(f"Request: {event.get('httpMethod')} {event.get('path')}")

        # Get user ID from Cognito authorizer
        user_id = get_user_id(event)
        if not user_id:
            return error_response("Unauthorized", status_code=401)

        # Get HTTP method and path
        http_method = event.get('httpMethod')
        path = event.get('path')

        # Route request
        if path == '/receipts/upload' and http_method == 'POST':
            return handle_upload(event, user_id)
        elif path == '/receipts' and http_method == 'GET':
            return handle_list(event, user_id)
        elif path.startswith('/receipts/') and http_method == 'GET':
            return handle_get(event, user_id)
        elif path.startswith('/receipts/') and http_method == 'DELETE':
            return handle_delete(event, user_id)
        else:
            return error_response("Route not found", status_code=404)

    except ExpenseTrackerException as e:
        logger.error(f"Application error: {str(e)}")
        return error_response(e.message, status_code=e.status_code)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return error_response("Internal server error", status_code=500)


def handle_upload(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Handle receipt upload.

    Args:
        event: Lambda event
        user_id: User ID

    Returns:
        API Gateway response
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))

        # Validate required fields
        validate_required_fields(body, ['image_data', 'filename'])

        image_data = body['image_data']
        filename = body['filename']
        content_type = body.get('content_type', 'image/jpeg')

        # Upload receipt
        receipt = upload_service.upload_receipt(
            user_id=user_id,
            image_data=image_data,
            filename=filename,
            content_type=content_type
        )

        logger.info(f"Receipt uploaded successfully: {receipt['receipt_id']}")

        return success_response(
            data=receipt,
            message="Receipt uploaded successfully. Processing will begin shortly.",
            status_code=201
        )

    except ValidationError as e:
        return validation_error_response(str(e))
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return error_response(str(e), status_code=400)


def handle_list(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Handle list receipts.

    Args:
        event: Lambda event
        user_id: User ID

    Returns:
        API Gateway response
    """
    try:
        # Get query parameters
        query_params = event.get('queryStringParameters') or {}
        limit = int(query_params.get('limit', 50))
        last_key = query_params.get('last_key')

        # Parse last_key if provided
        last_evaluated_key = None
        if last_key:
            try:
                last_evaluated_key = json.loads(last_key)
            except json.JSONDecodeError:
                return validation_error_response("Invalid last_key format")

        # List receipts
        result = upload_service.list_receipts(
            user_id=user_id,
            limit=min(limit, 100),  # Cap at 100
            last_evaluated_key=last_evaluated_key
        )

        response_data = {
            'receipts': result['receipts'],
            'count': len(result['receipts'])
        }

        if result['last_evaluated_key']:
            response_data['last_key'] = json.dumps(result['last_evaluated_key'])

        return success_response(data=response_data)

    except Exception as e:
        logger.error(f"List error: {str(e)}")
        return error_response(str(e), status_code=400)


def handle_get(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Handle get receipt details.

    Args:
        event: Lambda event
        user_id: User ID

    Returns:
        API Gateway response
    """
    try:
        # Extract receipt ID from path
        path_params = event.get('pathParameters') or {}
        receipt_id = path_params.get('id')

        if not receipt_id:
            return validation_error_response("Receipt ID is required")

        # Get receipt
        receipt = upload_service.get_receipt(user_id, receipt_id)

        return success_response(data=receipt)

    except ValidationError as e:
        return not_found_response(str(e))
    except Exception as e:
        logger.error(f"Get error: {str(e)}")
        return error_response(str(e), status_code=400)


def handle_delete(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Handle delete receipt.

    Args:
        event: Lambda event
        user_id: User ID

    Returns:
        API Gateway response
    """
    try:
        # Extract receipt ID from path
        path_params = event.get('pathParameters') or {}
        receipt_id = path_params.get('id')

        if not receipt_id:
            return validation_error_response("Receipt ID is required")

        # Delete receipt
        upload_service.delete_receipt(user_id, receipt_id)

        logger.info(f"Receipt deleted successfully: {receipt_id}")

        return success_response(
            message="Receipt deleted successfully"
        )

    except ValidationError as e:
        return not_found_response(str(e))
    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        return error_response(str(e), status_code=400)


def get_user_id(event: Dict[str, Any]) -> str:
    """
    Extract user ID from Cognito authorizer claims.

    Args:
        event: Lambda event

    Returns:
        User ID (sub claim)
    """
    request_context = event.get('requestContext', {})
    authorizer = request_context.get('authorizer', {})
    claims = authorizer.get('claims', {})
    return claims.get('sub')
