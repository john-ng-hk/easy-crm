"""
Unit tests for processing status cancellation functionality.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from moto import mock_aws
import boto3
import os
import sys

# Add the lambda function path to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'status-reader'))

from status_service import ProcessingStatusService, StatusValidationError, StatusNotFoundError
import lambda_function


class TestStatusCancellation:
    """Test cases for status cancellation functionality."""
    
    @mock_aws
    def test_cancel_processing_success(self):
        """Test successful processing cancellation."""
        # Setup DynamoDB table
        dynamodb = boto3.client('dynamodb', region_name='us-east-1')
        table_name = 'ProcessingStatus'
        
        dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'uploadId', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'uploadId', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Initialize status service
        status_service = ProcessingStatusService(dynamodb_client=dynamodb, table_name=table_name)
        
        # Create initial status
        upload_id = 'test-upload-123'
        status_service.create_status(upload_id, 'test.csv', 1024, 'processing')
        
        # Update with some progress
        status_service.update_status(
            upload_id=upload_id,
            progress={
                'totalBatches': 10,
                'completedBatches': 3,
                'totalLeads': 100,
                'processedLeads': 30
            }
        )
        
        # Cancel processing
        cancelled_status = status_service.cancel_processing(upload_id)
        
        # Verify cancellation
        assert cancelled_status['status'] == 'cancelled'
        assert cancelled_status['stage'] == 'cancelled'
        assert cancelled_status['progress']['completedBatches'] == 3
        assert cancelled_status['progress']['totalBatches'] == 10
        assert cancelled_status['progress']['percentage'] == 30.0
        assert 'cancellationTime' in cancelled_status['metadata']
        assert cancelled_status['metadata']['cancellationReason'] == 'User requested cancellation'
    
    @mock_aws
    def test_cancel_processing_already_completed(self):
        """Test cancellation of already completed processing."""
        # Setup DynamoDB table
        dynamodb = boto3.client('dynamodb', region_name='us-east-1')
        table_name = 'ProcessingStatus'
        
        dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'uploadId', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'uploadId', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Initialize status service
        status_service = ProcessingStatusService(dynamodb_client=dynamodb, table_name=table_name)
        
        # Create completed status
        upload_id = 'test-upload-456'
        status_service.create_status(upload_id, 'test.csv', 1024, 'completed')
        
        # Try to cancel completed processing
        with pytest.raises(StatusValidationError) as exc_info:
            status_service.cancel_processing(upload_id)
        
        assert 'Cannot cancel processing - already completed' in str(exc_info.value)
    
    @mock_aws
    def test_cancel_processing_not_found(self):
        """Test cancellation of non-existent processing."""
        # Setup DynamoDB table
        dynamodb = boto3.client('dynamodb', region_name='us-east-1')
        table_name = 'ProcessingStatus'
        
        dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'uploadId', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'uploadId', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Initialize status service
        status_service = ProcessingStatusService(dynamodb_client=dynamodb, table_name=table_name)
        
        # Try to cancel non-existent processing
        with pytest.raises(StatusNotFoundError):
            status_service.cancel_processing('non-existent-upload')
    
    @patch('lambda_function.status_service')
    @patch('lambda_function.cancel_processing_workflow')
    def test_handle_cancel_processing_success(self, mock_cancel_workflow, mock_status_service):
        """Test successful cancel processing API handler."""
        # Mock status service
        mock_status_service.get_status.return_value = {
            'status': 'processing',
            'progress': {'completedBatches': 2, 'totalBatches': 5}
        }
        
        # Mock cancel workflow
        mock_cancel_workflow.return_value = {
            'status': 'cancelled',
            'stage': 'cancelled',
            'progress': {'completedBatches': 2, 'totalBatches': 5, 'percentage': 40.0}
        }
        
        # Create mock context
        context = Mock()
        context.aws_request_id = 'test-request-123'
        
        # Call handler
        result = lambda_function.handle_cancel_processing('test-upload-123', context)
        
        # Verify response
        assert result['statusCode'] == 200
        response_body = json.loads(result['body'])
        assert response_body['status'] == 'cancelled'
        
        # Verify service calls
        mock_status_service.get_status.assert_called_once_with('test-upload-123')
        mock_cancel_workflow.assert_called_once()
    
    @patch('lambda_function.status_service')
    def test_handle_cancel_processing_already_completed(self, mock_status_service):
        """Test cancel processing API handler for already completed processing."""
        # Mock status service
        mock_status_service.get_status.return_value = {
            'status': 'completed',
            'progress': {'completedBatches': 5, 'totalBatches': 5}
        }
        
        # Create mock context
        context = Mock()
        context.aws_request_id = 'test-request-123'
        
        # Call handler
        result = lambda_function.handle_cancel_processing('test-upload-123', context)
        
        # Verify response
        assert result['statusCode'] == 409  # Conflict
        response_body = json.loads(result['body'])
        assert 'Cannot cancel processing - already completed' in response_body['error']['message']
    
    @patch('lambda_function.status_service')
    def test_handle_cancel_processing_not_found(self, mock_status_service):
        """Test cancel processing API handler for non-existent processing."""
        # Mock status service to raise not found error
        mock_status_service.get_status.side_effect = StatusNotFoundError('test-upload-123')
        
        # Create mock context
        context = Mock()
        context.aws_request_id = 'test-request-123'
        
        # Call handler
        result = lambda_function.handle_cancel_processing('test-upload-123', context)
        
        # Verify response
        assert result['statusCode'] == 404  # Not Found
    
    @patch('boto3.client')
    def test_purge_upload_messages(self, mock_boto3_client):
        """Test SQS message purging functionality."""
        # Mock SQS client
        mock_sqs = Mock()
        mock_boto3_client.return_value = mock_sqs
        
        # Mock SQS responses
        mock_sqs.receive_message.side_effect = [
            {
                'Messages': [
                    {
                        'MessageId': 'msg-1',
                        'ReceiptHandle': 'handle-1',
                        'Body': json.dumps({'uploadId': 'test-upload-123', 'batch_id': 'batch-1'})
                    },
                    {
                        'MessageId': 'msg-2',
                        'ReceiptHandle': 'handle-2',
                        'Body': json.dumps({'uploadId': 'other-upload', 'batch_id': 'batch-2'})
                    }
                ]
            },
            {'Messages': []}  # No more messages
        ]
        
        mock_sqs.delete_message_batch.return_value = {
            'Successful': [{'Id': 'msg-1'}],
            'Failed': []
        }
        
        # Call purge function
        lambda_function.purge_upload_messages(mock_sqs, 'test-queue-url', 'test-upload-123')
        
        # Verify SQS calls
        assert mock_sqs.receive_message.call_count == 2
        mock_sqs.delete_message_batch.assert_called_once_with(
            QueueUrl='test-queue-url',
            Entries=[{'Id': 'msg-1', 'ReceiptHandle': 'handle-1'}]
        )


if __name__ == '__main__':
    pytest.main([__file__])