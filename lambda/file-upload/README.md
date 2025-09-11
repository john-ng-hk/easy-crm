# File Upload Lambda Function

This Lambda function generates presigned S3 URLs for secure file uploads in the Lead Management System.

## Purpose

- Generates presigned S3 URLs for CSV and Excel file uploads
- Validates file types and sizes before generating URLs
- Provides secure, time-limited upload URLs to prevent unauthorized access
- Handles error cases gracefully with proper HTTP status codes

## Supported File Types

- CSV files (`.csv`) - `text/csv`
- Excel files (`.xlsx`) - `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- Legacy Excel files (`.xls`) - `application/vnd.ms-excel`

## Configuration

### Environment Variables

- `UPLOAD_BUCKET` - S3 bucket name for file uploads (required)
- `MAX_FILE_SIZE_MB` - Maximum file size in MB (default: 10)
- `PRESIGNED_URL_EXPIRATION` - URL expiration time in seconds (default: 3600)

### IAM Permissions Required

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:PutObjectAcl"
            ],
            "Resource": "arn:aws:s3:::your-upload-bucket/*"
        }
    ]
}
```

## API Usage

### Request

```http
POST /upload
Content-Type: application/json

{
    "fileName": "leads.csv",
    "fileType": "text/csv",
    "fileSize": 1024000
}
```

### Successful Response (200)

```json
{
    "uploadUrl": "https://s3.amazonaws.com/bucket/presigned-url",
    "fileKey": "uploads/uuid/leads.csv",
    "fileId": "uuid-string",
    "expiresIn": 3600,
    "maxFileSize": 10485760,
    "supportedTypes": [
        "text/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ]
}
```

### Error Response (400/500)

```json
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "fileName is required",
        "timestamp": "2024-01-01T12:00:00Z",
        "requestId": "request-id"
    }
}
```

## File Upload Process

1. Client calls this Lambda function with file metadata
2. Function validates file type and size
3. Function generates unique file key with UUID
4. Function creates presigned S3 URL with metadata
5. Client uploads file directly to S3 using presigned URL
6. S3 triggers lead-splitter Lambda function for processing

## Error Handling

### Validation Errors (400)
- Missing required fields (`fileName`, `fileSize`)
- Invalid file type (not CSV/Excel)
- File size exceeds limit
- Invalid file name characters

### Server Errors (500)
- S3 bucket not found
- Insufficient S3 permissions
- AWS service errors

## Security Features

- File type validation prevents malicious uploads
- File size limits prevent abuse
- Presigned URLs expire after configured time
- Unique file keys prevent conflicts
- Dangerous file name characters are rejected

## Testing

Run unit tests:
```bash
python -m pytest tests/unit/test_file_upload.py -v
```

Run integration tests:
```bash
python -m pytest tests/integration/test_file_upload_integration.py -v
```

## Dependencies

- `boto3` - AWS SDK for Python
- `botocore` - Low-level AWS service access

## File Structure

```
lambda/file-upload/
├── lambda_function.py    # Main Lambda handler
├── requirements.txt      # Python dependencies
└── README.md            # This documentation
```