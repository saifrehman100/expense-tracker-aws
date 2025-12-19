"""Email service using AWS SES."""

import os
import boto3
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """AWS SES email service."""

    def __init__(self):
        """Initialize SES client."""
        # Support for LocalStack
        endpoint_url = os.environ.get('LOCALSTACK_ENDPOINT')
        if endpoint_url and os.environ.get('USE_LOCALSTACK', 'false').lower() == 'true':
            self.client = boto3.client('ses', endpoint_url=endpoint_url)
        else:
            self.client = boto3.client('ses')

        self.sender_email = os.environ.get('SES_SENDER_EMAIL', 'noreply@example.com')

    def send_report_email(
        self,
        recipient_email: str,
        report_type: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send report email.

        Args:
            recipient_email: Recipient email address
            report_type: Type of report (weekly/monthly)
            html_content: HTML content
            text_content: Optional plain text content

        Returns:
            SES response

        Raises:
            Exception: If email sending fails
        """
        subject = f"Your {report_type.capitalize()} Expense Report"

        if not text_content:
            text_content = f"Your {report_type} expense report is ready. Please view this email in HTML format."

        try:
            logger.info(f"Sending {report_type} report email to {recipient_email}")

            response = self.client.send_email(
                Source=self.sender_email,
                Destination={
                    'ToAddresses': [recipient_email]
                },
                Message={
                    'Subject': {
                        'Data': subject,
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Text': {
                            'Data': text_content,
                            'Charset': 'UTF-8'
                        },
                        'Html': {
                            'Data': html_content,
                            'Charset': 'UTF-8'
                        }
                    }
                }
            )

            logger.info(f"Email sent successfully. Message ID: {response['MessageId']}")

            return {
                'message_id': response['MessageId'],
                'success': True
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']

            logger.error(f"Failed to send email: {error_code} - {error_message}")

            if error_code == 'MessageRejected':
                raise Exception(f"Email rejected: {error_message}")
            elif error_code == 'MailFromDomainNotVerifiedException':
                raise Exception("Sender email not verified in SES")
            else:
                raise Exception(f"Failed to send email: {error_message}")

    def send_budget_alert_email(
        self,
        recipient_email: str,
        recipient_name: str,
        budget_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send budget alert email.

        Args:
            recipient_email: Recipient email address
            recipient_name: Recipient name
            budget_data: Budget data

        Returns:
            SES response

        Raises:
            Exception: If email sending fails
        """
        category = budget_data.get('category', 'Unknown')
        current_spending = budget_data.get('current_spending', 0)
        budget_amount = budget_data.get('amount', 0)
        percentage_used = budget_data.get('percentage_used', 0)
        period = budget_data.get('period', 'monthly')

        subject = f"Budget Alert: {category} - {percentage_used:.0f}% Used"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #ff9800; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                <h1 style="margin: 0;">Budget Alert</h1>
            </div>

            <div style="background-color: white; padding: 20px; border: 1px solid #e0e0e0;">
                <p>Hi {recipient_name},</p>

                <p>Your <strong>{category}</strong> budget for this {period} has reached <strong>{percentage_used:.1f}%</strong> of the allocated amount.</p>

                <div style="background-color: #fff3cd; border-left: 4px solid #ff9800; padding: 15px; margin: 20px 0;">
                    <h3 style="margin: 0 0 10px 0; color: #ff9800;">Budget Status</h3>
                    <p style="margin: 5px 0;"><strong>Category:</strong> {category}</p>
                    <p style="margin: 5px 0;"><strong>Budget Amount:</strong> ${budget_amount:.2f}</p>
                    <p style="margin: 5px 0;"><strong>Current Spending:</strong> ${current_spending:.2f}</p>
                    <p style="margin: 5px 0;"><strong>Remaining:</strong> ${budget_amount - current_spending:.2f}</p>
                    <p style="margin: 5px 0;"><strong>Percentage Used:</strong> {percentage_used:.1f}%</p>
                </div>

                <p>Consider reviewing your expenses to stay within budget.</p>

                <p>Best regards,<br>Your Expense Tracker Team</p>
            </div>

            <div style="background-color: #f9f9f9; padding: 15px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 8px 8px; text-align: center; color: #666; font-size: 12px;">
                <p>Smart Expense Tracker - Your Personal Finance Assistant</p>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        Budget Alert

        Hi {recipient_name},

        Your {category} budget for this {period} has reached {percentage_used:.1f}% of the allocated amount.

        Budget Status:
        - Category: {category}
        - Budget Amount: ${budget_amount:.2f}
        - Current Spending: ${current_spending:.2f}
        - Remaining: ${budget_amount - current_spending:.2f}
        - Percentage Used: {percentage_used:.1f}%

        Consider reviewing your expenses to stay within budget.

        Best regards,
        Your Expense Tracker Team
        """

        try:
            logger.info(f"Sending budget alert email to {recipient_email}")

            response = self.client.send_email(
                Source=self.sender_email,
                Destination={
                    'ToAddresses': [recipient_email]
                },
                Message={
                    'Subject': {
                        'Data': subject,
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Text': {
                            'Data': text_content,
                            'Charset': 'UTF-8'
                        },
                        'Html': {
                            'Data': html_content,
                            'Charset': 'UTF-8'
                        }
                    }
                }
            )

            logger.info(f"Budget alert email sent. Message ID: {response['MessageId']}")

            return {
                'message_id': response['MessageId'],
                'success': True
            }

        except ClientError as e:
            error_message = e.response['Error']['Message']
            logger.error(f"Failed to send budget alert email: {error_message}")
            raise Exception(f"Failed to send email: {error_message}")

    def verify_email(self, email: str) -> Dict[str, Any]:
        """
        Verify an email address in SES (for testing/setup).

        Args:
            email: Email address to verify

        Returns:
            Verification response

        Raises:
            Exception: If verification fails
        """
        try:
            logger.info(f"Initiating email verification for {email}")

            response = self.client.verify_email_identity(EmailAddress=email)

            logger.info(f"Verification email sent to {email}")

            return {
                'success': True,
                'message': f"Verification email sent to {email}. Please check your inbox."
            }

        except ClientError as e:
            error_message = e.response['Error']['Message']
            logger.error(f"Email verification failed: {error_message}")
            raise Exception(f"Failed to verify email: {error_message}")
