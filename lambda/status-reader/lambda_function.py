import json
import os
import boto3
from botocore.exceptions import ClientError
import logging
import sys
from datetime import datetime

# Add shared modules to path
sys.path.append('/opt/python')
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from status_service import ProcessingStatusService
from atomic_status_service import AtomicStatusService, StatusServiceError, StatusNotFoundError
from error_handling import lambda_handler_wrapper, create_error_response, create_success_response

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize status service (will be initialized in lambda_handler)
status_service = None

@lambda_handler_wrapper
def lambda_handler(event, context):
    """
    Lambda function to retrieve processing status by uploadId and handle cancellation requests.
    """
    global status_service
    
    # Initialize status service if not already done
    if status_service is None:
        table_name = os.environ.get('PROCESSING_STATUS_TABLE', 'ProcessingStatus')
        status_service = AtomicStatusService(table_name=table_name)
    
    # Handle OPTIONS request for CORS
    if event.get('httpMethod') == 'OPTIONS':
        return create_success_response({}, 200)
    
    # Extract uploadId from path parameters
    path_params = event.get('pathParameters') or {}
    upload_id = path_params.get('uploadId')
    
    if not upload_id:
        logger.warning("Missing uploadId parameter in request")
        return create_error_response(
            Exception("Missing uploadId parameter. Please provide a valid upload ID."),
            context.aws_request_id if context else None
        )
    
    # Handle different HTTP methods
    http_method = event.get('httpMethod', 'GET')
    
    if http_method == 'GET':
        return handle_get_status(upload_id, context)
    elif http_method == 'POST':
        # Check if this is a cancel request
        resource_path = event.get('resource', '')
        if '/cancel' in resource_path:
            return handle_cancel_processing(upload_id, context)
        elif '/force-complete' in resource_path:
            return handle_force_completion(upload_id, context)
        else:
            logger.warning(f"Unsupported POST endpoint for uploadId: {upload_id}")
            return create_error_response(
                Exception("Unsupported POST endpoint"),
                context.aws_request_id if context else None
            )
    elif http_method == 'PUT':
        return handle_update_status(upload_id, event, context)
    else:
        logger.warning(f"Unsupported HTTP method: {http_method}")
        return create_error_response(
            Exception(f"Unsupported HTTP method: {http_method}"),
            context.aws_request_id if context else None
        )


def handle_get_status(upload_id: str, context):
    """
    Handle GET request to retrieve processing status.
    
    Args:
        upload_id: Upload ID to get status for
        context: Lambda context
        
    Returns:
        API Gateway response
    """
    logger.info(f"Retrieving status for uploadId: {upload_id}")
    
    try:
        # Get status using the enhanced status service
        status_data = status_service.get_status(upload_id)
        
        # Enhance status response with user-friendly information
        enhanced_status = enhance_status_response(status_data)
        
        logger.info(f"Successfully retrieved status for uploadId: {upload_id}")
        return create_success_response(enhanced_status)
        
    except StatusNotFoundError as e:
        logger.warning(f"Status not found for uploadId: {upload_id}")
        return create_error_response(e, context.aws_request_id if context else None)
        
    except StatusServiceError as e:
        logger.error(f"Status service error for uploadId {upload_id}: {e.message}")
        return create_error_response(e, context.aws_request_id if context else None)
        
    except Exception as e:
        logger.error(f"Unexpected error retrieving status for uploadId {upload_id}: {str(e)}")
        return create_error_response(e, context.aws_request_id if context else None)


