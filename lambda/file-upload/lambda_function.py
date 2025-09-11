"""
File Upload Lambda Function

Generates presigned S3 URLs for secure file uploads.
Validates file types (CSV/Excel only) and handles upload requests.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

import boto3
from botocore.exceptions import ClientError

# Import shared utilities
import sys
import os
sys.path.append('/opt/python')
sys.path.append('../shared')

# Try different import paths for different environments
try:
    from shared.error_handling import (
        lambda_handler_wrapper, 
        create_success_response, 
        ValidationError,
        LambdaError,
        setup_logging
    )
    from shared.validation import LeadValidator
    from shared.status_service import ProcessingStatusService
except ImportError:
    # For testing environment
    sys.path.append(os.path.join(os.path.dirname(__file__), '../shared'))
    from error_handling import (
        lambda_handler_wrapper, 
        create_success_response, 
        ValidationError,
        LambdaError,
        setup_logging
    )
    from validation import LeadValidator
    from status_service import ProcessingStatusService

# Initialize AWS clients (will be initialized in lambda_handler)
s3_client = None
dynamodb_client = None
status_service = None
logger = setup_logging()

# Environment variables
UPLOAD_BUCKET = os.environ.get('FILES_BUCKET')
PROCESSING_STATUS_TABLE = os.environ.get('PROCESSING_STATUS_TABLE')
MAX_FILE_SIZE_MB = int(os.environ.get('MAX_FILE_SIZE_MB', '10'))
PRESIGNED_URL_EXPIRATION = int(os.environ.get('PRESIGNED_URL_EXPIRATION', '3600'))

@lambda_handler_wrapper
def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda handler for file upload presigned URL generation.
    
    Expected input:
    {
        "fileName": "leads.csv",
        "fileType": "text/csv",
        "fileSize": 1024000
    }
    
    Returns:
    {
        "uploadUrl": "https://s3.amazonaws.com/...",
        "fileKey": "uploads/uuid/leads.csv",
        "uploadId": "uuid",
        "expiresIn": 3600
    }
    """
    global s3_client, dynamodb_client, status_service
    
    # Initialize AWS clients if not already done
    if s3_client is None:
        s3_client = boto3.client('s3')
        dynamodb_client = boto3.client('dynamodb')
        
        # Initialize status service if table is configured
        if PROCESSING_STATUS_TABLE:
            status_service = ProcessingStatusService(
                dynamodb_client=dynamodb_client,
                table_name=PROCESSING_STATUS_TABLE
            )
    
    logger.info("Processing file upload request")
    
    # Parse request body
    try:
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
    except json.JSONDecodeError:
        raise ValidationError("Invalid JSON in request body")
    
    # Extract and validate input parameters
    file_name = body.get('fileName')
    file_type = body.get('fileType')
    file_size = body.get('fileSize')
    
    if not file_name:
        raise ValidationError("fileName is required", field="fileName")
    
    if not file_size:
        raise ValidationError("fileSize is required", field="fileSize")
    
    try:
        file_size = int(file_size)
    except (ValueError, TypeError):
        raise ValidationError("fileSize must be a valid integer", field="fileSize")
    
    # Validate file type
    if not LeadValidator.validate_file_type(file_name, file_type):
        raise ValidationError(
            "Invalid file type. Only CSV and Excel files (.csv, .xlsx, .xls) are supported",
            field="fileType"
        )
    
    # Validate file size
    if not LeadValidator.validate_file_size(file_size, MAX_FILE_SIZE_MB):
        raise ValidationError(
            f"File size exceeds maximum limit of {MAX_FILE_SIZE_MB}MB",
            field="fileSize"
        )
    
    # Generate unique file key and upload ID
    file_id = str(uuid.uuid4())
    upload_id = str(uuid.uuid4())  # Separate upload ID for status tracking
    file_key = f"uploads/{file_id}/{file_name}"
    
    logger.info(f"Generating presigned URL for file: {file_key}, uploadId: {upload_id}")
    
    try:
        # Create initial status record if status service is available
        if status_service:
            try:
                status_service.create_status(
                    upload_id=upload_id,
                    file_name=file_name,
                    file_size=file_size
                )
                logger.info(f"Created initial status record for uploadId: {upload_id}")
            except Exception as e:
                logger.warning(f"Failed to create status record: {str(e)}")
                # Continue with upload even if status creation fails
        
        # Generate presigned URL for PUT operation
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': UPLOAD_BUCKET,
                'Key': file_key,
                'ContentType': file_type or 'application/octet-stream',
                'Metadata': {
                    'original-filename': file_name,
                    'upload-timestamp': datetime.now(timezone.utc).isoformat(),
                    'file-id': file_id,
                    'upload-id': upload_id  # Include upload ID in metadata
                }
            },
            ExpiresIn=PRESIGNED_URL_EXPIRATION
        )
        
        logger.info(f"Successfully generated presigned URL for file: {file_key}")
        
        return create_success_response({
            'uploadUrl': presigned_url,
            'fileKey': file_key,
            'fileId': file_id,
            'uploadId': upload_id,  # Return upload ID for status tracking
            'expiresIn': PRESIGNED_URL_EXPIRATION,
            'maxFileSize': MAX_FILE_SIZE_MB * 1024 * 1024,  # Return in bytes
            'supportedTypes': ['text/csv', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']
        })
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"S3 error generating presigned URL: {error_code}")
        
        if error_code == 'NoSuchBucket':
            raise LambdaError(
                "Upload bucket not found. Please contact system administrator.",
                status_code=500,
                error_code='BUCKET_NOT_FOUND'
            )
        elif error_code == 'AccessDenied':
            raise LambdaError(
                "Insufficient permissions to generate upload URL.",
                status_code=500,
                error_code='ACCESS_DENIED'
            )
        else:
            raise LambdaError(
                "Failed to generate upload URL. Please try again.",
                status_code=500,
                error_code='S3_ERROR'
            )
    
    except Exception as e:
        logger.error(f"Unexpected error generating presigned URL: {str(e)}")
        raise LambdaError(
            "An unexpected error occurred while processing your request.",
            status_code=500,
            error_code='INTERNAL_ERROR'
        )

