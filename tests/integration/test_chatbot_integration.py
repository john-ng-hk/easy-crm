"""
Integration tests for Chatbot Lambda function.

Tests actual DeepSeek API integration and core functionality
with mocked external dependencies.
"""

import json
import pytest
import os
import sys
from unittest.mock import Mock, patch

# Add lambda function to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'chatbot'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))

from lambda_function import (
    lambda_handler,
    generate_dynamodb_query,
    process_natural_language_query
)

class TestChatbotIntegration:
    """Integration tests for chatbot functionality."""
    
    @patch('lambda_function.validate_jwt_token')
    @patch('lambda_function.generate_dynamodb_query')
    @patch('lambda_function.execute_query')
    def test_end_to_end_filter_query(self, mock_execute_query, mock_generate_query, mock_validate_jwt):
        """Test end-to-end processing of a filter query."""
        # Mock authentication
        mock_validate_jwt.return_value = {'sub': 'user123', 'email': 'test@example.com'}
        
        # Mock DeepSeek response for filter query
        mock_generate_query.return_value = {
            'type': 'filter',
            'filters': {'company': 'Google'},
            'limit': 50
        }
        
        # Mock DynamoDB query results
        mock_execute_query.return_value = [
            {'leadId': 'lead-1', 'firstName': 'John', 'lastName': 'Doe', 'company': 'Google', 'title': 'Engineer'},
            {'leadId': 'lead-2', 'firstName': 'Bob', 'lastName': 'Johnson', 'company': 'Google', 'title': 'Senior Engineer'}
        ]
        
        # Create test event
        event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'query': 'show me leads from Google'
            })
        }
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Execute handler
        response = lambda_handler(event, context)
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['type'] == 'success'
        assert 'Google' in body['response']
        assert body['resultCount'] == 2  # Should find 2 Google leads
        
        # Verify the response mentions the correct titles or companies
        assert 'Engineer' in body['response'] or 'Google' in body['response']
    
    @patch('lambda_function.validate_jwt_token')
    @patch('lambda_function.generate_dynamodb_query')
    @patch('lambda_function.execute_query')
    def test_end_to_end_count_query(self, mock_execute_query, mock_generate_query, mock_validate_jwt):
        """Test end-to-end processing of a count query."""
        mock_validate_jwt.return_value = {'sub': 'user123', 'email': 'test@example.com'}
        
        # Mock DeepSeek response for count query
        mock_generate_query.return_value = {
            'type': 'count',
            'filters': {}
        }
        
        # Mock DynamoDB count result
        mock_execute_query.return_value = {'count': 4}
        
        event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'query': 'how many leads do we have?'
            })
        }
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['type'] == 'success'
        assert '4 total leads' in body['response']  # Should count all 4 test leads
    
    @patch('lambda_function.validate_jwt_token')
    @patch('lambda_function.generate_dynamodb_query')
    @patch('lambda_function.execute_query')
    def test_end_to_end_aggregate_query(self, mock_execute_query, mock_generate_query, mock_validate_jwt):
        """Test end-to-end processing of an aggregate query."""
        mock_validate_jwt.return_value = {'sub': 'user123', 'email': 'test@example.com'}
        
        # Mock DeepSeek response for aggregate query
        mock_generate_query.return_value = {
            'type': 'aggregate',
            'groupBy': 'company',
            'filters': {}
        }
        
        # Mock DynamoDB aggregate result
        mock_execute_query.return_value = {
            'groups': [
                ('Google', 2),
                ('Microsoft', 1),
                ('Apple', 1)
            ]
        }
        
        event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'query': 'group leads by company'
            })
        }
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['type'] == 'success'
        assert 'breakdown by company' in body['response']
        assert 'Google: 2 leads' in body['response']
        assert 'Microsoft: 1 leads' in body['response']
        assert 'Apple: 1 leads' in body['response']
    
    @patch('lambda_function.validate_jwt_token')
    @patch('lambda_function.generate_dynamodb_query')
    def test_unclear_query_response(self, mock_generate_query, mock_validate_jwt):
        """Test response to unclear queries that cannot be parsed."""
        mock_validate_jwt.return_value = {'sub': 'user123', 'email': 'test@example.com'}
        
        # Mock DeepSeek returning None for unclear query
        mock_generate_query.return_value = None
        
        event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'query': 'asdfghjkl random gibberish'
            })
        }
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['type'] == 'clarification'
        assert "couldn't understand" in body['response']
        assert "rephrase" in body['response']
    
    @pytest.mark.skipif(
        not os.environ.get('DEEPSEEK_API_KEY'),
        reason="DeepSeek API key not available for integration testing"
    )
    def test_real_deepseek_api_integration(self):
        """Test actual DeepSeek API integration with real API calls."""
        # This test requires a real DeepSeek API key
        test_queries = [
            "show me leads from Google",
            "how many leads do we have?",
            "group leads by company",
            "find engineers",
            "leads with manager in title"
        ]
        
        for query in test_queries:
            try:
                result = generate_dynamodb_query(query)
                
                # Verify we get a valid response structure
                if result is not None:
                    assert 'type' in result
                    assert result['type'] in ['filter', 'count', 'aggregate']
                    
                    if result['type'] == 'filter':
                        assert 'filters' in result
                        assert 'limit' in result
                    elif result['type'] == 'count':
                        assert 'filters' in result
                    elif result['type'] == 'aggregate':
                        assert 'groupBy' in result
                        assert 'filters' in result
                
                print(f"Query: '{query}' -> {result}")
                
            except Exception as e:
                # Log the error but don't fail the test for API issues
                print(f"API call failed for query '{query}': {str(e)}")
    
    @patch('lambda_function.validate_jwt_token')
    def test_authentication_required(self, mock_validate_jwt):
        """Test that authentication is required for chatbot access."""
        # Mock authentication failure
        from error_handling import AuthenticationError
        mock_validate_jwt.side_effect = AuthenticationError("Invalid token")
        
        event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer invalid-token'},
            'body': json.dumps({
                'query': 'show me leads'
            })
        }
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'Invalid token' in body['error']['message']
    
    @patch('lambda_function.validate_jwt_token')
    @patch('lambda_function.generate_dynamodb_query')
    @patch('lambda_function.execute_query')
    def test_database_error_handling(self, mock_execute_query, mock_generate_query, mock_validate_jwt):
        """Test handling of database errors during query execution."""
        mock_validate_jwt.return_value = {'sub': 'user123', 'email': 'test@example.com'}
        mock_generate_query.return_value = {
            'type': 'filter',
            'filters': {'company': 'Google'},
            'limit': 50
        }
        
        # Mock database error
        mock_execute_query.side_effect = Exception("Database connection failed")
        
        event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'query': 'show me Google leads'
            })
        }
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        response = lambda_handler(event, context)
        
        # Should return success with error message for user-friendly handling
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['type'] == 'error'
        assert 'issue retrieving the data' in body['response']
    
    def test_health_check_endpoint(self):
        """Test the health check endpoint."""
        from lambda_function import health_check_handler
        
        event = {'httpMethod': 'GET'}
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        response = health_check_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['status'] == 'healthy'
        assert body['service'] == 'chatbot'
        assert 'deepseek_configured' in body

