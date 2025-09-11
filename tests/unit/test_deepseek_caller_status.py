"""
Unit tests for DeepSeek Caller Lambda function with status tracking integration.
Tests the batch progress tracking functionality.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
import os

# Add the lambda function path to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'deepseek-caller'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))

# Mock environment variables before importing
os.environ['DEEPSEEK_API_KEY'] = 'test-api-key'
os.environ['LEADS_TABLE'] = 'test-leads-table'
os.environ['PROCESSING_STATUS_TABLE'] = 'test-status-table'
os.environ['AWS_REGION'] = 'ap-southeast-1'

from lambda_function import process_batch_with_deepseek, lambda_handler


class TestDeepSeekCallerStatusTracking:
    """Test DeepSeek Caller status tracking functionality."""
    
    @pytest.fixture
    def mock_db_utils(self):
        """Mock DynamoDB utils."""
        mock_db = Mock()
        mock_db.batch_upsert_leads.return_value = {
            'created_leads': ['lead1', 'lead2'],
            'updated_leads': ['lead3'],
            'duplicate_actions': [],
            'processing_stats': {'processing_time_ms': 1000}
        }
        return mock_db
    
    @pytest.fixture
    def mock_status_service(self):
        """Mock ProcessingStatusService."""
        mock_status = Mock()
        mock_status.get_status.return_value = {
            'progress': {
                'totalBatches': 3,
                'completedBatches': 1,
                'processedLeads': 10
            }
        }
        return mock_status
    
    @pytest.fixture
    def sample_batch_data(self):
        """Sample batch data for testing."""
        return {
            'batch_id': 'test-batch-123',
            'upload_id': 'test-upload-456',
            'source_file': 'test.csv',
            'batch_number': 2,
            'total_batches': 3,
            'leads': [
                {'name': 'John Doe', 'email': 'john@example.com'},
                {'name': 'Jane Smith', 'email': 'jane@example.com'}
            ]
        }
    
    @patch('lambda_function.DeepSeekClient')
    def test_process_batch_updates_progress_mid_processing(self, mock_deepseek_class, mock_db_utils, mock_status_service, sample_batch_data):
        """Test that batch processing updates progress correctly for mid-processing batches."""
        # Setup mocks
        mock_deepseek = Mock()
        mock_deepseek.standardize_leads.return_value = [
            {'firstName': 'John', 'lastName': 'Doe', 'email': 'john@example.com'},
            {'firstName': 'Jane', 'lastName': 'Smith', 'email': 'jane@example.com'}
        ]
        mock_deepseek_class.return_value = mock_deepseek
        
        # Process batch
        with patch('lambda_function.LeadValidator') as mock_validator:
            mock_validator.validate_lead_data.return_value = (True, [])
            
            result = process_batch_with_deepseek(sample_batch_data, mock_db_utils, mock_status_service)
        
        # Verify status service was called to get current status
        mock_status_service.get_status.assert_called_once_with('test-upload-456')
        
        # Verify status service was called to update progress (not completion)
        mock_status_service.update_status.assert_called_once()
        call_args = mock_status_service.update_status.call_args
        
        assert call_args[1]['upload_id'] == 'test-upload-456'
        assert 'progress' in call_args[1]
        
        progress = call_args[1]['progress']
        assert progress['totalBatches'] == 3
        assert progress['completedBatches'] == 2  # 1 + 1 (current batch)
        assert progress['processedLeads'] == 12  # 10 + 2 (current batch leads)
        
        # Verify completion status was not set (since not all batches completed)
        assert call_args[1].get('status') != 'completed'
        assert call_args[1].get('stage') != 'completed'
    
    @patch('lambda_function.DeepSeekClient')
    def test_process_batch_completes_processing(self, mock_deepseek_class, mock_db_utils, mock_status_service, sample_batch_data):
        """Test that batch processing marks as completed when all batches are done."""
        # Setup mocks for final batch
        mock_deepseek = Mock()
        mock_deepseek.standardize_leads.return_value = [
            {'firstName': 'John', 'lastName': 'Doe', 'email': 'john@example.com'},
            {'firstName': 'Jane', 'lastName': 'Smith', 'email': 'jane@example.com'}
        ]
        mock_deepseek_class.return_value = mock_deepseek
        
        # Mock current status showing this is the last batch
        mock_status_service.get_status.return_value = {
            'progress': {
                'totalBatches': 3,
                'completedBatches': 2,  # This will be the 3rd and final batch
                'processedLeads': 20
            }
        }
        
        # Process batch
        with patch('lambda_function.LeadValidator') as mock_validator:
            mock_validator.validate_lead_data.return_value = (True, [])
            
            result = process_batch_with_deepseek(sample_batch_data, mock_db_utils, mock_status_service)
        
        # Verify status service was called to update with completion
        mock_status_service.update_status.assert_called_once()
        call_args = mock_status_service.update_status.call_args
        
        assert call_args[1]['upload_id'] == 'test-upload-456'
        assert call_args[1]['status'] == 'completed'
        assert call_args[1]['stage'] == 'completed'
        
        progress = call_args[1]['progress']
        assert progress['totalBatches'] == 3
        assert progress['completedBatches'] == 3  # All batches completed
        assert progress['processedLeads'] == 22  # 20 + 2 (current batch leads)
    
    @patch('lambda_function.DeepSeekClient')
    def test_process_batch_handles_deepseek_error_with_status_update(self, mock_deepseek_class, mock_db_utils, mock_status_service, sample_batch_data):
        """Test that DeepSeek errors update status correctly."""
        # Setup mock to raise error
        mock_deepseek = Mock()
        mock_deepseek.standardize_leads.side_effect = Exception("DeepSeek API error")
        mock_deepseek_class.return_value = mock_deepseek
        
        # Process batch and expect error
        with pytest.raises(Exception):
            process_batch_with_deepseek(sample_batch_data, mock_db_utils, mock_status_service)
        
        # Verify error status was set
        mock_status_service.set_error.assert_called_once()
        call_args = mock_status_service.set_error.call_args
        
        assert call_args[1]['upload_id'] == 'test-upload-456'
        assert 'DeepSeek processing failed for batch 2' in call_args[1]['error_message']
        assert call_args[1]['error_code'] == 'DEEPSEEK_API_ERROR'
    
    @patch('lambda_function.DeepSeekClient')
    def test_process_batch_handles_validation_error_with_status_update(self, mock_deepseek_class, mock_db_utils, mock_status_service, sample_batch_data):
        """Test that validation errors update status correctly."""
        # Setup mocks
        mock_deepseek = Mock()
        mock_deepseek.standardize_leads.return_value = [
            {'firstName': 'John', 'lastName': 'Doe', 'email': 'john@example.com'}
        ]
        mock_deepseek_class.return_value = mock_deepseek
        
        # Mock validation to fail for all leads
        with patch('lambda_function.LeadValidator') as mock_validator:
            mock_validator.validate_lead_data.return_value = (False, ['Invalid data'])
            
            # Process batch and expect error
            with pytest.raises(Exception):
                process_batch_with_deepseek(sample_batch_data, mock_db_utils, mock_status_service)
        
        # Verify error status was set
        mock_status_service.set_error.assert_called_once()
        call_args = mock_status_service.set_error.call_args
        
        assert call_args[1]['upload_id'] == 'test-upload-456'
        assert 'Validation failed for batch 2' in call_args[1]['error_message']
        assert call_args[1]['error_code'] == 'VALIDATION_ERROR'
    
    @patch('lambda_function.DeepSeekClient')
    def test_process_batch_handles_database_error_with_status_update(self, mock_deepseek_class, mock_db_utils, mock_status_service, sample_batch_data):
        """Test that database errors update status correctly."""
        # Setup mocks
        mock_deepseek = Mock()
        mock_deepseek.standardize_leads.return_value = [
            {'firstName': 'John', 'lastName': 'Doe', 'email': 'john@example.com'},
            {'firstName': 'Jane', 'lastName': 'Smith', 'email': 'jane@example.com'}
        ]
        mock_deepseek_class.return_value = mock_deepseek
        
        # Mock database operations to fail
        mock_db_utils.batch_upsert_leads.side_effect = Exception("Database error")
        mock_db_utils.batch_create_leads.side_effect = Exception("Fallback database error")
        
        # Process batch and expect error
        with patch('lambda_function.LeadValidator') as mock_validator:
            mock_validator.validate_lead_data.return_value = (True, [])
            
            with pytest.raises(Exception):
                process_batch_with_deepseek(sample_batch_data, mock_db_utils, mock_status_service)
        
        # Verify error status was set
        mock_status_service.set_error.assert_called_once()
        call_args = mock_status_service.set_error.call_args
        
        assert call_args[1]['upload_id'] == 'test-upload-456'
        assert 'Database storage failed for batch 2' in call_args[1]['error_message']
        assert call_args[1]['error_code'] == 'DATABASE_ERROR'
    
    def test_process_batch_without_status_service(self, mock_db_utils, sample_batch_data):
        """Test that batch processing works without status service (graceful degradation)."""
        with patch('lambda_function.DeepSeekClient') as mock_deepseek_class:
            mock_deepseek = Mock()
            mock_deepseek.standardize_leads.return_value = [
                {'firstName': 'John', 'lastName': 'Doe', 'email': 'john@example.com'}
            ]
            mock_deepseek_class.return_value = mock_deepseek
            
            with patch('lambda_function.LeadValidator') as mock_validator:
                mock_validator.validate_lead_data.return_value = (True, [])
                
                # Process batch without status service
                result = process_batch_with_deepseek(sample_batch_data, mock_db_utils, None)
        
        # Verify processing completed successfully
        assert result['batch_id'] == 'test-batch-123'
        assert result['upload_id'] == 'test-upload-456'
        assert result['processed_leads'] == 1
    
    def test_process_batch_without_upload_id(self, mock_db_utils, mock_status_service):
        """Test that batch processing works without upload_id (graceful degradation)."""
        batch_data = {
            'batch_id': 'test-batch-123',
            'source_file': 'test.csv',
            'batch_number': 1,
            'total_batches': 1,
            'leads': [{'name': 'John Doe', 'email': 'john@example.com'}]
        }
        
        with patch('lambda_function.DeepSeekClient') as mock_deepseek_class:
            mock_deepseek = Mock()
            mock_deepseek.standardize_leads.return_value = [
                {'firstName': 'John', 'lastName': 'Doe', 'email': 'john@example.com'}
            ]
            mock_deepseek_class.return_value = mock_deepseek
            
            with patch('lambda_function.LeadValidator') as mock_validator:
                mock_validator.validate_lead_data.return_value = (True, [])
                
                # Process batch without upload_id
                result = process_batch_with_deepseek(batch_data, mock_db_utils, mock_status_service)
        
        # Verify processing completed successfully
        assert result['batch_id'] == 'test-batch-123'
        assert result['upload_id'] is None
        assert result['processed_leads'] == 1
        
        # Verify status service was not called (no upload_id)
        mock_status_service.get_status.assert_not_called()
        mock_status_service.update_status.assert_not_called()
    
    @patch('lambda_function.ProcessingStatusService')
    @patch('lambda_function.DynamoDBUtils')
    def test_lambda_handler_initializes_status_service(self, mock_db_class, mock_status_class):
        """Test that lambda handler initializes status service correctly."""
        # Setup mocks
        mock_db = Mock()
        mock_db_class.return_value = mock_db
        
        mock_status = Mock()
        mock_status_class.return_value = mock_status
        
        # Create test event
        event = {
            'Records': [
                {
                    'body': json.dumps({
                        'batch_id': 'test-batch',
                        'upload_id': 'test-upload',
                        'leads': [{'name': 'Test', 'email': 'test@example.com'}]
                    })
                }
            ]
        }
        
        with patch('lambda_function.process_batch_with_deepseek') as mock_process:
            mock_process.return_value = {
                'batch_id': 'test-batch',
                'upload_id': 'test-upload',
                'processed_leads': 1,
                'created_leads': 1,
                'updated_leads': 0
            }
            
            # Call lambda handler
            result = lambda_handler(event, {})
        
        # Verify status service was initialized with correct table name
        mock_status_class.assert_called_once_with(table_name='test-status-table')
        
        # Verify process function was called with status service
        mock_process.assert_called_once()
        call_args = mock_process.call_args[0]
        assert len(call_args) == 3  # batch_data, db_utils, status_service
        assert call_args[2] == mock_status  # status_service parameter
    
    @patch('lambda_function.ProcessingStatusService')
    @patch('lambda_function.DynamoDBUtils')
    def test_lambda_handler_handles_processing_error_with_status_update(self, mock_db_class, mock_status_class):
        """Test that lambda handler updates status on processing errors."""
        # Setup mocks
        mock_db = Mock()
        mock_db_class.return_value = mock_db
        
        mock_status = Mock()
        mock_status_class.return_value = mock_status
        
        # Create test event
        event = {
            'Records': [
                {
                    'body': json.dumps({
                        'batch_id': 'test-batch',
                        'upload_id': 'test-upload',
                        'batch_number': 1,
                        'leads': [{'name': 'Test', 'email': 'test@example.com'}]
                    })
                }
            ]
        }
        
        with patch('lambda_function.process_batch_with_deepseek') as mock_process:
            mock_process.side_effect = Exception("Processing failed")
            
            # Call lambda handler - error handling wrapper will catch and return error response
            result = lambda_handler(event, {})
        
        # Verify error response was returned
        assert result['statusCode'] == 500
        assert 'error' in result['body']
        
        # Verify error status was set
        mock_status.set_error.assert_called_once()
        call_args = mock_status.set_error.call_args
        
        assert call_args[1]['upload_id'] == 'test-upload'
        assert 'Batch processing failed for batch 1' in call_args[1]['error_message']
        assert call_args[1]['error_code'] == 'BATCH_PROCESSING_ERROR'


if __name__ == '__main__':
    pytest.main([__file__])