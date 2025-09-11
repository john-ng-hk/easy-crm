"""
Unit tests for Lead Exporter Lambda function.

Tests CSV generation, filtering integration, error handling,
and proper response formatting for lead export functionality.
"""

import pytest
import json
import base64
import csv
import io
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Mock AWS services before importing the lambda function
with patch('boto3.resource'):
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-exporter'))
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))
    
    from lambda_function import (
        lambda_handler,
        get_filtered_leads_for_export,
        generate_csv_data,
        validate_export_request,
        get_export_preview_handler,
        CSV_HEADERS
    )

@pytest.fixture
def sample_leads():
    """Sample leads data for testing."""
    return [
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
            'createdAt': '2024-01-15T10:30:00Z',
            'updatedAt': '2024-01-15T10:30:00Z'
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
            'createdAt': '2024-01-16T14:20:00Z',
            'updatedAt': '2024-01-16T14:20:00Z'
        }
    ]

@pytest.fixture
def api_event():
    """Sample API Gateway event."""
    return {
        'httpMethod': 'POST',
        'headers': {
            'Authorization': 'Bearer valid-jwt-token'
        },
        'queryStringParameters': {
            'filter_company': 'Tech',
            'filter_title': 'Engineer',
            'filter_phone': '555'
        }
    }

@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = Mock()
    context.function_name = 'lead-exporter-lambda'
    context.memory_limit_in_mb = 256
    context.remaining_time_in_millis = lambda: 30000
    return context

class TestLeadExporter:
    """Test cases for lead exporter functionality."""

class TestCSVGeneration:
    """Test CSV generation functionality."""
    
    def test_generate_csv_data_success(self, sample_leads):
        """Test successful CSV generation."""
        csv_data = generate_csv_data(sample_leads)
        
        # Verify CSV structure
        assert isinstance(csv_data, str)
        assert len(csv_data) > 0
        
        # Parse CSV to verify content
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        rows = list(csv_reader)
        
        # Verify header row
        assert csv_reader.fieldnames == CSV_HEADERS
        
        # Verify data rows
        assert len(rows) == 2
        assert rows[0]['firstName'] == 'John'
        assert rows[0]['lastName'] == 'Doe'
        assert rows[0]['company'] == 'Tech Corp'
        assert rows[0]['phone'] == '+1-555-0123'
        assert rows[1]['firstName'] == 'Jane'
        assert rows[1]['lastName'] == 'Smith'
        assert rows[1]['company'] == 'Innovation Inc'
        assert rows[1]['phone'] == '+1-555-0456'
    
    def test_generate_csv_data_empty_list(self):
        """Test CSV generation with empty leads list."""
        csv_data = generate_csv_data([])
        
        # Should still have headers
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        rows = list(csv_reader)
        
        assert csv_reader.fieldnames == CSV_HEADERS
        assert len(rows) == 0
    
    def test_generate_csv_data_missing_fields(self):
        """Test CSV generation with leads missing some fields."""
        incomplete_leads = [
            {
                'leadId': 'lead-1',
                'firstName': 'John',
                'lastName': 'Doe'
                # Missing other fields
            }
        ]
        
        csv_data = generate_csv_data(incomplete_leads)
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        rows = list(csv_reader)
        
        assert len(rows) == 1
        assert rows[0]['firstName'] == 'John'
        assert rows[0]['lastName'] == 'Doe'
        assert rows[0]['title'] == 'N/A'  # Should default to N/A
        assert rows[0]['company'] == 'N/A'
        assert rows[0]['email'] == 'N/A'
        assert rows[0]['phone'] == 'N/A'
    
    def test_generate_csv_data_none_values(self):
        """Test CSV generation with None values."""
        leads_with_none = [
            {
                'leadId': 'lead-1',
                'firstName': None,
                'lastName': 'Doe',
                'title': '',
                'company': 'Tech Corp',
                'email': None,
                'phone': None,
                'remarks': 'Some remarks',
                'sourceFile': 'test.csv',
                'createdAt': '2024-01-15T10:30:00Z',
                'updatedAt': '2024-01-15T10:30:00Z'
            }
        ]
        
        csv_data = generate_csv_data(leads_with_none)
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        rows = list(csv_reader)
        
        assert len(rows) == 1
        assert rows[0]['firstName'] == 'N/A'  # None should become N/A
        assert rows[0]['lastName'] == 'Doe'
        assert rows[0]['title'] == ''  # Empty string preserved
        assert rows[0]['email'] == 'N/A'  # None should become N/A
        assert rows[0]['phone'] == 'N/A'  # None should become N/A
    
    def test_generate_csv_data_invalid_input(self):
        """Test CSV generation with invalid input."""
        with pytest.raises(Exception):  # Should raise ValidationError
            generate_csv_data("not a list")
    
    def test_csv_headers_order(self, sample_leads):
        """Test that CSV headers are in the correct order."""
        csv_data = generate_csv_data(sample_leads)
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        
        expected_headers = [
            'leadId', 'firstName', 'lastName', 'title', 'company', 
            'email', 'phone', 'remarks', 'sourceFile', 'createdAt', 'updatedAt'
        ]
        
        assert csv_reader.fieldnames == expected_headers

