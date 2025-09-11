# Easy CRM Infrastructure

This directory contains CloudFormation templates for deploying the Easy CRM Lead Management System infrastructure on AWS.

## Architecture Overview

The infrastructure follows a serverless microservices architecture with the following components:

- **Storage**: DynamoDB table for leads data with EmailIndex GSI for duplicate detection, and S3 buckets for file storage and website hosting
- **Authentication**: AWS Cognito User Pool and Identity Pool for user management
- **Compute**: Lambda functions for business logic processing with duplicate lead handling
- **API**: API Gateway for RESTful API endpoints with CORS and authentication
- **CDN**: CloudFront distribution for global content delivery and SSL termination
- **Duplicate Handling**: Email-based duplicate detection and automatic lead updates

## Templates

### main.yaml
Root CloudFormation template that orchestrates all nested stacks. This is the entry point for deployment.

**Parameters:**
- `DeepSeekApiKey`: API key for DeepSeek AI service (required)
- `DomainName`: Custom domain name (optional)
- `CertificateArn`: ACM certificate ARN for SSL (required if domain provided)
- `Environment`: Environment name (dev/staging/prod)

### storage.yaml
Creates DynamoDB table with Global Secondary Indexes and S3 buckets for file storage and website hosting.

**Resources:**
- DynamoDB table with GSIs for efficient querying (including EmailIndex for duplicate detection)
- ProcessingStatus table for real-time status tracking with TTL auto-expiration
- S3 bucket for file uploads with lifecycle policies
- S3 bucket for static website hosting
- CloudFront Origin Access Identity for secure S3 access
- SQS queue for batch processing with Dead Letter Queue

### cognito.yaml
Sets up AWS Cognito for user authentication and authorization.

**Resources:**
- Cognito User Pool with email verification
- User Pool Client for web application
- Identity Pool for AWS resource access
- IAM roles for authenticated and unauthenticated users

### lambda.yaml
Deploys Lambda functions and IAM roles with appropriate permissions.

**Resources:**
- 7 Lambda functions (file-upload, lead-splitter, deepseek-caller, lead-reader, lead-exporter, status-reader, chatbot)
- IAM execution role with DynamoDB, S3, and Cognito permissions
- S3 event trigger configuration for file processing
- ProcessingStatus table permissions for status tracking

### api-gateway.yaml
Creates API Gateway with REST endpoints and Cognito authorization.

**Resources:**
- REST API with CORS configuration
- Cognito authorizer for protected endpoints
- Lambda integrations for all endpoints
- API deployment and stage configuration

### cloudfront.yaml
Sets up CloudFront distribution for global content delivery and SSL.

**Resources:**
- CloudFront distribution with S3 and API Gateway origins
- Custom domain and SSL certificate integration
- Route53 DNS records (if custom domain provided)
- Caching behaviors for optimal performance

## Processing Status Tracking System

### Overview

The Easy CRM system includes a comprehensive real-time processing status tracking system that provides users with live feedback during file upload and processing operations. This system enables users to monitor progress, estimate completion times, and cancel operations if needed.

### Architecture Components

#### ProcessingStatus DynamoDB Table

A dedicated table for storing processing status information:

```yaml
ProcessingStatusTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: !Sub "ProcessingStatus-${Environment}"
    AttributeDefinitions:
      - AttributeName: uploadId
        AttributeType: S
    KeySchema:
      - AttributeName: uploadId
        KeyType: HASH
    BillingMode: PAY_PER_REQUEST
    TimeToLiveSpecification:
      AttributeName: ttl
      Enabled: true
```

**Purpose**: Stores real-time processing status with automatic expiration after 24 hours
**Key Schema**: `uploadId` as partition key for fast lookups
**TTL**: Automatic cleanup of old status records to manage storage costs

#### Status Reader Lambda Function

Dedicated Lambda function for status API endpoints:
- **GET /status/{uploadId}**: Retrieve current processing status
- **POST /status/{uploadId}/cancel**: Cancel in-progress operations
- **Authentication**: Cognito JWT token validation
- **Rate Limiting**: Built-in throttling to prevent abuse

#### Enhanced Lambda Functions

**File Upload Function**: Creates initial status records
- Generates unique `uploadId` for each upload
- Creates status record with "uploading" state
- Returns `uploadId` to frontend for tracking

**Lead Splitter Function**: Updates status during file processing
- Updates status to "processing" when file processing begins
- Calculates total batches and updates progress information
- Handles errors by updating status with error details

