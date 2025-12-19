"""Budget service for managing budgets and alerts."""

import os
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import logging
from boto3.dynamodb.conditions import Key

from shared.dynamodb import DynamoDBClient
from shared.validators import (
    validate_amount,
    validate_category,
    validate_period,
    validate_threshold,
    sanitize_string
)
from shared.exceptions import ValidationError, NotFoundError

logger = logging.getLogger(__name__)


class BudgetService:
    """Service for managing budgets."""

    def __init__(self):
        """Initialize budget service."""
        self.budgets_table = DynamoDBClient(os.environ.get('BUDGETS_TABLE'))
        self.expenses_table = DynamoDBClient(os.environ.get('EXPENSES_TABLE'))

    def create_budget(
        self,
        user_id: str,
        category: str,
        amount: float,
        period: str,
        alert_threshold: int = 90
    ) -> Dict[str, Any]:
        """
        Create a new budget.

        Args:
            user_id: User ID
            category: Budget category
            amount: Budget amount
            period: Budget period (weekly/monthly)
            alert_threshold: Alert threshold percentage (default: 90%)

        Returns:
            Created budget

        Raises:
            ValidationError: If validation fails
        """
        # Validate inputs
        category = validate_category(category)
        amount = float(validate_amount(amount))
        period = validate_period(period)
        alert_threshold = validate_threshold(alert_threshold)

        # Generate budget ID
        budget_id = str(uuid.uuid4())

        # Create budget record
        budget = {
            'user_id': user_id,
            'budget_id': budget_id,
            'category': category,
            'amount': amount,
            'period': period,
            'alert_threshold': alert_threshold,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'is_active': True
        }

        # Save to DynamoDB
        self.budgets_table.put_item(budget)

        logger.info(f"Created budget {budget_id} for category {category}")
        return budget

    def get_budget(self, user_id: str, budget_id: str) -> Dict[str, Any]:
        """
        Get budget by ID.

        Args:
            user_id: User ID
            budget_id: Budget ID

        Returns:
            Budget data

        Raises:
            NotFoundError: If budget not found
        """
        budget = self.budgets_table.get_item({
            'user_id': user_id,
            'budget_id': budget_id
        })

        if not budget:
            raise NotFoundError("Budget not found")

        # Add current spending
        budget['current_spending'] = self._get_current_spending(
            user_id,
            budget['category'],
            budget['period']
        )

        # Calculate percentage used
        if budget['amount'] > 0:
            budget['percentage_used'] = round(
                (budget['current_spending'] / budget['amount']) * 100,
                2
            )
        else:
            budget['percentage_used'] = 0.0

        # Check if over budget
        budget['is_over_budget'] = budget['current_spending'] > budget['amount']

        # Check if alert should be triggered
        budget['should_alert'] = (
            budget['percentage_used'] >= budget['alert_threshold']
        )

        return budget

    def list_budgets(
        self,
        user_id: str,
        active_only: bool = True
    ) -> Dict[str, Any]:
        """
        List budgets for a user.

        Args:
            user_id: User ID
            active_only: Only return active budgets

        Returns:
            Dictionary with budgets
        """
        # Query all budgets for user
        result = self.budgets_table.query(
            key_condition_expression=Key('user_id').eq(user_id),
            scan_forward=False
        )

        budgets = result['items']

        # Filter active budgets if requested
        if active_only:
            budgets = [b for b in budgets if b.get('is_active', True)]

        # Add current spending and status to each budget
        for budget in budgets:
            budget['current_spending'] = self._get_current_spending(
                user_id,
                budget['category'],
                budget['period']
            )

            if budget['amount'] > 0:
                budget['percentage_used'] = round(
                    (budget['current_spending'] / budget['amount']) * 100,
                    2
                )
            else:
                budget['percentage_used'] = 0.0

            budget['is_over_budget'] = budget['current_spending'] > budget['amount']
            budget['should_alert'] = (
                budget['percentage_used'] >= budget['alert_threshold']
            )

        return {
            'budgets': budgets,
            'count': len(budgets)
        }

    def update_budget(
        self,
        user_id: str,
        budget_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update budget.

        Args:
            user_id: User ID
            budget_id: Budget ID
            updates: Fields to update

        Returns:
            Updated budget

        Raises:
            NotFoundError: If budget not found
            ValidationError: If validation fails
        """
        # Verify budget exists
        budget = self.get_budget(user_id, budget_id)

        # Validate updates
        if 'amount' in updates:
            updates['amount'] = float(validate_amount(updates['amount']))

        if 'category' in updates:
            updates['category'] = validate_category(updates['category'])

        if 'period' in updates:
            updates['period'] = validate_period(updates['period'])

        if 'alert_threshold' in updates:
            updates['alert_threshold'] = validate_threshold(updates['alert_threshold'])

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
        updated_budget = self.budgets_table.update_item(
            key={'user_id': user_id, 'budget_id': budget_id},
            update_expression=update_expr,
            expression_values=expr_values,
            expression_names=expr_names
        )

        logger.info(f"Updated budget {budget_id}")
        return updated_budget

    def delete_budget(self, user_id: str, budget_id: str) -> None:
        """
        Delete budget (mark as inactive).

        Args:
            user_id: User ID
            budget_id: Budget ID

        Raises:
            NotFoundError: If budget not found
        """
        # Verify budget exists
        self.get_budget(user_id, budget_id)

        # Mark as inactive instead of deleting
        self.budgets_table.update_item(
            key={'user_id': user_id, 'budget_id': budget_id},
            update_expression="SET is_active = :inactive, updated_at = :updated_at",
            expression_values={
                ':inactive': False,
                ':updated_at': datetime.utcnow().isoformat()
            }
        )

        logger.info(f"Deactivated budget {budget_id}")

    def _get_current_spending(
        self,
        user_id: str,
        category: str,
        period: str
    ) -> float:
        """
        Get current spending for a budget period.

        Args:
            user_id: User ID
            category: Budget category
            period: Budget period (weekly/monthly)

        Returns:
            Total spending amount
        """
        # Calculate date range based on period
        end_date = datetime.utcnow()

        if period == 'weekly':
            # Start from beginning of current week (Monday)
            days_since_monday = end_date.weekday()
            start_date = end_date - timedelta(days=days_since_monday)
        else:  # monthly
            # Start from beginning of current month
            start_date = end_date.replace(day=1)

        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

        # Query expenses for category in date range
        from boto3.dynamodb.conditions import Attr

        result = self.expenses_table.query(
            key_condition_expression=Key('user_id').eq(user_id) & Key('category').eq(category),
            filter_expression=Attr('date').between(start_date_str, end_date_str),
            index_name='user-category-index'
        )

        # Sum up amounts
        total = sum(float(expense.get('amount', 0)) for expense in result['items'])

        return round(total, 2)

    def check_budget_alerts(self, user_id: str) -> list:
        """
        Check all budgets for alerts.

        Args:
            user_id: User ID

        Returns:
            List of budgets that should trigger alerts
        """
        budgets_result = self.list_budgets(user_id, active_only=True)
        budgets = budgets_result['budgets']

        # Filter budgets that should trigger alerts
        alert_budgets = [
            budget for budget in budgets
            if budget.get('should_alert', False)
        ]

        return alert_budgets
