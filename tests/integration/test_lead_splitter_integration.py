"""
Integration tests for Lead Splitter Lambda function.
Tests actual AWS service integration and end-to-end workflows.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch, Mock
import boto3
from moto import mock_aws

# Add lambda paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-splitter'))

from lambda_function import lambda_handler


class TestLeadSplitterIntegration(unittest.TestCase):
    """Integration test cases for Lead Splitter Lambda function."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_csv_content = b"""Name,Company,Email,Phone,Title
John Doe,Acme Corp,john@acme.com,555-1234,Sales Manager
Jane Smith,Tech Solutions,jane@techsol.com,555-5678,Marketing Director
Bob Johnson,Global Inc,bob@global.com,555-9012,CEO"""
    
    @mock_aws
    def test_end_to_end_csv_processing(self):
        """Test complete CSV processing workflow."""
        # Setup AWS mocks
        s3 = boto3.client('s3', region_name='ap-southeast-1')
        sqs = boto3.client('sqs', region_name='ap-southeast-1')
        
        bucket_name = 'test-files-bucket'
        key = 'uploads/test-leads.csv'
        
        # Create S3 bucket and upload file
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': 'ap-southeast-1'}
        )
        s3.put_object(Bucket=bucket_name, Key=key, Body=self.test_csv_content)
        
        # Create SQS queue
        queue_url = sqs.create_queue(QueueName='lead-processing-queue')['QueueUrl']
        
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
            
            # Verify successful processing
            self.assertEqual(response['statusCode'], 200)
            self.assertIn('results', response['body'])
            
            results = response['body']['results']
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]['total_leads'], 3)
            self.assertEqual(results[0]['batches_sent'], 1)
            
            # Verify SQS message was sent
            messages = sqs.receive_message(QueueUrl=queue_url)
            self.assertIn('Messages', messages)
            
            # Verify message content
            message_body = json.loads(messages['Messages'][0]['Body'])
            self.assertEqual(message_body['source_file'], 'test-leads.csv')
            self.assertEqual(len(message_body['leads']), 3)
    
    @mock_aws
    def test_large_file_batching(self):
        """Test processing of large files that require multiple batches."""
        # Create large CSV content (15 leads)
        large_csv_content = b"Name,Company,Email\n"
        for i in range(15):
            large_csv_content += f"User{i},Company{i},user{i}@company{i}.com\n".encode()
        
        # Setup AWS mocks
        s3 = boto3.client('s3', region_name='ap-southeast-1')
        sqs = boto3.client('sqs', region_name='ap-southeast-1')
        
        bucket_name = 'test-files-bucket'
        key = 'uploads/large-leads.csv'
        
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': 'ap-southeast-1'}
        )
        s3.put_object(Bucket=bucket_name, Key=key, Body=large_csv_content)
        
        queue_url = sqs.create_queue(QueueName='lead-processing-queue')['QueueUrl']
        
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
            
            # Verify successful processing
            self.assertEqual(response['statusCode'], 200)
            
            results = response['body']['results']
            self.assertEqual(results[0]['total_leads'], 15)
            self.assertEqual(results[0]['batches_sent'], 2)  # 10 + 5 leads
            
            # Verify multiple SQS messages were sent
            all_messages = []
            while True:
                messages = sqs.receive_message(QueueUrl=queue_url)
                if 'Messages' not in messages:
                    break
                all_messages.extend(messages['Messages'])
                # Delete received messages to avoid re-receiving
                for msg in messages['Messages']:
                    sqs.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=msg['ReceiptHandle']
                    )
            
            self.assertEqual(len(all_messages), 2)
    
    @mock_aws
    def test_invalid_file_handling(self):
        """Test handling of invalid or corrupted files."""
        # Setup AWS mocks
        s3 = boto3.client('s3', region_name='ap-southeast-1')
        sqs = boto3.client('sqs', region_name='ap-southeast-1')
        
        bucket_name = 'test-files-bucket'
        key = 'uploads/invalid.csv'
        
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': 'ap-southeast-1'}
        )
        # Upload invalid CSV content
        s3.put_object(Bucket=bucket_name, Key=key, Body=b"invalid,csv,content\nwith,missing,headers")
        
        queue_url = sqs.create_queue(QueueName='lead-processing-queue')['QueueUrl']
        
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': bucket_name},
                    'object': {'key': key}
                }
            }]
        }
        
        with patch.dict(os.environ, {'PROCESSING_QUEUE_URL': queue_url}):
            # Should handle gracefully without crashing
            try:
                response = lambda_handler(event, {})
                # If it succeeds, verify it handled the error gracefully
                self.assertEqual(response['statusCode'], 200)
            except Exception as e:
                # If it fails, it should be a controlled failure
                self.assertIsInstance(e, (ValueError, FileNotFoundError))
    
    @mock_aws
    @patch('lambda_function.status_service')
    def test_status_tracking_integration(self, mock_status_service):
        """Test that status tracking is properly integrated with lead splitting."""
        # Setup mocks
        mock_status_service.update_status = Mock()
        mock_status_service.set_error = Mock()
        
        # Setup AWS mocks
        s3 = boto3.client('s3', region_name='ap-southeast-1')
        sqs = boto3.client('sqs', region_name='ap-southeast-1')
        
        bucket_name = 'test-files-bucket'
        upload_id = "12345678-1234-1234-1234-123456789012"
        key = f'uploads/{upload_id}/test-leads.csv'
        
        # Create S3 bucket and upload file
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': 'ap-southeast-1'}
        )
        s3.put_object(Bucket=bucket_name, Key=key, Body=self.test_csv_content)
        
        # Create SQS queue
        queue_url = sqs.create_queue(QueueName='lead-processing-queue')['QueueUrl']
        
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
            
            # Verify successful processing
            self.assertEqual(response['statusCode'], 200)
            
            # Verify status was updated to processing
            mock_status_service.update_status.assert_any_call(
                upload_id=upload_id,
                status='processing',
                stage='file_processing'
            )
            
            # Verify batch information was updated
            mock_status_service.update_status.assert_any_call(
                upload_id=upload_id,
                status='processing',
                stage='batch_processing',
                progress={
                    'totalBatches': 1,  # 3 leads = 1 batch (batch size 10)
                    'completedBatches': 0,
                    'totalLeads': 3,
                    'processedLeads': 0
                }
            )
            
            # Verify SQS message includes upload_id
            messages = sqs.receive_message(QueueUrl=queue_url)
            self.assertIn('Messages', messages)
            
            message_body = json.loads(messages['Messages'][0]['Body'])
            self.assertEqual(message_body['upload_id'], upload_id)
            self.assertEqual(message_body['source_file'], 'test-leads.csv')
            self.assertEqual(len(message_body['leads']), 3)


if __name__ == '__main__':
    unittest.main()