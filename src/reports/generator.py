"""Report generation utilities."""

import os
from typing import Dict, Any, List
from datetime import datetime, timedelta
from collections import defaultdict
import logging
from io import StringIO
import csv

from shared.dynamodb import DynamoDBClient

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Service for generating expense reports."""

    def __init__(self):
        """Initialize report generator."""
        self.expenses_table = DynamoDBClient(os.environ.get('EXPENSES_TABLE'))
        self.budgets_table = DynamoDBClient(os.environ.get('BUDGETS_TABLE'))
        self.users_table = DynamoDBClient(os.environ.get('USERS_TABLE'))

    def generate_weekly_report(self, user_id: str) -> Dict[str, Any]:
        """
        Generate weekly expense report.

        Args:
            user_id: User ID

        Returns:
            Weekly report data
        """
        # Calculate date range (last 7 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)

        return self._generate_report(
            user_id=user_id,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            report_type='weekly'
        )

    def generate_monthly_report(self, user_id: str) -> Dict[str, Any]:
        """
        Generate monthly expense report.

        Args:
            user_id: User ID

        Returns:
            Monthly report data
        """
        # Calculate date range (current month)
        end_date = datetime.utcnow()
        start_date = end_date.replace(day=1)

        return self._generate_report(
            user_id=user_id,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            report_type='monthly'
        )

    def _generate_report(
        self,
        user_id: str,
        start_date: str,
        end_date: str,
        report_type: str
    ) -> Dict[str, Any]:
        """
        Generate expense report for date range.

        Args:
            user_id: User ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            report_type: Report type (weekly/monthly)

        Returns:
            Report data
        """
        from boto3.dynamodb.conditions import Key, Attr

        # Fetch expenses for date range
        expenses = []
        last_key = None

        while True:
            result = self.expenses_table.query(
                key_condition_expression=Key('user_id').eq(user_id) & Key('date').between(start_date, end_date),
                index_name='user-date-index',
                limit=100,
                exclusive_start_key=last_key
            )

            expenses.extend(result['items'])
            last_key = result.get('last_evaluated_key')

            if not last_key:
                break

        # Calculate statistics
        total_amount = 0.0
        by_category = defaultdict(lambda: {'amount': 0.0, 'count': 0})
        by_merchant = defaultdict(lambda: {'amount': 0.0, 'count': 0})
        by_date = defaultdict(float)

        for expense in expenses:
            amount = float(expense.get('amount', 0))
            category = expense.get('category', 'Other')
            merchant = expense.get('merchant', 'Unknown')
            date = expense.get('date', '')

            total_amount += amount

            by_category[category]['amount'] += amount
            by_category[category]['count'] += 1

            by_merchant[merchant]['amount'] += amount
            by_merchant[merchant]['count'] += 1

            if date:
                by_date[date] += amount

        # Get top merchants
        top_merchants = sorted(
            by_merchant.items(),
            key=lambda x: x[1]['amount'],
            reverse=True
        )[:10]

        # Calculate average daily spending
        date_range_days = (
            datetime.strptime(end_date, '%Y-%m-%d') -
            datetime.strptime(start_date, '%Y-%m-%d')
        ).days + 1

        average_daily = total_amount / date_range_days if date_range_days > 0 else 0.0

        # Get user info
        user = self.users_table.get_item({'user_id': user_id}) or {}

        # Build report
        report = {
            'report_type': report_type,
            'start_date': start_date,
            'end_date': end_date,
            'generated_at': datetime.utcnow().isoformat(),
            'user': {
                'user_id': user_id,
                'email': user.get('email', ''),
                'name': user.get('name', '')
            },
            'summary': {
                'total_amount': round(total_amount, 2),
                'expense_count': len(expenses),
                'average_expense': round(total_amount / len(expenses), 2) if expenses else 0.0,
                'average_daily': round(average_daily, 2),
                'date_range_days': date_range_days
            },
            'by_category': {
                k: {
                    'amount': round(v['amount'], 2),
                    'count': v['count'],
                    'percentage': round((v['amount'] / total_amount * 100), 2) if total_amount > 0 else 0.0
                }
                for k, v in by_category.items()
            },
            'top_merchants': [
                {
                    'name': merchant,
                    'amount': round(data['amount'], 2),
                    'count': data['count']
                }
                for merchant, data in top_merchants
            ],
            'daily_spending': {
                date: round(amount, 2)
                for date, amount in sorted(by_date.items())
            }
        }

        return report

    def export_to_csv(self, user_id: str, start_date: str, end_date: str) -> str:
        """
        Export expenses to CSV format.

        Args:
            user_id: User ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            CSV content as string
        """
        from boto3.dynamodb.conditions import Key

        # Fetch expenses for date range
        expenses = []
        last_key = None

        while True:
            result = self.expenses_table.query(
                key_condition_expression=Key('user_id').eq(user_id) & Key('date').between(start_date, end_date),
                index_name='user-date-index',
                limit=100,
                exclusive_start_key=last_key
            )

            expenses.extend(result['items'])
            last_key = result.get('last_evaluated_key')

            if not last_key:
                break

        # Create CSV
        output = StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'Date',
            'Merchant',
            'Category',
            'Amount',
            'Items',
            'Receipt ID',
            'Created At'
        ])

        # Write expenses
        for expense in sorted(expenses, key=lambda x: x.get('date', '')):
            items_str = '; '.join([
                item.get('description', '')
                for item in expense.get('items', [])
                if item
            ])

            writer.writerow([
                expense.get('date', ''),
                expense.get('merchant', ''),
                expense.get('category', ''),
                f"${expense.get('amount', 0):.2f}",
                items_str,
                expense.get('receipt_id', ''),
                expense.get('created_at', '')
            ])

        csv_content = output.getvalue()
        output.close()

        return csv_content

    def format_report_html(self, report: Dict[str, Any]) -> str:
        """
        Format report as HTML for email.

        Args:
            report: Report data

        Returns:
            HTML content
        """
        report_type = report['report_type'].capitalize()
        total_amount = report['summary']['total_amount']
        expense_count = report['summary']['expense_count']
        average_expense = report['summary']['average_expense']

        # Build category rows
        category_rows = ''
        for category, data in sorted(
            report['by_category'].items(),
            key=lambda x: x[1]['amount'],
            reverse=True
        ):
            category_rows += f"""
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">{category}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #e0e0e0; text-align: right;">${data['amount']:.2f}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #e0e0e0; text-align: right;">{data['count']}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #e0e0e0; text-align: right;">{data['percentage']:.1f}%</td>
                </tr>
            """

        # Build merchant rows
        merchant_rows = ''
        for merchant_data in report['top_merchants'][:5]:
            merchant_rows += f"""
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">{merchant_data['name']}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #e0e0e0; text-align: right;">${merchant_data['amount']:.2f}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #e0e0e0; text-align: right;">{merchant_data['count']}</td>
                </tr>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{report_type} Expense Report</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #4CAF50; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                <h1 style="margin: 0;">{report_type} Expense Report</h1>
                <p style="margin: 10px 0 0 0;">{report['start_date']} to {report['end_date']}</p>
            </div>

            <div style="background-color: #f9f9f9; padding: 20px; border: 1px solid #e0e0e0;">
                <h2 style="color: #4CAF50; margin-top: 0;">Summary</h2>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                    <div style="background-color: white; padding: 15px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <h3 style="margin: 0 0 10px 0; color: #666; font-size: 14px;">Total Expenses</h3>
                        <p style="margin: 0; font-size: 28px; font-weight: bold; color: #4CAF50;">${total_amount:.2f}</p>
                    </div>
                    <div style="background-color: white; padding: 15px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <h3 style="margin: 0 0 10px 0; color: #666; font-size: 14px;">Number of Expenses</h3>
                        <p style="margin: 0; font-size: 28px; font-weight: bold; color: #2196F3;">{expense_count}</p>
                    </div>
                </div>
            </div>

            <div style="background-color: white; padding: 20px; border: 1px solid #e0e0e0; border-top: none;">
                <h2 style="color: #4CAF50;">Expenses by Category</h2>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background-color: #f5f5f5;">
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #4CAF50;">Category</th>
                            <th style="padding: 10px; text-align: right; border-bottom: 2px solid #4CAF50;">Amount</th>
                            <th style="padding: 10px; text-align: right; border-bottom: 2px solid #4CAF50;">Count</th>
                            <th style="padding: 10px; text-align: right; border-bottom: 2px solid #4CAF50;">Percentage</th>
                        </tr>
                    </thead>
                    <tbody>
                        {category_rows}
                    </tbody>
                </table>
            </div>

            <div style="background-color: white; padding: 20px; border: 1px solid #e0e0e0; border-top: none;">
                <h2 style="color: #4CAF50;">Top Merchants</h2>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background-color: #f5f5f5;">
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #4CAF50;">Merchant</th>
                            <th style="padding: 10px; text-align: right; border-bottom: 2px solid #4CAF50;">Amount</th>
                            <th style="padding: 10px; text-align: right; border-bottom: 2px solid #4CAF50;">Transactions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {merchant_rows}
                    </tbody>
                </table>
            </div>

            <div style="background-color: #f9f9f9; padding: 20px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 8px 8px; text-align: center; color: #666; font-size: 12px;">
                <p>Report generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
                <p>Smart Expense Tracker - Your Personal Finance Assistant</p>
            </div>
        </body>
        </html>
        """

        return html
