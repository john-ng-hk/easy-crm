# Easy CRM Demo Deployment Guide

This guide will help you deploy a demo instance of the Easy CRM system for demonstration purposes.

## 🎯 Demo Environment Overview

The demo environment is configured with:
- **Stack Name**: `easy-crm-demo`
- **Environment**: `demo`
- **Region**: `ap-southeast-1`
- **Cost Optimized**: Lower memory allocations and shorter log retention
- **Purpose**: Demonstration and testing

## 📋 Prerequisites

### 1. AWS Account Setup
- AWS CLI installed and configured
- AWS profile `nch-prod` configured (or update the profile in `config/environments/demo.yaml`)
- Appropriate IAM permissions for CloudFormation, Lambda, DynamoDB, S3, Cognito, API Gateway, CloudFront

### 2. Required Services
- **DeepSeek API Key**: Get from [DeepSeek AI](https://platform.deepseek.com/)
- **ACM Certificate** (optional): For custom domain SSL

### 3. Environment Variables
```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key-here"
export CERTIFICATE_ARN="arn:aws:acm:us-east-1:YOUR_ACCOUNT_ID:certificate/YOUR_CERT_ID"  # Optional
```

## 🚀 Deployment Steps

### Step 1: Prepare Configuration

1. **Copy frontend configuration template:**
   ```bash
   cp frontend/config.json.example frontend/config.json
   ```

2. **Set your DeepSeek API key:**
   ```bash
   export DEEPSEEK_API_KEY="sk-your-actual-api-key-here"
   ```

3. **Optional - Set custom domain certificate:**
   ```bash
   export CERTIFICATE_ARN="arn:aws:acm:us-east-1:123456789012:certificate/your-cert-id"
   ```

### Step 2: Deploy Infrastructure

1. **Run the deployment script:**
   ```bash
   ./scripts/deploy.sh demo
   ```

   The script will:
   - Validate prerequisites
   - Create S3 bucket for CloudFormation templates
   - Upload nested templates
   - Deploy the complete infrastructure stack
   - Run smoke tests
   - Display deployment outputs

2. **Expected deployment time:** 10-15 minutes

### Step 3: Deploy Lambda Functions

1. **Package and deploy Lambda functions:**
   ```bash
   ./scripts/package-lambdas.sh demo
   ```

   This will:
   - Package each Lambda function with dependencies
   - Update function code in AWS
   - Verify deployments

### Step 4: Deploy Frontend

1. **Deploy frontend files:**
   ```bash
   ./scripts/deploy-frontend.sh demo
   ```

   This will:
   - Update frontend configuration with actual AWS resource URLs
   - Upload static files to S3
   - Invalidate CloudFront cache

### Step 5: Verify Deployment

1. **Run validation script:**
   ```bash
   ./scripts/validate-deployment.sh demo
   ```

2. **Run smoke tests:**
   ```bash
   ./scripts/smoke-tests.sh demo
   ```

## 🔧 Configuration Details

### Demo Environment Resources

After deployment, you'll have:

- **DynamoDB Table**: `easy-crm-leads-demo`
- **S3 Buckets**:
  - Files: `easy-crm-files-{account-id}-demo`
  - Website: `easy-crm-website-{account-id}-demo`
- **Lambda Functions**:
  - `easy-crm-file-upload-demo`
  - `easy-crm-lead-splitter-demo`
  - `easy-crm-deepseek-caller-demo`
  - `easy-crm-lead-reader-demo`
  - `easy-crm-lead-exporter-demo`
  - `easy-crm-chatbot-demo`
  - `easy-crm-status-reader-demo`
- **SQS Queue**: `easy-crm-lead-processing-demo`
- **API Gateway**: REST API with `/demo` stage
- **Cognito**: User Pool and Identity Pool
- **CloudFront**: CDN distribution

### Cost Optimization Features

The demo environment includes:
- Lower Lambda memory allocations (128-256 MB vs 512 MB)
- Shorter CloudWatch log retention (3 days vs 14 days)
- Limited Lambda concurrency (5 vs 10)
- On-demand DynamoDB billing
- CloudFront PriceClass_100 (cost-effective regions)

## 🌐 Accessing Your Demo

### Get Deployment URLs

After successful deployment, get the URLs:

```bash
aws cloudformation describe-stacks \
  --stack-name easy-crm-demo \
  --region ap-southeast-1 \
  --profile nch-prod \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table
```

### Key URLs:
- **Website URL**: CloudFront distribution URL
- **API Gateway URL**: For API access
- **Cognito User Pool**: For user management

## 🧪 Testing Your Demo

### 1. Create Test User

```bash
# Get User Pool ID from CloudFormation outputs
USER_POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name easy-crm-demo \
  --region ap-southeast-1 \
  --profile nch-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
  --output text)

# Create test user
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username demo-user \
  --user-attributes Name=email,Value=demo@example.com \
  --temporary-password TempPass123! \
  --message-action SUPPRESS \
  --region ap-southeast-1 \
  --profile nch-prod
```

### 2. Upload Test Data

Use the provided test files:
- `easy-crm-test.xlsx` - Multi-worksheet Excel file
- `test-leads-excel.csv` - CSV test data

### 3. Test Features

1. **File Upload**: Upload CSV/Excel files
2. **Multi-Worksheet Processing**: Upload Excel files with multiple sheets
3. **Duplicate Detection**: Upload files with duplicate email addresses
4. **Lead Management**: View, filter, and sort leads
5. **Phone Field Integration**: Test phone number formatting and tel: links
6. **Natural Language Chat**: Query leads using plain English
7. **Data Export**: Export filtered lead data to CSV
8. **Real-time Status**: Monitor upload and processing progress

## 🔍 Monitoring and Troubleshooting

### CloudWatch Logs

Monitor Lambda function logs:
```bash
# View logs for specific function
aws logs tail /aws/lambda/easy-crm-lead-splitter-demo --follow --region ap-southeast-1 --profile nch-prod

# View all CRM-related log groups
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/easy-crm" --region ap-southeast-1 --profile nch-prod
```

### Common Issues

1. **DeepSeek API Errors**: Check API key validity and quota
2. **Lambda Timeouts**: Monitor function duration in CloudWatch
3. **DynamoDB Throttling**: Check read/write capacity metrics
4. **S3 Upload Issues**: Verify bucket permissions and CORS configuration

### Debug Commands

```bash
# Check stack status
aws cloudformation describe-stacks --stack-name easy-crm-demo --region ap-southeast-1 --profile nch-prod

# Check Lambda function status
aws lambda list-functions --region ap-southeast-1 --profile nch-prod | grep easy-crm-demo

# Check DynamoDB table
aws dynamodb describe-table --table-name easy-crm-leads-demo --region ap-southeast-1 --profile nch-prod
```

## 🧹 Cleanup

When you're done with the demo:

```bash
# Delete the CloudFormation stack (this removes all resources)
aws cloudformation delete-stack --stack-name easy-crm-demo --region ap-southeast-1 --profile nch-prod

# Clean up S3 template bucket (if not used by other stacks)
aws s3 rm s3://easy-crm-templates-{account-id}/ --recursive --profile nch-prod
aws s3 rb s3://easy-crm-templates-{account-id}/ --profile nch-prod
```

## 📞 Support

For issues or questions:
1. Check [SECURITY_CHECKLIST.md](SECURITY_CHECKLIST.md) for setup requirements
2. Review [docs/deployment-troubleshooting.md](docs/deployment-troubleshooting.md)
3. Check CloudWatch logs for detailed error information
4. Verify all prerequisites are met

## 🎉 Demo Script

### Quick Demo Flow:

1. **Show the landing page** - Clean, modern interface
2. **Upload a CSV file** - Demonstrate drag-and-drop upload
3. **Show real-time processing** - Progress indicators and status updates
4. **Upload Excel with multiple worksheets** - Show multi-sheet processing
5. **Demonstrate duplicate handling** - Upload file with duplicate emails
6. **Show lead management** - Filtering, sorting, pagination
7. **Test phone field integration** - Click-to-call functionality
8. **Use natural language chat** - "Show me all leads from tech companies"
9. **Export filtered data** - CSV export functionality
10. **Show mobile responsiveness** - Responsive design on different devices

This demo environment showcases all the key features while being cost-effective for demonstration purposes.