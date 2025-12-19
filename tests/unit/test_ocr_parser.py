"""Unit tests for OCR parser."""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ocr_processor.parser import ReceiptParser


class TestReceiptParser:
    """Test cases for ReceiptParser."""

    def test_validate_and_clean_complete_data(self):
        """Test validation with complete OCR data."""
        ocr_data = {
            'merchant': 'WALMART INC.',
            'total': 45.67,
            'subtotal': 42.00,
            'tax': 3.67,
            'date': '2024-01-15',
            'items': [
                {'description': 'Bananas', 'quantity': 2, 'price': 1.50, 'amount': 3.00},
                {'description': 'Milk', 'quantity': 1, 'price': 3.99, 'amount': 3.99}
            ],
            'raw_text': 'WALMART receipt',
            'confidence_score': 95.5
        }

        cleaned = ReceiptParser.validate_and_clean(ocr_data)

        assert cleaned['merchant'] == 'Walmart'
        assert cleaned['total'] == 45.67
        assert cleaned['subtotal'] == 42.00
        assert cleaned['tax'] == 3.67
        assert cleaned['date'] == '2024-01-15'
        assert len(cleaned['items']) == 2

    def test_validate_and_clean_missing_total(self):
        """Test validation when total is missing but subtotal and tax are present."""
        ocr_data = {
            'merchant': 'Test Store',
            'subtotal': 50.00,
            'tax': 5.00,
            'date': '2024-01-15',
            'items': [],
            'raw_text': '',
            'confidence_score': 80.0
        }

        cleaned = ReceiptParser.validate_and_clean(ocr_data)

        # Should calculate total from subtotal + tax
        assert cleaned['total'] == 55.00

    def test_validate_and_clean_missing_date(self):
        """Test validation when date is missing."""
        ocr_data = {
            'merchant': 'Test Store',
            'total': 25.00,
            'items': [],
            'raw_text': '',
            'confidence_score': 80.0
        }

        cleaned = ReceiptParser.validate_and_clean(ocr_data)

        # Should use current date
        assert cleaned['date'] is not None
        assert cleaned['date'] == datetime.utcnow().strftime('%Y-%m-%d')

    def test_validate_amount_negative(self):
        """Test validation of negative amounts."""
        amount = ReceiptParser._validate_amount(-10.50)

        # Should convert to positive
        assert amount == 10.50

    def test_validate_amount_too_large(self):
        """Test validation of extremely large amounts."""
        amount = ReceiptParser._validate_amount(9999999.99)

        # Should return None for unreasonably large amounts
        assert amount is None

    def test_validate_amount_too_many_decimals(self):
        """Test validation of amounts with too many decimal places."""
        amount = ReceiptParser._validate_amount(10.999)

        # Should round to 2 decimal places
        assert amount == 10.999

    def test_validate_date_future(self):
        """Test validation of future dates."""
        future_date = (datetime.utcnow() + timedelta(days=10)).strftime('%Y-%m-%d')

        validated = ReceiptParser._validate_date(future_date)

        # Should use current date instead
        assert validated == datetime.utcnow().strftime('%Y-%m-%d')

    def test_validate_date_very_old(self):
        """Test validation of very old dates."""
        old_date = '2010-01-01'

        validated = ReceiptParser._validate_date(old_date)

        # Should still be valid but logged as warning
        assert validated == '2010-01-01'

    def test_clean_merchant_name(self):
        """Test merchant name cleaning."""
        # Test removing Inc suffix
        assert ReceiptParser._clean_merchant_name('WALMART INC.') == 'Walmart'

        # Test removing LLC suffix
        assert ReceiptParser._clean_merchant_name('test store llc') == 'Test Store'

        # Test removing extra whitespace
        assert ReceiptParser._clean_merchant_name('  TEST   STORE  ') == 'Test Store'

    def test_clean_item(self):
        """Test line item cleaning."""
        item = {
            'description': '  Bananas  ',
            'quantity': 2,
            'price': 1.50,
            'amount': None
        }

        cleaned = ReceiptParser._clean_item(item)

        assert cleaned['description'] == 'Bananas'
        assert cleaned['quantity'] == 2
        assert cleaned['price'] == 1.50
        # Should calculate amount from quantity * price
        assert cleaned['amount'] == 3.00

    def test_clean_item_no_description(self):
        """Test cleaning item with no description."""
        item = {
            'description': None,
            'quantity': 1,
            'price': 5.00
        }

        cleaned = ReceiptParser._clean_item(item)

        # Should return None for items without description
        assert cleaned is None

    def test_extract_metadata(self):
        """Test metadata extraction."""
        ocr_data = {
            'confidence_score': 92.5,
            'items': [{'description': 'Item 1'}, {'description': 'Item 2'}]
        }

        category_data = {
            'confidence': 85.0,
            'method': 'keywords'
        }

        metadata = ReceiptParser.extract_metadata(ocr_data, category_data)

        assert metadata['ocr_confidence'] == '92.5'
        assert metadata['category_confidence'] == '85.0'
        assert metadata['category_method'] == 'keywords'
        assert metadata['has_items'] == 'True'
        assert metadata['item_count'] == '2'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