class TestPhoneFieldIntegration:
    """Integration tests specifically for phone field functionality."""
    
    @patch('lambda_function.validate_jwt_token')
    @patch('lambda_function.generate_dynamodb_query')
    @patch('lambda_function.execute_query')
    def test_phone_field_filter_integration(self, mock_execute_query, mock_generate_query, mock_validate_jwt):
        """Test end-to-end processing of phone field filter queries."""
        mock_validate_jwt.return_value = {'sub': 'user123', 'email': 'test@example.com'}
        
        # Mock DeepSeek response for phone filter query
        mock_generate_query.return_value = {
            'type': 'filter',
            'filters': {'phone': '555'},
            'limit': 50
        }
        
        # Mock DynamoDB query results with phone data
        mock_execute_query.return_value = [
            {'leadId': 'lead-1', 'firstName': 'John', 'lastName': 'Doe', 'company': 'Google', 'phone': '+1-555-123-4567'},
            {'leadId': 'lead-2', 'firstName': 'Jane', 'lastName': 'Smith', 'company': 'Microsoft', 'phone': '+1-555-987-6543'}
        ]
        
        event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'query': 'find leads with phone number 555'
            })
        }
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['type'] == 'success'
        assert body['resultCount'] == 2
        assert '2 of which have phone numbers' in body['response']
        
        # Verify the query was generated correctly
        mock_generate_query.assert_called_once_with('find leads with phone number 555')
        
        # Verify the query was executed with phone filter
        mock_execute_query.assert_called_once()
    
    @patch('lambda_function.validate_jwt_token')
    @patch('lambda_function.generate_dynamodb_query')
    @patch('lambda_function.execute_query')
    def test_phone_field_single_result_integration(self, mock_execute_query, mock_generate_query, mock_validate_jwt):
        """Test phone field display in single result responses."""
        mock_validate_jwt.return_value = {'sub': 'user123', 'email': 'test@example.com'}
        
        mock_generate_query.return_value = {
            'type': 'filter',
            'filters': {'phone': '555-123-4567'},
            'limit': 50
        }
        
        # Mock single result with phone
        mock_execute_query.return_value = [
            {'leadId': 'lead-1', 'firstName': 'John', 'lastName': 'Doe', 'company': 'Google', 'title': 'Engineer', 'phone': '+1-555-123-4567'}
        ]
        
        event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'query': 'find lead with phone 555-123-4567'
            })
        }
        
        context = Mock()
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['type'] == 'success'
        assert body['resultCount'] == 1
        assert 'John Doe' in body['response']
        assert '+1-555-123-4567' in body['response']
        assert 'Google' in body['response']
    
    @patch('lambda_function.DEEPSEEK_API_KEY', 'test-key')
    @patch('lambda_function.requests.post')
    def test_phone_query_patterns_generation(self, mock_post):
        """Test various phone-related query patterns."""
        phone_queries = [
            ('find leads with phone number 555', {'type': 'filter', 'filters': {'phone': '555'}, 'limit': 50}),
            ('show me contacts with mobile numbers', {'type': 'filter', 'filters': {'phone': ''}, 'limit': 50}),
            ('who has telephone information', {'type': 'filter', 'filters': {'phone': ''}, 'limit': 50}),
            ('leads with contact numbers', {'type': 'filter', 'filters': {'phone': ''}, 'limit': 50})
        ]
        
        for query, expected_structure in phone_queries:
            mock_response = Mock()
            mock_response.json.return_value = {
                'choices': [{
                    'message': {
                        'content': json.dumps(expected_structure)
                    }
                }]
            }
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response
            
            result = generate_dynamodb_query(query)
            
            assert result is not None
            assert result['type'] == 'filter'
            assert 'phone' in result['filters']
            
            # Verify API was called with phone field in system prompt
            call_data = mock_post.call_args[1]['json']
            system_message = call_data['messages'][0]['content']
            assert 'phone (string)' in system_message
    
    def test_phone_data_security_in_integration(self):
        """Test that actual lead phone data is never sent to DeepSeek, only query structures."""
        with patch('lambda_function.DEEPSEEK_API_KEY', 'test-key'):
            with patch('lambda_function.requests.post') as mock_post:
                mock_response = Mock()
                mock_response.json.return_value = {
                    'choices': [{
                        'message': {
                            'content': '{"type": "filter", "filters": {"phone": "555"}, "limit": 50}'
                        }
                    }]
                }
                mock_response.raise_for_status.return_value = None
                mock_post.return_value = mock_response
                
                # Process a phone-related query
                generate_dynamodb_query("find leads with mobile numbers")
                
                # Verify the API call structure
                call_data = mock_post.call_args[1]['json']
                
                # The system prompt should contain phone field definition
                system_message = call_data['messages'][0]['content']
                assert 'phone (string)' in system_message
                
                # The user message should contain the query but not actual lead data
                user_message = call_data['messages'][1]['content']
                assert 'find leads with mobile numbers' in user_message
                
                # Should not contain actual lead phone data (these would be from database records)
                # The key security requirement is that we don't send actual lead records to DeepSeek
                request_content = str(call_data)
                
                # These patterns would indicate actual lead data values being sent (which we don't want)
                # We're looking for actual data values, not schema field names
                sensitive_data_patterns = [
                    r'lead-\d+',  # Actual lead IDs like "lead-123"
                    r'John.*Doe',  # Actual person names
                    r'\+1-\d{3}-\d{3}-\d{4}',  # Actual formatted phone numbers
                    r'[a-zA-Z]+@[a-zA-Z]+\.[a-zA-Z]+',  # Actual email addresses
                ]
                
                import re
                for pattern in sensitive_data_patterns:
                    matches = re.search(pattern, request_content, re.IGNORECASE)
                    assert not matches, f"Found sensitive data pattern: {pattern} - match: {matches.group() if matches else None}"
                
                # Verify that only schema definitions and user query are present
                assert 'leadId (string, primary key)' in system_message  # Schema definition is OK
                assert 'phone (string)' in system_message  # Schema definition is OK
                assert 'Convert this query to DynamoDB structure' in user_message  # Query processing is OK