class TestFilteringIntegration:
    """Test filtering integration with DynamoDB."""
    
    @patch('lambda_function.dynamodb_utils')
    def test_get_filtered_leads_for_export_success(self, mock_dynamodb_utils, sample_leads):
        """Test successful lead retrieval with filters."""
        # Mock DynamoDB response
        mock_dynamodb_utils.get_all_leads_for_export.return_value = sample_leads
        
        filters = {'company': 'Tech', 'title': 'Engineer'}
        result = get_filtered_leads_for_export(filters)
        
        # Verify DynamoDB was called with correct filters
        mock_dynamodb_utils.get_all_leads_for_export.assert_called_once_with(filters)
        
        # Verify result formatting
        assert len(result) == 2
        assert result[0]['firstName'] == 'John'
        assert result[0]['company'] == 'Tech Corp'
        assert result[1]['firstName'] == 'Jane'
        assert result[1]['company'] == 'Innovation Inc'
    
    @patch('lambda_function.dynamodb_utils')
    def test_get_filtered_leads_for_export_empty_result(self, mock_dynamodb_utils):
        """Test lead retrieval with no matching results."""
        mock_dynamodb_utils.get_all_leads_for_export.return_value = []
        
        filters = {'company': 'NonExistent'}
        result = get_filtered_leads_for_export(filters)
        
        assert result == []
        mock_dynamodb_utils.get_all_leads_for_export.assert_called_once_with(filters)
    
    @patch('lambda_function.dynamodb_utils')
    def test_get_filtered_leads_for_export_database_error(self, mock_dynamodb_utils):
        """Test handling of database errors during lead retrieval."""
        mock_dynamodb_utils.get_all_leads_for_export.side_effect = Exception("Database connection failed")
        
        filters = {'company': 'Tech'}
        
        with pytest.raises(Exception):  # Should raise DatabaseError
            get_filtered_leads_for_export(filters)

class TestValidation:
    """Test request validation functionality."""
    
    def test_validate_export_request_success(self):
        """Test successful request validation."""
        query_params = {
            'filter_firstName': 'John',
            'filter_company': 'Tech Corp',
            'filter_email': 'john@example.com',
            'filter_phone': '+1-555-0123'
        }
        
        filters = validate_export_request(query_params)
        
        expected_filters = {
            'firstName': 'John',
            'company': 'Tech Corp',
            'email': 'john@example.com',
            'phone': '+1-555-0123'
        }
        
        assert filters == expected_filters
    
    def test_validate_export_request_empty_filters(self):
        """Test validation with empty filter values."""
        query_params = {
            'filter_firstName': '',
            'filter_company': '   ',  # Whitespace only
            'filter_email': 'john@example.com',
            'filter_phone': '   '  # Whitespace only
        }
        
        filters = validate_export_request(query_params)
        
        # Only non-empty filters should be included
        assert filters == {'email': 'john@example.com'}
    
    def test_validate_export_request_no_filters(self):
        """Test validation with no filter parameters."""
        query_params = {}
        
        filters = validate_export_request(query_params)
        
        assert filters == {}
    
    def test_validate_export_request_invalid_field(self):
        """Test validation ignores invalid filter fields."""
        query_params = {
            'filter_firstName': 'John',
            'filter_phone': '+1-555-0123',
            'filter_invalidField': 'SomeValue',  # Should be ignored
            'otherParam': 'Value'  # Should be ignored
        }
        
        filters = validate_export_request(query_params)
        
        assert filters == {'firstName': 'John', 'phone': '+1-555-0123'}
    
    def test_validate_export_request_long_value(self):
        """Test validation with overly long filter values."""
        long_value = 'x' * 101  # Exceeds 100 character limit
        query_params = {
            'filter_firstName': long_value
        }
        
        with pytest.raises(Exception):  # Should raise ValidationError
            validate_export_request(query_params)

