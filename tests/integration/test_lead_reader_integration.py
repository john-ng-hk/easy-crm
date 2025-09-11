"""
Integration tests for Lead Reader Lambda function.

Tests the complete functionality including DynamoDB integration,
filtering, sorting, and pagination with real AWS services.
"""

import json
import pytest
import boto3
import uuid
from datetime import datetime
from moto import mock_aws
import sys
import os

# Add lambda function to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))

from lambda_function import lambda_handler, get_single_lead_handler
from dynamodb_utils import DynamoDBUtils

@mock_aws
class TestLeadReaderIntegration:
    """Integration tests for Lead Reader Lambda function."""
    
    def setup_method(self, method):
        """Set up test environment with DynamoDB table and test data."""
        # Create DynamoDB table
        self.dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
        
        self.table_name = 'leads'
        self.table = self.dynamodb.create_table(
            TableName=self.table_name,
            KeySchema=[
                {
                    'AttributeName': 'leadId',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'leadId',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'company',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'email',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'createdAt',
                    'AttributeType': 'S'
                }
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'CompanyIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'company',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'createdAt',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    }
                },
                {
                    'IndexName': 'EmailIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'email',
                            'KeyType': 'HASH'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    }
                },
                {
                    'IndexName': 'CreatedAtIndex',
                    'KeySchema': [
                        {
                            'AttributeName': 'createdAt',
                            'KeyType': 'HASH'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    }
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Initialize DynamoDB utils with mocked table
        self.db_utils = DynamoDBUtils(table_name=self.table_name)
        # Override the table reference to use our mocked table
        self.db_utils.table = self.table
        
        # Create test data
        self.test_leads = [
            {
                'firstName': 'John',
                'lastName': 'Doe',
                'title': 'Software Engineer',
                'company': 'Tech Corp',
                'email': 'john.doe@techcorp.com',
                'phone': '+1-555-0123',
                'remarks': 'Interested in cloud solutions'
            },
            {
                'firstName': 'Jane',
                'lastName': 'Smith',
                'title': 'Product Manager',
                'company': 'Innovation Inc',
                'email': 'jane.smith@innovation.com',
                'phone': '+1-555-0456',
                'remarks': 'Looking for automation tools'
            },
            {
                'firstName': 'Bob',
                'lastName': 'Johnson',
                'title': 'CTO',
                'company': 'Tech Corp',
                'email': 'bob.johnson@techcorp.com',
                'phone': '+1-555-0789',
                'remarks': 'Decision maker for tech purchases'
            },
            {
                'firstName': 'Alice',
                'lastName': 'Williams',
                'title': 'Developer',
                'company': 'StartupXYZ',
                'email': 'alice@startupxyz.com',
                'phone': '+44-20-1234-5678',
                'remarks': 'Early adopter of new technologies'
            },
            {
                'firstName': 'Charlie',
                'lastName': 'Brown',
                'title': 'Manager',
                'company': 'Big Enterprise',
                'email': 'charlie.brown@bigenterprise.com',
                'phone': '+1-800-555-0001',
                'remarks': 'Needs enterprise-grade solutions'
            }
        ]
        
        # Insert test data
        self.lead_ids = []
        for lead_data in self.test_leads:
            lead_id = self.db_utils.create_lead(lead_data, 'test-file.csv')
            self.lead_ids.append(lead_id)
        
        # Mock context
        self.mock_context = type('MockContext', (), {
            'aws_request_id': 'test-request-id'
        })()
    
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
    
    def test_get_all_leads_default_pagination(self):
        """Test retrieving all leads with default pagination."""
        event = self.create_api_event()
        
        # Patch the dynamodb_utils in the lambda function to use our mocked instance
        import lambda_function
        original_utils = lambda_function.dynamodb_utils
        lambda_function.dynamodb_utils = self.db_utils
        
        try:
            response = lambda_handler(event, self.mock_context)
        finally:
            lambda_function.dynamodb_utils = original_utils
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Should return all 5 leads
        assert len(body['leads']) == 5
        assert body['pagination']['page'] == 1
        assert body['pagination']['pageSize'] == 50
        assert body['pagination']['totalCount'] == 5
        assert body['pagination']['totalPages'] == 1
        assert body['pagination']['hasMore'] is False
        
        # Check that all required fields are present
        for lead in body['leads']:
            assert 'leadId' in lead
            assert 'firstName' in lead
            assert 'lastName' in lead
            assert 'title' in lead
            assert 'company' in lead
            assert 'email' in lead
            assert 'phone' in lead
            assert 'remarks' in lead
            assert 'sourceFile' in lead
            assert 'createdAt' in lead
            assert 'updatedAt' in lead
    
    def test_pagination_with_small_page_size(self):
        """Test pagination with small page size."""
        query_params = {
            'page': '1',
            'pageSize': '2'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        response = lambda_handler(event, self.mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Should return only 2 leads
        assert len(body['leads']) == 2
        assert body['pagination']['page'] == 1
        assert body['pagination']['pageSize'] == 2
        assert body['pagination']['totalCount'] == 5
        assert body['pagination']['totalPages'] == 3  # 5 leads / 2 per page = 3 pages
        assert body['pagination']['hasMore'] is True
    
    def test_filter_by_first_name(self):
        """Test filtering leads by first name."""
        query_params = {
            'filter_firstName': 'John'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        response = lambda_handler(event, self.mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Should return only John Doe
        assert len(body['leads']) == 1
        assert body['leads'][0]['firstName'] == 'John'
        assert body['leads'][0]['lastName'] == 'Doe'
        assert body['filters'] == {'firstName': 'John'}
    
    def test_filter_by_company(self):
        """Test filtering leads by company."""
        query_params = {
            'filter_company': 'Tech Corp'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        response = lambda_handler(event, self.mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Should return John Doe and Bob Johnson (both from Tech Corp)
        assert len(body['leads']) == 2
        companies = [lead['company'] for lead in body['leads']]
        assert all(company == 'Tech Corp' for company in companies)
        assert body['filters'] == {'company': 'Tech Corp'}
    
    def test_filter_by_partial_match(self):
        """Test filtering with partial string matching."""
        query_params = {
            'filter_company': 'Tech'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        response = lambda_handler(event, self.mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Should return leads from Tech Corp (contains 'Tech')
        assert len(body['leads']) == 2
        for lead in body['leads']:
            assert 'Tech' in lead['company']
    
    def test_multiple_filters(self):
        """Test applying multiple filters simultaneously."""
        query_params = {
            'filter_company': 'Tech Corp',
            'filter_title': 'CTO'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        response = lambda_handler(event, self.mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Should return only Bob Johnson (CTO at Tech Corp)
        assert len(body['leads']) == 1
        assert body['leads'][0]['firstName'] == 'Bob'
        assert body['leads'][0]['title'] == 'CTO'
        assert body['leads'][0]['company'] == 'Tech Corp'
    
    def test_sort_by_first_name_ascending(self):
        """Test sorting leads by first name in ascending order."""
        query_params = {
            'sortBy': 'firstName',
            'sortOrder': 'asc'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        response = lambda_handler(event, self.mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Check that leads are sorted by first name ascending
        first_names = [lead['firstName'] for lead in body['leads']]
        assert first_names == sorted(first_names)
        assert body['sorting']['sortBy'] == 'firstName'
        assert body['sorting']['sortOrder'] == 'asc'
    
    def test_sort_by_last_name_descending(self):
        """Test sorting leads by last name in descending order."""
        query_params = {
            'sortBy': 'lastName',
            'sortOrder': 'desc'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        response = lambda_handler(event, self.mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Check that leads are sorted by last name descending
        last_names = [lead['lastName'] for lead in body['leads']]
        assert last_names == sorted(last_names, reverse=True)
        assert body['sorting']['sortBy'] == 'lastName'
        assert body['sorting']['sortOrder'] == 'desc'
    
    def test_sort_by_company(self):
        """Test sorting leads by company name."""
        query_params = {
            'sortBy': 'company',
            'sortOrder': 'asc'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        response = lambda_handler(event, self.mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Check that leads are sorted by company ascending
        companies = [lead['company'] for lead in body['leads']]
        assert companies == sorted(companies)
    
    def test_filter_and_sort_combined(self):
        """Test combining filters and sorting."""
        query_params = {
            'filter_company': 'Tech',
            'sortBy': 'firstName',
            'sortOrder': 'desc'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        response = lambda_handler(event, self.mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Should return Tech Corp leads sorted by first name descending
        assert len(body['leads']) == 2
        first_names = [lead['firstName'] for lead in body['leads']]
        assert first_names == sorted(first_names, reverse=True)
        
        # All should be from companies containing 'Tech'
        for lead in body['leads']:
            assert 'Tech' in lead['company']
    
    def test_pagination_with_filters(self):
        """Test pagination combined with filters."""
        query_params = {
            'filter_company': 'Tech Corp',
            'page': '1',
            'pageSize': '1'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        response = lambda_handler(event, self.mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Should return 1 lead from Tech Corp
        assert len(body['leads']) == 1
        assert body['leads'][0]['company'] == 'Tech Corp'
        assert body['pagination']['page'] == 1
        assert body['pagination']['pageSize'] == 1
        assert body['pagination']['hasMore'] is True  # There's another Tech Corp lead
    
    def test_empty_filter_results(self):
        """Test filtering with no matching results."""
        query_params = {
            'filter_firstName': 'NonExistentName'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        response = lambda_handler(event, self.mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Should return empty results
        assert len(body['leads']) == 0
        assert body['pagination']['totalCount'] == 0
        assert body['pagination']['totalPages'] == 1
        assert body['pagination']['hasMore'] is False
    
    def test_get_single_lead_by_id(self):
        """Test retrieving a single lead by ID."""
        lead_id = self.lead_ids[0]
        
        event = self.create_api_event(path_params={'leadId': lead_id})
        
        response = get_single_lead_handler(event, self.mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['lead']['leadId'] == lead_id
        assert body['lead']['firstName'] == 'John'
        assert body['lead']['lastName'] == 'Doe'
    
    def test_get_single_lead_not_found(self):
        """Test retrieving a non-existent lead."""
        event = self.create_api_event(path_params={'leadId': 'non-existent-id'})
        
        response = get_single_lead_handler(event, self.mock_context)
        
        assert response['statusCode'] == 400  # ValidationError for not found
    
    def test_invalid_pagination_parameters(self):
        """Test error handling for invalid pagination parameters."""
        # Test negative page number
        event = self.create_api_event(query_params={'page': '-1'})
        response = lambda_handler(event, self.mock_context)
        assert response['statusCode'] == 400
        
        # Test zero page number
        event = self.create_api_event(query_params={'page': '0'})
        response = lambda_handler(event, self.mock_context)
        assert response['statusCode'] == 400
        
        # Test page size too large
        event = self.create_api_event(query_params={'pageSize': '101'})
        response = lambda_handler(event, self.mock_context)
        assert response['statusCode'] == 400
    
    def test_invalid_sorting_parameters(self):
        """Test error handling for invalid sorting parameters."""
        # Test invalid sort field
        event = self.create_api_event(query_params={'sortBy': 'invalidField'})
        response = lambda_handler(event, self.mock_context)
        assert response['statusCode'] == 400
        
        # Test invalid sort order
        event = self.create_api_event(query_params={'sortOrder': 'invalid'})
        response = lambda_handler(event, self.mock_context)
        assert response['statusCode'] == 400
    
    def test_cors_headers_present(self):
        """Test that CORS headers are present in responses."""
        event = self.create_api_event()
        
        response = lambda_handler(event, self.mock_context)
        
        assert response['statusCode'] == 200
        headers = response['headers']
        assert 'Access-Control-Allow-Origin' in headers
        assert 'Access-Control-Allow-Headers' in headers
        assert 'Access-Control-Allow-Methods' in headers
        assert headers['Access-Control-Allow-Origin'] == '*'
    
    def test_cors_preflight_request(self):
        """Test CORS preflight OPTIONS request."""
        event = self.create_api_event(method='OPTIONS')
        
        response = lambda_handler(event, self.mock_context)
        
        assert response['statusCode'] == 200
        headers = response['headers']
        assert 'Access-Control-Allow-Origin' in headers
        assert 'Access-Control-Allow-Headers' in headers
        assert 'Access-Control-Allow-Methods' in headers
    
    def test_authentication_required(self):
        """Test that authentication is required."""
        event = {
            'httpMethod': 'GET',
            'headers': {},  # No Authorization header
            'queryStringParameters': {}
        }
        
        response = lambda_handler(event, self.mock_context)
        
        assert response['statusCode'] == 401
        body = json.loads(response['body'])
        assert 'error' in body
        assert body['error']['code'] == 'AUTHENTICATION_ERROR'
    
    def test_large_dataset_performance(self):
        """Test performance with larger dataset."""
        # Add more test data
        additional_leads = []
        for i in range(20):
            lead_data = {
                'firstName': f'User{i}',
                'lastName': f'Test{i}',
                'title': f'Position{i}',
                'company': f'Company{i % 5}',  # 5 different companies
                'email': f'user{i}@company{i % 5}.com',
                'remarks': f'Test lead number {i}'
            }
            additional_leads.append(lead_data)
        
        # Batch insert additional leads
        self.db_utils.batch_create_leads(additional_leads, 'large-test-file.csv')
        
        # Test querying all leads
        event = self.create_api_event()
        
        response = lambda_handler(event, self.mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Should return all 25 leads (5 original + 20 additional)
        assert len(body['leads']) == 25
        assert body['pagination']['totalCount'] == 25
    
    def test_filter_case_sensitivity(self):
        """Test that filtering handles case variations properly."""
        query_params = {
            'filter_company': 'tech corp'  # lowercase
        }
        
        event = self.create_api_event(query_params=query_params)
        
        response = lambda_handler(event, self.mock_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Should still find Tech Corp leads (case-insensitive matching)
        # Note: This depends on the DynamoDB implementation
        # The current implementation uses contains() which is case-sensitive
        # So this test verifies the current behavior
        assert len(body['leads']) == 0  # No matches due to case sensitivity
    
    def test_filter_by_phone_field(self):
        """Test filtering leads by phone field."""
        query_params = {
            'filter_phone': '+1-555-0123'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        # Patch the dynamodb_utils in the lambda function to use our mocked instance
        import lambda_function
        original_utils = lambda_function.dynamodb_utils
        lambda_function.dynamodb_utils = self.db_utils
        
        try:
            response = lambda_handler(event, self.mock_context)
        finally:
            lambda_function.dynamodb_utils = original_utils
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Should return only John Doe with matching phone
        assert len(body['leads']) == 1
        assert body['leads'][0]['firstName'] == 'John'
        assert body['leads'][0]['phone'] == '+1-555-0123'
        assert body['filters'] == {'phone': '+1-555-0123'}
    
    def test_filter_by_phone_partial_match(self):
        """Test filtering by partial phone number."""
        query_params = {
            'filter_phone': '555'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        # Patch the dynamodb_utils in the lambda function to use our mocked instance
        import lambda_function
        original_utils = lambda_function.dynamodb_utils
        lambda_function.dynamodb_utils = self.db_utils
        
        try:
            response = lambda_handler(event, self.mock_context)
        finally:
            lambda_function.dynamodb_utils = original_utils
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Should return leads with phone numbers containing '555'
        assert len(body['leads']) >= 4  # John, Jane, Bob, Charlie have 555 in their numbers
        for lead in body['leads']:
            assert '555' in lead['phone']
    
    def test_filter_by_phone_country_code(self):
        """Test filtering by country code in phone number."""
        query_params = {
            'filter_phone': '+44'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        # Patch the dynamodb_utils in the lambda function to use our mocked instance
        import lambda_function
        original_utils = lambda_function.dynamodb_utils
        lambda_function.dynamodb_utils = self.db_utils
        
        try:
            response = lambda_handler(event, self.mock_context)
        finally:
            lambda_function.dynamodb_utils = original_utils
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Should return only Alice with UK phone number
        assert len(body['leads']) == 1
        assert body['leads'][0]['firstName'] == 'Alice'
        assert body['leads'][0]['phone'] == '+44-20-1234-5678'
    
    def test_sort_by_phone_ascending(self):
        """Test sorting leads by phone field in ascending order."""
        query_params = {
            'sortBy': 'phone',
            'sortOrder': 'asc'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        # Patch the dynamodb_utils in the lambda function to use our mocked instance
        import lambda_function
        original_utils = lambda_function.dynamodb_utils
        lambda_function.dynamodb_utils = self.db_utils
        
        try:
            response = lambda_handler(event, self.mock_context)
        finally:
            lambda_function.dynamodb_utils = original_utils
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Check that leads are sorted by phone ascending
        phone_numbers = [lead['phone'] for lead in body['leads']]
        assert phone_numbers == sorted(phone_numbers)
        assert body['sorting']['sortBy'] == 'phone'
        assert body['sorting']['sortOrder'] == 'asc'
    
    def test_sort_by_phone_descending(self):
        """Test sorting leads by phone field in descending order."""
        query_params = {
            'sortBy': 'phone',
            'sortOrder': 'desc'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        # Patch the dynamodb_utils in the lambda function to use our mocked instance
        import lambda_function
        original_utils = lambda_function.dynamodb_utils
        lambda_function.dynamodb_utils = self.db_utils
        
        try:
            response = lambda_handler(event, self.mock_context)
        finally:
            lambda_function.dynamodb_utils = original_utils
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Check that leads are sorted by phone descending
        phone_numbers = [lead['phone'] for lead in body['leads']]
        assert phone_numbers == sorted(phone_numbers, reverse=True)
        assert body['sorting']['sortBy'] == 'phone'
        assert body['sorting']['sortOrder'] == 'desc'
    
    def test_filter_and_sort_by_phone(self):
        """Test combining phone filter with phone sorting."""
        query_params = {
            'filter_phone': '+1',  # US phone numbers
            'sortBy': 'phone',
            'sortOrder': 'asc'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        # Patch the dynamodb_utils in the lambda function to use our mocked instance
        import lambda_function
        original_utils = lambda_function.dynamodb_utils
        lambda_function.dynamodb_utils = self.db_utils
        
        try:
            response = lambda_handler(event, self.mock_context)
        finally:
            lambda_function.dynamodb_utils = original_utils
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Should return US phone numbers sorted ascending
        assert len(body['leads']) >= 4  # John, Jane, Bob, Charlie have +1 numbers
        phone_numbers = [lead['phone'] for lead in body['leads']]
        assert phone_numbers == sorted(phone_numbers)
        
        # All should have +1 country code
        for lead in body['leads']:
            assert '+1' in lead['phone']
    
    def test_multiple_filters_including_phone(self):
        """Test applying multiple filters including phone field."""
        query_params = {
            'filter_company': 'Tech Corp',
            'filter_phone': '555'
        }
        
        event = self.create_api_event(query_params=query_params)
        
        # Patch the dynamodb_utils in the lambda function to use our mocked instance
        import lambda_function
        original_utils = lambda_function.dynamodb_utils
        lambda_function.dynamodb_utils = self.db_utils
        
        try:
            response = lambda_handler(event, self.mock_context)
        finally:
            lambda_function.dynamodb_utils = original_utils
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Should return Tech Corp leads with 555 in phone number
        assert len(body['leads']) == 2  # John and Bob from Tech Corp
        for lead in body['leads']:
            assert lead['company'] == 'Tech Corp'
            assert '555' in lead['phone']
    
    def test_phone_field_in_response_format(self):
        """Test that phone field is properly included in response format."""
        event = self.create_api_event()
        
        # Patch the dynamodb_utils in the lambda function to use our mocked instance
        import lambda_function
        original_utils = lambda_function.dynamodb_utils
        lambda_function.dynamodb_utils = self.db_utils
        
        try:
            response = lambda_handler(event, self.mock_context)
        finally:
            lambda_function.dynamodb_utils = original_utils
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        # Check that phone field is present and properly formatted
        for lead in body['leads']:
            assert 'phone' in lead
            assert isinstance(lead['phone'], str)
            # Phone should not be empty (all test leads have phone numbers)
            assert lead['phone'] != ''
            assert lead['phone'] != 'N/A'

if __name__ == '__main__':
    pytest.main([__file__])