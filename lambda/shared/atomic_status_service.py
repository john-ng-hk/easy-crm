"""
Atomic Status Service - Provides atomic operations for batch completion tracking.

This service extends the ProcessingStatusService with atomic operations to prevent
race conditions when multiple batches complete simultaneously.
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

from status_service import ProcessingStatusService, StatusServiceError, StatusNotFoundError

logger = logging.getLogger(__name__)


class AtomicStatusService(ProcessingStatusService):
    """Extended status service with atomic batch completion operations."""
    
    def atomic_increment_batch_completion(self, upload_id: str, leads_processed: int = 0) -> Dict[str, Any]:
        """
        Atomically increment the completed batch count and check for completion.
        
        This method uses DynamoDB's atomic ADD operation to prevent race conditions
        when multiple Lambda instances are processing batches concurrently.
        
        Args:
            upload_id: Unique identifier for the upload
            leads_processed: Number of leads processed in this batch
            
        Returns:
            Updated status record with completion information
            
        Raises:
            StatusNotFoundError: If status record not found
            StatusServiceError: If atomic operation fails
        """
        self._validate_upload_id(upload_id)
        
        current_time = self._get_current_timestamp()
        ttl = self._calculate_ttl()
        
        # First, atomically increment the completed batches and processed leads
        try:
            response = self.dynamodb.update_item(
                TableName=self.table_name,
                Key={'uploadId': {'S': upload_id}},
                UpdateExpression="ADD progress.completedBatches :one, progress.processedLeads :leads SET updatedAt = :updated_at, #ttl = :ttl",
                ExpressionAttributeNames={'#ttl': 'ttl'},
                ExpressionAttributeValues={
                    ':one': {'N': '1'},
                    ':leads': {'N': str(leads_processed)},
                    ':updated_at': {'S': current_time},
                    ':ttl': {'N': str(ttl)}
                },
                ConditionExpression='attribute_exists(uploadId)',
                ReturnValues='ALL_NEW'
            )
            
            updated_record = response['Attributes']
            formatted_record = self._format_status_record(updated_record)
            
            # Check if we need to mark as completed
            progress = formatted_record.get('progress', {})
            completed_batches = progress.get('completedBatches', 0)
            total_batches = progress.get('totalBatches', 0)
            
            logger.info(f"Atomic increment for upload {upload_id}: {completed_batches}/{total_batches} batches completed")
            
            # If all batches are completed, update status to completed
            if completed_batches >= total_batches and total_batches > 0:
                try:
                    # Calculate final percentage
                    final_progress = progress.copy()
                    final_progress['percentage'] = 100.0
                    
                    completion_result = self.update_status(
                        upload_id=upload_id,
                        status='completed',
                        stage='completed',
                        progress=final_progress,
                        metadata={'completionTime': current_time}
                    )
                    
                    logger.info(f"Processing completed for upload {upload_id}: {completed_batches}/{total_batches} batches, {progress.get('processedLeads', 0)} leads processed")
                    return completion_result
                    
                except Exception as completion_error:
                    logger.error(f"Failed to mark upload {upload_id} as completed: {completion_error}")
                    # Return the incremented record even if completion marking fails
                    return formatted_record
            
            return formatted_record
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ConditionalCheckFailedException':
                raise StatusNotFoundError(upload_id)
            else:
                raise StatusServiceError(f"Atomic increment failed: {e.response['Error']['Message']}")
        except Exception as e:
            logger.error(f"Unexpected error in atomic increment: {e}")
            raise StatusServiceError(f"Atomic increment operation failed: {str(e)}")
    
    def get_batch_completion_status(self, upload_id: str) -> Dict[str, Any]:
        """
        Get the current batch completion status with additional completion metadata.
        
        Args:
            upload_id: Unique identifier for the upload
            
        Returns:
            Status record with completion analysis
        """
        status = self.get_status(upload_id)
        progress = status.get('progress', {})
        
        completed_batches = progress.get('completedBatches', 0)
        total_batches = progress.get('totalBatches', 0)
        
        # Add completion analysis
        status['completion_analysis'] = {
            'is_completed': completed_batches >= total_batches and total_batches > 0,
            'completion_percentage': (completed_batches / total_batches * 100) if total_batches > 0 else 0,
            'remaining_batches': max(0, total_batches - completed_batches),
            'is_stuck': completed_batches == total_batches - 1 and status.get('status') != 'completed'
        }
        
        return status
    
    def force_completion_if_stuck(self, upload_id: str) -> Dict[str, Any]:
        """
        Force completion if the processing appears to be stuck at the last batch.
        
        This is a recovery method for cases where the atomic increment worked
        but the completion status update failed.
        
        Args:
            upload_id: Unique identifier for the upload
            
        Returns:
            Updated status record
        """
        status = self.get_batch_completion_status(upload_id)
        analysis = status.get('completion_analysis', {})
        progress = status.get('progress', {})
        
        # Check if stuck (completed batches >= total batches but status is not completed)
        completed_batches = progress.get('completedBatches', 0)
        total_batches = progress.get('totalBatches', 0)
        current_status = status.get('status', '')
        
        is_stuck = (completed_batches >= total_batches and 
                   total_batches > 0 and 
                   current_status != 'completed')
        
        if is_stuck or analysis.get('is_stuck'):
            logger.warning(f"Forcing completion for stuck upload {upload_id}: {completed_batches}/{total_batches} batches, status: {current_status}")
            
            final_progress = progress.copy()
            final_progress['percentage'] = 100.0
            final_progress['completedBatches'] = total_batches
            
            return self.update_status(
                upload_id=upload_id,
                status='completed',
                stage='completed',
                progress=final_progress,
                metadata={
                    'completionTime': self._get_current_timestamp(),
                    'forcedCompletion': 1,  # Use 1 instead of True for DynamoDB compatibility
                    'forcedCompletionReason': f'Stuck at {completed_batches}/{total_batches} batches'
                }
            )
        
        return status


def create_atomic_status_service(table_name: str = None) -> AtomicStatusService:
    """
    Factory function to create an AtomicStatusService instance.
    
    Args:
        table_name: Optional table name override
        
    Returns:
        AtomicStatusService instance
    """
    return AtomicStatusService(table_name=table_name)