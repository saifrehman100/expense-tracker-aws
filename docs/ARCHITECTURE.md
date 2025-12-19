# Architecture Overview

## System Architecture

The Smart Expense Tracker is built using AWS serverless architecture with event-driven microservices.

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   Client    │────▶│ API Gateway │────▶│  Lambda Auth    │
└─────────────┘     └─────────────┘     │  (Cognito)      │
                                        └────────┬────────┘
                                                 │
┌────────────────────────────────────────────────┼────────────────────────────────────┐
│                                                │                                    │
▼                                                ▼                                    ▼
┌───────────────┐                      ┌─────────────────┐                  ┌─────────────────┐
│ Receipt Upload│                      │ Expense Service │                  │ Report Service  │
│ Service       │                      │                 │                  │                 │
│ (Lambda)      │                      │ (Lambda)        │                  │ (Lambda)        │
└───────┬───────┘                      └────────┬────────┘                  └────────┬────────┘
        │                                       │                                     │
        ▼                                       ▼                                     ▼
┌───────────────┐                      ┌─────────────────┐                  ┌─────────────────┐
│      S3       │───────▶ Trigger ───▶ │    Textract     │                  │      SES        │
│ (Receipts)    │                      │   Processing    │                  │ (Email Reports) │
└───────────────┘                      │    (Lambda)     │                  └─────────────────┘
                                       └────────┬────────┘
                                                │
                                                ▼
                                       ┌─────────────────┐
                                       │   Comprehend    │
                                       │ (Categorize)    │
                                       └────────┬────────┘
                                                │
                                                ▼
                                       ┌─────────────────┐
                                       │   DynamoDB      │
                                       │ (Expenses DB)   │
                                       └─────────────────┘
