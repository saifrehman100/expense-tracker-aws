"""Expense service for managing expenses."""

import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import logging
from boto3.dynamodb.conditions import Key, Attr

from shared.dynamodb import DynamoDBClient
from shared.validators import (
    validate_amount,
    validate_category,
    validate_date,
    sanitize_string
)
from shared.exceptions import ValidationError, NotFoundError

logger = logging.getLogger(__name__)


class ExpenseService:
    """Service for managing expenses."""

    def __init__(self):
        """Initialize expense service."""
        self.expenses_table = DynamoDBClient(os.environ.get('EXPENSES_TABLE'))

    def get_expense(self, user_id: str, expense_id: str) -> Dict[str, Any]:
        """
        Get expense by ID.

        Args:
            user_id: User ID
            expense_id: Expense ID

        Returns:
            Expense data

        Raises:
            NotFoundError: If expense not found
        """
        expense = self.expenses_table.get_item({
            'user_id': user_id,
            'expense_id': expense_id
        })

        if not expense:
            raise NotFoundError("Expense not found")

        return expense

    def list_expenses(
        self,
        user_id: str,
        category: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50,
        last_evaluated_key: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        List expenses for a user with optional filters.

        Args:
            user_id: User ID
            category: Optional category filter
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            limit: Maximum number of results
            last_evaluated_key: Pagination key

        Returns:
            Dictionary with expenses and pagination key
        """
        # Use appropriate index based on filters
        if category:
            # Query by category
            result = self._query_by_category(
                user_id, category, start_date, end_date, limit, last_evaluated_key
            )
        elif start_date or end_date:
            # Query by date range
            result = self._query_by_date_range(
                user_id, start_date, end_date, limit, last_evaluated_key
            )
        else:
            # Query all expenses for user
            result = self.expenses_table.query(
                key_condition_expression=Key('user_id').eq(user_id),
                limit=limit,
                scan_forward=False,  # Most recent first
                exclusive_start_key=last_evaluated_key
            )

        return {
            'expenses': result['items'],
            'count': len(result['items']),
            'last_evaluated_key': result['last_evaluated_key']
        }

    def _query_by_category(
        self,
        user_id: str,
        category: str,
        start_date: Optional[str],
        end_date: Optional[str],
        limit: int,
        last_evaluated_key: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Query expenses by category."""
        key_condition = Key('user_id').eq(user_id) & Key('category').eq(category)

        # Add date filter if provided
        filter_expr = None
        if start_date and end_date:
            filter_expr = Attr('date').between(start_date, end_date)
        elif start_date:
            filter_expr = Attr('date').gte(start_date)
        elif end_date:
            filter_expr = Attr('date').lte(end_date)

        return self.expenses_table.query(
            key_condition_expression=key_condition,
            filter_expression=filter_expr,
            index_name='user-category-index',
            limit=limit,
            scan_forward=False,
            exclusive_start_key=last_evaluated_key
        )

    def _query_by_date_range(
        self,
        user_id: str,
        start_date: Optional[str],
        end_date: Optional[str],
        limit: int,
        last_evaluated_key: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Query expenses by date range."""
        # Build key condition with date range
        if start_date and end_date:
            key_condition = Key('user_id').eq(user_id) & Key('date').between(start_date, end_date)
        elif start_date:
            key_condition = Key('user_id').eq(user_id) & Key('date').gte(start_date)
        elif end_date:
            key_condition = Key('user_id').eq(user_id) & Key('date').lte(end_date)
        else:
            key_condition = Key('user_id').eq(user_id)

        return self.expenses_table.query(
            key_condition_expression=key_condition,
            index_name='user-date-index',
            limit=limit,
            scan_forward=False,
            exclusive_start_key=last_evaluated_key
        )

    def update_expense(
        self,
        user_id: str,
        expense_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update expense.

        Args:
            user_id: User ID
            expense_id: Expense ID
            updates: Fields to update

        Returns:
            Updated expense

        Raises:
            NotFoundError: If expense not found
            ValidationError: If validation fails
        """
        # Verify expense exists
        expense = self.get_expense(user_id, expense_id)

        # Validate updates
        if 'amount' in updates:
            updates['amount'] = float(validate_amount(updates['amount']))

        if 'category' in updates:
            updates['category'] = validate_category(updates['category'])

        if 'date' in updates:
            updates['date'] = validate_date(updates['date'])

        if 'merchant' in updates:
            updates['merchant'] = sanitize_string(updates['merchant'], max_length=200)

        if 'notes' in updates:
            updates['notes'] = sanitize_string(updates['notes'], max_length=1000)

        # Build update expression
        update_parts = []
        expr_values = {}
        expr_names = {}

        for key, value in updates.items():
            update_parts.append(f"#{key} = :{key}")
            expr_names[f'#{key}'] = key
            expr_values[f':{key}'] = value

        # Add updated_at timestamp
        update_parts.append("#updated_at = :updated_at")
        expr_names['#updated_at'] = 'updated_at'
        expr_values[':updated_at'] = datetime.utcnow().isoformat()

        update_expr = "SET " + ", ".join(update_parts)

        # Update in DynamoDB
        updated_expense = self.expenses_table.update_item(
            key={'user_id': user_id, 'expense_id': expense_id},
            update_expression=update_expr,
            expression_values=expr_values,
            expression_names=expr_names
        )

        logger.info(f"Updated expense {expense_id}")
        return updated_expense

    def delete_expense(self, user_id: str, expense_id: str) -> None:
        """
        Delete expense.

        Args:
            user_id: User ID
            expense_id: Expense ID

        Raises:
            NotFoundError: If expense not found
        """
        # Verify expense exists
        self.get_expense(user_id, expense_id)

        # Delete from DynamoDB
        self.expenses_table.delete_item({
            'user_id': user_id,
            'expense_id': expense_id
        })

        logger.info(f"Deleted expense {expense_id}")

    def get_summary(
        self,
        user_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get expense summary.

        Args:
            user_id: User ID
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)

        Returns:
            Summary statistics
        """
        # If no dates provided, use last 30 days
        if not start_date and not end_date:
            end_date = datetime.utcnow().strftime('%Y-%m-%d')
            start_date = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')

        # Fetch expenses
        expenses = []
        last_key = None

        while True:
            result = self.list_expenses(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                limit=100,
                last_evaluated_key=last_key
            )

            expenses.extend(result['expenses'])
            last_key = result.get('last_evaluated_key')

            if not last_key:
                break

        # Calculate summary
        total_amount = 0.0
        by_category = defaultdict(float)
        by_month = defaultdict(float)

        for expense in expenses:
            amount = float(expense.get('amount', 0))
            total_amount += amount

            # Group by category
            category = expense.get('category', 'Other')
            by_category[category] += amount

            # Group by month
            date_str = expense.get('date', '')
            if date_str:
                month = date_str[:7]  # YYYY-MM
                by_month[month] += amount

        expense_count = len(expenses)
        average_expense = total_amount / expense_count if expense_count > 0 else 0.0

        return {
            'total_amount': round(total_amount, 2),
            'expense_count': expense_count,
            'average_expense': round(average_expense, 2),
            'by_category': {k: round(v, 2) for k, v in by_category.items()},
            'by_month': {k: round(v, 2) for k, v in by_month.items()},
            'start_date': start_date,
            'end_date': end_date
        }
