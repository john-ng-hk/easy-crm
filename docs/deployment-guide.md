# Easy CRM Deployment Guide

This guide provides comprehensive instructions for deploying the Easy CRM system to AWS.

## Overview

Easy CRM uses a serverless architecture deployed on AWS with the following components:
- **CloudFormation**: Infrastructure as Code
- **Lambda**: Serverless compute functions
- **DynamoDB**: NoSQL database for lead storage
- **S3**: File storage and static website hosting
- **API Gateway**: REST API endpoints
- **Cognito**: User authentication
- **CloudFront**: CDN for global content delivery

## Prerequisites

### Required Software
- **AWS CLI v2**: [Installation Guide](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html)
- **Python 3.8+**: For Lambda function development
- **Git**: For version control

### AWS Configuration
1. **AWS Account**: Active AWS account with appropriate permissions
2. **AWS Profile**: Configured profile named `nch-prod`
3. **IAM Permissions**: Required permissions for all AWS services used
4. **DeepSeek API Key**: Valid API key for AI integration

### Required IAM Permissions
Your AWS user/role needs the following permissions:
- CloudFormation: Full access
- Lambda: Full access
- DynamoDB: Full access
- S3: Full access
- Cognito: Full access
- API Gateway: Full access
- CloudFront: Full access
- IAM: CreateRole, AttachRolePolicy, PassRole

## Environment Setup

### 1. Clone Repository
```bash
git clone <repository-url>
cd easy-crm
```

### 2. Create Python Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
pip install -r requirements.txt
```

### 3. Configure AWS Profile
```bash
aws configure --profile nch-prod
# Enter your AWS Access Key ID, Secret Access Key, and region (ap-southeast-1)
```

### 4. Validate Prerequisites
```bash
./scripts/validate-deployment.sh prod
```

## Deployment Process

### Step 1: Validate Environment
Before deploying, ensure all prerequisites are met:

```bash
# Validate deployment prerequisites
./scripts/validate-deployment.sh [environment]

# Validate CloudFormation templates
./scripts/validate-templates.sh
```

### Step 2: Deploy Infrastructure
Deploy the AWS infrastructure using CloudFormation:

```bash
# Deploy to production (default)
./scripts/deploy.sh

# Deploy to specific environment
./scripts/deploy.sh dev
./scripts/deploy.sh staging
./scripts/deploy.sh prod
```

The deployment script will:
1. Load environment-specific configuration
2. Validate prerequisites and templates
3. Create S3 bucket for CloudFormation templates
4. Upload nested templates to S3
5. Deploy the main CloudFormation stack
6. Run smoke tests to validate deployment
7. Display deployment summary and next steps

### Step 3: Deploy Lambda Functions
Package and deploy Lambda function code:

```bash
# Deploy Lambda functions
./scripts/package-lambdas.sh [environment]
```

This script will:
1. Create deployment packages for each Lambda function
2. Include shared utilities and dependencies
3. Update function code in AWS
4. Validate function status

### Step 4: Deploy Frontend
Deploy the web application to S3:

```bash
# Deploy frontend files
./scripts/deploy-frontend.sh [environment]
```

This script will:
1. Generate configuration files with actual AWS resource URLs
2. Upload HTML, CSS, and JavaScript files to S3
3. Configure proper content types and caching headers
4. Display access URLs for the application

### Step 5: Run Smoke Tests
Validate the complete deployment:

```bash
# Run comprehensive smoke tests
./scripts/smoke-tests.sh [environment]
```

## Environment-Specific Deployments

### Development Environment
```bash
./scripts/validate-deployment.sh dev
./scripts/deploy.sh dev
./scripts/package-lambdas.sh dev
./scripts/deploy-frontend.sh dev
./scripts/smoke-tests.sh dev
```

**Development Configuration:**
- Reduced resource allocations
- Shorter log retention (7 days)
- No deletion protection
- Basic monitoring

### Staging Environment
```bash
./scripts/validate-deployment.sh staging
./scripts/deploy.sh staging
./scripts/package-lambdas.sh staging
./scripts/deploy-frontend.sh staging
./scripts/smoke-tests.sh staging
```

**Staging Configuration:**
- Production-like resource allocations
- Extended log retention (14 days)
- Point-in-time recovery enabled
- Detailed monitoring enabled

### Production Environment
```bash
./scripts/validate-deployment.sh prod
./scripts/deploy.sh prod
./scripts/package-lambdas.sh prod
./scripts/deploy-frontend.sh prod
./scripts/smoke-tests.sh prod
```

**Production Configuration:**
- Full resource allocations
- Extended log retention (30 days)
- Deletion protection enabled
- Comprehensive monitoring and alerting

## Configuration Files

### Environment Configurations
Environment-specific settings are stored in `config/environments/`:

- `dev.yaml`: Development environment settings
- `staging.yaml`: Staging environment settings  
- `prod.yaml`: Production environment settings

### Deployment Configuration
Global deployment settings in `config/deployment.yaml`:
- Parameter validation rules
- Resource naming conventions
- Deployment phases
- Rollback strategies
- Security configurations

## Monitoring and Maintenance

### CloudWatch Logs
Monitor application logs:
```bash
# View Lambda function logs
aws logs tail /aws/lambda/easy-crm-file-upload-prod --follow --profile nch-prod

