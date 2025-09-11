# Batch Processing Architecture for Large Lead Files

## Problem Statement

The original file formatter function had limitations when processing large CSV/Excel files with many leads:

1. **DeepSeek API Limits**: DeepSeek may not handle large amounts of leads in a single request
2. **Timeout Issues**: Processing many leads could exceed Lambda timeout limits
3. **Memory Constraints**: Large files could cause memory issues
4. **Error Recovery**: If processing failed, the entire file would need to be reprocessed

## Solution: Split Processing with SQS

The solution splits the file processing into two separate Lambda functions connected by an SQS queue:

### Architecture Overview

```
S3 File Upload → Lead Splitter → SQS Queue → DeepSeek Caller → Duplicate Detection → DynamoDB
```

### Components

#### 1. Lead Splitter Function (`lambda/lead-splitter/`)
**Replaces**: Original `file-formatter` function  
**Trigger**: S3 PUT events on `uploads/` prefix  
**Purpose**: 
- Download and parse CSV/Excel files
- Split leads into batches of 10
- Send each batch to SQS queue

**Benefits**:
- Fast processing of file parsing
- Immediate feedback on file validity
- Efficient memory usage for large files

#### 2. DeepSeek Caller Function (`lambda/deepseek-caller/`)
**New Function**  
**Trigger**: SQS messages from Lead Processing Queue  
**Purpose**:
- Process batches of leads with DeepSeek AI
- Validate and standardize lead data
- Store processed leads in DynamoDB

**Benefits**:
- Controlled batch size for DeepSeek API
- Parallel processing of multiple batches
- Isolated error handling per batch

#### 3. SQS Queue (`easy-crm-lead-processing-{env}`)
**Configuration**:
- Visibility Timeout: 15 minutes (for DeepSeek processing)
- Message Retention: 14 days
- Dead Letter Queue: After 3 failed attempts
- Long Polling: 20 seconds

## Processing Flow

### 1. File Upload
```
User uploads file → S3 bucket (uploads/ prefix)
```

### 2. Lead Splitting
```
S3 Event → Lead Splitter Function
├── Download file from S3
├── Parse CSV/Excel (pandas)
├── Validate file format
├── Split into batches of 10 leads
└── Send each batch to SQS queue
```

### 3. Batch Processing
```
SQS Message → DeepSeek Caller Function
├── Receive batch from SQS
├── Call DeepSeek API for standardization
├── Validate standardized data
├── Detect and handle duplicates
│   ├── Normalize email addresses
│   ├── Check for batch-level duplicates
│   ├── Query existing leads via EmailIndex GSI
│   └── Perform upsert operations
├── Store/update leads in DynamoDB
└── Delete SQS message (success)
```

## Duplicate Lead Handling

### Overview

The batch processing architecture includes comprehensive duplicate lead detection and handling based on email addresses. This ensures that the database always contains the most recent information for each contact while maintaining processing efficiency.

### Duplicate Detection Strategy

#### 1. Email Normalization
```python
def normalize_email(email: str) -> str:
    """Normalize email for consistent duplicate detection."""
    if not email or email.strip().lower() in ['', 'n/a', 'null', 'none']:
        return 'N/A'
    return email.strip().lower()
```

#### 2. Batch-Level Duplicate Resolution
- **Within-Batch Duplicates**: When multiple leads in the same batch have the same email
- **Resolution Strategy**: Last occurrence wins (most recent data in the batch)
- **Performance**: Resolved in-memory before database operations

#### 3. Database-Level Duplicate Detection
- **EmailIndex GSI**: Efficient lookup of existing leads by email address
- **Query Pattern**: Single email lookups using GSI partition key
- **Fallback Handling**: If GSI unavailable, creates new leads and logs the issue

### Duplicate Handling Workflow

#### Processing Steps in DeepSeek Caller
```
1. Receive standardized batch from DeepSeek API
2. Normalize all email addresses in batch
3. Detect and resolve within-batch duplicates
4. For each unique email in batch:
   a. Query EmailIndex GSI for existing lead
   b. If exists: Update existing lead (preserve leadId, createdAt)
   c. If not exists: Create new lead
   d. Log duplicate action if applicable
5. Store batch processing statistics
```