def handle_update_status(upload_id: str, event, context):
    """
    Handle PUT request to update processing status.
    
    Args:
        upload_id: Upload ID to update status for
        event: Lambda event with request body
        context: Lambda context
        
    Returns:
        API Gateway response
    """
    logger.info(f"Updating status for uploadId: {upload_id}")
    
    try:
        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)
        
        # Extract status update parameters
        new_status = body.get('status')
        new_stage = body.get('stage')
        progress = body.get('progress')
        metadata = body.get('metadata')
        
        if not new_status:
            logger.warning(f"Missing status parameter in update request for uploadId: {upload_id}")
            return create_error_response(
                Exception("Missing 'status' parameter in request body"),
                context.aws_request_id if context else None,
                status_code=400
            )
        
        # Update status using the status service
        updated_status = status_service.update_status(
            upload_id=upload_id,
            status=new_status,
            stage=new_stage,
            progress=progress,
            metadata=metadata
        )
        
        # Enhance status response with user-friendly information
        enhanced_status = enhance_status_response(updated_status)
        
        logger.info(f"Successfully updated status for uploadId: {upload_id} to {new_status}")
        return create_success_response(enhanced_status)
        
    except StatusNotFoundError as e:
        logger.warning(f"Status not found for uploadId: {upload_id}")
        return create_error_response(e, context.aws_request_id if context else None, status_code=404)
        
    except StatusServiceError as e:
        logger.error(f"Status service error for uploadId {upload_id}: {e.message}")
        return create_error_response(e, context.aws_request_id if context else None)
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in request body for uploadId {upload_id}: {str(e)}")
        return create_error_response(
            Exception("Invalid JSON in request body"),
            context.aws_request_id if context else None,
            status_code=400
        )
        
    except Exception as e:
        logger.error(f"Unexpected error updating status for uploadId {upload_id}: {str(e)}")
        return create_error_response(e, context.aws_request_id if context else None)


def handle_cancel_processing(upload_id: str, context):
    """
    Handle POST request to cancel processing.
    
    Args:
        upload_id: Upload ID to cancel processing for
        context: Lambda context
        
    Returns:
        API Gateway response
    """
    logger.info(f"Cancelling processing for uploadId: {upload_id}")
    
    try:
        # Get current status to validate cancellation is possible
        current_status = status_service.get_status(upload_id)
        current_status_value = current_status.get('status')
        
        # Check if processing can be cancelled
        if current_status_value in ['completed', 'error', 'cancelled']:
            logger.warning(f"Cannot cancel processing for uploadId {upload_id}: already in final state '{current_status_value}'")
            return create_error_response(
                Exception(f"Cannot cancel processing - already {current_status_value}"),
                context.aws_request_id if context else None,
                status_code=409  # Conflict
            )
        
        # Cancel the processing
        cancelled_status = cancel_processing_workflow(upload_id, current_status)
        
        # Enhance response with user-friendly information
        enhanced_status = enhance_status_response(cancelled_status)
        
        logger.info(f"Successfully cancelled processing for uploadId: {upload_id}")
        return create_success_response(enhanced_status)
        
    except StatusNotFoundError as e:
        logger.warning(f"Status not found for uploadId: {upload_id}")
        return create_error_response(e, context.aws_request_id if context else None, status_code=404)
        
    except StatusServiceError as e:
        logger.error(f"Status service error for uploadId {upload_id}: {e.message}")
        return create_error_response(e, context.aws_request_id if context else None)
        
    except Exception as e:
        logger.error(f"Unexpected error cancelling processing for uploadId {upload_id}: {str(e)}")
        return create_error_response(e, context.aws_request_id if context else None)


