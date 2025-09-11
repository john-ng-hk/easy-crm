"""
Unit tests for Chatbot Lambda function.

Tests natural language query processing, DeepSeek integration,
DynamoDB query generation, and response formatting.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add lambda function to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'chatbot'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))

from lambda_function import (
    lambda_handler,
    process_natural_language_query,
    generate_dynamodb_query,
    validate_query_structure,
    execute_query,
    format_query_results
)

class TestChatbotLambdaHandler:
    """Test cases for the main Lambda handler."""
    
    @patch('lambda_function.validate_jwt_token')
    @patch('lambda_function.process_natural_language_query')
    def test_successful_query_processing(self, mock_process_query, mock_validate_jwt):
        """Test successful natural language query processing."""
        # Setup mocks
        mock_validate_jwt.return_value = {'sub': 'user123', 'email': 'test@example.com'}
        mock_process_query.return_value = {
            'response': 'I found 5 leads from tech companies.',
            'type': 'success',
            'query': 'show me leads from tech companies',
            'resultCount': 5
        }
        
        # Create test event
        event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({
                'query': 'show me leads from tech companies'
            })
        }
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        # Execute handler
        response = lambda_handler(event, context)
        
        # Verify response
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['response'] == 'I found 5 leads from tech companies.'
        assert body['type'] == 'success'
        assert body['resultCount'] == 5
        
        # Verify mocks were called
        mock_validate_jwt.assert_called_once_with(event)
        mock_process_query.assert_called_once_with('show me leads from tech companies', 'user123')
    
    @patch('lambda_function.validate_jwt_token')
    def test_missing_query_validation(self, mock_validate_jwt):
        """Test validation error for missing query."""
        mock_validate_jwt.return_value = {'sub': 'user123'}
        
        event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({})
        }
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Query is required' in body['error']['message']
    
    @patch('lambda_function.validate_jwt_token')
    def test_query_too_long_validation(self, mock_validate_jwt):
        """Test validation error for query that's too long."""
        mock_validate_jwt.return_value = {'sub': 'user123'}
        
        long_query = 'a' * 501  # Exceeds 500 character limit
        
        event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': json.dumps({'query': long_query})
        }
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Query too long' in body['error']['message']
    
    def test_cors_preflight_request(self):
        """Test CORS preflight OPTIONS request handling."""
        event = {'httpMethod': 'OPTIONS'}
        context = Mock()
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in response['headers']
    
    @patch('lambda_function.validate_jwt_token')
    def test_invalid_json_body(self, mock_validate_jwt):
        """Test handling of invalid JSON in request body."""
        mock_validate_jwt.return_value = {'sub': 'user123'}
        
        event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer valid-token'},
            'body': 'invalid json'
        }
        
        context = Mock()
        context.aws_request_id = 'test-request-id'
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Invalid JSON' in body['error']['message']

