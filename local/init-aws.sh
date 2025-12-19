#!/bin/bash

# Initialize LocalStack AWS resources for Expense Tracker

echo "Initializing LocalStack AWS resources..."

# Wait for LocalStack to be ready
sleep 5

# Set AWS credentials for LocalStack
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

# Create S3 bucket
echo "Creating S3 bucket..."
awslocal s3 mb s3://expense-tracker-receipts

# Create DynamoDB tables
echo "Creating DynamoDB tables..."

# Users table
awslocal dynamodb create-table \
    --table-name expense-tracker-users \
    --attribute-definitions \
        AttributeName=user_id,AttributeType=S \
        AttributeName=email,AttributeType=S \
    --key-schema \
        AttributeName=user_id,KeyType=HASH \
    --global-secondary-indexes \
        "[
            {
                \"IndexName\": \"email-index\",
                \"KeySchema\": [{\"AttributeName\":\"email\",\"KeyType\":\"HASH\"}],
                \"Projection\":{\"ProjectionType\":\"ALL\"}
            }
        ]" \
    --billing-mode PAY_PER_REQUEST

# Receipts table
awslocal dynamodb create-table \
    --table-name expense-tracker-receipts \
    --attribute-definitions \
        AttributeName=user_id,AttributeType=S \
        AttributeName=receipt_id,AttributeType=S \
    --key-schema \
        AttributeName=user_id,KeyType=HASH \
        AttributeName=receipt_id,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST

# Expenses table
awslocal dynamodb create-table \
    --table-name expense-tracker-expenses \
    --attribute-definitions \
        AttributeName=user_id,AttributeType=S \
        AttributeName=expense_id,AttributeType=S \
        AttributeName=date,AttributeType=S \
        AttributeName=category,AttributeType=S \
    --key-schema \
        AttributeName=user_id,KeyType=HASH \
        AttributeName=expense_id,KeyType=RANGE \
    --global-secondary-indexes \
        "[
            {
                \"IndexName\": \"user-date-index\",
                \"KeySchema\": [
                    {\"AttributeName\":\"user_id\",\"KeyType\":\"HASH\"},
                    {\"AttributeName\":\"date\",\"KeyType\":\"RANGE\"}
                ],
                \"Projection\":{\"ProjectionType\":\"ALL\"}
            },
            {
                \"IndexName\": \"user-category-index\",
                \"KeySchema\": [
                    {\"AttributeName\":\"user_id\",\"KeyType\":\"HASH\"},
                    {\"AttributeName\":\"category\",\"KeyType\":\"RANGE\"}
                ],
                \"Projection\":{\"ProjectionType\":\"ALL\"}
            }
        ]" \
    --billing-mode PAY_PER_REQUEST

# Budgets table
awslocal dynamodb create-table \
    --table-name expense-tracker-budgets \
    --attribute-definitions \
        AttributeName=user_id,AttributeType=S \
        AttributeName=budget_id,AttributeType=S \
    --key-schema \
        AttributeName=user_id,KeyType=HASH \
        AttributeName=budget_id,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST

echo "LocalStack initialization complete!"
