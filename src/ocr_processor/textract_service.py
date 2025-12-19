"""AWS Textract service for receipt OCR."""

import os
import boto3
from typing import Dict, Any, List
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class TextractService:
    """AWS Textract client wrapper for receipt processing."""

    def __init__(self):
        """Initialize Textract client."""
        # Support for LocalStack
        endpoint_url = os.environ.get('LOCALSTACK_ENDPOINT')
        if endpoint_url and os.environ.get('USE_LOCALSTACK', 'false').lower() == 'true':
            self.client = boto3.client('textract', endpoint_url=endpoint_url)
        else:
            self.client = boto3.client('textract')

        self.confidence_threshold = float(
            os.environ.get('TEXTRACT_CONFIDENCE_THRESHOLD', '80')
        )

    def analyze_expense(self, bucket: str, key: str) -> Dict[str, Any]:
        """
        Analyze expense document using Textract.

        Args:
            bucket: S3 bucket name
            key: S3 object key

        Returns:
            Extracted expense data

        Raises:
            Exception: If Textract analysis fails
        """
        try:
            logger.info(f"Analyzing expense document: s3://{bucket}/{key}")

            response = self.client.analyze_expense(
                Document={
                    'S3Object': {
                        'Bucket': bucket,
                        'Name': key
                    }
                }
            )

            # Parse expense documents
            expense_documents = response.get('ExpenseDocuments', [])

            if not expense_documents:
                logger.warning("No expense documents found")
                return self._empty_result()

            # Process first document (receipts typically have one)
            document = expense_documents[0]

            # Extract summary fields and line items
            result = self._extract_expense_data(document)

            logger.info(f"Successfully analyzed expense: {result}")
            return result

        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Textract analysis failed: {error_code}")
            raise Exception(f"Textract analysis failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during Textract analysis: {str(e)}")
            raise

    def detect_document_text(self, bucket: str, key: str) -> str:
        """
        Detect all text in document (fallback method).

        Args:
            bucket: S3 bucket name
            key: S3 object key

        Returns:
            Extracted text

        Raises:
            Exception: If text detection fails
        """
        try:
            logger.info(f"Detecting document text: s3://{bucket}/{key}")

            response = self.client.detect_document_text(
                Document={
                    'S3Object': {
                        'Bucket': bucket,
                        'Name': key
                    }
                }
            )

            # Extract all text
            blocks = response.get('Blocks', [])
            text_lines = []

            for block in blocks:
                if block['BlockType'] == 'LINE':
                    text_lines.append(block.get('Text', ''))

            full_text = '\n'.join(text_lines)
            logger.info(f"Extracted {len(text_lines)} lines of text")

            return full_text

        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Text detection failed: {error_code}")
            raise Exception(f"Text detection failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during text detection: {str(e)}")
            raise

    def _extract_expense_data(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract structured expense data from Textract document.

        Args:
            document: Textract expense document

        Returns:
            Structured expense data
        """
        result = {
            'merchant': None,
            'total': None,
            'subtotal': None,
            'tax': None,
            'date': None,
            'items': [],
            'raw_text': '',
            'confidence_score': 0.0
        }

        # Extract summary fields
        summary_fields = document.get('SummaryFields', [])
        confidence_scores = []

        for field in summary_fields:
            field_type = field.get('Type', {}).get('Text', '')
            value_detection = field.get('ValueDetection', {})
            value = value_detection.get('Text', '')
            confidence = value_detection.get('Confidence', 0)

            if confidence >= self.confidence_threshold:
                confidence_scores.append(confidence)

                if field_type == 'VENDOR_NAME':
                    result['merchant'] = value
                elif field_type == 'TOTAL':
                    result['total'] = self._parse_amount(value)
                elif field_type == 'SUBTOTAL':
                    result['subtotal'] = self._parse_amount(value)
                elif field_type == 'TAX':
                    result['tax'] = self._parse_amount(value)
                elif field_type in ['INVOICE_RECEIPT_DATE', 'DATE']:
                    result['date'] = self._parse_date(value)

        # Extract line items
        line_item_groups = document.get('LineItemGroups', [])

        for group in line_item_groups:
            for line_item in group.get('LineItems', []):
                item = self._extract_line_item(line_item)
                if item:
                    result['items'].append(item)

        # Calculate average confidence
        if confidence_scores:
            result['confidence_score'] = sum(confidence_scores) / len(confidence_scores)

        # Build raw text from all fields
        all_text = []
        for field in summary_fields:
            text = field.get('ValueDetection', {}).get('Text', '')
            if text:
                all_text.append(text)

        result['raw_text'] = ' '.join(all_text)

        return result

    def _extract_line_item(self, line_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract line item data.

        Args:
            line_item: Textract line item

        Returns:
            Structured line item data
        """
        item = {
            'description': None,
            'quantity': None,
            'price': None,
            'amount': None
        }

        for field in line_item.get('LineItemExpenseFields', []):
            field_type = field.get('Type', {}).get('Text', '')
            value = field.get('ValueDetection', {}).get('Text', '')
            confidence = field.get('ValueDetection', {}).get('Confidence', 0)

            if confidence >= self.confidence_threshold:
                if field_type == 'ITEM':
                    item['description'] = value
                elif field_type == 'QUANTITY':
                    item['quantity'] = self._parse_quantity(value)
                elif field_type == 'PRICE':
                    item['price'] = self._parse_amount(value)
                elif field_type == 'EXPENSE_ROW':
                    item['amount'] = self._parse_amount(value)

        # Only return items with at least a description
        if item['description']:
            return item
        return None

    @staticmethod
    def _parse_amount(value: str) -> float:
        """Parse monetary amount from string."""
        if not value:
            return None

        try:
            # Remove currency symbols and whitespace
            cleaned = value.replace('$', '').replace(',', '').strip()
            return float(cleaned)
        except ValueError:
            logger.warning(f"Failed to parse amount: {value}")
            return None

    @staticmethod
    def _parse_quantity(value: str) -> float:
        """Parse quantity from string."""
        if not value:
            return None

        try:
            return float(value.replace(',', '').strip())
        except ValueError:
            logger.warning(f"Failed to parse quantity: {value}")
            return None

    @staticmethod
    def _parse_date(value: str) -> str:
        """Parse date from string."""
        if not value:
            return None

        from dateutil import parser
        try:
            parsed_date = parser.parse(value, fuzzy=True)
            # Return in ISO format (YYYY-MM-DD)
            return parsed_date.strftime('%Y-%m-%d')
        except Exception:
            logger.warning(f"Failed to parse date: {value}")
            return None

    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        """Return empty result structure."""
        return {
            'merchant': None,
            'total': None,
            'subtotal': None,
            'tax': None,
            'date': None,
            'items': [],
            'raw_text': '',
            'confidence_score': 0.0
        }