def handle_force_completion(upload_id: str, context):
    """
    Handle POST request to force completion of stuck processing.
    
    This endpoint checks if processing is stuck (e.g., 13/14 batches completed
    but status is still 'processing') and forces completion if appropriate.
    
    Args:
        upload_id: Upload ID to force completion for
        context: Lambda context
        
    Returns:
        API Gateway response
    """
    logger.info(f"Checking for stuck processing and forcing completion for uploadId: {upload_id}")
    
    try:
        # Get current status with completion analysis
        current_status = status_service.get_batch_completion_status(upload_id)
        analysis = current_status.get('completion_analysis', {})
        
        # Check if processing is actually stuck
        if not analysis.get('is_stuck') and current_status.get('status') == 'completed':
            logger.info(f"Processing for uploadId {upload_id} is already completed - no action needed")
            enhanced_status = enhance_status_response(current_status)
            return create_success_response({
                'message': 'Processing is already completed',
                'status': enhanced_status,
                'action_taken': 'none'
            })
        
        # Check if processing can be force completed
        progress = current_status.get('progress', {})
        completed_batches = progress.get('completedBatches', 0)
        total_batches = progress.get('totalBatches', 0)
        
        if total_batches == 0:
            logger.warning(f"Cannot force completion for uploadId {upload_id}: no batches configured")
            return create_error_response(
                Exception("Cannot force completion - no batches configured"),
                context.aws_request_id if context else None,
                status_code=400  # Bad Request
            )
        
        if completed_batches < total_batches - 1:
            logger.warning(f"Cannot force completion for uploadId {upload_id}: too many batches remaining ({completed_batches}/{total_batches})")
            return create_error_response(
                Exception(f"Cannot force completion - too many batches remaining ({completed_batches}/{total_batches}). Force completion is only allowed when stuck at the last batch."),
                context.aws_request_id if context else None,
                status_code=400  # Bad Request
            )
        
        # Force completion
        logger.warning(f"Forcing completion for stuck processing: uploadId {upload_id}, batches: {completed_batches}/{total_batches}")
        forced_status = status_service.force_completion_if_stuck(upload_id)
        
        # Enhance response with user-friendly information
        enhanced_status = enhance_status_response(forced_status)
        
        action_message = f"Forced completion: {completed_batches}/{total_batches} batches"
        if forced_status.get('metadata', {}).get('forcedCompletion'):
            action_message += " (recovery applied)"
        
        logger.info(f"Successfully forced completion for uploadId: {upload_id}")
        return create_success_response({
            'message': 'Processing completion forced successfully',
            'status': enhanced_status,
            'action_taken': action_message,
            'recovery_applied': bool(forced_status.get('metadata', {}).get('forcedCompletion'))
        })
        
    except StatusNotFoundError as e:
        logger.warning(f"Status not found for uploadId: {upload_id}")
        return create_error_response(e, context.aws_request_id if context else None, status_code=404)
        
    except StatusServiceError as e:
        logger.error(f"Status service error for uploadId {upload_id}: {e.message}")
        return create_error_response(e, context.aws_request_id if context else None)
        
    except Exception as e:
        logger.error(f"Unexpected error forcing completion for uploadId {upload_id}: {str(e)}")
        return create_error_response(e, context.aws_request_id if context else None)


def enhance_status_response(status_data: dict) -> dict:
    """
    Enhance status response with user-friendly information and recovery options.
    
    Args:
        status_data: Raw status data from the service
        
    Returns:
        Enhanced status response
    """
    enhanced = status_data.copy()
    
    # Add user-friendly status messages
    enhanced['userMessage'] = get_user_friendly_message(status_data)
    
    # Add recovery information for error states
    if status_data.get('status') == 'error':
        enhanced['recovery'] = get_recovery_options(status_data)
    
    # Add progress indicators
    if status_data.get('progress'):
        enhanced['progressIndicators'] = get_progress_indicators(status_data['progress'])
    
    # Add estimated completion information
    if status_data.get('status') == 'processing':
        enhanced['estimatedCompletion'] = get_estimated_completion(status_data)
    
    return enhanced


def get_user_friendly_message(status_data: dict) -> str:
    """
    Generate user-friendly status message.
    
    Args:
        status_data: Status data
        
    Returns:
        User-friendly message
    """
    status = status_data.get('status', 'unknown')
    stage = status_data.get('stage', '')
    progress = status_data.get('progress', {})
    error = status_data.get('error', {})
    
    if status == 'uploading':
        return "Your file is being uploaded to our servers..."
    elif status == 'uploaded':
        return "File uploaded successfully! Processing will begin shortly."
    elif status == 'processing':
        if stage == 'file_processing':
            return "Reading and validating your file contents..."
        elif stage == 'batch_processing':
            completed = progress.get('completedBatches', 0)
            total = progress.get('totalBatches', 0)
            if total > 0:
                return f"Processing your leads... ({completed}/{total} batches completed)"
            else:
                return "Processing your leads through AI standardization..."
        else:
            return "Processing your leads..."
    elif status == 'completed':
        total_leads = progress.get('processedLeads', 0)
        created_leads = progress.get('createdLeads', 0)
        updated_leads = progress.get('updatedLeads', 0)
        
        if created_leads > 0 and updated_leads > 0:
            return f"Successfully processed {total_leads} leads! ({created_leads} new, {updated_leads} updated)"
        elif total_leads > 0:
            return f"Successfully processed {total_leads} leads!"
        else:
            return "Processing completed successfully!"
    elif status == 'error':
        error_message = error.get('message', 'An error occurred during processing')
        if error.get('recoverable', False):
            return f"{error_message} (Recovery options available)"
        else:
            return error_message
    elif status == 'cancelled':
        return "Processing was cancelled by user request."
    else:
        return "Processing status unknown. Please contact support if this persists."