def validate_upload_request(body: Dict[str, Any]) -> None:
    """
    Validate the upload request parameters.
    
    Args:
        body: Request body dictionary
        
    Raises:
        ValidationError: If validation fails
    """
    required_fields = ['fileName', 'fileSize']
    
    for field in required_fields:
        if field not in body or not body[field]:
            raise ValidationError(f"{field} is required", field=field)
    
    # Additional validation can be added here
    file_name = body['fileName']
    
    # Check for potentially dangerous file names
    dangerous_patterns = ['..', '/', '\\', '<', '>', ':', '"', '|', '?', '*']
    if any(pattern in file_name for pattern in dangerous_patterns):
        raise ValidationError(
            "File name contains invalid characters",
            field="fileName"
        )
    
    # Check file name length
    if len(file_name) > 255:
        raise ValidationError(
            "File name is too long (maximum 255 characters)",
            field="fileName"
        )

def get_file_extension(filename: str) -> str:
    """
    Extract file extension from filename.
    
    Args:
        filename: Name of the file
        
    Returns:
        str: File extension (including dot)
    """
    if '.' not in filename:
        return ''
    return filename.lower().split('.')[-1]

def generate_file_metadata(file_name: str, file_size: int, file_type: str = None) -> Dict[str, str]:
    """
    Generate metadata for S3 object.
    
    Args:
        file_name: Original file name
        file_size: File size in bytes
        file_type: MIME type of file
        
    Returns:
        Dict[str, str]: Metadata dictionary
    """
    return {
        'original-filename': file_name,
        'file-size': str(file_size),
        'content-type': file_type or 'application/octet-stream',
        'upload-timestamp': datetime.now(timezone.utc).isoformat(),
        'processing-status': 'pending'
    }