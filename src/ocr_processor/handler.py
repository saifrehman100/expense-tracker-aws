"""Lambda handler for OCR processing."""

import json
import os
import logging
from typing import Dict, Any
from datetime import datetime
import uuid
import sys

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from shared.dynamodb import DynamoDBClient
from shared.s3 import S3Client
from ocr_processor.textract_service import TextractService
from ocr_processor.comprehend_service import ComprehendService
from ocr_processor.parser import ReceiptParser

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize clients
receipts_table = DynamoDBClient(os.environ.get('RECEIPTS_TABLE'))
expenses_table = DynamoDBClient(os.environ.get('EXPENSES_TABLE'))
s3_client = S3Client(os.environ.get('RECEIPTS_BUCKET'))
textract_service = TextractService()
comprehend_service = ComprehendService()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for OCR processing.

    Triggered by S3 uploads to receipts/ prefix.
    Processes receipt with Textract, categorizes with Comprehend,
    and creates expense record.

    Args:
        event: S3 event
        context: Lambda context

    Returns:
        Processing result
    """
    logger.info(f"OCR processor triggered: {json.dumps(event)}")

    try:
        # Parse S3 event
        for record in event.get('Records', []):
            process_receipt(record)

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Processing complete'})
        }

    except Exception as e:
        logger.error(f"OCR processing failed: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def process_receipt(record: Dict[str, Any]) -> None:
    """
    Process a single receipt.

    Args:
        record: S3 event record
    """
    try:
        # Extract S3 info
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']

        logger.info(f"Processing receipt: s3://{bucket}/{key}")

        # Extract user_id and receipt_id from S3 key
        # Expected format: receipts/{user_id}/{receipt_id}.{ext}
        key_parts = key.split('/')
        if len(key_parts) != 3 or key_parts[0] != 'receipts':
            logger.error(f"Invalid S3 key format: {key}")
            return

        user_id = key_parts[1]
        receipt_filename = key_parts[2]
        receipt_id = receipt_filename.rsplit('.', 1)[0]

        # Update receipt status to processing
        update_receipt_status(user_id, receipt_id, 'processing')

        # Step 1: Extract data with Textract
        logger.info("Step 1: Extracting data with Textract")
        ocr_data = textract_service.analyze_expense(bucket, key)

        # Step 2: Validate and clean OCR data
        logger.info("Step 2: Validating and cleaning OCR data")
        cleaned_data = ReceiptParser.validate_and_clean(ocr_data)

        # Step 3: Categorize with Comprehend
        logger.info("Step 3: Categorizing expense")
        category_data = comprehend_service.categorize_expense(
            merchant=cleaned_data.get('merchant'),
            items=cleaned_data.get('items', []),
            raw_text=cleaned_data.get('raw_text', '')
        )

        # Step 4: Create expense record
        logger.info("Step 4: Creating expense record")
        expense_id = create_expense_record(
            user_id=user_id,
            receipt_id=receipt_id,
            s3_key=key,
            ocr_data=cleaned_data,
            category_data=category_data
        )

        # Step 5: Update receipt status to processed
        logger.info("Step 5: Updating receipt status")
        update_receipt_status(
            user_id=user_id,
            receipt_id=receipt_id,
            status='processed',
            expense_id=expense_id
        )

        logger.info(f"Successfully processed receipt {receipt_id} -> expense {expense_id}")

    except Exception as e:
        logger.error(f"Error processing receipt: {str(e)}", exc_info=True)

        # Update receipt status to failed
        try:
            key_parts = record['s3']['object']['key'].split('/')
            if len(key_parts) == 3:
                user_id = key_parts[1]
                receipt_id = key_parts[2].rsplit('.', 1)[0]
                update_receipt_status(
                    user_id=user_id,
                    receipt_id=receipt_id,
                    status='failed',
                    error_message=str(e)
                )
        except Exception:
            pass

        raise


def create_expense_record(
    user_id: str,
    receipt_id: str,
    s3_key: str,
    ocr_data: Dict[str, Any],
    category_data: Dict[str, Any]
) -> str:
    """
    Create expense record in DynamoDB.

    Args:
        user_id: User ID
        receipt_id: Receipt ID
        s3_key: S3 key for receipt image
        ocr_data: Cleaned OCR data
        category_data: Category data

    Returns:
        Expense ID
    """
    expense_id = str(uuid.uuid4())

    # Generate presigned URL for receipt
    receipt_url = s3_client.get_presigned_url(s3_key, expiration=31536000)  # 1 year

    # Build expense record
    expense = {
        'user_id': user_id,
        'expense_id': expense_id,
        'receipt_id': receipt_id,
        'amount': ocr_data.get('total') or 0.0,
        'merchant': ocr_data.get('merchant') or 'Unknown Merchant',
        'category': category_data.get('category', 'Other'),
        'date': ocr_data.get('date') or datetime.utcnow().strftime('%Y-%m-%d'),
        'items': ocr_data.get('items', []),
        'receipt_url': receipt_url,
        'receipt_s3_key': s3_key,
        'raw_text': ocr_data.get('raw_text', ''),
        'confidence_score': ocr_data.get('confidence_score', 0.0),
        'category_confidence': category_data.get('confidence', 0.0),
        'subtotal': ocr_data.get('subtotal'),
        'tax': ocr_data.get('tax'),
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat(),
        'metadata': ReceiptParser.extract_metadata(ocr_data, category_data)
    }

    # Save to DynamoDB
    expenses_table.put_item(expense)

    logger.info(f"Created expense record: {expense_id}")
    return expense_id


def update_receipt_status(
    user_id: str,
    receipt_id: str,
    status: str,
    expense_id: str = None,
    error_message: str = None
) -> None:
    """
    Update receipt status in DynamoDB.

    Args:
        user_id: User ID
        receipt_id: Receipt ID
        status: New status
        expense_id: Optional expense ID
        error_message: Optional error message
    """
    update_expr = "SET #status = :status, processed_at = :processed_at"
    expr_values = {
        ':status': status,
        ':processed_at': datetime.utcnow().isoformat()
    }
    expr_names = {
        '#status': 'status'
    }

    if expense_id:
        update_expr += ", expense_id = :expense_id"
        expr_values[':expense_id'] = expense_id

    if error_message:
        update_expr += ", error_message = :error_message"
        expr_values[':error_message'] = error_message

    receipts_table.update_item(
        key={'user_id': user_id, 'receipt_id': receipt_id},
        update_expression=update_expr,
        expression_values=expr_values,
        expression_names=expr_names
    )

    logger.info(f"Updated receipt {receipt_id} status to {status}")
