#!/bin/bash

# Setup script for AWS Cognito User Pool
# This script should be run after deploying the SAM application

set -e

echo "======================================"
echo "Cognito User Pool Setup"
echo "======================================"

# Get stack name from user or use default
STACK_NAME="${1:-expense-tracker-aws}"

echo "Getting Cognito User Pool information from stack: $STACK_NAME"

# Get User Pool ID and Client ID from CloudFormation outputs
USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" \
    --output text)

CLIENT_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" \
    --output text)

if [ -z "$USER_POOL_ID" ] || [ -z "$CLIENT_ID" ]; then
    echo "Error: Could not retrieve Cognito information from CloudFormation stack"
    exit 1
fi

echo "User Pool ID: $USER_POOL_ID"
echo "Client ID: $CLIENT_ID"

# Update .env file if it exists
if [ -f .env ]; then
    echo "Updating .env file with Cognito information..."
    sed -i.bak "s/COGNITO_USER_POOL_ID=.*/COGNITO_USER_POOL_ID=$USER_POOL_ID/" .env
    sed -i.bak "s/COGNITO_CLIENT_ID=.*/COGNITO_CLIENT_ID=$CLIENT_ID/" .env
    rm .env.bak
    echo ".env file updated"
fi

# Create a test user (optional)
read -p "Do you want to create a test user? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter test user email: " TEST_EMAIL
    read -sp "Enter test user password (min 8 chars, must include uppercase, lowercase, number, special char): " TEST_PASSWORD
    echo
    read -p "Enter test user name: " TEST_NAME

    echo "Creating test user..."

    aws cognito-idp admin-create-user \
        --user-pool-id "$USER_POOL_ID" \
        --username "$TEST_EMAIL" \
        --user-attributes \
            Name=email,Value="$TEST_EMAIL" \
            Name=email_verified,Value=true \
            Name=name,Value="$TEST_NAME" \
        --temporary-password "$TEST_PASSWORD" \
        --message-action SUPPRESS

    aws cognito-idp admin-set-user-password \
        --user-pool-id "$USER_POOL_ID" \
        --username "$TEST_EMAIL" \
        --password "$TEST_PASSWORD" \
        --permanent

    echo "Test user created successfully!"
    echo "Email: $TEST_EMAIL"
fi

echo "======================================"
echo "Cognito setup complete!"
echo "======================================"
