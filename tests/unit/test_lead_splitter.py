"""
Unit tests for Lead Splitter Lambda function.
Tests CSV/Excel processing and SQS batch creation.
"""

import json
import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
import boto3
from moto import mock_aws

# Set AWS region for tests
os.environ['AWS_DEFAULT_REGION'] = 'ap-southeast-1'

# Add lambda paths for imports
lead_splitter_path = os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-splitter')
shared_path = os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared')
sys.path.insert(0, lead_splitter_path)
sys.path.insert(0, shared_path)

from lambda_function import (
    lambda_handler,
    FileProcessor,
    download_file_from_s3,
    split_leads_into_batches,
    send_batch_to_sqs
)
from error_handling import FileProcessingError


class TestLeadSplitter(unittest.TestCase):
    """Test cases for Lead Splitter Lambda function."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_csv_content = b"""Name,Company,Email,Phone,Title
John Doe,Acme Corp,john@acme.com,555-1234,Sales Manager
Jane Smith,Tech Solutions,jane@techsol.com,555-5678,Marketing Director"""
        
        self.test_leads = [
            {
                'Name': 'John Doe',
                'Company': 'Acme Corp',
                'Email': 'john@acme.com',
                'Phone': '555-1234',
                'Title': 'Sales Manager'
            },
            {
                'Name': 'Jane Smith',
                'Company': 'Tech Solutions',
                'Email': 'jane@techsol.com',
                'Phone': '555-5678',
                'Title': 'Marketing Director'
            }
        ]
    
    def test_csv_processing(self):
        """Test CSV file processing."""
        processor = FileProcessor()
        leads = processor.read_csv_file(self.test_csv_content)
        
        self.assertEqual(len(leads), 2)
        self.assertEqual(leads[0]['Name'], 'John Doe')
        self.assertEqual(leads[0]['Company'], 'Acme Corp')
        self.assertEqual(leads[1]['Name'], 'Jane Smith')
    
    def test_split_leads_into_batches(self):
        """Test lead splitting functionality."""
        # Test with batch size 10 (default)
        batches = split_leads_into_batches(self.test_leads)
        self.assertEqual(len(batches), 1)
        self.assertEqual(len(batches[0]), 2)
        
        # Test with custom batch size
        batches = split_leads_into_batches(self.test_leads, batch_size=1)
        self.assertEqual(len(batches), 2)
        self.assertEqual(len(batches[0]), 1)
        self.assertEqual(len(batches[1]), 1)
    
    @mock_aws
    def test_send_batch_to_sqs(self):
        """Test SQS message sending."""
        # Create mock SQS queue
        sqs = boto3.client('sqs', region_name='ap-southeast-1')
        queue_url = sqs.create_queue(QueueName='test-queue')['QueueUrl']
        
        with patch.dict(os.environ, {'PROCESSING_QUEUE_URL': queue_url}):
            message_id = send_batch_to_sqs(
                batch=self.test_leads,
                source_file='test.csv',
                batch_number=1,
                total_batches=1
            )
            
            self.assertIsNotNone(message_id)
            
            # Verify message was sent
            messages = sqs.receive_message(QueueUrl=queue_url)
            self.assertIn('Messages', messages)
    
    @mock_aws
    def test_s3_file_download(self):
        """Test S3 file download functionality."""
        # Create mock S3 bucket and object
        s3 = boto3.client('s3', region_name='ap-southeast-1')
        bucket_name = 'test-bucket'
        key = 'test-file.csv'
        
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': 'ap-southeast-1'}
        )
        s3.put_object(Bucket=bucket_name, Key=key, Body=self.test_csv_content)
        
        # Test download
        content = download_file_from_s3(bucket_name, key)
        self.assertEqual(content, self.test_csv_content)
    
    @mock_aws
    def test_lambda_handler_success(self):
        """Test successful Lambda handler execution."""
        # Setup mocks
        s3 = boto3.client('s3', region_name='ap-southeast-1')
        sqs = boto3.client('sqs', region_name='ap-southeast-1')
        
        bucket_name = 'test-bucket'
        key = 'uploads/test.csv'
        
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': 'ap-southeast-1'}
        )
        s3.put_object(Bucket=bucket_name, Key=key, Body=self.test_csv_content)
        
        queue_url = sqs.create_queue(QueueName='test-queue')['QueueUrl']
        
        # Create S3 event
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': bucket_name},
                    'object': {'key': key}
                }
            }]
        }
        
        with patch.dict(os.environ, {'PROCESSING_QUEUE_URL': queue_url}):
            response = lambda_handler(event, {})
            
            self.assertEqual(response['statusCode'], 200)
            self.assertIn('results', response['body'])
    
    def test_invalid_file_type(self):
        """Test handling of invalid file types."""
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 'uploads/test.txt'}  # Invalid file type
                }
            }]
        }
        
        with patch.dict(os.environ, {'PROCESSING_QUEUE_URL': 'test-queue'}):
            response = lambda_handler(event, {})
            
            # Should complete successfully but skip invalid file
            self.assertEqual(response['statusCode'], 200)


if __name__ == '__main__':
    unittest.main()