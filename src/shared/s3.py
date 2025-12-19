"""S3 utilities and helper functions."""

import os
import boto3
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError
import logging
import base64
from datetime import datetime, timedelta

from .exceptions import StorageError

logger = logging.getLogger(__name__)


class S3Client:
    """S3 client wrapper with common operations."""

    def __init__(self, bucket_name: str):
        """
        Initialize S3 client.

        Args:
            bucket_name: Name of the S3 bucket
        """
        self.bucket_name = bucket_name

        # Support for LocalStack
        endpoint_url = os.environ.get('LOCALSTACK_ENDPOINT')
        if endpoint_url and os.environ.get('USE_LOCALSTACK', 'false').lower() == 'true':
            self.s3 = boto3.client('s3', endpoint_url=endpoint_url)
        else:
            self.s3 = boto3.client('s3')

    def upload_file(
        self,
        file_content: bytes,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Upload a file to S3.

        Args:
            file_content: File content as bytes
            key: S3 object key
            content_type: Optional content type
            metadata: Optional metadata

        Returns:
            S3 object key

        Raises:
            StorageError: If the upload fails
        """
        try:
            kwargs = {
                'Bucket': self.bucket_name,
                'Key': key,
                'Body': file_content,
                'ServerSideEncryption': 'AES256'
            }

            if content_type:
                kwargs['ContentType'] = content_type

            if metadata:
                kwargs['Metadata'] = metadata

            self.s3.put_object(**kwargs)
            logger.info(f"Successfully uploaded file to s3://{self.bucket_name}/{key}")
            return key
        except ClientError as e:
            logger.error(f"Error uploading file to S3: {e}")
            raise StorageError(f"Failed to upload file: {str(e)}")

    def upload_base64(
        self,
        base64_content: str,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Upload a base64-encoded file to S3.

        Args:
            base64_content: Base64-encoded file content
            key: S3 object key
            content_type: Optional content type
            metadata: Optional metadata

        Returns:
            S3 object key

        Raises:
            StorageError: If the upload fails
        """
        try:
            # Decode base64 content
            file_content = base64.b64decode(base64_content)
            return self.upload_file(file_content, key, content_type, metadata)
        except Exception as e:
            logger.error(f"Error decoding/uploading base64 file: {e}")
            raise StorageError(f"Failed to upload base64 file: {str(e)}")

    def download_file(self, key: str) -> bytes:
        """
        Download a file from S3.

        Args:
            key: S3 object key

        Returns:
            File content as bytes

        Raises:
            StorageError: If the download fails
        """
        try:
            response = self.s3.get_object(Bucket=self.bucket_name, Key=key)
            return response['Body'].read()
        except ClientError as e:
            logger.error(f"Error downloading file from S3: {e}")
            raise StorageError(f"Failed to download file: {str(e)}")

    def delete_file(self, key: str) -> None:
        """
        Delete a file from S3.

        Args:
            key: S3 object key

        Raises:
            StorageError: If the deletion fails
        """
        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Successfully deleted file s3://{self.bucket_name}/{key}")
        except ClientError as e:
            logger.error(f"Error deleting file from S3: {e}")
            raise StorageError(f"Failed to delete file: {str(e)}")

    def get_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
        operation: str = 'get_object'
    ) -> str:
        """
        Generate a presigned URL for an S3 object.

        Args:
            key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)
            operation: S3 operation (default: 'get_object')

        Returns:
            Presigned URL

        Raises:
            StorageError: If URL generation fails
        """
        try:
            url = self.s3.generate_presigned_url(
                operation,
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned URL: {e}")
            raise StorageError(f"Failed to generate presigned URL: {str(e)}")

    def get_presigned_post(
        self,
        key: str,
        expiration: int = 3600,
        conditions: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Generate presigned POST data for uploading to S3.

        Args:
            key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)
            conditions: Optional list of conditions

        Returns:
            Dictionary with url and fields for POST request

        Raises:
            StorageError: If generation fails
        """
        try:
            if conditions is None:
                conditions = []

            response = self.s3.generate_presigned_post(
                Bucket=self.bucket_name,
                Key=key,
                ExpiresIn=expiration,
                Conditions=conditions
            )
            return response
        except ClientError as e:
            logger.error(f"Error generating presigned POST: {e}")
            raise StorageError(f"Failed to generate presigned POST: {str(e)}")

    def file_exists(self, key: str) -> bool:
        """
        Check if a file exists in S3.

        Args:
            key: S3 object key

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False

    def get_file_metadata(self, key: str) -> Dict[str, Any]:
        """
        Get metadata for an S3 object.

        Args:
            key: S3 object key

        Returns:
            Metadata dictionary

        Raises:
            StorageError: If operation fails
        """
        try:
            response = self.s3.head_object(Bucket=self.bucket_name, Key=key)
            return {
                'content_type': response.get('ContentType'),
                'content_length': response.get('ContentLength'),
                'last_modified': response.get('LastModified'),
                'metadata': response.get('Metadata', {}),
                'etag': response.get('ETag')
            }
        except ClientError as e:
            logger.error(f"Error getting file metadata: {e}")
            raise StorageError(f"Failed to get file metadata: {str(e)}")

    def list_files(self, prefix: str = '', max_keys: int = 1000) -> list:
        """
        List files in S3 bucket with optional prefix.

        Args:
            prefix: Optional key prefix
            max_keys: Maximum number of keys to return

        Returns:
            List of file keys

        Raises:
            StorageError: If operation fails
        """
        try:
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )

            return [obj['Key'] for obj in response.get('Contents', [])]
        except ClientError as e:
            logger.error(f"Error listing files: {e}")
            raise StorageError(f"Failed to list files: {str(e)}")
