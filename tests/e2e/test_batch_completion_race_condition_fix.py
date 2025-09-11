"""
End-to-end test for the batch completion race condition fix.

This test validates that the atomic batch completion prevents race conditions
and ensures proper completion tracking for multi-batch file processing.
"""

import pytest
import json
import time
import threading
from unittest.mock import Mock, patch, MagicMock
import boto3
from moto import mock_aws

# Import the modules we're testing
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'deepseek-caller'))

from atomic_status_service import AtomicStatusService
from dynamodb_utils import DynamoDBUtils

# Import from deepseek-caller specifically
deepseek_caller_path = os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'deepseek-caller')
sys.path.insert(0, deepseek_caller_path)
from lambda_function import process_batch_with_deepseek


@mock_aws
class TestBatchCompletionRaceConditionFix:
    """End-to-end test for batch completion race condition fix."""
    
    def setup_method(self, method):
        """Set up test environment."""
        # Create mock DynamoDB tables
        self.dynamodb = boto3.client('dynamodb', region_name='ap-southeast-1')
        
        # Create ProcessingStatus table
        self.status_table_name = 'ProcessingStatus'
        self.dynamodb.create_table(
            TableName=self.status_table_name,
            KeySchema=[
                {'AttributeName': 'uploadId', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'uploadId', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Create Leads table
        self.leads_table_name = 'easy-crm-leads-test'
        self.dynamodb.create_table(
            TableName=self.leads_table_name,
            KeySchema=[
                {'AttributeName': 'leadId', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'leadId', 'AttributeType': 'S'},
                {'AttributeName': 'email', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
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
        
        # Initialize services
        self.status_service = AtomicStatusService(
            dynamodb_client=self.dynamodb,
            table_name=self.status_table_name
        )
        
        self.db_utils = DynamoDBUtils(
            table_name=self.leads_table_name,
            region='ap-southeast-1'
        )
        
        # Test data
        self.upload_id = 'test-race-condition-fix-123'
        self.file_name = 'test-14-batches.xlsx'
        self.file_size = 140000
        self.total_batches = 14
    
    def create_mock_batch_data(self, batch_number: int, leads_count: int = 10) -> dict:
        """Create mock batch data for testing."""
        leads = []
        for i in range(leads_count):
            leads.append({
                'firstName': f'Test{batch_number}_{i}',
                'lastName': f'User{batch_number}_{i}',
                'email': f'test{batch_number}_{i}@example.com',
                'company': f'Company{batch_number}_{i}',
                'phone': f'+1-555-{batch_number:03d}-{i:04d}',
                'title': f'Title{batch_number}_{i}'
            })
        
        return {
            'batch_id': f'batch-{batch_number}-{self.upload_id}',
            'upload_id': self.upload_id,
            'source_file': self.file_name,
            'batch_number': batch_number,
            'total_batches': self.total_batches,
            'leads': leads
        }
    
    @patch('lambda_function.DeepSeekClient')
    def test_sequential_batch_processing_with_atomic_completion(self, mock_deepseek_client):
        """Test sequential batch processing with atomic completion."""
        # Mock DeepSeek client to return standardized data
        mock_client_instance = MagicMock()
        mock_deepseek_client.return_value = mock_client_instance
        
        def mock_standardize_leads(raw_data):
            # Return the same data but "standardized"
            return raw_data
        
        mock_client_instance.standardize_leads = mock_standardize_leads
        
        # Create initial status
        self.status_service.create_status(
            upload_id=self.upload_id,
            file_name=self.file_name,
            file_size=self.file_size,
            initial_status='processing'
        )
        
        # Set up batch processing
        self.status_service.update_status(
            upload_id=self.upload_id,
            stage='batch_processing',
            progress={
                'totalBatches': self.total_batches,
                'completedBatches': 0,
                'totalLeads': 140,
                'processedLeads': 0
            }
        )
        
        # Process all batches sequentially
        for batch_num in range(1, self.total_batches + 1):
            batch_data = self.create_mock_batch_data(batch_num)
            
            # Process batch using the actual DeepSeek caller function
            result = process_batch_with_deepseek(
                batch_data=batch_data,
                db_utils=self.db_utils,
                status_service=self.status_service
            )
            
            # Verify batch processing succeeded
            assert result['batch_number'] == batch_num
            assert result['upload_id'] == self.upload_id
            assert result['processed_leads'] == 10
            
            # Check status after each batch
            status = self.status_service.get_status(self.upload_id)
            progress = status.get('progress', {})
            
            assert progress.get('completedBatches') == batch_num
            assert progress.get('totalBatches') == self.total_batches
            
            if batch_num == self.total_batches:
                # Last batch should mark as completed
                assert status.get('status') == 'completed'
                assert status.get('stage') == 'completed'
                assert progress.get('percentage') == 100.0
            else:
                # Intermediate batches should remain in processing
                assert status.get('status') == 'processing'
    
    @patch('lambda_function.DeepSeekClient')
    def test_concurrent_batch_processing_race_condition_prevention(self, mock_deepseek_client):
        """Test concurrent batch processing with race condition prevention."""
        # Mock DeepSeek client
        mock_client_instance = MagicMock()
        mock_deepseek_client.return_value = mock_client_instance
        mock_client_instance.standardize_leads = lambda raw_data: raw_data
        
        # Create initial status
        self.status_service.create_status(
            upload_id=self.upload_id,
            file_name=self.file_name,
            file_size=self.file_size,
            initial_status='processing'
        )
        
        # Set up batch processing
        self.status_service.update_status(
            upload_id=self.upload_id,
            stage='batch_processing',
            progress={
                'totalBatches': self.total_batches,
                'completedBatches': 0,
                'totalLeads': 140,
                'processedLeads': 0
            }
        )
        
        # Process first 12 batches sequentially
        for batch_num in range(1, 13):
            batch_data = self.create_mock_batch_data(batch_num)
            process_batch_with_deepseek(
                batch_data=batch_data,
                db_utils=self.db_utils,
                status_service=self.status_service
            )
        
        # Verify we're at 12/14
        status = self.status_service.get_status(self.upload_id)
        assert status['progress']['completedBatches'] == 12
        assert status['status'] == 'processing'
        
        # Now process batches 13 and 14 concurrently to test race condition prevention
        results = []
        errors = []
        
        def process_batch_concurrent(batch_number):
            try:
                batch_data = self.create_mock_batch_data(batch_number)
                result = process_batch_with_deepseek(
                    batch_data=batch_data,
                    db_utils=self.db_utils,
                    status_service=self.status_service
                )
                results.append((batch_number, result))
            except Exception as e:
                errors.append((batch_number, e))
        
        # Start both threads simultaneously
        thread_13 = threading.Thread(target=process_batch_concurrent, args=(13,))
        thread_14 = threading.Thread(target=process_batch_concurrent, args=(14,))
        
        thread_13.start()
        thread_14.start()
        
        # Wait for both to complete
        thread_13.join()
        thread_14.join()
        
        # Verify no errors occurred
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"
        
        # Check final status - should be completed with 14/14
        final_status = self.status_service.get_status(self.upload_id)
        
        # With atomic operations, we should always end up with correct final state
        assert final_status['progress']['completedBatches'] == 14
        assert final_status['progress']['totalBatches'] == 14
        assert final_status['status'] == 'completed'
        assert final_status['stage'] == 'completed'
        assert final_status['progress']['percentage'] == 100.0
        
        # Verify that the total processed leads is correct
        assert final_status['progress']['processedLeads'] == 140  # 14 batches * 10 leads each
    
    def test_force_completion_recovery_mechanism(self):
        """Test the force completion recovery mechanism for stuck processing."""
        # Create initial status
        self.status_service.create_status(
            upload_id=self.upload_id,
            file_name=self.file_name,
            file_size=self.file_size,
            initial_status='processing'
        )
        
        # Simulate a stuck state (all batches completed but status not updated)
        self.status_service.update_status(
            upload_id=self.upload_id,
            stage='batch_processing',
            progress={
                'totalBatches': self.total_batches,
                'completedBatches': self.total_batches,  # All batches completed
                'totalLeads': 140,
                'processedLeads': 140
            }
            # Note: status remains 'processing' - this simulates the bug
        )
        
        # Verify the stuck state
        status = self.status_service.get_batch_completion_status(self.upload_id)
        analysis = status.get('completion_analysis', {})
        assert analysis.get('is_stuck') == True
        assert status.get('status') == 'processing'
        
        # Force completion should detect and fix the stuck state
        result = self.status_service.force_completion_if_stuck(self.upload_id)
        
        # Should now be marked as completed
        assert result.get('status') == 'completed'
        assert result.get('stage') == 'completed'
        assert result.get('progress', {}).get('percentage') == 100.0
        assert result.get('metadata', {}).get('forcedCompletion') == 1
        
        # Verify the fix is persistent
        final_status = self.status_service.get_status(self.upload_id)
        assert final_status.get('status') == 'completed'
    
    def test_completion_analysis_accuracy(self):
        """Test the accuracy of completion analysis for various scenarios."""
        # Test scenario 1: Normal processing (5/10 batches)
        self.status_service.create_status(
            upload_id=self.upload_id,
            file_name=self.file_name,
            file_size=self.file_size,
            initial_status='processing'
        )
        
        self.status_service.update_status(
            upload_id=self.upload_id,
            progress={
                'totalBatches': 10,
                'completedBatches': 5,
                'totalLeads': 100,
                'processedLeads': 50
            }
        )
        
        status = self.status_service.get_batch_completion_status(self.upload_id)
        analysis = status.get('completion_analysis', {})
        
        assert analysis.get('is_completed') == False
        assert analysis.get('completion_percentage') == 50.0
        assert analysis.get('remaining_batches') == 5
        assert analysis.get('is_stuck') == False
        
        # Test scenario 2: Stuck at last batch (9/10 batches, still processing)
        self.status_service.update_status(
            upload_id=self.upload_id,
            progress={
                'totalBatches': 10,
                'completedBatches': 9,
                'totalLeads': 100,
                'processedLeads': 90
            }
        )
        
        status = self.status_service.get_batch_completion_status(self.upload_id)
        analysis = status.get('completion_analysis', {})
        
        assert analysis.get('is_completed') == False
        assert analysis.get('completion_percentage') == 90.0
        assert analysis.get('remaining_batches') == 1
        assert analysis.get('is_stuck') == True  # 9/10 and not completed = stuck
        
        # Test scenario 3: Properly completed (10/10 batches, completed status)
        self.status_service.update_status(
            upload_id=self.upload_id,
            status='completed',
            stage='completed',
            progress={
                'totalBatches': 10,
                'completedBatches': 10,
                'totalLeads': 100,
                'processedLeads': 100,
                'percentage': 100.0
            }
        )
        
        status = self.status_service.get_batch_completion_status(self.upload_id)
        analysis = status.get('completion_analysis', {})
        
        assert analysis.get('is_completed') == True
        assert analysis.get('completion_percentage') == 100.0
        assert analysis.get('remaining_batches') == 0
        assert analysis.get('is_stuck') == False  # Completed properly


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])