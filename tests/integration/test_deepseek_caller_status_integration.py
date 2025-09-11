"""
Integration tests for DeepSeek Caller Lambda function with status tracking.
Tests the integration between DeepSeek Caller and ProcessingStatusService.
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

from lambda_function import lambda_handler
from status_service import ProcessingStatusService


class TestDeepSeekCallerStatusIntegration:
    """Test DeepSeek Caller status tracking integration."""
    
    @pytest.fixture
    def sample_sqs_event(self):
        """Sample SQS event for testing."""
        return {
            'Records': [
                {
                    'body': json.dumps({
                        'batch_id': 'test-batch-123',
                        'upload_id': 'test-upload-456',
                        'source_file': 'test.csv',
                        'batch_number': 1,
                        'total_batches': 2,
                        'leads': [
                            {'name': 'John Doe', 'email': 'john@example.com', 'company': 'Acme Corp'},
                            {'name': 'Jane Smith', 'email': 'jane@example.com', 'company': 'Beta Inc'}
                        ],
                        'timestamp': datetime.utcnow().isoformat(),
                        'environment': 'test'
                    })
                }
            ]
        }
    
    @patch('lambda_function.requests.post')
    @patch('lambda_function.DynamoDBUtils')
    @patch('lambda_function.ProcessingStatusService')
    def test_successful_batch_processing_updates_status(self, mock_status_class, mock_db_class, mock_requests, sample_sqs_event):
        """Test that successful batch processing updates status correctly."""
        # Setup DeepSeek API mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': json.dumps([
                        {
                            'firstName': 'John',
                            'lastName': 'Doe',
                            'email': 'john@example.com',
                            'company': 'Acme Corp',
                            'title': 'Manager',
                            'phone': '+1-555-123-4567',
                            'remarks': 'N/A'
                        },
                        {
                            'firstName': 'Jane',
                            'lastName': 'Smith',
                            'email': 'jane@example.com',
                            'company': 'Beta Inc',
                            'title': 'Director',
                            'phone': '+1-555-987-6543',
                            'remarks': 'N/A'
                        }
                    ])
                }
            }]
        }
        mock_requests.return_value = mock_response
        
        # Setup DynamoDB mock
        mock_db = Mock()
        mock_db.batch_upsert_leads.return_value = {
            'created_leads': ['lead1', 'lead2'],
            'updated_leads': [],
            'duplicate_actions': [],
            'processing_stats': {'processing_time_ms': 500}
        }
        mock_db_class.return_value = mock_db
        
        # Setup status service mock
        mock_status = Mock()
        mock_status.get_status.return_value = {
            'progress': {
                'totalBatches': 2,
                'completedBatches': 0,
                'processedLeads': 0
            }
        }
        mock_status_class.return_value = mock_status
        
        # Call lambda handler
        result = lambda_handler(sample_sqs_event, {})
        
        # Verify successful response
        assert result['statusCode'] == 200
        assert 'results' in result['body']
        
        # Verify status service was initialized
        mock_status_class.assert_called_once_with(table_name='test-status-table')
        
        # Verify status was retrieved
        mock_status.get_status.assert_called_once_with('test-upload-456')
        
        # Verify status was updated with progress
        mock_status.update_status.assert_called_once()
        call_args = mock_status.update_status.call_args
        
        assert call_args[1]['upload_id'] == 'test-upload-456'
        assert 'progress' in call_args[1]
        
        progress = call_args[1]['progress']
        assert progress['totalBatches'] == 2
        assert progress['completedBatches'] == 1  # First batch completed
        assert progress['processedLeads'] == 2   # Two leads processed
        
        # Verify not marked as completed (only 1 of 2 batches done)
        assert call_args[1].get('status') != 'completed'
    
    @patch('lambda_function.requests.post')
    @patch('lambda_function.DynamoDBUtils')
    @patch('lambda_function.ProcessingStatusService')
    def test_final_batch_processing_marks_completed(self, mock_status_class, mock_db_class, mock_requests, sample_sqs_event):
        """Test that processing the final batch marks status as completed."""
        # Modify event to be the final batch
        event_data = json.loads(sample_sqs_event['Records'][0]['body'])
        event_data['batch_number'] = 2  # Final batch
        sample_sqs_event['Records'][0]['body'] = json.dumps(event_data)
        
        # Setup DeepSeek API mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': json.dumps([
                        {
                            'firstName': 'John',
                            'lastName': 'Doe',
                            'email': 'john@example.com',
                            'company': 'Acme Corp',
                            'title': 'Manager',
                            'phone': '+1-555-123-4567',
                            'remarks': 'N/A'
                        }
                    ])
                }
            }]
        }
        mock_requests.return_value = mock_response
        
        # Setup DynamoDB mock
        mock_db = Mock()
        mock_db.batch_upsert_leads.return_value = {
            'created_leads': ['lead3'],
            'updated_leads': [],
            'duplicate_actions': [],
            'processing_stats': {'processing_time_ms': 300}
        }
        mock_db_class.return_value = mock_db
        
        # Setup status service mock - simulate first batch already completed
        mock_status = Mock()
        mock_status.get_status.return_value = {
            'progress': {
                'totalBatches': 2,
                'completedBatches': 1,  # First batch already done
                'processedLeads': 2     # Two leads already processed
            }
        }
        mock_status_class.return_value = mock_status
        
        # Call lambda handler
        result = lambda_handler(sample_sqs_event, {})
        
        # Verify successful response
        assert result['statusCode'] == 200
        
        # Verify status was updated with completion
        mock_status.update_status.assert_called_once()
        call_args = mock_status.update_status.call_args
        
        assert call_args[1]['upload_id'] == 'test-upload-456'
        assert call_args[1]['status'] == 'completed'
        assert call_args[1]['stage'] == 'completed'
        
        progress = call_args[1]['progress']
        assert progress['totalBatches'] == 2
        assert progress['completedBatches'] == 2  # All batches completed
        assert progress['processedLeads'] == 3   # Total leads processed (2 + 1)
    
    @patch('lambda_function.requests.post')
    @patch('lambda_function.DynamoDBUtils')
    @patch('lambda_function.ProcessingStatusService')
    def test_deepseek_api_error_updates_status(self, mock_status_class, mock_db_class, mock_requests, sample_sqs_event):
        """Test that DeepSeek API errors update status correctly."""
        # Setup DeepSeek API mock to fail
        mock_requests.side_effect = Exception("API connection failed")
        
        # Setup DynamoDB mock
        mock_db = Mock()
        mock_db_class.return_value = mock_db
        
        # Setup status service mock
        mock_status = Mock()
        mock_status_class.return_value = mock_status
        
        # Call lambda handler
        result = lambda_handler(sample_sqs_event, {})
        
        # Verify error response (ExternalAPIError returns 502)
        assert result['statusCode'] == 502
        assert 'error' in result['body']
        
        # Verify error status was set (called twice - once for DeepSeek error, once for batch error)
        assert mock_status.set_error.call_count == 2
        
        # Check the first call (DeepSeek error)
        first_call = mock_status.set_error.call_args_list[0]
        assert first_call[1]['upload_id'] == 'test-upload-456'
        assert 'DeepSeek processing failed for batch 1' in first_call[1]['error_message']
        assert first_call[1]['error_code'] == 'DEEPSEEK_API_ERROR'
    
    @patch('lambda_function.requests.post')
    @patch('lambda_function.DynamoDBUtils')
    @patch('lambda_function.ProcessingStatusService')
    def test_database_error_updates_status(self, mock_status_class, mock_db_class, mock_requests, sample_sqs_event):
        """Test that database errors update status correctly."""
        # Setup DeepSeek API mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': json.dumps([
                        {
                            'firstName': 'John',
                            'lastName': 'Doe',
                            'email': 'john@example.com',
                            'company': 'Acme Corp',
                            'title': 'Manager',
                            'phone': '+1-555-123-4567',
                            'remarks': 'N/A'
                        }
                    ])
                }
            }]
        }
        mock_requests.return_value = mock_response
        
        # Setup DynamoDB mock to fail
        mock_db = Mock()
        mock_db.batch_upsert_leads.side_effect = Exception("Database connection failed")
        mock_db.batch_create_leads.side_effect = Exception("Fallback also failed")
        mock_db_class.return_value = mock_db
        
        # Setup status service mock
        mock_status = Mock()
        mock_status_class.return_value = mock_status
        
        # Call lambda handler
        result = lambda_handler(sample_sqs_event, {})
        
        # Verify error response
        assert result['statusCode'] == 500
        assert 'error' in result['body']
        
        # Verify error status was set (called twice - once for database error, once for batch error)
        assert mock_status.set_error.call_count == 2
        
        # Check the first call (database error)
        first_call = mock_status.set_error.call_args_list[0]
        assert first_call[1]['upload_id'] == 'test-upload-456'
        assert 'Database storage failed for batch 1' in first_call[1]['error_message']
        assert first_call[1]['error_code'] == 'DATABASE_ERROR'
    
    @patch('lambda_function.requests.post')
    @patch('lambda_function.DynamoDBUtils')
    def test_graceful_degradation_without_status_service(self, mock_db_class, mock_requests, sample_sqs_event):
        """Test that processing works gracefully without status service."""
        # Don't set PROCESSING_STATUS_TABLE environment variable
        if 'PROCESSING_STATUS_TABLE' in os.environ:
            del os.environ['PROCESSING_STATUS_TABLE']
        
        # Setup DeepSeek API mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': json.dumps([
                        {
                            'firstName': 'John',
                            'lastName': 'Doe',
                            'email': 'john@example.com',
                            'company': 'Acme Corp',
                            'title': 'Manager',
                            'phone': '+1-555-123-4567',
                            'remarks': 'N/A'
                        }
                    ])
                }
            }]
        }
        mock_requests.return_value = mock_response
        
        # Setup DynamoDB mock
        mock_db = Mock()
        mock_db.batch_upsert_leads.return_value = {
            'created_leads': ['lead1'],
            'updated_leads': [],
            'duplicate_actions': [],
            'processing_stats': {'processing_time_ms': 300}
        }
        mock_db_class.return_value = mock_db
        
        # Call lambda handler
        result = lambda_handler(sample_sqs_event, {})
        
        # Verify successful response
        assert result['statusCode'] == 200
        assert 'results' in result['body']
        
        # Verify processing completed successfully without status updates
        results = result['body']['results']
        assert len(results) == 1
        assert results[0]['batch_id'] == 'test-batch-123'
        assert results[0]['upload_id'] == 'test-upload-456'
        assert results[0]['processed_leads'] == 1
        
        # Restore environment variable for other tests
        os.environ['PROCESSING_STATUS_TABLE'] = 'test-status-table'
    
    @patch('lambda_function.requests.post')
    @patch('lambda_function.DynamoDBUtils')
    @patch('lambda_function.ProcessingStatusService')
    def test_batch_without_upload_id_skips_status_updates(self, mock_status_class, mock_db_class, mock_requests, sample_sqs_event):
        """Test that batches without upload_id skip status updates gracefully."""
        # Remove upload_id from event
        event_data = json.loads(sample_sqs_event['Records'][0]['body'])
        del event_data['upload_id']
        sample_sqs_event['Records'][0]['body'] = json.dumps(event_data)
        
        # Setup DeepSeek API mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': json.dumps([
                        {
                            'firstName': 'John',
                            'lastName': 'Doe',
                            'email': 'john@example.com',
                            'company': 'Acme Corp',
                            'title': 'Manager',
                            'phone': '+1-555-123-4567',
                            'remarks': 'N/A'
                        }
                    ])
                }
            }]
        }
        mock_requests.return_value = mock_response
        
        # Setup DynamoDB mock
        mock_db = Mock()
        mock_db.batch_upsert_leads.return_value = {
            'created_leads': ['lead1'],
            'updated_leads': [],
            'duplicate_actions': [],
            'processing_stats': {'processing_time_ms': 300}
        }
        mock_db_class.return_value = mock_db
        
        # Setup status service mock
        mock_status = Mock()
        mock_status_class.return_value = mock_status
        
        # Call lambda handler
        result = lambda_handler(sample_sqs_event, {})
        
        # Verify successful response
        assert result['statusCode'] == 200
        
        # Verify status service was not called (no upload_id)
        mock_status.get_status.assert_not_called()
        mock_status.update_status.assert_not_called()
        mock_status.set_error.assert_not_called()
        
        # Verify processing completed successfully
        results = result['body']['results']
        assert len(results) == 1
        assert results[0]['batch_id'] == 'test-batch-123'
        assert results[0]['upload_id'] is None
        assert results[0]['processed_leads'] == 1


if __name__ == '__main__':
    pytest.main([__file__])