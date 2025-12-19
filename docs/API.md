# API Documentation

Complete API reference for the Smart Expense Tracker application.

## Base URL

```
https://<api-id>.execute-api.<region>.amazonaws.com/Prod
```

Get your API URL from CloudFormation outputs after deployment.

## Authentication

All endpoints (except auth endpoints) require authentication using AWS Cognito JWT tokens.

### Headers

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

## Response Format

### Success Response

```json
{
  "success": true,
  "data": { ... },
  "message": "Optional success message"
}
```

### Error Response

```json
{
  "success": false,
  "error": {
    "message": "Error description",
    "code": "ERROR_CODE",
    "details": { ... }
  }
}
```

## Authentication Endpoints

### Register User

Create a new user account.

**Endpoint:** `POST /auth/register`

**No Authentication Required**

**Request Body:**

```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "name": "John Doe"
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "user_id": "uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "user_confirmed": false
  },
  "message": "User registered successfully. Please check your email to confirm your account."
}
```

### Login

Authenticate and receive JWT tokens.

**Endpoint:** `POST /auth/login`

**No Authentication Required**

**Request Body:**

```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "user": {
      "user_id": "uuid",
      "email": "user@example.com",
      "name": "John Doe"
    },
    "tokens": {
      "access_token": "eyJra...",
      "id_token": "eyJra...",
      "refresh_token": "eyJra...",
      "expires_in": 3600,
      "token_type": "Bearer"
    }
  },
  "message": "Login successful"
}
```

### Refresh Token

Refresh expired access token.

**Endpoint:** `POST /auth/refresh`

**No Authentication Required**

**Request Body:**

```json
{
  "refresh_token": "eyJra..."
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "tokens": {
      "access_token": "eyJra...",
      "id_token": "eyJra...",
      "expires_in": 3600,
      "token_type": "Bearer"
    }
  }
}
```

## Receipt Endpoints

### Upload Receipt

Upload a receipt image for processing.

**Endpoint:** `POST /receipts/upload`

**Authentication Required**

**Request Body:**

```json
{
  "image_data": "base64_encoded_image_data",
  "filename": "receipt.jpg",
  "content_type": "image/jpeg"
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "user_id": "uuid",
    "receipt_id": "uuid",
    "s3_key": "receipts/user_id/receipt_id.jpg",
    "filename": "receipt.jpg",
    "status": "pending",
    "uploaded_at": "2024-01-15T10:00:00Z"
  },
  "message": "Receipt uploaded successfully. Processing will begin shortly."
}
```

### List Receipts

Get list of user's receipts.

**Endpoint:** `GET /receipts`

**Authentication Required**

**Query Parameters:**

- `limit` (optional): Number of results (default: 50, max: 100)
- `last_key` (optional): Pagination key from previous response

**Response:**

```json
{
  "success": true,
  "data": {
    "receipts": [
      {
        "receipt_id": "uuid",
        "filename": "receipt.jpg",
        "status": "processed",
        "uploaded_at": "2024-01-15T10:00:00Z",
        "processed_at": "2024-01-15T10:01:00Z",
        "image_url": "https://..."
      }
    ],
    "count": 10,
    "last_key": "..."
  }
}
```

### Get Receipt Details

Get details of a specific receipt.

**Endpoint:** `GET /receipts/{id}`

**Authentication Required**

**Response:**

```json
{
  "success": true,
  "data": {
    "receipt_id": "uuid",
    "filename": "receipt.jpg",
    "status": "processed",
    "uploaded_at": "2024-01-15T10:00:00Z",
    "processed_at": "2024-01-15T10:01:00Z",
    "expense_id": "uuid",
    "image_url": "https://..."
  }
}
```

### Delete Receipt

Delete a receipt.

**Endpoint:** `DELETE /receipts/{id}`

**Authentication Required**

**Response:**

```json
{
  "success": true,
  "message": "Receipt deleted successfully"
}
```

## Expense Endpoints

### List Expenses

Get list of expenses with optional filters.

**Endpoint:** `GET /expenses`

**Authentication Required**

**Query Parameters:**

- `category` (optional): Filter by category
- `start_date` (optional): Start date (YYYY-MM-DD)
- `end_date` (optional): End date (YYYY-MM-DD)
- `limit` (optional): Number of results (default: 50, max: 100)
- `last_key` (optional): Pagination key

**Response:**

```json
{
  "success": true,
  "data": {
    "expenses": [
      {
        "expense_id": "uuid",
        "amount": 45.67,
        "merchant": "Walmart",
        "category": "Groceries",
        "date": "2024-01-15",
        "receipt_url": "https://...",
        "created_at": "2024-01-15T10:00:00Z"
      }
    ],
    "count": 10,
    "last_key": "..."
  }
}
```

### Get Expense Details

Get details of a specific expense.

**Endpoint:** `GET /expenses/{id}`

**Authentication Required**

**Response:**

```json
{
  "success": true,
  "data": {
    "expense_id": "uuid",
    "amount": 45.67,
    "merchant": "Walmart",
    "category": "Groceries",
    "date": "2024-01-15",
    "items": [
      {
        "description": "Bananas",
        "quantity": 2,
        "price": 1.50,
        "amount": 3.00
      }
    ],
    "receipt_url": "https://...",
    "confidence_score": 95.5,
    "created_at": "2024-01-15T10:00:00Z"
  }
}
```

### Update Expense

Update expense details.

**Endpoint:** `PUT /expenses/{id}`

**Authentication Required**

