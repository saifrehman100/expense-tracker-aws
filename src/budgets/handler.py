"""Lambda handler for budget operations."""

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
from budgets.service import BudgetService

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize service
budget_service = BudgetService()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for budget operations.

    Handles:
    - POST /budgets - Create budget
    - GET /budgets - List budgets
    - PUT /budgets/{id} - Update budget
    - DELETE /budgets/{id} - Delete budget

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
        if path == '/budgets' and http_method == 'POST':
            return handle_create(event, user_id)
        elif path == '/budgets' and http_method == 'GET':
            return handle_list(event, user_id)
        elif path.startswith('/budgets/') and http_method == 'PUT':
            return handle_update(event, user_id)
        elif path.startswith('/budgets/') and http_method == 'DELETE':
            return handle_delete(event, user_id)
        else:
            return error_response("Route not found", status_code=404)

    except ExpenseTrackerException as e:
        logger.error(f"Application error: {str(e)}")
        return error_response(e.message, status_code=e.status_code)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return error_response("Internal server error", status_code=500)


def handle_create(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Handle create budget.

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
        validate_required_fields(body, ['category', 'amount', 'period'])

        category = body['category']
        amount = body['amount']
        period = body['period']
        alert_threshold = body.get('alert_threshold', 90)

        # Create budget
        budget = budget_service.create_budget(
            user_id=user_id,
            category=category,
            amount=amount,
            period=period,
            alert_threshold=alert_threshold
        )

        logger.info(f"Budget created successfully: {budget['budget_id']}")

        return success_response(
            data=budget,
            message="Budget created successfully",
            status_code=201
        )

    except ValidationError as e:
        return validation_error_response(str(e))
    except Exception as e:
        logger.error(f"Create error: {str(e)}")
        return error_response(str(e), status_code=400)


def handle_list(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Handle list budgets.

    Args:
        event: Lambda event
        user_id: User ID

    Returns:
        API Gateway response
    """
    try:
        # Get query parameters
        query_params = event.get('queryStringParameters') or {}
        active_only = query_params.get('active_only', 'true').lower() == 'true'

        # List budgets
        result = budget_service.list_budgets(
            user_id=user_id,
            active_only=active_only
        )

        return success_response(data=result)

    except Exception as e:
        logger.error(f"List error: {str(e)}")
        return error_response(str(e), status_code=400)


def handle_update(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Handle update budget.

    Args:
        event: Lambda event
        user_id: User ID

    Returns:
        API Gateway response
    """
    try:
        # Extract budget ID from path
        path_params = event.get('pathParameters') or {}
        budget_id = path_params.get('id')

        if not budget_id:
            return validation_error_response("Budget ID is required")

        # Parse request body
        body = json.loads(event.get('body', '{}'))

        if not body:
            return validation_error_response("No updates provided")

        # Update budget
        updated_budget = budget_service.update_budget(user_id, budget_id, body)

        logger.info(f"Budget updated successfully: {budget_id}")

        return success_response(
            data=updated_budget,
            message="Budget updated successfully"
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
    Handle delete budget.

    Args:
        event: Lambda event
        user_id: User ID

    Returns:
        API Gateway response
    """
    try:
        # Extract budget ID from path
        path_params = event.get('pathParameters') or {}
        budget_id = path_params.get('id')

        if not budget_id:
            return validation_error_response("Budget ID is required")

        # Delete budget
        budget_service.delete_budget(user_id, budget_id)

        logger.info(f"Budget deleted successfully: {budget_id}")

        return success_response(
            message="Budget deleted successfully"
        )

    except NotFoundError as e:
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