#### Upsert Operations
```python
def upsert_lead(lead_data: Dict[str, Any], source_file: str) -> Tuple[str, bool]:
    """
    Insert new lead or update existing lead based on email.
    
    Returns:
        Tuple[str, bool]: (leadId, was_updated)
    """
    normalized_email = normalize_email(lead_data.get('email', ''))
    
    if normalized_email == 'N/A':
        # Always create new lead for empty emails
        return create_new_lead(lead_data, source_file), False
    
    existing_lead = find_lead_by_email(normalized_email)
    
    if existing_lead:
        # Update existing lead
        updated_lead = update_existing_lead(existing_lead, lead_data, source_file)
        return existing_lead['leadId'], True
    else:
        # Create new lead
        return create_new_lead(lead_data, source_file), False
```

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
- **Data Types**: All field types handled consistently (strings, numbers, etc.)

### Performance Optimization

#### EmailIndex GSI Efficiency
- **Query Time**: ~1-5ms per email lookup
- **Batch Impact**: +10-20% processing time for duplicate detection
- **Memory Usage**: Minimal additional overhead (~1KB per batch)

#### Batch Processing Optimizations
```python
def batch_upsert_leads(leads_data: List[Dict], source_file: str) -> Dict:
    """
    Optimized batch processing with duplicate handling.
    
    Optimizations:
    1. In-memory batch deduplication first
    2. Batch email queries where possible
    3. Parallel processing of independent operations
    4. Efficient logging and metrics collection
    """
    # Resolve within-batch duplicates first
    unique_leads, duplicate_logs = resolve_batch_duplicates(leads_data)
    
    # Process each unique lead
    results = {
        'created_leads': [],
        'updated_leads': [],
        'duplicate_actions': duplicate_logs,
        'processing_stats': {}
    }
    
    for lead_data in unique_leads:
        lead_id, was_updated = upsert_lead(lead_data, source_file)
        
        if was_updated:
            results['updated_leads'].append(lead_id)
        else:
            results['created_leads'].append(lead_id)
    
    return results
```

### Error Handling and Fallbacks

#### GSI Unavailability
```python
try:
    existing_lead = find_lead_by_email(normalized_email)
except ClientError as e:
    if e.response['Error']['Code'] == 'ResourceNotFoundException':
        logger.warning(f"EmailIndex GSI not available, creating new lead")
        existing_lead = None
    else:
        raise DatabaseError(f"Failed to query EmailIndex: {str(e)}")
```

#### Fallback Strategies
1. **GSI Query Failure**: Create new leads (no duplicate detection)
2. **Update Operation Failure**: Retry with exponential backoff, then create new
3. **Batch Processing Timeout**: Process remaining leads individually
4. **Memory Constraints**: Process smaller sub-batches

### Logging and Audit Trail

#### Duplicate Action Logging
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

#### Processing Statistics
```json
{
  "batch_id": "batch-uuid-456",
  "total_leads": 10,
  "duplicates_detected": 3,
  "leads_created": 7,
  "leads_updated": 3,
  "processing_time_ms": 1250,
  "email_index_queries": 10,
  "duplicate_detection_time_ms": 150
}
```

### Monitoring and Metrics

#### CloudWatch Metrics
- `DuplicateLeadsDetected`: Count of duplicates found per batch
- `LeadsUpdated`: Count of existing leads updated
- `LeadsCreated`: Count of new leads created
- `DuplicateDetectionLatency`: Time spent on duplicate detection
- `EmailIndexQueryErrors`: Count of GSI query failures

#### Alerting Thresholds
- **High Duplicate Rate**: >50% duplicates in batch (may indicate data quality issues)
- **GSI Query Failures**: >5% failure rate (infrastructure issue)
- **Processing Time Impact**: >30% increase in batch processing time

## Benefits

### Scalability
- **Large Files**: Can handle files with thousands of leads
- **Parallel Processing**: Multiple batches processed simultaneously
- **Resource Efficiency**: Each function optimized for its specific task

### Reliability
- **Error Isolation**: Failed batch doesn't affect other batches
- **Retry Logic**: SQS automatically retries failed messages
- **Dead Letter Queue**: Failed messages preserved for investigation
- **Partial Success**: Successfully processed batches are saved even if others fail