class TestLambdaHandler:
    """Test main Lambda handler functionality."""
    
    @patch('lambda_function.validate_jwt_token')
    @patch('lambda_function.get_filtered_leads_for_export')
    def test_lambda_handler_success(self, mock_get_leads, mock_validate_jwt, 
                                  api_event, lambda_context, sample_leads):
        """Test successful export request."""
        # Mock authentication
        mock_validate_jwt.return_value = {'sub': 'user123'}
        
        # Mock lead retrieval
        mock_get_leads.return_value = sample_leads
        
        response = lambda_handler(api_event, lambda_context)
        
        # Verify response structure
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['leadCount'] == 2
        assert 'csvData' in body
        assert 'filename' in body
        assert body['message'] == 'Successfully exported 2 leads'
        
        # Verify CSV data is base64 encoded
        csv_data = base64.b64decode(body['csvData']).decode('utf-8')
        assert 'firstName,lastName' in csv_data or 'John,Doe' in csv_data
    
    @patch('lambda_function.validate_jwt_token')
    @patch('lambda_function.get_filtered_leads_for_export')
    def test_lambda_handler_no_matching_leads(self, mock_get_leads, mock_validate_jwt, 
                                            api_event, lambda_context):
        """Test export request with no matching leads."""
        mock_validate_jwt.return_value = {'sub': 'user123'}
        mock_get_leads.return_value = []
        
        response = lambda_handler(api_event, lambda_context)
        
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['leadCount'] == 0
        assert body['csvData'] is None
        assert 'No leads match' in body['message']
    
    def test_lambda_handler_cors_preflight(self, lambda_context):
        """Test CORS preflight request handling."""
        cors_event = {
            'httpMethod': 'OPTIONS'
        }
        
        response = lambda_handler(cors_event, lambda_context)
        
        assert response['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in response['headers']
    
    @patch('lambda_function.validate_jwt_token')
    def test_lambda_handler_authentication_error(self, mock_validate_jwt, 
                                               api_event, lambda_context):
        """Test handling of authentication errors."""
        mock_validate_jwt.side_effect = Exception("Invalid token")
        
        response = lambda_handler(api_event, lambda_context)
        
        assert response['statusCode'] == 401
    
    @patch('lambda_function.validate_jwt_token')
    @patch('lambda_function.get_filtered_leads_for_export')
    def test_lambda_handler_database_error(self, mock_get_leads, mock_validate_jwt, 
                                         api_event, lambda_context):
        """Test handling of database errors."""
        mock_validate_jwt.return_value = {'sub': 'user123'}
        mock_get_leads.side_effect = Exception("Database error")
        
        response = lambda_handler(api_event, lambda_context)
        
        assert response['statusCode'] == 500

class TestExportPreview:
    """Test export preview functionality."""
    
    @patch('lambda_function.validate_jwt_token')
    @patch('lambda_function.get_filtered_leads_for_export')
    def test_get_export_preview_handler_success(self, mock_get_leads, mock_validate_jwt, 
                                              api_event, lambda_context, sample_leads):
        """Test successful export preview request."""
        mock_validate_jwt.return_value = {'sub': 'user123'}
        mock_get_leads.return_value = sample_leads
        
        response = get_export_preview_handler(api_event, lambda_context)
        
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['leadCount'] == 2
        assert '2 leads match' in body['message']
        assert 'filters' in body
    
    @patch('lambda_function.validate_jwt_token')
    @patch('lambda_function.get_filtered_leads_for_export')
    def test_get_export_preview_handler_no_leads(self, mock_get_leads, mock_validate_jwt, 
                                                api_event, lambda_context):
        """Test export preview with no matching leads."""
        mock_validate_jwt.return_value = {'sub': 'user123'}
        mock_get_leads.return_value = []
        
        response = get_export_preview_handler(api_event, lambda_context)
        
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['leadCount'] == 0
        assert '0 leads match' in body['message']

class TestErrorHandling:
    """Test error handling scenarios."""
    
    @patch('lambda_function.validate_jwt_token')
    def test_malformed_query_parameters(self, mock_validate_jwt, lambda_context):
        """Test handling of malformed query parameters."""
        mock_validate_jwt.return_value = {'sub': 'user123'}
        
        malformed_event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer token'},
            'queryStringParameters': None  # This could cause issues
        }
        
        # Should handle gracefully and not crash
        response = lambda_handler(malformed_event, lambda_context)
        
        # Should still process (with no filters)
        assert response['statusCode'] in [200, 500]  # Either success or handled error
    
    def test_csv_generation_with_special_characters(self):
        """Test CSV generation with special characters and quotes."""
        leads_with_special_chars = [
            {
                'leadId': 'lead-1',
                'firstName': 'John "Johnny"',
                'lastName': "O'Connor",
                'title': 'Senior Engineer, Team Lead',
                'company': 'Tech & Innovation Corp',
                'email': 'john@tech-innovation.com',
                'phone': '+1-(555) 123-4567 ext. 890',
                'remarks': 'Interested in "cloud solutions" & automation',
                'sourceFile': 'leads,with,commas.csv',
                'createdAt': '2024-01-15T10:30:00Z',
                'updatedAt': '2024-01-15T10:30:00Z'
            }
        ]
        
        csv_data = generate_csv_data(leads_with_special_chars)
        
        # Should not crash and should properly escape special characters
        assert isinstance(csv_data, str)
        assert len(csv_data) > 0
        
        # Parse back to verify proper escaping
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        rows = list(csv_reader)
        
        assert len(rows) == 1
        assert rows[0]['firstName'] == 'John "Johnny"'
        assert rows[0]['lastName'] == "O'Connor"
        assert rows[0]['company'] == 'Tech & Innovation Corp'
        assert rows[0]['phone'] == '+1-(555) 123-4567 ext. 890'

