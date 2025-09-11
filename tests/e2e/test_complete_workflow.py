"""
End-to-end tests for the complete lead management system workflow.

Tests the entire system from file upload through processing to data retrieval,
using the actual easy-crm-test.xlsx file and real system interactions.
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
from io import BytesIO

# Add lambda paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))

class TestCompleteWorkflow:
    """End-to-end workflow tests."""
    
    @pytest.fixture
    def aws_environment(self):
        """Set up complete AWS environment for testing."""
        with mock_aws():
            # Create S3 client and buckets
            s3_client = boto3.client('s3', region_name='ap-southeast-1')
            
            upload_bucket = 'test-upload-bucket'
            s3_client.create_bucket(
                Bucket=upload_bucket,
                CreateBucketConfiguration={'LocationConstraint': 'ap-southeast-1'}
            )
            
            # Create DynamoDB table
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
                'upload_bucket': upload_bucket,
                'dynamodb_table': table
            }
    
    @pytest.fixture
    def test_csv_data(self):
        """Create test CSV data similar to easy-crm-test.xlsx structure."""
        return """Name,Job Title,Company,Email Address,Phone,Notes
John Smith,Software Engineer,Tech Solutions Inc,john.smith@techsolutions.com,+1-555-0123,Interested in cloud migration
Sarah Johnson,Marketing Manager,Digital Marketing Co,sarah.j@digitalmarketing.com,+1-555-0124,Looking for automation tools
Michael Chen,CTO,StartupXYZ,michael.chen@startupxyz.com,+1-555-0125,Evaluating new technologies
Lisa Williams,Product Manager,Innovation Corp,lisa.w@innovation.com,+1-555-0126,Needs scalable solutions
David Brown,Senior Developer,Tech Solutions Inc,david.brown@techsolutions.com,+1-555-0127,Python and AWS expert"""
    
    @pytest.fixture
    def lambda_context(self):
        """Mock Lambda context."""
        context = Mock()
        context.aws_request_id = 'e2e-test-request'
        context.function_name = 'test-function'
        context.memory_limit_in_mb = 256
        context.remaining_time_in_millis = lambda: 30000
        return context
    
    def test_complete_csv_upload_to_retrieval_workflow(self, aws_environment, test_csv_data, lambda_context):
        """Test complete workflow: upload CSV -> process -> retrieve leads."""
        s3_client = aws_environment['s3_client']
        upload_bucket = aws_environment['upload_bucket']
        
        # Step 1: Simulate file upload Lambda
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'file-upload'))
        
        with patch.dict(os.environ, {
            'UPLOAD_BUCKET': upload_bucket,
            'MAX_FILE_SIZE_MB': '10',
            'PRESIGNED_URL_EXPIRATION': '3600'
        }):
            from lambda_function import lambda_handler as upload_handler
            
            upload_event = {
                'body': json.dumps({
                    'fileName': 'test_leads.csv',
                    'fileType': 'text/csv',
                    'fileSize': len(test_csv_data.encode('utf-8'))
                })
            }
            
            with patch('lambda_function.s3_client', s3_client):
                upload_response = upload_handler(upload_event, lambda_context)
            
            assert upload_response['statusCode'] == 200
            upload_body = json.loads(upload_response['body'])
            file_key = upload_body['fileKey']
        
        # Step 2: Upload the actual file to S3
        s3_client.put_object(
            Bucket=upload_bucket,
            Key=file_key,
            Body=test_csv_data.encode('utf-8'),
            ContentType='text/csv'
        )
        
        # Step 3: Simulate lead splitter Lambda processing
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-splitter'))
        
        with patch.dict(os.environ, {
            'DEEPSEEK_API_KEY': 'test-key',
            'DYNAMODB_TABLE_NAME': 'test-leads'
        }):
            # Import after setting environment
            from lambda_function import lambda_handler as formatter_handler
            
            # Create S3 trigger event
            s3_event = {
                'Records': [{
                    's3': {
                        'bucket': {'name': upload_bucket},
                        'object': {'key': file_key}
                    }
                }]
            }
            
            # Mock DeepSeek API response
            mock_deepseek_response = [
                {
                    'firstName': 'John',
                    'lastName': 'Smith',
                    'title': 'Software Engineer',
                    'company': 'Tech Solutions Inc',
                    'email': 'john.smith@techsolutions.com',
                    'remarks': 'Interested in cloud migration, Phone: +1-555-0123'
                },
                {
                    'firstName': 'Sarah',
                    'lastName': 'Johnson',
                    'title': 'Marketing Manager',
                    'company': 'Digital Marketing Co',
                    'email': 'sarah.j@digitalmarketing.com',
                    'remarks': 'Looking for automation tools, Phone: +1-555-0124'
                },
                {
                    'firstName': 'Michael',
                    'lastName': 'Chen',
                    'title': 'CTO',
                    'company': 'StartupXYZ',
                    'email': 'michael.chen@startupxyz.com',
                    'remarks': 'Evaluating new technologies, Phone: +1-555-0125'
                },
                {
                    'firstName': 'Lisa',
                    'lastName': 'Williams',
                    'title': 'Product Manager',
                    'company': 'Innovation Corp',
                    'email': 'lisa.w@innovation.com',
                    'remarks': 'Needs scalable solutions, Phone: +1-555-0126'
                },
                {
                    'firstName': 'David',
                    'lastName': 'Brown',
                    'title': 'Senior Developer',
                    'company': 'Tech Solutions Inc',
                    'email': 'david.brown@techsolutions.com',
                    'remarks': 'Python and AWS expert, Phone: +1-555-0127'
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
                
                with patch('lambda_function.s3_client', s3_client):
                    formatter_response = formatter_handler(s3_event, lambda_context)
            
            assert formatter_response['statusCode'] == 200
            formatter_body = formatter_response['body']
            assert formatter_body['message'] == 'File processing completed successfully'
            assert len(formatter_body['results']) == 1
            assert formatter_body['results'][0]['processed_leads'] == 5
        
        # Step 4: Test lead retrieval
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        
        # Import lead reader after setting up the environment
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
        
        # Verify all leads were processed and stored
        assert len(reader_body['leads']) == 5
        assert reader_body['pagination']['totalCount'] == 5
        
        # Verify lead data integrity
        lead_names = [(lead['firstName'], lead['lastName']) for lead in reader_body['leads']]
        expected_names = [('John', 'Smith'), ('Sarah', 'Johnson'), ('Michael', 'Chen'), 
                         ('Lisa', 'Williams'), ('David', 'Brown')]
        
        for expected_name in expected_names:
            assert expected_name in lead_names
        
        # Step 5: Test filtering functionality
        filter_event = {
            'httpMethod': 'GET',
            'headers': {'Authorization': 'Bearer test-token'},
            'queryStringParameters': {
                'filter_company': 'Tech Solutions'
            }
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            filter_response = reader_handler(filter_event, lambda_context)
        
        assert filter_response['statusCode'] == 200
        filter_body = json.loads(filter_response['body'])
        
        # Should find 2 leads from Tech Solutions Inc
        assert len(filter_body['leads']) == 2
        for lead in filter_body['leads']:
            assert 'Tech Solutions' in lead['company']
    
    def test_complete_excel_workflow_with_export(self, aws_environment, lambda_context):
        """Test complete workflow with Excel file and CSV export."""
        s3_client = aws_environment['s3_client']
        upload_bucket = aws_environment['upload_bucket']
        
        # Create test Excel data
        df = pd.DataFrame({
            'Full Name': ['Alice Johnson', 'Bob Wilson', 'Carol Davis'],
            'Position': ['UX Designer', 'Data Analyst', 'Project Manager'],
            'Organization': ['Design Studio', 'Analytics Corp', 'Management Inc'],
            'Contact Email': ['alice@design.com', 'bob@analytics.com', 'carol@management.com'],
            'Phone Number': ['+1-555-0200', '+1-555-0201', '+1-555-0202'],
            'Additional Info': ['Creative solutions', 'Data-driven insights', 'Agile methodology']
        })
        
        excel_buffer = BytesIO()
        df.to_excel(excel_buffer, index=False)
        excel_content = excel_buffer.getvalue()
        
        # Step 1: Upload Excel file
        file_key = 'uploads/test-excel/test_leads.xlsx'
        s3_client.put_object(
            Bucket=upload_bucket,
            Key=file_key,
            Body=excel_content,
            ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        # Step 2: Process Excel file
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-splitter'))
        
        with patch.dict(os.environ, {
            'DEEPSEEK_API_KEY': 'test-key',
            'DYNAMODB_TABLE_NAME': 'test-leads'
        }):
            from lambda_function import lambda_handler as formatter_handler
            
            s3_event = {
                'Records': [{
                    's3': {
                        'bucket': {'name': upload_bucket},
                        'object': {'key': file_key}
                    }
                }]
            }
            
            # Mock DeepSeek response for Excel data
            mock_deepseek_response = [
                {
                    'firstName': 'Alice',
                    'lastName': 'Johnson',
                    'title': 'UX Designer',
                    'company': 'Design Studio',
                    'email': 'alice@design.com',
                    'remarks': 'Creative solutions, Phone: +1-555-0200'
                },
                {
                    'firstName': 'Bob',
                    'lastName': 'Wilson',
                    'title': 'Data Analyst',
                    'company': 'Analytics Corp',
                    'email': 'bob@analytics.com',
                    'remarks': 'Data-driven insights, Phone: +1-555-0201'
                },
                {
                    'firstName': 'Carol',
                    'lastName': 'Davis',
                    'title': 'Project Manager',
                    'company': 'Management Inc',
                    'email': 'carol@management.com',
                    'remarks': 'Agile methodology, Phone: +1-555-0202'
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
                
                with patch('lambda_function.s3_client', s3_client):
                    formatter_response = formatter_handler(s3_event, lambda_context)
            
            assert formatter_response['statusCode'] == 200
        
        # Step 3: Test CSV export
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-exporter'))
        
        from lambda_function import lambda_handler as exporter_handler
        
        export_event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer test-token'},
            'queryStringParameters': {
                'filter_title': 'Designer'
            }
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            export_response = exporter_handler(export_event, lambda_context)
        
        assert export_response['statusCode'] == 200
        export_body = json.loads(export_response['body'])
        
        # Should export 1 lead (Alice Johnson - UX Designer)
        assert export_body['leadCount'] == 1
        assert export_body['csvData'] is not None
        
        # Verify CSV content
        import base64
        import csv
        from io import StringIO
        
        csv_data = base64.b64decode(export_body['csvData']).decode('utf-8')
        csv_reader = csv.DictReader(StringIO(csv_data))
        rows = list(csv_reader)
        
        assert len(rows) == 1
        assert rows[0]['firstName'] == 'Alice'
        assert rows[0]['title'] == 'UX Designer'
    
    def test_chatbot_integration_workflow(self, aws_environment, lambda_context):
        """Test chatbot integration with the complete system."""
        # First, populate some test data
        dynamodb_table = aws_environment['dynamodb_table']
        
        test_leads = [
            {
                'leadId': 'chat-test-1',
                'firstName': 'Emma',
                'lastName': 'Thompson',
                'title': 'Software Engineer',
                'company': 'Google',
                'email': 'emma@google.com',
                'remarks': 'Cloud architecture expert',
                'sourceFile': 'chat-test.csv',
                'createdAt': '2024-01-15T10:00:00Z',
                'updatedAt': '2024-01-15T10:00:00Z'
            },
            {
                'leadId': 'chat-test-2',
                'firstName': 'James',
                'lastName': 'Wilson',
                'title': 'Product Manager',
                'company': 'Microsoft',
                'email': 'james@microsoft.com',
                'remarks': 'AI and ML focus',
                'sourceFile': 'chat-test.csv',
                'createdAt': '2024-01-16T10:00:00Z',
                'updatedAt': '2024-01-16T10:00:00Z'
            }
        ]
        
        # Insert test data
        with dynamodb_table.batch_writer() as batch:
            for lead in test_leads:
                batch.put_item(Item=lead)
        
        # Test chatbot queries
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'chatbot'))
        
        from lambda_function import lambda_handler as chatbot_handler
        
        # Test filter query
        chat_event = {
            'httpMethod': 'POST',
            'headers': {'Authorization': 'Bearer test-token'},
            'body': json.dumps({
                'query': 'show me leads from Google'
            })
        }
        
        with patch('lambda_function.validate_jwt_token') as mock_jwt:
            mock_jwt.return_value = {'sub': 'test-user'}
            
            with patch('lambda_function.generate_dynamodb_query') as mock_generate:
                mock_generate.return_value = {
                    'type': 'filter',
                    'filters': {'company': 'Google'},
                    'limit': 50
                }
                
                chat_response = chatbot_handler(chat_event, lambda_context)
        
        assert chat_response['statusCode'] == 200
        chat_body = json.loads(chat_response['body'])
        
        assert chat_body['type'] == 'success'
        assert 'Google' in chat_body['response']
        assert chat_body['resultCount'] == 1
    
    def test_error_handling_throughout_workflow(self, aws_environment, lambda_context):
        """Test error handling at various points in the workflow."""
        s3_client = aws_environment['s3_client']
        upload_bucket = aws_environment['upload_bucket']
        
        # Test 1: Invalid file upload
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'file-upload'))
        
        with patch.dict(os.environ, {
            'UPLOAD_BUCKET': upload_bucket,
            'MAX_FILE_SIZE_MB': '10',
            'PRESIGNED_URL_EXPIRATION': '3600'
        }):
            from lambda_function import lambda_handler as upload_handler
            
            # Test unsupported file type
            invalid_upload_event = {
                'body': json.dumps({
                    'fileName': 'document.pdf',
                    'fileType': 'application/pdf',
                    'fileSize': 1024
                })
            }
            
            upload_response = upload_handler(invalid_upload_event, lambda_context)
            assert upload_response['statusCode'] == 400
        
        # Test 2: Lead splitter with invalid file
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-splitter'))
        
        # Upload invalid file content
        invalid_file_key = 'uploads/invalid.csv'
        s3_client.put_object(
            Bucket=upload_bucket,
            Key=invalid_file_key,
            Body=b'invalid,csv,content\nwith\ninconsistent\ncolumns',
            ContentType='text/csv'
        )
        
        with patch.dict(os.environ, {
            'DEEPSEEK_API_KEY': 'test-key',
            'DYNAMODB_TABLE_NAME': 'test-leads'
        }):
            from lambda_function import lambda_handler as formatter_handler
            
            invalid_s3_event = {
                'Records': [{
                    's3': {
                        'bucket': {'name': upload_bucket},
                        'object': {'key': invalid_file_key}
                    }
                }]
            }
            
            with patch('lambda_function.s3_client', s3_client):
                # Should handle the error gracefully
                formatter_response = formatter_handler(invalid_s3_event, lambda_context)
            
            # Should complete but with error handling
            assert formatter_response['statusCode'] in [200, 422]  # Success or handled error
        
        # Test 3: Authentication errors
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-reader'))
        
        from lambda_function import lambda_handler as reader_handler
        
        # Test missing authentication
        unauth_event = {
            'httpMethod': 'GET',
            'headers': {},  # No Authorization header
            'queryStringParameters': {}
        }
        
        reader_response = reader_handler(unauth_event, lambda_context)
        assert reader_response['statusCode'] == 401
    
    @pytest.mark.skipif(
        not os.path.exists(os.path.join(os.path.dirname(__file__), '..', '..', 'easy-crm-test.xlsx')),
        reason="easy-crm-test.xlsx file not found"
    )
    def test_real_test_file_processing(self, aws_environment, lambda_context):
        """Test processing the actual easy-crm-test.xlsx file."""
        test_file_path = os.path.join(os.path.dirname(__file__), '..', '..', 'easy-crm-test.xlsx')
        
        # Read the actual test file
        with open(test_file_path, 'rb') as f:
            excel_content = f.read()
        
        s3_client = aws_environment['s3_client']
        upload_bucket = aws_environment['upload_bucket']
        
        # Upload the real test file
        file_key = 'uploads/easy-crm-test.xlsx'
        s3_client.put_object(
            Bucket=upload_bucket,
            Key=file_key,
            Body=excel_content,
            ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        # Process with lead splitter
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-splitter'))
        
        with patch.dict(os.environ, {
            'DEEPSEEK_API_KEY': 'test-key',
            'DYNAMODB_TABLE_NAME': 'test-leads'
        }):
            from lambda_function import FileProcessor
            
            # Test file reading
            leads = FileProcessor.read_excel_file(excel_content)
            
            assert len(leads) > 0
            print(f"Successfully read {len(leads)} leads from easy-crm-test.xlsx")
            
            # Verify data structure
            if leads:
                first_lead = leads[0]
                print(f"Sample lead keys: {list(first_lead.keys())}")
                
                # Should have some recognizable fields
                lead_keys = list(first_lead.keys())
                assert len(lead_keys) > 0

if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])