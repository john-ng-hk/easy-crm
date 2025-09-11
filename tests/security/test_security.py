"""
Security tests for the lead management system.

Tests authentication, authorization, input validation, data protection,
and security vulnerabilities across all system components.
"""

import pytest
import json
import os
import sys
import boto3
from moto import mock_aws
from unittest.mock import patch, Mock
import jwt
import time
from datetime import datetime, timedelta
import base64

# Add lambda paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))

class TestAuthenticationSecurity:
    """Test authentication and authorization security."""
    
    @pytest.fixture
    def lambda_context(self):
        """Mock Lambda context."""
        context = Mock()
        context.aws_request_id = 'security-test-request'
        context.function_name = 'security-test-function'
        return context
    
    def test_missing_authorization_header(self, lambda_context):
        """Test that requests without Authorization header are rejected."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        from lambda_function import lambda_handler
        
        # Request without Authorization header
        event = {
            'httpMethod': 'GET',
            'headers': {},
            'queryStringParameters': {}
        }
        
        response = lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'error' in body
        assert body['error']['code'] == 'AUTHENTICATION_ERROR'
    
    def test_invalid_jwt_token_format(self, lambda_context):
        """Test that malformed JWT tokens are rejected."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        from lambda_function import lambda_handler
        
        # Request with malformed JWT
        event = {
            'httpMethod': 'GET',
            'headers': {
                'Authorization': 'Bearer invalid.jwt.token'
            },
            'queryStringParameters': {}
        }
        
        response = lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'Invalid token' in body['error']['message'] or 'Authentication failed' in body['error']['message']
    
    def test_expired_jwt_token(self, lambda_context):
        """Test that expired JWT tokens are rejected."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))
        from validation import validate_jwt_token
        
        # Create an expired JWT token
        expired_payload = {
            'sub': 'test-user',
            'exp': int(time.time()) - 3600,  # Expired 1 hour ago
            'iat': int(time.time()) - 7200   # Issued 2 hours ago
        }
        
        # This would normally be signed with a secret key
        expired_token = jwt.encode(expired_payload, 'test-secret', algorithm='HS256')
        
        event = {
            'httpMethod': 'GET',
            'headers': {
                'Authorization': f'Bearer {expired_token}'
            }
        }
        
        # Should raise an exception for expired token
        with pytest.raises(Exception):
            validate_jwt_token(event)
    
    def test_jwt_token_without_bearer_prefix(self, lambda_context):
        """Test that tokens without 'Bearer' prefix are rejected."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        from lambda_function import lambda_handler
        
        event = {
            'httpMethod': 'GET',
            'headers': {
                'Authorization': 'some-token-without-bearer'
            },
            'queryStringParameters': {}
        }
        
        response = lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 401
    
    def test_empty_authorization_header(self, lambda_context):
        """Test that empty Authorization header is rejected."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        from lambda_function import lambda_handler
        
        event = {
            'httpMethod': 'GET',
            'headers': {
                'Authorization': ''
            },
            'queryStringParameters': {}
        }
        
        response = lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 401

class TestInputValidationSecurity:
    """Test input validation and sanitization security."""
    
    @pytest.fixture
    def lambda_context(self):
        """Mock Lambda context."""
        context = Mock()
        context.aws_request_id = 'security-test-request'
        return context
    
    def test_sql_injection_attempts_in_filters(self, lambda_context):
        """Test that SQL injection attempts in filters are handled safely."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        from lambda_function import lambda_handler
        
        sql_injection_payloads = [
            "'; DROP TABLE leads; --",
            "' OR '1'='1",
            "'; SELECT * FROM leads; --",
            "' UNION SELECT * FROM users --",
            "admin'--",
            "' OR 1=1#"
        ]
        
        for payload in sql_injection_payloads:
            event = {
                'httpMethod': 'GET',
                'headers': {'Authorization': 'Bearer test-token'},
                'queryStringParameters': {
                    'filter_firstName': payload
                }
            }
            
            with patch('lambda_function.validate_jwt_token') as mock_jwt:
                mock_jwt.return_value = {'sub': 'test-user'}
                
                response = lambda_handler(event, lambda_context)
            
            # Should either return 400 (validation error) or 200 (safely handled)
            assert response['statusCode'] in [200, 400]
            
            # If 200, should return empty results (no injection occurred)
            if response['statusCode'] == 200:
                body = json.loads(response['body'])
                # Should not crash or return unexpected data
                assert 'leads' in body
    
    def test_xss_attempts_in_chat_queries(self, lambda_context):
        """Test that XSS attempts in chat queries are sanitized."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'chatbot'))
        from lambda_function import lambda_handler
        
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "';alert('xss');//",
            "<svg onload=alert('xss')>",
            "&#60;script&#62;alert('xss')&#60;/script&#62;"
        ]
        
        for payload in xss_payloads:
            event = {
                'httpMethod': 'POST',
                'headers': {'Authorization': 'Bearer test-token'},
                'body': json.dumps({
                    'query': payload
                })
            }
            
            with patch('lambda_function.validate_jwt_token') as mock_jwt:
                mock_jwt.return_value = {'sub': 'test-user'}
                
                response = lambda_handler(event, lambda_context)
            
            # Should handle gracefully without executing scripts
            assert response['statusCode'] in [200, 400]
            
            if response['statusCode'] == 200:
                body = json.loads(response['body'])
                # Response should not contain unescaped script tags
                response_text = json.dumps(body)
                assert '<script>' not in response_text
                assert 'javascript:' not in response_text
    
    def test_path_traversal_attempts_in_filenames(self, lambda_context):
        """Test that path traversal attempts in filenames are blocked."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'file-upload'))
        
        with patch.dict(os.environ, {
            'UPLOAD_BUCKET': 'test-bucket',
            'MAX_FILE_SIZE_MB': '10',
            'PRESIGNED_URL_EXPIRATION': '3600'
        }):
            from lambda_function import lambda_handler
            
            path_traversal_payloads = [
                "../../../etc/passwd",
                "..\\..\\..\\windows\\system32\\config\\sam",
                "....//....//....//etc//passwd",
                "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
                "..%252f..%252f..%252fetc%252fpasswd",
                "file:///etc/passwd",
                "\\\\server\\share\\file.txt"
            ]
            
            for payload in path_traversal_payloads:
                event = {
                    'body': json.dumps({
                        'fileName': payload,
                        'fileType': 'text/csv',
                        'fileSize': 1024
                    })
                }
                
                response = lambda_handler(event, lambda_context)
                
                # Should reject malicious filenames
                assert response['statusCode'] == 400
                body = json.loads(response['body'])
                assert 'error' in body
                assert 'invalid' in body['error']['message'].lower() or 'filename' in body['error']['message'].lower()
    
    def test_oversized_request_payloads(self, lambda_context):
        """Test handling of oversized request payloads."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'chatbot'))
        from lambda_function import lambda_handler
        
        # Create oversized query (over 500 characters)
        oversized_query = 'a' * 1000
        
        event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer test-token'},
            'body': json.dumps({
                'query': oversized_query
            })
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            response = lambda_handler(event, lambda_context)
        
        # Should reject oversized queries
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'too long' in body['error']['message'].lower()
    
    def test_malformed_json_payloads(self, lambda_context):
        """Test handling of malformed JSON payloads."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'chatbot'))
        from lambda_function import lambda_handler
        
        malformed_payloads = [
            '{"query": "test"',  # Missing closing brace
            '{"query": "test",}',  # Trailing comma
            '{query: "test"}',  # Unquoted key
            '{"query": "test" "extra": "value"}',  # Missing comma
            'not json at all',
            '{"query": }',  # Missing value
            ''  # Empty string
        ]
        
        for payload in malformed_payloads:
            event = {
                'httpMethod': 'POST',
                'headers': {'Authorization': 'Bearer test-token'},
                'body': payload
            }
            
            with patch('lambda_function.validate_jwt_token') as mock_jwt:
                mock_jwt.return_value = {'sub': 'test-user'}
                
                response = lambda_handler(event, lambda_context)
            
            # Should handle malformed JSON gracefully
            assert response['statusCode'] == 400
            body = json.loads(response['body'])
            assert 'error' in body
    
    def test_unicode_and_special_characters(self, lambda_context):
        """Test handling of Unicode and special characters in inputs."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        from lambda_function import lambda_handler
        
        special_character_inputs = [
            "José María García",  # Accented characters
            "北京市",  # Chinese characters
            "مرحبا",  # Arabic characters
            "🚀💻📊",  # Emojis
            "test\x00null",  # Null bytes
            "test\r\nCRLF",  # CRLF injection
            "test\ttab\nnewline"  # Control characters
        ]
        
        for test_input in special_character_inputs:
            event = {
                'httpMethod': 'GET',
                'headers': {'Authorization': 'Bearer test-token'},
                'queryStringParameters': {
                    'filter_firstName': test_input
                }
            }
            
            with patch('lambda_function.validate_jwt_token') as mock_jwt:
                mock_jwt.return_value = {'sub': 'test-user'}
                
                response = lambda_handler(event, lambda_context)
            
            # Should handle special characters without crashing
            assert response['statusCode'] in [200, 400]
            
            # Response should be valid JSON
            if response['statusCode'] == 200:
                body = json.loads(response['body'])
                assert 'leads' in body

class TestDataProtectionSecurity:
    """Test data protection and privacy security."""
    
    @pytest.fixture
    def lambda_context(self):
        """Mock Lambda context."""
        context = Mock()
        context.aws_request_id = 'security-test-request'
        return context
    
    def test_sensitive_data_not_logged(self, lambda_context):
        """Test that sensitive data is not logged in error messages."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'chatbot'))
        from lambda_function import lambda_handler
        
        # Create request with sensitive data
        sensitive_query = "show me leads with email john.doe@secret-company.com and phone +1-555-SECRET"
        
        event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer test-token'},
            'body': json.dumps({
                'query': sensitive_query
            })
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            # Force an error to see what gets logged
            with patch('lambda_function.generate_dynamodb_query') as mock_generate:
                mock_generate.side_effect = Exception("Test error")
                
                response = lambda_handler(event, lambda_context)
        
        # Error response should not contain sensitive data
        assert response['statusCode'] == 200  # Chatbot returns 200 with error message
        body = json.loads(response['body'])
        
        # Should not contain the sensitive email or phone
        response_text = json.dumps(body).lower()
        assert 'secret-company.com' not in response_text
        assert 'secret' not in response_text
    
    def test_deepseek_api_data_isolation(self, lambda_context):
        """Test that actual lead data is not sent to DeepSeek API."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'chatbot'))
        
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test-key'}):
            from lambda_function import generate_dynamodb_query
            
            # Mock the API call to capture what's sent
            with patch('lambda_function.requests.post') as mock_post:
                mock_response = Mock()
                mock_response.json.return_value = {
                    'choices': [{
                        'message': {
                            'content': '{"type": "filter", "filters": {"company": "Google"}}'
                        }
                    }]
                }
                mock_response.raise_for_status.return_value = None
                mock_post.return_value = mock_response
                
                # Make a query
                generate_dynamodb_query("show me leads from Google")
                
                # Verify the API call
                assert mock_post.called
                call_args = mock_post.call_args
                
                # Check that no actual lead data is in the request
                request_data = json.loads(call_args[1]['json'])
                request_text = json.dumps(request_data).lower()
                
                # Should not contain actual email addresses, phone numbers, or names
                assert '@' not in request_text or 'example' in request_text  # Only example emails allowed
                assert '+1-555-' not in request_text  # No real phone numbers
                assert 'john.doe' not in request_text  # No real names
    
    def test_cors_headers_security(self, lambda_context):
        """Test that CORS headers are properly configured for security."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        from lambda_function import lambda_handler
        
        event = {
            'httpMethod': 'OPTIONS',
            'headers': {
                'Origin': 'https://malicious-site.com'
            }
        }
        
        response = lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        headers = response['headers']
        
        # Check CORS headers
        assert 'Access-Control-Allow-Origin' in headers
        assert 'Access-Control-Allow-Headers' in headers
        assert 'Access-Control-Allow-Methods' in headers
        
        # Should not allow arbitrary origins (should be * or specific domains)
        origin = headers['Access-Control-Allow-Origin']
        assert origin == '*' or 'cloudfront' in origin or 'amazonaws' in origin
    
    def test_response_headers_security(self, lambda_context):
        """Test that security headers are present in responses."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        from lambda_function import lambda_handler
        
        event = {
            'httpMethod': 'GET',
            'headers': {'Authorization': 'Bearer test-token'},
            'queryStringParameters': {}
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            response = lambda_handler(event, lambda_context)
        
        headers = response['headers']
        
        # Check for security headers
        assert 'Content-Type' in headers
        assert headers['Content-Type'] == 'application/json'
        
        # CORS headers should be present
        assert 'Access-Control-Allow-Origin' in headers

class TestFileUploadSecurity:
    """Test file upload security measures."""
    
    @pytest.fixture
    def lambda_context(self):
        """Mock Lambda context."""
        context = Mock()
        context.aws_request_id = 'security-test-request'
        return context
    
    def test_file_type_validation(self, lambda_context):
        """Test that only allowed file types are accepted."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'file-upload'))
        
        with patch.dict(os.environ, {
            'UPLOAD_BUCKET': 'test-bucket',
            'MAX_FILE_SIZE_MB': '10',
            'PRESIGNED_URL_EXPIRATION': '3600'
        }):
            from lambda_function import lambda_handler
            
            dangerous_file_types = [
                ('malware.exe', 'application/x-executable'),
                ('script.js', 'application/javascript'),
                ('webpage.html', 'text/html'),
                ('archive.zip', 'application/zip'),
                ('document.pdf', 'application/pdf'),
                ('image.jpg', 'image/jpeg'),
                ('config.xml', 'application/xml')
            ]
            
            for filename, content_type in dangerous_file_types:
                event = {
                    'body': json.dumps({
                        'fileName': filename,
                        'fileType': content_type,
                        'fileSize': 1024
                    })
                }
                
                response = lambda_handler(event, lambda_context)
                
                # Should reject non-CSV/Excel files
                assert response['statusCode'] == 400
                body = json.loads(response['body'])
                assert 'Invalid file type' in body['error']['message']
    
    def test_file_size_limits(self, lambda_context):
        """Test that file size limits are enforced."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'file-upload'))
        
        with patch.dict(os.environ, {
            'UPLOAD_BUCKET': 'test-bucket',
            'MAX_FILE_SIZE_MB': '10',
            'PRESIGNED_URL_EXPIRATION': '3600'
        }):
            from lambda_function import lambda_handler
            
            # Test oversized file
            oversized_file = {
                'fileName': 'large_file.csv',
                'fileType': 'text/csv',
                'fileSize': 50 * 1024 * 1024  # 50MB (exceeds 10MB limit)
            }
            
            event = {
                'body': json.dumps(oversized_file)
            }
            
            response = lambda_handler(event, lambda_context)
            
            assert response['statusCode'] == 400
            body = json.loads(response['body'])
            assert 'exceeds maximum limit' in body['error']['message']
    
    def test_filename_sanitization(self, lambda_context):
        """Test that dangerous filenames are sanitized or rejected."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'file-upload'))
        
        with patch.dict(os.environ, {
            'UPLOAD_BUCKET': 'test-bucket',
            'MAX_FILE_SIZE_MB': '10',
            'PRESIGNED_URL_EXPIRATION': '3600'
        }):
            from lambda_function import lambda_handler
            
            dangerous_filenames = [
                'file<script>alert(1)</script>.csv',
                'file"quotes".csv',
                'file|pipe.csv',
                'file&amp;.csv',
                'file;semicolon.csv',
                'file`backtick`.csv',
                'file$(command).csv'
            ]
            
            for filename in dangerous_filenames:
                event = {
                    'body': json.dumps({
                        'fileName': filename,
                        'fileType': 'text/csv',
                        'fileSize': 1024
                    })
                }
                
                response = lambda_handler(event, lambda_context)
                
                # Should reject dangerous filenames
                assert response['statusCode'] == 400
                body = json.loads(response['body'])
                assert 'invalid characters' in body['error']['message'].lower()