**DeepSeek Caller Function**: Tracks batch processing progress
- Updates completed batch count after each successful batch
- Calculates processed leads count and percentage
- Updates status to "completed" when all batches finish

### Status Data Model

#### Status Record Structure
```json
{
  "uploadId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "stage": "batch_processing",
  "progress": {
    "totalBatches": 10,
    "completedBatches": 3,
    "totalLeads": 100,
    "processedLeads": 30,
    "percentage": 30.0
  },
  "metadata": {
    "fileName": "leads.xlsx",
    "fileSize": 1024000,
    "startTime": "2025-01-09T10:00:00Z",
    "estimatedCompletion": "2025-01-09T10:05:00Z"
  },
  "error": {
    "message": "Processing error description",
    "code": "ERROR_CODE",
    "timestamp": "2025-01-09T10:02:00Z"
  },
  "createdAt": "2025-01-09T10:00:00Z",
  "updatedAt": "2025-01-09T10:02:30Z",
  "ttl": 1736424000
}
```

#### Status Values
- `uploading`: File upload in progress
- `uploaded`: File upload completed
- `processing`: File being processed and split into batches
- `completed`: All processing completed successfully
- `error`: Processing failed with error
- `cancelled`: Processing cancelled by user

#### Stage Values
- `file_upload`: File upload stage
- `file_processing`: File reading and batch creation
- `batch_processing`: AI processing of batches
- `completed`: All stages completed

### Frontend Integration

#### ProcessingStatusIndicator Component
JavaScript component that provides real-time status updates:
- **Polling Mechanism**: Polls status API every 2 seconds
- **Progress Display**: Visual progress bar with percentage and batch information
- **Error Handling**: Displays user-friendly error messages
- **Cancellation**: Provides cancel button for long-running operations
- **Auto-refresh**: Automatically refreshes lead table when processing completes

#### Status Polling Strategy
```javascript
class ProcessingStatusIndicator {
  startPolling() {
    this.pollInterval = setInterval(async () => {
      try {
        const status = await this.fetchStatus();
        this.render(status);
        
        if (status.status === 'completed') {
          this.handleCompletion(status);
        } else if (status.status === 'error') {
          this.handleError(status);
        }
      } catch (error) {
        this.handlePollingError(error);
      }
    }, 2000);
  }
}
```

### Performance Considerations

#### Polling Optimization
- **Frequency**: 2-second intervals during active processing
- **Exponential Backoff**: Increased intervals for errors
- **Auto-stop**: Polling stops after completion or timeout
- **Rate Limiting**: Frontend respects API rate limits

#### Database Performance
- **Single-item Queries**: Fast lookups using partition key
- **TTL Cleanup**: Automatic cleanup prevents table growth
- **On-demand Billing**: Scales with actual usage
- **Minimal Data**: Only essential status information stored

### Error Handling and Recovery

#### Cancellation Logic
```python
def cancel_processing(upload_id: str) -> dict:
    """Cancel in-progress processing operation."""
    # Update status to cancelled
    update_status(upload_id, 'cancelled', stage='cancelled')
    
    # Signal batch processors to stop
    # (Current batches complete, new batches are skipped)
    
    return {
        'uploadId': upload_id,
        'status': 'cancelled',
        'message': 'Processing cancellation requested'
    }
```

#### Error Recovery
- **Transient Errors**: Automatic retry with exponential backoff
- **Permanent Errors**: Clear error messages with recovery suggestions
- **Partial Failures**: Status tracking for partially completed operations
- **Timeout Handling**: Graceful handling of long-running operations

### Security and Access Control

#### Authentication
- All status endpoints require Cognito JWT tokens
- Users can only access their own upload status
- Token validation on every API request

#### Data Privacy
- Status records contain no sensitive lead data
- Automatic expiration after 24 hours
- Error messages sanitized to prevent information leakage

#### Rate Limiting
- Per-user rate limits to prevent abuse
- Exponential backoff for failed requests
- Graceful degradation under high load

### Monitoring and Alerting

#### CloudWatch Metrics
- `StatusPollingRequests`: Number of status API requests
- `StatusUpdateLatency`: Time to update status records
- `ProcessingCancellations`: Number of cancelled operations
- `StatusAPIErrors`: API error rates and types

#### Operational Monitoring
```bash
# Monitor status API performance
aws logs tail /aws/lambda/easy-crm-status-reader-prod --follow --profile nch-prod

# Check status table metrics
aws dynamodb describe-table --table-name ProcessingStatus-prod --profile nch-prod

# Monitor processing status distribution
aws dynamodb scan --table-name ProcessingStatus-prod --select COUNT --profile nch-prod
```

