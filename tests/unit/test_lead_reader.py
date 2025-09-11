"""
Unit tests for Lead Reader Lambda function.

Tests filtering, sorting, pagination logic, and error handling
for the lead reader functionality.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add lambda function to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))

from lambda_function import (
    lambda_handler, 
    query_leads_with_pagination,
    format_leads_for_response,
    get_lead_by_id,
    get_single_lead_handler
)

class TestLeadReaderLambda:
    """Test cases for Lead Reader Lambda function."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sample_leads = [
            {
                'leadId': 'lead-1',
                'firstName': 'John',
                'lastName': 'Doe',
                'title': 'Software Engineer',
                'company': 'Tech Corp',
                'email': 'john.doe@techcorp.com',
                'phone': '+1-555-0123',
                'remarks': 'Interested in cloud solutions',
                'sourceFile': 'leads.csv',
                'createdAt': '2024-01-01T10:00:00Z',
                'updatedAt': '2024-01-01T10:00:00Z'
            },
            {
                'leadId': 'lead-2',
                'firstName': 'Jane',
                'lastName': 'Smith',
                'title': 'Product Manager',
                'company': 'Innovation Inc',
                'email': 'jane.smith@innovation.com',
                'phone': '+1-555-0456',
                'remarks': 'Looking for automation tools',
                'sourceFile': 'leads.csv',
                'createdAt': '2024-01-02T10:00:00Z',
                'updatedAt': '2024-01-02T10:00:00Z'
            }
        ]
        
        self.mock_context = Mock()
        self.mock_context.aws_request_id = 'test-request-id'
    
    def create_api_event(self, query_params=None, path_params=None, method='GET'):
        """Create a mock API Gateway event."""
        return {
            'httpMethod': method,
            'headers': {
                'Authorization': 'Bearer valid-jwt-token'
            },
            'queryStringParameters': query_params,
            'pathParameters': path_params
        }
    
    @patch('lambda_function.validate_jwt_token')
    @patch('lambda_function.query_leads_with_pagination')
    def test_lambda_handler_success(self, mock_query, mock_validate):
        """Test successful lead retrieval."""
        # Setup mocks
        mock_validate.return_value = {'sub': 'user123'}
        mock_query.return_value = {
            'leads': self.sample_leads,
            'pagination': {
                'page': 1,
                'pageSize': 50,
                'totalCount': 2,
                'totalPages': 1,
                'hasMore': False,
                'lastEvaluatedKey': None
            },
            'filters': {},
            'sorting': {
                'sortBy': 'createdAt',
                'sortOrder': 'desc'
            }
        }
        
        # Create event
        event = self.create_api_event()
        
        # Execute
        response = lambda_handler(event, self.mock_context)
        
        # Verify
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert len(body['leads']) == 2
        assert body['pagination']['totalCount'] == 2
        mock_validate.assert_called_once()
        mock_query.assert_called_once()
    
    @patch('lambda_function.validate_jwt_token')
    def test_lambda_handler_cors_preflight(self, mock_validate):
        """Test CORS preflight request handling."""
        event = self.create_api_event(method='OPTIONS')
        
        response = lambda_handler(event, self.mock_context)
        
        assert response['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in response['headers']
        mock_validate.assert_not_called()
    
    @patch('lambda_function.validate_jwt_token')
    def test_lambda_handler_with_filters(self, mock_validate):
        """Test lead retrieval with filters."""
        mock_validate.return_value = {'sub': 'user123'}
        
        query_params = {
            'filter_firstName': 'John',
            'filter_company': 'Tech',
            'page': '1',
            'pageSize': '25'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        with patch('lambda_function.query_leads_with_pagination') as mock_query:
            mock_query.return_value = {
                'leads': [self.sample_leads[0]],
                'pagination': {
                    'page': 1,
                    'pageSize': 25,
                    'totalCount': 1,
                    'totalPages': 1,
                    'hasMore': False,
                    'lastEvaluatedKey': None
                },
                'filters': {'firstName': 'John', 'company': 'Tech'},
                'sorting': {'sortBy': 'createdAt', 'sortOrder': 'desc'}
            }
            
            response = lambda_handler(event, self.mock_context)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['filters'] == {'firstName': 'John', 'company': 'Tech'}
            
            # Verify query was called with correct filters
            call_args = mock_query.call_args[1]
            assert call_args['filters'] == {'firstName': 'John', 'company': 'Tech'}
            assert call_args['page'] == 1
            assert call_args['page_size'] == 25
    
    @patch('lambda_function.validate_jwt_token')
    def test_lambda_handler_with_sorting(self, mock_validate):
        """Test lead retrieval with custom sorting."""
        mock_validate.return_value = {'sub': 'user123'}
        
        query_params = {
            'sortBy': 'lastName',
            'sortOrder': 'asc'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        with patch('lambda_function.query_leads_with_pagination') as mock_query:
            mock_query.return_value = {
                'leads': self.sample_leads,
                'pagination': {
                    'page': 1,
                    'pageSize': 50,
                    'totalCount': 2,
                    'totalPages': 1,
                    'hasMore': False,
                    'lastEvaluatedKey': None
                },
                'filters': {},
                'sorting': {'sortBy': 'lastName', 'sortOrder': 'asc'}
            }
            
            response = lambda_handler(event, self.mock_context)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['sorting']['sortBy'] == 'lastName'
            assert body['sorting']['sortOrder'] == 'asc'
            
            # Verify query was called with correct sorting
            call_args = mock_query.call_args[1]
            assert call_args['sort_by'] == 'lastName'
            assert call_args['sort_order'] == 'asc'
    
    @patch('lambda_function.validate_jwt_token')
    def test_lambda_handler_pagination_validation(self, mock_validate):
        """Test pagination parameter validation."""
        mock_validate.return_value = {'sub': 'user123'}
        
        # Test invalid page number
        event = self.create_api_event(query_params={'page': '0'})
        response = lambda_handler(event, self.mock_context)
        assert response['statusCode'] == 400
        
        # Test invalid page size
        event = self.create_api_event(query_params={'pageSize': '101'})
        response = lambda_handler(event, self.mock_context)
        assert response['statusCode'] == 400
    
    @patch('lambda_function.validate_jwt_token')
    def test_lambda_handler_sorting_validation(self, mock_validate):
        """Test sorting parameter validation."""
        mock_validate.return_value = {'sub': 'user123'}
        
        # Test invalid sort field
        event = self.create_api_event(query_params={'sortBy': 'invalidField'})
        response = lambda_handler(event, self.mock_context)
        assert response['statusCode'] == 400
        
        # Test invalid sort order
        event = self.create_api_event(query_params={'sortOrder': 'invalid'})
        response = lambda_handler(event, self.mock_context)
        assert response['statusCode'] == 400
    
    @patch('lambda_function.validate_jwt_token')
    def test_lambda_handler_with_phone_filter(self, mock_validate):
        """Test lead retrieval with phone field filter."""
        mock_validate.return_value = {'sub': 'user123'}
        
        query_params = {
            'filter_phone': '+1-555-0123',
            'page': '1',
            'pageSize': '50'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        with patch('lambda_function.query_leads_with_pagination') as mock_query:
            mock_query.return_value = {
                'leads': [self.sample_leads[0]],
                'pagination': {
                    'page': 1,
                    'pageSize': 50,
                    'totalCount': 1,
                    'totalPages': 1,
                    'hasMore': False,
                    'lastEvaluatedKey': None
                },
                'filters': {'phone': '+1-555-0123'},
                'sorting': {'sortBy': 'createdAt', 'sortOrder': 'desc'}
            }
            
            response = lambda_handler(event, self.mock_context)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['filters'] == {'phone': '+1-555-0123'}
            
            # Verify query was called with correct phone filter
            call_args = mock_query.call_args[1]
            assert call_args['filters'] == {'phone': '+1-555-0123'}
    
    @patch('lambda_function.validate_jwt_token')
    def test_lambda_handler_with_phone_sorting(self, mock_validate):
        """Test lead retrieval with phone field sorting."""
        mock_validate.return_value = {'sub': 'user123'}
        
        query_params = {
            'sortBy': 'phone',
            'sortOrder': 'asc'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        with patch('lambda_function.query_leads_with_pagination') as mock_query:
            mock_query.return_value = {
                'leads': self.sample_leads,
                'pagination': {
                    'page': 1,
                    'pageSize': 50,
                    'totalCount': 2,
                    'totalPages': 1,
                    'hasMore': False,
                    'lastEvaluatedKey': None
                },
                'filters': {},
                'sorting': {'sortBy': 'phone', 'sortOrder': 'asc'}
            }
            
            response = lambda_handler(event, self.mock_context)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['sorting']['sortBy'] == 'phone'
            assert body['sorting']['sortOrder'] == 'asc'
            
            # Verify query was called with correct phone sorting
            call_args = mock_query.call_args[1]
            assert call_args['sort_by'] == 'phone'
            assert call_args['sort_order'] == 'asc'
    
    @patch('lambda_function.validate_jwt_token')
    def test_lambda_handler_with_multiple_filters_including_phone(self, mock_validate):
        """Test lead retrieval with multiple filters including phone."""
        mock_validate.return_value = {'sub': 'user123'}
        
        query_params = {
            'filter_firstName': 'John',
            'filter_phone': '555',
            'filter_company': 'Tech',
            'page': '1',
            'pageSize': '25'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        with patch('lambda_function.query_leads_with_pagination') as mock_query:
            mock_query.return_value = {
                'leads': [self.sample_leads[0]],
                'pagination': {
                    'page': 1,
                    'pageSize': 25,
                    'totalCount': 1,
                    'totalPages': 1,
                    'hasMore': False,
                    'lastEvaluatedKey': None
                },
                'filters': {'firstName': 'John', 'phone': '555', 'company': 'Tech'},
                'sorting': {'sortBy': 'createdAt', 'sortOrder': 'desc'}
            }
            
            response = lambda_handler(event, self.mock_context)
            
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            expected_filters = {'firstName': 'John', 'phone': '555', 'company': 'Tech'}
            assert body['filters'] == expected_filters
            
            # Verify query was called with correct filters including phone
            call_args = mock_query.call_args[1]
            assert call_args['filters'] == expected_filters
    
    def test_lambda_handler_missing_auth(self):
        """Test request without authentication."""
        event = {
            'httpMethod': 'GET',
            'headers': {},
            'queryStringParameters': {}
        }
        
        response = lambda_handler(event, self.mock_context)
        assert response['statusCode'] == 401
    
    @patch('lambda_function.dynamodb_utils')
    def test_query_leads_with_pagination(self, mock_db):
        """Test the query_leads_with_pagination function."""
        # Setup mock
        mock_db.query_leads.return_value = {
            'leads': self.sample_leads,
            'totalCount': 2,
            'hasMore': False,
            'lastEvaluatedKey': None
        }
        
        # Execute
        result = query_leads_with_pagination(
            filters={'firstName': 'John'},
            sort_by='lastName',
            sort_order='asc',
            page=1,
            page_size=50
        )
        
        # Verify
        assert len(result['leads']) == 2
        assert result['pagination']['page'] == 1
        assert result['pagination']['pageSize'] == 50
        assert result['pagination']['totalCount'] == 2
        assert result['pagination']['totalPages'] == 1
        assert result['filters'] == {'firstName': 'John'}
        assert result['sorting']['sortBy'] == 'lastName'
        assert result['sorting']['sortOrder'] == 'asc'
        
        # Verify database call
        mock_db.query_leads.assert_called_once_with(
            filters={'firstName': 'John'},
            sort_by='lastName',
            sort_order='asc',
            page_size=50,
            last_evaluated_key=None
        )
    
    def test_format_leads_for_response(self):
        """Test lead data formatting for API response."""
        formatted = format_leads_for_response(self.sample_leads)
        
        assert len(formatted) == 2
        
        # Check first lead
        lead1 = formatted[0]
        assert lead1['leadId'] == 'lead-1'
        assert lead1['firstName'] == 'John'
        assert lead1['lastName'] == 'Doe'
        assert lead1['title'] == 'Software Engineer'
        assert lead1['company'] == 'Tech Corp'
        assert lead1['email'] == 'john.doe@techcorp.com'
        assert lead1['phone'] == '+1-555-0123'
        assert lead1['remarks'] == 'Interested in cloud solutions'
        assert lead1['sourceFile'] == 'leads.csv'
        assert 'createdAt' in lead1
        assert 'updatedAt' in lead1
    
    def test_format_leads_with_missing_fields(self):
        """Test lead formatting with missing fields."""
        incomplete_lead = {
            'leadId': 'lead-3',
            'firstName': 'Bob'
            # Missing other fields
        }
        
        formatted = format_leads_for_response([incomplete_lead])
        
        assert len(formatted) == 1
        lead = formatted[0]
        assert lead['leadId'] == 'lead-3'
        assert lead['firstName'] == 'Bob'
        assert lead['lastName'] == 'N/A'
        assert lead['title'] == 'N/A'
        assert lead['company'] == 'N/A'
        assert lead['email'] == 'N/A'
        assert lead['phone'] == 'N/A'
        assert lead['remarks'] == 'N/A'
    
    @patch('lambda_function.dynamodb_utils')
    def test_get_lead_by_id_success(self, mock_db):
        """Test successful single lead retrieval."""
        mock_db.get_lead.return_value = self.sample_leads[0]
        
        result = get_lead_by_id('lead-1')
        
        assert result['leadId'] == 'lead-1'
        assert result['firstName'] == 'John'
        mock_db.get_lead.assert_called_once_with('lead-1')
    
    @patch('lambda_function.dynamodb_utils')
    def test_get_lead_by_id_not_found(self, mock_db):
        """Test lead retrieval when lead not found."""
        mock_db.get_lead.return_value = None
        
        with pytest.raises(Exception):  # Should raise ValidationError
            get_lead_by_id('nonexistent-lead')
    
    def test_get_lead_by_id_invalid_input(self):
        """Test lead retrieval with invalid input."""
        with pytest.raises(Exception):  # Should raise ValidationError
            get_lead_by_id('')
        
        with pytest.raises(Exception):  # Should raise ValidationError
            get_lead_by_id(None)
    
    @patch('lambda_function.validate_jwt_token')
    @patch('lambda_function.get_lead_by_id')
    def test_get_single_lead_handler_success(self, mock_get_lead, mock_validate):
        """Test single lead handler success."""
        mock_validate.return_value = {'sub': 'user123'}
        mock_get_lead.return_value = self.sample_leads[0]
        
        event = self.create_api_event(path_params={'leadId': 'lead-1'})
        
        response = get_single_lead_handler(event, self.mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['lead']['leadId'] == 'lead-1'
        mock_get_lead.assert_called_once_with('lead-1')
    
    @patch('lambda_function.validate_jwt_token')
    def test_get_single_lead_handler_missing_id(self, mock_validate):
        """Test single lead handler with missing lead ID."""
        mock_validate.return_value = {'sub': 'user123'}
        
        event = self.create_api_event(path_params={})
        
        response = get_single_lead_handler(event, self.mock_context)
        
        assert response['statusCode'] == 400
    
    @patch('lambda_function.dynamodb_utils')
    def test_pagination_calculation(self, mock_db):
        """Test pagination metadata calculation."""
        # Test with total count that requires multiple pages
        mock_db.query_leads.return_value = {
            'leads': self.sample_leads,
            'totalCount': 150,
            'hasMore': True,
            'lastEvaluatedKey': {'leadId': 'last-key'}
        }
        
        result = query_leads_with_pagination(
            filters={},
            sort_by='createdAt',
            sort_order='desc',
            page=2,
            page_size=50
        )
        
        pagination = result['pagination']
        assert pagination['page'] == 2
        assert pagination['pageSize'] == 50
        assert pagination['totalCount'] == 150
        assert pagination['totalPages'] == 3  # 150 / 50 = 3
        assert pagination['hasMore'] is True
        assert pagination['lastEvaluatedKey'] is not None
    
    @patch('lambda_function.dynamodb_utils')
    def test_empty_results(self, mock_db):
        """Test handling of empty query results."""
        mock_db.query_leads.return_value = {
            'leads': [],
            'totalCount': 0,
            'hasMore': False,
            'lastEvaluatedKey': None
        }
        
        result = query_leads_with_pagination(
            filters={'firstName': 'NonExistent'},
            sort_by='createdAt',
            sort_order='desc',
            page=1,
            page_size=50
        )
        
        assert len(result['leads']) == 0
        assert result['pagination']['totalCount'] == 0
        assert result['pagination']['totalPages'] == 1
        assert result['pagination']['hasMore'] is False
    
    @patch('lambda_function.validate_jwt_token')
    def test_last_evaluated_key_parsing(self, mock_validate):
        """Test parsing of lastEvaluatedKey from query parameters."""
        mock_validate.return_value = {'sub': 'user123'}
        
        # Test valid JSON
        last_key = {'leadId': 'some-key'}
        query_params = {
            'lastEvaluatedKey': json.dumps(last_key)
        }
        
        event = self.create_api_event(query_params=query_params)
        
        with patch('lambda_function.query_leads_with_pagination') as mock_query:
            mock_query.return_value = {
                'leads': [],
                'pagination': {
                    'page': 1,
                    'pageSize': 50,
                    'totalCount': 0,
                    'totalPages': 1,
                    'hasMore': False,
                    'lastEvaluatedKey': None
                },
                'filters': {},
                'sorting': {'sortBy': 'createdAt', 'sortOrder': 'desc'}
            }
            
            response = lambda_handler(event, self.mock_context)
            
            assert response['statusCode'] == 200
            call_args = mock_query.call_args[1]
            assert call_args['last_evaluated_key'] == last_key
    
    @patch('lambda_function.validate_jwt_token')
    def test_invalid_last_evaluated_key(self, mock_validate):
        """Test handling of invalid lastEvaluatedKey."""
        mock_validate.return_value = {'sub': 'user123'}
        
        query_params = {
            'lastEvaluatedKey': 'invalid-json'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        response = lambda_handler(event, self.mock_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'lastEvaluatedKey' in body['error']['message']
    
    @patch('lambda_function.validate_jwt_token')
    def test_phone_field_in_valid_sort_fields(self, mock_validate):
        """Test that phone field is accepted as a valid sort field."""
        mock_validate.return_value = {'sub': 'user123'}
        
        query_params = {
            'sortBy': 'phone',
            'sortOrder': 'desc'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        with patch('lambda_function.query_leads_with_pagination') as mock_query:
            mock_query.return_value = {
                'leads': self.sample_leads,
                'pagination': {
                    'page': 1,
                    'pageSize': 50,
                    'totalCount': 2,
                    'totalPages': 1,
                    'hasMore': False,
                    'lastEvaluatedKey': None
                },
                'filters': {},
                'sorting': {'sortBy': 'phone', 'sortOrder': 'desc'}
            }
            
            response = lambda_handler(event, self.mock_context)
            
            # Should succeed without validation error
            assert response['statusCode'] == 200
            body = json.loads(response['body'])
            assert body['sorting']['sortBy'] == 'phone'
            assert body['sorting']['sortOrder'] == 'desc'

if __name__ == '__main__':
    pytest.main([__file__])