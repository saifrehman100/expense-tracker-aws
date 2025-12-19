"""Lambda handler for authentication operations."""

import json
import os
import logging
from datetime import datetime
from typing import Dict, Any
import sys

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success_response, error_response, validation_error_response
from shared.validators import validate_email, validate_password, validate_required_fields
from shared.dynamodb import DynamoDBClient
from shared.exceptions import ExpenseTrackerException, ValidationError
from auth.cognito_utils import CognitoClient

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize clients
cognito_client = CognitoClient()
users_table = DynamoDBClient(os.environ.get('USERS_TABLE'))


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for authentication operations.

    Handles:
    - POST /auth/register - Register new user
    - POST /auth/login - Sign in user
    - POST /auth/refresh - Refresh tokens

    Args:
        event: Lambda event
        context: Lambda context

    Returns:
        API Gateway response
    """
    try:
        # Log request
        logger.info(f"Request: {event.get('httpMethod')} {event.get('path')}")

        # Get HTTP method and path
        http_method = event.get('httpMethod')
        path = event.get('path')

        # Route request
        if path == '/auth/register' and http_method == 'POST':
            return handle_register(event)
        elif path == '/auth/login' and http_method == 'POST':
            return handle_login(event)
        elif path == '/auth/refresh' and http_method == 'POST':
            return handle_refresh(event)
        else:
            return error_response("Route not found", status_code=404)

    except ExpenseTrackerException as e:
        logger.error(f"Application error: {str(e)}")
        return error_response(e.message, status_code=e.status_code)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return error_response("Internal server error", status_code=500)


def handle_register(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle user registration.

    Args:
        event: Lambda event

    Returns:
        API Gateway response
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))

        # Validate required fields
        validate_required_fields(body, ['email', 'password', 'name'])

        # Extract and validate fields
        email = validate_email(body['email'])
        password = validate_password(body['password'])
        name = body['name'].strip()

        if not name or len(name) < 2:
            raise ValidationError("Name must be at least 2 characters")

        # Register user in Cognito
        cognito_response = cognito_client.sign_up(email, password, name)

        # Create user record in DynamoDB
        user_id = cognito_response['user_sub']
        user_record = {
            'user_id': user_id,
            'email': email,
            'name': name,
            'created_at': datetime.utcnow().isoformat(),
            'preferences': {
                'currency': 'USD',
                'notification_enabled': True
            }
        }

        users_table.put_item(user_record)

        logger.info(f"User registered successfully: {email}")

        return success_response(
            data={
                'user_id': user_id,
                'email': email,
                'name': name,
                'user_confirmed': cognito_response['user_confirmed']
            },
            message="User registered successfully. Please check your email to confirm your account.",
            status_code=201
        )

    except ValidationError as e:
        return validation_error_response(str(e))
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return error_response(str(e), status_code=400)


def handle_login(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle user login.

    Args:
        event: Lambda event

    Returns:
        API Gateway response
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))

        # Validate required fields
        validate_required_fields(body, ['email', 'password'])

        # Extract and validate fields
        email = validate_email(body['email'])
        password = body['password']

        # Authenticate with Cognito
        auth_result = cognito_client.sign_in(email, password)

        # Get user info
        user_info = cognito_client.get_user(auth_result['access_token'])

        # Get user record from DynamoDB
        user_record = users_table.get_item({'user_id': user_info['user_sub']})

        logger.info(f"User logged in successfully: {email}")

        return success_response(
            data={
                'user': {
                    'user_id': user_info['user_sub'],
                    'email': user_info['email'],
                    'name': user_info['name']
                },
                'tokens': {
                    'access_token': auth_result['access_token'],
                    'id_token': auth_result['id_token'],
                    'refresh_token': auth_result['refresh_token'],
                    'expires_in': auth_result['expires_in'],
                    'token_type': auth_result['token_type']
                }
            },
            message="Login successful"
        )

    except ValidationError as e:
        return validation_error_response(str(e))
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return error_response(str(e), status_code=401)


def handle_refresh(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle token refresh.

    Args:
        event: Lambda event

    Returns:
        API Gateway response
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))

        # Validate required fields
        validate_required_fields(body, ['refresh_token'])

        refresh_token = body['refresh_token']

        # Refresh tokens with Cognito
        auth_result = cognito_client.refresh_token(refresh_token)

        logger.info("Tokens refreshed successfully")

        return success_response(
            data={
                'tokens': {
                    'access_token': auth_result['access_token'],
                    'id_token': auth_result['id_token'],
                    'expires_in': auth_result['expires_in'],
                    'token_type': auth_result['token_type']
                }
            },
            message="Tokens refreshed successfully"
        )

    except ValidationError as e:
        return validation_error_response(str(e))
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        return error_response(str(e), status_code=401)


def get_user_from_token(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract user information from JWT token in request.

    Args:
        event: Lambda event

    Returns:
        User information from token claims
    """
    # Get claims from request context (set by API Gateway Cognito authorizer)
    request_context = event.get('requestContext', {})
    authorizer = request_context.get('authorizer', {})
    claims = authorizer.get('claims', {})

    return {
        'user_id': claims.get('sub'),
        'email': claims.get('email'),
        'name': claims.get('name')
    }
