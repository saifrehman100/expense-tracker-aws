"""Unit tests for expense service."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from expenses.service import ExpenseService
from shared.exceptions import NotFoundError, ValidationError


class TestExpenseService:
    """Test cases for ExpenseService."""

    @pytest.fixture
    def expense_service(self):
        """Create expense service instance with mocked DynamoDB."""
        with patch('expenses.service.DynamoDBClient') as mock_db:
            service = ExpenseService()
            service.expenses_table = Mock()
            return service

    @pytest.fixture
    def sample_expense(self):
        """Sample expense data."""
        return {
            'user_id': 'user123',
            'expense_id': 'exp123',
            'amount': 45.67,
            'merchant': 'Walmart',
            'category': 'Groceries',
            'date': '2024-01-15',
            'created_at': '2024-01-15T10:00:00',
            'updated_at': '2024-01-15T10:00:00'
        }

    def test_get_expense_success(self, expense_service, sample_expense):
        """Test getting an expense successfully."""
        expense_service.expenses_table.get_item.return_value = sample_expense

        result = expense_service.get_expense('user123', 'exp123')

        assert result == sample_expense
        expense_service.expenses_table.get_item.assert_called_once_with({
            'user_id': 'user123',
            'expense_id': 'exp123'
        })

    def test_get_expense_not_found(self, expense_service):
        """Test getting a non-existent expense."""
        expense_service.expenses_table.get_item.return_value = None

        with pytest.raises(NotFoundError, match="Expense not found"):
            expense_service.get_expense('user123', 'nonexistent')

    def test_update_expense_success(self, expense_service, sample_expense):
        """Test updating an expense successfully."""
        expense_service.expenses_table.get_item.return_value = sample_expense
        expense_service.expenses_table.update_item.return_value = {
            **sample_expense,
            'amount': 50.00
        }

        updates = {'amount': 50.00}
        result = expense_service.update_expense('user123', 'exp123', updates)

        assert result['amount'] == 50.00
        expense_service.expenses_table.update_item.assert_called_once()

    def test_update_expense_validate_amount(self, expense_service, sample_expense):
        """Test that update validates amount."""
        expense_service.expenses_table.get_item.return_value = sample_expense

        with pytest.raises(ValidationError):
            expense_service.update_expense('user123', 'exp123', {'amount': -10})

    def test_update_expense_validate_category(self, expense_service, sample_expense):
        """Test that update validates category."""
        expense_service.expenses_table.get_item.return_value = sample_expense

        with pytest.raises(ValidationError):
            expense_service.update_expense('user123', 'exp123', {'category': 'InvalidCategory'})

    def test_delete_expense_success(self, expense_service, sample_expense):
        """Test deleting an expense successfully."""
        expense_service.expenses_table.get_item.return_value = sample_expense

        expense_service.delete_expense('user123', 'exp123')

        expense_service.expenses_table.delete_item.assert_called_once_with({
            'user_id': 'user123',
            'expense_id': 'exp123'
        })

    def test_delete_expense_not_found(self, expense_service):
        """Test deleting a non-existent expense."""
        expense_service.expenses_table.get_item.return_value = None

        with pytest.raises(NotFoundError):
            expense_service.delete_expense('user123', 'nonexistent')

    def test_get_summary(self, expense_service):
        """Test getting expense summary."""
        # Mock expenses
        expenses = [
            {
                'amount': 45.67,
                'category': 'Groceries',
                'date': '2024-01-15'
            },
            {
                'amount': 25.00,
                'category': 'Food & Dining',
                'date': '2024-01-16'
            },
            {
                'amount': 30.00,
                'category': 'Groceries',
                'date': '2024-01-17'
            }
        ]

        expense_service.expenses_table.query.return_value = {
            'items': expenses,
            'last_evaluated_key': None
        }

        summary = expense_service.get_summary('user123', '2024-01-15', '2024-01-20')

        assert summary['total_amount'] == 100.67
        assert summary['expense_count'] == 3
        assert summary['by_category']['Groceries'] == 75.67
        assert summary['by_category']['Food & Dining'] == 25.00
        assert summary['by_month']['2024-01'] == 100.67

    def test_list_expenses_with_category_filter(self, expense_service):
        """Test listing expenses with category filter."""
        mock_result = {
            'items': [{'expense_id': 'exp1'}, {'expense_id': 'exp2'}],
            'last_evaluated_key': None
        }

        expense_service.expenses_table.query.return_value = mock_result

        result = expense_service.list_expenses(
            user_id='user123',
            category='Groceries'
        )

        assert result['count'] == 2
        assert result['expenses'] == mock_result['items']

    def test_list_expenses_with_date_range(self, expense_service):
        """Test listing expenses with date range."""
        mock_result = {
            'items': [{'expense_id': 'exp1'}],
            'last_evaluated_key': None
        }

        expense_service.expenses_table.query.return_value = mock_result

        result = expense_service.list_expenses(
            user_id='user123',
            start_date='2024-01-01',
            end_date='2024-01-31'
        )

        assert result['count'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