```

## Components

### API Layer

#### API Gateway
- REST API with Cognito authorizer
- CORS enabled for cross-origin requests
- Request validation and throttling
- Custom domain support ready

#### Authentication
- AWS Cognito User Pool for user management
- JWT-based authentication
- Email verification workflow
- Password policy enforcement

### Compute Layer

#### Lambda Functions

**Auth Function** (256MB, 30s timeout)
- User registration and login
- Token management
- Integration with Cognito

**Receipt Upload Function** (512MB, 30s timeout)
- Receipt image upload to S3
- Metadata storage in DynamoDB
- Presigned URL generation

**OCR Processor Function** (1024MB, 60s timeout)
- Event-driven (S3 trigger)
- Textract integration for OCR
- Comprehend integration for categorization
- Expense record creation

**Expense Function** (256MB, 30s timeout)
- CRUD operations for expenses
- Advanced querying and filtering
- Summary and analytics

**Budget Function** (256MB, 30s timeout)
- Budget management
- Spending tracking
- Alert threshold monitoring

**Report Function** (512MB, 60s timeout)
- Report generation (weekly/monthly)
- CSV export
- Email delivery via SES

### Storage Layer

#### S3 Buckets

**Receipts Bucket**
- Encrypted storage (AES256)
- Versioning enabled
- Lifecycle policy (7-year retention)
- Event notifications for OCR processing

#### DynamoDB Tables

**Users Table**
```
Primary Key: user_id (String)
GSI: email-index (email)
```

**Receipts Table**
```
Primary Key: user_id (String)
Sort Key: receipt_id (String)
```

**Expenses Table**
```
Primary Key: user_id (String)
Sort Key: expense_id (String)
GSI1: user-date-index (user_id, date)
GSI2: user-category-index (user_id, category)
```

**Budgets Table**
```
Primary Key: user_id (String)
Sort Key: budget_id (String)
```

### AI/ML Services

#### AWS Textract
- AnalyzeExpense API for receipt processing
- Extracts: merchant, total, tax, items, date
- Confidence scoring for data quality

#### AWS Comprehend
- Entity detection for merchant recognition
- Custom categorization logic
- Keyword-based fallback for reliability

### Communication

#### AWS SES
- Transactional emails (reports)
- Budget alert notifications
- HTML and text email support
- Sender verification required

## Data Flow

### Receipt Processing Flow

1. **Upload**
   - Client uploads base64-encoded image
   - Receipt Upload Lambda validates and stores in S3
   - Creates receipt record in DynamoDB (status: pending)

2. **OCR Processing**
   - S3 event triggers OCR Processor Lambda
   - Textract analyzes receipt image
   - Extracts merchant, amounts, date, items

3. **Categorization**
   - Comprehend analyzes merchant name
   - Keyword matching for fallback
   - Assigns category with confidence score

4. **Storage**
   - Creates expense record in DynamoDB
   - Updates receipt status (pending → processed)
   - Links expense to receipt

### Query Flow

1. **Request**
   - Client sends authenticated request
   - API Gateway validates JWT token
   - Routes to appropriate Lambda

2. **Processing**
   - Lambda queries DynamoDB
   - Uses GSI for efficient filtering
   - Paginates large result sets

3. **Response**
   - Standardized JSON response
   - Includes pagination tokens
   - Presigned URLs for S3 objects

### Report Generation Flow

1. **Data Collection**
   - Query expenses for date range
   - Aggregate by category and merchant
   - Calculate statistics

2. **Formatting**
   - Generate HTML/CSV report
   - Include charts and summaries
   - Brand with application styling

3. **Delivery**
   - Send via SES (for email reports)
   - Return CSV directly (for exports)
   - Store in user's account

## Security Architecture

### Authentication & Authorization

- **Cognito User Pool**: Centralized user management
- **JWT Tokens**: Stateless authentication
- **API Gateway Authorizer**: Automatic token validation
- **User Isolation**: All queries filtered by user_id

### Data Protection

- **Encryption at Rest**:
  - S3: AES-256
  - DynamoDB: AWS-managed keys

- **Encryption in Transit**:
  - HTTPS only (TLS 1.2+)
  - API Gateway enforced

- **Access Control**:
  - IAM roles with least privilege
  - Resource-based policies
  - VPC endpoints (optional)

### Data Privacy

- **User Data Isolation**: Partition key filtering
- **Receipt Retention**: Configurable lifecycle
- **Personal Data**: GDPR-compliant design
- **Audit Logs**: CloudWatch Logs retention

## Scalability

### Horizontal Scaling

- **Lambda**: Auto-scales to demand
- **API Gateway**: Handles thousands of concurrent requests
- **DynamoDB**: On-demand pricing, auto-scaling
- **S3**: Unlimited storage capacity

### Performance Optimization

- **DynamoDB GSIs**: Optimized query patterns
- **Lambda Layers**: Shared dependencies
- **Connection Pooling**: Reuse boto3 clients
- **Pagination**: Large result set handling

### Cost Optimization

- **On-Demand Pricing**: Pay only for usage
- **Lambda Right-Sizing**: Memory optimization
- **S3 Lifecycle**: Archive old receipts
- **Reserved Capacity**: For predictable workloads (optional)

## Monitoring & Observability

### CloudWatch Logs

- Structured JSON logging
- Log retention: 30 days (configurable)
- Log groups per Lambda function
- Correlation IDs for tracing

### X-Ray Tracing

- End-to-end request tracing
- Service map visualization
- Performance bottleneck identification
- Error rate tracking

### Application Insights

- Automated setup
- Anomaly detection
- Performance metrics
- Resource health monitoring

### Key Metrics

- **API Metrics**:
  - Request count
  - Latency (p50, p95, p99)
  - Error rate
  - Throttling

- **Lambda Metrics**:
  - Invocation count
  - Duration
  - Error count
  - Concurrent executions

- **DynamoDB Metrics**:
  - Read/write capacity
  - Throttled requests
  - Latency

## Disaster Recovery

### Backup Strategy

- **DynamoDB**: Point-in-time recovery enabled
- **S3**: Versioning enabled
- **Configuration**: Infrastructure as Code (SAM)

### Recovery Time Objective (RTO)

- **Application**: < 1 hour (redeploy from SAM)
- **Data**: < 15 minutes (DynamoDB PITR)

### Recovery Point Objective (RPO)

- **DynamoDB**: 5 seconds (PITR)
- **S3**: 0 seconds (versioning)

## Future Enhancements

### Planned Features

- **Multi-currency Support**: Currency conversion
- **Recurring Expenses**: Subscription tracking
- **Receipt Splitting**: Share expenses
- **Mobile App**: React Native client
- **Advanced Analytics**: ML-powered insights

### Architecture Evolution

- **Event Sourcing**: For audit trail
- **CQRS**: Separate read/write models
- **GraphQL**: Flexible querying
- **WebSockets**: Real-time updates
- **CDN**: Static asset delivery
