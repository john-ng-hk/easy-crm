"""
Unit tests for File Upload Lambda function.
Tests presigned URL generation, validation, and error handling.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError
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

    # Import after path setup and env patching
    import lambda_function
    from lambda_function import lambda_handler, validate_upload_request, generate_file_metadata
    from error_handling import ValidationError, LambdaError

class TestFileUploadLambda:
    """Test cases for file upload Lambda function."""
    
    def setup_method(self):
        """Set up test environment before each test."""
        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            'UPLOAD_BUCKET': 'test-upload-bucket',
            'MAX_FILE_SIZE_MB': '10',
            'PRESIGNED_URL_EXPIRATION': '3600'
        })
        self.env_patcher.start()
        
        # Mock context
        self.mock_context = Mock()
        self.mock_context.aws_request_id = 'test-request-id'
    
    def teardown_method(self):
        """Clean up after each test."""
        self.env_patcher.stop()
    
    @patch('lambda_function.s3_client')
    def test_successful_csv_upload_request(self, mock_s3_client):
        """Test successful presigned URL generation for CSV file."""
        # Arrange
        mock_s3_client.generate_presigned_url.return_value = 'https://test-presigned-url.com'
        
        event = {
            'body': json.dumps({
                'fileName': 'test_leads.csv',
                'fileType': 'text/csv',
                'fileSize': 1024
            })
        }
        
        # Act
        response = lambda_handler(event, self.mock_context)
        
        # Assert
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'uploadUrl' in body
        assert 'fileKey' in body
        assert 'fileId' in body
        assert 'expiresIn' in body
        assert body['uploadUrl'] == 'https://test-presigned-url.com'
        assert body['expiresIn'] == 3600
        assert 'uploads/' in body['fileKey']
        assert body['fileKey'].endswith('/test_leads.csv')
        
        # Verify S3 client was called correctly
        mock_s3_client.generate_presigned_url.assert_called_once()
        call_args = mock_s3_client.generate_presigned_url.call_args
        assert call_args[0][0] == 'put_object'
        assert call_args[1]['Params']['Bucket'] == 'test-upload-bucket'
        assert call_args[1]['Params']['ContentType'] == 'text/csv'
        assert call_args[1]['Params']['ContentLength'] == 1024
        assert call_args[1]['ExpiresIn'] == 3600
    
    @patch('lambda_function.s3_client')
    def test_successful_excel_upload_request(self, mock_s3_client):
        """Test successful presigned URL generation for Excel file."""
        # Arrange
        mock_s3_client.generate_presigned_url.return_value = 'https://test-presigned-url.com'
        
        event = {
            'body': json.dumps({
                'fileName': 'test_leads.xlsx',
                'fileType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'fileSize': 2048
            })
        }
        
        # Act
        response = lambda_handler(event, self.mock_context)
        
        # Assert
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['uploadUrl'] == 'https://test-presigned-url.com'
        assert body['fileKey'].endswith('/test_leads.xlsx')
    
    def test_missing_filename_validation(self):
        """Test validation error when fileName is missing."""
        # Arrange
        event = {
            'body': json.dumps({
                'fileType': 'text/csv',
                'fileSize': 1024
            })
        }
        
        # Act
        response = lambda_handler(event, self.mock_context)
        
        # Assert
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'VALIDATION_ERROR'
        assert 'fileName is required' in body['error']['message']
    
    def test_missing_filesize_validation(self):
        """Test validation error when fileSize is missing."""
        # Arrange
        event = {
            'body': json.dumps({
                'fileName': 'test.csv',
                'fileType': 'text/csv'
            })
        }
        
        # Act
        response = lambda_handler(event, self.mock_context)
        
        # Assert
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'VALIDATION_ERROR'
        assert 'fileSize is required' in body['error']['message']
    
    def test_invalid_file_type_validation(self):
        """Test validation error for unsupported file types."""
        # Arrange
        event = {
            'body': json.dumps({
                'fileName': 'test.txt',
                'fileType': 'text/plain',
                'fileSize': 1024
            })
        }
        
        # Act
        response = lambda_handler(event, self.mock_context)
        
        # Assert
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'VALIDATION_ERROR'
        assert 'Invalid file type' in body['error']['message']
    
    def test_file_size_too_large_validation(self):
        """Test validation error when file size exceeds limit."""
        # Arrange
        large_file_size = 15 * 1024 * 1024  # 15MB (exceeds 10MB limit)
        event = {
            'body': json.dumps({
                'fileName': 'large_file.csv',
                'fileType': 'text/csv',
                'fileSize': large_file_size
            })
        }
        
        # Act
        response = lambda_handler(event, self.mock_context)
        
        # Assert
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'VALIDATION_ERROR'
        assert 'exceeds maximum limit' in body['error']['message']
    
    def test_invalid_json_body(self):
        """Test error handling for invalid JSON in request body."""
        # Arrange
        event = {
            'body': 'invalid json {'
        }
        
        # Act
        response = lambda_handler(event, self.mock_context)
        
        # Assert
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'VALIDATION_ERROR'
        assert 'Invalid JSON' in body['error']['message']
    
    def test_invalid_file_size_format(self):
        """Test validation error for non-numeric file size."""
        # Arrange
        event = {
            'body': json.dumps({
                'fileName': 'test.csv',
                'fileType': 'text/csv',
                'fileSize': 'not_a_number'
            })
        }
        
        # Act
        response = lambda_handler(event, self.mock_context)
        
        # Assert
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error']['code'] == 'VALIDATION_ERROR'
        assert 'must be a valid integer' in body['error']['message']
    
    @patch('lambda_function.s3_client')
    def test_s3_bucket_not_found_error(self, mock_s3_client):
        """Test error handling when S3 bucket doesn't exist."""
        # Arrange
        mock_s3_client.generate_presigned_url.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchBucket', 'Message': 'Bucket not found'}},
            'generate_presigned_url'
        )
        
        event = {
            'body': json.dumps({
                'fileName': 'test.csv',
                'fileType': 'text/csv',
                'fileSize': 1024
            })
        }
        
        # Act
        response = lambda_handler(event, self.mock_context)
        
        # Assert
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['error']['code'] == 'BUCKET_NOT_FOUND'
        assert 'Upload bucket not found' in body['error']['message']
    
    @patch('lambda_function.s3_client')
    def test_s3_access_denied_error(self, mock_s3_client):
        """Test error handling for S3 access denied."""
        # Arrange
        mock_s3_client.generate_presigned_url.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
            'generate_presigned_url'
        )
        
        event = {
            'body': json.dumps({
                'fileName': 'test.csv',
                'fileType': 'text/csv',
                'fileSize': 1024
            })
        }
        
        # Act
        response = lambda_handler(event, self.mock_context)
        
        # Assert
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['error']['code'] == 'ACCESS_DENIED'
        assert 'Insufficient permissions' in body['error']['message']
    
    @patch('lambda_function.s3_client')
    def test_generic_s3_error(self, mock_s3_client):
        """Test error handling for generic S3 errors."""
        # Arrange
        mock_s3_client.generate_presigned_url.side_effect = ClientError(
            {'Error': {'Code': 'InternalError', 'Message': 'Internal error'}},
            'generate_presigned_url'
        )
        
        event = {
            'body': json.dumps({
                'fileName': 'test.csv',
                'fileType': 'text/csv',
                'fileSize': 1024
            })
        }
        
        # Act
        response = lambda_handler(event, self.mock_context)
        
        # Assert
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['error']['code'] == 'S3_ERROR'
        assert 'Failed to generate upload URL' in body['error']['message']
    
    def test_validate_upload_request_success(self):
        """Test successful upload request validation."""
        # Arrange
        valid_body = {
            'fileName': 'test.csv',
            'fileSize': 1024
        }
        
        # Act & Assert (should not raise exception)
        validate_upload_request(valid_body)
    
    def test_validate_upload_request_missing_fields(self):
        """Test upload request validation with missing required fields."""
        # Test missing fileName
        with pytest.raises(ValidationError) as exc_info:
            validate_upload_request({'fileSize': 1024})
        assert 'fileName is required' in str(exc_info.value)
        
        # Test missing fileSize
        with pytest.raises(ValidationError) as exc_info:
            validate_upload_request({'fileName': 'test.csv'})
        assert 'fileSize is required' in str(exc_info.value)
    
    def test_validate_upload_request_dangerous_filename(self):
        """Test upload request validation with dangerous file names."""
        dangerous_names = [
            '../../../etc/passwd',
            'file<script>alert(1)</script>.csv',
            'file|rm -rf /.csv',
            'file"quotes".csv'
        ]
        
        for dangerous_name in dangerous_names:
            with pytest.raises(ValidationError) as exc_info:
                validate_upload_request({
                    'fileName': dangerous_name,
                    'fileSize': 1024
                })
            assert 'invalid characters' in str(exc_info.value)
    
    def test_validate_upload_request_long_filename(self):
        """Test upload request validation with overly long file name."""
        # Arrange
        long_filename = 'a' * 256 + '.csv'  # 260 characters total
        
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            validate_upload_request({
                'fileName': long_filename,
                'fileSize': 1024
            })
        assert 'too long' in str(exc_info.value)
    
    def test_generate_file_metadata(self):
        """Test file metadata generation."""
        # Arrange
        file_name = 'test_leads.csv'
        file_size = 1024
        file_type = 'text/csv'
        
        # Act
        metadata = generate_file_metadata(file_name, file_size, file_type)
        
        # Assert
        assert metadata['original-filename'] == file_name
        assert metadata['file-size'] == str(file_size)
        assert metadata['content-type'] == file_type
        assert metadata['processing-status'] == 'pending'
        assert 'upload-timestamp' in metadata
    
    @patch('lambda_function.s3_client')
    def test_file_key_uniqueness(self, mock_s3_client):
        """Test that generated file keys are unique."""
        # Arrange
        mock_s3_client.generate_presigned_url.return_value = 'https://test-url.com'
        
        event = {
            'body': json.dumps({
                'fileName': 'test.csv',
                'fileType': 'text/csv',
                'fileSize': 1024
            })
        }
        
        # Act - make multiple requests
        response1 = lambda_handler(event, self.mock_context)
        response2 = lambda_handler(event, self.mock_context)
        
        # Assert
        body1 = json.loads(response1['body'])
        body2 = json.loads(response2['body'])
        
        assert body1['fileKey'] != body2['fileKey']
        assert body1['fileId'] != body2['fileId']
    
    def test_supported_file_extensions(self):
        """Test all supported file extensions are accepted."""
        supported_files = [
            ('test.csv', 'text/csv'),
            ('test.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('test.xls', 'application/vnd.ms-excel')
        ]
        
        for file_name, content_type in supported_files:
            body = {
                'fileName': file_name,
                'fileType': content_type,
                'fileSize': 1024
            }
            
            # Should not raise ValidationError
            validate_upload_request(body)
    
    @patch('lambda_function.s3_client')
    def test_response_includes_configuration_info(self, mock_s3_client):
        """Test that response includes useful configuration information."""
        # Arrange
        mock_s3_client.generate_presigned_url.return_value = 'https://test-url.com'
        
        event = {
            'body': json.dumps({
                'fileName': 'test.csv',
                'fileType': 'text/csv',
                'fileSize': 1024
            })
        }
        
        # Act
        response = lambda_handler(event, self.mock_context)
        
        # Assert
        body = json.loads(response['body'])
        assert 'maxFileSize' in body
        assert 'supportedTypes' in body
        assert body['maxFileSize'] == 10 * 1024 * 1024  # 10MB in bytes
        assert isinstance(body['supportedTypes'], list)
        assert len(body['supportedTypes']) > 0

if __name__ == '__main__':
    pytest.main([__file__])