"""Integration tests for receipt upload flow."""

import pytest
import json
import base64
from unittest.mock import Mock, patch
from moto import mock_s3, mock_dynamodb
import boto3
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


@pytest.fixture
def aws_credentials():
    """Mock AWS Credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'


@pytest.fixture
def s3_client(aws_credentials):
    """Create mock S3 client."""
    with mock_s3():
        s3 = boto3.client('s3', region_name='us-east-1')
        # Create bucket
        s3.create_bucket(Bucket='test-receipts-bucket')
        yield s3


@pytest.fixture
def dynamodb_client(aws_credentials):
    """Create mock DynamoDB client."""
    with mock_dynamodb():
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

        # Create receipts table
        receipts_table = dynamodb.create_table(
            TableName='test-receipts',
            KeySchema=[
                {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                {'AttributeName': 'receipt_id', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'user_id', 'AttributeType': 'S'},
                {'AttributeName': 'receipt_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        # Create expenses table
        expenses_table = dynamodb.create_table(
            TableName='test-expenses',
            KeySchema=[
                {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                {'AttributeName': 'expense_id', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'user_id', 'AttributeType': 'S'},
                {'AttributeName': 'expense_id', 'AttributeType': 'S'},
                {'AttributeName': 'date', 'AttributeType': 'S'},
                {'AttributeName': 'category', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST',
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'user-date-index',
                    'KeySchema': [
                        {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                        {'AttributeName': 'date', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                },
                {
                    'IndexName': 'user-category-index',
                    'KeySchema': [
                        {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                        {'AttributeName': 'category', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                }
            ]
        )

        yield dynamodb


@pytest.fixture
def sample_receipt_image():
    """Sample receipt image data (base64 encoded)."""
    # Create a simple 1x1 pixel PNG
    png_data = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00'
        b'\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc'
        b'\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    return base64.b64encode(png_data).decode('utf-8')


class TestReceiptUploadFlow:
    """Integration tests for receipt upload flow."""

    def test_upload_receipt_end_to_end(self, s3_client, dynamodb_client, sample_receipt_image):
        """Test complete receipt upload flow."""
        # Set environment variables
        os.environ['RECEIPTS_BUCKET'] = 'test-receipts-bucket'
        os.environ['RECEIPTS_TABLE'] = 'test-receipts'
        os.environ['USE_LOCALSTACK'] = 'false'

        from receipts.upload import ReceiptUploadService

        # Create service
        upload_service = ReceiptUploadService()

        # Upload receipt
        result = upload_service.upload_receipt(
            user_id='user123',
            image_data=sample_receipt_image,
            filename='receipt.png',
            content_type='image/png'
        )

        # Verify result
        assert result['user_id'] == 'user123'
        assert result['receipt_id'] is not None
        assert result['status'] == 'pending'
        assert result['s3_key'].startswith('receipts/user123/')

        # Verify S3 upload
        s3_objects = s3_client.list_objects_v2(Bucket='test-receipts-bucket')
        assert s3_objects['KeyCount'] == 1

        # Verify DynamoDB record
        receipts_table = dynamodb_client.Table('test-receipts')
        receipt = receipts_table.get_item(
            Key={'user_id': 'user123', 'receipt_id': result['receipt_id']}
        )
        assert receipt['Item']['status'] == 'pending'

    def test_get_receipt(self, s3_client, dynamodb_client, sample_receipt_image):
        """Test retrieving a receipt."""
        os.environ['RECEIPTS_BUCKET'] = 'test-receipts-bucket'
        os.environ['RECEIPTS_TABLE'] = 'test-receipts'
        os.environ['USE_LOCALSTACK'] = 'false'

        from receipts.upload import ReceiptUploadService

        upload_service = ReceiptUploadService()

        # Upload first
        uploaded = upload_service.upload_receipt(
            user_id='user123',
            image_data=sample_receipt_image,
            filename='receipt.png'
        )

        # Get receipt
        receipt = upload_service.get_receipt('user123', uploaded['receipt_id'])

        assert receipt['user_id'] == 'user123'
        assert receipt['receipt_id'] == uploaded['receipt_id']
        assert 'image_url' in receipt

    def test_delete_receipt(self, s3_client, dynamodb_client, sample_receipt_image):
        """Test deleting a receipt."""
        os.environ['RECEIPTS_BUCKET'] = 'test-receipts-bucket'
        os.environ['RECEIPTS_TABLE'] = 'test-receipts'
        os.environ['USE_LOCALSTACK'] = 'false'

        from receipts.upload import ReceiptUploadService

        upload_service = ReceiptUploadService()

        # Upload first
        uploaded = upload_service.upload_receipt(
            user_id='user123',
            image_data=sample_receipt_image,
            filename='receipt.png'
        )

        # Delete receipt
        upload_service.delete_receipt('user123', uploaded['receipt_id'])

        # Verify S3 deletion
        s3_objects = s3_client.list_objects_v2(Bucket='test-receipts-bucket')
        assert s3_objects.get('KeyCount', 0) == 0

        # Verify DynamoDB deletion
        receipts_table = dynamodb_client.Table('test-receipts')
        receipt = receipts_table.get_item(
            Key={'user_id': 'user123', 'receipt_id': uploaded['receipt_id']}
        )
        assert 'Item' not in receipt


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