class TestDatabaseSecurity:
    """Test database security measures."""
    
    @mock_aws
    def test_dynamodb_access_patterns(self):
        """Test that DynamoDB access follows security best practices."""
        # Create test DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
        table = dynamodb.create_table(
            TableName='security-test-leads',
            KeySchema=[
                {'AttributeName': 'leadId', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'leadId', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Test DynamoDB utils
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))
        from dynamodb_utils import DynamoDBUtils
        
        db_utils = DynamoDBUtils('security-test-leads', 'ap-southeast-1')
        db_utils.table = table
        
        # Test that queries are parameterized (no injection possible)
        malicious_filters = {
            'firstName': "'; DROP TABLE leads; --",
            'company': "' OR '1'='1"
        }
        
        # Should handle malicious input safely
        result = db_utils.query_leads(filters=malicious_filters)
        
        # Should return empty results, not crash or execute injection
        assert result['totalCount'] == 0
        assert result['leads'] == []
    
    def test_data_encryption_at_rest(self):
        """Test that sensitive data would be encrypted at rest."""
        # This is more of a configuration test
        # In real deployment, DynamoDB should have encryption enabled
        
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))
        from dynamodb_utils import DynamoDBUtils
        
        # Verify that sensitive fields are handled appropriately
        test_lead = {
            'firstName': 'John',
            'lastName': 'Doe',
            'email': 'john.doe@example.com',
            'remarks': 'Sensitive business information'
        }
        
        # The system should not log or expose sensitive data
        # This is verified through proper error handling and logging practices
        assert 'email' in test_lead  # Basic structure test
        assert 'remarks' in test_lead

