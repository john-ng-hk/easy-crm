"""
Comprehensive end-to-end tests for duplicate lead handling functionality.

Tests the complete workflow: file upload → duplicate detection → lead storage → frontend display
Covers all requirements from the duplicate lead handling specification.
"""

import pytest
import json
import os
import sys
import time
import boto3
from moto import mock_aws
from unittest.mock import patch, Mock, MagicMock
import pandas as pd
from io import BytesIO, StringIO
import csv
import base64
from datetime import datetime, timezone
import uuid

# Add lambda paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'file-upload'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-splitter'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'deepseek-caller'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-exporter'))


class TestDuplicateHandlingE2E:
    """Comprehensive end-to-end tests for duplicate lead handling."""
    
    @pytest.fixture
    def aws_environment(self):
        """Set up complete AWS environment for duplicate handling testing."""
        with mock_aws():
            # Create S3 client and buckets
            s3_client = boto3.client('s3', region_name='ap-southeast-1')
            sqs_client = boto3.client('sqs', region_name='ap-southeast-1')
            
            upload_bucket = 'test-upload-bucket'
            s3_client.create_bucket(
                Bucket=upload_bucket,
                CreateBucketConfiguration={'LocationConstraint': 'ap-southeast-1'}
            )
            
            # Create SQS queue for batch processing
            queue_response = sqs_client.create_queue(
                QueueName='test-lead-processing-queue',
                Attributes={
                    'VisibilityTimeoutSeconds': '300',
                    'MessageRetentionPeriod': '1209600'
                }
            )
            queue_url = queue_response['QueueUrl']
            
            # Create DynamoDB table with EmailIndex GSI
            dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
            table = dynamodb.create_table(
                TableName='test-leads',
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
                        'Projection': {'ProjectionType': 'ALL'},
                        'BillingMode': 'PAY_PER_REQUEST'
                    },
                    {
                        'IndexName': 'EmailIndex',
                        'KeySchema': [
                            {'AttributeName': 'email', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'BillingMode': 'PAY_PER_REQUEST'
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            
            yield {
                's3_client': s3_client,
                'sqs_client': sqs_client,
                'upload_bucket': upload_bucket,
                'queue_url': queue_url,
                'dynamodb_table': table
            }
    
    @pytest.fixture
    def lambda_context(self):
        """Mock Lambda context."""
        context = Mock()
        context.aws_request_id = 'duplicate-e2e-test'
        context.function_name = 'test-function'
        context.memory_limit_in_mb = 512
        context.remaining_time_in_millis = lambda: 30000
        return context
    
    @pytest.fixture
    def initial_leads_data(self):
        """Initial leads data for testing duplicates."""
        return """Name,Email,Company,Title,Phone,Notes
John Smith,john.smith@techcorp.com,TechCorp Inc,Software Engineer,+1-555-0100,Initial lead data
Jane Doe,jane.doe@designco.com,DesignCo Ltd,UX Designer,+1-555-0101,Creative professional
Bob Wilson,bob.wilson@datacorp.com,DataCorp LLC,Data Analyst,+1-555-0102,Analytics expert"""
    
    @pytest.fixture
    def duplicate_leads_data(self):
        """Duplicate leads data with updated information."""
        return """Full Name,Email Address,Organization,Job Title,Phone Number,Additional Info
John Smith,john.smith@techcorp.com,TechCorp Inc,Senior Software Engineer,+1-555-0100,Updated: Now senior engineer
Jane Doe,JANE.DOE@DESIGNCO.COM,DesignCo Ltd,Lead UX Designer,+1-555-0101,Updated: Promoted to lead
Alice Johnson,alice.johnson@newcorp.com,NewCorp Inc,Product Manager,+1-555-0103,New lead - not a duplicate
Bob Wilson,  bob.wilson@datacorp.com  ,DataCorp LLC,Senior Data Analyst,+1-555-0102,Updated: Promoted to senior"""
    
    def test_complete_duplicate_handling_workflow(self, aws_environment, lambda_context, 
                                                initial_leads_data, duplicate_leads_data):
        """
        Test complete workflow: initial upload → duplicate upload → verification.
        Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
        """
        s3_client = aws_environment['s3_client']
        sqs_client = aws_environment['sqs_client']
        upload_bucket = aws_environment['upload_bucket']
        queue_url = aws_environment['queue_url']
        
        # Step 1: Upload initial leads file
        initial_file_key = 'uploads/initial_leads.csv'
        s3_client.put_object(
            Bucket=upload_bucket,
            Key=initial_file_key,
            Body=initial_leads_data.encode('utf-8'),
            ContentType='text/csv'
        )
        
        # Step 2: Process initial file with lead splitter
        with patch.dict(os.environ, {
            'SQS_QUEUE_URL': queue_url,
            'BATCH_SIZE': '10'
        }):
            from lambda_function import lambda_handler as splitter_handler
            
            initial_s3_event = {
                'Records': [{
                    's3': {
                        'bucket': {'name': upload_bucket},
                        'object': {'key': initial_file_key}
                    }
                }]
            }
            
            with patch('lambda_function.s3_client', s3_client):
                with patch('lambda_function.sqs_client', sqs_client):
                    splitter_response = splitter_handler(initial_s3_event, lambda_context)
            
            assert splitter_response['statusCode'] == 200
        
        # Step 3: Process initial batch with DeepSeek caller
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'deepseek-caller'))
        
        with patch.dict(os.environ, {
            'DEEPSEEK_API_KEY': 'test-key',
            'DYNAMODB_TABLE_NAME': 'test-leads'
        }):
            from lambda_function import lambda_handler as deepseek_handler
            
            # Get message from SQS
            messages = sqs_client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1)
            assert 'Messages' in messages
            
            message = messages['Messages'][0]
            batch_data = json.loads(message['Body'])
            
            # Mock DeepSeek API response for initial data
            mock_initial_response = [
                {
                    'firstName': 'John',
                    'lastName': 'Smith',
                    'title': 'Software Engineer',
                    'company': 'TechCorp Inc',
                    'email': 'john.smith@techcorp.com',
                    'phone': '+1-555-0100',
                    'remarks': 'Initial lead data'
                },
                {
                    'firstName': 'Jane',
                    'lastName': 'Doe',
                    'title': 'UX Designer',
                    'company': 'DesignCo Ltd',
                    'email': 'jane.doe@designco.com',
                    'phone': '+1-555-0101',
                    'remarks': 'Creative professional'
                },
                {
                    'firstName': 'Bob',
                    'lastName': 'Wilson',
                    'title': 'Data Analyst',
                    'company': 'DataCorp LLC',
                    'email': 'bob.wilson@datacorp.com',
                    'phone': '+1-555-0102',
                    'remarks': 'Analytics expert'
                }
            ]
            
            sqs_event = {
                'Records': [{
                    'body': message['Body'],
                    'receiptHandle': message['ReceiptHandle']
                }]
            }
            
            with patch('requests.post') as mock_post:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    'choices': [{
                        'message': {
                            'content': json.dumps(mock_initial_response)
                        }
                    }]
                }
                mock_post.return_value = mock_response
                
                deepseek_response = deepseek_handler(sqs_event, lambda_context)
            
            assert deepseek_response['statusCode'] == 200
        
        # Step 4: Verify initial leads are stored
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        
        from lambda_function import lambda_handler as reader_handler
        
        reader_event = {
            'httpMethod': 'GET',
            'headers': {'Authorization': 'Bearer test-token'},
            'queryStringParameters': {}
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            initial_reader_response = reader_handler(reader_event, lambda_context)
        
        assert initial_reader_response['statusCode'] == 200
        initial_body = json.loads(initial_reader_response['body'])
        
        # Should have 3 initial leads
        assert len(initial_body['leads']) == 3
        assert initial_body['pagination']['totalCount'] == 3
        
        # Store original lead IDs and timestamps for comparison
        original_leads = {lead['email']: {
            'leadId': lead['leadId'],
            'createdAt': lead['createdAt'],
            'title': lead['title']
        } for lead in initial_body['leads']}
        
        # Step 5: Upload duplicate leads file
        duplicate_file_key = 'uploads/duplicate_leads.csv'
        s3_client.put_object(
            Bucket=duplicate_file_key,
            Key=duplicate_file_key,
            Body=duplicate_leads_data.encode('utf-8'),
            ContentType='text/csv'
        )
        
        # Step 6: Process duplicate file with lead splitter
        duplicate_s3_event = {
            'Records': [{
                's3': {
                    'bucket': {'name': upload_bucket},
                    'object': {'key': duplicate_file_key}
                }
            }]
        }
        
        with patch('lambda_function.s3_client', s3_client):
            with patch('lambda_function.sqs_client', sqs_client):
                duplicate_splitter_response = splitter_handler(duplicate_s3_event, lambda_context)
        
        assert duplicate_splitter_response['statusCode'] == 200
        
        # Step 7: Process duplicate batch with DeepSeek caller
        # Get new message from SQS
        duplicate_messages = sqs_client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1)
        assert 'Messages' in duplicate_messages
        
        duplicate_message = duplicate_messages['Messages'][0]
        
        # Mock DeepSeek API response for duplicate data (with updates)
        mock_duplicate_response = [
            {
                'firstName': 'John',
                'lastName': 'Smith',
                'title': 'Senior Software Engineer',  # Updated title
                'company': 'TechCorp Inc',
                'email': 'john.smith@techcorp.com',
                'phone': '+1-555-0100',
                'remarks': 'Updated: Now senior engineer'  # Updated remarks
            },
            {
                'firstName': 'Jane',
                'lastName': 'Doe',
                'title': 'Lead UX Designer',  # Updated title
                'company': 'DesignCo Ltd',
                'email': 'jane.doe@designco.com',  # Normalized from uppercase
                'phone': '+1-555-0101',
                'remarks': 'Updated: Promoted to lead'  # Updated remarks
            },
            {
                'firstName': 'Alice',
                'lastName': 'Johnson',
                'title': 'Product Manager',
                'company': 'NewCorp Inc',
                'email': 'alice.johnson@newcorp.com',  # New lead
                'phone': '+1-555-0103',
                'remarks': 'New lead - not a duplicate'
            },
            {
                'firstName': 'Bob',
                'lastName': 'Wilson',
                'title': 'Senior Data Analyst',  # Updated title
                'company': 'DataCorp LLC',
                'email': 'bob.wilson@datacorp.com',  # Normalized from whitespace
                'phone': '+1-555-0102',
                'remarks': 'Updated: Promoted to senior'  # Updated remarks
            }
        ]
        
        duplicate_sqs_event = {
            'Records': [{
                'body': duplicate_message['Body'],
                'receiptHandle': duplicate_message['ReceiptHandle']
            }]
        }
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'choices': [{
                    'message': {
                        'content': json.dumps(mock_duplicate_response)
                    }
                }]
            }
            mock_post.return_value = mock_response
            
            duplicate_deepseek_response = deepseek_handler(duplicate_sqs_event, lambda_context)
        
        assert duplicate_deepseek_response['statusCode'] == 200
        
        # Step 8: Verify duplicate handling results
        final_reader_response = reader_handler(reader_event, lambda_context)
        assert final_reader_response['statusCode'] == 200
        final_body = json.loads(final_reader_response['body'])
        
        # Should have 4 leads total (3 updated + 1 new)
        assert len(final_body['leads']) == 4
        assert final_body['pagination']['totalCount'] == 4
        
        # Verify duplicate handling behavior
        final_leads = {lead['email']: lead for lead in final_body['leads']}
        
        # Check John Smith (duplicate - should be updated)
        john_lead = final_leads['john.smith@techcorp.com']
        assert john_lead['leadId'] == original_leads['john.smith@techcorp.com']['leadId']  # Same ID
        assert john_lead['createdAt'] == original_leads['john.smith@techcorp.com']['createdAt']  # Same createdAt
        assert john_lead['title'] == 'Senior Software Engineer'  # Updated title
        assert john_lead['updatedAt'] != john_lead['createdAt']  # Updated timestamp
        assert john_lead['sourceFile'] == 'duplicate_leads.csv'  # Updated source file
        
        # Check Jane Doe (duplicate with case difference - should be updated)
        jane_lead = final_leads['jane.doe@designco.com']
        assert jane_lead['leadId'] == original_leads['jane.doe@designco.com']['leadId']  # Same ID
        assert jane_lead['title'] == 'Lead UX Designer'  # Updated title
        
        # Check Bob Wilson (duplicate with whitespace - should be updated)
        bob_lead = final_leads['bob.wilson@datacorp.com']
        assert bob_lead['leadId'] == original_leads['bob.wilson@datacorp.com']['leadId']  # Same ID
        assert bob_lead['title'] == 'Senior Data Analyst'  # Updated title
        
        # Check Alice Johnson (new lead - should be created)
        alice_lead = final_leads['alice.johnson@newcorp.com']
        assert alice_lead['leadId'] not in [lead['leadId'] for lead in original_leads.values()]  # New ID
        assert alice_lead['title'] == 'Product Manager'
        assert alice_lead['sourceFile'] == 'duplicate_leads.csv'
    
    def test_csv_export_with_deduplicated_data(self, aws_environment, lambda_context):
        """
        Test CSV export functionality with deduplicated data.
        Requirements: 6.3
        """
        # Pre-populate table with deduplicated data
        dynamodb_table = aws_environment['dynamodb_table']
        
        test_leads = [
            {
                'leadId': 'export-test-1',
                'firstName': 'John',
                'lastName': 'Smith',
                'title': 'Senior Software Engineer',
                'company': 'TechCorp Inc',
                'email': 'john.smith@techcorp.com',
                'phone': '+1-555-0100',
                'remarks': 'Updated lead after duplicate handling',
                'sourceFile': 'latest_upload.csv',
                'createdAt': '2024-01-15T10:00:00Z',
                'updatedAt': '2024-01-20T14:30:00Z'  # Shows it was updated
            },
            {
                'leadId': 'export-test-2',
                'firstName': 'Alice',
                'lastName': 'Johnson',
                'title': 'Product Manager',
                'company': 'NewCorp Inc',
                'email': 'alice.johnson@newcorp.com',
                'phone': '+1-555-0103',
                'remarks': 'New lead - not a duplicate',
                'sourceFile': 'latest_upload.csv',
                'createdAt': '2024-01-20T14:30:00Z',
                'updatedAt': '2024-01-20T14:30:00Z'
            }
        ]
        
        # Insert test data
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
        
        # Should export 2 leads (no duplicates)
        assert export_body['leadCount'] == 2
        assert export_body['csvData'] is not None
        
        # Verify CSV content
        csv_data = base64.b64decode(export_body['csvData']).decode('utf-8')
        csv_reader = csv.DictReader(StringIO(csv_data))
        rows = list(csv_reader)
        
        assert len(rows) == 2
        
        # Verify deduplicated data is exported
        exported_emails = [row['email'] for row in rows]
        assert 'john.smith@techcorp.com' in exported_emails
        assert 'alice.johnson@newcorp.com' in exported_emails
        
        # Verify updated data is in export
        john_row = next(row for row in rows if row['email'] == 'john.smith@techcorp.com')
        assert john_row['title'] == 'Senior Software Engineer'  # Updated title
        assert john_row['sourceFile'] == 'latest_upload.csv'  # Latest source file
    
    def test_frontend_display_verification(self, aws_environment, lambda_context):
        """
        Test that frontend shows deduplicated leads with correct timestamps.
        Requirements: 6.1, 6.2
        """
        # Pre-populate table with leads that have different created/updated timestamps
        dynamodb_table = aws_environment['dynamodb_table']
        
        test_leads = [
            {
                'leadId': 'frontend-test-1',
                'firstName': 'Emma',
                'lastName': 'Wilson',
                'title': 'Senior Developer',
                'company': 'DevCorp',
                'email': 'emma.wilson@devcorp.com',
                'phone': '+1-555-0200',
                'remarks': 'Updated after duplicate detection',
                'sourceFile': 'second_upload.csv',
                'createdAt': '2024-01-15T10:00:00Z',  # Original creation
                'updatedAt': '2024-01-22T16:45:00Z'   # Updated due to duplicate
            },
            {
                'leadId': 'frontend-test-2',
                'firstName': 'Mike',
                'lastName': 'Johnson',
                'title': 'Designer',
                'company': 'DesignStudio',
                'email': 'mike.johnson@designstudio.com',
                'phone': '+1-555-0201',
                'remarks': 'Original lead - no duplicates',
                'sourceFile': 'first_upload.csv',
                'createdAt': '2024-01-20T12:00:00Z',
                'updatedAt': '2024-01-20T12:00:00Z'  # Same as created (no updates)
            }
        ]
        
        # Insert test data
        with dynamodb_table.batch_writer() as batch:
            for lead in test_leads:
                batch.put_item(Item=lead)
        
        # Test lead reader (simulates frontend data retrieval)
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        
        from lambda_function import lambda_handler as reader_handler
        
        reader_event = {
            'httpMethod': 'GET',
            'headers': {'Authorization': 'Bearer test-token'},
            'queryStringParameters': {
                'sortBy': 'updatedAt',
                'sortOrder': 'desc'
            }
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            reader_response = reader_handler(reader_event, lambda_context)
        
        assert reader_response['statusCode'] == 200
        reader_body = json.loads(reader_response['body'])
        
        assert len(reader_body['leads']) == 2
        leads = reader_body['leads']
        
        # Verify timestamp handling
        emma_lead = next(lead for lead in leads if lead['email'] == 'emma.wilson@devcorp.com')
        mike_lead = next(lead for lead in leads if lead['email'] == 'mike.johnson@designstudio.com')
        
        # Emma's lead should show it was updated (different createdAt and updatedAt)
        assert emma_lead['createdAt'] != emma_lead['updatedAt']
        assert emma_lead['sourceFile'] == 'second_upload.csv'
        
        # Mike's lead should show no updates (same createdAt and updatedAt)
        assert mike_lead['createdAt'] == mike_lead['updatedAt']
        assert mike_lead['sourceFile'] == 'first_upload.csv'
        
        # Verify sorting by updatedAt works (Emma should be first due to more recent update)
        assert leads[0]['email'] == 'emma.wilson@devcorp.com'
    
    def test_performance_with_high_duplicate_percentage(self, aws_environment, lambda_context):
        """
        Test performance with large batches containing high duplicate percentages.
        Requirements: 7.2, 7.5
        """
        # Create a large dataset with 80% duplicates
        large_dataset_csv = self._create_large_duplicate_dataset(100, duplicate_percentage=0.8)
        
        s3_client = aws_environment['s3_client']
        sqs_client = aws_environment['sqs_client']
        upload_bucket = aws_environment['upload_bucket']
        queue_url = aws_environment['queue_url']
        
        # Upload large file
        large_file_key = 'uploads/large_duplicate_test.csv'
        s3_client.put_object(
            Bucket=upload_bucket,
            Key=large_file_key,
            Body=large_dataset_csv.encode('utf-8'),
            ContentType='text/csv'
        )
        
        # Measure processing time
        start_time = time.time()
        
        # Process with lead splitter
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-splitter'))
        
        with patch.dict(os.environ, {
            'SQS_QUEUE_URL': queue_url,
            'BATCH_SIZE': '20'  # Larger batch size for performance test
        }):
            from lambda_function import lambda_handler as splitter_handler
            
            large_s3_event = {
                'Records': [{
                    's3': {
                        'bucket': {'name': upload_bucket},
                        'object': {'key': large_file_key}
                    }
                }]
            }
            
            with patch('lambda_function.s3_client', s3_client):
                with patch('lambda_function.sqs_client', sqs_client):
                    splitter_response = splitter_handler(large_s3_event, lambda_context)
        
        splitter_time = time.time() - start_time
        
        assert splitter_response['statusCode'] == 200
        
        # Verify batch creation performance
        assert splitter_time < 30.0  # Should complete within 30 seconds
        
        # Check that batches were created
        messages_response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10
        )
        
        assert 'Messages' in messages_response
        batch_count = len(messages_response['Messages'])
        assert batch_count > 0
        
        # Simulate processing one batch to test duplicate detection performance
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'deepseek-caller'))
        
        with patch.dict(os.environ, {
            'DEEPSEEK_API_KEY': 'test-key',
            'DYNAMODB_TABLE_NAME': 'test-leads'
        }):
            from lambda_function import lambda_handler as deepseek_handler
            
            # Process first batch
            first_message = messages_response['Messages'][0]
            batch_data = json.loads(first_message['Body'])
            
            # Mock DeepSeek response with duplicates
            mock_response_data = self._create_mock_deepseek_response(batch_data['batch_data'])
            
            sqs_event = {
                'Records': [{
                    'body': first_message['Body'],
                    'receiptHandle': first_message['ReceiptHandle']
                }]
            }
            
            batch_start_time = time.time()
            
            with patch('requests.post') as mock_post:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    'choices': [{
                        'message': {
                            'content': json.dumps(mock_response_data)
                        }
                    }]
                }
                mock_post.return_value = mock_response
                
                deepseek_response = deepseek_handler(sqs_event, lambda_context)
            
            batch_processing_time = time.time() - batch_start_time
            
            assert deepseek_response['statusCode'] == 200
            
            # Verify duplicate detection doesn't cause significant delay
            assert batch_processing_time < 10.0  # Should complete within 10 seconds per batch
            
            # Verify duplicate handling statistics in response
            response_body = deepseek_response.get('body', {})
            if isinstance(response_body, str):
                response_body = json.loads(response_body)
            
            # Should have processing statistics
            assert 'processed_leads' in response_body or 'message' in response_body
    
    def test_error_recovery_and_fallback_behavior(self, aws_environment, lambda_context):
        """
        Test error recovery scenarios and fallback behavior.
        Requirements: 7.2, 7.5
        """
        s3_client = aws_environment['s3_client']
        sqs_client = aws_environment['sqs_client']
        upload_bucket = aws_environment['upload_bucket']
        queue_url = aws_environment['queue_url']
        
        # Test 1: EmailIndex GSI unavailable scenario
        test_data = """Name,Email,Company
John Doe,john@test.com,TestCorp
Jane Smith,jane@test.com,TestCorp"""
        
        file_key = 'uploads/error_test.csv'
        s3_client.put_object(
            Bucket=upload_bucket,
            Key=file_key,
            Body=test_data.encode('utf-8'),
            ContentType='text/csv'
        )
        
        # Process with lead splitter
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-splitter'))
        
        with patch.dict(os.environ, {
            'SQS_QUEUE_URL': queue_url,
            'BATCH_SIZE': '10'
        }):
            from lambda_function import lambda_handler as splitter_handler
            
            s3_event = {
                'Records': [{
                    's3': {
                        'bucket': {'name': upload_bucket},
                        'object': {'key': file_key}
                    }
                }]
            }
            
            with patch('lambda_function.s3_client', s3_client):
                with patch('lambda_function.sqs_client', sqs_client):
                    splitter_response = splitter_handler(s3_event, lambda_context)
        
        assert splitter_response['statusCode'] == 200
        
        # Test 2: DeepSeek caller with GSI failure fallback
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'deepseek-caller'))
        
        with patch.dict(os.environ, {
            'DEEPSEEK_API_KEY': 'test-key',
            'DYNAMODB_TABLE_NAME': 'test-leads'
        }):
            from lambda_function import lambda_handler as deepseek_handler
            
            # Get message from SQS
            messages = sqs_client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1)
            assert 'Messages' in messages
            
            message = messages['Messages'][0]
            
            # Mock DeepSeek response
            mock_response_data = [
                {
                    'firstName': 'John',
                    'lastName': 'Doe',
                    'title': 'Engineer',
                    'company': 'TestCorp',
                    'email': 'john@test.com',
                    'phone': 'N/A',
                    'remarks': 'Test lead'
                },
                {
                    'firstName': 'Jane',
                    'lastName': 'Smith',
                    'title': 'Manager',
                    'company': 'TestCorp',
                    'email': 'jane@test.com',
                    'phone': 'N/A',
                    'remarks': 'Test lead'
                }
            ]
            
            sqs_event = {
                'Records': [{
                    'body': message['Body'],
                    'receiptHandle': message['ReceiptHandle']
                }]
            }
            
            # Test with EmailIndex GSI failure (simulate ResourceNotFoundException)
            from botocore.exceptions import ClientError
            
            def mock_gsi_failure(*args, **kwargs):
                raise ClientError(
                    error_response={'Error': {'Code': 'ResourceNotFoundException'}},
                    operation_name='Query'
                )
            
            with patch('requests.post') as mock_post:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    'choices': [{
                        'message': {
                            'content': json.dumps(mock_response_data)
                        }
                    }]
                }
                mock_post.return_value = mock_response
                
                # Mock EmailIndex query to fail
                with patch('lambda_function.DynamoDBUtils.find_lead_by_email', side_effect=mock_gsi_failure):
                    deepseek_response = deepseek_handler(sqs_event, lambda_context)
            
            # Should still succeed with fallback behavior (create new leads)
            assert deepseek_response['statusCode'] == 200
        
        # Test 3: DeepSeek API failure handling
        api_failure_sqs_event = {
            'Records': [{
                'body': message['Body'],
                'receiptHandle': message['ReceiptHandle']
            }]
        }
        
        with patch('requests.post') as mock_post:
            # Simulate API failure
            mock_post.side_effect = Exception("DeepSeek API unavailable")
            
            api_failure_response = deepseek_handler(api_failure_sqs_event, lambda_context)
            
            # Should handle the error gracefully
            assert api_failure_response['statusCode'] in [500, 422]  # Error handled
        
        # Test 4: Malformed data handling
        malformed_data = """Name,Email
"John Doe with, comma",invalid-email
,empty-name@test.com
Normal User,normal@test.com"""
        
        malformed_file_key = 'uploads/malformed_test.csv'
        s3_client.put_object(
            Bucket=upload_bucket,
            Key=malformed_file_key,
            Body=malformed_data.encode('utf-8'),
            ContentType='text/csv'
        )
        
        malformed_s3_event = {
            'Records': [{
                's3': {
                    'bucket': {'name': upload_bucket},
                    'object': {'key': malformed_file_key}
                }
            }]
        }
        
        with patch('lambda_function.s3_client', s3_client):
            with patch('lambda_function.sqs_client', sqs_client):
                malformed_response = splitter_handler(malformed_s3_event, lambda_context)
        
        # Should handle malformed data gracefully
        assert malformed_response['statusCode'] in [200, 422]  # Success or handled error
    
    def _create_large_duplicate_dataset(self, total_records, duplicate_percentage=0.8):
        """Create a large CSV dataset with specified duplicate percentage."""
        unique_count = int(total_records * (1 - duplicate_percentage))
        duplicate_count = total_records - unique_count
        
        csv_lines = ['Name,Email,Company,Title,Phone']
        
        # Create unique records
        for i in range(unique_count):
            csv_lines.append(f'User {i},user{i}@company{i}.com,Company {i},Title {i},+1-555-{i:04d}')
        
        # Create duplicate records (variations of the unique ones)
        for i in range(duplicate_count):
            base_index = i % unique_count
            # Create variations (case changes, whitespace, etc.)
            if i % 3 == 0:
                # Case variation
                csv_lines.append(f'USER {base_index},USER{base_index}@COMPANY{base_index}.COM,Company {base_index},Title {base_index},+1-555-{base_index:04d}')
            elif i % 3 == 1:
                # Whitespace variation
                csv_lines.append(f'  User {base_index}  ,  user{base_index}@company{base_index}.com  ,Company {base_index},Title {base_index},+1-555-{base_index:04d}')
            else:
                # Exact duplicate
                csv_lines.append(f'User {base_index},user{base_index}@company{base_index}.com,Company {base_index},Title {base_index},+1-555-{base_index:04d}')
        
        return '\n'.join(csv_lines)
    
    def _create_mock_deepseek_response(self, batch_data):
        """Create mock DeepSeek response for batch data."""
        response = []
        for i, lead in enumerate(batch_data):
            response.append({
                'firstName': f'FirstName{i}',
                'lastName': f'LastName{i}',
                'title': f'Title{i}',
                'company': f'Company{i}',
                'email': lead.get('Email', f'email{i}@test.com').lower().strip(),
                'phone': lead.get('Phone', f'+1-555-{i:04d}'),
                'remarks': f'Processed lead {i}'
            })
        return response


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])