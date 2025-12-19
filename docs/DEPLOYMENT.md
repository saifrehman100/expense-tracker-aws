# Deployment Guide

Comprehensive guide for deploying the Smart Expense Tracker to AWS.

## Prerequisites

### Required Tools

- **AWS CLI** (v2.0+)
  ```bash
  aws --version
  ```

- **AWS SAM CLI** (v1.100+)
  ```bash
  sam --version
  ```

- **Python** (3.11+)
  ```bash
  python3 --version
  ```

- **Docker** (for local testing)
  ```bash
  docker --version
  ```

### AWS Account Setup

1. **Create AWS Account**: https://aws.amazon.com/
2. **Create IAM User**: With AdministratorAccess (for deployment)
3. **Configure AWS CLI**:
   ```bash
   aws configure
   # Enter: Access Key, Secret Key, Region, Output format
   ```

## Initial Deployment

### Step 1: Clone and Setup

```bash
# Clone repository
git clone <repository-url>
cd expense-tracker-aws

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### Step 2: Configure Environment

Edit `.env` file with your settings:

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# SES Configuration
SES_SENDER_EMAIL=noreply@yourdomain.com
```

### Step 3: Build Application

```bash
sam build
```

This creates:
- `.aws-sam/build/` directory with built artifacts
- Packaged Lambda functions
- Dependency layers

### Step 4: Deploy with Guided Setup

```bash
sam deploy --guided
```

Answer the prompts:

```
Stack Name [expense-tracker-aws]: expense-tracker-aws
AWS Region [us-east-1]: us-east-1
Parameter Environment [dev]: dev
Parameter SenderEmail [noreply@example.com]: your-email@domain.com
Confirm changes before deploy [Y/n]: Y
Allow SAM CLI IAM role creation [Y/n]: Y
Disable rollback [y/N]: N
Save arguments to configuration file [Y/n]: Y
SAM configuration file [samconfig.toml]:
SAM configuration environment [default]: default
```

Deployment takes ~10-15 minutes.

### Step 5: Post-Deployment Configuration

#### Setup Cognito

```bash
./scripts/setup_cognito.sh expense-tracker-aws
```

Follow prompts to create test user (optional).

#### Verify SES Email

```bash
./scripts/setup_ses.sh your-email@domain.com
```

Check your email and click verification link.

#### Get API URL

```bash
aws cloudformation describe-stacks \
  --stack-name expense-tracker-aws \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text
```

## Environment-Specific Deployments

### Development

```bash
sam build && sam deploy --config-env dev
```

### Staging

```bash
sam build && sam deploy --config-env staging \
  --parameter-overrides Environment=staging
```

### Production

```bash
sam build && sam deploy --config-env prod \
  --parameter-overrides Environment=prod
```

## Manual Deployment Steps

### Without Guided Deployment

```bash
# Build
sam build

# Deploy
sam deploy \
  --stack-name expense-tracker-aws-prod \
  --s3-bucket your-deployment-bucket \
  --s3-prefix expense-tracker \
  --region us-east-1 \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      Environment=prod \
      SenderEmail=noreply@yourdomain.com
```

## Updating Deployment

### Update Code

```bash
# Make code changes
# Then rebuild and deploy
sam build && sam deploy
```

### Update Configuration Only

```bash
sam deploy \
  --parameter-overrides \
      SenderEmail=new-email@domain.com
```

### Update Infrastructure

Modify `template.yaml`, then:

```bash
sam build && sam deploy
```

SAM will create a CloudFormation change set showing what will change.

## CI/CD Deployment

### GitHub Actions

The included workflow (`.github/workflows/deploy.yml`) automates deployment.

#### Setup Secrets

Add to GitHub repository secrets:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `SES_SENDER_EMAIL`

#### Trigger Deployment

```bash
# Push to main branch
git push origin main

# Or manually trigger via GitHub Actions UI
```

### GitLab CI/CD

Example `.gitlab-ci.yml`:

```yaml
stages:
  - build
  - deploy

build:
  stage: build
  image: python:3.11
  script:
    - pip install aws-sam-cli
    - sam build
  artifacts:
    paths:
      - .aws-sam/

deploy:
  stage: deploy
  image: python:3.11
  script:
    - pip install aws-sam-cli
    - sam deploy --no-confirm-changeset --no-fail-on-empty-changeset
  only:
    - main
```

## Rollback

### Automatic Rollback

CloudFormation automatically rolls back on deployment failure.

### Manual Rollback

```bash
# List stack events
aws cloudformation describe-stack-events \
  --stack-name expense-tracker-aws \
  --max-items 10

# Rollback to previous version
aws cloudformation cancel-update-stack \
  --stack-name expense-tracker-aws
```