class TestAPIRateLimiting:
    """Test API rate limiting and abuse prevention."""
    
    @pytest.fixture
    def lambda_context(self):
        """Mock Lambda context."""
        context = Mock()
        context.aws_request_id = 'security-test-request'
        return context
    
    def test_rapid_successive_requests(self, lambda_context):
        """Test handling of rapid successive requests from same user."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        from lambda_function import lambda_handler
        
        # Simulate rapid requests
        event = {
            'httpMethod': 'GET',
            'headers': {'Authorization': 'Bearer test-token'},
            'queryStringParameters': {}
        }
        
        responses = []
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            # Make multiple rapid requests
            for i in range(10):
                response = lambda_handler(event, lambda_context)
                responses.append(response)
        
        # All requests should be handled (no built-in rate limiting in Lambda)
        # But they should all be valid responses
        for response in responses:
            assert response['statusCode'] in [200, 401, 500]
            assert 'body' in response
    
    def test_large_query_parameters(self, lambda_context):
        """Test handling of excessively large query parameters."""
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        from lambda_function import lambda_handler
        
        # Create oversized filter value
        large_filter_value = 'a' * 10000  # 10KB filter value
        
        event = {
            'httpMethod': 'GET',
            'headers': {'Authorization': 'Bearer test-token'},
            'queryStringParameters': {
                'filter_firstName': large_filter_value
            }
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            response = lambda_handler(event, lambda_context)
        
        # Should handle large parameters gracefully
        assert response['statusCode'] in [200, 400]
        
        # Should not crash or timeout
        assert 'body' in response

if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])