"""
Integration tests for Excel multi-worksheet processing.
Tests the complete workflow from file upload through batch processing.
"""

import pytest
import pandas as pd
from io import BytesIO
import json
import sys
import os
from unittest.mock import patch, MagicMock
from moto import mock_aws
import boto3

# Set AWS region for tests
os.environ['AWS_DEFAULT_REGION'] = 'ap-southeast-1'

# Add lambda paths for imports
lead_splitter_path = os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-splitter')
shared_path = os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared')
sys.path.insert(0, lead_splitter_path)
sys.path.insert(0, shared_path)

# Import with environment variable patching
with patch.dict(os.environ, {'PROCESSING_QUEUE_URL': 'dummy-queue-url'}):
    from lambda_function import lambda_handler, FileProcessor
    from error_handling import FileProcessingError


class TestExcelMultiWorksheetIntegration:
    """Integration tests for multi-worksheet Excel processing."""
    
    def create_multi_worksheet_excel(self):
        """Create a test Excel file with multiple worksheets containing different lead formats."""
        # Sales team data
        sales_data = {
            'Full Name': ['John Smith', 'Sarah Johnson'],
            'Email': ['john.smith@company.com', 'sarah.j@company.com'],
            'Phone Number': ['+1-555-0101', '+1-555-0102'],
            'Company Name': ['Tech Solutions Inc', 'Digital Marketing Co'],
            'Job Title': ['Sales Manager', 'Account Executive']
        }
        
        # Marketing team data with different field names
        marketing_data = {
            'Name': ['Mike Wilson', 'Lisa Chen'],
            'Work Email': ['mike@startup.com', 'lisa.chen@startup.com'],
            'Mobile': ['555-0103', '555-0104'],
            'Organization': ['StartupXYZ', 'StartupXYZ'],
            'Position': ['Marketing Director', 'Content Manager']
        }
        
        # Partner referrals with minimal data
        referral_data = {
            'Contact Name': ['David Brown'],
            'Email Address': ['david.brown@partner.com'],
            'Phone': ['+1-555-0105'],
            'Company': ['Partner Corp']
        }
        
        # Create Excel file with multiple sheets
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            pd.DataFrame(sales_data).to_excel(writer, sheet_name='Sales Team', index=False)
            pd.DataFrame(marketing_data).to_excel(writer, sheet_name='Marketing Leads', index=False)
            pd.DataFrame(referral_data).to_excel(writer, sheet_name='Partner Referrals', index=False)
        
        return excel_buffer.getvalue()
    
    @mock_aws
    def test_multi_worksheet_s3_event_processing(self):
        """Test processing S3 event with multi-worksheet Excel file."""
        # Setup AWS resources
        s3 = boto3.client('s3', region_name='ap-southeast-1')
        sqs = boto3.client('sqs', region_name='ap-southeast-1')
        
        # Create S3 bucket
        bucket_name = 'test-upload-bucket'
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': 'ap-southeast-1'}
        )
        
        # Create SQS queue
        queue_url = sqs.create_queue(QueueName='test-processing-queue')['QueueUrl']
        
        # Upload multi-worksheet Excel file
        excel_content = self.create_multi_worksheet_excel()
        file_key = 'uploads/multi_sheet_leads.xlsx'
        
        s3.put_object(
            Bucket=bucket_name,
            Key=file_key,
            Body=excel_content,
            ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        # Create S3 event
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': bucket_name},
                    'object': {'key': file_key}
                }
            }]
        }
        
        # Process the event
        with patch.dict(os.environ, {'PROCESSING_QUEUE_URL': queue_url}):
            response = lambda_handler(event, {})
        
        # Verify successful processing
        assert response['statusCode'] == 200
        assert 'results' in response['body']
        
        results = response['body']['results']
        assert len(results) == 1
        
        result = results[0]
        assert result['file'] == 'multi_sheet_leads.xlsx'
        assert result['total_leads'] == 5  # 2 + 2 + 1 from three sheets
        assert result['batches_sent'] == 1  # All leads fit in one batch (default batch size is 10)
        
        # Verify SQS messages were sent
        messages_response = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10)
        assert 'Messages' in messages_response
        
        messages = messages_response['Messages']
        assert len(messages) == 1
        
        # Parse the message body
        message_body = json.loads(messages[0]['Body'])
        assert message_body['source_file'] == 'multi_sheet_leads.xlsx'
        assert message_body['batch_number'] == 1
        assert message_body['total_batches'] == 1
        assert len(message_body['leads']) == 5
        
        # Verify worksheet information is preserved
        leads = message_body['leads']
        worksheet_names = set(lead['_worksheet'] for lead in leads)
        expected_sheets = {'Sales Team', 'Marketing Leads', 'Partner Referrals'}
        assert worksheet_names == expected_sheets
        
        # Verify data from each worksheet
        sales_leads = [lead for lead in leads if lead['_worksheet'] == 'Sales Team']
        marketing_leads = [lead for lead in leads if lead['_worksheet'] == 'Marketing Leads']
        referral_leads = [lead for lead in leads if lead['_worksheet'] == 'Partner Referrals']
        
        assert len(sales_leads) == 2
        assert len(marketing_leads) == 2
        assert len(referral_leads) == 1
        
        # Verify specific data integrity
        assert sales_leads[0]['Full Name'] == 'John Smith'
        assert sales_leads[0]['Email'] == 'john.smith@company.com'
        assert marketing_leads[0]['Name'] == 'Mike Wilson'
        assert referral_leads[0]['Contact Name'] == 'David Brown'
    
    @mock_aws
    def test_large_multi_worksheet_batching(self):
        """Test that large multi-worksheet files are properly batched."""
        # Create Excel file with multiple sheets and many records
        excel_buffer = BytesIO()
        
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            # Create 3 sheets with 8 records each (24 total)
            for sheet_num in range(1, 4):
                sheet_data = {
                    'Name': [f'Person {i}' for i in range(1, 9)],
                    'Email': [f'person{i}@sheet{sheet_num}.com' for i in range(1, 9)],
                    'Phone': [f'+1-555-{sheet_num:02d}{i:02d}' for i in range(1, 9)],
                    'Company': [f'Company {sheet_num}-{i}' for i in range(1, 9)]
                }
                
                pd.DataFrame(sheet_data).to_excel(
                    writer, 
                    sheet_name=f'Sheet{sheet_num}', 
                    index=False
                )
        
        excel_content = excel_buffer.getvalue()
        
        # Setup AWS resources
        s3 = boto3.client('s3', region_name='ap-southeast-1')
        sqs = boto3.client('sqs', region_name='ap-southeast-1')
        
        bucket_name = 'test-upload-bucket'
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': 'ap-southeast-1'}
        )
        
        queue_url = sqs.create_queue(QueueName='test-processing-queue')['QueueUrl']
        
        # Upload file
        file_key = 'uploads/large_multi_sheet.xlsx'
        s3.put_object(Bucket=bucket_name, Key=file_key, Body=excel_content)
        
        # Create S3 event
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': bucket_name},
                    'object': {'key': file_key}
                }
            }]
        }
        
        # Process with smaller batch size to test batching
        with patch.dict(os.environ, {'PROCESSING_QUEUE_URL': queue_url}):
            # Mock the batch size to be smaller for testing
            with patch('lambda_function.split_leads_into_batches') as mock_split:
                # Force smaller batches (5 leads per batch)
                def custom_split(leads, batch_size=10):
                    batches = []
                    for i in range(0, len(leads), 5):  # Use batch size of 5
                        batch = leads[i:i + 5]
                        batches.append(batch)
                    return batches
                
                mock_split.side_effect = custom_split
                
                response = lambda_handler(event, {})
        
        # Verify processing
        assert response['statusCode'] == 200
        
        result = response['body']['results'][0]
        assert result['total_leads'] == 24  # 8 × 3 sheets
        assert result['batches_sent'] == 5  # 24 leads ÷ 5 per batch = 5 batches (rounded up)
        
        # Verify multiple SQS messages were sent
        all_messages = []
        while True:
            messages_response = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10)
            if 'Messages' not in messages_response:
                break
            all_messages.extend(messages_response['Messages'])
            # Delete received messages to avoid re-processing
            for message in messages_response['Messages']:
                sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=message['ReceiptHandle']
                )
        
        assert len(all_messages) == 5  # Should have 5 batch messages
        
        # Verify all leads are accounted for across batches
        total_leads_in_batches = 0
        worksheet_distribution = {}
        
        for message in all_messages:
            message_body = json.loads(message['Body'])
            batch_leads = message_body['leads']
            total_leads_in_batches += len(batch_leads)
            
            # Track worksheet distribution
            for lead in batch_leads:
                worksheet = lead['_worksheet']
                worksheet_distribution[worksheet] = worksheet_distribution.get(worksheet, 0) + 1
        
        assert total_leads_in_batches == 24
        assert len(worksheet_distribution) == 3  # All 3 worksheets represented
        assert sum(worksheet_distribution.values()) == 24
    
    def test_direct_file_processor_multi_worksheet(self):
        """Test FileProcessor directly with multi-worksheet Excel."""
        excel_content = self.create_multi_worksheet_excel()
        
        # Process the file
        leads = FileProcessor.read_excel_file(excel_content)
        
        # Verify results
        assert len(leads) == 5
        
        # Check worksheet distribution
        worksheet_counts = {}
        for lead in leads:
            worksheet = lead['_worksheet']
            worksheet_counts[worksheet] = worksheet_counts.get(worksheet, 0) + 1
        
        expected_counts = {
            'Sales Team': 2,
            'Marketing Leads': 2,
            'Partner Referrals': 1
        }
        
        assert worksheet_counts == expected_counts
        
        # Verify field preservation across worksheets
        sales_lead = next(lead for lead in leads if lead['_worksheet'] == 'Sales Team')
        marketing_lead = next(lead for lead in leads if lead['_worksheet'] == 'Marketing Leads')
        referral_lead = next(lead for lead in leads if lead['_worksheet'] == 'Partner Referrals')
        
        # Sales team uses 'Full Name', 'Email', 'Phone Number'
        assert 'Full Name' in sales_lead
        assert 'Email' in sales_lead
        assert 'Phone Number' in sales_lead
        
        # Marketing team uses 'Name', 'Work Email', 'Mobile'
        assert 'Name' in marketing_lead
        assert 'Work Email' in marketing_lead
        assert 'Mobile' in marketing_lead
        
        # Referrals use 'Contact Name', 'Email Address', 'Phone'
        assert 'Contact Name' in referral_lead
        assert 'Email Address' in referral_lead
        assert 'Phone' in referral_lead