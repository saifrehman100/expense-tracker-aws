"""Lambda handler for expense operations."""

import json
import os
import logging
from typing import Dict, Any
import sys

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success_response, error_response, validation_error_response, not_found_response
from shared.validators import validate_required_fields
from shared.exceptions import ExpenseTrackerException, ValidationError, NotFoundError
from expenses.service import ExpenseService

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize service
expense_service = ExpenseService()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for expense operations.

    Handles:
    - GET /expenses - List expenses
    - GET /expenses/{id} - Get expense details
    - PUT /expenses/{id} - Update expense
    - DELETE /expenses/{id} - Delete expense
    - GET /expenses/summary - Get expense summary

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
        if path == '/expenses' and http_method == 'GET':
            return handle_list(event, user_id)
        elif path == '/expenses/summary' and http_method == 'GET':
            return handle_summary(event, user_id)
        elif path.startswith('/expenses/') and http_method == 'GET':
            return handle_get(event, user_id)
        elif path.startswith('/expenses/') and http_method == 'PUT':
            return handle_update(event, user_id)
        elif path.startswith('/expenses/') and http_method == 'DELETE':
            return handle_delete(event, user_id)
        else:
            return error_response("Route not found", status_code=404)

    except ExpenseTrackerException as e:
        logger.error(f"Application error: {str(e)}")
        return error_response(e.message, status_code=e.status_code)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return error_response("Internal server error", status_code=500)


def handle_list(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Handle list expenses.

    Args:
        event: Lambda event
        user_id: User ID

    Returns:
        API Gateway response
    """
    try:
        # Get query parameters
        query_params = event.get('queryStringParameters') or {}

        category = query_params.get('category')
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')
        limit = int(query_params.get('limit', 50))
        last_key = query_params.get('last_key')

        # Parse last_key if provided
        last_evaluated_key = None
        if last_key:
            try:
                last_evaluated_key = json.loads(last_key)
            except json.JSONDecodeError:
                return validation_error_response("Invalid last_key format")

        # List expenses
        result = expense_service.list_expenses(
            user_id=user_id,
            category=category,
            start_date=start_date,
            end_date=end_date,
            limit=min(limit, 100),  # Cap at 100
            last_evaluated_key=last_evaluated_key
        )

        response_data = {
            'expenses': result['expenses'],
            'count': result['count']
        }

        if result['last_evaluated_key']:
            response_data['last_key'] = json.dumps(result['last_evaluated_key'])

        return success_response(data=response_data)

    except Exception as e:
        logger.error(f"List error: {str(e)}")
        return error_response(str(e), status_code=400)


def handle_get(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Handle get expense details.

    Args:
        event: Lambda event
        user_id: User ID

    Returns:
        API Gateway response
    """
    try:
        # Extract expense ID from path
        path_params = event.get('pathParameters') or {}
        expense_id = path_params.get('id')

        if not expense_id:
            return validation_error_response("Expense ID is required")

        # Get expense
        expense = expense_service.get_expense(user_id, expense_id)

        return success_response(data=expense)

    except NotFoundError as e:
        return not_found_response(str(e))
    except Exception as e:
        logger.error(f"Get error: {str(e)}")
        return error_response(str(e), status_code=400)


def handle_update(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Handle update expense.

    Args:
        event: Lambda event
        user_id: User ID

    Returns:
        API Gateway response
    """
    try:
        # Extract expense ID from path
        path_params = event.get('pathParameters') or {}
        expense_id = path_params.get('id')

        if not expense_id:
            return validation_error_response("Expense ID is required")

        # Parse request body
        body = json.loads(event.get('body', '{}'))

        if not body:
            return validation_error_response("No updates provided")

        # Update expense
        updated_expense = expense_service.update_expense(user_id, expense_id, body)

        logger.info(f"Expense updated successfully: {expense_id}")

        return success_response(
            data=updated_expense,
            message="Expense updated successfully"
        )

    except ValidationError as e:
        return validation_error_response(str(e))
    except NotFoundError as e:
        return not_found_response(str(e))
    except Exception as e:
        logger.error(f"Update error: {str(e)}")
        return error_response(str(e), status_code=400)


def handle_delete(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Handle delete expense.

    Args:
        event: Lambda event
        user_id: User ID

    Returns:
        API Gateway response
    """
    try:
        # Extract expense ID from path
        path_params = event.get('pathParameters') or {}
        expense_id = path_params.get('id')

        if not expense_id:
            return validation_error_response("Expense ID is required")

        # Delete expense
        expense_service.delete_expense(user_id, expense_id)

        logger.info(f"Expense deleted successfully: {expense_id}")

        return success_response(
            message="Expense deleted successfully"
        )

    except NotFoundError as e:
        return not_found_response(str(e))
    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        return error_response(str(e), status_code=400)


def handle_summary(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Handle get expense summary.

    Args:
        event: Lambda event
        user_id: User ID

    Returns:
        API Gateway response
    """
    try:
        # Get query parameters
        query_params = event.get('queryStringParameters') or {}
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')

        # Get summary
        summary = expense_service.get_summary(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )

        return success_response(data=summary)

    except Exception as e:
        logger.error(f"Summary error: {str(e)}")
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
