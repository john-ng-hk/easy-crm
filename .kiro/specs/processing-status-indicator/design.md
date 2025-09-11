# Design Document

## Overview

The processing status indicator feature will provide real-time feedback to users during file upload and lead processing operations. The system will track processing stages through the existing batch processing architecture and display status updates in the frontend UI. The design leverages DynamoDB for status persistence, polling for real-time updates, and integrates seamlessly with the current upload workflow.

## Architecture

### High-Level Flow

```
User Upload → Status Tracking → Real-time Updates → Auto Refresh
     ↓              ↓                ↓               ↓
File Upload    DynamoDB Status   Frontend Polling  Lead Table
   (S3)         Persistence        (API Gateway)    Refresh
```

### Component Integration

The status system integrates with existing components:

1. **Frontend Upload Module** - Initiates status tracking and displays UI
2. **Lead Splitter Lambda** - Updates status during file processing
3. **DeepSeek Caller Lambda** - Updates batch progress
4. **DynamoDB** - Stores processing status and progress
5. **API Gateway** - Provides status polling endpoint
6. **Lead Reader Lambda** - Enhanced to support status queries

## Components and Interfaces

### 1. Processing Status Data Model

**DynamoDB Table: ProcessingStatus**

```json
{
  "uploadId": "uuid-string",           // Partition Key
  "status": "uploading|uploaded|processing|completed|error",
  "stage": "file_upload|file_processing|batch_processing|completed",
  "progress": {
    "totalBatches": 10,
    "completedBatches": 3,
    "totalLeads": 100,
    "processedLeads": 30
  },
  "metadata": {
    "fileName": "leads.xlsx",
    "fileSize": 1024000,
    "startTime": "2025-01-09T10:00:00Z",
    "estimatedCompletion": "2025-01-09T10:05:00Z"
  },
  "error": {
    "message": "Error description",
    "code": "ERROR_CODE",
    "timestamp": "2025-01-09T10:02:00Z"
  },
  "createdAt": "2025-01-09T10:00:00Z",
  "updatedAt": "2025-01-09T10:02:30Z",
  "ttl": 1736424000  // Auto-expire after 24 hours
}
```

### 2. Frontend Status Component

**Status Indicator UI Component**

```javascript
class ProcessingStatusIndicator {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.uploadId = null;
    this.pollInterval = null;
    this.isVisible = false;
  }

  show(uploadId, initialStatus = 'uploading') {
    this.uploadId = uploadId;
    this.render(initialStatus);
    this.startPolling();
    this.isVisible = true;
  }

  hide() {
    this.stopPolling();
    this.container.style.display = 'none';
    this.isVisible = false;
  }

  startPolling() {
    this.pollInterval = setInterval(() => {
      this.fetchStatus();
    }, 2000); // Poll every 2 seconds
  }

  async fetchStatus() {
    // Poll API for status updates
  }

  render(statusData) {
    // Render status UI with progress
  }
}
```

### 3. Backend Status Management

**Status Service (Lambda Shared Module)**

```python
class ProcessingStatusService:
    def __init__(self, dynamodb_client):
        self.dynamodb = dynamodb_client
        self.table_name = 'ProcessingStatus'
    
    def create_status(self, upload_id, file_name, file_size):
        """Initialize processing status"""
        
    def update_status(self, upload_id, status, stage=None, progress=None):
        """Update processing status and progress"""
        
    def get_status(self, upload_id):
        """Retrieve current processing status"""
        
    def set_error(self, upload_id, error_message, error_code):
        """Set error status with details"""
        
    def complete_processing(self, upload_id, total_leads):
        """Mark processing as completed"""
```

### 4. API Endpoints

**New Status Endpoint**

```yaml
/status/{uploadId}:
  get:
    summary: Get processing status
    parameters:
      - name: uploadId
        in: path
        required: true
        schema:
          type: string
    responses:
      200:
        description: Processing status
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ProcessingStatus'
```

## Data Models

### ProcessingStatus Schema

