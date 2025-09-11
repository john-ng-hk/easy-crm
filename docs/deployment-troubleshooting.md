# Deployment Troubleshooting Guide

This guide helps you troubleshoot common deployment issues with the Easy CRM system.

## Prerequisites Checklist

Before deploying, ensure you have:

- [ ] AWS CLI installed and configured
- [ ] AWS profile `nch-prod` configured with appropriate permissions
- [ ] DeepSeek API key available
- [ ] Python 3.13 and virtual environment set up
- [ ] All required dependencies installed

## Common Deployment Issues

### 1. AWS CLI Authentication Issues

**Problem:** `Unable to locate credentials` or `Access Denied` errors

**Solutions:**
```bash
# Check if profile exists
aws configure list-profiles

# Test credentials
aws sts get-caller-identity --profile nch-prod

# Reconfigure profile if needed
aws configure --profile nch-prod
```

**Required IAM Permissions:**
- CloudFormation: Full access
- Lambda: Full access
- DynamoDB: Full access
- S3: Full access
- Cognito: Full access
- API Gateway: Full access
- CloudFront: Full access
- IAM: CreateRole, AttachRolePolicy, PassRole

### 2. CloudFormation Template Validation Errors

**Problem:** Template validation fails during deployment

**Solutions:**
```bash
# Validate all templates
./scripts/validate-templates.sh

# Validate specific template
aws cloudformation validate-template \
    --template-body file://infrastructure/main.yaml \
    --profile nch-prod
```

**Common Template Issues:**
- Missing required parameters
- Invalid resource references
- Circular dependencies between nested stacks
- Resource naming conflicts

### 3. Stack Deployment Failures

**Problem:** CloudFormation stack creation or update fails

**Diagnosis:**
```bash
# Check stack events
aws cloudformation describe-stack-events \
    --stack-name easy-crm \
    --profile nch-prod \
    --region ap-southeast-1

# Check stack status
aws cloudformation describe-stacks \
    --stack-name easy-crm \
    --profile nch-prod \
    --region ap-southeast-1
```

**Common Causes:**
- Resource limits exceeded (e.g., Lambda concurrent executions)
- IAM permission issues
- Resource naming conflicts
- Parameter validation failures
- Nested stack template not found in S3

**Solutions:**
- Review CloudFormation events in AWS Console
- Check resource quotas in AWS Service Quotas
- Verify IAM permissions
- Ensure nested templates are uploaded to S3

### 4. Lambda Function Deployment Issues

**Problem:** Lambda functions fail to deploy or update

**Diagnosis:**
```bash
# Check function status
aws lambda get-function \
    --function-name easy-crm-file-upload-prod \
    --profile nch-prod \
    --region ap-southeast-1

# Check function logs
aws logs describe-log-groups \
    --log-group-name-prefix "/aws/lambda/easy-crm" \
    --profile nch-prod \
    --region ap-southeast-1
```

**Common Issues:**
- Virtual environment not activated
- Missing dependencies in requirements.txt
- Package size exceeds Lambda limits (50MB zipped)
- Function code syntax errors
- Environment variables not set correctly

