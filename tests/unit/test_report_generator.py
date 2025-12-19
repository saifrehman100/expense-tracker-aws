"""Unit tests for report generator."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from reports.generator import ReportGenerator


class TestReportGenerator:
    """Test cases for ReportGenerator."""

    @pytest.fixture
    def report_generator(self):
        """Create report generator instance with mocked DynamoDB."""
        with patch('reports.generator.DynamoDBClient') as mock_db:
            generator = ReportGenerator()
            generator.expenses_table = Mock()
            generator.budgets_table = Mock()
            generator.users_table = Mock()
            return generator

    @pytest.fixture
    def sample_expenses(self):
        """Sample expenses data."""
        return [
            {
                'amount': 45.67,
                'merchant': 'Walmart',
                'category': 'Groceries',
                'date': '2024-01-15',
                'items': []
            },
            {
                'amount': 25.00,
                'merchant': 'Starbucks',
                'category': 'Food & Dining',
                'date': '2024-01-16',
                'items': []
            },
            {
                'amount': 30.00,
                'merchant': 'Target',
                'category': 'Shopping',
                'date': '2024-01-17',
                'items': []
            }
        ]

    def test_generate_weekly_report(self, report_generator, sample_expenses):
        """Test generating weekly report."""
        report_generator.expenses_table.query.return_value = {
            'items': sample_expenses,
            'last_evaluated_key': None
        }

        report_generator.users_table.get_item.return_value = {
            'user_id': 'user123',
            'email': 'test@example.com',
            'name': 'Test User'
        }

        report = report_generator.generate_weekly_report('user123')

        assert report['report_type'] == 'weekly'
        assert report['summary']['total_amount'] == 100.67
        assert report['summary']['expense_count'] == 3
        assert 'Groceries' in report['by_category']
        assert report['by_category']['Groceries']['amount'] == 45.67

    def test_generate_monthly_report(self, report_generator, sample_expenses):
        """Test generating monthly report."""
        report_generator.expenses_table.query.return_value = {
            'items': sample_expenses,
            'last_evaluated_key': None
        }

        report_generator.users_table.get_item.return_value = {
            'user_id': 'user123',
            'email': 'test@example.com',
            'name': 'Test User'
        }

        report = report_generator.generate_monthly_report('user123')

        assert report['report_type'] == 'monthly'
        assert report['summary']['total_amount'] == 100.67

    def test_generate_report_with_pagination(self, report_generator):
        """Test report generation with pagination."""
        # Simulate pagination with multiple queries
        expenses_page1 = [{'amount': 10.00, 'category': 'Food & Dining', 'merchant': 'Store1', 'date': '2024-01-15'}] * 50
        expenses_page2 = [{'amount': 20.00, 'category': 'Shopping', 'merchant': 'Store2', 'date': '2024-01-16'}] * 50

        report_generator.expenses_table.query.side_effect = [
            {'items': expenses_page1, 'last_evaluated_key': {'key': 'value'}},
            {'items': expenses_page2, 'last_evaluated_key': None}
        ]

        report_generator.users_table.get_item.return_value = {
            'user_id': 'user123',
            'email': 'test@example.com',
            'name': 'Test User'
        }

        report = report_generator.generate_weekly_report('user123')

        # Should have combined all expenses
        assert report['summary']['expense_count'] == 100
        assert report['summary']['total_amount'] == 1500.00  # (50 * 10) + (50 * 20)

    def test_export_to_csv(self, report_generator, sample_expenses):
        """Test CSV export."""
        report_generator.expenses_table.query.return_value = {
            'items': sample_expenses,
            'last_evaluated_key': None
        }

        csv_content = report_generator.export_to_csv('user123', '2024-01-01', '2024-01-31')

        # Check CSV content
        assert 'Date,Merchant,Category,Amount' in csv_content
        assert 'Walmart' in csv_content
        assert 'Starbucks' in csv_content
        assert '45.67' in csv_content

    def test_format_report_html(self, report_generator):
        """Test HTML formatting."""
        report = {
            'report_type': 'weekly',
            'start_date': '2024-01-15',
            'end_date': '2024-01-21',
            'summary': {
                'total_amount': 100.67,
                'expense_count': 5,
                'average_expense': 20.13
            },
            'by_category': {
                'Groceries': {'amount': 50.00, 'count': 2, 'percentage': 49.7}
            },
            'top_merchants': [
                {'name': 'Walmart', 'amount': 50.00, 'count': 2}
            ]
        }

        html = report_generator.format_report_html(report)

        # Check HTML contains key elements
        assert 'Weekly Expense Report' in html
        assert '2024-01-15' in html
        assert '100.67' in html
        assert 'Groceries' in html
        assert 'Walmart' in html

    def test_top_merchants_limited_to_10(self, report_generator):
        """Test that top merchants are limited to 10."""
        # Create 15 unique merchants
        expenses = [
            {
                'amount': float(i * 10),
                'merchant': f'Merchant{i}',
                'category': 'Shopping',
                'date': '2024-01-15',
                'items': []
            }
            for i in range(15)
        ]

        report_generator.expenses_table.query.return_value = {
            'items': expenses,
            'last_evaluated_key': None
        }

        report_generator.users_table.get_item.return_value = {
            'user_id': 'user123',
            'email': 'test@example.com',
            'name': 'Test User'
        }

        report = report_generator.generate_weekly_report('user123')

        # Should only have top 10 merchants
        assert len(report['top_merchants']) == 10

    def test_report_with_no_expenses(self, report_generator):
        """Test report generation with no expenses."""
        report_generator.expenses_table.query.return_value = {
            'items': [],
            'last_evaluated_key': None
        }

        report_generator.users_table.get_item.return_value = {
            'user_id': 'user123',
            'email': 'test@example.com',
            'name': 'Test User'
        }

        report = report_generator.generate_weekly_report('user123')

        assert report['summary']['total_amount'] == 0.0
        assert report['summary']['expense_count'] == 0
        assert report['summary']['average_expense'] == 0.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