### Cost Optimization
- **Concurrency Control**: Limited to 5 concurrent DeepSeek calls
- **Efficient Resource Usage**: Functions only run when needed
- **Timeout Management**: Prevents runaway executions

### Monitoring
- **Granular Metrics**: Separate metrics for parsing vs. processing
- **Queue Visibility**: Monitor processing rates and backlogs
- **Batch Tracking**: Each batch has unique ID for tracing

## Configuration Changes

### Infrastructure Updates

#### Lambda Functions
```yaml
# New Functions
LeadSplitterFunction:
  - Timeout: 300 seconds (5 minutes)
  - Memory: 512 MB
  - Environment: PROCESSING_QUEUE_URL

DeepSeekCallerFunction:
  - Timeout: 900 seconds (15 minutes)
  - Memory: 512 MB
  - Concurrency: 5 (limited)
  - Environment: DEEPSEEK_API_KEY, LEADS_TABLE
```

#### SQS Queue
```yaml
LeadProcessingQueue:
  - VisibilityTimeout: 900 seconds
  - MessageRetention: 14 days
  - DeadLetterQueue: After 3 attempts
```

#### IAM Permissions
- Added SQS permissions for both functions
- Maintained existing DynamoDB and S3 permissions

### Deployment Changes

#### Package Script
Updated `scripts/package-lambdas.sh` to deploy:
- `lead-splitter` (replaces `file-formatter`)
- `deepseek-caller` (new function)

#### Infrastructure Deployment
- SQS queue created in lambda.yaml
- S3 notifications updated to trigger lead-splitter
- Event source mapping for SQS → DeepSeek caller

## Message Format

### SQS Message Structure
```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "source_file": "leads_2025.csv",
  "batch_number": 1,
  "total_batches": 5,
  "leads": [
    {
      "Name": "John Doe",
      "Company": "Acme Corp",
      "Email": "john@acme.com"
    }
  ],
  "timestamp": "2025-01-08T10:30:00Z",
  "environment": "prod"
}
```

### Message Attributes
- `source_file`: Original filename
- `batch_number`: Current batch (1-based)
- `lead_count`: Number of leads in batch

## Error Handling

### Lead Splitter Errors
- File parsing failures logged and function fails
- Invalid file types skipped with warning
- S3 download failures cause function retry

### DeepSeek Caller Errors
- DeepSeek API failures trigger SQS retry
- Validation failures logged but don't fail function
- DynamoDB errors cause message retry
- After 3 failures, message sent to DLQ

### Monitoring Points
1. **File Processing Rate**: Lead splitter invocations
2. **Queue Depth**: Messages waiting for processing
3. **Processing Time**: DeepSeek caller duration
4. **Error Rate**: Failed messages and DLQ depth
5. **API Usage**: DeepSeek API call frequency

## Migration Notes

### Backward Compatibility
- API endpoints remain unchanged
- Frontend requires no modifications
- Existing leads in DynamoDB unaffected

### Deployment Order
1. Deploy infrastructure (creates SQS queue)
2. Deploy Lambda functions (both new functions)
3. Test with small file upload
4. Monitor queue processing

### Rollback Plan
If issues arise:
1. Revert to single file-formatter function
2. Remove SQS queue and event source mapping
3. Update S3 notifications to trigger file-formatter

## Testing Strategy

### Unit Tests
- Lead splitter: File parsing and batch creation
- DeepSeek caller: API integration and data validation

### Integration Tests
- End-to-end file processing flow
- SQS message handling and retry logic
- Error scenarios and DLQ behavior

### Performance Tests
- Large file processing (1000+ leads)
- Concurrent file uploads
- Queue throughput under load

## Future Enhancements

### Potential Improvements
1. **Dynamic Batch Size**: Adjust based on file size or lead complexity
2. **Priority Queues**: Different processing priorities for different file types
3. **Progress Tracking**: Real-time progress updates for large files
4. **Batch Optimization**: Intelligent batching based on lead similarity
5. **Cost Monitoring**: Track DeepSeek API usage and costs per file