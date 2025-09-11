"""
Integration tests for Lead Exporter Lambda function.

Tests the complete export workflow including DynamoDB integration,
CSV generation, and filtering consistency with the lead reader.
"""

import pytest
import json
import base64
import csv
import io
import boto3
from moto import mock_aws
from datetime import datetime
import os
import sys
from unittest.mock import patch

# Add lambda function to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-exporter'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))

from lambda_function import lambda_handler, get_export_preview_handler
from dynamodb_utils import DynamoDBUtils

@pytest.fixture
def dynamodb_table():
    """Create a mock DynamoDB table for testing."""
    with mock_aws():
        # Create DynamoDB resource
        dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
        
        # Create table
        table = dynamodb.create_table(
            TableName='leads',
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
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Wait for table to be created
        table.wait_until_exists()
        
        yield table

@pytest.fixture
def sample_leads_data():
    """Sample leads data for testing."""
    return [
        {
            'leadId': 'lead-001',
            'firstName': 'John',
            'lastName': 'Doe',
            'title': 'Software Engineer',
            'company': 'Tech Corp',
            'email': 'john.doe@techcorp.com',
            'remarks': 'Interested in cloud solutions',
            'sourceFile': 'leads_batch_1.csv',
            'createdAt': '2024-01-15T10:30:00Z',
            'updatedAt': '2024-01-15T10:30:00Z'
        },
        {
            'leadId': 'lead-002',
            'firstName': 'Jane',
            'lastName': 'Smith',
            'title': 'Product Manager',
            'company': 'Innovation Inc',
            'email': 'jane.smith@innovation.com',
            'remarks': 'Looking for automation tools',
            'sourceFile': 'leads_batch_1.csv',
            'createdAt': '2024-01-16T14:20:00Z',
            'updatedAt': '2024-01-16T14:20:00Z'
        },
        {
            'leadId': 'lead-003',
            'firstName': 'Bob',
            'lastName': 'Johnson',
            'title': 'Senior Developer',
            'company': 'Tech Corp',
            'email': 'bob.johnson@techcorp.com',
            'remarks': 'Needs scalable infrastructure',
            'sourceFile': 'leads_batch_2.csv',
            'createdAt': '2024-01-17T09:15:00Z',
            'updatedAt': '2024-01-17T09:15:00Z'
        },
        {
            'leadId': 'lead-004',
            'firstName': 'Alice',
            'lastName': 'Williams',
            'title': 'CTO',
            'company': 'StartupXYZ',
            'email': 'alice@startupxyz.com',
            'remarks': 'Evaluating new technologies',
            'sourceFile': 'leads_batch_2.csv',
            'createdAt': '2024-01-18T16:45:00Z',
            'updatedAt': '2024-01-18T16:45:00Z'
        }
    ]

@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    class MockContext:
        def __init__(self):
            self.function_name = 'lead-exporter-lambda'
            self.memory_limit_in_mb = 256
            self.invoked_function_arn = 'arn:aws:lambda:ap-southeast-1:123456789012:function:lead-exporter-lambda'
            self.aws_request_id = 'test-request-id-123'
            
        def get_remaining_time_in_millis(self):
            return 30000
    
    return MockContext()

class TestLeadExporterIntegration:
    """Integration tests for lead exporter functionality."""
    
    def setup_method(self):
        """Set up test data in DynamoDB."""
        pass
    
    def populate_test_data(self, dynamodb_table, leads_data):
        """Populate DynamoDB table with test data."""
        with dynamodb_table.batch_writer() as batch:
            for lead in leads_data:
                batch.put_item(Item=lead)
    
    @pytest.mark.integration
    def test_export_all_leads_no_filters(self, dynamodb_table, sample_leads_data, lambda_context):
        """Test exporting all leads without any filters."""
        # Populate test data
        self.populate_test_data(dynamodb_table, sample_leads_data)
        
        # Create API Gateway event with no filters
        event = {
            'httpMethod': 'POST',
            'headers': {
                'Authorization': 'Bearer mock-jwt-token'
            },
            'body': json.dumps({})
        }
        
        # Mock JWT validation
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            response = lambda_handler(event, lambda_context)
        
        # Verify response
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['leadCount'] == 4
        assert 'csvData' in body
        assert 'filename' in body
        
        # Decode and verify CSV content
        csv_data = base64.b64decode(body['csvData']).decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        rows = list(csv_reader)
        
        assert len(rows) == 4
        
        # Verify all leads are present
        lead_ids = [row['leadId'] for row in rows]
        expected_ids = ['lead-001', 'lead-002', 'lead-003', 'lead-004']
        assert set(lead_ids) == set(expected_ids)
    
    @pytest.mark.integration
    def test_export_with_company_filter(self, dynamodb_table, sample_leads_data, lambda_context):
        """Test exporting leads with company filter."""
        self.populate_test_data(dynamodb_table, sample_leads_data)
        
        # Create event with company filter
        event = {
            'httpMethod': 'POST',
            'headers': {
                'Authorization': 'Bearer mock-jwt-token'
            },
            'body': json.dumps({
                'filters': {
                    'company': 'Tech Corp'
                }
            })
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            response = lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['leadCount'] == 2  # Only Tech Corp leads
        
        # Verify CSV content
        csv_data = base64.b64decode(body['csvData']).decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        rows = list(csv_reader)
        
        assert len(rows) == 2
        for row in rows:
            assert 'Tech Corp' in row['company']
    
    @pytest.mark.integration
    def test_export_with_multiple_filters(self, dynamodb_table, sample_leads_data, lambda_context):
        """Test exporting leads with multiple filters."""
        self.populate_test_data(dynamodb_table, sample_leads_data)
        
        # Create event with multiple filters
        event = {
            'httpMethod': 'POST',
            'headers': {
                'Authorization': 'Bearer mock-jwt-token'
            },
            'body': json.dumps({
                'filters': {
                    'company': 'Tech',  # Should match "Tech Corp"
                    'title': 'Engineer'  # Should match "Software Engineer"
                }
            })
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            response = lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['leadCount'] == 1  # Only John Doe matches both filters
        
        # Verify CSV content
        csv_data = base64.b64decode(body['csvData']).decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        rows = list(csv_reader)
        
        assert len(rows) == 1
        assert rows[0]['firstName'] == 'John'
        assert rows[0]['lastName'] == 'Doe'
    
    @pytest.mark.integration
    def test_export_no_matching_leads(self, dynamodb_table, sample_leads_data, lambda_context):
        """Test export when no leads match the filters."""
        self.populate_test_data(dynamodb_table, sample_leads_data)
        
        # Create event with filter that matches no leads
        event = {
            'httpMethod': 'POST',
            'headers': {
                'Authorization': 'Bearer mock-jwt-token'
            },
            'body': json.dumps({
                'filters': {
                    'company': 'NonExistentCompany'
                }
            })
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            response = lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['leadCount'] == 0
        assert body['csvData'] is None
        assert 'No leads match' in body['message']
    
    @pytest.mark.integration
    def test_export_preview_functionality(self, dynamodb_table, sample_leads_data, lambda_context):
        """Test export preview handler."""
        self.populate_test_data(dynamodb_table, sample_leads_data)
        
        # Create event for preview
        event = {
            'httpMethod': 'POST',
            'headers': {
                'Authorization': 'Bearer mock-jwt-token'
            },
            'body': json.dumps({
                'filters': {
                    'company': 'Tech Corp'
                }
            })
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            response = get_export_preview_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['leadCount'] == 2
        assert '2 leads match' in body['message']
        assert 'csvData' not in body  # Preview should not include CSV data
    
    @pytest.mark.integration
    def test_csv_format_consistency(self, dynamodb_table, sample_leads_data, lambda_context):
        """Test that CSV format matches expected structure."""
        self.populate_test_data(dynamodb_table, sample_leads_data)
        
        event = {
            'httpMethod': 'POST',
            'headers': {
                'Authorization': 'Bearer mock-jwt-token'
            },
            'body': json.dumps({})
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            response = lambda_handler(event, lambda_context)
        
        # Decode CSV and verify structure
        body = json.loads(response['body'])
        csv_data = base64.b64decode(body['csvData']).decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        
        # Verify headers
        expected_headers = [
            'leadId', 'firstName', 'lastName', 'title', 'company',
            'email', 'phone', 'remarks', 'sourceFile', 'createdAt', 'updatedAt'
        ]
        assert csv_reader.fieldnames == expected_headers
        
        # Verify data integrity
        rows = list(csv_reader)
        for row in rows:
            assert all(header in row for header in expected_headers)
            assert row['leadId'].startswith('lead-')
            assert '@' in row['email'] or row['email'] == 'N/A'
    
    @pytest.mark.integration
    def test_large_dataset_export(self, dynamodb_table, lambda_context):
        """Test export with a larger dataset."""
        # Generate larger test dataset
        large_dataset = []
        for i in range(100):
            lead = {
                'leadId': f'lead-{i:03d}',
                'firstName': f'FirstName{i}',
                'lastName': f'LastName{i}',
                'title': f'Title{i}',
                'company': f'Company{i % 10}',  # 10 different companies
                'email': f'user{i}@company{i % 10}.com',
                'remarks': f'Remarks for lead {i}',
                'sourceFile': f'batch_{i // 20}.csv',
                'createdAt': f'2024-01-{(i % 28) + 1:02d}T10:30:00Z',
                'updatedAt': f'2024-01-{(i % 28) + 1:02d}T10:30:00Z'
            }
            large_dataset.append(lead)
        
        self.populate_test_data(dynamodb_table, large_dataset)
        
        # Export all leads
        event = {
            'httpMethod': 'POST',
            'headers': {
                'Authorization': 'Bearer mock-jwt-token'
            },
            'body': json.dumps({})
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            response = lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['leadCount'] == 100
        
        # Verify CSV can be parsed
        csv_data = base64.b64decode(body['csvData']).decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        rows = list(csv_reader)
        
        assert len(rows) == 100
    
    @pytest.mark.integration
    def test_filtering_consistency_with_lead_reader(self, dynamodb_table, sample_leads_data, lambda_context):
        """Test that filtering works consistently with lead reader logic."""
        self.populate_test_data(dynamodb_table, sample_leads_data)
        
        # Test case-insensitive filtering (DynamoDB contains() is case-sensitive, 
        # but our test data should work with exact matches)
        test_cases = [
            {
                'filter': {'filter_firstName': 'John'},
                'expected_count': 1,
                'expected_names': ['John']
            },
            {
                'filter': {'filter_company': 'Tech'},
                'expected_count': 2,
                'expected_companies': ['Tech Corp', 'Tech Corp']
            },
            {
                'filter': {'filter_title': 'Manager'},
                'expected_count': 1,
                'expected_titles': ['Product Manager']
            }
        ]
        
        for test_case in test_cases:
            event = {
                'httpMethod': 'POST',
                'headers': {
                    'Authorization': 'Bearer mock-jwt-token'
                },
                'queryStringParameters': test_case['filter']
            }
            
            with patch('lambda_function.validate_jwt_token') as mock_jwt:
                mock_jwt.return_value = {'sub': 'test-user'}
                
                response = lambda_handler(event, lambda_context)
            
            assert response['statusCode'] == 200
            
            body = json.loads(response['body'])
            assert body['leadCount'] == test_case['expected_count']
            
            if test_case['expected_count'] > 0:
                # Verify CSV content matches expectations
                csv_data = base64.b64decode(body['csvData']).decode('utf-8')
                csv_reader = csv.DictReader(io.StringIO(csv_data))
                rows = list(csv_reader)
                
                assert len(rows) == test_case['expected_count']

class TestErrorHandlingIntegration:
    """Test error handling in integration scenarios."""
    
    @pytest.mark.integration
    def test_dynamodb_connection_error(self, lambda_context):
        """Test handling of DynamoDB connection errors."""
        # Create event without setting up DynamoDB
        event = {
            'httpMethod': 'POST',
            'headers': {
                'Authorization': 'Bearer mock-jwt-token'
            },
            'queryStringParameters': {}
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            # This should handle the DynamoDB error gracefully
            response = lambda_handler(event, lambda_context)
        
        # Should return an error response, not crash
        assert response['statusCode'] in [500, 503]  # Server error
    
    @pytest.mark.integration
    def test_authentication_failure(self, dynamodb_table, lambda_context):
        """Test handling of authentication failures."""
        event = {
            'httpMethod': 'POST',
            'headers': {
                'Authorization': 'Bearer invalid-token'
            },
            'queryStringParameters': {}
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.side_effect = Exception("Invalid JWT token")
            
            response = lambda_handler(event, lambda_context)
        
        assert response['statusCode'] == 401
    
    @pytest.mark.integration
    def test_cors_preflight_request(self, lambda_context):
        """Test CORS preflight request handling."""
        cors_event = {
            'httpMethod': 'OPTIONS',
            'headers': {
                'Origin': 'https://example.com'
            }
        }
        
        response = lambda_handler(cors_event, lambda_context)
        
        assert response['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in response['headers']
        assert 'Access-Control-Allow-Methods' in response['headers']