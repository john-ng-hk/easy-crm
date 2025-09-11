"""
Simplified end-to-end test for phone field integration.

Tests the core phone field functionality through the system components.
"""

import pytest
import json
import os
import sys
import boto3
from moto import mock_aws
from unittest.mock import patch, Mock
import csv
import base64
from io import StringIO

# Add lambda paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))


class TestPhoneFieldSimpleE2E:
    """Simplified end-to-end tests for phone field integration."""
    
    @pytest.fixture
    def aws_environment(self):
        """Set up AWS environment for testing."""
        with mock_aws():
            # Create DynamoDB table
            dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
            table = dynamodb.create_table(
                TableName='test-phone-leads',
                KeySchema=[
                    {'AttributeName': 'leadId', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'leadId', 'AttributeType': 'S'},
                    {'AttributeName': 'company', 'AttributeType': 'S'},
                    {'AttributeName': 'email', 'AttributeType': 'S'},
                    {'AttributeName': 'createdAt', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'CompanyIndex',
                        'KeySchema': [
                            {'AttributeName': 'company', 'KeyType': 'HASH'},
                            {'AttributeName': 'createdAt', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    },
                    {
                        'IndexName': 'EmailIndex',
                        'KeySchema': [
                            {'AttributeName': 'email', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            
            yield {
                'dynamodb_table': table
            }
    
    @pytest.fixture
    def lambda_context(self):
        """Mock Lambda context."""
        context = Mock()
        context.aws_request_id = 'phone-simple-e2e-test'
        context.function_name = 'test-phone-function'
        context.memory_limit_in_mb = 256
        context.remaining_time_in_millis = lambda: 30000
        return context
    
    def test_phone_field_deepseek_to_storage_workflow(self, aws_environment, lambda_context):
        """Test phone field processing from DeepSeek to DynamoDB storage."""
        # Test DeepSeek Caller with phone field
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'deepseek-caller'))
        
        with patch.dict(os.environ, {
            'DEEPSEEK_API_KEY': 'test-key',
            'LEADS_TABLE': 'test-phone-leads',
            'AWS_REGION': 'ap-southeast-1'
        }):
            from lambda_function import lambda_handler as deepseek_handler
            
            # Create SQS message with phone data
            sqs_event = {
                'Records': [{
                    'body': json.dumps({
                        'batch_id': 'phone-test-batch',
                        'source_file': 'phone_test.csv',
                        'batch_number': 1,
                        'total_batches': 1,
                        'leads': [
                            {
                                'Name': 'John Smith',
                                'Company': 'Tech Corp',
                                'Email': 'john@tech.com',
                                'Phone': '+1-555-1234',
                                'Title': 'Engineer'
                            },
                            {
                                'Name': 'Jane Doe',
                                'Company': 'Data Inc',
                                'Email': 'jane@data.com',
                                'Phone': '',  # Empty phone
                                'Title': 'Analyst'
                            }
                        ]
                    })
                }]
            }
            
            # Mock DeepSeek response with phone field
            mock_deepseek_response = [
                {
                    'firstName': 'John',
                    'lastName': 'Smith',
                    'title': 'Engineer',
                    'company': 'Tech Corp',
                    'email': 'john@tech.com',
                    'phone': '+1-555-1234',
                    'remarks': 'N/A'
                },
                {
                    'firstName': 'Jane',
                    'lastName': 'Doe',
                    'title': 'Analyst',
                    'company': 'Data Inc',
                    'email': 'jane@data.com',
                    'phone': 'N/A',
                    'remarks': 'N/A'
                }
            ]
            
            with patch('requests.post') as mock_post:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    'choices': [{
                        'message': {
                            'content': json.dumps(mock_deepseek_response)
                        }
                    }]
                }
                mock_post.return_value = mock_response
                
                deepseek_response = deepseek_handler(sqs_event, lambda_context)
            
            # Verify DeepSeek processing succeeded
            assert deepseek_response['statusCode'] == 200
            response_body = deepseek_response['body']
            assert response_body['batch_id'] == 'phone-test-batch'
            assert response_body['stored_leads'] == 2
    
    def test_phone_field_retrieval_and_filtering(self, aws_environment, lambda_context):
        """Test phone field retrieval and filtering through Lead Reader."""
        # First, populate test data with phone fields
        dynamodb_table = aws_environment['dynamodb_table']
        
        test_leads = [
            {
                'leadId': 'phone-lead-1',
                'firstName': 'Alice',
                'lastName': 'Johnson',
                'title': 'Manager',
                'company': 'Phone Corp',
                'email': 'alice@phonecorp.com',
                'phone': '+1-555-1111',
                'remarks': 'Test lead 1',
                'sourceFile': 'phone-test.csv',
                'createdAt': '2024-01-15T10:00:00Z',
                'updatedAt': '2024-01-15T10:00:00Z'
            },
            {
                'leadId': 'phone-lead-2',
                'firstName': 'Bob',
                'lastName': 'Wilson',
                'title': 'Developer',
                'company': 'Tech Inc',
                'email': 'bob@tech.com',
                'phone': 'N/A',
                'remarks': 'Test lead 2',
                'sourceFile': 'phone-test.csv',
                'createdAt': '2024-01-16T10:00:00Z',
                'updatedAt': '2024-01-16T10:00:00Z'
            }
        ]
        
        # Insert test data
        with dynamodb_table.batch_writer() as batch:
            for lead in test_leads:
                batch.put_item(Item=lead)
        
        # Test Lead Reader with phone field
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        from lambda_function import lambda_handler as reader_handler
        
        # Test 1: Retrieve all leads (should include phone field)
        reader_event = {
            'httpMethod': 'GET',
            'headers': {'Authorization': 'Bearer test-token'},
            'queryStringParameters': {}
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            reader_response = reader_handler(reader_event, lambda_context)
        
        assert reader_response['statusCode'] == 200
        reader_body = json.loads(reader_response['body'])
        
        # Verify phone field is included in all leads
        assert len(reader_body['leads']) == 2
        for lead in reader_body['leads']:
            assert 'phone' in lead
            assert lead['phone'] is not None
        
        # Verify specific phone values
        phone_values = [lead['phone'] for lead in reader_body['leads']]
        assert '+1-555-1111' in phone_values
        assert 'N/A' in phone_values
        
        # Test 2: Filter by phone number
        filter_event = {
            'httpMethod': 'GET',
            'headers': {'Authorization': 'Bearer test-token'},
            'queryStringParameters': {
                'filter_phone': '+1-555-1111'
            }
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            filter_response = reader_handler(filter_event, lambda_context)
        
        assert filter_response['statusCode'] == 200
        filter_body = json.loads(filter_response['body'])
        
        # Should find exactly 1 lead with the specific phone number
        assert len(filter_body['leads']) == 1
        assert filter_body['leads'][0]['phone'] == '+1-555-1111'
        assert filter_body['leads'][0]['firstName'] == 'Alice'
    
    def test_phone_field_csv_export(self, aws_environment, lambda_context):
        """Test phone field inclusion in CSV export."""
        # Populate test data
        dynamodb_table = aws_environment['dynamodb_table']
        
        test_leads = [
            {
                'leadId': 'export-phone-1',
                'firstName': 'Export',
                'lastName': 'Test1',
                'title': 'Tester',
                'company': 'Export Corp',
                'email': 'export1@test.com',
                'phone': '+1-555-EXPORT',
                'remarks': 'Export test lead 1',
                'sourceFile': 'export-test.csv',
                'createdAt': '2024-01-15T10:00:00Z',
                'updatedAt': '2024-01-15T10:00:00Z'
            },
            {
                'leadId': 'export-phone-2',
                'firstName': 'Export',
                'lastName': 'Test2',
                'title': 'Analyst',
                'company': 'Export Inc',
                'email': 'export2@test.com',
                'phone': 'N/A',
                'remarks': 'Export test lead 2',
                'sourceFile': 'export-test.csv',
                'createdAt': '2024-01-16T10:00:00Z',
                'updatedAt': '2024-01-16T10:00:00Z'
            }
        ]
        
        with dynamodb_table.batch_writer() as batch:
            for lead in test_leads:
                batch.put_item(Item=lead)
        
        # Test CSV export
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-exporter'))
        from lambda_function import lambda_handler as exporter_handler
        
        export_event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer test-token'},
            'queryStringParameters': {}
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            export_response = exporter_handler(export_event, lambda_context)
        
        assert export_response['statusCode'] == 200
        export_body = json.loads(export_response['body'])
        
        # Verify export includes phone field
        assert export_body['leadCount'] == 2
        assert export_body['csvData'] is not None
        
        # Decode and verify CSV content
        csv_data = base64.b64decode(export_body['csvData']).decode('utf-8')
        csv_reader = csv.DictReader(StringIO(csv_data))
        rows = list(csv_reader)
        
        # Verify phone column exists and has correct values
        assert len(rows) == 2
        assert 'phone' in rows[0]
        assert 'phone' in rows[1]
        
        phone_values = [row['phone'] for row in rows]
        assert '+1-555-EXPORT' in phone_values
        assert 'N/A' in phone_values
    
    def test_phone_field_chatbot_integration(self, aws_environment, lambda_context):
        """Test phone field handling in chatbot queries."""
        # Populate test data
        dynamodb_table = aws_environment['dynamodb_table']
        
        test_leads = [
            {
                'leadId': 'chat-phone-1',
                'firstName': 'Chat',
                'lastName': 'Test1',
                'title': 'Manager',
                'company': 'Chat Corp',
                'email': 'chat1@test.com',
                'phone': '+1-555-CHAT1',
                'remarks': 'Chat test lead 1',
                'sourceFile': 'chat-test.csv',
                'createdAt': '2024-01-15T10:00:00Z',
                'updatedAt': '2024-01-15T10:00:00Z'
            },
            {
                'leadId': 'chat-phone-2',
                'firstName': 'Chat',
                'lastName': 'Test2',
                'title': 'Developer',
                'company': 'Chat Inc',
                'email': 'chat2@test.com',
                'phone': 'N/A',
                'remarks': 'Chat test lead 2',
                'sourceFile': 'chat-test.csv',
                'createdAt': '2024-01-16T10:00:00Z',
                'updatedAt': '2024-01-16T10:00:00Z'
            }
        ]
        
        with dynamodb_table.batch_writer() as batch:
            for lead in test_leads:
                batch.put_item(Item=lead)
        
        # Test chatbot with phone-related queries
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'chatbot'))
        from lambda_function import lambda_handler as chatbot_handler
        
        # Test query for leads with phone numbers
        phone_query_event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer test-token'},
            'body': json.dumps({
                'query': 'show me leads with phone numbers'
            })
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            with patch('lambda_function.generate_dynamodb_query') as mock_generate:
                # Mock DeepSeek to understand phone-related query
                mock_generate.return_value = {
                    'type': 'scan',
                    'filters': {},
                    'limit': 50
                }
                
                phone_response = chatbot_handler(phone_query_event, lambda_context)
        
        assert phone_response['statusCode'] == 200
        phone_body = json.loads(phone_response['body'])
        
        assert phone_body['type'] == 'success'
        assert phone_body['resultCount'] == 2  # Both leads should be returned
        
        # Verify phone field is mentioned in response
        response_text = phone_body['response'].lower()
        assert 'phone' in response_text or 'chat1' in response_text or 'n/a' in response_text
    
    def test_phone_field_validation_integration(self, aws_environment, lambda_context):
        """Test phone field validation throughout the system."""
        # Test phone validation in shared utilities
        from validation import LeadValidator
        
        # Test valid phone
        valid_lead_with_phone = {
            'firstName': 'Test',
            'lastName': 'User',
            'company': 'Test Corp',
            'email': 'test@test.com',
            'phone': '+1-555-123-4567',
            'title': 'Tester',
            'remarks': 'N/A'
        }
        
        is_valid, errors = LeadValidator.validate_lead_data(valid_lead_with_phone)
        assert is_valid
        assert len(errors) == 0
        
        # Test N/A phone (should be valid)
        na_phone_lead = {
            'firstName': 'Test',
            'lastName': 'User',
            'company': 'Test Corp',
            'email': 'test@test.com',
            'phone': 'N/A',
            'title': 'Tester',
            'remarks': 'N/A'
        }
        
        is_valid, errors = LeadValidator.validate_lead_data(na_phone_lead)
        assert is_valid
        assert len(errors) == 0
        
        # Test invalid phone format
        invalid_phone_lead = {
            'firstName': 'Test',
            'lastName': 'User',
            'company': 'Test Corp',
            'email': 'test@test.com',
            'phone': 'invalid-phone-format',
            'title': 'Tester',
            'remarks': 'N/A'
        }
        
        is_valid, errors = LeadValidator.validate_lead_data(invalid_phone_lead)
        assert not is_valid
        assert any('phone' in error.lower() for error in errors)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])