**Solutions:**
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Check package size
du -sh lambda/*/

# Test function locally
python lambda/file-upload/lambda_function.py
```

### 5. DynamoDB Access Issues

**Problem:** Lambda functions cannot access DynamoDB table

**Diagnosis:**
```bash
# Check table status
aws dynamodb describe-table \
    --table-name easy-crm-leads-prod \
    --profile nch-prod \
    --region ap-southeast-1

# Test table access
aws dynamodb scan \
    --table-name easy-crm-leads-prod \
    --limit 1 \
    --profile nch-prod \
    --region ap-southeast-1
```

**Common Causes:**
- IAM role missing DynamoDB permissions
- Table not created or in wrong region
- Table name mismatch in Lambda environment variables
- Network connectivity issues

### 6. API Gateway Issues

**Problem:** API endpoints return errors or are not accessible

**Diagnosis:**
```bash
# Get API Gateway URL
aws cloudformation describe-stacks \
    --stack-name easy-crm \
    --profile nch-prod \
    --region ap-southeast-1 \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue'

# Test API endpoint
curl -X OPTIONS https://your-api-url/leads \
    -H "Origin: https://example.com" \
    -H "Access-Control-Request-Method: GET"
```

**Common Issues:**
- CORS not configured correctly
- Lambda integration not working
- Cognito authorizer configuration issues
- API deployment not triggered

### 7. Frontend Deployment Issues

**Problem:** Frontend files not accessible or configuration errors

**Diagnosis:**
```bash
# Check S3 bucket contents
aws s3 ls s3://your-website-bucket --profile nch-prod

# Check bucket policy
aws s3api get-bucket-policy \
    --bucket your-website-bucket \
    --profile nch-prod
```

**Common Issues:**
- S3 bucket policy not allowing public read
- CloudFront distribution not configured
- Configuration file (config.json) not updated
- Static website hosting not enabled

**Solutions:**
```bash
# Redeploy frontend
./scripts/deploy-frontend.sh prod

# Check CloudFront distribution
aws cloudfront list-distributions \
    --profile nch-prod \
    --query 'DistributionList.Items[?Comment==`Easy CRM Distribution`]'
```

### 8. DeepSeek API Integration Issues

**Problem:** File processing fails due to DeepSeek API errors

**Diagnosis:**
- Check Lambda function logs in CloudWatch
- Verify DeepSeek API key is correct
- Test API key manually with curl

**Common Issues:**
- Invalid or expired API key
- Rate limiting from DeepSeek
- Network connectivity issues
- API response format changes

**Solutions:**
```bash
# Test DeepSeek API manually
curl -X POST https://api.deepseek.com/v1/chat/completions \
    -H "Authorization: Bearer YOUR_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"test"}]}'

# Update API key in Lambda environment
aws lambda update-function-configuration \
    --function-name easy-crm-deepseek-caller-prod \
    --environment Variables='{DEEPSEEK_API_KEY=new_key}' \
    --profile nch-prod
```

## Environment-Specific Issues

### Development Environment
- Use smaller resource allocations
- Disable deletion protection
- Shorter log retention periods
- Reduced concurrent execution limits

### Staging Environment
- Enable detailed monitoring
- Use production-like configuration
- Test with realistic data volumes
- Validate all integrations

### Production Environment
- Enable deletion protection
- Configure proper backup policies
- Set up monitoring and alerting
- Use reserved capacity for predictable workloads

## Useful Commands

### Stack Management
```bash
# Delete stack (careful!)
aws cloudformation delete-stack \
    --stack-name easy-crm-dev \
    --profile nch-prod

# Update stack with new template
aws cloudformation update-stack \
    --stack-name easy-crm \
    --template-body file://infrastructure/main.yaml \
    --parameters ParameterKey=DeepSeekApiKey,ParameterValue=new_key \
    --profile nch-prod

# Cancel stack update
aws cloudformation cancel-update-stack \
    --stack-name easy-crm \
    --profile nch-prod
```

### Monitoring and Debugging
```bash
# View CloudWatch logs
aws logs tail /aws/lambda/easy-crm-file-upload-prod \
    --follow \
    --profile nch-prod

# Check API Gateway logs
aws logs describe-log-groups \
    --log-group-name-prefix "API-Gateway-Execution-Logs" \
    --profile nch-prod

# Monitor DynamoDB metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/DynamoDB \
    --metric-name ConsumedReadCapacityUnits \
    --dimensions Name=TableName,Value=easy-crm-leads-prod \
    --start-time 2024-01-01T00:00:00Z \
    --end-time 2024-01-01T01:00:00Z \
    --period 300 \
    --statistics Sum \
    --profile nch-prod
```

## Getting Help

1. **Check CloudFormation Events**: Always start with CloudFormation console events
2. **Review CloudWatch Logs**: Lambda and API Gateway logs provide detailed error information
3. **Run Smoke Tests**: Use `./scripts/smoke-tests.sh` to validate deployment
4. **AWS Documentation**: Refer to AWS service documentation for specific error codes
5. **Community Support**: AWS forums and Stack Overflow for common issues

## Prevention Best Practices

1. **Always validate templates** before deployment
2. **Test in development environment** first
3. **Use version control** for all infrastructure changes
4. **Monitor resource quotas** and limits
5. **Keep deployment scripts** up to date
6. **Document environment-specific configurations**
7. **Regular backup and disaster recovery testing**