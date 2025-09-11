"""
End-to-end test for phone field integration throughout the complete workflow.

Tests that phone field is properly handled from file upload through processing,
storage, retrieval, filtering, export, and chatbot queries.
"""

import pytest
import json
import os
import sys
import time
import boto3
from moto import mock_aws
from unittest.mock import patch, Mock
import pandas as pd
from io import BytesIO, StringIO
import csv
import base64

# Add lambda paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))


class TestPhoneFieldEndToEnd:
    """End-to-end tests for phone field integration."""
    
    @pytest.fixture
    def aws_environment(self):
        """Set up complete AWS environment for testing."""
        with mock_aws():
            # Create S3 client and buckets
            s3_client = boto3.client('s3', region_name='ap-southeast-1')
            
            upload_bucket = 'test-phone-upload-bucket'
            s3_client.create_bucket(
                Bucket=upload_bucket,
                CreateBucketConfiguration={'LocationConstraint': 'ap-southeast-1'}
            )
            
            # Create DynamoDB table with phone field support
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
                    {'AttributeName': 'createdAt', 'AttributeType': 'S'},
                    {'AttributeName': 'phone', 'AttributeType': 'S'}
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
                    },
                    {
                        'IndexName': 'PhoneIndex',
                        'KeySchema': [
                            {'AttributeName': 'phone', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            
            yield {
                's3_client': s3_client,
                'upload_bucket': upload_bucket,
                'dynamodb_table': table
            }
    
    @pytest.fixture
    def test_csv_with_phone_data(self):
        """Create test CSV data with phone field variations."""
        return """Name,Job Title,Company,Email Address,Phone Number,Notes
John Smith,Software Engineer,Tech Solutions Inc,john.smith@techsolutions.com,+1-555-0123,Interested in cloud migration
Sarah Johnson,Marketing Manager,Digital Marketing Co,sarah.j@digitalmarketing.com,(555) 456-7890,Looking for automation tools
Michael Chen,CTO,StartupXYZ,michael.chen@startupxyz.com,555.789.0123,Evaluating new technologies
Lisa Williams,Product Manager,Innovation Corp,lisa.w@innovation.com,+1 555 234 5678,Needs scalable solutions
David Brown,Senior Developer,Tech Solutions Inc,david.brown@techsolutions.com,,Python and AWS expert
Emma Davis,UX Designer,Creative Studio,emma@creative.com,1-800-CALL-NOW,Design thinking specialist"""
    
    @pytest.fixture
    def lambda_context(self):
        """Mock Lambda context."""
        context = Mock()
        context.aws_request_id = 'phone-e2e-test-request'
        context.function_name = 'test-phone-function'
        context.memory_limit_in_mb = 256
        context.remaining_time_in_millis = lambda: 30000
        return context
    
    def test_complete_phone_field_workflow(self, aws_environment, test_csv_with_phone_data, lambda_context):
        """Test complete workflow with phone field processing."""
        s3_client = aws_environment['s3_client']
        upload_bucket = aws_environment['upload_bucket']
        
        # Step 1: Upload CSV file with phone data
        file_key = 'uploads/phone-test/phone_leads.csv'
        s3_client.put_object(
            Bucket=upload_bucket,
            Key=file_key,
            Body=test_csv_with_phone_data.encode('utf-8'),
            ContentType='text/csv'
        )
        
        # Step 2: Process file with DeepSeek Caller (includes phone field)
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
                        'batch_id': 'phone-batch-1',
                        'source_file': 'phone_leads.csv',
                        'batch_number': 1,
                        'total_batches': 1,
                        'leads': [
                            {
                                'Name': 'John Smith',
                                'Job Title': 'Software Engineer',
                                'Company': 'Tech Solutions Inc',
                                'Email Address': 'john.smith@techsolutions.com',
                                'Phone Number': '+1-555-0123',
                                'Notes': 'Interested in cloud migration'
                            },
                            {
                                'Name': 'Sarah Johnson',
                                'Job Title': 'Marketing Manager',
                                'Company': 'Digital Marketing Co',
                                'Email Address': 'sarah.j@digitalmarketing.com',
                                'Phone Number': '(555) 456-7890',
                                'Notes': 'Looking for automation tools'
                            },
                            {
                                'Name': 'David Brown',
                                'Job Title': 'Senior Developer',
                                'Company': 'Tech Solutions Inc',
                                'Email Address': 'david.brown@techsolutions.com',
                                'Phone Number': '',
                                'Notes': 'Python and AWS expert'
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
                    'title': 'Software Engineer',
                    'company': 'Tech Solutions Inc',
                    'email': 'john.smith@techsolutions.com',
                    'phone': '+1-555-0123',
                    'remarks': 'Interested in cloud migration'
                },
                {
                    'firstName': 'Sarah',
                    'lastName': 'Johnson',
                    'title': 'Marketing Manager',
                    'company': 'Digital Marketing Co',
                    'email': 'sarah.j@digitalmarketing.com',
                    'phone': '+1-555-456-7890',
                    'remarks': 'Looking for automation tools'
                },
                {
                    'firstName': 'David',
                    'lastName': 'Brown',
                    'title': 'Senior Developer',
                    'company': 'Tech Solutions Inc',
                    'email': 'david.brown@techsolutions.com',
                    'phone': 'N/A',
                    'remarks': 'Python and AWS expert'
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
            
            assert deepseek_response['statusCode'] == 200
            response_body = deepseek_response['body']
            assert response_body['batch_id'] == 'phone-batch-1'
            assert response_body['stored_leads'] == 3
        
        # Step 3: Test lead retrieval with phone field
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        
        from lambda_function import lambda_handler as reader_handler
        
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
        
        # Verify phone field is included in response
        assert len(reader_body['leads']) == 3
        
        # Check phone field values
        phone_values = [lead['phone'] for lead in reader_body['leads']]
        assert '+1-555-0123' in phone_values
        assert '+1-555-456-7890' in phone_values
        assert 'N/A' in phone_values
        
        # Verify phone field is in all lead objects
        for lead in reader_body['leads']:
            assert 'phone' in lead
            assert lead['phone'] is not None
    
    def test_phone_field_filtering_and_sorting(self, aws_environment, lambda_context):
        """Test phone field filtering and sorting functionality."""
        # First, populate test data with various phone formats
        dynamodb_table = aws_environment['dynamodb_table']
        
        test_leads = [
            {
                'leadId': 'phone-filter-1',
                'firstName': 'Alice',
                'lastName': 'Johnson',
                'title': 'Manager',
                'company': 'Phone Corp',
                'email': 'alice@phonecorp.com',
                'phone': '+1-555-1111',
                'remarks': 'Test lead 1',
                'sourceFile': 'phone-filter-test.csv',
                'createdAt': '2024-01-15T10:00:00Z',
                'updatedAt': '2024-01-15T10:00:00Z'
            },
            {
                'leadId': 'phone-filter-2',
                'firstName': 'Bob',
                'lastName': 'Wilson',
                'title': 'Developer',
                'company': 'Tech Inc',
                'email': 'bob@tech.com',
                'phone': '+1-555-2222',
                'remarks': 'Test lead 2',
                'sourceFile': 'phone-filter-test.csv',
                'createdAt': '2024-01-16T10:00:00Z',
                'updatedAt': '2024-01-16T10:00:00Z'
            },
            {
                'leadId': 'phone-filter-3',
                'firstName': 'Carol',
                'lastName': 'Davis',
                'title': 'Analyst',
                'company': 'Data Corp',
                'email': 'carol@data.com',
                'phone': 'N/A',
                'remarks': 'Test lead 3',
                'sourceFile': 'phone-filter-test.csv',
                'createdAt': '2024-01-17T10:00:00Z',
                'updatedAt': '2024-01-17T10:00:00Z'
            }
        ]
        
        # Insert test data
        with dynamodb_table.batch_writer() as batch:
            for lead in test_leads:
                batch.put_item(Item=lead)
        
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        from lambda_function import lambda_handler as reader_handler
        
        # Test 1: Filter by phone number
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
        
        # Should find 1 lead with specific phone number
        assert len(filter_body['leads']) == 1
        assert filter_body['leads'][0]['phone'] == '+1-555-1111'
        assert filter_body['leads'][0]['firstName'] == 'Alice'
        
        # Test 2: Filter by partial phone number
        partial_filter_event = {
            'httpMethod': 'GET',
            'headers': {'Authorization': 'Bearer test-token'},
            'queryStringParameters': {
                'filter_phone': '555-'
            }
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            partial_response = reader_handler(partial_filter_event, lambda_context)
        
        assert partial_response['statusCode'] == 200
        partial_body = json.loads(partial_response['body'])
        
        # Should find 2 leads with phone numbers containing '555-'
        assert len(partial_body['leads']) == 2
        
        # Test 3: Sort by phone field
        sort_event = {
            'httpMethod': 'GET',
            'headers': {'Authorization': 'Bearer test-token'},
            'queryStringParameters': {
                'sortBy': 'phone',
                'sortOrder': 'asc'
            }
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            sort_response = reader_handler(sort_event, lambda_context)
        
        assert sort_response['statusCode'] == 200
        sort_body = json.loads(sort_response['body'])
        
        # Verify sorting (N/A should come first, then phone numbers)
        assert len(sort_body['leads']) == 3
        phone_values = [lead['phone'] for lead in sort_body['leads']]
        
        # Check that sorting worked (N/A first, then numbers)
        assert phone_values[0] == 'N/A'
        assert '+1-555-' in phone_values[1]
        assert '+1-555-' in phone_values[2]
    
    def test_phone_field_in_csv_export(self, aws_environment, lambda_context):
        """Test that phone field is included in CSV export."""
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
    
    def test_phone_field_in_chatbot_queries(self, aws_environment, lambda_context):
        """Test phone field handling in chatbot natural language queries."""
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
        
        # Test 1: Query for leads with phone numbers
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
                    'type': 'filter',
                    'filters': {'phone': {'not_equals': 'N/A'}},
                    'limit': 50
                }
                
                phone_response = chatbot_handler(phone_query_event, lambda_context)
        
        assert phone_response['statusCode'] == 200
        phone_body = json.loads(phone_response['body'])
        
        assert phone_body['type'] == 'success'
        assert phone_body['resultCount'] == 1  # Only one lead has a real phone number
        
        # Test 2: Query for specific phone number
        specific_phone_event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer test-token'},
            'body': json.dumps({
                'query': 'find lead with phone number 555-CHAT1'
            })
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            with patch('lambda_function.generate_dynamodb_query') as mock_generate:
                mock_generate.return_value = {
                    'type': 'filter',
                    'filters': {'phone': '+1-555-CHAT1'},
                    'limit': 50
                }
                
                specific_response = chatbot_handler(specific_phone_event, lambda_context)
        
        assert specific_response['statusCode'] == 200
        specific_body = json.loads(specific_response['body'])
        
        assert specific_body['type'] == 'success'
        assert specific_body['resultCount'] == 1
        
        # Verify phone field is included in chatbot response
        assert 'phone' in specific_body['response'].lower() or '+1-555-CHAT1' in specific_body['response']
    
    def test_phone_field_validation_throughout_workflow(self, aws_environment, lambda_context):
        """Test phone field validation at various points in the workflow."""
        # Test various phone number formats
        phone_test_cases = [
            {
                'input': '+1-555-123-4567',
                'expected': '+1-555-123-4567',
                'should_pass': True
            },
            {
                'input': '(555) 123-4567',
                'expected': '+1-555-123-4567',  # DeepSeek should standardize
                'should_pass': True
            },
            {
                'input': '555.123.4567',
                'expected': '+1-555-123-4567',  # DeepSeek should standardize
                'should_pass': True
            },
            {
                'input': '',
                'expected': 'N/A',
                'should_pass': True
            },
            {
                'input': 'invalid-phone',
                'expected': 'N/A',  # DeepSeek should handle invalid formats
                'should_pass': True
            }
        ]
        
        s3_client = aws_environment['s3_client']
        upload_bucket = aws_environment['upload_bucket']
        
        for i, test_case in enumerate(phone_test_cases):
            # Create CSV with specific phone format
            test_csv = f"""Name,Company,Email,Phone
Test User {i},Test Corp,test{i}@test.com,{test_case['input']}"""
            
            file_key = f'uploads/phone-validation-{i}.csv'
            s3_client.put_object(
                Bucket=upload_bucket,
                Key=file_key,
                Body=test_csv.encode('utf-8'),
                ContentType='text/csv'
            )
            
            # Process with DeepSeek Caller
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'deepseek-caller'))
            
            with patch.dict(os.environ, {
                'DEEPSEEK_API_KEY': 'test-key',
                'LEADS_TABLE': 'test-phone-leads',
                'AWS_REGION': 'ap-southeast-1'
            }):
                from lambda_function import lambda_handler as deepseek_handler
                
                sqs_event = {
                    'Records': [{
                        'body': json.dumps({
                            'batch_id': f'phone-validation-{i}',
                            'source_file': f'phone-validation-{i}.csv',
                            'batch_number': 1,
                            'total_batches': 1,
                            'leads': [{
                                'Name': f'Test User {i}',
                                'Company': 'Test Corp',
                                'Email': f'test{i}@test.com',
                                'Phone': test_case['input']
                            }]
                        })
                    }]
                }
                
                # Mock DeepSeek response with expected phone format
                mock_deepseek_response = [{
                    'firstName': 'Test',
                    'lastName': f'User {i}',
                    'title': 'N/A',
                    'company': 'Test Corp',
                    'email': f'test{i}@test.com',
                    'phone': test_case['expected'],
                    'remarks': 'N/A'
                }]
                
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
                    
                    response = deepseek_handler(sqs_event, lambda_context)
                
                if test_case['should_pass']:
                    assert response['statusCode'] == 200
                    assert response['body']['stored_leads'] == 1
                else:
                    # Should handle gracefully even with invalid data
                    assert response['statusCode'] in [200, 422]
    
    def test_phone_field_regression_testing(self, aws_environment, lambda_context):
        """Test that existing functionality still works with phone field integration."""
        # Test that all existing functionality works with phone field present
        
        # 1. Test that leads without phone field still work
        dynamodb_table = aws_environment['dynamodb_table']
        
        legacy_lead = {
            'leadId': 'legacy-lead-1',
            'firstName': 'Legacy',
            'lastName': 'User',
            'title': 'Manager',
            'company': 'Legacy Corp',
            'email': 'legacy@test.com',
            'remarks': 'Legacy lead without phone field',
            'sourceFile': 'legacy-test.csv',
            'createdAt': '2024-01-15T10:00:00Z',
            'updatedAt': '2024-01-15T10:00:00Z'
            # Note: No phone field
        }
        
        dynamodb_table.put_item(Item=legacy_lead)
        
        # Test lead retrieval still works
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        from lambda_function import lambda_handler as reader_handler
        
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
        
        # Should handle leads without phone field gracefully
        assert len(reader_body['leads']) >= 1
        
        # Find the legacy lead
        legacy_retrieved = None
        for lead in reader_body['leads']:
            if lead['leadId'] == 'legacy-lead-1':
                legacy_retrieved = lead
                break
        
        assert legacy_retrieved is not None
        # Should have phone field set to N/A or empty string
        assert 'phone' in legacy_retrieved
        assert legacy_retrieved['phone'] in ['N/A', '', None]
        
        # 2. Test existing filters still work
        filter_event = {
            'httpMethod': 'GET',
            'headers': {'Authorization': 'Bearer test-token'},
            'queryStringParameters': {
                'filter_company': 'Legacy Corp'
            }
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            filter_response = reader_handler(filter_event, lambda_context)
        
        assert filter_response['statusCode'] == 200
        filter_body = json.loads(filter_response['body'])
        
        # Should find the legacy lead by company filter
        assert len(filter_body['leads']) == 1
        assert filter_body['leads'][0]['company'] == 'Legacy Corp'


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])