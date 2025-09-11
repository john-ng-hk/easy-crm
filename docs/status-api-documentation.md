# Status API Documentation

## Overview

The Status API provides real-time access to file processing status information. This API enables the frontend to display progress updates and allows users to monitor and control their file processing operations.

## Base URL

```
https://your-api-id.execute-api.ap-southeast-1.amazonaws.com/prod
```

## Authentication

All status API endpoints require authentication using AWS Cognito JWT tokens.

### Headers Required
```http
Authorization: Bearer <jwt-token>
Content-Type: application/json
```

### Authentication Flow
1. User authenticates with Cognito User Pool
2. Cognito returns JWT access token
3. Include token in Authorization header for all API calls
4. Token is validated by API Gateway Cognito Authorizer

## Endpoints

### GET /status/{uploadId}

Retrieve the current processing status for a specific upload.

#### Parameters

| Parameter | Type | Location | Required | Description |
|-----------|------|----------|----------|-------------|
| uploadId | string | path | Yes | Unique identifier for the upload operation |

#### Request Example

```http
GET /status/550e8400-e29b-41d4-a716-446655440000
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### Response Format

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
  "createdAt": "2025-01-09T10:00:00Z",
  "updatedAt": "2025-01-09T10:02:30Z"
}
```

#### Status Values

| Status | Description |
|--------|-------------|
| `uploading` | File is being uploaded to S3 |
| `uploaded` | File upload completed, processing starting |
| `processing` | File is being processed and split into batches |
| `completed` | All processing completed successfully |
| `error` | Processing failed with an error |
| `cancelled` | Processing was cancelled by user |

#### Stage Values

| Stage | Description |
|-------|-------------|
| `file_upload` | File upload in progress |
| `file_processing` | File being read and split into batches |
| `batch_processing` | Batches being processed through AI |
| `completed` | All processing stages completed |

#### Response Codes

| Code | Description |
|------|-------------|
| 200 | Success - Status retrieved |
| 401 | Unauthorized - Invalid or missing JWT token |
| 404 | Not Found - Upload ID not found or expired |
| 500 | Internal Server Error - Server processing error |

#### Error Response Format

```json
{
  "error": {
    "code": "UPLOAD_NOT_FOUND",
    "message": "Upload ID not found or has expired",
    "timestamp": "2025-01-09T10:05:00Z"
  }
}
```

### POST /status/{uploadId}/cancel

Cancel an in-progress processing operation.

#### Parameters

| Parameter | Type | Location | Required | Description |
|-----------|------|----------|----------|-------------|
| uploadId | string | path | Yes | Unique identifier for the upload operation |

#### Request Example

```http
POST /status/550e8400-e29b-41d4-a716-446655440000/cancel
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json
```

#### Response Format

```json
{
  "uploadId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "cancelled",
  "message": "Processing cancellation requested",
  "timestamp": "2025-01-09T10:03:00Z"
}
```

#### Response Codes

| Code | Description |
|------|-------------|
| 200 | Success - Cancellation requested |
| 400 | Bad Request - Cannot cancel completed or already cancelled operation |
| 401 | Unauthorized - Invalid or missing JWT token |
| 404 | Not Found - Upload ID not found or expired |
| 500 | Internal Server Error - Server processing error |

## Data Models

### ProcessingStatus

Complete data model for processing status records.

```json
{
  "uploadId": {
    "type": "string",
    "description": "Unique identifier for the upload",
    "example": "550e8400-e29b-41d4-a716-446655440000"
  },
  "status": {
    "type": "string",
    "enum": ["uploading", "uploaded", "processing", "completed", "error", "cancelled"],
    "description": "Current processing status"
  },
  "stage": {
    "type": "string",
    "enum": ["file_upload", "file_processing", "batch_processing", "completed"],
    "description": "Current processing stage"
  },
  "progress": {
    "type": "object",
    "properties": {
      "totalBatches": {
        "type": "integer",
        "description": "Total number of batches to process"
      },
      "completedBatches": {
        "type": "integer",
        "description": "Number of batches completed"
      },
      "totalLeads": {
        "type": "integer",
        "description": "Total number of leads in file"
      },
      "processedLeads": {
        "type": "integer",
        "description": "Number of leads processed so far"
      },
      "percentage": {
        "type": "number",
        "description": "Completion percentage (0-100)"
      }
    }
  },
  "metadata": {
    "type": "object",
    "properties": {
      "fileName": {
        "type": "string",
        "description": "Original filename"
      },
      "fileSize": {
        "type": "integer",
        "description": "File size in bytes"
      },
      "startTime": {
        "type": "string",
        "format": "date-time",
        "description": "Processing start time (ISO 8601)"
      },
      "estimatedCompletion": {
        "type": "string",
        "format": "date-time",
        "description": "Estimated completion time (ISO 8601)"
      }
    }
  },
  "error": {
    "type": "object",
    "properties": {
      "message": {
        "type": "string",
        "description": "Human-readable error message"
      },
      "code": {
        "type": "string",
        "description": "Machine-readable error code"
      },
      "timestamp": {
        "type": "string",
        "format": "date-time",
        "description": "Error occurrence time (ISO 8601)"
      }
    }
  },
  "createdAt": {
    "type": "string",
    "format": "date-time",
    "description": "Status record creation time (ISO 8601)"
  },
  "updatedAt": {
    "type": "string",
    "format": "date-time",
    "description": "Last update time (ISO 8601)"
  },
  "ttl": {
    "type": "integer",
    "description": "TTL timestamp for automatic expiration (Unix timestamp)"
  }
}
```