## Duplicate Lead Handling

### Overview

The Easy CRM system includes comprehensive duplicate lead detection and handling based on email addresses. This feature ensures that the database always contains the most recent information for each contact while maintaining processing efficiency.

### Architecture Components

#### EmailIndex Global Secondary Index (GSI)

The DynamoDB table includes an EmailIndex GSI for efficient duplicate detection:

```yaml
EmailIndex:
  Type: AWS::DynamoDB::GlobalSecondaryIndex
  Properties:
    IndexName: EmailIndex
    KeySchema:
      - AttributeName: email
        KeyType: HASH
    Projection:
      ProjectionType: ALL
    BillingMode: PAY_PER_REQUEST
```

**Purpose**: Enables fast lookups of existing leads by email address
**Query Pattern**: `email = :normalized_email_value`
**Performance**: ~1-5ms per email lookup

#### Enhanced Lambda Functions

**DeepSeek Caller Function**: Enhanced with duplicate detection logic
- Normalizes email addresses (case-insensitive, whitespace trimming)
- Detects duplicates within batches (last occurrence wins)
- Queries existing leads using EmailIndex GSI
- Performs upsert operations (insert new or update existing)
- Logs all duplicate handling actions

**Shared Utilities**: New modules for duplicate handling
- `email_utils.py`: Email normalization and validation
- Enhanced `dynamodb_utils.py`: Upsert methods and duplicate detection

### Duplicate Detection Process

#### 1. Email Normalization
```python
def normalize_email(email: str) -> str:
    """Normalize email for consistent duplicate detection."""
    if not email or email.strip().lower() in ['', 'n/a', 'null', 'none']:
        return 'N/A'
    return email.strip().lower()
```

#### 2. Batch-Level Duplicate Resolution
- **Within-Batch Duplicates**: Multiple leads with same email in one batch
- **Resolution Strategy**: Last occurrence wins (most recent data)
- **Performance**: Resolved in-memory before database operations

#### 3. Database-Level Duplicate Detection
- **EmailIndex Query**: Efficient lookup using GSI partition key
- **Upsert Logic**: Update existing or create new based on query result
- **Fallback Handling**: Create new leads if GSI unavailable

### Data Preservation Rules

#### Preserved Fields (on update)
- `leadId`: Original unique identifier maintained
- `createdAt`: Original creation timestamp preserved
- `email`: Normalized email address (case-insensitive)

#### Updated Fields (on update)
- `firstName`, `lastName`, `title`, `company`, `phone`, `remarks`: All replaced with new data
- `sourceFile`: Updated to reflect the latest file that provided the data
- `updatedAt`: Set to current timestamp

#### Field-Level Handling
- **No Field Merging**: New data completely replaces existing field values
- **Empty Values**: If new data has empty/N/A values, they still overwrite existing data
- **Data Types**: All field types handled consistently

### Performance Impact

#### Processing Time
- **Baseline**: ~2-5 seconds per 10-lead batch
- **With Duplicates**: ~2.5-6 seconds per 10-lead batch
- **Overhead**: 10-20% increase in processing time

#### Memory Usage
- **Additional Memory**: ~1KB per batch for duplicate tracking
- **GSI Query Results**: ~1KB per existing lead found
- **Total Impact**: <5% increase in memory usage

### Error Handling

#### GSI Unavailability
```python
try:
    existing_lead = find_lead_by_email(normalized_email)
except ClientError as e:
    if e.response['Error']['Code'] == 'ResourceNotFoundException':
        logger.warning("EmailIndex GSI not available, creating new lead")
        existing_lead = None
    else:
        raise DatabaseError(f"Failed to query EmailIndex: {str(e)}")
```

#### Fallback Strategies
1. **GSI Query Failure**: Create new leads (no duplicate detection)
2. **Update Operation Failure**: Retry with exponential backoff, then create new
3. **Batch Processing Timeout**: Process remaining leads individually
4. **Memory Constraints**: Process smaller sub-batches

### Monitoring and Logging

#### CloudWatch Metrics
- `DuplicateLeadsDetected`: Count of duplicates found per batch
- `LeadsUpdated`: Count of existing leads updated
- `LeadsCreated`: Count of new leads created
- `DuplicateDetectionLatency`: Time spent on duplicate detection
- `EmailIndexQueryErrors`: Count of GSI query failures

