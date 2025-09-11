# Lambda Functions Architecture

## Overview

The Easy CRM system uses a microservices architecture with AWS Lambda functions. The file processing has been split into two parts to handle large amounts of leads efficiently using SQS for batch processing.

## Functions

### 1. File Upload (`file-upload/`)
- **Trigger**: API Gateway
- **Purpose**: Generate presigned S3 URLs for file uploads and create initial status records
- **Timeout**: 30 seconds
- **Memory**: 128 MB
- **Environment Variables**:
  - `PROCESSING_STATUS_TABLE`: DynamoDB table name for status tracking

### 2. Lead Splitter (`lead-splitter/`)
- **Trigger**: S3 PUT events (replaces old file-formatter)
- **Purpose**: 
  - Download and parse CSV/Excel files from S3
  - **Multi-Worksheet Support**: Process ALL worksheets in Excel files automatically
  - **Worksheet Tracking**: Add `_worksheet` field to track data source
  - Split leads into batches of 10
  - Send batches to SQS queue for processing
  - **Status Updates**: Update processing status during file processing
- **Timeout**: 300 seconds (5 minutes)
- **Memory**: 512 MB
- **Environment Variables**:
  - `PROCESSING_QUEUE_URL`: SQS queue URL for lead processing
  - `PROCESSING_STATUS_TABLE`: DynamoDB table name for status tracking

### 3. DeepSeek Caller (`deepseek-caller/`)
- **Trigger**: SQS messages from Lead Processing Queue
- **Purpose**:
  - Process batches of leads using DeepSeek AI
  - Standardize lead data format
  - Store processed leads in DynamoDB
  - **Progress Tracking**: Update batch completion progress in status system
- **Timeout**: 900 seconds (15 minutes)
- **Memory**: 512 MB
- **Concurrency**: Limited to 5 concurrent executions
- **Environment Variables**:
  - `DEEPSEEK_API_KEY`: API key for DeepSeek service
  - `LEADS_TABLE`: DynamoDB table name
  - `PROCESSING_STATUS_TABLE`: DynamoDB table name for status tracking

### 4. Lead Reader (`lead-reader/`)
- **Trigger**: API Gateway
- **Purpose**: Retrieve leads with filtering and pagination
- **Timeout**: 30 seconds
- **Memory**: 256 MB

### 5. Lead Exporter (`lead-exporter/`)
- **Trigger**: API Gateway
- **Purpose**: Export leads to CSV format
- **Timeout**: 60 seconds
- **Memory**: 256 MB

### 6. Status Reader (`status-reader/`)
- **Trigger**: API Gateway
- **Purpose**: Real-time processing status retrieval and cancellation
- **Timeout**: 30 seconds
- **Memory**: 256 MB
- **Environment Variables**:
  - `PROCESSING_STATUS_TABLE`: DynamoDB table name for status tracking

### 7. Chatbot (`chatbot/`)
- **Trigger**: API Gateway
- **Purpose**: Natural language queries using DeepSeek AI
- **Timeout**: 60 seconds
- **Memory**: 256 MB

## Processing Flow

```
1. User uploads CSV/Excel file
   ↓
2. File Upload function creates initial status record (status: "uploading")
   ↓
3. File stored in S3 (uploads/ prefix) → Status updated to "uploaded"
   ↓
4. S3 triggers Lead Splitter function
   ↓
5. Lead Splitter:
   - Updates status to "processing"
   - Downloads and parses file
   - For Excel files: processes ALL worksheets automatically
   - Adds `_worksheet` field to track data source
   - Splits leads into batches of 10
   - Updates status with total batches count
   - Sends each batch to SQS queue
   ↓
6. SQS triggers DeepSeek Caller function (one per batch)
   ↓
7. DeepSeek Caller:
   - Processes batch with DeepSeek AI
   - Validates standardized data
   - Stores leads in DynamoDB
   - Updates status with completed batch count and progress
   ↓
8. When all batches complete → Status updated to "completed"
   ↓
9. Frontend automatically refreshes lead table
```

## Status Tracking Integration

### Status Updates Throughout Processing

```
Status: "uploading" → File Upload function
Status: "uploaded" → File stored in S3
Status: "processing" → Lead Splitter starts
Progress: {totalBatches: N} → Lead Splitter completes splitting
Progress: {completedBatches: X, processedLeads: Y} → Each DeepSeek Caller completion
Status: "completed" → All batches processed
```

### Frontend Polling
- Status Reader function provides real-time status via API
- Frontend polls every 2 seconds during processing
- Automatic lead table refresh on completion
- Cancel functionality for long-running operations

## Benefits of New Architecture

### Scalability
- **Batch Processing**: Large files are processed in manageable chunks
- **Parallel Processing**: Multiple batches can be processed simultaneously
- **Queue Management**: SQS handles message delivery and retry logic

### Reliability
- **Error Isolation**: Failed batches don't affect other batches
- **Dead Letter Queue**: Failed messages are preserved for investigation
- **Retry Logic**: Automatic retry for transient failures

### Cost Optimization
- **Concurrency Limits**: Prevents excessive DeepSeek API calls
- **Efficient Resource Usage**: Functions only run when needed
- **Timeout Management**: Prevents runaway executions

### Monitoring
- **Granular Metrics**: Separate metrics for splitting and processing
- **Queue Visibility**: Monitor queue depth and processing rates
- **Error Tracking**: Clear separation of parsing vs. processing errors

## SQS Configuration

### Lead Processing Queue
- **Name**: `easy-crm-lead-processing-{environment}`
- **Visibility Timeout**: 900 seconds (15 minutes)
- **Message Retention**: 14 days
- **Long Polling**: 20 seconds
- **Dead Letter Queue**: After 3 failed attempts

### Message Format
```json
{
  "batch_id": "uuid",
  "source_file": "filename.csv",
  "batch_number": 1,
  "total_batches": 5,
  "leads": [...],
  "timestamp": "2025-01-08T10:30:00Z",
  "environment": "prod"
}
```

## Deployment

Use the updated `package-lambdas.sh` script to deploy all functions:

```bash
./scripts/package-lambdas.sh prod
```

The script will:
1. Package each function with its dependencies
2. Copy shared utilities to each package
3. Deploy to AWS Lambda
4. Handle both new functions (lead-splitter, deepseek-caller)

## Monitoring and Troubleshooting

### CloudWatch Metrics
- **Lead Splitter**: Monitor file processing success/failure rates
- **DeepSeek Caller**: Track batch processing times and DeepSeek API calls
- **SQS Queue**: Monitor message count, age, and processing rates

### Common Issues
1. **Large Files**: Increase Lead Splitter timeout if needed
2. **DeepSeek Rate Limits**: Adjust concurrency limits
3. **Queue Backlog**: Monitor and scale processing capacity
4. **Validation Failures**: Check lead data format and validation rules

### Logs
- All functions use structured logging with correlation IDs
- Batch processing includes batch_id for tracing
- Error logs include context for debugging