**Request Body:**

```json
{
  "amount": 50.00,
  "merchant": "Updated Merchant",
  "category": "Food & Dining",
  "date": "2024-01-16",
  "notes": "Manual correction"
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "expense_id": "uuid",
    "amount": 50.00,
    "merchant": "Updated Merchant",
    "category": "Food & Dining",
    "updated_at": "2024-01-16T10:00:00Z"
  },
  "message": "Expense updated successfully"
}
```

### Delete Expense

Delete an expense.

**Endpoint:** `DELETE /expenses/{id}`

**Authentication Required**

**Response:**

```json
{
  "success": true,
  "message": "Expense deleted successfully"
}
```

### Get Expense Summary

Get spending summary with statistics.

**Endpoint:** `GET /expenses/summary`

**Authentication Required**

**Query Parameters:**

- `start_date` (optional): Start date (YYYY-MM-DD)
- `end_date` (optional): End date (YYYY-MM-DD)

**Response:**

```json
{
  "success": true,
  "data": {
    "total_amount": 1250.50,
    "expense_count": 45,
    "average_expense": 27.79,
    "by_category": {
      "Groceries": 450.00,
      "Food & Dining": 350.50,
      "Transportation": 450.00
    },
    "by_month": {
      "2024-01": 1250.50
    },
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }
}
```

## Budget Endpoints

### Create Budget

Create a new budget.

**Endpoint:** `POST /budgets`

**Authentication Required**

**Request Body:**

```json
{
  "category": "Groceries",
  "amount": 500.00,
  "period": "monthly",
  "alert_threshold": 90
}
```

**Valid Periods:** `weekly`, `monthly`

**Response:**

```json
{
  "success": true,
  "data": {
    "budget_id": "uuid",
    "category": "Groceries",
    "amount": 500.00,
    "period": "monthly",
    "alert_threshold": 90,
    "is_active": true,
    "created_at": "2024-01-15T10:00:00Z"
  },
  "message": "Budget created successfully"
}
```

### List Budgets

Get list of budgets.

**Endpoint:** `GET /budgets`

**Authentication Required**

**Query Parameters:**

- `active_only` (optional): Only return active budgets (default: true)

**Response:**

```json
{
  "success": true,
  "data": {
    "budgets": [
      {
        "budget_id": "uuid",
        "category": "Groceries",
        "amount": 500.00,
        "period": "monthly",
        "current_spending": 350.00,
        "percentage_used": 70.0,
        "is_over_budget": false,
        "should_alert": false
      }
    ],
    "count": 5
  }
}
```

### Update Budget

Update budget details.

**Endpoint:** `PUT /budgets/{id}`

**Authentication Required**

**Request Body:**

```json
{
  "amount": 600.00,
  "alert_threshold": 85
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "budget_id": "uuid",
    "amount": 600.00,
    "alert_threshold": 85,
    "updated_at": "2024-01-16T10:00:00Z"
  },
  "message": "Budget updated successfully"
}
```

### Delete Budget

Delete (deactivate) a budget.

**Endpoint:** `DELETE /budgets/{id}`

**Authentication Required**

**Response:**

```json
{
  "success": true,
  "message": "Budget deleted successfully"
}
```

## Report Endpoints

### Get Weekly Report

Generate weekly expense report.

**Endpoint:** `GET /reports/weekly`

**Authentication Required**

**Response:**

```json
{
  "success": true,
  "data": {
    "report_type": "weekly",
    "start_date": "2024-01-08",
    "end_date": "2024-01-15",
    "summary": {
      "total_amount": 450.00,
      "expense_count": 15,
      "average_expense": 30.00,
      "average_daily": 64.29
    },
    "by_category": {
      "Groceries": {
        "amount": 200.00,
        "count": 5,
        "percentage": 44.4
      }
    },
    "top_merchants": [
      {
        "name": "Walmart",
        "amount": 150.00,
        "count": 3
      }
    ]
  }
}
```

### Get Monthly Report

Generate monthly expense report.

**Endpoint:** `GET /reports/monthly`

**Authentication Required**

**Response:** Same format as weekly report

### Email Report

Send report to user's email.

**Endpoint:** `POST /reports/email`

**Authentication Required**

**Request Body:**

```json
{
  "report_type": "monthly"
}
```

**Valid Report Types:** `weekly`, `monthly`

**Response:**

```json
{
  "success": true,
  "data": {
    "message_id": "ses-message-id",
    "recipient": "user@example.com",
    "report_type": "monthly"
  },
  "message": "Monthly report sent to user@example.com"
}
```

### Export Expenses

Export expenses as CSV.

**Endpoint:** `GET /reports/export`

**Authentication Required**

**Query Parameters:**

- `start_date` (required): Start date (YYYY-MM-DD)
- `end_date` (required): End date (YYYY-MM-DD)

**Response:** CSV file download

## Valid Categories

- Food & Dining
- Transportation
- Shopping
- Entertainment
- Utilities
- Healthcare
- Travel
- Education
- Groceries
- Other

## Error Codes

- `VALIDATION_ERROR` (400): Invalid input data
- `UNAUTHORIZED` (401): Missing or invalid authentication
- `FORBIDDEN` (403): Insufficient permissions
- `NOT_FOUND` (404): Resource not found
- `ERROR_500` (500): Internal server error

## Rate Limits

API Gateway throttling:
- Burst: 5000 requests
- Rate: 10000 requests per second

## Examples

See the [examples](../examples/) directory for code samples in various languages.