class TestQueryGeneration:
    """Test cases for DeepSeek query generation."""
    
    @patch('lambda_function.DEEPSEEK_API_KEY', 'test-api-key')
    @patch('lambda_function.requests.post')
    def test_successful_query_generation(self, mock_post):
        """Test successful query generation from natural language."""
        # Mock DeepSeek API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': '{"type": "filter", "filters": {"company": "Google"}, "limit": 50}'
                }
            }]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        # Test query generation
        result = generate_dynamodb_query("show me leads from Google")
        
        # Verify result
        assert result is not None
        assert result['type'] == 'filter'
        assert result['filters']['company'] == 'Google'
        assert result['limit'] == 50
        
        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == 'https://api.deepseek.com/v1/chat/completions'
        assert 'Authorization' in call_args[1]['headers']
        assert call_args[1]['headers']['Authorization'] == 'Bearer test-api-key'
    
    @patch('lambda_function.DEEPSEEK_API_KEY', 'test-api-key')
    @patch('lambda_function.requests.post')
    def test_phone_query_generation(self, mock_post):
        """Test successful phone field query generation from natural language."""
        # Mock DeepSeek API response for phone query
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
        
        # Test phone query generation
        result = generate_dynamodb_query("find leads with phone number 555")
        
        # Verify result
        assert result is not None
        assert result['type'] == 'filter'
        assert result['filters']['phone'] == '555'
        assert result['limit'] == 50
    
    @patch('lambda_function.DEEPSEEK_API_KEY', 'test-api-key')
    @patch('lambda_function.requests.post')
    def test_invalid_json_response_handling(self, mock_post):
        """Test handling of invalid JSON response from DeepSeek."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'This is not valid JSON'
                }
            }]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = generate_dynamodb_query("unclear query")
        
        assert result is None
    
    @patch('lambda_function.DEEPSEEK_API_KEY', None)
    def test_missing_api_key(self):
        """Test error handling when API key is not configured."""
        with pytest.raises(Exception) as exc_info:
            generate_dynamodb_query("test query")
        
        assert "DeepSeek API key not configured" in str(exc_info.value)
    
    @patch('lambda_function.DEEPSEEK_API_KEY', 'test-api-key')
    @patch('lambda_function.requests.post')
    def test_api_request_failure(self, mock_post):
        """Test handling of API request failures."""
        mock_post.side_effect = Exception("Network error")
        
        with pytest.raises(Exception) as exc_info:
            generate_dynamodb_query("test query")
        
        assert "DeepSeek API error" in str(exc_info.value)

class TestQueryStructureValidation:
    """Test cases for query structure validation."""
    
    def test_valid_filter_query(self):
        """Test validation of valid filter query structure."""
        query = {
            'type': 'filter',
            'filters': {'company': 'Google', 'title': 'Engineer'},
            'limit': 25
        }
        
        assert validate_query_structure(query) is True
    
    def test_valid_count_query(self):
        """Test validation of valid count query structure."""
        query = {
            'type': 'count',
            'filters': {'company': 'Microsoft'}
        }
        
        assert validate_query_structure(query) is True
    
    def test_valid_aggregate_query(self):
        """Test validation of valid aggregate query structure."""
        query = {
            'type': 'aggregate',
            'groupBy': 'company',
            'filters': {}
        }
        
        assert validate_query_structure(query) is True
    
    def test_invalid_query_type(self):
        """Test rejection of invalid query type."""
        query = {
            'type': 'invalid_type',
            'filters': {}
        }
        
        assert validate_query_structure(query) is False
    
    def test_invalid_filter_field(self):
        """Test rejection of invalid filter field."""
        query = {
            'type': 'filter',
            'filters': {'invalid_field': 'value'},
            'limit': 50
        }
        
        assert validate_query_structure(query) is False
    
    def test_valid_phone_filter_query(self):
        """Test validation of valid phone filter query structure."""
        query = {
            'type': 'filter',
            'filters': {'phone': '555'},
            'limit': 50
        }
        
        assert validate_query_structure(query) is True
    
    def test_invalid_aggregate_group_by(self):
        """Test rejection of invalid groupBy field in aggregate query."""
        query = {
            'type': 'aggregate',
            'groupBy': 'invalid_field',
            'filters': {}
        }
        
        assert validate_query_structure(query) is False
    
    def test_limit_adjustment(self):
        """Test automatic limit adjustment for out-of-range values."""
        query = {
            'type': 'filter',
            'filters': {'company': 'Google'},
            'limit': 200  # Exceeds maximum
        }
        
        result = validate_query_structure(query)
        assert result is True
        assert query['limit'] == 50  # Should be adjusted to default

class TestQueryExecution:
    """Test cases for DynamoDB query execution."""
    
    @patch('lambda_function.dynamodb_utils')
    def test_filter_query_execution(self, mock_dynamodb):
        """Test execution of filter query."""
        # Mock DynamoDB response
        mock_dynamodb.query_leads.return_value = {
            'leads': [
                {'leadId': '1', 'firstName': 'John', 'lastName': 'Doe', 'company': 'Google'},
                {'leadId': '2', 'firstName': 'Jane', 'lastName': 'Smith', 'company': 'Google'}
            ]
        }
        
        query_structure = {
            'type': 'filter',
            'filters': {'company': 'Google'},
            'limit': 50
        }
        
        result = execute_query(query_structure)
        
        assert len(result) == 2
        assert result[0]['company'] == 'Google'
        assert result[1]['company'] == 'Google'
        
        # Verify DynamoDB was called correctly
        mock_dynamodb.query_leads.assert_called_once_with(
            filters={'company': 'Google'},
            sort_by='createdAt',
            sort_order='desc',
            page_size=50
        )
    
    @patch('lambda_function.dynamodb_utils')
    def test_count_query_execution(self, mock_dynamodb):
        """Test execution of count query."""
        mock_dynamodb.query_leads.return_value = {
            'totalCount': 25
        }
        
        query_structure = {
            'type': 'count',
            'filters': {'company': 'Microsoft'}
        }
        
        result = execute_query(query_structure)
        
        assert result['count'] == 25
    
    @patch('lambda_function.dynamodb_utils')
    def test_aggregate_query_execution(self, mock_dynamodb):
        """Test execution of aggregate query."""
        mock_dynamodb.get_all_leads_for_export.return_value = [
            {'company': 'Google', 'firstName': 'John'},
            {'company': 'Google', 'firstName': 'Jane'},
            {'company': 'Microsoft', 'firstName': 'Bob'},
            {'company': 'Apple', 'firstName': 'Alice'}
        ]
        
        query_structure = {
            'type': 'aggregate',
            'groupBy': 'company',
            'filters': {}
        }
        
        result = execute_query(query_structure)
        
        assert 'groups' in result
        groups = dict(result['groups'])
        assert groups['Google'] == 2
        assert groups['Microsoft'] == 1
        assert groups['Apple'] == 1

class TestResponseFormatting:
    """Test cases for response formatting."""
    
    def test_format_single_lead_result(self):
        """Test formatting of single lead result."""
        query_structure = {'type': 'filter', 'filters': {'company': 'Google'}}
        results = [
            {'firstName': 'John', 'lastName': 'Doe', 'company': 'Google', 'title': 'Engineer'}
        ]
        
        response = format_query_results("show me leads from Google", query_structure, results)
        
        assert "I found 1 lead" in response
        assert "John Doe" in response
        assert "Google" in response
        assert "Engineer" in response
    
    def test_format_single_lead_result_with_phone(self):
        """Test formatting of single lead result with phone number."""
        query_structure = {'type': 'filter', 'filters': {'phone': '555'}}
        results = [
            {'firstName': 'John', 'lastName': 'Doe', 'company': 'Google', 'title': 'Engineer', 'phone': '+1-555-123-4567'}
        ]
        
        response = format_query_results("find leads with phone 555", query_structure, results)
        
        assert "I found 1 lead" in response
        assert "John Doe" in response
        assert "Google" in response
        assert "Engineer" in response
        assert "+1-555-123-4567" in response
    
    def test_format_multiple_leads_result(self):
        """Test formatting of multiple leads result."""
        query_structure = {'type': 'filter', 'filters': {'title': 'Engineer'}}
        results = [
            {'firstName': 'John', 'lastName': 'Doe', 'company': 'Google', 'title': 'Engineer'},
            {'firstName': 'Jane', 'lastName': 'Smith', 'company': 'Microsoft', 'title': 'Engineer'},
            {'firstName': 'Bob', 'lastName': 'Johnson', 'company': 'Apple', 'title': 'Engineer'}
        ]
        
        response = format_query_results("show me engineers", query_structure, results)
        
        assert "I found 3 leads" in response
        assert any(company in response for company in ['Google', 'Microsoft', 'Apple'])
    
    def test_format_multiple_leads_with_phone_filter(self):
        """Test formatting of multiple leads result with phone filter."""
        query_structure = {'type': 'filter', 'filters': {'phone': '555'}}
        results = [
            {'firstName': 'John', 'lastName': 'Doe', 'company': 'Google', 'title': 'Engineer', 'phone': '+1-555-123-4567'},
            {'firstName': 'Jane', 'lastName': 'Smith', 'company': 'Microsoft', 'title': 'Manager', 'phone': '+1-555-987-6543'},
            {'firstName': 'Bob', 'lastName': 'Johnson', 'company': 'Apple', 'title': 'Developer', 'phone': 'N/A'}
        ]
        
        response = format_query_results("find leads with phone 555", query_structure, results)
        
        assert "I found 3 leads" in response
        assert "2 of which have phone numbers" in response
        assert any(company in response for company in ['Google', 'Microsoft', 'Apple'])
    
    def test_format_count_result(self):
        """Test formatting of count query result."""
        query_structure = {'type': 'count', 'filters': {'company': 'Google'}}
        results = {'count': 15}
        
        response = format_query_results("how many leads from Google", query_structure, results)
        
        assert "15 leads" in response
        assert "company containing 'Google'" in response
    
    def test_format_aggregate_result(self):
        """Test formatting of aggregate query result."""
        query_structure = {'type': 'aggregate', 'groupBy': 'company', 'filters': {}}
        results = {
            'groups': [
                ('Google', 10),
                ('Microsoft', 8),
                ('Apple', 5)
            ]
        }
        
        response = format_query_results("group leads by company", query_structure, results)
        
        assert "breakdown by company" in response
        assert "Google: 10 leads" in response
        assert "Microsoft: 8 leads" in response
        assert "Apple: 5 leads" in response
    
    def test_format_empty_result(self):
        """Test formatting of empty result."""
        query_structure = {'type': 'filter', 'filters': {'company': 'NonExistent'}}
        results = []
        
        response = format_query_results("show me leads from NonExistent", query_structure, results)
        
        assert "didn't find any leads" in response

class TestPhoneFieldQueries:
    """Test cases specifically for phone field query handling."""
    
    @patch('lambda_function.DEEPSEEK_API_KEY', 'test-api-key')
    @patch('lambda_function.requests.post')
    def test_phone_number_query_parsing(self, mock_post):
        """Test parsing of phone number related queries."""
        test_cases = [
            ("find leads with phone number 555", {"type": "filter", "filters": {"phone": "555"}, "limit": 50}),
            ("show me contacts with mobile numbers", {"type": "filter", "filters": {"phone": ""}, "limit": 50}),
            ("who has telephone information", {"type": "filter", "filters": {"phone": ""}, "limit": 50}),
        ]
        
        for query, expected_structure in test_cases:
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
            assert result['type'] == expected_structure['type']
            assert 'phone' in result['filters']
    
    @patch('lambda_function.dynamodb_utils')
    def test_phone_filter_execution(self, mock_dynamodb):
        """Test execution of phone field filter queries."""
        # Mock DynamoDB response with phone data
        mock_dynamodb.query_leads.return_value = {
            'leads': [
                {'leadId': '1', 'firstName': 'John', 'lastName': 'Doe', 'phone': '+1-555-123-4567'},
                {'leadId': '2', 'firstName': 'Jane', 'lastName': 'Smith', 'phone': '+1-555-987-6543'}
            ]
        }
        
        query_structure = {
            'type': 'filter',
            'filters': {'phone': '555'},
            'limit': 50
        }
        
        result = execute_query(query_structure)
        
        assert len(result) == 2
        assert all('phone' in lead for lead in result)
        assert all('555' in lead['phone'] for lead in result)
        
        # Verify DynamoDB was called with phone filter
        mock_dynamodb.query_leads.assert_called_once_with(
            filters={'phone': '555'},
            sort_by='createdAt',
            sort_order='desc',
            page_size=50
        )
    
    def test_phone_field_in_response_formatting(self):
        """Test that phone field is properly included in response formatting."""
        query_structure = {'type': 'filter', 'filters': {'phone': '555'}}
        results = [
            {'firstName': 'John', 'lastName': 'Doe', 'company': 'Google', 'phone': '+1-555-123-4567'},
            {'firstName': 'Jane', 'lastName': 'Smith', 'company': 'Microsoft', 'phone': 'N/A'},
            {'firstName': 'Bob', 'lastName': 'Johnson', 'company': 'Apple', 'phone': '+1-555-999-8888'}
        ]
        
        response = format_query_results("find leads with phone 555", query_structure, results)
        
        # Should mention phone numbers in the response
        assert "2 of which have phone numbers" in response
        assert "I found 3 leads" in response
    
    def test_phone_data_not_sent_to_deepseek(self):
        """Test that actual phone data is never sent to DeepSeek API."""
        # This test ensures we only send query structures, not actual lead data
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
            
            # Set API key for the test
            with patch('lambda_function.DEEPSEEK_API_KEY', 'test-key'):
                generate_dynamodb_query("find leads with phone 555")
            
            # Verify the API call
            mock_post.assert_called_once()
            call_data = mock_post.call_args[1]['json']
            
            # Check that no actual phone numbers are in the request
            request_content = str(call_data)
            assert '+1-' not in request_content  # No actual phone numbers
            assert '555-' not in request_content  # No actual phone numbers
            assert 'phone' in request_content.lower()  # But phone field is mentioned in system prompt

class TestProcessNaturalLanguageQuery:
    """Test cases for the main query processing function."""
    
    @patch('lambda_function.generate_dynamodb_query')
    @patch('lambda_function.execute_query')
    @patch('lambda_function.format_query_results')
    def test_successful_query_processing(self, mock_format, mock_execute, mock_generate):
        """Test successful end-to-end query processing."""
        # Setup mocks
        mock_generate.return_value = {'type': 'filter', 'filters': {'company': 'Google'}}
        mock_execute.return_value = [{'firstName': 'John', 'company': 'Google'}]
        mock_format.return_value = "I found 1 lead from Google."
        
        result = process_natural_language_query("show me Google leads", "user123")
        
        assert result['type'] == 'success'
        assert result['response'] == "I found 1 lead from Google."
        assert result['resultCount'] == 1
        
        # Verify all functions were called
        mock_generate.assert_called_once_with("show me Google leads")
        mock_execute.assert_called_once()
        mock_format.assert_called_once()
    
    @patch('lambda_function.generate_dynamodb_query')
    def test_unclear_query_handling(self, mock_generate):
        """Test handling of unclear queries that cannot be parsed."""
        mock_generate.return_value = None
        
        result = process_natural_language_query("unclear gibberish", "user123")
        
        assert result['type'] == 'clarification'
        assert "couldn't understand" in result['response']
        assert "rephrase" in result['response']
    
    @patch('lambda_function.generate_dynamodb_query')
    @patch('lambda_function.execute_query')
    def test_database_error_handling(self, mock_execute, mock_generate):
        """Test handling of database errors during query execution."""
        mock_generate.return_value = {'type': 'filter', 'filters': {'company': 'Google'}}
        mock_execute.side_effect = Exception("Database connection failed")
        
        result = process_natural_language_query("show me Google leads", "user123")
        
        assert result['type'] == 'error'
        assert "issue retrieving the data" in result['response']

if __name__ == '__main__':
    pytest.main([__file__])