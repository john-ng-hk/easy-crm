"""
Comprehensive unit tests for the status system components.

This test suite covers all status system components including:
- ProcessingStatusService advanced functionality
- Status validation and error handling
- TTL management and expiration
- Progress calculation algorithms
- Error recovery mechanisms
"""

import pytest
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

# Import the service and exceptions
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../lambda/shared'))

from status_service import (
    ProcessingStatusService, 
    StatusServiceError, 
    StatusNotFoundError, 
    StatusConflictError,
    StatusDatabaseError,
    StatusValidationError
)


class TestProcessingStatusServiceAdvanced:
    """Advanced test cases for ProcessingStatusService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_dynamodb = Mock()
        self.service = ProcessingStatusService(
            dynamodb_client=self.mock_dynamodb,
            table_name='test-processing-status'
        )
    
    def test_validate_upload_id_valid_formats(self):
        """Test upload ID validation with various valid formats."""
        valid_upload_ids = [
            "test-upload-123",
            "upload_456",
            "UPLOAD789",
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "simple123",
            "test_upload_with_underscores",
            "test-upload-with-hyphens"
        ]
        
        for upload_id in valid_upload_ids:
            # Should not raise any exception
            self.service._validate_upload_id(upload_id)
    
    def test_validate_upload_id_invalid_formats(self):
        """Test upload ID validation with invalid formats."""
        invalid_upload_ids = [
            "",                    # Empty string
            None,                  # None value
            123,                   # Non-string
            "test upload",         # Contains space
            "test@upload",         # Contains special character
            "test.upload",         # Contains dot
            "test/upload",         # Contains slash
            "a" * 256,            # Too long (>255 characters)
            "test\nupload",       # Contains newline
            "test\tupload"        # Contains tab
        ]
        
        for upload_id in invalid_upload_ids:
            with pytest.raises(StatusValidationError):
                self.service._validate_upload_id(upload_id)
    
    def test_validate_status_value_all_valid_statuses(self):
        """Test status validation with all valid status values."""
        valid_statuses = ['uploading', 'uploaded', 'processing', 'completed', 'error', 'cancelled']
        
        for status in valid_statuses:
            # Should not raise any exception
            self.service._validate_status_value(status)
    
    def test_validate_status_value_invalid_statuses(self):
        """Test status validation with invalid status values."""
        invalid_statuses = [
            "invalid",
            "UPLOADING",  # Case sensitive
            "in_progress",
            "",
            None,
            123
        ]
        
        for status in invalid_statuses:
            with pytest.raises(StatusValidationError):
                self.service._validate_status_value(status)
    
    def test_validate_stage_value_all_valid_stages(self):
        """Test stage validation with all valid stage values."""
        valid_stages = ['file_upload', 'file_processing', 'batch_processing', 'completed', 'cancelled']
        
        for stage in valid_stages:
            # Should not raise any exception
            self.service._validate_stage_value(stage)
    
    def test_validate_stage_value_invalid_stages(self):
        """Test stage validation with invalid stage values."""
        invalid_stages = [
            "invalid_stage",
            "FILE_UPLOAD",  # Case sensitive
            "upload",
            "",
            None,
            123
        ]
        
        for stage in invalid_stages:
            with pytest.raises(StatusValidationError):
                self.service._validate_stage_value(stage)
    
    def test_retry_with_backoff_success_on_first_attempt(self):
        """Test retry mechanism when operation succeeds on first attempt."""
        mock_operation = Mock(return_value="success")
        
        result = self.service._retry_with_backoff(mock_operation, "test_operation")
        
        assert result == "success"
        assert mock_operation.call_count == 1
    
    def test_retry_with_backoff_success_after_retries(self):
        """Test retry mechanism when operation succeeds after retries."""
        mock_operation = Mock()
        # Fail twice, then succeed
        mock_operation.side_effect = [
            ClientError({'Error': {'Code': 'ThrottlingException'}}, 'TestOperation'),
            ClientError({'Error': {'Code': 'ThrottlingException'}}, 'TestOperation'),
            "success"
        ]
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = self.service._retry_with_backoff(mock_operation, "test_operation")
        
        assert result == "success"
        assert mock_operation.call_count == 3
    
    def test_retry_with_backoff_max_retries_exceeded(self):
        """Test retry mechanism when max retries are exceeded."""
        mock_operation = Mock()
        # Always fail with retryable error
        mock_operation.side_effect = ClientError(
            {'Error': {'Code': 'ThrottlingException', 'Message': 'Throttled'}}, 
            'TestOperation'
        )
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            with pytest.raises(StatusDatabaseError):
                self.service._retry_with_backoff(mock_operation, "test_operation")
        
        # Should try max_retries + 1 times (initial + retries)
        assert mock_operation.call_count == self.service.retry_config['max_retries'] + 1
    
    def test_retry_with_backoff_non_retryable_error(self):
        """Test retry mechanism with non-retryable errors."""
        mock_operation = Mock()
        # Non-retryable error
        mock_operation.side_effect = ClientError(
            {'Error': {'Code': 'ValidationException', 'Message': 'Invalid input'}}, 
            'TestOperation'
        )
        
        with pytest.raises(StatusValidationError):
            self.service._retry_with_backoff(mock_operation, "test_operation")
        
        # Should only try once for non-retryable errors
        assert mock_operation.call_count == 1
    
    def test_convert_client_error_conditional_check_failed_create_context(self):
        """Test ClientError conversion for ConditionalCheckFailedException in create context."""
        error = ClientError(
            {'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'Item already exists'}},
            'PutItem'
        )
        
        result = self.service._convert_client_error(error, 'create')
        
        assert isinstance(result, StatusConflictError)
    
    def test_convert_client_error_conditional_check_failed_update_context(self):
        """Test ClientError conversion for ConditionalCheckFailedException in update context."""
        error = ClientError(
            {'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'Item not found'}},
            'UpdateItem'
        )
        
        result = self.service._convert_client_error(error, 'update')
        
        assert isinstance(result, StatusNotFoundError)
    
    def test_convert_client_error_resource_not_found(self):
        """Test ClientError conversion for ResourceNotFoundException."""
        error = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Table not found'}},
            'GetItem'
        )
        
        result = self.service._convert_client_error(error)
        
        assert isinstance(result, StatusNotFoundError)
    
    def test_convert_client_error_throttling(self):
        """Test ClientError conversion for throttling errors."""
        throttling_errors = ['ProvisionedThroughputExceededException', 'ThrottlingException']
        
        for error_code in throttling_errors:
            error = ClientError(
                {'Error': {'Code': error_code, 'Message': 'Throttled'}},
                'UpdateItem'
            )
            
            result = self.service._convert_client_error(error)
            
            assert isinstance(result, StatusDatabaseError)
            assert result.retry_after == 5
    
    def test_convert_client_error_validation_exception(self):
        """Test ClientError conversion for ValidationException."""
        error = ClientError(
            {'Error': {'Code': 'ValidationException', 'Message': 'Invalid parameter'}},
            'PutItem'
        )
        
        result = self.service._convert_client_error(error)
        
        assert isinstance(result, StatusValidationError)
    
    def test_convert_client_error_generic_error(self):
        """Test ClientError conversion for generic errors."""
        error = ClientError(
            {'Error': {'Code': 'InternalServerError', 'Message': 'Internal error'}},
            'GetItem'
        )
        
        result = self.service._convert_client_error(error)
        
        assert isinstance(result, StatusDatabaseError)
    
    def test_calculate_progress_and_estimates_with_sufficient_data(self):
        """Test progress and estimates calculation with sufficient processing data."""
        # Mock existing status with start time 60 seconds ago
        past_time = datetime.utcnow() - timedelta(seconds=60)
        start_time = past_time.isoformat() + 'Z'
        
        existing_status = {
            'metadata': {
                'startTime': start_time
            }
        }
        
        new_progress = {
            'totalBatches': 10,
            'completedBatches': 3
        }
        
        current_time = datetime.utcnow().isoformat() + 'Z'
        
        result = self.service._calculate_progress_and_estimates(
            new_progress, existing_status, current_time
        )
        
        # Should calculate percentage
        assert result['percentage'] == 30.0
        
        # Should have processing rate and estimates for longer operations
        assert 'processingRate' in result
        assert 'estimatedRemainingSeconds' in result
        assert 'estimatedCompletion' in result
        assert 'showEstimates' in result
    
    def test_calculate_progress_and_estimates_short_operation(self):
        """Test progress calculation for short operations (no estimates shown)."""
        # Mock existing status with start time 5 seconds ago (short operation)
        recent_time = datetime.utcnow() - timedelta(seconds=5)
        start_time = recent_time.isoformat() + 'Z'
        
        existing_status = {
            'metadata': {
                'startTime': start_time
            }
        }
        
        new_progress = {
            'totalBatches': 2,
            'completedBatches': 1
        }
        
        current_time = datetime.utcnow().isoformat() + 'Z'
        
        result = self.service._calculate_progress_and_estimates(
            new_progress, existing_status, current_time
        )
        
        # Should calculate percentage
        assert result['percentage'] == 50.0
        
        # Should not show estimates for short operations
        if 'showEstimates' in result:
            assert result['showEstimates'] is False
    
    def test_calculate_progress_and_estimates_no_existing_status(self):
        """Test progress calculation with no existing status."""
        new_progress = {
            'totalBatches': 5,
            'completedBatches': 2
        }
        
        current_time = datetime.utcnow().isoformat() + 'Z'
        
        result = self.service._calculate_progress_and_estimates(
            new_progress, None, current_time
        )
        
        # Should only calculate basic percentage
        assert result['percentage'] == 40.0
        
        # Should not have estimates without existing status
        assert 'estimatedRemainingSeconds' not in result
        assert 'processingRate' not in result
    
    def test_calculate_progress_and_estimates_invalid_time_format(self):
        """Test progress calculation with invalid time format."""
        existing_status = {
            'metadata': {
                'startTime': 'invalid-time-format'
            }
        }
        
        new_progress = {
            'totalBatches': 10,
            'completedBatches': 3
        }
        
        current_time = datetime.utcnow().isoformat() + 'Z'
        
        # Should not raise exception, just skip estimates
        result = self.service._calculate_progress_and_estimates(
            new_progress, existing_status, current_time
        )
        
        # Should still calculate basic percentage
        assert result['percentage'] == 30.0
        
        # Should not have estimates due to invalid time format
        assert 'estimatedRemainingSeconds' not in result
    
    def test_set_error_with_recovery_options(self):
        """Test setting error status with recovery options."""
        upload_id = "test-upload-123"
        error_message = "Network timeout occurred"
        error_code = "NETWORK_ERROR"
        
        mock_response = {
            'Attributes': {
                'uploadId': {'S': upload_id},
                'status': {'S': 'error'},
                'error': {
                    'M': {
                        'message': {'S': error_message},
                        'code': {'S': error_code},
                        'timestamp': {'S': '2025-01-09T12:00:00Z'},
                        'recoverable': {'BOOL': True},
                        'retryAfter': {'N': '30'}
                    }
                },
                'updatedAt': {'S': '2025-01-09T12:00:00Z'},
                'ttl': {'N': '1736424000'}
            }
        }
        self.mock_dynamodb.update_item.return_value = mock_response
        
        with patch.object(self.service, '_get_current_timestamp', return_value='2025-01-09T12:00:00Z'), \
             patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            
            result = self.service.set_error(
                upload_id, error_message, error_code, 
                recoverable=True, retry_after=30
            )
            
            # Verify error information
            assert result['status'] == 'error'
            assert result['error']['message'] == error_message
            assert result['error']['code'] == error_code
            assert result['error']['recoverable'] is True
            assert result['error']['retryAfter'] == 30
    
    def test_complete_processing_with_lead_counts(self):
        """Test processing completion with detailed lead counts."""
        upload_id = "test-upload-123"
        total_leads = 100
        created_leads = 60
        updated_leads = 40
        
        # Mock get_status call
        current_status = {
            'uploadId': upload_id,
            'status': 'processing',
            'progress': {
                'totalBatches': 10,
                'completedBatches': 8
            }
        }
        
        # Mock update_status call
        completed_status = {
            'uploadId': upload_id,
            'status': 'completed',
            'stage': 'completed',
            'progress': {
                'totalBatches': 10,
                'completedBatches': 10,
                'totalLeads': total_leads,
                'processedLeads': total_leads,
                'createdLeads': created_leads,
                'updatedLeads': updated_leads,
                'percentage': 100.0
            }
        }
        
        with patch.object(self.service, 'get_status', return_value=current_status), \
             patch.object(self.service, 'update_status', return_value=completed_status) as mock_update:
            
            result = self.service.complete_processing(
                upload_id, total_leads, created_leads, updated_leads
            )
            
            # Verify update_status was called with lead counts
            call_args = mock_update.call_args[1]
            assert call_args['progress']['createdLeads'] == created_leads
            assert call_args['progress']['updatedLeads'] == updated_leads
            
            # Verify result
            assert result['progress']['createdLeads'] == created_leads
            assert result['progress']['updatedLeads'] == updated_leads
    
    def test_complete_processing_validation_errors(self):
        """Test processing completion with validation errors."""
        upload_id = "test-upload-123"
        
        # Test invalid total_leads
        with pytest.raises(StatusValidationError, match="Total leads must be a non-negative integer"):
            self.service.complete_processing(upload_id, -1)
        
        with pytest.raises(StatusValidationError, match="Total leads must be a non-negative integer"):
            self.service.complete_processing(upload_id, "invalid")
        
        # Test invalid created_leads
        with pytest.raises(StatusValidationError, match="Created leads must be a non-negative integer"):
            self.service.complete_processing(upload_id, 100, -1)
        
        # Test invalid updated_leads
        with pytest.raises(StatusValidationError, match="Updated leads must be a non-negative integer"):
            self.service.complete_processing(upload_id, 100, 50, -1)
    
    def test_cancel_processing_success(self):
        """Test successful processing cancellation."""
        upload_id = "test-upload-123"
        cancellation_reason = "User requested cancellation"
        
        # Mock get_status call
        current_status = {
            'uploadId': upload_id,
            'status': 'processing',
            'progress': {
                'totalBatches': 10,
                'completedBatches': 3,
                'processedLeads': 30
            }
        }
        
        # Mock update_status call
        cancelled_status = {
            'uploadId': upload_id,
            'status': 'cancelled',
            'stage': 'cancelled',
            'progress': {
                'totalBatches': 10,
                'completedBatches': 3,
                'processedLeads': 30,
                'percentage': 30.0
            },
            'metadata': {
                'cancellationReason': cancellation_reason
            }
        }
        
        with patch.object(self.service, 'get_status', return_value=current_status), \
             patch.object(self.service, 'update_status', return_value=cancelled_status) as mock_update:
            
            result = self.service.cancel_processing(upload_id, cancellation_reason)
            
            # Verify update_status was called correctly
            call_args = mock_update.call_args[1]
            assert call_args['status'] == 'cancelled'
            assert call_args['stage'] == 'cancelled'
            assert call_args['metadata']['cancellationReason'] == cancellation_reason
            
            # Verify result
            assert result['status'] == 'cancelled'
            assert result['metadata']['cancellationReason'] == cancellation_reason
    
    def test_cancel_processing_validation_error(self):
        """Test processing cancellation with validation error."""
        upload_id = "test-upload-123"
        
        # Test invalid cancellation reason
        with pytest.raises(StatusValidationError, match="Cancellation reason must be a non-empty string"):
            self.service.cancel_processing(upload_id, "")
        
        with pytest.raises(StatusValidationError, match="Cancellation reason must be a non-empty string"):
            self.service.cancel_processing(upload_id, None)


class TestStatusServiceExceptions:
    """Test custom exception classes for the status service."""
    
    def test_status_service_error_basic(self):
        """Test basic StatusServiceError functionality."""
        error = StatusServiceError("Test error message")
        
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.error_code == "StatusServiceError"
        assert error.retry_after is None
    
    def test_status_service_error_with_code_and_retry(self):
        """Test StatusServiceError with error code and retry_after."""
        error = StatusServiceError("Test error", "CUSTOM_ERROR", 30)
        
        assert error.message == "Test error"
        assert error.error_code == "CUSTOM_ERROR"
        assert error.retry_after == 30
    
    def test_status_not_found_error(self):
        """Test StatusNotFoundError functionality."""
        error = StatusNotFoundError("test-upload-123")
        
        assert "test-upload-123" in str(error)
        assert error.upload_id == "test-upload-123"
        assert error.error_code == "STATUS_NOT_FOUND"
    
    def test_status_not_found_error_no_upload_id(self):
        """Test StatusNotFoundError without upload ID."""
        error = StatusNotFoundError()
        
        assert "Status record not found" in str(error)
        assert error.upload_id is None
    
    def test_status_conflict_error(self):
        """Test StatusConflictError functionality."""
        error = StatusConflictError("test-upload-123")
        
        assert "test-upload-123" in str(error)
        assert error.upload_id == "test-upload-123"
        assert error.error_code == "STATUS_CONFLICT"
    
    def test_status_database_error(self):
        """Test StatusDatabaseError functionality."""
        error = StatusDatabaseError("Database connection failed", "get_item", 10)
        
        assert error.message == "Database connection failed"
        assert error.operation == "get_item"
        assert error.retry_after == 10
        assert error.error_code == "DATABASE_ERROR"
    
    def test_status_validation_error(self):
        """Test StatusValidationError functionality."""
        error = StatusValidationError("Invalid upload ID format", "uploadId")
        
        assert error.message == "Invalid upload ID format"
        assert error.field == "uploadId"
        assert error.error_code == "VALIDATION_ERROR"


class TestStatusServiceEdgeCases:
    """Test edge cases and boundary conditions for the status service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_dynamodb = Mock()
        self.service = ProcessingStatusService(
            dynamodb_client=self.mock_dynamodb,
            table_name='test-processing-status'
        )
    
    def test_create_status_with_minimal_file_size(self):
        """Test status creation with minimal file size."""
        upload_id = "test-upload-123"
        file_name = "empty.csv"
        file_size = 0  # Empty file
        
        self.mock_dynamodb.put_item.return_value = {}
        
        with patch.object(self.service, '_get_current_timestamp', return_value='2025-01-09T12:00:00Z'), \
             patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            
            result = self.service.create_status(upload_id, file_name, file_size)
            
            # Should handle zero file size
            assert result['metadata']['fileSize'] == 0
    
    def test_create_status_with_maximum_file_name_length(self):
        """Test status creation with very long file name."""
        upload_id = "test-upload-123"
        file_name = "a" * 255  # Maximum reasonable file name length
        file_size = 1024
        
        self.mock_dynamodb.put_item.return_value = {}
        
        with patch.object(self.service, '_get_current_timestamp', return_value='2025-01-09T12:00:00Z'), \
             patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            
            result = self.service.create_status(upload_id, file_name, file_size)
            
            # Should handle long file names
            assert result['metadata']['fileName'] == file_name
    
    def test_update_status_with_zero_progress(self):
        """Test status update with zero progress values."""
        upload_id = "test-upload-123"
        
        # Mock existing status
        existing_status = {
            'uploadId': upload_id,
            'status': 'processing',
            'progress': {'totalBatches': 0, 'completedBatches': 0}
        }
        
        mock_response = {
            'Attributes': {
                'uploadId': {'S': upload_id},
                'status': {'S': 'processing'},
                'progress': {
                    'M': {
                        'totalBatches': {'N': '0'},
                        'completedBatches': {'N': '0'},
                        'percentage': {'N': '0.0'}
                    }
                },
                'updatedAt': {'S': '2025-01-09T12:00:00Z'},
                'ttl': {'N': '1736424000'}
            }
        }
        self.mock_dynamodb.update_item.return_value = mock_response
        
        with patch.object(self.service, 'get_status', return_value=existing_status), \
             patch.object(self.service, '_get_current_timestamp', return_value='2025-01-09T12:00:00Z'), \
             patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            
            result = self.service.update_status(
                upload_id=upload_id,
                progress={'totalBatches': 0, 'completedBatches': 0}
            )
            
            # Should handle zero values correctly
            assert result['progress']['percentage'] == 0.0
    
    def test_update_status_with_large_progress_numbers(self):
        """Test status update with large progress numbers."""
        upload_id = "test-upload-123"
        
        # Mock existing status
        existing_status = {
            'uploadId': upload_id,
            'status': 'processing',
            'progress': {'totalBatches': 0, 'completedBatches': 0}
        }
        
        large_total = 1000000
        large_completed = 500000
        
        mock_response = {
            'Attributes': {
                'uploadId': {'S': upload_id},
                'status': {'S': 'processing'},
                'progress': {
                    'M': {
                        'totalBatches': {'N': str(large_total)},
                        'completedBatches': {'N': str(large_completed)},
                        'percentage': {'N': '50.0'}
                    }
                },
                'updatedAt': {'S': '2025-01-09T12:00:00Z'},
                'ttl': {'N': '1736424000'}
            }
        }
        self.mock_dynamodb.update_item.return_value = mock_response
        
        with patch.object(self.service, 'get_status', return_value=existing_status), \
             patch.object(self.service, '_get_current_timestamp', return_value='2025-01-09T12:00:00Z'), \
             patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            
            result = self.service.update_status(
                upload_id=upload_id,
                progress={'totalBatches': large_total, 'completedBatches': large_completed}
            )
            
            # Should handle large numbers correctly
            assert result['progress']['totalBatches'] == large_total
            assert result['progress']['completedBatches'] == large_completed
            assert result['progress']['percentage'] == 50.0
    
    def test_ttl_calculation_edge_cases(self):
        """Test TTL calculation with edge cases."""
        # Test with zero hours (should still work)
        ttl_zero = self.service._calculate_ttl(0)
        current_time = int(datetime.utcnow().timestamp())
        assert ttl_zero >= current_time  # Should be at least current time
        
        # Test with very large hours
        ttl_large = self.service._calculate_ttl(8760)  # 1 year
        expected_large = current_time + (8760 * 3600)
        assert abs(ttl_large - expected_large) < 60  # Within 1 minute tolerance
    
    def test_format_status_record_with_missing_fields(self):
        """Test status record formatting with missing optional fields."""
        minimal_item = {
            'uploadId': {'S': 'test-123'},
            'status': {'S': 'processing'}
        }
        
        result = self.service._format_status_record(minimal_item)
        
        # Should handle missing fields gracefully
        assert result['uploadId'] == 'test-123'
        assert result['status'] == 'processing'
        # Missing fields should not be present or should have default values
        assert 'progress' not in result or result['progress'] is None
        assert 'metadata' not in result or result['metadata'] is None
    
    def test_format_status_record_with_empty_nested_objects(self):
        """Test status record formatting with empty nested objects."""
        item_with_empty_nested = {
            'uploadId': {'S': 'test-123'},
            'status': {'S': 'processing'},
            'progress': {'M': {}},
            'metadata': {'M': {}},
            'error': {'M': {}}
        }
        
        result = self.service._format_status_record(item_with_empty_nested)
        
        # Should handle empty nested objects
        assert result['uploadId'] == 'test-123'
        assert result['status'] == 'processing'
        assert result['progress'] == {}
        assert result['metadata'] == {}
        assert result['error'] == {}


if __name__ == '__main__':
    pytest.main([__file__, '-v'])