def get_recovery_options(status_data: dict) -> dict:
    """
    Get recovery options for error states.
    
    Args:
        status_data: Status data with error information
        
    Returns:
        Recovery options
    """
    error = status_data.get('error', {})
    error_code = error.get('code', '')
    recoverable = error.get('recoverable', False)
    retry_after = error.get('retryAfter')
    
    recovery_options = {
        'available': recoverable,
        'options': []
    }
    
    if not recoverable:
        recovery_options['message'] = "This error cannot be automatically recovered. Please try uploading your file again."
        return recovery_options
    
    # Add specific recovery options based on error type
    if error_code in ['NETWORK_ERROR', 'TIMEOUT_ERROR']:
        recovery_options['options'].append({
            'type': 'retry',
            'label': 'Retry Processing',
            'description': 'Retry the processing operation',
            'retryAfter': retry_after
        })
    elif error_code in ['API_ERROR', 'EXTERNAL_SERVICE_ERROR']:
        recovery_options['options'].append({
            'type': 'retry',
            'label': 'Retry with Backoff',
            'description': 'Retry processing with increased delay',
            'retryAfter': retry_after or 60
        })
    elif error_code == 'VALIDATION_ERROR':
        recovery_options['options'].append({
            'type': 'reupload',
            'label': 'Upload Corrected File',
            'description': 'Please correct the file format and upload again'
        })
    
    if not recovery_options['options']:
        recovery_options['options'].append({
            'type': 'manual',
            'label': 'Contact Support',
            'description': 'Contact support for manual recovery assistance'
        })
    
    return recovery_options


def get_progress_indicators(progress_data: dict) -> dict:
    """
    Get enhanced progress indicators.
    
    Args:
        progress_data: Progress data
        
    Returns:
        Enhanced progress indicators
    """
    indicators = {
        'percentage': progress_data.get('percentage', 0),
        'stages': []
    }
    
    # Define processing stages
    stages = [
        {'name': 'File Upload', 'key': 'file_upload'},
        {'name': 'File Processing', 'key': 'file_processing'},
        {'name': 'Batch Processing', 'key': 'batch_processing'},
        {'name': 'Completed', 'key': 'completed'}
    ]
    
    current_stage = progress_data.get('stage', 'file_upload')
    
    for i, stage in enumerate(stages):
        stage_info = {
            'name': stage['name'],
            'status': 'pending'
        }
        
        if stage['key'] == current_stage:
            stage_info['status'] = 'active'
        elif i < stages.index(next(s for s in stages if s['key'] == current_stage)):
            stage_info['status'] = 'completed'
        
        indicators['stages'].append(stage_info)
    
    return indicators


def get_estimated_completion(status_data: dict) -> dict:
    """
    Get estimated completion information.
    
    Args:
        status_data: Status data
        
    Returns:
        Estimated completion information
    """
    progress = status_data.get('progress', {})
    metadata = status_data.get('metadata', {})
    
    completion_info = {}
    
    # Use progress-based estimates if available
    if progress.get('estimatedRemainingSeconds'):
        completion_info['remainingSeconds'] = progress['estimatedRemainingSeconds']
        completion_info['showEstimate'] = progress.get('showEstimates', False)
    
    # Use metadata-based estimates as fallback
    elif metadata.get('estimatedCompletion'):
        from datetime import datetime
        try:
            estimated_time = datetime.fromisoformat(metadata['estimatedCompletion'].replace('Z', '+00:00'))
            now = datetime.now(estimated_time.tzinfo)
            remaining_seconds = max(0, int((estimated_time - now).total_seconds()))
            completion_info['remainingSeconds'] = remaining_seconds
            completion_info['showEstimate'] = remaining_seconds > 30
        except (ValueError, TypeError):
            pass
    
    return completion_info


