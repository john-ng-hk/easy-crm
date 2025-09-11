"""
Test for concurrent batch completion issue - reproduces the race condition
where multiple batches complete simultaneously and cause the progress to get stuck.
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

from status_service import ProcessingStatusService


@mock_aws
class TestConcurrentBatchCompletion:
    """Test concurrent batch completion scenarios."""
    
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
        
        # Initialize status service
        self.status_service = ProcessingStatusService(
            dynamodb_client=self.dynamodb,
            table_name=self.table_name
        )
        
        # Test data
        self.upload_id = 'test-concurrent-upload-123'
        self.file_name = 'test-concurrent-batches.xlsx'
        self.file_size = 140000  # Large file with 14 batches
    
    def simulate_batch_completion(self, batch_number, total_batches, leads_per_batch=10):
        """
        Simulate a single batch completion - this mimics what DeepSeek caller does.
        
        Args:
            batch_number: The batch number being completed
            total_batches: Total number of batches
            leads_per_batch: Number of leads in this batch
        """
        try:
            # Get current status (this is where the race condition happens)
            current_status = self.status_service.get_status(self.upload_id)
            current_progress = current_status.get('progress', {})
            
            # Calculate updated progress (read-modify-write - NOT ATOMIC)
            completed_batches = current_progress.get('completedBatches', 0) + 1
            total_batches_count = current_progress.get('totalBatches', total_batches)
            processed_leads = current_progress.get('processedLeads', 0) + leads_per_batch
            
            # Update progress
            updated_progress = {
                'totalBatches': total_batches_count,
                'completedBatches': completed_batches,
                'processedLeads': processed_leads
            }
            
            # Check if all batches are completed
            if completed_batches >= total_batches_count:
                # Mark as completed
                result = self.status_service.update_status(
                    upload_id=self.upload_id,
                    status='completed',
                    stage='completed',
                    progress=updated_progress
                )
                print(f"Batch {batch_number}: COMPLETED - {completed_batches}/{total_batches_count}")
                return result
            else:
                # Update progress
                result = self.status_service.update_status(
                    upload_id=self.upload_id,
                    progress=updated_progress
                )
                print(f"Batch {batch_number}: Progress - {completed_batches}/{total_batches_count}")
                return result
                
        except Exception as e:
            print(f"Batch {batch_number}: ERROR - {str(e)}")
            raise
    
    def test_concurrent_batch_completion_race_condition(self):
        """Test that demonstrates the race condition with concurrent batch completion."""
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
        
        # Process first 12 batches sequentially (no race condition)
        for batch_num in range(1, 13):
            self.simulate_batch_completion(batch_num, total_batches)
        
        # Verify we're at 12/14
        status = self.status_service.get_status(self.upload_id)
        assert status['progress']['completedBatches'] == 12
        assert status['status'] == 'processing'
        
        # Now simulate concurrent completion of batches 13 and 14
        # This is where the race condition occurs in production
        results = []
        errors = []
        
        def complete_batch_13():
            try:
                result = self.simulate_batch_completion(13, total_batches)
                results.append(('batch_13', result))
            except Exception as e:
                errors.append(('batch_13', e))
        
        def complete_batch_14():
            try:
                result = self.simulate_batch_completion(14, total_batches)
                results.append(('batch_14', result))
            except Exception as e:
                errors.append(('batch_14', e))
        
        # Start both threads simultaneously to create race condition
        thread_13 = threading.Thread(target=complete_batch_13)
        thread_14 = threading.Thread(target=complete_batch_14)
        
        thread_13.start()
        thread_14.start()
        
        # Wait for both to complete
        thread_13.join()
        thread_14.join()
        
        # Check for errors
        if errors:
            print(f"Errors occurred: {errors}")
        
        # Check final status
        final_status = self.status_service.get_status(self.upload_id)
        print(f"Final status: {final_status['status']}")
        print(f"Final progress: {final_status['progress']['completedBatches']}/{final_status['progress']['totalBatches']}")
        
        # This test demonstrates the race condition - sometimes it will be stuck at 13/14
        # In a real scenario, this would cause the progress indicator to get stuck
        
        # The issue is that both threads might read completedBatches=12 and both increment to 13
        # instead of one reading 12->13 and the other reading 13->14
        
        # Expected behavior: should be completed with 14/14
        # Actual behavior (with race condition): might be stuck at 13/14
        
        print(f"Race condition test completed. Final state: {final_status['progress']['completedBatches']}/{final_status['progress']['totalBatches']}")
        
        # Note: This test might pass sometimes and fail other times due to the race condition
        # The fix should make it always pass
    
    def test_atomic_batch_completion_fix(self):
        """Test the atomic batch completion fix using DynamoDB atomic counters."""
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
        
        # This test will use the fixed atomic increment method
        # (We'll implement this fix after confirming the race condition)
        
        # For now, this is a placeholder for the fix
        # The fix should use DynamoDB's atomic ADD operation instead of read-modify-write
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])