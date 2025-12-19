"""Receipt upload utilities."""

import os
import uuid
from datetime import datetime
from typing import Dict, Any
import logging

from shared.s3 import S3Client
from shared.dynamodb import DynamoDBClient
from shared.validators import (
    validate_file_extension,
    validate_file_size,
    validate_base64_image
)
from shared.exceptions import ValidationError, StorageError

logger = logging.getLogger(__name__)

# Allowed image extensions
ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.pdf']

# Maximum file size (5MB)
MAX_FILE_SIZE_MB = 5


class ReceiptUploadService:
    """Service for handling receipt uploads."""

    def __init__(self):
        """Initialize upload service."""
        self.s3_client = S3Client(os.environ.get('RECEIPTS_BUCKET'))
        self.receipts_table = DynamoDBClient(os.environ.get('RECEIPTS_TABLE'))

    def upload_receipt(
        self,
        user_id: str,
        image_data: str,
        filename: str,
        content_type: str = 'image/jpeg'
    ) -> Dict[str, Any]:
        """
        Upload a receipt image.

        Args:
            user_id: User ID
            image_data: Base64-encoded image data
            filename: Original filename
            content_type: Image content type

        Returns:
            Receipt information

        Raises:
            ValidationError: If validation fails
            StorageError: If upload fails
        """
        # Validate filename extension
        validate_file_extension(filename, ALLOWED_EXTENSIONS)

        # Validate base64 image data
        clean_image_data = validate_base64_image(image_data)

        # Estimate file size (base64 is ~1.33x larger than binary)
        import base64
        estimated_size = len(clean_image_data) * 0.75
        validate_file_size(int(estimated_size), MAX_FILE_SIZE_MB)

        # Generate unique receipt ID
        receipt_id = str(uuid.uuid4())

        # Generate S3 key with user prefix
        extension = filename.rsplit('.', 1)[-1].lower()
        s3_key = f"receipts/{user_id}/{receipt_id}.{extension}"

        # Upload to S3
        try:
            self.s3_client.upload_base64(
                base64_content=clean_image_data,
                key=s3_key,
                content_type=content_type,
                metadata={
                    'user_id': user_id,
                    'receipt_id': receipt_id,
                    'original_filename': filename,
                    'uploaded_at': datetime.utcnow().isoformat()
                }
            )

            logger.info(f"Receipt uploaded to S3: {s3_key}")
        except Exception as e:
            logger.error(f"Failed to upload receipt to S3: {str(e)}")
            raise StorageError(f"Failed to upload receipt: {str(e)}")

        # Create receipt record in DynamoDB
        receipt_record = {
            'user_id': user_id,
            'receipt_id': receipt_id,
            's3_key': s3_key,
            'filename': filename,
            'status': 'pending',
            'uploaded_at': datetime.utcnow().isoformat()
        }

        try:
            self.receipts_table.put_item(receipt_record)
            logger.info(f"Receipt record created: {receipt_id}")
        except Exception as e:
            logger.error(f"Failed to create receipt record: {str(e)}")
            # Try to clean up S3 upload
            try:
                self.s3_client.delete_file(s3_key)
            except Exception:
                pass
            raise StorageError(f"Failed to create receipt record: {str(e)}")

        return receipt_record

    def get_receipt(self, user_id: str, receipt_id: str) -> Dict[str, Any]:
        """
        Get receipt information.

        Args:
            user_id: User ID
            receipt_id: Receipt ID

        Returns:
            Receipt information

        Raises:
            NotFoundError: If receipt not found
        """
        receipt = self.receipts_table.get_item({
            'user_id': user_id,
            'receipt_id': receipt_id
        })

        if not receipt:
            raise ValidationError("Receipt not found")

        # Generate presigned URL for image
        receipt['image_url'] = self.s3_client.get_presigned_url(
            receipt['s3_key'],
            expiration=3600
        )

        return receipt

    def list_receipts(
        self,
        user_id: str,
        limit: int = 50,
        last_evaluated_key: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        List receipts for a user.

        Args:
            user_id: User ID
            limit: Maximum number of receipts to return
            last_evaluated_key: Pagination key

        Returns:
            Dictionary with receipts and pagination key
        """
        from boto3.dynamodb.conditions import Key

        result = self.receipts_table.query(
            key_condition_expression=Key('user_id').eq(user_id),
            limit=limit,
            scan_forward=False,  # Most recent first
            exclusive_start_key=last_evaluated_key
        )

        # Add presigned URLs to receipts
        for receipt in result['items']:
            receipt['image_url'] = self.s3_client.get_presigned_url(
                receipt['s3_key'],
                expiration=3600
            )

        return {
            'receipts': result['items'],
            'last_evaluated_key': result['last_evaluated_key']
        }

    def delete_receipt(self, user_id: str, receipt_id: str) -> None:
        """
        Delete a receipt.

        Args:
            user_id: User ID
            receipt_id: Receipt ID

        Raises:
            NotFoundError: If receipt not found
            StorageError: If deletion fails
        """
        # Get receipt to find S3 key
        receipt = self.receipts_table.get_item({
            'user_id': user_id,
            'receipt_id': receipt_id
        })

        if not receipt:
            raise ValidationError("Receipt not found")

        # Delete from S3
        try:
            self.s3_client.delete_file(receipt['s3_key'])
            logger.info(f"Receipt deleted from S3: {receipt['s3_key']}")
        except Exception as e:
            logger.error(f"Failed to delete receipt from S3: {str(e)}")
            # Continue with DynamoDB deletion even if S3 fails

        # Delete from DynamoDB
        try:
            self.receipts_table.delete_item({
                'user_id': user_id,
                'receipt_id': receipt_id
            })
            logger.info(f"Receipt record deleted: {receipt_id}")
        except Exception as e:
            logger.error(f"Failed to delete receipt record: {str(e)}")
            raise StorageError(f"Failed to delete receipt: {str(e)}")