```json
{
  "type": "object",
  "properties": {
    "uploadId": {"type": "string"},
    "status": {
      "type": "string",
      "enum": ["uploading", "uploaded", "processing", "completed", "error", "cancelled"]
    },
    "stage": {
      "type": "string", 
      "enum": ["file_upload", "file_processing", "batch_processing", "completed"]
    },
    "progress": {
      "type": "object",
      "properties": {
        "totalBatches": {"type": "integer"},
        "completedBatches": {"type": "integer"},
        "totalLeads": {"type": "integer"},
        "processedLeads": {"type": "integer"},
        "percentage": {"type": "number"}
      }
    },
    "metadata": {
      "type": "object",
      "properties": {
        "fileName": {"type": "string"},
        "fileSize": {"type": "integer"},
        "startTime": {"type": "string", "format": "date-time"},
        "estimatedCompletion": {"type": "string", "format": "date-time"}
      }
    },
    "error": {
      "type": "object",
      "properties": {
        "message": {"type": "string"},
        "code": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"}
      }
    }
  }
}
```

## Error Handling

### Error States and Recovery

1. **Upload Failures**
   - Network errors during S3 upload
   - File validation failures
   - S3 permission issues

2. **Processing Failures**
   - Lead splitter Lambda errors
   - DeepSeek API failures
   - DynamoDB write failures

3. **Status Polling Failures**
   - API Gateway timeouts
   - Network connectivity issues
   - Authentication failures

### Error Recovery Strategies

```javascript
class StatusErrorHandler {
  handlePollingError(error) {
    if (error.code === 'NETWORK_ERROR') {
      // Exponential backoff retry
      this.retryWithBackoff();
    } else if (error.code === 'AUTH_ERROR') {
      // Refresh authentication
      this.refreshAuth();
    } else {
      // Show error to user
      this.showError(error.message);
    }
  }
  
  retryWithBackoff() {
    const delay = Math.min(1000 * Math.pow(2, this.retryCount), 30000);
    setTimeout(() => this.fetchStatus(), delay);
  }
}
```

## Testing Strategy

### Unit Tests

1. **ProcessingStatusService Tests**
   - Status creation and updates
   - Progress calculation
   - Error handling
   - TTL management

2. **Frontend Component Tests**
   - Status display rendering
   - Polling mechanism
   - Error state handling
   - Auto-hide functionality

### Integration Tests

1. **End-to-End Status Flow**
   - File upload → status creation
   - Batch processing → progress updates
   - Completion → auto refresh
   - Error scenarios → error display

2. **API Integration Tests**
   - Status endpoint functionality
   - Authentication and authorization
   - Error response handling
   - Performance under load

### Performance Tests

1. **Polling Performance**
   - Multiple concurrent users
   - Database query performance
   - API response times
   - Memory usage during long operations

## Implementation Phases

### Phase 1: Core Infrastructure
- Create ProcessingStatus DynamoDB table
- Implement ProcessingStatusService
- Add status API endpoint
- Basic frontend status component

### Phase 2: Integration
- Integrate with file upload flow
- Update Lead Splitter for status tracking
- Update DeepSeek Caller for progress updates
- Implement frontend polling

### Phase 3: Enhanced Features
- Progress estimation algorithms
- Cancellation functionality
- Auto-refresh lead table
- Error recovery mechanisms

### Phase 4: Polish and Optimization
- UI/UX improvements
- Performance optimization
- Comprehensive testing
- Documentation updates

## Security Considerations

### Access Control
- Status endpoints require authentication
- Users can only access their own upload status
- Status data includes no sensitive information

### Data Privacy
- Status records auto-expire after 24 hours
- No lead data stored in status records
- Error messages sanitized to prevent information leakage

### Rate Limiting
- Polling frequency limited to prevent abuse
- Status updates throttled to prevent spam
- Graceful degradation under high load

This design provides a comprehensive solution for real-time processing status tracking that integrates seamlessly with the existing Easy CRM architecture while maintaining performance and security standards.