### Point-in-Time Recovery

For data recovery:

```bash
# DynamoDB table recovery
aws dynamodb restore-table-to-point-in-time \
  --source-table-name expense-tracker-expenses \
  --target-table-name expense-tracker-expenses-restored \
  --restore-date-time 2024-01-15T10:00:00Z
```

## Monitoring Deployment

### CloudFormation Events

```bash
# Watch stack events
sam deploy --no-execute-changeset

# Then in another terminal
aws cloudformation describe-stack-events \
  --stack-name expense-tracker-aws
```

### Deployment Logs

```bash
# View Lambda logs during deployment
sam logs -n ExpenseFunction --tail
```

## Troubleshooting

### Common Issues

**Issue**: `Unable to upload artifact ... AccessDenied`
- **Solution**: Ensure IAM user has S3 permissions

**Issue**: `Stack ... is in ROLLBACK_COMPLETE state`
- **Solution**: Delete stack and redeploy
  ```bash
  aws cloudformation delete-stack --stack-name expense-tracker-aws
  ```

**Issue**: `Resource ... already exists`
- **Solution**: Use different stack name or delete existing resource

**Issue**: `Insufficient permissions`
- **Solution**: Ensure IAM user has required permissions

### Debug Mode

```bash
# Enable SAM debug logging
sam deploy --debug
```

### Validate Template

```bash
# Validate SAM template
sam validate

# Validate CloudFormation template
aws cloudformation validate-template \
  --template-body file://template.yaml
```

## Cost Optimization

### Estimate Costs

Use AWS Pricing Calculator: https://calculator.aws/

Expected costs for moderate usage:
- Lambda: $0.20-2.00/month
- DynamoDB: $2.50-10.00/month
- S3: $0.50-2.00/month
- Textract: $1.50-15.00/month
- API Gateway: $0.10-1.00/month

**Total**: ~$5-30/month

### Reduce Costs

1. **Use Free Tier**:
   - Lambda: 1M requests/month free
   - DynamoDB: 25GB storage free
   - S3: 5GB storage free

2. **Optimize Lambda**:
   - Right-size memory allocation
   - Reduce timeout values
   - Use ARM processors (Graviton2)

3. **DynamoDB**:
   - Use on-demand for dev/staging
   - Use provisioned for production (if predictable)

4. **S3 Lifecycle**:
   - Glacier archive after 1 year
   - Delete after 7 years

## Security Best Practices

### IAM Roles

- Use separate roles for each Lambda
- Follow least privilege principle
- Enable IAM Access Analyzer

### Secrets Management

- Use AWS Secrets Manager for sensitive data
- Rotate secrets regularly
- Never commit secrets to git

### Network Security

- Consider VPC for Lambda functions
- Use VPC endpoints for AWS services
- Enable WAF for API Gateway

## Backup Strategy

### Automated Backups

- DynamoDB: Point-in-time recovery (enabled)
- S3: Versioning (enabled)
- CloudFormation: Template in source control

### Manual Backup

```bash
# Export DynamoDB table
aws dynamodb scan --table-name expense-tracker-expenses \
  > backup-expenses.json

# Sync S3 bucket
aws s3 sync s3://expense-tracker-receipts ./backup-receipts
```

## Disaster Recovery

### Multi-Region Deployment

For high availability, deploy to multiple regions:

```bash
# Deploy to us-east-1
sam deploy --region us-east-1 --stack-name expense-tracker-us-east-1

# Deploy to us-west-2
sam deploy --region us-west-2 --stack-name expense-tracker-us-west-2
```

Then use Route 53 for failover.

### Recovery Procedure

1. **Identify Issue**: Check CloudWatch alarms
2. **Assess Impact**: Review error logs
3. **Execute Recovery**:
   - Rollback deployment, or
   - Restore from backup, or
   - Redeploy from source
4. **Verify**: Run smoke tests
5. **Document**: Create incident report

## Production Checklist

Before deploying to production:

- [ ] All environment variables configured
- [ ] SES email verified
- [ ] Cognito user pool configured
- [ ] DynamoDB backup enabled
- [ ] CloudWatch alarms set up
- [ ] Cost alerts configured
- [ ] Security review completed
- [ ] Load testing performed
- [ ] Runbook documented
- [ ] Team trained on operations

## Support

For deployment issues:
- AWS Support: https://console.aws.amazon.com/support
- SAM Documentation: https://docs.aws.amazon.com/serverless-application-model/
- GitHub Issues: <repository-url>/issues
