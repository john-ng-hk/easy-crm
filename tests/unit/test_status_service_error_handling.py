"""
Unit tests for ProcessingStatusService error handling and recovery mechanisms.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError
import sys
import os

# Add the lambda shared directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))

from status_service import (
    ProcessingStatusService, 
    StatusServiceError, 
    StatusNotFoundError, 
    StatusConflictError,
    StatusDatabaseError,
    StatusValidationError
)


class TestStatusServiceErrorHandling:
    """Test error handling and recovery mechanisms in ProcessingStatusService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_dynamodb = Mock()
        self.service = ProcessingStatusService(
            dynamodb_client=self.mock_dynamodb,
            table_name='test-status-table'
        )
        self.test_upload_id = 'test-upload-123'
        self.test_file_name = 'test-file.csv'
        self.test_file_size = 1024
    
    def test_validate_upload_id_valid(self):
        """Test upload ID validation with valid input."""
        # Should not raise any exception
        self.service._validate_upload_id('valid-upload-123')
        self.service._validate_upload_id('test_upload_456')
        self.service._validate_upload_id('upload789')
    
    def test_validate_upload_id_invalid(self):
        """Test upload ID validation with invalid input."""
        with pytest.raises(StatusValidationError) as exc_info:
            self.service._validate_upload_id('')
        assert 'non-empty string' in str(exc_info.value)
        
        with pytest.raises(StatusValidationError) as exc_info:
            self.service._validate_upload_id(None)
        assert 'non-empty string' in str(exc_info.value)
        
        with pytest.raises(StatusValidationError) as exc_info:
            self.service._validate_upload_id('invalid@upload')
        assert 'invalid characters' in str(exc_info.value)
        
        with pytest.raises(StatusValidationError) as exc_info:
            self.service._validate_upload_id('a' * 256)  # Too long
        assert 'too long' in str(exc_info.value)
    
    def test_validate_status_value_valid(self):
        """Test status value validation with valid input."""
        valid_statuses = ['uploading', 'uploaded', 'processing', 'completed', 'error', 'cancelled']
        for status in valid_statuses:
            self.service._validate_status_value(status)
    
    def test_validate_status_value_invalid(self):
        """Test status value validation with invalid input."""
        with pytest.raises(StatusValidationError) as exc_info:
            self.service._validate_status_value('invalid_status')
        assert 'Invalid status' in str(exc_info.value)
    
    def test_validate_stage_value_valid(self):
        """Test stage value validation with valid input."""
        valid_stages = ['file_upload', 'file_processing', 'batch_processing', 'completed']
        for stage in valid_stages:
            self.service._validate_stage_value(stage)
    
    def test_validate_stage_value_invalid(self):
        """Test stage value validation with invalid input."""
        with pytest.raises(StatusValidationError) as exc_info:
            self.service._validate_stage_value('invalid_stage')
        assert 'Invalid stage' in str(exc_info.value)
    
    def test_convert_client_error_conditional_check_failed(self):
        """Test conversion of ConditionalCheckFailedException."""
        # Test create context (should be conflict)
        error = ClientError(
            error_response={
                'Error': {
                    'Code': 'ConditionalCheckFailedException',
                    'Message': 'The conditional request failed'
                }
            },
            operation_name='PutItem'
        )
        
        converted = self.service._convert_client_error(error, 'create')
        assert isinstance(converted, StatusConflictError)
        
        # Test update context (should be not found)
        converted = self.service._convert_client_error(error, 'update')
        assert isinstance(converted, StatusNotFoundError)
    
    def test_convert_client_error_resource_not_found(self):
        """Test conversion of ResourceNotFoundException."""
        error = ClientError(
            error_response={
                'Error': {
                    'Code': 'ResourceNotFoundException',
                    'Message': 'Requested resource not found'
                }
            },
            operation_name='GetItem'
        )
        
        converted = self.service._convert_client_error(error)
        assert isinstance(converted, StatusNotFoundError)
    
    def test_convert_client_error_throttling(self):
        """Test conversion of throttling errors."""
        error = ClientError(
            error_response={
                'Error': {
                    'Code': 'ProvisionedThroughputExceededException',
                    'Message': 'Request rate is too high'
                }
            },
            operation_name='UpdateItem'
        )
        
        converted = self.service._convert_client_error(error)
        assert isinstance(converted, StatusDatabaseError)
        assert converted.retry_after == 5
    
    def test_convert_client_error_validation(self):
        """Test conversion of ValidationException."""
        error = ClientError(
            error_response={
                'Error': {
                    'Code': 'ValidationException',
                    'Message': 'Invalid parameter value'
                }
            },
            operation_name='PutItem'
        )
        
        converted = self.service._convert_client_error(error)
        assert isinstance(converted, StatusValidationError)
    
    def test_retry_with_backoff_success_on_first_attempt(self):
        """Test retry mechanism when operation succeeds on first attempt."""
        mock_operation = Mock(return_value='success')
        
        result = self.service._retry_with_backoff(mock_operation, 'test_operation')
        
        assert result == 'success'
        assert mock_operation.call_count == 1
    
    def test_retry_with_backoff_success_after_retries(self):
        """Test retry mechanism when operation succeeds after retries."""
        mock_operation = Mock()
        # Fail twice, then succeed
        mock_operation.side_effect = [
            ClientError(
                error_response={'Error': {'Code': 'ThrottlingException', 'Message': 'Throttled'}},
                operation_name='TestOp'
            ),
            ClientError(
                error_response={'Error': {'Code': 'ThrottlingException', 'Message': 'Throttled'}},
                operation_name='TestOp'
            ),
            'success'
        ]
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = self.service._retry_with_backoff(mock_operation, 'test_operation')
        
        assert result == 'success'
        assert mock_operation.call_count == 3
    
    def test_retry_with_backoff_non_retryable_error(self):
        """Test retry mechanism with non-retryable error."""
        mock_operation = Mock()
        mock_operation.side_effect = ClientError(
            error_response={'Error': {'Code': 'ValidationException', 'Message': 'Invalid'}},
            operation_name='TestOp'
        )
        
        with pytest.raises(StatusValidationError):
            self.service._retry_with_backoff(mock_operation, 'test_operation')
        
        assert mock_operation.call_count == 1  # Should not retry
    
    def test_retry_with_backoff_max_retries_exceeded(self):
        """Test retry mechanism when max retries are exceeded."""
        mock_operation = Mock()
        mock_operation.side_effect = ClientError(
            error_response={'Error': {'Code': 'ThrottlingException', 'Message': 'Throttled'}},
            operation_name='TestOp'
        )
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            with pytest.raises(StatusDatabaseError):
                self.service._retry_with_backoff(mock_operation, 'test_operation')
        
        assert mock_operation.call_count == 4  # Initial + 3 retries
    
    def test_create_status_with_validation_error(self):
        """Test create_status with validation errors."""
        # Test invalid upload ID
        with pytest.raises(StatusValidationError):
            self.service.create_status('', self.test_file_name, self.test_file_size)
        
        # Test invalid file name
        with pytest.raises(StatusValidationError):
            self.service.create_status(self.test_upload_id, '', self.test_file_size)
        
        # Test invalid file size
        with pytest.raises(StatusValidationError):
            self.service.create_status(self.test_upload_id, self.test_file_name, -1)
    
    def test_create_status_with_conflict_error(self):
        """Test create_status when record already exists."""
        self.mock_dynamodb.put_item.side_effect = ClientError(
            error_response={'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'Item exists'}},
            operation_name='PutItem'
        )
        
        with pytest.raises(StatusConflictError) as exc_info:
            self.service.create_status(self.test_upload_id, self.test_file_name, self.test_file_size)
        
        assert exc_info.value.error_code == 'STATUS_CONFLICT'
    
    def test_update_status_with_not_found_error(self):
        """Test update_status when record doesn't exist."""
        self.mock_dynamodb.update_item.side_effect = ClientError(
            error_response={'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'Item not found'}},
            operation_name='UpdateItem'
        )
        
        with pytest.raises(StatusNotFoundError) as exc_info:
            self.service.update_status(self.test_upload_id, status='processing')
        
        assert exc_info.value.error_code == 'STATUS_NOT_FOUND'
    
    def test_get_status_with_not_found_error(self):
        """Test get_status when record doesn't exist."""
        self.mock_dynamodb.get_item.return_value = {}  # No 'Item' key
        
        with pytest.raises(StatusNotFoundError) as exc_info:
            self.service.get_status(self.test_upload_id)
        
        assert exc_info.value.upload_id == self.test_upload_id
    
    def test_set_error_with_enhanced_information(self):
        """Test set_error with enhanced error information."""
        mock_response = {
            'Attributes': {
                'uploadId': {'S': self.test_upload_id},
                'status': {'S': 'error'},
                'error': {
                    'M': {
                        'message': {'S': 'Test error'},
                        'code': {'S': 'TEST_ERROR'},
                        'timestamp': {'S': '2023-01-01T00:00:00Z'},
                        'recoverable': {'BOOL': True},
                        'retryAfter': {'N': '60'}
                    }
                }
            }
        }
        self.mock_dynamodb.update_item.return_value = mock_response
        
        result = self.service.set_error(
            self.test_upload_id, 
            'Test error', 
            'TEST_ERROR',
            recoverable=True,
            retry_after=60
        )
        
        assert result['status'] == 'error'
        assert result['error']['recoverable'] == True
        assert result['error']['retryAfter'] == 60
    
    def test_complete_processing_with_enhanced_information(self):
        """Test complete_processing with enhanced completion information."""
        # Mock get_status call
        mock_current_status = {
            'progress': {
                'totalBatches': 5,
                'completedBatches': 4
            }
        }
        
        with patch.object(self.service, 'get_status', return_value=mock_current_status):
            with patch.object(self.service, 'update_status') as mock_update:
                mock_update.return_value = {'status': 'completed'}
                
                result = self.service.complete_processing(
                    self.test_upload_id, 
                    total_leads=100,
                    created_leads=80,
                    updated_leads=20
                )
                
                # Verify update_status was called with correct parameters
                mock_update.assert_called_once()
                call_args = mock_update.call_args
                
                assert call_args[1]['status'] == 'completed'
                assert call_args[1]['stage'] == 'completed'
                assert call_args[1]['progress']['createdLeads'] == 80
                assert call_args[1]['progress']['updatedLeads'] == 20
    
    def test_recover_from_error_success(self):
        """Test successful error recovery."""
        # Mock current error status
        mock_error_status = {
            'status': 'error',
            'error': {
                'recoverable': True,
                'message': 'Recoverable error'
            }
        }
        
        with patch.object(self.service, 'get_status', return_value=mock_error_status):
            with patch.object(self.service, 'update_status') as mock_update:
                mock_update.return_value = {'status': 'processing'}
                
                result = self.service.recover_from_error(self.test_upload_id, 'Manual retry')
                
                # Verify update_status was called with correct parameters
                mock_update.assert_called_once()
                call_args = mock_update.call_args
                
                assert call_args[1]['status'] == 'processing'
                assert call_args[1]['stage'] == 'batch_processing'
                assert 'Manual retry' in call_args[1]['metadata']['recoveryAction']
    
    def test_recover_from_error_not_in_error_state(self):
        """Test error recovery when not in error state."""
        # Mock current non-error status
        mock_status = {
            'status': 'processing'
        }
        
        with patch.object(self.service, 'get_status', return_value=mock_status):
            with pytest.raises(StatusValidationError) as exc_info:
                self.service.recover_from_error(self.test_upload_id)
            
            assert 'Can only recover from error status' in str(exc_info.value)
    
    def test_recover_from_error_not_recoverable(self):
        """Test error recovery when error is not recoverable."""
        # Mock current non-recoverable error status
        mock_error_status = {
            'status': 'error',
            'error': {
                'recoverable': False,
                'message': 'Non-recoverable error'
            }
        }
        
        with patch.object(self.service, 'get_status', return_value=mock_error_status):
            with pytest.raises(StatusValidationError) as exc_info:
                self.service.recover_from_error(self.test_upload_id)
            
            assert 'Error is not recoverable' in str(exc_info.value)


if __name__ == '__main__':
    pytest.main([__file__])