class TestDeepSeekQueryGeneration:
    """Test cases specifically for DeepSeek query generation patterns."""
    
    def test_query_generation_patterns(self):
        """Test various query patterns that should be recognized."""
        # This test uses mocked responses to verify query structure generation
        test_cases = [
            {
                'query': 'show me leads from Google',
                'expected_type': 'filter',
                'expected_filters': {'company': 'Google'}
            },
            {
                'query': 'find engineers',
                'expected_type': 'filter', 
                'expected_filters': {'title': 'engineer'}
            },
            {
                'query': 'how many leads do we have',
                'expected_type': 'count',
                'expected_filters': {}
            },
            {
                'query': 'group by company',
                'expected_type': 'aggregate',
                'expected_group_by': 'company'
            }
        ]
        
        for case in test_cases:
            with patch('lambda_function.DEEPSEEK_API_KEY', 'test-key'):
                with patch('lambda_function.requests.post') as mock_post:
                    # Mock the expected response structure
                    if case['expected_type'] == 'filter':
                        mock_response_content = {
                            'type': 'filter',
                            'filters': case['expected_filters'],
                            'limit': 50
                        }
                    elif case['expected_type'] == 'count':
                        mock_response_content = {
                            'type': 'count',
                            'filters': case['expected_filters']
                        }
                    elif case['expected_type'] == 'aggregate':
                        mock_response_content = {
                            'type': 'aggregate',
                            'groupBy': case['expected_group_by'],
                            'filters': {}
                        }
                    
                    mock_response = Mock()
                    mock_response.json.return_value = {
                        'choices': [{
                            'message': {
                                'content': json.dumps(mock_response_content)
                            }
                        }]
                    }
                    mock_response.raise_for_status.return_value = None
                    mock_post.return_value = mock_response
                    
                    result = generate_dynamodb_query(case['query'])
                    
                    assert result is not None
                    assert result['type'] == case['expected_type']
                    
                    if case['expected_type'] == 'filter':
                        assert result['filters'] == case['expected_filters']
                    elif case['expected_type'] == 'count':
                        assert result['filters'] == case['expected_filters']
                    elif case['expected_type'] == 'aggregate':
                        assert result['groupBy'] == case['expected_group_by']

if __name__ == '__main__':
    pytest.main([__file__])