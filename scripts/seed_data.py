#!/usr/bin/env python3
"""
Seed data script for testing the expense tracker application.
Creates sample users, expenses, and budgets for testing purposes.
"""

import boto3
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
import random

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from shared.validators import VALID_CATEGORIES


def get_table_names_from_stack(stack_name='expense-tracker-aws'):
    """Get table names from CloudFormation stack."""
    cf = boto3.client('cloudformation')

    try:
        response = cf.describe_stacks(StackName=stack_name)
        outputs = response['Stacks'][0]['Outputs']

        table_names = {}
        for output in outputs:
            key = output['OutputKey']
            if 'Table' in key:
                table_name = output['OutputValue']
                if 'Users' in key:
                    table_names['users'] = table_name
                elif 'Expenses' in key:
                    table_names['expenses'] = table_name
                elif 'Budgets' in key:
                    table_names['budgets'] = table_name
                elif 'Receipts' in key:
                    table_names['receipts'] = table_name

        return table_names
    except Exception as e:
        print(f"Error getting table names from stack: {e}")
        print("Using default table names...")
        return {
            'users': 'expense-tracker-aws-users',
            'expenses': 'expense-tracker-aws-expenses',
            'budgets': 'expense-tracker-aws-budgets',
            'receipts': 'expense-tracker-aws-receipts'
        }


def seed_expenses(dynamodb, table_name, user_id, num_expenses=50):
    """Seed sample expenses."""
    table = dynamodb.Table(table_name)

    merchants = {
        'Food & Dining': ['Starbucks', 'McDonalds', 'Chipotle', 'Local Restaurant', 'Pizza Hut'],
        'Groceries': ['Walmart', 'Target', 'Whole Foods', 'Trader Joes', 'Kroger'],
        'Transportation': ['Uber', 'Lyft', 'Shell Gas', 'Parking Garage', 'Metro Transit'],
        'Shopping': ['Amazon', 'Best Buy', 'Nike Store', 'H&M', 'Apple Store'],
        'Entertainment': ['Netflix', 'Movie Theater', 'Concert Ticket', 'Spotify', 'Gaming Store'],
        'Utilities': ['Electric Company', 'Water Utility', 'Internet Provider', 'Phone Bill'],
        'Healthcare': ['CVS Pharmacy', 'Dental Clinic', 'Doctor Office', 'Walgreens'],
        'Travel': ['Marriott Hotel', 'Airbnb', 'Delta Airlines', 'Rental Car'],
        'Education': ['Online Course', 'Bookstore', 'Training Workshop'],
        'Other': ['Miscellaneous Store', 'Unknown Merchant']
    }

    print(f"Creating {num_expenses} sample expenses...")

    expenses = []
    for i in range(num_expenses):
        # Random date within last 60 days
        days_ago = random.randint(0, 60)
        date = (datetime.utcnow() - timedelta(days=days_ago)).strftime('%Y-%m-%d')

        # Random category
        category = random.choice(VALID_CATEGORIES)

        # Random merchant from category
        merchant = random.choice(merchants.get(category, merchants['Other']))

        # Random amount
        amount = round(random.uniform(5.0, 200.0), 2)

        expense = {
            'user_id': user_id,
            'expense_id': str(uuid.uuid4()),
            'amount': Decimal(str(amount)),
            'merchant': merchant,
            'category': category,
            'date': date,
            'items': [],
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'confidence_score': Decimal(str(random.uniform(80.0, 99.0)))
        }

        expenses.append(expense)

    # Batch write expenses
    with table.batch_writer() as batch:
        for expense in expenses:
            batch.put_item(Item=expense)

    print(f"Created {len(expenses)} expenses")
    return expenses


def seed_budgets(dynamodb, table_name, user_id):
    """Seed sample budgets."""
    table = dynamodb.Table(table_name)

    budgets_data = [
        {'category': 'Food & Dining', 'amount': 500, 'period': 'monthly'},
        {'category': 'Groceries', 'amount': 400, 'period': 'monthly'},
        {'category': 'Transportation', 'amount': 200, 'period': 'monthly'},
        {'category': 'Shopping', 'amount': 300, 'period': 'monthly'},
        {'category': 'Entertainment', 'amount': 150, 'period': 'monthly'}
    ]

    print(f"Creating {len(budgets_data)} sample budgets...")

    budgets = []
    for budget_data in budgets_data:
        budget = {
            'user_id': user_id,
            'budget_id': str(uuid.uuid4()),
            'category': budget_data['category'],
            'amount': Decimal(str(budget_data['amount'])),
            'period': budget_data['period'],
            'alert_threshold': 90,
            'is_active': True,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }

        budgets.append(budget)

    # Batch write budgets
    with table.batch_writer() as batch:
        for budget in budgets:
            batch.put_item(Item=budget)

    print(f"Created {len(budgets)} budgets")
    return budgets


def main():
    """Main function."""
    print("=" * 50)
    print("Expense Tracker - Seed Data Script")
    print("=" * 50)

    # Get stack name
    stack_name = input("Enter stack name (default: expense-tracker-aws): ").strip()
    if not stack_name:
        stack_name = 'expense-tracker-aws'

    # Get table names
    print("\nGetting table names from CloudFormation...")
    table_names = get_table_names_from_stack(stack_name)

    print("\nTable names:")
    for key, value in table_names.items():
        print(f"  {key}: {value}")

    # Get user ID
    user_id = input("\nEnter user ID (Cognito sub) to seed data for: ").strip()
    if not user_id:
        print("Error: User ID is required")
        sys.exit(1)

    # Get number of expenses
    num_expenses = input("Enter number of expenses to create (default: 50): ").strip()
    num_expenses = int(num_expenses) if num_expenses else 50

    # Connect to DynamoDB
    print("\nConnecting to DynamoDB...")
    dynamodb = boto3.resource('dynamodb')

    # Seed expenses
    print("\nSeeding expenses...")
    expenses = seed_expenses(dynamodb, table_names['expenses'], user_id, num_expenses)

    # Seed budgets
    print("\nSeeding budgets...")
    budgets = seed_budgets(dynamodb, table_names['budgets'], user_id)

    print("\n" + "=" * 50)
    print("Data seeding complete!")
    print("=" * 50)
    print(f"\nCreated:")
    print(f"  - {len(expenses)} expenses")
    print(f"  - {len(budgets)} budgets")
    print(f"\nFor user: {user_id}")


if __name__ == '__main__':
    main()
