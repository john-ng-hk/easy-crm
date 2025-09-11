"""
Error handling and logging utilities for Lambda functions.
Provides standardized error responses and logging configuration.
"""

import json
import logging
import traceback
from typing import Dict, Any, Optional
from datetime import datetime
import boto3
from botocore.exceptions import ClientError, BotoCoreError

# Configure logging
def setup_logging(level: str = 'INFO') -> logging.Logger:
    """
    Set up standardized logging configuration for Lambda functions.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger()
    
    # Clear existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create new handler
    handler = logging.StreamHandler()
    
    # Set format
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(name)s: %(message)s'
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper()))
    
    return logger

class LambdaError(Exception):
    """Base exception class for Lambda function errors."""
    
    def __init__(self, message: str, status_code: int = 500, error_code: str = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        super().__init__(self.message)

class ValidationError(LambdaError):
    """Exception for data validation errors."""
    
    def __init__(self, message: str, field: str = None):
        self.field = field
        super().__init__(message, status_code=400, error_code='VALIDATION_ERROR')

class PhoneValidationError(ValidationError):
    """Exception for phone number validation errors."""
    
    def __init__(self, message: str, phone_value: str = None):
        self.phone_value = phone_value
        super().__init__(message, field='phone')

class FileProcessingError(LambdaError):
    """Exception for file processing errors."""
    
    def __init__(self, message: str, file_name: str = None):
        self.file_name = file_name
        super().__init__(message, status_code=422, error_code='FILE_PROCESSING_ERROR')

class ExternalAPIError(LambdaError):
    """Exception for external API errors (e.g., DeepSeek)."""
    
    def __init__(self, message: str, api_name: str = None, retry_after: int = None):
        self.api_name = api_name
        self.retry_after = retry_after
        super().__init__(message, status_code=502, error_code='EXTERNAL_API_ERROR')

class DatabaseError(LambdaError):
    """Exception for database operation errors."""
    
    def __init__(self, message: str, operation: str = None):
        self.operation = operation
        super().__init__(message, status_code=500, error_code='DATABASE_ERROR')

class AuthenticationError(LambdaError):
    """Exception for authentication/authorization errors."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, status_code=401, error_code='AUTHENTICATION_ERROR')

class AuthorizationError(LambdaError):
    """Exception for authorization errors."""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, status_code=403, error_code='AUTHORIZATION_ERROR')

def create_error_response(error: Exception, request_id: str = None, status_code: int = None) -> Dict[str, Any]:
    """
    Create standardized error response for Lambda functions.
    
    Args:
        error: Exception that occurred
        request_id: AWS request ID for tracking
        status_code: Optional HTTP status code override
        
    Returns:
        Dict: Standardized error response
    """
    timestamp = datetime.utcnow().isoformat()
    
    if isinstance(error, LambdaError):
        final_status_code = status_code if status_code is not None else error.status_code
        return {
            'statusCode': final_status_code,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
            },
            'body': json.dumps({
                'error': {
                    'code': error.error_code,
                    'message': error.message,
                    'timestamp': timestamp,
                    'requestId': request_id
                }
            })
        }
    elif isinstance(error, ClientError):
        # AWS service errors
        error_code = error.response['Error']['Code']
        error_message = error.response['Error']['Message']
        
        # Map common AWS errors to appropriate HTTP status codes
        status_code_map = {
            'ValidationException': 400,
            'ResourceNotFoundException': 404,
            'ConditionalCheckFailedException': 409,
            'ProvisionedThroughputExceededException': 429,
            'ThrottlingException': 429,
            'AccessDeniedException': 403,
            'UnauthorizedOperation': 403
        }
        
        mapped_status_code = status_code_map.get(error_code, 500)
        final_status_code = status_code if status_code is not None else mapped_status_code
        
        return {
            'statusCode': final_status_code,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
            },
            'body': json.dumps({
                'error': {
                    'code': error_code,
                    'message': error_message,
                    'timestamp': timestamp,
                    'requestId': request_id
                }
            })
        }
    else:
        # Generic errors
        final_status_code = status_code if status_code is not None else 500
        return {
            'statusCode': final_status_code,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
            },
            'body': json.dumps({
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': str(error),
                    'timestamp': timestamp,
                    'requestId': request_id
                }
            })
        }

def create_success_response(data: Any, status_code: int = 200) -> Dict[str, Any]:
    """
    Create standardized success response for Lambda functions.
    
    Args:
        data: Response data to return
        status_code: HTTP status code
        
    Returns:
        Dict: Standardized success response
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps(data, default=str)  # default=str handles datetime objects
    }

def lambda_handler_wrapper(func):
    """
    Decorator to wrap Lambda handlers with standardized error handling.
    
    Args:
        func: Lambda handler function to wrap
        
    Returns:
        Wrapped function with error handling
    """
    def wrapper(event, context):
        logger = setup_logging()
        request_id = context.aws_request_id if context else None
        
        try:
            logger.info(f"Processing request: {request_id}")
            logger.debug(f"Event: {json.dumps(event, default=str)}")
            
            result = func(event, context)
            
            logger.info(f"Request completed successfully: {request_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing request {request_id}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return create_error_response(e, request_id)
    
    return wrapper

def retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1.0):
    """
    Retry function with exponential backoff.
    
    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        
    Returns:
        Function result or raises last exception
    """
    import time
    
    logger = logging.getLogger(__name__)
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Max retries ({max_retries}) exceeded for function {func.__name__}")
                raise
            
            delay = base_delay * (2 ** attempt)
            logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}, retrying in {delay}s: {str(e)}")
            time.sleep(delay)

def validate_jwt_token(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Validate JWT token from API Gateway event.
    
    Args:
        event: API Gateway event
        
    Returns:
        Optional[Dict]: User claims if valid, None otherwise
        
    Raises:
        AuthenticationError: If token is missing or invalid
    """
    # Check for Authorization header
    headers = event.get('headers', {})
    auth_header = headers.get('Authorization') or headers.get('authorization')
    
    if not auth_header:
        raise AuthenticationError("Authorization header missing")
    
    if not auth_header.startswith('Bearer '):
        raise AuthenticationError("Invalid authorization header format")
    
    token = auth_header[7:]  # Remove 'Bearer ' prefix
    
    if not token:
        raise AuthenticationError("JWT token missing")
    
    # In a real implementation, you would validate the JWT token here
    # For now, we'll assume the token is valid if present
    # This would typically involve:
    # 1. Verifying the token signature
    # 2. Checking expiration
    # 3. Validating issuer and audience
    
    # Mock user claims for development
    return {
        'sub': 'user123',
        'email': 'user@example.com',
        'cognito:username': 'testuser'
    }

def log_performance_metrics(func):
    """
    Decorator to log performance metrics for Lambda functions.
    
    Args:
        func: Function to monitor
        
    Returns:
        Wrapped function with performance logging
    """
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(__name__)
        start_time = datetime.utcnow()
        
        try:
            result = func(*args, **kwargs)
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            logger.info(f"Function {func.__name__} completed in {duration:.3f}s")
            
            return result
            
        except Exception as e:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            logger.error(f"Function {func.__name__} failed after {duration:.3f}s: {str(e)}")
            raise
    
    return wrapper