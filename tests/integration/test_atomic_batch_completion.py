"""
Test for atomic batch completion - verifies that the atomic increment prevents
race conditions and ensures proper completion tracking.
"""

import pytest
import json
import time
import threading
from unittest.mock import Mock, patch
import boto3
from moto import mock_aws

# Import the modules we're testing
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))

from atomic_status_service import AtomicStatusService


@mock_aws
class TestAtomicBatchCompletion:
    """Test atomic batch completion functionality."""
    
    def setup_method(self, method):
        """Set up test environment."""
        # Create mock DynamoDB table
        self.dynamodb = boto3.client('dynamodb', region_name='ap-southeast-1')
        
        # Create ProcessingStatus table
        self.table_name = 'ProcessingStatus'
        self.dynamodb.create_table(
            TableName=self.table_name,
            KeySchema=[
                {'AttributeName': 'uploadId', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'uploadId', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Initialize atomic status service
        self.status_service = AtomicStatusService(
            dynamodb_client=self.dynamodb,
            table_name=self.table_name
        )
        
        # Test data
        self.upload_id = 'test-atomic-upload-123'
        self.file_name = 'test-atomic-batches.xlsx'
        self.file_size = 140000  # Large file with 14 batches
    
    def test_atomic_increment_single_batch(self):
        """Test atomic increment for a single batch."""
        total_batches = 5
        
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
                'totalBatches': total_batches,
                'completedBatches': 0,
                'totalLeads': 50,
                'processedLeads': 0
            }
        )
        
        # Process batches using atomic increment
        for batch_num in range(1, total_batches + 1):
            result = self.status_service.atomic_increment_batch_completion(
                upload_id=self.upload_id,
                leads_processed=10
            )
            
            progress = result.get('progress', {})
            completed_batches = progress.get('completedBatches', 0)
            
            assert completed_batches == batch_num
            
            if batch_num == total_batches:
                # Last batch should mark as completed
                assert result.get('status') == 'completed'
                assert result.get('stage') == 'completed'
                assert progress.get('percentage') == 100.0
            else:
                # Intermediate batches should remain in processing
                assert result.get('status') == 'processing'
    
    def test_atomic_increment_concurrent_batches(self):
        """Test atomic increment with concurrent batch completions."""
        total_batches = 14
        
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
                'totalBatches': total_batches,
                'completedBatches': 0,
                'totalLeads': 140,
                'processedLeads': 0
            }
        )
        
        # Process first 12 batches sequentially
        for batch_num in range(1, 13):
            self.status_service.atomic_increment_batch_completion(
                upload_id=self.upload_id,
                leads_processed=10
            )
        
        # Verify we're at 12/14
        status = self.status_service.get_status(self.upload_id)
        assert status['progress']['completedBatches'] == 12
        assert status['status'] == 'processing'
        
        # Now simulate concurrent completion of batches 13 and 14
        results = []
        errors = []
        
        def complete_batch_atomic():
            try:
                result = self.status_service.atomic_increment_batch_completion(
                    upload_id=self.upload_id,
                    leads_processed=10
                )
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Start both threads simultaneously
        thread_13 = threading.Thread(target=complete_batch_atomic)
        thread_14 = threading.Thread(target=complete_batch_atomic)
        
        thread_13.start()
        thread_14.start()
        
        # Wait for both to complete
        thread_13.join()
        thread_14.join()
        
        # Check for errors
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"
        
        # Check final status
        final_status = self.status_service.get_status(self.upload_id)
        
        # With atomic operations, we should always end up with 14/14 and completed status
        assert final_status['progress']['completedBatches'] == 14
        assert final_status['progress']['totalBatches'] == 14
        assert final_status['status'] == 'completed'
        assert final_status['stage'] == 'completed'
        assert final_status['progress']['percentage'] == 100.0
        
        # Verify that at least one of the results shows completion
        completion_results = [r for r in results if r.get('status') == 'completed']
        assert len(completion_results) >= 1, "At least one result should show completion"
    
    def test_batch_completion_status_analysis(self):
        """Test the batch completion status analysis functionality."""
        total_batches = 5
        
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
                'totalBatches': total_batches,
                'completedBatches': 0,
                'totalLeads': 50,
                'processedLeads': 0
            }
        )
        
        # Process 4 out of 5 batches (simulate stuck at 4/5)
        for batch_num in range(1, 5):
            self.status_service.atomic_increment_batch_completion(
                upload_id=self.upload_id,
                leads_processed=10
            )
        
        # Get completion status analysis
        status_with_analysis = self.status_service.get_batch_completion_status(self.upload_id)
        analysis = status_with_analysis.get('completion_analysis', {})
        
        # Should detect that it's stuck at the last batch
        assert analysis.get('is_completed') == False
        assert analysis.get('completion_percentage') == 80.0  # 4/5 = 80%
        assert analysis.get('remaining_batches') == 1
        assert analysis.get('is_stuck') == True  # 4/5 and not completed = stuck
    
    def test_force_completion_if_stuck(self):
        """Test the force completion functionality for stuck processing."""
        total_batches = 3
        
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
                'totalBatches': total_batches,
                'completedBatches': 0,
                'totalLeads': 30,
                'processedLeads': 0
            }
        )
        
        # Process 2 out of 3 batches (simulate stuck at 2/3)
        for batch_num in range(1, 3):
            self.status_service.atomic_increment_batch_completion(
                upload_id=self.upload_id,
                leads_processed=10
            )
        
        # Manually set completedBatches to 3 but keep status as processing (simulate the bug)
        self.status_service.update_status(
            upload_id=self.upload_id,
            progress={
                'totalBatches': total_batches,
                'completedBatches': total_batches,  # All batches completed
                'totalLeads': 30,
                'processedLeads': 30
            }
            # Note: status remains 'processing' - this simulates the bug
        )
        
        # Force completion should detect and fix the stuck state
        result = self.status_service.force_completion_if_stuck(self.upload_id)
        
        # Should now be marked as completed
        assert result.get('status') == 'completed'
        assert result.get('stage') == 'completed'
        assert result.get('progress', {}).get('percentage') == 100.0
        assert result.get('metadata', {}).get('forcedCompletion') == 1  # Numeric value for DynamoDB compatibility
    
    def test_atomic_increment_with_zero_batches(self):
        """Test atomic increment edge case with zero total batches."""
        # Create initial status with zero batches
        self.status_service.create_status(
            upload_id=self.upload_id,
            file_name=self.file_name,
            file_size=0,
            initial_status='processing'
        )
        
        # Set up with zero batches (edge case)
        self.status_service.update_status(
            upload_id=self.upload_id,
            stage='batch_processing',
            progress={
                'totalBatches': 0,
                'completedBatches': 0,
                'totalLeads': 0,
                'processedLeads': 0
            }
        )
        
        # Atomic increment should handle this gracefully
        result = self.status_service.atomic_increment_batch_completion(
            upload_id=self.upload_id,
            leads_processed=0
        )
        
        # Should increment to 1 completed batch but not mark as completed (since total is 0)
        assert result.get('progress', {}).get('completedBatches') == 1
        assert result.get('status') == 'processing'  # Should not auto-complete with 0 total batches


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])