def cancel_processing_workflow(upload_id: str, current_status: dict) -> dict:
    """
    Cancel the processing workflow for a given upload.
    
    This function handles cancellation by:
    1. Updating the status to 'cancelled'
    2. Attempting to purge remaining SQS messages for this upload
    3. Cleaning up any incomplete processing state
    
    Args:
        upload_id: Upload ID to cancel processing for
        current_status: Current status record
        
    Returns:
        Updated status record with cancellation information
        
    Raises:
        StatusServiceError: If cancellation fails
    """
    try:
        # Initialize SQS client for message purging
        sqs = boto3.client('sqs')
        queue_url = os.environ.get('SQS_QUEUE_URL')
        
        # Calculate partial completion information
        progress = current_status.get('progress', {})
        completed_batches = progress.get('completedBatches', 0)
        total_batches = progress.get('totalBatches', 0)
        processed_leads = progress.get('processedLeads', 0)
        
        # Create cancellation metadata
        cancellation_metadata = {
            'cancellationTime': datetime.utcnow().isoformat() + 'Z',
            'cancellationReason': 'User requested cancellation',
            'partialCompletion': {
                'batchesCompleted': completed_batches,
                'totalBatches': total_batches,
                'leadsProcessed': processed_leads,
                'completionPercentage': (completed_batches / total_batches * 100) if total_batches > 0 else 0
            }
        }
        
        # Update status to cancelled with partial completion info
        cancelled_status = status_service.update_status(
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
            metadata=cancellation_metadata
        )
        
        # Attempt to purge remaining SQS messages for this upload
        if queue_url:
            try:
                purge_upload_messages(sqs, queue_url, upload_id)
                logger.info(f"Successfully purged SQS messages for uploadId: {upload_id}")
            except Exception as e:
                logger.warning(f"Failed to purge SQS messages for uploadId {upload_id}: {str(e)}")
                # Don't fail the cancellation if message purging fails
        else:
            logger.warning("SQS_QUEUE_URL not configured, skipping message purging")
        
        logger.info(f"Processing cancelled for uploadId: {upload_id} (completed {completed_batches}/{total_batches} batches)")
        return cancelled_status
        
    except StatusServiceError:
        raise
    except Exception as e:
        logger.error(f"Error cancelling processing workflow: {str(e)}")
        raise StatusServiceError(f"Failed to cancel processing: {str(e)}")


def purge_upload_messages(sqs_client, queue_url: str, upload_id: str, max_messages: int = 100):
    """
    Attempt to purge SQS messages related to a specific upload.
    
    Note: This is a best-effort operation. Due to SQS's distributed nature,
    some messages may still be processed after cancellation.
    
    Args:
        sqs_client: Boto3 SQS client
        queue_url: SQS queue URL
        upload_id: Upload ID to purge messages for
        max_messages: Maximum number of messages to check (default: 100)
    """
    try:
        messages_purged = 0
        
        # Receive messages in batches and delete those matching the upload_id
        while messages_purged < max_messages:
            response = sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=10,  # Maximum allowed by SQS
                WaitTimeSeconds=1,  # Short polling to avoid delays
                MessageAttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            if not messages:
                break  # No more messages
            
            messages_to_delete = []
            
            for message in messages:
                try:
                    # Parse message body to check if it belongs to this upload
                    body = json.loads(message['Body'])
                    message_upload_id = body.get('uploadId') or body.get('file_key', '').split('/')[-1].split('.')[0]
                    
                    if message_upload_id == upload_id:
                        messages_to_delete.append({
                            'Id': message['MessageId'],
                            'ReceiptHandle': message['ReceiptHandle']
                        })
                        logger.debug(f"Marked message for deletion: {message['MessageId']}")
                    else:
                        # Return message to queue by not deleting it
                        # SQS will make it available again after visibility timeout
                        pass
                        
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to parse SQS message: {str(e)}")
                    # Skip malformed messages
                    continue
            
            # Delete messages that belong to this upload
            if messages_to_delete:
                try:
                    delete_response = sqs_client.delete_message_batch(
                        QueueUrl=queue_url,
                        Entries=messages_to_delete
                    )
                    
                    successful_deletes = len(delete_response.get('Successful', []))
                    failed_deletes = len(delete_response.get('Failed', []))
                    
                    messages_purged += successful_deletes
                    
                    if failed_deletes > 0:
                        logger.warning(f"Failed to delete {failed_deletes} messages for uploadId: {upload_id}")
                    
                    logger.debug(f"Deleted {successful_deletes} messages for uploadId: {upload_id}")
                    
                except Exception as e:
                    logger.error(f"Error deleting SQS messages: {str(e)}")
                    break
            
            # If we didn't find any messages for this upload in this batch, stop looking
            if not messages_to_delete:
                break
        
        logger.info(f"Purged {messages_purged} SQS messages for uploadId: {upload_id}")
        
    except Exception as e:
        logger.error(f"Error purging SQS messages for uploadId {upload_id}: {str(e)}")
        raise