# View API Gateway logs
aws logs describe-log-groups --log-group-name-prefix "API-Gateway-Execution-Logs" --profile nch-prod
```

### Resource Monitoring
```bash
# Check stack status
aws cloudformation describe-stacks --stack-name easy-crm --profile nch-prod

# Monitor DynamoDB table
aws dynamodb describe-table --table-name easy-crm-leads-prod --profile nch-prod

# Check Lambda function status
aws lambda list-functions --profile nch-prod --region ap-southeast-1
```

### Cost Optimization
- Monitor AWS Cost Explorer for usage patterns
- Review DynamoDB capacity utilization
- Optimize Lambda memory allocations based on CloudWatch metrics
- Configure S3 lifecycle policies for cost savings

## Security Best Practices

### Access Control
- Use least-privilege IAM policies
- Regularly rotate API keys and credentials
- Enable MFA for AWS console access
- Monitor CloudTrail logs for suspicious activity

### Data Protection
- All data encrypted in transit and at rest
- Regular security updates for Lambda runtimes
- Input validation and sanitization
- Secure API endpoints with authentication

### Compliance
- Regular backup testing
- Data retention policy compliance
- Security audit logging
- Incident response procedures

## Troubleshooting

### Common Issues
See [Deployment Troubleshooting Guide](deployment-troubleshooting.md) for detailed troubleshooting steps.

### Quick Diagnostics
```bash
# Run smoke tests to identify issues
./scripts/smoke-tests.sh [environment]

# Check CloudFormation events
aws cloudformation describe-stack-events --stack-name easy-crm --profile nch-prod

# Validate templates
./scripts/validate-templates.sh
```

### Getting Help
1. Check CloudFormation console for detailed error messages
2. Review CloudWatch logs for application errors
3. Run validation scripts to identify configuration issues
4. Consult AWS documentation for service-specific errors

## Rollback Procedures

### Infrastructure Rollback
```bash
# Rollback to previous CloudFormation stack version
aws cloudformation cancel-update-stack --stack-name easy-crm --profile nch-prod

# Or update with previous template version
aws cloudformation update-stack \
    --stack-name easy-crm \
    --template-body file://previous-template.yaml \
    --profile nch-prod
```

### Lambda Function Rollback
```bash
# Rollback to previous function version
aws lambda update-function-code \
    --function-name easy-crm-file-upload-prod \
    --zip-file fileb://previous-version.zip \
    --profile nch-prod
```

### Frontend Rollback
```bash
# Restore previous frontend version from backup
aws s3 sync s3://backup-bucket/frontend/ s3://website-bucket/ --profile nch-prod
```

## Automation and CI/CD

### GitHub Actions Integration
Example workflow for automated deployment:

```yaml
name: Deploy Easy CRM
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ap-southeast-1
      - name: Deploy infrastructure
        run: ./scripts/deploy.sh prod
      - name: Deploy Lambda functions
        run: ./scripts/package-lambdas.sh prod
      - name: Deploy frontend
        run: ./scripts/deploy-frontend.sh prod
      - name: Run smoke tests
        run: ./scripts/smoke-tests.sh prod
```

### Deployment Pipeline
1. **Development**: Automatic deployment on feature branch commits
2. **Staging**: Automatic deployment on main branch commits
3. **Production**: Manual approval required for production deployment

## Performance Optimization

### Lambda Functions
- Monitor execution duration and memory usage
- Optimize function memory allocation
- Use provisioned concurrency for consistent performance
- Implement connection pooling for database operations

### DynamoDB
- Monitor read/write capacity utilization
- Optimize query patterns and indexes
- Use DynamoDB Accelerator (DAX) for caching if needed
- Implement proper partition key design

### CloudFront
- Configure appropriate cache behaviors
- Use compression for static assets
- Implement proper cache invalidation strategies
- Monitor cache hit ratios

## Disaster Recovery

### Backup Strategy
- DynamoDB point-in-time recovery enabled
- S3 versioning and cross-region replication
- CloudFormation templates in version control
- Regular backup testing procedures

### Recovery Procedures
1. **Data Recovery**: Restore from DynamoDB point-in-time recovery
2. **Infrastructure Recovery**: Redeploy from CloudFormation templates
3. **Application Recovery**: Redeploy Lambda functions and frontend
4. **Validation**: Run comprehensive smoke tests

### Business Continuity
- Multi-region deployment for critical workloads
- Automated failover procedures
- Regular disaster recovery testing
- Documentation of recovery time objectives (RTO) and recovery point objectives (RPO)