# Infrastructure and Deployment Guide

## CloudFormation Architecture

The Easy CRM infrastructure uses a nested CloudFormation stack architecture for modularity and maintainability. The main template orchestrates 5 nested stacks:

### Stack Dependencies

```text
main.yaml
├── storage.yaml (DynamoDB + S3)
├── cognito.yaml (Authentication)
├── lambda.yaml (Functions + IAM) [depends on: storage, cognito]
├── api-gateway.yaml (REST API) [depends on: lambda, cognito]
└── cloudfront.yaml (CDN + SSL) [depends on: storage, api-gateway]
```

## Deployment Scripts

### ./scripts/deploy.sh

Automated deployment script that:

- Uses predefined ACM certificate for SSL (arn:aws:acm:us-east-1:YOUR_ACCOUNT_ID:certificate/YOUR_CERTIFICATE_ID)
- Prompts for DeepSeek API key (or uses DEEPSEEK_API_KEY environment variable)
- Creates S3 bucket for nested templates
- Uploads all nested templates to S3
- Validates the main template
- Deploys the complete infrastructure stack with custom domain
- Displays stack outputs upon completion

### ./scripts/package-lambdas.sh

Lambda deployment script that:

- Packages each Lambda function with dependencies
- Copies shared utilities to each function package
- Installs requirements.txt dependencies
- Updates Lambda function code via AWS CLI
- Handles all 5 Lambda functions automatically

### ./scripts/validate-templates.sh

Template validation script that:

- Validates all CloudFormation templates for syntax errors
- Uses AWS CLI validate-template command
- Provides clear success/failure feedback
- Must pass before deployment

## Required AWS Resources

### Pre-Deployment Requirements

1. **AWS CLI**: Configured with `nch-prod` profile
2. **IAM Permissions**: Full access to CloudFormation, Lambda, DynamoDB, S3, Cognito, API Gateway, CloudFront
3. **DeepSeek API Key**: Valid API key for AI integration
4. **ACM Certificate** (optional): For custom domain SSL

### Created Resources

- **DynamoDB**: `easy-crm-leads-prod` table with 3 GSIs
- **S3 Buckets**: 
  - Files bucket: `easy-crm-files-{account-id}-prod`
  - Website bucket: `easy-crm-website-{account-id}-prod`
  - Templates bucket: `easy-crm-templates-{account-id}`
- **Lambda Functions**: 6 functions with IAM roles, environment variables, and AWS Pandas Layer
  - `easy-crm-file-upload-prod` (presigned S3 URL generation)
  - `easy-crm-lead-splitter-prod` (batch processing - replaces file-formatter)
  - `easy-crm-deepseek-caller-prod` (DeepSeek API integration - batch processor)
  - `easy-crm-lead-reader-prod` (lead retrieval with phone field support)
  - `easy-crm-lead-exporter-prod` (CSV export with phone field support)
  - `easy-crm-chatbot-prod` (natural language queries with phone field support)
- **SQS Queue**: `easy-crm-lead-processing-prod` with Dead Letter Queue
- **API Gateway**: REST API with Cognito authorizer and CORS
- **Cognito**: User Pool, Identity Pool, and IAM roles
- **CloudFront**: CDN distribution with custom domain and SSL certificate

## Environment Configuration

### Parameters

- `Environment`: dev/staging/prod (affects resource naming)
- `DeepSeekApiKey`: Stored as environment variable in Lambda functions
- `CertificateArn`: Predefined ACM certificate (arn:aws:acm:us-east-1:YOUR_ACCOUNT_ID:certificate/YOUR_CERTIFICATE_ID)

### Current Deployment

- **Custom Domain**: your-domain.com
- **CloudFront Distribution**: YOUR_DISTRIBUTION_ID
- **API Gateway**: https://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod
- **Environment**: prod
- **Status**: ✅ Fully deployed and operational
- **Last Updated**: September 8, 2025

### Recent Fixes Applied

