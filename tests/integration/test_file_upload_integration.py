"""
Integration tests for File Upload Lambda function.
Tests the function with realistic scenarios and actual AWS service interactions.
"""

import json
import pytest
from unittest.mock import Mock, patch
import sys
import os

# Patch environment variables before importing
with patch.dict(os.environ, {
    'UPLOAD_BUCKET': 'test-upload-bucket',
    'MAX_FILE_SIZE_MB': '10',
    'PRESIGNED_URL_EXPIRATION': '3600'
}):
    # Add lambda directory to path for imports
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lambda/file-upload'))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lambda/shared'))

    from lambda_function import lambda_handler

class TestFileUploadIntegration:
    """Integration test cases for file upload Lambda function."""
    
    def setup_method(self):
        """Set up test environment before each test."""
        # Mock context
        self.mock_context = Mock()
        self.mock_context.aws_request_id = 'integration-test-request-id'
    
    @patch('lambda_function.s3_client')
    def test_realistic_csv_upload_scenario(self, mock_s3_client):
        """Test a realistic CSV file upload scenario."""
        # Arrange - simulate a real CSV file upload request
        mock_s3_client.generate_presigned_url.return_value = 'https://s3.amazonaws.com/test-bucket/presigned-url'
        
        event = {
            'httpMethod': 'POST',
            'headers': {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer test-jwt-token'
            },
            'body': json.dumps({
                'fileName': 'customer_leads_2024.csv',
                'fileType': 'text/csv',
                'fileSize': 2048576  # 2MB file
            })
        }
        
        # Act
        response = lambda_handler(event, self.mock_context)
        
        # Assert
        assert response['statusCode'] == 200
        
        # Verify CORS headers are present
        assert 'Access-Control-Allow-Origin' in response['headers']
        assert 'Access-Control-Allow-Headers' in response['headers']
        assert 'Access-Control-Allow-Methods' in response['headers']
        
        # Verify response body structure
        body = json.loads(response['body'])
        assert 'uploadUrl' in body
        assert 'fileKey' in body
        assert 'fileId' in body
        assert 'expiresIn' in body
        assert 'maxFileSize' in body
        assert 'supportedTypes' in body
        
        # Verify file key structure
        assert body['fileKey'].startswith('uploads/')
        assert body['fileKey'].endswith('/customer_leads_2024.csv')
        
        # Verify configuration values
        assert body['expiresIn'] == 3600
        assert body['maxFileSize'] == 10 * 1024 * 1024  # 10MB
        assert 'text/csv' in body['supportedTypes']
        
        # Verify S3 client was called with correct parameters
        mock_s3_client.generate_presigned_url.assert_called_once()
        call_args = mock_s3_client.generate_presigned_url.call_args
        
        assert call_args[0][0] == 'put_object'
        params = call_args[1]['Params']
        assert params['Bucket'] == 'test-upload-bucket'
        assert params['ContentType'] == 'text/csv'
        assert params['ContentLength'] == 2048576
        assert 'Metadata' in params
        assert params['Metadata']['original-filename'] == 'customer_leads_2024.csv'
    
    @patch('lambda_function.s3_client')
    def test_realistic_excel_upload_scenario(self, mock_s3_client):
        """Test a realistic Excel file upload scenario."""
        # Arrange
        mock_s3_client.generate_presigned_url.return_value = 'https://s3.amazonaws.com/test-bucket/excel-presigned-url'
        
        event = {
            'httpMethod': 'POST',
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'fileName': 'Q4_Sales_Leads.xlsx',
                'fileType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'fileSize': 5242880  # 5MB file
            })
        }
        
        # Act
        response = lambda_handler(event, self.mock_context)
        
        # Assert
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Verify Excel-specific handling
        assert body['fileKey'].endswith('/Q4_Sales_Leads.xlsx')
        
        # Verify S3 parameters for Excel file
        call_args = mock_s3_client.generate_presigned_url.call_args
        params = call_args[1]['Params']
        assert params['ContentType'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert params['ContentLength'] == 5242880
    
    def test_edge_case_maximum_file_size(self):
        """Test handling of maximum allowed file size."""
        # Arrange - exactly at the limit
        max_size = 10 * 1024 * 1024  # 10MB
        
        event = {
            'body': json.dumps({
                'fileName': 'large_leads_file.csv',
                'fileType': 'text/csv',
                'fileSize': max_size
            })
        }
        
        # Act & Assert - should not raise validation error
        with patch('lambda_function.s3_client') as mock_s3_client:
            mock_s3_client.generate_presigned_url.return_value = 'https://test-url.com'
            response = lambda_handler(event, self.mock_context)
            assert response['statusCode'] == 200
    
    def test_edge_case_just_over_file_size_limit(self):
        """Test handling of file size just over the limit."""
        # Arrange - 1 byte over the limit
        max_size = 10 * 1024 * 1024 + 1  # 10MB + 1 byte
        
        event = {
            'body': json.dumps({
                'fileName': 'oversized_file.csv',
                'fileType': 'text/csv',
                'fileSize': max_size
            })
        }
        
        # Act
        response = lambda_handler(event, self.mock_context)
        
        # Assert
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'exceeds maximum limit' in body['error']['message']
    
    def test_realistic_error_scenarios(self):
        """Test realistic error scenarios that might occur in production."""
        
        # Test 1: Empty file name
        event = {
            'body': json.dumps({
                'fileName': '',
                'fileType': 'text/csv',
                'fileSize': 1024
            })
        }
        
        response = lambda_handler(event, self.mock_context)
        assert response['statusCode'] == 400
        
        # Test 2: Malformed JSON
        event = {
            'body': '{"fileName": "test.csv", "fileSize": 1024'  # Missing closing brace
        }
        
        response = lambda_handler(event, self.mock_context)
        assert response['statusCode'] == 400
        
        # Test 3: Unsupported file type
        event = {
            'body': json.dumps({
                'fileName': 'document.pdf',
                'fileType': 'application/pdf',
                'fileSize': 1024
            })
        }
        
        response = lambda_handler(event, self.mock_context)
        assert response['statusCode'] == 400
    
    @patch('lambda_function.s3_client')
    def test_file_metadata_completeness(self, mock_s3_client):
        """Test that all required metadata is included in S3 object."""
        # Arrange
        mock_s3_client.generate_presigned_url.return_value = 'https://test-url.com'
        
        event = {
            'body': json.dumps({
                'fileName': 'test_metadata.csv',
                'fileType': 'text/csv',
                'fileSize': 1024
            })
        }
        
        # Act
        response = lambda_handler(event, self.mock_context)
        
        # Assert
        assert response['statusCode'] == 200
        
        # Verify metadata structure
        call_args = mock_s3_client.generate_presigned_url.call_args
        metadata = call_args[1]['Params']['Metadata']
        
        required_metadata_keys = [
            'original-filename',
            'upload-timestamp',
            'file-id'
        ]
        
        for key in required_metadata_keys:
            assert key in metadata, f"Missing required metadata key: {key}"
        
        # Verify metadata values
        assert metadata['original-filename'] == 'test_metadata.csv'
        assert len(metadata['file-id']) > 0  # Should have a file ID
        assert 'T' in metadata['upload-timestamp']  # Should be ISO format timestamp

if __name__ == '__main__':
    pytest.main([__file__])