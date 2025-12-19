"""Parser for OCR results."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)


class ReceiptParser:
    """Parser for receipt OCR results."""

    @staticmethod
    def validate_and_clean(ocr_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean OCR data.

        Args:
            ocr_data: Raw OCR data from Textract

        Returns:
            Cleaned and validated data
        """
        cleaned = ocr_data.copy()

        # Validate and fix amount
        if cleaned.get('total'):
            cleaned['total'] = ReceiptParser._validate_amount(cleaned['total'])

        if cleaned.get('subtotal'):
            cleaned['subtotal'] = ReceiptParser._validate_amount(cleaned['subtotal'])

        if cleaned.get('tax'):
            cleaned['tax'] = ReceiptParser._validate_amount(cleaned['tax'])

        # Validate amounts relationship
        if cleaned.get('total') and cleaned.get('subtotal') and cleaned.get('tax'):
            # Check if total ≈ subtotal + tax (within 10% tolerance)
            expected_total = cleaned['subtotal'] + cleaned['tax']
            if abs(cleaned['total'] - expected_total) / cleaned['total'] > 0.10:
                logger.warning(
                    f"Amount mismatch: total={cleaned['total']}, "
                    f"subtotal={cleaned['subtotal']}, tax={cleaned['tax']}"
                )

        # If total is missing but we have subtotal and tax, calculate it
        if not cleaned.get('total') and cleaned.get('subtotal') and cleaned.get('tax'):
            cleaned['total'] = cleaned['subtotal'] + cleaned['tax']
            logger.info(f"Calculated total from subtotal and tax: {cleaned['total']}")

        # If total is missing but we have subtotal, use subtotal as total
        if not cleaned.get('total') and cleaned.get('subtotal'):
            cleaned['total'] = cleaned['subtotal']
            logger.info(f"Using subtotal as total: {cleaned['total']}")

        # Validate and fix date
        if cleaned.get('date'):
            cleaned['date'] = ReceiptParser._validate_date(cleaned['date'])

        # If date is missing, try to infer from current date (use today as default)
        if not cleaned.get('date'):
            cleaned['date'] = datetime.utcnow().strftime('%Y-%m-%d')
            logger.info(f"Using current date as receipt date: {cleaned['date']}")

        # Clean merchant name
        if cleaned.get('merchant'):
            cleaned['merchant'] = ReceiptParser._clean_merchant_name(cleaned['merchant'])

        # Clean items
        if cleaned.get('items'):
            cleaned['items'] = [
                ReceiptParser._clean_item(item)
                for item in cleaned['items']
                if item
            ]

        return cleaned

    @staticmethod
    def _validate_amount(amount: Any) -> Optional[float]:
        """Validate and convert amount to float."""
        if amount is None:
            return None

        try:
            value = float(amount)
            if value < 0:
                logger.warning(f"Negative amount detected: {value}")
                return abs(value)
            if value > 999999.99:
                logger.warning(f"Extremely large amount detected: {value}")
                return None
            return round(value, 2)
        except (ValueError, TypeError):
            logger.warning(f"Invalid amount value: {amount}")
            return None

    @staticmethod
    def _validate_date(date_str: str) -> Optional[str]:
        """Validate and normalize date string."""
        if not date_str:
            return None

        try:
            # Parse date
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')

            # Check if date is reasonable (not in future, not too old)
            now = datetime.utcnow()
            if date_obj > now:
                logger.warning(f"Future date detected: {date_str}, using today")
                return now.strftime('%Y-%m-%d')

            # Check if date is more than 10 years old
            if date_obj < now - timedelta(days=3650):
                logger.warning(f"Very old date detected: {date_str}")

            return date_str

        except ValueError:
            logger.warning(f"Invalid date format: {date_str}")
            return None

    @staticmethod
    def _clean_merchant_name(merchant: str) -> str:
        """Clean merchant name."""
        if not merchant:
            return "Unknown Merchant"

        # Remove extra whitespace
        cleaned = ' '.join(merchant.split())

        # Capitalize properly
        cleaned = cleaned.title()

        # Remove common suffixes
        suffixes_to_remove = [' Inc', ' Inc.', ' LLC', ' Ltd', ' Corp', ' Corporation']
        for suffix in suffixes_to_remove:
            if cleaned.endswith(suffix):
                cleaned = cleaned[:-len(suffix)]

        return cleaned.strip() or "Unknown Merchant"

    @staticmethod
    def _clean_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Clean line item."""
        if not item or not item.get('description'):
            return None

        cleaned = {
            'description': item['description'].strip(),
            'quantity': item.get('quantity'),
            'price': ReceiptParser._validate_amount(item.get('price')),
            'amount': ReceiptParser._validate_amount(item.get('amount'))
        }

        # If amount is missing but we have quantity and price, calculate it
        if not cleaned['amount'] and cleaned['quantity'] and cleaned['price']:
            cleaned['amount'] = round(cleaned['quantity'] * cleaned['price'], 2)

        return cleaned

    @staticmethod
    def extract_metadata(ocr_data: Dict[str, Any], category_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract metadata for expense record.

        Args:
            ocr_data: OCR data
            category_data: Category data from Comprehend

        Returns:
            Metadata dictionary
        """
        return {
            'ocr_confidence': str(round(ocr_data.get('confidence_score', 0), 2)),
            'category_confidence': str(round(category_data.get('confidence', 0), 2)),
            'category_method': category_data.get('method', 'unknown'),
            'has_items': str(len(ocr_data.get('items', [])) > 0),
            'item_count': str(len(ocr_data.get('items', [])))
        }
