# Smart Expense Tracker with Receipt OCR

A production-ready serverless expense tracking application built on AWS with automated receipt processing using OCR and AI.

## Features

- **Receipt OCR**: Automatically extract expense data from receipt images using AWS Textract
- **Smart Categorization**: AI-powered expense categorization using AWS Comprehend
- **Budget Management**: Set budgets and receive alerts when approaching limits
- **Expense Reports**: Generate weekly/monthly reports with email delivery
- **User Authentication**: Secure authentication using AWS Cognito
- **REST API**: Full-featured API for expense management
- **CSV Export**: Export expenses for external analysis

## Architecture

Built using AWS serverless architecture:
- **Lambda**: Serverless compute for all business logic
- **API Gateway**: RESTful API endpoints
- **DynamoDB**: NoSQL database for expenses, budgets, and receipts
- **S3**: Object storage for receipt images
- **Cognito**: User authentication and authorization
- **Textract**: OCR for receipt processing
- **Comprehend**: AI-powered categorization
- **SES**: Email notifications and reports

## Prerequisites

- AWS Account
- AWS CLI configured
- AWS SAM CLI installed
- Python 3.11+
- Docker (for local testing)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Build and Deploy

```bash
# Build the application
sam build

# Deploy with guided deployment
sam deploy --guided
```

### 4. Post-Deployment Setup

```bash
# Setup Cognito User Pool
./scripts/setup_cognito.sh

# Verify SES Email
./scripts/setup_ses.sh your-email@example.com

# Seed Test Data (Optional)
python3 ./scripts/seed_data.py
```

## API Documentation

See [docs/API.md](docs/API.md) for complete API reference.

## Local Development

```bash
# Start LocalStack
cd local && docker-compose up -d

# Run tests
pytest --cov=src

# Start API locally
sam local start-api
```

## Project Structure

```
expense-tracker-aws/
├── src/                      # Source code
│   ├── auth/                 # Authentication service
│   ├── receipts/             # Receipt upload service
│   ├── ocr_processor/        # OCR processing service
│   ├── expenses/             # Expense management service
│   ├── budgets/              # Budget management service
│   ├── reports/              # Report generation service
│   └── shared/               # Shared utilities
├── tests/                    # Test files
├── scripts/                  # Setup scripts
├── local/                    # Local development
├── docs/                     # Documentation
├── template.yaml             # SAM template
└── requirements.txt          # Dependencies
```

## Documentation

- [API Documentation](docs/API.md)
- [Architecture Overview](docs/ARCHITECTURE.md)
- [Deployment Guide](docs/DEPLOYMENT.md)

## License

MIT License