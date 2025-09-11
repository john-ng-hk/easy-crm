"""
Integration tests for status-reader Lambda function error handling and recovery.
"""

import pytest
import json
import boto3
from moto import mock_aws
import sys
import os

# Add the lambda directory to the path
status_reader_path = os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'status-reader')
shared_path = os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared')
sys.path.insert(0, status_reader_path)
sys.path.insert(0, shared_path)

from lambda_function import lambda_handler, enhance_status_response, get_user_friendly_message, get_recovery_options


class TestStatusReaderErrorHandling:
    """Test error handling in status-reader Lambda function."""
    
    @mock_aws
    def setup_method(self):
        """Set up test fixtures."""
        # Create mock DynamoDB table
        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        self.table_name = 'test-processing-status'
        
        self.table = self.dynamodb.create_table(
            TableName=self.table_name,
            KeySchema=[
                {'AttributeName': 'uploadId', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'uploadId', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Set environment variable
        os.environ['PROCESSING_STATUS_TABLE'] = self.table_name
        
        self.test_upload_id = 'test-upload-123'
    
    def teardown_method(self):
        """Clean up after tests."""
        if 'PROCESSING_STATUS_TABLE' in os.environ:
            del os.environ['PROCESSING_STATUS_TABLE']
    
    def test_missing_upload_id_parameter(self):
        """Test handling of missing uploadId parameter."""
        event = {
            'httpMethod': 'GET',
            'pathParameters': None
        }
        context = type('Context', (), {'aws_request_id': 'test-request-123'})()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Missing uploadId parameter' in body['error']['message']
    
    def test_empty_upload_id_parameter(self):
        """Test handling of empty uploadId parameter."""
        event = {
            'httpMethod': 'GET',
            'pathParameters': {'uploadId': ''}
        }
        context = type('Context', (), {'aws_request_id': 'test-request-123'})()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Missing uploadId parameter' in body['error']['message']
    
    @mock_aws
    def test_status_not_found(self):
        """Test handling when status record is not found."""
        event = {
            'httpMethod': 'GET',
            'pathParameters': {'uploadId': 'non-existent-upload'}
        }
        context = type('Context', (), {'aws_request_id': 'test-request-123'})()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert 'STATUS_NOT_FOUND' in body['error']['code']
    
    @mock_aws
    def test_successful_status_retrieval(self):
        """Test successful status retrieval with enhancement."""
        # Insert test status record
        test_status = {
            'uploadId': self.test_upload_id,
            'status': 'processing',
            'stage': 'batch_processing',
            'progress': {
                'totalBatches': 10,
                'completedBatches': 5,
                'percentage': 50.0
            },
            'metadata': {
                'fileName': 'test.csv',
                'fileSize': 1024
            },
            'createdAt': '2023-01-01T00:00:00Z',
            'updatedAt': '2023-01-01T00:05:00Z'
        }
        
        self.table.put_item(Item=test_status)
        
        event = {
            'httpMethod': 'GET',
            'pathParameters': {'uploadId': self.test_upload_id}
        }
        context = type('Context', (), {'aws_request_id': 'test-request-123'})()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Check enhanced response
        assert body['uploadId'] == self.test_upload_id
        assert body['status'] == 'processing'
        assert 'userMessage' in body
        assert 'progressIndicators' in body
        assert 'Processing your leads' in body['userMessage']
    
    @mock_aws
    def test_error_status_with_recovery_options(self):
        """Test status retrieval for error state with recovery options."""
        # Insert test error status record
        test_status = {
            'uploadId': self.test_upload_id,
            'status': 'error',
            'error': {
                'message': 'Network timeout occurred',
                'code': 'NETWORK_ERROR',
                'recoverable': True,
                'retryAfter': 30
            },
            'createdAt': '2023-01-01T00:00:00Z',
            'updatedAt': '2023-01-01T00:05:00Z'
        }
        
        self.table.put_item(Item=test_status)
        
        event = {
            'httpMethod': 'GET',
            'pathParameters': {'uploadId': self.test_upload_id}
        }
        context = type('Context', (), {'aws_request_id': 'test-request-123'})()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Check error handling and recovery options
        assert body['status'] == 'error'
        assert 'recovery' in body
        assert body['recovery']['available'] == True
        assert len(body['recovery']['options']) > 0
        assert 'Recovery options available' in body['userMessage']
    
    def test_options_request_cors(self):
        """Test CORS OPTIONS request handling."""
        event = {
            'httpMethod': 'OPTIONS'
        }
        context = type('Context', (), {'aws_request_id': 'test-request-123'})()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in response['headers']
        assert 'Access-Control-Allow-Methods' in response['headers']
    
    def test_enhance_status_response_processing(self):
        """Test status response enhancement for processing state."""
        status_data = {
            'uploadId': 'test-123',
            'status': 'processing',
            'stage': 'batch_processing',
            'progress': {
                'totalBatches': 10,
                'completedBatches': 3,
                'percentage': 30.0
            }
        }
        
        enhanced = enhance_status_response(status_data)
        
        assert 'userMessage' in enhanced
        assert 'progressIndicators' in enhanced
        assert 'Processing your leads' in enhanced['userMessage']
        assert enhanced['progressIndicators']['percentage'] == 30.0
    
    def test_enhance_status_response_completed(self):
        """Test status response enhancement for completed state."""
        status_data = {
            'uploadId': 'test-123',
            'status': 'completed',
            'progress': {
                'processedLeads': 100,
                'createdLeads': 80,
                'updatedLeads': 20
            }
        }
        
        enhanced = enhance_status_response(status_data)
        
        assert 'userMessage' in enhanced
        assert 'Successfully processed 100 leads' in enhanced['userMessage']
        assert '80 new, 20 updated' in enhanced['userMessage']
    
    def test_enhance_status_response_error_recoverable(self):
        """Test status response enhancement for recoverable error state."""
        status_data = {
            'uploadId': 'test-123',
            'status': 'error',
            'error': {
                'message': 'API timeout',
                'code': 'API_ERROR',
                'recoverable': True,
                'retryAfter': 60
            }
        }
        
        enhanced = enhance_status_response(status_data)
        
        assert 'userMessage' in enhanced
        assert 'recovery' in enhanced
        assert enhanced['recovery']['available'] == True
        assert 'Recovery options available' in enhanced['userMessage']
    
    def test_enhance_status_response_error_non_recoverable(self):
        """Test status response enhancement for non-recoverable error state."""
        status_data = {
            'uploadId': 'test-123',
            'status': 'error',
            'error': {
                'message': 'Invalid file format',
                'code': 'VALIDATION_ERROR',
                'recoverable': False
            }
        }
        
        enhanced = enhance_status_response(status_data)
        
        assert 'userMessage' in enhanced
        assert 'recovery' in enhanced
        assert enhanced['recovery']['available'] == False
        assert 'Invalid file format' in enhanced['userMessage']
    
    def test_get_user_friendly_message_various_states(self):
        """Test user-friendly message generation for various states."""
        test_cases = [
            ({'status': 'uploading'}, 'uploading'),
            ({'status': 'uploaded'}, 'uploaded successfully'),
            ({'status': 'processing', 'stage': 'file_processing'}, 'Reading and validating'),
            ({'status': 'processing', 'stage': 'batch_processing', 'progress': {'completedBatches': 3, 'totalBatches': 10}}, 'batch 3 of 10'),
            ({'status': 'completed', 'progress': {'processedLeads': 50}}, 'Successfully processed 50 leads'),
            ({'status': 'cancelled'}, 'cancelled by user'),
        ]
        
        for status_data, expected_text in test_cases:
            message = get_user_friendly_message(status_data)
            assert expected_text.lower() in message.lower()
    
    def test_get_recovery_options_network_error(self):
        """Test recovery options for network errors."""
        status_data = {
            'error': {
                'code': 'NETWORK_ERROR',
                'recoverable': True,
                'retryAfter': 30
            }
        }
        
        recovery = get_recovery_options(status_data)
        
        assert recovery['available'] == True
        assert len(recovery['options']) > 0
        assert any(option['type'] == 'retry' for option in recovery['options'])
    
    def test_get_recovery_options_validation_error(self):
        """Test recovery options for validation errors."""
        status_data = {
            'error': {
                'code': 'VALIDATION_ERROR',
                'recoverable': True
            }
        }
        
        recovery = get_recovery_options(status_data)
        
        assert recovery['available'] == True
        assert any(option['type'] == 'reupload' for option in recovery['options'])
    
    def test_get_recovery_options_non_recoverable(self):
        """Test recovery options for non-recoverable errors."""
        status_data = {
            'error': {
                'code': 'FATAL_ERROR',
                'recoverable': False
            }
        }
        
        recovery = get_recovery_options(status_data)
        
        assert recovery['available'] == False
        assert 'cannot be automatically recovered' in recovery['message']


if __name__ == '__main__':
    pytest.main([__file__])