"""
Processing Status Service for tracking file upload and processing status.

This service manages the lifecycle of processing status records in DynamoDB,
including creation, updates, progress tracking, TTL management, and comprehensive
error handling with retry mechanisms.
"""

import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union, Callable
import boto3
from botocore.exceptions import ClientError, BotoCoreError
import logging

logger = logging.getLogger(__name__)


class StatusServiceError(Exception):
    """Base exception for ProcessingStatusService errors."""
    
    def __init__(self, message: str, error_code: str = None, retry_after: int = None):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.retry_after = retry_after
        super().__init__(self.message)


class StatusNotFoundError(StatusServiceError):
    """Exception raised when status record is not found."""
    
    def __init__(self, upload_id: str = None):
        self.upload_id = upload_id
        if upload_id:
            message = f"Status record not found for upload {upload_id}"
        else:
            message = "Status record not found"
        super().__init__(message, "STATUS_NOT_FOUND")


class StatusConflictError(StatusServiceError):
    """Exception raised when status record already exists."""
    
    def __init__(self, upload_id: str = None):
        self.upload_id = upload_id
        if upload_id:
            message = f"Status record already exists for upload {upload_id}"
        else:
            message = "Status record already exists"
        super().__init__(message, "STATUS_CONFLICT")


class StatusDatabaseError(StatusServiceError):
    """Exception raised for database operation errors."""
    
    def __init__(self, message: str, operation: str = None, retry_after: int = None):
        self.operation = operation
        super().__init__(message, "DATABASE_ERROR", retry_after)


class StatusValidationError(StatusServiceError):
    """Exception raised for validation errors."""
    
    def __init__(self, message: str, field: str = None):
        self.field = field
        super().__init__(message, "VALIDATION_ERROR")