### Error Response

Standard error response format for all endpoints.

```json
{
  "error": {
    "code": {
      "type": "string",
      "description": "Machine-readable error code"
    },
    "message": {
      "type": "string",
      "description": "Human-readable error message"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "Error occurrence time (ISO 8601)"
    }
  }
}
```

## Error Codes

### Authentication Errors

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `UNAUTHORIZED` | 401 | Missing or invalid JWT token |
| `TOKEN_EXPIRED` | 401 | JWT token has expired |
| `INVALID_TOKEN` | 401 | JWT token format is invalid |

### Request Errors

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `UPLOAD_NOT_FOUND` | 404 | Upload ID not found or expired |
| `INVALID_UPLOAD_ID` | 400 | Upload ID format is invalid |
| `CANNOT_CANCEL` | 400 | Operation cannot be cancelled (completed/cancelled) |

### Server Errors

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INTERNAL_ERROR` | 500 | Unexpected server error |
| `DATABASE_ERROR` | 500 | Database operation failed |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |

## Usage Examples

### JavaScript Frontend Integration

```javascript
class StatusAPI {
  constructor(apiBaseUrl, authToken) {
    this.baseUrl = apiBaseUrl;
    this.authToken = authToken;
  }

  async getStatus(uploadId) {
    const response = await fetch(`${this.baseUrl}/status/${uploadId}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${this.authToken}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Status API error: ${response.status}`);
    }

    return await response.json();
  }

  async cancelProcessing(uploadId) {
    const response = await fetch(`${this.baseUrl}/status/${uploadId}/cancel`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.authToken}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Cancel API error: ${response.status}`);
    }

    return await response.json();
  }
}

// Usage example
const statusAPI = new StatusAPI(API_BASE_URL, userToken);

// Poll for status updates
async function pollStatus(uploadId) {
  try {
    const status = await statusAPI.getStatus(uploadId);
    console.log('Current status:', status);
    
    if (status.status === 'completed') {
      console.log('Processing completed!');
      return status;
    } else if (status.status === 'error') {
      console.error('Processing failed:', status.error);
      return status;
    }
    
    // Continue polling
    setTimeout(() => pollStatus(uploadId), 2000);
  } catch (error) {
    console.error('Status polling error:', error);
  }
}
```

### Python Backend Integration

```python
import requests
import time

class StatusClient:
    def __init__(self, base_url, auth_token):
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer {auth_token}',
            'Content-Type': 'application/json'
        }
    
    def get_status(self, upload_id):
        """Get current processing status"""
        response = requests.get(
            f'{self.base_url}/status/{upload_id}',
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def cancel_processing(self, upload_id):
        """Cancel processing operation"""
        response = requests.post(
            f'{self.base_url}/status/{upload_id}/cancel',
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def wait_for_completion(self, upload_id, timeout=300):
        """Wait for processing to complete"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_status(upload_id)
            
            if status['status'] in ['completed', 'error', 'cancelled']:
                return status
            
            time.sleep(2)
        
        raise TimeoutError(f'Processing timeout after {timeout} seconds')

# Usage example
client = StatusClient(API_BASE_URL, auth_token)
status = client.wait_for_completion(upload_id)
print(f'Final status: {status["status"]}')
```

## Rate Limiting

### Polling Guidelines
- **Recommended Frequency**: Poll every 2-3 seconds during active processing
- **Backoff Strategy**: Increase interval for long-running operations
- **Maximum Frequency**: No more than once per second
- **Timeout**: Stop polling after 30 minutes of inactivity

### Rate Limits
- **Per User**: 100 requests per minute
- **Per Upload**: 1000 total requests per upload ID
- **Burst Limit**: 10 requests per second for short bursts

## Best Practices

### Frontend Implementation
1. **Exponential Backoff**: Implement backoff for failed requests
2. **Error Handling**: Handle all error codes gracefully
3. **User Feedback**: Show clear status messages to users
4. **Cleanup**: Stop polling when user navigates away

### Backend Integration
1. **Authentication**: Always validate JWT tokens
2. **Caching**: Cache status responses briefly to reduce load
3. **Monitoring**: Log API usage and error rates
4. **Timeouts**: Set appropriate request timeouts

### Security Considerations
1. **Token Validation**: Verify JWT tokens on every request
2. **Access Control**: Users can only access their own upload status
3. **Data Sanitization**: Sanitize all input parameters
4. **Rate Limiting**: Implement rate limiting to prevent abuse

## Monitoring and Debugging

### CloudWatch Metrics
- **Request Count**: Total API requests per endpoint
- **Error Rate**: Percentage of failed requests
- **Response Time**: Average response latency
- **Authentication Failures**: Failed authentication attempts

### Logging
- **Request Logs**: All API requests with timestamps
- **Error Logs**: Detailed error information
- **Performance Logs**: Response times and database query performance
- **Security Logs**: Authentication and authorization events

### Debugging Tips
1. **Check Authentication**: Verify JWT token is valid and not expired
2. **Validate Upload ID**: Ensure upload ID exists and hasn't expired (24-hour TTL)
3. **Monitor Logs**: Check CloudWatch logs for detailed error information
4. **Test Connectivity**: Verify network connectivity to API Gateway

This API documentation provides comprehensive information for integrating with the processing status system, enabling real-time monitoring and control of file processing operations.