- ✅ Fixed pagination indicator showing "0 to 0 of 0 leads" 
- ✅ Fixed pagination not refreshing when clicking next/previous buttons
- ✅ Corrected API Gateway URL configuration in frontend
- ✅ Streamlined configuration loading process
- ✅ Updated gitignore to exclude Lambda package dependencies
- ✅ Migrated from file-formatter to batch processing architecture
- ✅ Integrated phone field support across all components
- ✅ Added AWS Pandas Layer for Excel processing without numpy conflicts
- ✅ Implemented comprehensive testing suite (31 phone field tests passing)
- ✅ Added SQS Dead Letter Queue for failed message handling

### Resource Naming Convention

- DynamoDB: `easy-crm-leads-{environment}`
- S3 Files: `easy-crm-files-{account-id}-{environment}`
- S3 Website: `easy-crm-website-{account-id}-{environment}`
- Lambda: `easy-crm-{function-name}-{environment}`
- Templates: `easy-crm-templates-{account-id}`

## Security Configuration

### IAM Roles and Policies

- **Lambda Execution Role**: Least-privilege access to DynamoDB, S3, and Cognito
- **Cognito Authenticated Role**: API Gateway invoke permissions
- **Cognito Unauthenticated Role**: Minimal permissions for public access

### Encryption and Security

- **DynamoDB**: Server-side encryption enabled
- **S3**: AES256 encryption for all buckets
- **API Gateway**: HTTPS only with Cognito JWT validation
- **CloudFront**: SSL/TLS termination with security headers

## Monitoring and Logging

### CloudWatch Integration

- Lambda function logs automatically created
- API Gateway request/response logging enabled
- DynamoDB point-in-time recovery enabled
- CloudFront access logs available (optional)

### Cost Optimization

- DynamoDB on-demand billing for variable workloads
- S3 lifecycle policies for automatic cleanup
- CloudFront PriceClass_100 for cost efficiency
- Lambda functions sized appropriately for workload

## Troubleshooting

### Common Deployment Issues

1. **Template Validation Errors**: Run `./scripts/validate-templates.sh`
2. **Permission Denied**: Check AWS profile and IAM permissions
3. **Stack Creation Failed**: Check CloudFormation events in AWS Console
4. **Lambda Deployment Failed**: Ensure virtual environment is activated

### Useful Commands

```bash
# Check stack status
aws cloudformation describe-stacks --stack-name easy-crm --profile nch-prod

# View stack events
aws cloudformation describe-stack-events --stack-name easy-crm --profile nch-prod

# Update single Lambda function
aws lambda update-function-code --function-name easy-crm-file-upload-prod --zip-file fileb://function.zip --profile nch-prod

# Delete stack (careful!)
aws cloudformation delete-stack --stack-name easy-crm --profile nch-prod
```

## Resource Management

### Active Stacks

The current deployment consists of these CloudFormation stacks:

- **Main Stack**: `easy-crm` - Root orchestration stack
- **Nested Stacks** (managed by main stack):
  - `easy-crm-StorageStack-15SFXOBBB6X1H` - DynamoDB and S3 resources
  - `easy-crm-CognitoStack-1AYB4IFU6CNEY` - Authentication resources
  - `easy-crm-LambdaStack-IMOUKM5ETLA` - Lambda functions and IAM roles
  - `easy-crm-ApiGatewayStack-1IF611WKQO5BF` - API Gateway and endpoints

### Cleanup Commands

```bash
# List all CRM-related stacks
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --profile nch-prod --query 'StackSummaries[?contains(StackName, `easy-crm`)].StackName'

# Delete unused standalone stacks (if any)
aws cloudformation delete-stack --stack-name <unused-stack-name> --profile nch-prod

# Clean up unused S3 objects (be careful!)
aws s3 rm s3://easy-crm-templates-{account-id}/ --recursive --profile nch-prod
```

## Best Practices

### Development

- Always validate templates before deployment
- Use virtual environments for Python development
- Test Lambda functions locally before deployment
- Follow the deployment order: infrastructure → Lambda code → frontend
- Clean up unused resources regularly

### Production

- Use separate environments (dev/staging/prod)
- Monitor CloudWatch logs and metrics
- Regularly rotate DeepSeek API key
- Review IAM policies periodically
- Enable AWS Config for compliance monitoring
- Monitor costs and clean up unused resources