#### Audit Trail
```json
{
  "timestamp": "2025-01-20T14:30:00Z",
  "action": "lead_updated",
  "email": "john.doe@example.com",
  "leadId": "existing-uuid-123",
  "previousSourceFile": "old-upload.csv",
  "newSourceFile": "new-upload.csv",
  "fieldsChanged": ["title", "company", "phone"],
  "batchId": "batch-uuid-456"
}
```

### Validation and Testing

#### Deployment Validation
```bash
# Validate duplicate handling setup
./scripts/validate-duplicate-handling.sh

# Run duplicate handling tests
python -m pytest tests/unit/test_email_utils.py -v
python -m pytest tests/unit/test_dynamodb_duplicate_utils.py -v
python -m pytest tests/integration/test_duplicate_handling_workflow.py -v
```

#### Smoke Tests
The smoke tests (`./scripts/smoke-tests.sh`) include duplicate handling verification:
- EmailIndex GSI existence and status
- Email normalization functionality
- DynamoDB duplicate handling methods
- Lambda function environment variables

## Deployment

### Prerequisites

1. **AWS CLI**: Install and configure with `nch-prod` profile
2. **Permissions**: Ensure the AWS profile has permissions to create all required resources
3. **DeepSeek API Key**: Obtain API key from DeepSeek AI service
4. **Domain & Certificate** (optional): If using custom domain, ensure ACM certificate exists

### Quick Deployment

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Validate all templates
./scripts/validate-templates.sh

# Deploy infrastructure
./scripts/deploy.sh

# Deploy Lambda function code (after infrastructure is ready)
./scripts/package-lambdas.sh
```

### Manual Deployment

1. **Upload Templates to S3**:
```bash
# Create bucket for templates
aws s3 mb s3://easy-crm-templates-$(aws sts get-caller-identity --query Account --output text) --profile nch-prod

# Upload nested templates
aws s3 cp infrastructure/ s3://easy-crm-templates-$(aws sts get-caller-identity --query Account --output text)/ --recursive --exclude "*.md" --profile nch-prod
```

2. **Deploy Main Stack**:
```bash
aws cloudformation deploy \
  --template-file infrastructure/main.yaml \
  --stack-name easy-crm \
  --parameter-overrides \
    Environment=prod \
    DeepSeekApiKey=YOUR_API_KEY \
    DomainName=your-domain.com \
    CertificateArn=arn:aws:acm:us-east-1:123456789012:certificate/12345678-1234-1234-1234-123456789012 \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-southeast-1 \
  --profile nch-prod
```

3. **Update Lambda Code**:
```bash
./scripts/package-lambdas.sh
```

## Configuration

### Environment Variables

Lambda functions use the following environment variables:
- `LEADS_TABLE`: DynamoDB table name for leads
- `FILES_BUCKET`: S3 bucket name for file storage
- `DEEPSEEK_API_KEY`: API key for DeepSeek AI service
- `ENVIRONMENT`: Environment name (dev/staging/prod)

### Security

- All resources use least-privilege IAM policies
- Data encrypted in transit and at rest
- API Gateway uses Cognito JWT tokens for authorization
- CloudFront enforces HTTPS and proper caching headers
- S3 buckets have public access blocked by default

### Monitoring

- CloudWatch logs enabled for all Lambda functions
- API Gateway request/response logging enabled
- CloudFront access logs can be enabled if needed
- DynamoDB point-in-time recovery enabled

## Troubleshooting

### Common Issues

1. **Template Validation Errors**: Run `./scripts/validate-templates.sh` to check syntax
2. **Permission Denied**: Ensure AWS profile has required permissions
3. **Stack Creation Failed**: Check CloudFormation events in AWS Console
4. **Lambda Deployment Failed**: Ensure virtual environment is activated

### Useful Commands

```bash
# Check stack status
aws cloudformation describe-stacks --stack-name easy-crm --profile nch-prod

# View stack events
aws cloudformation describe-stack-events --stack-name easy-crm --profile nch-prod

# Delete stack (careful!)
aws cloudformation delete-stack --stack-name easy-crm --profile nch-prod

# Update Lambda function code only
aws lambda update-function-code --function-name easy-crm-file-upload-prod --zip-file fileb://function.zip --profile nch-prod
```

## Cost Optimization

- DynamoDB uses on-demand billing for variable workloads
- Lambda functions sized appropriately for their workload
- CloudFront uses PriceClass_100 for cost optimization
- S3 lifecycle policies automatically delete old files

## Security Best Practices

- Regular security updates for Lambda runtimes
- Monitor CloudTrail logs for API access
- Rotate DeepSeek API key regularly
- Review IAM policies periodically
- Enable AWS Config for compliance monitoring