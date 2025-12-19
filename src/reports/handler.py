"""Lambda handler for report operations."""

import json
import os
import logging
from typing import Dict, Any
import sys
import base64

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.response import success_response, error_response, validation_error_response
from shared.validators import validate_required_fields
from shared.exceptions import ExpenseTrackerException
from shared.dynamodb import DynamoDBClient
from reports.generator import ReportGenerator
from reports.email_service import EmailService

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize services
report_generator = ReportGenerator()
email_service = EmailService()
users_table = DynamoDBClient(os.environ.get('USERS_TABLE'))


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for report operations.

    Handles:
    - GET /reports/weekly - Get weekly report
    - GET /reports/monthly - Get monthly report
    - POST /reports/email - Email report
    - GET /reports/export - Export as CSV

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
        if path == '/reports/weekly' and http_method == 'GET':
            return handle_weekly_report(event, user_id)
        elif path == '/reports/monthly' and http_method == 'GET':
            return handle_monthly_report(event, user_id)
        elif path == '/reports/email' and http_method == 'POST':
            return handle_email_report(event, user_id)
        elif path == '/reports/export' and http_method == 'GET':
            return handle_export(event, user_id)
        else:
            return error_response("Route not found", status_code=404)

    except ExpenseTrackerException as e:
        logger.error(f"Application error: {str(e)}")
        return error_response(e.message, status_code=e.status_code)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return error_response("Internal server error", status_code=500)


def handle_weekly_report(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Handle weekly report request.

    Args:
        event: Lambda event
        user_id: User ID

    Returns:
        API Gateway response
    """
    try:
        logger.info(f"Generating weekly report for user {user_id}")

        # Generate report
        report = report_generator.generate_weekly_report(user_id)

        return success_response(data=report)

    except Exception as e:
        logger.error(f"Weekly report error: {str(e)}")
        return error_response(str(e), status_code=400)


def handle_monthly_report(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Handle monthly report request.

    Args:
        event: Lambda event
        user_id: User ID

    Returns:
        API Gateway response
    """
    try:
        logger.info(f"Generating monthly report for user {user_id}")

        # Generate report
        report = report_generator.generate_monthly_report(user_id)

        return success_response(data=report)

    except Exception as e:
        logger.error(f"Monthly report error: {str(e)}")
        return error_response(str(e), status_code=400)


def handle_email_report(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Handle email report request.

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
        validate_required_fields(body, ['report_type'])

        report_type = body['report_type'].lower()

        if report_type not in ['weekly', 'monthly']:
            return validation_error_response("Report type must be 'weekly' or 'monthly'")

        # Get user info
        user = users_table.get_item({'user_id': user_id})
        if not user:
            return error_response("User not found", status_code=404)

        user_email = user.get('email')
        if not user_email:
            return error_response("User email not found", status_code=400)

        # Generate report
        if report_type == 'weekly':
            report = report_generator.generate_weekly_report(user_id)
        else:
            report = report_generator.generate_monthly_report(user_id)

        # Format as HTML
        html_content = report_generator.format_report_html(report)

        # Send email
        email_result = email_service.send_report_email(
            recipient_email=user_email,
            report_type=report_type,
            html_content=html_content
        )

        logger.info(f"Report email sent to {user_email}")

        return success_response(
            data={
                'message_id': email_result['message_id'],
                'recipient': user_email,
                'report_type': report_type
            },
            message=f"{report_type.capitalize()} report sent to {user_email}"
        )

    except Exception as e:
        logger.error(f"Email report error: {str(e)}")
        return error_response(str(e), status_code=400)


def handle_export(event: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Handle export report request.

    Args:
        event: Lambda event
        user_id: User ID

    Returns:
        API Gateway response with CSV file
    """
    try:
        # Get query parameters
        query_params = event.get('queryStringParameters') or {}
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')

        if not start_date or not end_date:
            return validation_error_response("start_date and end_date are required")

        logger.info(f"Exporting expenses for user {user_id} from {start_date} to {end_date}")

        # Generate CSV
        csv_content = report_generator.export_to_csv(user_id, start_date, end_date)

        # Return CSV as downloadable file
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/csv',
                'Content-Disposition': f'attachment; filename="expenses_{start_date}_{end_date}.csv"',
                'Access-Control-Allow-Origin': '*'
            },
            'body': csv_content
        }

    except Exception as e:
        logger.error(f"Export error: {str(e)}")
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