class TestPhoneFieldSupport:
    """Test phone field support in CSV export functionality."""
    
    def test_csv_generation_with_phone_field(self):
        """Test CSV generation includes phone field in correct position."""
        leads_with_phone = [
            {
                'leadId': 'lead-1',
                'firstName': 'John',
                'lastName': 'Doe',
                'title': 'Engineer',
                'company': 'Tech Corp',
                'email': 'john@tech.com',
                'phone': '+1-555-0123',
                'remarks': 'Test lead',
                'sourceFile': 'test.csv',
                'createdAt': '2024-01-15T10:30:00Z',
                'updatedAt': '2024-01-15T10:30:00Z'
            }
        ]
        
        csv_data = generate_csv_data(leads_with_phone)
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        rows = list(csv_reader)
        
        # Verify phone field is included and in correct position
        assert 'phone' in csv_reader.fieldnames
        phone_index = csv_reader.fieldnames.index('phone')
        email_index = csv_reader.fieldnames.index('email')
        remarks_index = csv_reader.fieldnames.index('remarks')
        
        # Phone should be between email and remarks
        assert email_index < phone_index < remarks_index
        
        # Verify phone data
        assert len(rows) == 1
        assert rows[0]['phone'] == '+1-555-0123'
    
    def test_csv_generation_missing_phone_field(self):
        """Test CSV generation when phone field is missing from lead data."""
        leads_without_phone = [
            {
                'leadId': 'lead-1',
                'firstName': 'John',
                'lastName': 'Doe',
                'title': 'Engineer',
                'company': 'Tech Corp',
                'email': 'john@tech.com',
                # phone field missing
                'remarks': 'Test lead',
                'sourceFile': 'test.csv',
                'createdAt': '2024-01-15T10:30:00Z',
                'updatedAt': '2024-01-15T10:30:00Z'
            }
        ]
        
        csv_data = generate_csv_data(leads_without_phone)
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        rows = list(csv_reader)
        
        # Phone field should still be in headers
        assert 'phone' in csv_reader.fieldnames
        
        # Phone value should default to N/A
        assert len(rows) == 1
        assert rows[0]['phone'] == 'N/A'
    
    def test_csv_generation_phone_field_variations(self):
        """Test CSV generation with various phone field formats."""
        leads_with_phone_variations = [
            {
                'leadId': 'lead-1',
                'firstName': 'John',
                'lastName': 'Doe',
                'phone': '+1-555-0123',  # Standard format
                'email': 'john@tech.com',
                'company': 'Tech Corp',
                'title': 'Engineer',
                'remarks': 'Standard phone',
                'sourceFile': 'test.csv',
                'createdAt': '2024-01-15T10:30:00Z',
                'updatedAt': '2024-01-15T10:30:00Z'
            },
            {
                'leadId': 'lead-2',
                'firstName': 'Jane',
                'lastName': 'Smith',
                'phone': '(555) 123-4567',  # Different format
                'email': 'jane@tech.com',
                'company': 'Tech Corp',
                'title': 'Manager',
                'remarks': 'Parentheses format',
                'sourceFile': 'test.csv',
                'createdAt': '2024-01-15T10:30:00Z',
                'updatedAt': '2024-01-15T10:30:00Z'
            },
            {
                'leadId': 'lead-3',
                'firstName': 'Bob',
                'lastName': 'Johnson',
                'phone': 'N/A',  # Explicit N/A
                'email': 'bob@tech.com',
                'company': 'Tech Corp',
                'title': 'Developer',
                'remarks': 'No phone available',
                'sourceFile': 'test.csv',
                'createdAt': '2024-01-15T10:30:00Z',
                'updatedAt': '2024-01-15T10:30:00Z'
            }
        ]
        
        csv_data = generate_csv_data(leads_with_phone_variations)
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        rows = list(csv_reader)
        
        assert len(rows) == 3
        assert rows[0]['phone'] == '+1-555-0123'
        assert rows[1]['phone'] == '(555) 123-4567'
        assert rows[2]['phone'] == 'N/A'
    
    def test_phone_field_filtering_support(self):
        """Test that phone field is supported in export filtering."""
        query_params = {
            'filter_phone': '555'
        }
        
        filters = validate_export_request(query_params)
        
        assert 'phone' in filters
        assert filters['phone'] == '555'
    
    def test_phone_field_filtering_with_special_characters(self):
        """Test phone field filtering with special characters."""
        query_params = {
            'filter_phone': '+1-555'
        }
        
        filters = validate_export_request(query_params)
        
        assert filters['phone'] == '+1-555'
    
    @patch('lambda_function.dynamodb_utils')
    def test_get_filtered_leads_includes_phone_filter(self, mock_dynamodb_utils):
        """Test that phone filters are passed to DynamoDB query."""
        mock_dynamodb_utils.get_all_leads_for_export.return_value = []
        
        filters = {'phone': '555', 'company': 'Tech'}
        get_filtered_leads_for_export(filters)
        
        # Verify DynamoDB was called with phone filter included
        mock_dynamodb_utils.get_all_leads_for_export.assert_called_once_with(filters)
        called_filters = mock_dynamodb_utils.get_all_leads_for_export.call_args[0][0]
        assert 'phone' in called_filters
        assert called_filters['phone'] == '555'
    
    @patch('lambda_function.validate_jwt_token')
    @patch('lambda_function.get_filtered_leads_for_export')
    def test_lambda_handler_with_phone_filter(self, mock_get_leads, mock_validate_jwt, lambda_context):
        """Test main handler with phone field filter."""
        mock_validate_jwt.return_value = {'sub': 'user123'}
        
        leads_with_phone = [
            {
                'leadId': 'lead-1',
                'firstName': 'John',
                'lastName': 'Doe',
                'phone': '+1-555-0123',
                'email': 'john@tech.com',
                'company': 'Tech Corp',
                'title': 'Engineer',
                'remarks': 'Test lead',
                'sourceFile': 'test.csv',
                'createdAt': '2024-01-15T10:30:00Z',
                'updatedAt': '2024-01-15T10:30:00Z'
            }
        ]
        mock_get_leads.return_value = leads_with_phone
        
        event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer token'},
            'queryStringParameters': {
                'filter_phone': '555'
            }
        }
        
        response = lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['leadCount'] == 1
        
        # Verify CSV contains phone data
        csv_data = base64.b64decode(body['csvData']).decode('utf-8')
        assert '+1-555-0123' in csv_data
        
        # Verify filters were applied correctly
        mock_get_leads.assert_called_once()
        called_filters = mock_get_leads.call_args[0][0]
        assert 'phone' in called_filters
        assert called_filters['phone'] == '555'