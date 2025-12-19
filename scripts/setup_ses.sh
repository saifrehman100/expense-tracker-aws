#!/bin/bash

# Setup script for AWS SES (Simple Email Service)
# This script verifies the sender email address for SES

set -e

echo "======================================"
echo "AWS SES Setup"
echo "======================================"

# Get sender email from user or environment
SENDER_EMAIL="${1:-${SES_SENDER_EMAIL}}"

if [ -z "$SENDER_EMAIL" ]; then
    read -p "Enter the sender email address to verify: " SENDER_EMAIL
fi

echo "Sender email: $SENDER_EMAIL"

# Get AWS region
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "AWS Region: $AWS_REGION"

# Verify email address
echo "Sending verification email to $SENDER_EMAIL..."

aws ses verify-email-identity \
    --email-address "$SENDER_EMAIL" \
    --region "$AWS_REGION"

echo ""
echo "======================================"
echo "Verification email sent!"
echo "======================================"
echo ""
echo "IMPORTANT: Please check your email ($SENDER_EMAIL) and click the verification link."
echo "The email should arrive within a few minutes."
echo ""
echo "You can check the verification status with:"
echo "  aws ses get-identity-verification-attributes --identities $SENDER_EMAIL --region $AWS_REGION"
echo ""

# Wait and check verification status
read -p "Press Enter to check verification status (or Ctrl+C to exit)..."

aws ses get-identity-verification-attributes \
    --identities "$SENDER_EMAIL" \
    --region "$AWS_REGION" \
    --output table

echo ""
echo "If the status shows 'Success', your email is verified and ready to use!"
echo "If the status shows 'Pending', please click the verification link in your email."