class ProcessingStatusService:
    """Service for managing processing status records in DynamoDB."""
    
    def __init__(self, dynamodb_client=None, table_name: str = None):
        """
        Initialize the ProcessingStatusService.
        
        Args:
            dynamodb_client: Optional boto3 DynamoDB client
            table_name: Optional table name override
        """
        self.dynamodb = dynamodb_client or boto3.client('dynamodb')
        self.table_name = table_name or 'ProcessingStatus'
        
        # Retry configuration
        self.retry_config = {
            'max_retries': 3,
            'base_delay': 1.0,
            'max_delay': 30.0,
            'backoff_multiplier': 2.0
        }
    
    def _retry_with_backoff(self, operation: Callable, operation_name: str = None) -> Any:
        """
        Execute operation with exponential backoff retry logic.
        
        Args:
            operation: Function to execute with retry logic
            operation_name: Name of the operation for logging
            
        Returns:
            Result of the operation
            
        Raises:
            StatusServiceError: If all retry attempts fail
        """
        last_error = None
        operation_name = operation_name or operation.__name__
        
        for attempt in range(self.retry_config['max_retries'] + 1):
            try:
                return operation()
            except ClientError as e:
                last_error = e
                error_code = e.response['Error']['Code']
                
                # Don't retry certain errors
                if error_code in ['ConditionalCheckFailedException', 'ValidationException']:
                    logger.warning(f"Non-retryable error in {operation_name}: {error_code}")
                    # Pass operation context to help determine error type
                    context = 'create' if 'create' in operation_name else 'update'
                    raise self._convert_client_error(e, context)
                
                # Don't retry on final attempt
                if attempt == self.retry_config['max_retries']:
                    logger.error(f"Max retries exceeded for {operation_name}: {error_code}")
                    break
                
                # Calculate delay with exponential backoff
                delay = min(
                    self.retry_config['base_delay'] * (self.retry_config['backoff_multiplier'] ** attempt),
                    self.retry_config['max_delay']
                )
                
                logger.warning(f"Retrying {operation_name} in {delay}s (attempt {attempt + 1}/{self.retry_config['max_retries']}): {error_code}")
                time.sleep(delay)
                
            except StatusServiceError as e:
                # Don't retry StatusServiceError exceptions, they are already properly categorized
                logger.warning(f"StatusServiceError in {operation_name}: {e.message}")
                raise e
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error in {operation_name}: {str(e)}")
                break
        
        # Convert and raise the final error
        if isinstance(last_error, ClientError):
            context = 'create' if 'create' in operation_name else 'update'
            raise self._convert_client_error(last_error, context)
        else:
            raise StatusServiceError(f"Operation {operation_name} failed: {str(last_error)}")
    
    def _convert_client_error(self, error: ClientError, context: str = None) -> StatusServiceError:
        """
        Convert AWS ClientError to appropriate StatusServiceError.
        
        Args:
            error: AWS ClientError to convert
            context: Additional context to help determine error type
            
        Returns:
            StatusServiceError: Converted error
        """
        error_code = error.response['Error']['Code']
        error_message = error.response['Error']['Message']
        
        if error_code == 'ConditionalCheckFailedException':
            # Use context to determine if this is "already exists" or "not found"
            if context == 'create' or 'attribute_not_exists' in error_message.lower():
                return StatusConflictError()
            else:
                return StatusNotFoundError()
        elif error_code == 'ResourceNotFoundException':
            return StatusNotFoundError()
        elif error_code in ['ProvisionedThroughputExceededException', 'ThrottlingException']:
            return StatusDatabaseError(f"Database throttling: {error_message}", retry_after=5)
        elif error_code == 'ValidationException':
            return StatusValidationError(f"Validation error: {error_message}")
        else:
            return StatusDatabaseError(f"Database error ({error_code}): {error_message}")
    
    def _validate_upload_id(self, upload_id: str) -> None:
        """
        Validate upload ID format.
        
        Args:
            upload_id: Upload ID to validate
            
        Raises:
            StatusValidationError: If upload ID is invalid
        """
        if not upload_id or not isinstance(upload_id, str):
            raise StatusValidationError("Upload ID must be a non-empty string", "uploadId")
        
        if len(upload_id) > 255:
            raise StatusValidationError("Upload ID is too long (max 255 characters)", "uploadId")
        
        # Basic format validation (alphanumeric, hyphens, underscores)
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', upload_id):
            raise StatusValidationError("Upload ID contains invalid characters", "uploadId")
    
    def _validate_status_value(self, status: str) -> None:
        """
        Validate status value.
        
        Args:
            status: Status value to validate
            
        Raises:
            StatusValidationError: If status is invalid
        """
        valid_statuses = ['uploading', 'uploaded', 'processing', 'completed', 'error', 'cancelled']
        if status not in valid_statuses:
            raise StatusValidationError(
                f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}", 
                "status"
            )
    
    def _validate_stage_value(self, stage: str) -> None:
        """
        Validate stage value.
        
        Args:
            stage: Stage value to validate
            
        Raises:
            StatusValidationError: If stage is invalid
        """
        valid_stages = ['file_upload', 'file_processing', 'batch_processing', 'completed', 'cancelled']
        if stage not in valid_stages:
            raise StatusValidationError(
                f"Invalid stage '{stage}'. Must be one of: {', '.join(valid_stages)}", 
                "stage"
            )
        
    def _calculate_ttl(self, hours: int = 24) -> int:
        """
        Calculate TTL timestamp for auto-expiration.
        
        Args:
            hours: Number of hours from now for expiration (default: 24)
            
        Returns:
            Unix timestamp for TTL
        """
        expiration_time = datetime.utcnow() + timedelta(hours=hours)
        return int(expiration_time.timestamp())
    
    def _get_current_timestamp(self) -> str:
        """Get current ISO timestamp."""
        return datetime.utcnow().isoformat() + 'Z'
    
    def _calculate_progress_and_estimates(self, new_progress: Dict[str, Union[int, float]], 
                                        existing_status: Dict[str, Any], 
                                        current_time: str) -> Dict[str, Union[int, float, str]]:
        """
        Calculate progress percentage and estimated completion time.
        
        Args:
            new_progress: New progress data
            existing_status: Current status record
            current_time: Current timestamp
            
        Returns:
            Enhanced progress data with percentage and estimates
        """
        enhanced_progress = {}
        
        # Calculate percentage
        if 'totalBatches' in new_progress and 'completedBatches' in new_progress:
            total = new_progress['totalBatches']
            completed = new_progress['completedBatches']
            percentage = (completed / total * 100) if total > 0 else 0.0
            enhanced_progress['percentage'] = percentage
        
        # Calculate processing rate and estimated completion time
        if existing_status and 'metadata' in existing_status:
            start_time_str = existing_status['metadata'].get('startTime')
            if start_time_str and 'completedBatches' in new_progress and 'totalBatches' in new_progress:
                try:
                    start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                    current_dt = datetime.fromisoformat(current_time.replace('Z', '+00:00'))
                    
                    elapsed_seconds = (current_dt - start_time).total_seconds()
                    completed_batches = new_progress['completedBatches']
                    total_batches = new_progress['totalBatches']
                    
                    # Only calculate estimates if we have meaningful data and processing has been running for at least 5 seconds
                    if elapsed_seconds >= 5 and completed_batches > 0 and total_batches > completed_batches:
                        # Calculate processing rate (batches per second)
                        processing_rate = completed_batches / elapsed_seconds
                        
                        if processing_rate > 0:
                            # Calculate remaining batches and estimated time
                            remaining_batches = total_batches - completed_batches
                            estimated_remaining_seconds = remaining_batches / processing_rate
                            
                            # Add estimated completion time
                            estimated_completion = current_dt + timedelta(seconds=estimated_remaining_seconds)
                            enhanced_progress['estimatedCompletion'] = estimated_completion.isoformat() + 'Z'
                            enhanced_progress['estimatedRemainingSeconds'] = int(estimated_remaining_seconds)
                            enhanced_progress['processingRate'] = round(processing_rate, 4)
                            
                            # Only show estimates if processing is expected to take longer than 30 seconds total
                            total_estimated_seconds = elapsed_seconds + estimated_remaining_seconds
                            if total_estimated_seconds > 30:
                                enhanced_progress['showEstimates'] = 1  # Use 1 instead of True for DynamoDB compatibility
                            else:
                                enhanced_progress['showEstimates'] = 0  # Use 0 instead of False for DynamoDB compatibility
                        
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error calculating time estimates: {e}")
        
        return enhanced_progress
    
    def create_status(self, upload_id: str, file_name: str, file_size: int, 
                     initial_status: str = 'uploading') -> Dict[str, Any]:
        """
        Create initial processing status record with comprehensive error handling.
        
        Args:
            upload_id: Unique identifier for the upload
            file_name: Name of the uploaded file
            file_size: Size of the file in bytes
            initial_status: Initial status (default: 'uploading')
            
        Returns:
            Created status record
            
        Raises:
            StatusValidationError: If input parameters are invalid
            StatusConflictError: If status record already exists
            StatusDatabaseError: If database operation fails
        """
        # Validate inputs
        self._validate_upload_id(upload_id)
        self._validate_status_value(initial_status)
        
        if not file_name or not isinstance(file_name, str):
            raise StatusValidationError("File name must be a non-empty string", "fileName")
        
        if not isinstance(file_size, int) or file_size < 0:
            raise StatusValidationError("File size must be a non-negative integer", "fileSize")
        
        current_time = self._get_current_timestamp()
        ttl = self._calculate_ttl()
        
        status_record = {
            'uploadId': {'S': upload_id},
            'status': {'S': initial_status},
            'stage': {'S': 'file_upload'},
            'progress': {
                'M': {
                    'totalBatches': {'N': '0'},
                    'completedBatches': {'N': '0'},
                    'totalLeads': {'N': '0'},
                    'processedLeads': {'N': '0'},
                    'percentage': {'N': '0.0'}
                }
            },
            'metadata': {
                'M': {
                    'fileName': {'S': file_name},
                    'fileSize': {'N': str(file_size)},
                    'startTime': {'S': current_time}
                }
            },
            'createdAt': {'S': current_time},
            'updatedAt': {'S': current_time},
            'ttl': {'N': str(ttl)}
        }
        
        def create_operation():
            self.dynamodb.put_item(
                TableName=self.table_name,
                Item=status_record,
                ConditionExpression='attribute_not_exists(uploadId)'
            )
            return status_record
        
        try:
            created_record = self._retry_with_backoff(create_operation, "create_status")
            logger.info(f"Created status record for upload {upload_id}")
            return self._format_status_record(created_record)
        except StatusServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating status record: {e}")
            raise StatusServiceError(f"Failed to create status record: {str(e)}")
    
    def update_status(self, upload_id: str, status: str = None, stage: str = None, 
                     progress: Dict[str, Union[int, float]] = None, 
                     metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Update processing status record with comprehensive error handling.
        
        Args:
            upload_id: Unique identifier for the upload
            status: New status value (optional)
            stage: New stage value (optional)
            progress: Progress updates (optional)
            metadata: Metadata updates (optional)
            
        Returns:
            Updated status record
            
        Raises:
            StatusValidationError: If input parameters are invalid
            StatusNotFoundError: If status record not found
            StatusDatabaseError: If database operation fails
        """
        # Validate inputs
        self._validate_upload_id(upload_id)
        
        if status:
            self._validate_status_value(status)
        
        if stage:
            self._validate_stage_value(stage)
        
        current_time = self._get_current_timestamp()
        ttl = self._calculate_ttl()
        
        # Build update expression
        update_expression = "SET updatedAt = :updated_at, #ttl = :ttl"
        expression_attribute_names = {'#ttl': 'ttl'}
        expression_attribute_values = {
            ':updated_at': {'S': current_time},
            ':ttl': {'N': str(ttl)}
        }
        
        if status:
            update_expression += ", #status = :status"
            expression_attribute_names['#status'] = 'status'
            expression_attribute_values[':status'] = {'S': status}
        
        if stage:
            update_expression += ", stage = :stage"
            expression_attribute_values[':stage'] = {'S': stage}
        
        if progress:
            # Get existing status to calculate progress and estimates
            try:
                existing_status = self.get_status(upload_id)
                enhanced_progress = self._calculate_progress_and_estimates(
                    progress, existing_status, current_time
                )
                progress.update(enhanced_progress)
            except StatusNotFoundError:
                # If record doesn't exist, just calculate basic percentage
                if 'totalBatches' in progress and 'completedBatches' in progress:
                    total = progress['totalBatches']
                    completed = progress['completedBatches']
                    percentage = (completed / total * 100) if total > 0 else 0.0
                    progress['percentage'] = percentage
            
            progress_map = {}
            for key, value in progress.items():
                if isinstance(value, (int, float)):
                    progress_map[key] = {'N': str(value)}
                else:
                    progress_map[key] = {'S': str(value)}
            
            update_expression += ", progress = :progress"
            expression_attribute_values[':progress'] = {'M': progress_map}
        
        if metadata:
            # Get existing metadata first to merge
            try:
                existing = self.get_status(upload_id)
                existing_metadata = existing.get('metadata', {})
                existing_metadata.update(metadata)
                
                metadata_map = {}
                for key, value in existing_metadata.items():
                    if isinstance(value, (int, float)):
                        metadata_map[key] = {'N': str(value)}
                    else:
                        metadata_map[key] = {'S': str(value)}
                
                update_expression += ", metadata = :metadata"
                expression_attribute_values[':metadata'] = {'M': metadata_map}
                
            except StatusNotFoundError:
                # If record doesn't exist, we'll let the update fail
                pass
        
        def update_operation():
            response = self.dynamodb.update_item(
                TableName=self.table_name,
                Key={'uploadId': {'S': upload_id}},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ConditionExpression='attribute_exists(uploadId)',
                ReturnValues='ALL_NEW'
            )
            return response['Attributes']
        
        try:
            updated_record = self._retry_with_backoff(update_operation, "update_status")
            logger.info(f"Updated status for upload {upload_id}")
            return self._format_status_record(updated_record)
        except StatusServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating status record: {e}")
            raise StatusServiceError(f"Failed to update status record: {str(e)}")
    
    def get_status(self, upload_id: str) -> Dict[str, Any]:
        """
        Retrieve processing status record with comprehensive error handling.
        
        Args:
            upload_id: Unique identifier for the upload
            
        Returns:
            Status record
            
        Raises:
            StatusValidationError: If upload_id is invalid
            StatusNotFoundError: If status record not found
            StatusDatabaseError: If database operation fails
        """
        # Validate input
        self._validate_upload_id(upload_id)
        
        def get_operation():
            response = self.dynamodb.get_item(
                TableName=self.table_name,
                Key={'uploadId': {'S': upload_id}}
            )
            
            if 'Item' not in response:
                raise StatusNotFoundError(upload_id)
            
            return response['Item']
        
        try:
            status_record = self._retry_with_backoff(get_operation, "get_status")
            return self._format_status_record(status_record)
        except StatusServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting status record: {e}")
            raise StatusServiceError(f"Failed to get status record: {str(e)}")
    
    def set_error(self, upload_id: str, error_message: str, error_code: str = 'PROCESSING_ERROR', 
                  recoverable: bool = False, retry_after: int = None) -> Dict[str, Any]:
        """
        Set error status for processing record with enhanced error information.
        
        Args:
            upload_id: Unique identifier for the upload
            error_message: Error description
            error_code: Error code (default: 'PROCESSING_ERROR')
            recoverable: Whether the error is recoverable (default: False)
            retry_after: Seconds to wait before retry (optional)
            
        Returns:
            Updated status record with error information
            
        Raises:
            StatusValidationError: If input parameters are invalid
            StatusNotFoundError: If status record not found
            StatusDatabaseError: If database operation fails
        """
        # Validate inputs
        self._validate_upload_id(upload_id)
        
        if not error_message or not isinstance(error_message, str):
            raise StatusValidationError("Error message must be a non-empty string", "errorMessage")
        
        if not error_code or not isinstance(error_code, str):
            raise StatusValidationError("Error code must be a non-empty string", "errorCode")
        
        current_time = self._get_current_timestamp()
        ttl = self._calculate_ttl()
        
        error_info = {
            'message': {'S': error_message},
            'code': {'S': error_code},
            'timestamp': {'S': current_time},
            'recoverable': {'BOOL': recoverable}
        }
        
        if retry_after is not None:
            error_info['retryAfter'] = {'N': str(retry_after)}
        
        def set_error_operation():
            response = self.dynamodb.update_item(
                TableName=self.table_name,
                Key={'uploadId': {'S': upload_id}},
                UpdateExpression="SET #status = :status, #error = :error, updatedAt = :updated_at, #ttl = :ttl",
                ExpressionAttributeNames={
                    '#status': 'status',
                    '#error': 'error',
                    '#ttl': 'ttl'
                },
                ExpressionAttributeValues={
                    ':status': {'S': 'error'},
                    ':error': {'M': error_info},
                    ':updated_at': {'S': current_time},
                    ':ttl': {'N': str(ttl)}
                },
                ConditionExpression='attribute_exists(uploadId)',
                ReturnValues='ALL_NEW'
            )
            return response['Attributes']
        
        try:
            updated_record = self._retry_with_backoff(set_error_operation, "set_error")
            logger.error(f"Set error status for upload {upload_id}: {error_message} (code: {error_code}, recoverable: {recoverable})")
            return self._format_status_record(updated_record)
        except StatusServiceError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error setting error status: {e}")
            raise StatusServiceError(f"Failed to set error status: {str(e)}")
    
    def complete_processing(self, upload_id: str, total_leads: int, 
                           created_leads: int = None, updated_leads: int = None) -> Dict[str, Any]:
        """
        Mark processing as completed with enhanced completion information.
        
        Args:
            upload_id: Unique identifier for the upload
            total_leads: Total number of leads processed
            created_leads: Number of new leads created (optional)
            updated_leads: Number of existing leads updated (optional)
            
        Returns:
            Updated status record
            
        Raises:
            StatusValidationError: If input parameters are invalid
            StatusNotFoundError: If status record not found
            StatusDatabaseError: If database operation fails
        """
        # Validate inputs
        self._validate_upload_id(upload_id)
        
        if not isinstance(total_leads, int) or total_leads < 0:
            raise StatusValidationError("Total leads must be a non-negative integer", "totalLeads")
        
        if created_leads is not None and (not isinstance(created_leads, int) or created_leads < 0):
            raise StatusValidationError("Created leads must be a non-negative integer", "createdLeads")
        
        if updated_leads is not None and (not isinstance(updated_leads, int) or updated_leads < 0):
            raise StatusValidationError("Updated leads must be a non-negative integer", "updatedLeads")
        
        current_time = self._get_current_timestamp()
        
        # Get current progress to calculate final values
        try:
            current_status = self.get_status(upload_id)
            current_progress = current_status.get('progress', {})
            
            final_progress = {
                'totalBatches': current_progress.get('totalBatches', 0),
                'completedBatches': current_progress.get('totalBatches', 0),  # All batches completed
                'totalLeads': total_leads,
                'processedLeads': total_leads,
                'percentage': 100.0
            }
            
            # Add lead creation/update counts if provided
            if created_leads is not None:
                final_progress['createdLeads'] = created_leads
            
            if updated_leads is not None:
                final_progress['updatedLeads'] = updated_leads
            
            completion_metadata = {
                'estimatedCompletion': current_time,
                'completionTime': current_time
            }
            
            return self.update_status(
                upload_id=upload_id,
                status='completed',
                stage='completed',
                progress=final_progress,
                metadata=completion_metadata
            )
            
        except StatusNotFoundError:
            logger.error(f"Cannot complete processing - status record not found for upload {upload_id}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error completing processing: {e}")
            raise StatusServiceError(f"Failed to complete processing: {str(e)}")
    
    def cancel_processing(self, upload_id: str, cancellation_reason: str = 'User requested cancellation') -> Dict[str, Any]:
        """
        Cancel processing for a given upload.
        
        Args:
            upload_id: Unique identifier for the upload
            cancellation_reason: Reason for cancellation (default: 'User requested cancellation')
            
        Returns:
            Updated status record with cancellation information
            
        Raises:
            StatusValidationError: If input parameters are invalid
            StatusNotFoundError: If status record not found
            StatusDatabaseError: If database operation fails
        """
        # Validate inputs
        self._validate_upload_id(upload_id)
        
        if not cancellation_reason or not isinstance(cancellation_reason, str):
            raise StatusValidationError("Cancellation reason must be a non-empty string", "cancellationReason")
        
        current_time = self._get_current_timestamp()
        
        # Get current status to calculate partial completion
        try:
            current_status = self.get_status(upload_id)
            current_status_value = current_status.get('status')
            
            # Check if processing can be cancelled
            if current_status_value in ['completed', 'error', 'cancelled']:
                raise StatusValidationError(
                    f"Cannot cancel processing - already {current_status_value}",
                    "status"
                )
            
            progress = current_status.get('progress', {})
            completed_batches = progress.get('completedBatches', 0)
            total_batches = progress.get('totalBatches', 0)
            processed_leads = progress.get('processedLeads', 0)
            
            # Create cancellation metadata
            cancellation_metadata = {
                'cancellationTime': current_time,
                'cancellationReason': cancellation_reason,
                'partialCompletion': {
                    'batchesCompleted': completed_batches,
                    'totalBatches': total_batches,
                    'leadsProcessed': processed_leads,
                    'completionPercentage': (completed_batches / total_batches * 100) if total_batches > 0 else 0
                }
            }
            
            # Update existing metadata
            existing_metadata = current_status.get('metadata', {})
            existing_metadata.update(cancellation_metadata)
            
            # Update status to cancelled
            return self.update_status(
                upload_id=upload_id,
                status='cancelled',
                stage='cancelled',
                progress={
                    'totalBatches': total_batches,
                    'completedBatches': completed_batches,
                    'totalLeads': progress.get('totalLeads', 0),
                    'processedLeads': processed_leads,
                    'percentage': (completed_batches / total_batches * 100) if total_batches > 0 else 0
                },
                metadata=existing_metadata
            )
            
        except StatusNotFoundError:
            logger.error(f"Cannot cancel processing - status record not found for upload {upload_id}")
            raise
        except StatusValidationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error cancelling processing: {e}")
            raise StatusServiceError(f"Failed to cancel processing: {str(e)}")
    
    def recover_from_error(self, upload_id: str, recovery_action: str = None) -> Dict[str, Any]:
        """
        Attempt to recover from an error state.
        
        Args:
            upload_id: Unique identifier for the upload
            recovery_action: Description of recovery action taken (optional)
            
        Returns:
            Updated status record
            
        Raises:
            StatusValidationError: If input parameters are invalid
            StatusNotFoundError: If status record not found
            StatusDatabaseError: If database operation fails
        """
        # Validate inputs
        self._validate_upload_id(upload_id)
        
        # Get current status to check if recovery is possible
        current_status = self.get_status(upload_id)
        
        if current_status.get('status') != 'error':
            raise StatusValidationError("Can only recover from error status", "status")
        
        error_info = current_status.get('error', {})
        if not error_info.get('recoverable', False):
            raise StatusValidationError("Error is not recoverable", "error")
        
        # Clear error and reset to processing state
        current_time = self._get_current_timestamp()
        
        recovery_metadata = {
            'recoveryAttempt': current_time,
            'recoveryAction': recovery_action or 'Manual recovery attempt'
        }
        
        return self.update_status(
            upload_id=upload_id,
            status='processing',
            stage='batch_processing',
            metadata=recovery_metadata
        )
    
    def _format_status_record(self, dynamodb_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format DynamoDB item to standard Python dictionary.
        
        Args:
            dynamodb_item: Raw DynamoDB item
            
        Returns:
            Formatted status record
        """
        def parse_dynamodb_value(value):
            """Parse DynamoDB attribute value to Python value."""
            if 'S' in value:
                return value['S']
            elif 'N' in value:
                # Try to return as int if possible, otherwise float
                num_str = value['N']
                if '.' in num_str:
                    return float(num_str)
                else:
                    return int(num_str)
            elif 'M' in value:
                return {k: parse_dynamodb_value(v) for k, v in value['M'].items()}
            elif 'L' in value:
                return [parse_dynamodb_value(item) for item in value['L']]
            elif 'BOOL' in value:
                return value['BOOL']
            elif 'NULL' in value:
                return None
            else:
                return value
        
        formatted = {}
        for key, value in dynamodb_item.items():
            formatted[key] = parse_dynamodb_value(value)
        
        return formatted