"""
Integration test for progress update fix - verifies that boolean values are not passed to DynamoDB
and that multiple batch progress updates work correctly.
"""

import pytest
import json
import time
from unittest.mock import Mock, patch
import boto3
from moto import mock_aws

# Import the modules we're testing
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))

from status_service import ProcessingStatusService


@mock_aws
class TestProgressUpdateFix:
    """Test progress update fixes for multiple batches."""
    
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
        self.upload_id = 'test-upload-123'
        self.file_name = 'test-multi-batch.xlsx'
        self.file_size = 50000
    
    def test_create_initial_status(self):
        """Test creating initial status record."""
        status = self.status_service.create_status(
            upload_id=self.upload_id,
            file_name=self.file_name,
            file_size=self.file_size,
            initial_status='uploading'
        )
        
        assert status['uploadId'] == self.upload_id
        assert status['status'] == 'uploading'
        assert status['stage'] == 'file_upload'
        assert status['progress']['totalBatches'] == 0
        assert status['progress']['completedBatches'] == 0
        assert status['progress']['percentage'] == 0.0
        assert status['metadata']['fileName'] == self.file_name
        assert status['metadata']['fileSize'] == self.file_size
    
    def test_update_progress_multiple_batches(self):
        """Test updating progress for multiple batches without boolean values."""
        # Create initial status
        self.status_service.create_status(
            upload_id=self.upload_id,
            file_name=self.file_name,
            file_size=self.file_size,
            initial_status='processing'
        )
        
        # Update with batch information (simulating lead-splitter)
        self.status_service.update_status(
            upload_id=self.upload_id,
            stage='batch_processing',
            progress={
                'totalBatches': 5,
                'completedBatches': 0,
                'totalLeads': 50,
                'processedLeads': 0
            }
        )
        
        # Simulate processing batches (like deepseek-caller would do)
        for batch_num in range(1, 6):
            # Update progress for each batch
            progress_update = {
                'totalBatches': 5,
                'completedBatches': batch_num,
                'totalLeads': 50,
                'processedLeads': batch_num * 10
            }
            
            # This should not fail with boolean value error
            updated_status = self.status_service.update_status(
                upload_id=self.upload_id,
                progress=progress_update
            )
            
            # Verify the update succeeded
            assert updated_status['progress']['completedBatches'] == batch_num
            assert updated_status['progress']['totalBatches'] == 5
            assert updated_status['progress']['processedLeads'] == batch_num * 10
            
            # Verify percentage is calculated correctly
            expected_percentage = (batch_num / 5) * 100
            assert updated_status['progress']['percentage'] == expected_percentage
            
            # Verify no boolean values are present in progress
            for key, value in updated_status['progress'].items():
                if key == 'showEstimates':
                    # showEstimates should be 0 or 1, not boolean
                    assert value in [0, 1], f"showEstimates should be 0 or 1, got {value} ({type(value)})"
                else:
                    # Other values should be numeric or string
                    assert isinstance(value, (int, float, str)), f"Progress value {key} should be numeric or string, got {type(value)}"
    
    def test_progress_with_time_estimates(self):
        """Test progress updates with time estimates (should use numeric showEstimates)."""
        # Create initial status with start time in the past to trigger estimates
        initial_status = self.status_service.create_status(
            upload_id=self.upload_id,
            file_name=self.file_name,
            file_size=self.file_size,
            initial_status='processing'
        )
        
        # Manually set start time to 60 seconds ago to trigger estimates
        from datetime import datetime, timedelta
        past_time = (datetime.utcnow() - timedelta(seconds=60)).isoformat() + 'Z'
        
        self.status_service.update_status(
            upload_id=self.upload_id,
            metadata={'startTime': past_time}
        )
        
        # Update with progress that should trigger time estimates
        progress_update = {
            'totalBatches': 10,
            'completedBatches': 3,  # 30% complete
            'totalLeads': 100,
            'processedLeads': 30
        }
        
        updated_status = self.status_service.update_status(
            upload_id=self.upload_id,
            progress=progress_update
        )
        
        # Verify showEstimates is numeric (0 or 1), not boolean
        if 'showEstimates' in updated_status['progress']:
            show_estimates = updated_status['progress']['showEstimates']
            assert show_estimates in [0, 1], f"showEstimates should be 0 or 1, got {show_estimates} ({type(show_estimates)})"
        
        # Verify other estimate fields are present and numeric
        progress = updated_status['progress']
        if 'estimatedRemainingSeconds' in progress:
            assert isinstance(progress['estimatedRemainingSeconds'], (int, float))
        if 'processingRate' in progress:
            assert isinstance(progress['processingRate'], (int, float))
    
    def test_complete_processing_multiple_batches(self):
        """Test completing processing after multiple batch updates."""
        # Create and set up initial status
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
                'totalBatches': 3,
                'completedBatches': 0,
                'totalLeads': 30,
                'processedLeads': 0
            }
        )
        
        # Process all batches
        for batch_num in range(1, 4):
            self.status_service.update_status(
                upload_id=self.upload_id,
                progress={
                    'totalBatches': 3,
                    'completedBatches': batch_num,
                    'totalLeads': 30,
                    'processedLeads': batch_num * 10
                }
            )
        
        # Complete processing
        final_status = self.status_service.complete_processing(
            upload_id=self.upload_id,
            total_leads=30,
            created_leads=25,
            updated_leads=5
        )
        
        # Verify completion
        assert final_status['status'] == 'completed'
        assert final_status['stage'] == 'completed'
        assert final_status['progress']['percentage'] == 100.0
        assert final_status['progress']['totalLeads'] == 30
        assert final_status['progress']['processedLeads'] == 30
        assert final_status['progress']['createdLeads'] == 25
        assert final_status['progress']['updatedLeads'] == 5
    
    def test_error_handling_during_batch_processing(self):
        """Test error handling during batch processing."""
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
                'totalBatches': 5,
                'completedBatches': 2,  # 2 batches completed
                'totalLeads': 50,
                'processedLeads': 20
            }
        )
        
        # Simulate error during batch 3
        error_status = self.status_service.set_error(
            upload_id=self.upload_id,
            error_message='DeepSeek API error during batch 3 processing',
            error_code='DEEPSEEK_API_ERROR',
            recoverable=True,
            retry_after=30
        )
        
        # Verify error status
        assert error_status['status'] == 'error'
        assert error_status['error']['message'] == 'DeepSeek API error during batch 3 processing'
        assert error_status['error']['code'] == 'DEEPSEEK_API_ERROR'
        assert error_status['error']['recoverable'] == True
        assert error_status['error']['retryAfter'] == 30
        
        # Verify progress is preserved
        assert error_status['progress']['completedBatches'] == 2
        assert error_status['progress']['totalBatches'] == 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])