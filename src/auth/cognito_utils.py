"""Cognito utilities for authentication."""

import os
import boto3
import hmac
import hashlib
import base64
from typing import Dict, Any
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class CognitoClient:
    """AWS Cognito client wrapper."""

    def __init__(self):
        """Initialize Cognito client."""
        self.client_id = os.environ.get('COGNITO_CLIENT_ID')
        self.user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')

        # Support for LocalStack
        endpoint_url = os.environ.get('LOCALSTACK_ENDPOINT')
        if endpoint_url and os.environ.get('USE_LOCALSTACK', 'false').lower() == 'true':
            self.client = boto3.client('cognito-idp', endpoint_url=endpoint_url)
        else:
            self.client = boto3.client('cognito-idp')

    def sign_up(self, email: str, password: str, name: str) -> Dict[str, Any]:
        """
        Register a new user.

        Args:
            email: User email
            password: User password
            name: User name

        Returns:
            Registration response

        Raises:
            ClientError: If registration fails
        """
        try:
            response = self.client.sign_up(
                ClientId=self.client_id,
                Username=email,
                Password=password,
                UserAttributes=[
                    {'Name': 'email', 'Value': email},
                    {'Name': 'name', 'Value': name}
                ]
            )

            logger.info(f"User registered successfully: {email}")
            return {
                'user_sub': response['UserSub'],
                'user_confirmed': response['UserConfirmed'],
                'code_delivery_details': response.get('CodeDeliveryDetails')
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Sign up failed: {error_code}")

            if error_code == 'UsernameExistsException':
                raise Exception("User already exists")
            elif error_code == 'InvalidPasswordException':
                raise Exception("Password does not meet requirements")
            elif error_code == 'InvalidParameterException':
                raise Exception("Invalid parameters provided")
            else:
                raise Exception(f"Registration failed: {e.response['Error']['Message']}")

    def confirm_sign_up(self, email: str, confirmation_code: str) -> None:
        """
        Confirm user registration.

        Args:
            email: User email
            confirmation_code: Confirmation code

        Raises:
            ClientError: If confirmation fails
        """
        try:
            self.client.confirm_sign_up(
                ClientId=self.client_id,
                Username=email,
                ConfirmationCode=confirmation_code
            )
            logger.info(f"User confirmed successfully: {email}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Confirmation failed: {error_code}")
            raise Exception(f"Confirmation failed: {e.response['Error']['Message']}")

    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """
        Sign in a user.

        Args:
            email: User email
            password: User password

        Returns:
            Authentication tokens

        Raises:
            ClientError: If sign in fails
        """
        try:
            response = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': email,
                    'PASSWORD': password
                }
            )

            auth_result = response['AuthenticationResult']

            logger.info(f"User signed in successfully: {email}")
            return {
                'access_token': auth_result['AccessToken'],
                'id_token': auth_result['IdToken'],
                'refresh_token': auth_result['RefreshToken'],
                'expires_in': auth_result['ExpiresIn'],
                'token_type': auth_result['TokenType']
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Sign in failed: {error_code}")

            if error_code == 'NotAuthorizedException':
                raise Exception("Invalid email or password")
            elif error_code == 'UserNotConfirmedException':
                raise Exception("User not confirmed")
            elif error_code == 'UserNotFoundException':
                raise Exception("User not found")
            else:
                raise Exception(f"Sign in failed: {e.response['Error']['Message']}")

    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh authentication tokens.

        Args:
            refresh_token: Refresh token

        Returns:
            New authentication tokens

        Raises:
            ClientError: If refresh fails
        """
        try:
            response = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='REFRESH_TOKEN_AUTH',
                AuthParameters={
                    'REFRESH_TOKEN': refresh_token
                }
            )

            auth_result = response['AuthenticationResult']

            logger.info("Token refreshed successfully")
            return {
                'access_token': auth_result['AccessToken'],
                'id_token': auth_result['IdToken'],
                'expires_in': auth_result['ExpiresIn'],
                'token_type': auth_result['TokenType']
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Token refresh failed: {error_code}")
            raise Exception(f"Token refresh failed: {e.response['Error']['Message']}")

    def get_user(self, access_token: str) -> Dict[str, Any]:
        """
        Get user information from access token.

        Args:
            access_token: Access token

        Returns:
            User information

        Raises:
            ClientError: If request fails
        """
        try:
            response = self.client.get_user(AccessToken=access_token)

            user_attributes = {attr['Name']: attr['Value'] for attr in response['UserAttributes']}

            return {
                'username': response['Username'],
                'user_attributes': user_attributes,
                'email': user_attributes.get('email'),
                'name': user_attributes.get('name'),
                'user_sub': user_attributes.get('sub')
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Get user failed: {error_code}")
            raise Exception(f"Get user failed: {e.response['Error']['Message']}")

    def forgot_password(self, email: str) -> Dict[str, Any]:
        """
        Initiate forgot password flow.

        Args:
            email: User email

        Returns:
            Code delivery details

        Raises:
            ClientError: If request fails
        """
        try:
            response = self.client.forgot_password(
                ClientId=self.client_id,
                Username=email
            )

            logger.info(f"Password reset initiated for: {email}")
            return {
                'code_delivery_details': response.get('CodeDeliveryDetails')
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Forgot password failed: {error_code}")
            raise Exception(f"Forgot password failed: {e.response['Error']['Message']}")

    def confirm_forgot_password(self, email: str, confirmation_code: str, new_password: str) -> None:
        """
        Confirm forgot password with new password.

        Args:
            email: User email
            confirmation_code: Confirmation code
            new_password: New password

        Raises:
            ClientError: If confirmation fails
        """
        try:
            self.client.confirm_forgot_password(
                ClientId=self.client_id,
                Username=email,
                ConfirmationCode=confirmation_code,
                Password=new_password
            )
            logger.info(f"Password reset confirmed for: {email}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Confirm forgot password failed: {error_code}")
            raise Exception(f"Confirm forgot password failed: {e.response['Error']['Message']}")

    def admin_create_user(self, email: str, name: str, temporary_password: str = None) -> Dict[str, Any]:
        """
        Admin create user (for testing/seeding).

        Args:
            email: User email
            name: User name
            temporary_password: Optional temporary password

        Returns:
            User information

        Raises:
            ClientError: If creation fails
        """
        try:
            kwargs = {
                'UserPoolId': self.user_pool_id,
                'Username': email,
                'UserAttributes': [
                    {'Name': 'email', 'Value': email},
                    {'Name': 'email_verified', 'Value': 'true'},
                    {'Name': 'name', 'Value': name}
                ],
                'MessageAction': 'SUPPRESS'
            }

            if temporary_password:
                kwargs['TemporaryPassword'] = temporary_password

            response = self.client.admin_create_user(**kwargs)

            logger.info(f"Admin created user: {email}")
            return {
                'username': response['User']['Username'],
                'user_sub': next(
                    (attr['Value'] for attr in response['User']['Attributes'] if attr['Name'] == 'sub'),
                    None
                )
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Admin create user failed: {error_code}")
            raise Exception(f"Admin create user failed: {e.response['Error']['Message']}")
