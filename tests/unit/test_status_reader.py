import json
import pytest
from unittest.mock import patch, Mock
import os
import sys

# Add the lambda directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lambda/status-reader'))

# Import the lambda function
import lambda_function

@pytest.fixture
def mock_env():
    """Mock environment variables"""
    with patch.dict(os.environ, {
        'PROCESSING_STATUS_TABLE': 'test-processing-status-table'
    }):
        yield

class TestStatusReaderLambda:
    """Test cases for the Status Reader Lambda function"""
    
    def setup_method(self):
        """Reset global state before each test"""
        lambda_function.dynamodb = None
        lambda_function.table = None
    
    def test_successful_status_retrieval(self, mock_env):
        """Test successful status retrieval"""
        # Arrange
        upload_id = 'test-upload-123'
        status_item = {
            'uploadId': upload_id,
            'status': 'processing',
            'stage': 'batch_processing',
            'progress': {
                'totalBatches': 10,
                'completedBatches': 3,
                'totalLeads': 100,
                'processedLeads': 30
            },
            'metadata': {
                'fileName': 'test.xlsx',
                'fileSize': 1024000,
                'startTime': '2025-01-09T10:00:00Z'
            },
            'createdAt': '2025-01-09T10:00:00Z',
            'updatedAt': '2025-01-09T10:02:30Z'
        }
        
        event = {
            'pathParameters': {
                'uploadId': upload_id
            }
        }
        
        # Act
        with patch('lambda_function.boto3.resource') as mock_boto3_resource:
            mock_table = Mock()
            mock_table.get_item.return_value = {'Item': status_item}
            
            mock_dynamodb = Mock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3_resource.return_value = mock_dynamodb
            
            response = lambda_function.lambda_handler(event, {})
        
        # Assert
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['uploadId'] == upload_id
        assert body['status'] == 'processing'
        assert body['stage'] == 'batch_processing'
        assert body['progress']['totalBatches'] == 10
        assert body['progress']['completedBatches'] == 3
        assert body['metadata']['fileName'] == 'test.xlsx'
        
        # Check CORS headers
        headers = response['headers']
        assert headers['Access-Control-Allow-Origin'] == '*'
        assert 'Access-Control-Allow-Headers' in headers
        assert 'Access-Control-Allow-Methods' in headers
    
    def test_missing_upload_id_parameter(self, mock_env):
        """Test handling of missing uploadId parameter"""
        # Arrange
        event = {
            'pathParameters': {}
        }
        
        # Act
        response = lambda_function.lambda_handler(event, {})
        
        # Assert
        assert response['statusCode'] == 400
        
        body = json.loads(response['body'])
        assert 'error' in body
        assert body['error'] == 'Missing uploadId parameter'
    
    def test_null_path_parameters(self, mock_env):
        """Test handling of null pathParameters"""
        # Arrange
        event = {
            'pathParameters': None
        }
        
        # Act
        response = lambda_function.lambda_handler(event, {})
        
        # Assert
        assert response['statusCode'] == 400
        
        body = json.loads(response['body'])
        assert 'error' in body
        assert body['error'] == 'Missing uploadId parameter'
    
    def test_status_not_found(self, mock_env):
        """Test handling when status is not found"""
        # Arrange
        upload_id = 'non-existent-upload-id'
        event = {
            'pathParameters': {
                'uploadId': upload_id
            }
        }
        
        # Act
        with patch('lambda_function.boto3.resource') as mock_boto3_resource:
            mock_table = Mock()
            mock_table.get_item.return_value = {}  # No Item key means not found
            
            mock_dynamodb = Mock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3_resource.return_value = mock_dynamodb
            
            response = lambda_function.lambda_handler(event, {})
        
        # Assert
        assert response['statusCode'] == 404
        
        body = json.loads(response['body'])
        assert 'error' in body
        assert body['error'] == 'Status not found'
    
    def test_status_with_error_information(self, mock_env):
        """Test status retrieval with error information"""
        # Arrange
        upload_id = 'error-upload-123'
        status_item = {
            'uploadId': upload_id,
            'status': 'error',
            'stage': 'file_processing',
            'error': {
                'message': 'Invalid file format',
                'code': 'INVALID_FORMAT',
                'timestamp': '2025-01-09T10:05:00Z'
            },
            'createdAt': '2025-01-09T10:00:00Z',
            'updatedAt': '2025-01-09T10:05:00Z'
        }
        
        event = {
            'pathParameters': {
                'uploadId': upload_id
            }
        }
        
        # Act
        with patch('lambda_function.boto3.resource') as mock_boto3_resource:
            mock_table = Mock()
            mock_table.get_item.return_value = {'Item': status_item}
            
            mock_dynamodb = Mock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3_resource.return_value = mock_dynamodb
            
            response = lambda_function.lambda_handler(event, {})
        
        # Assert
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['uploadId'] == upload_id
        assert body['status'] == 'error'
        assert body['error']['message'] == 'Invalid file format'
        assert body['error']['code'] == 'INVALID_FORMAT'
    
    def test_dynamodb_client_error(self, mock_env):
        """Test handling of DynamoDB client errors"""
        # Arrange
        upload_id = 'test-upload-123'
        event = {
            'pathParameters': {
                'uploadId': upload_id
            }
        }
        
        # Act
        with patch('lambda_function.boto3.resource') as mock_boto3_resource:
            mock_table = Mock()
            mock_table.get_item.side_effect = Exception("DynamoDB error")
            
            mock_dynamodb = Mock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3_resource.return_value = mock_dynamodb
            
            response = lambda_function.lambda_handler(event, {})
        
        # Assert
        assert response['statusCode'] == 500
        
        body = json.loads(response['body'])
        assert 'error' in body
        assert body['error'] == 'Internal server error'
    
    def test_cors_headers_present_in_all_responses(self, mock_env):
        """Test that CORS headers are present in all responses"""
        # Test 404 response
        event = {
            'pathParameters': {
                'uploadId': 'non-existent'
            }
        }
        
        with patch('lambda_function.boto3.resource') as mock_boto3_resource:
            mock_table = Mock()
            mock_table.get_item.return_value = {}
            
            mock_dynamodb = Mock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3_resource.return_value = mock_dynamodb
            
            response = lambda_function.lambda_handler(event, {})
        
        # Assert CORS headers are present
        headers = response['headers']
        assert headers['Access-Control-Allow-Origin'] == '*'
        assert 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token' in headers['Access-Control-Allow-Headers']
        assert 'GET,OPTIONS' in headers['Access-Control-Allow-Methods']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])