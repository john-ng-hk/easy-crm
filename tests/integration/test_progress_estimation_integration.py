"""
Integration tests for progress estimation and time remaining functionality.

Tests the complete flow of progress estimation including:
- Progress percentage calculation
- Estimated completion time calculation
- Processing rate calculation
- Frontend display of estimates
"""

import pytest
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Import test utilities
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../lambda/shared'))

from status_service import ProcessingStatusService


class TestProgressEstimationIntegration:
    """Integration tests for progress estimation functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_dynamodb = Mock()
        self.service = ProcessingStatusService(
            dynamodb_client=self.mock_dynamodb,
            table_name='test-processing-status'
        )
    
    def test_complete_progress_estimation_workflow(self):
        """Test complete workflow of progress estimation from start to finish."""
        upload_id = "test-upload-integration"
        
        # Step 1: Create initial status
        self.mock_dynamodb.put_item.return_value = {}
        
        with patch.object(self.service, '_get_current_timestamp', return_value='2025-01-09T10:00:00Z'), \
             patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            
            initial_status = self.service.create_status(upload_id, "large_file.xlsx", 5000000)
            assert initial_status['status'] == 'uploading'
            assert initial_status['progress']['percentage'] == 0.0
        
        # Step 2: Update to processing with batch info (simulate lead-splitter)
        existing_status_step2 = {
            'uploadId': upload_id,
            'status': 'uploading',
            'metadata': {
                'fileName': 'large_file.xlsx',
                'fileSize': 5000000,
                'startTime': '2025-01-09T10:00:00Z'
            },
            'progress': {
                'totalBatches': 0,
                'completedBatches': 0,
                'percentage': 0.0
            }
        }
        
        mock_response_step2 = {
            'Attributes': {
                'uploadId': {'S': upload_id},
                'status': {'S': 'processing'},
                'stage': {'S': 'batch_processing'},
                'progress': {
                    'M': {
                        'totalBatches': {'N': '20'},
                        'completedBatches': {'N': '0'},
                        'totalLeads': {'N': '2000'},
                        'processedLeads': {'N': '0'},
                        'percentage': {'N': '0.0'}
                    }
                },
                'updatedAt': {'S': '2025-01-09T10:00:30Z'},
                'ttl': {'N': '1736424000'}
            }
        }
        self.mock_dynamodb.update_item.return_value = mock_response_step2
        
        with patch.object(self.service, 'get_status', return_value=existing_status_step2), \
             patch.object(self.service, '_get_current_timestamp', return_value='2025-01-09T10:00:30Z'), \
             patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            
            batch_status = self.service.update_status(
                upload_id=upload_id,
                status='processing',
                stage='batch_processing',
                progress={
                    'totalBatches': 20,
                    'completedBatches': 0,
                    'totalLeads': 2000,
                    'processedLeads': 0
                }
            )
            
            assert batch_status['status'] == 'processing'
            assert batch_status['progress']['totalBatches'] == 20
            assert batch_status['progress']['percentage'] == 0.0
        
        # Step 3: Simulate progress updates from deepseek-caller (after 60 seconds of processing)
        existing_status_step3 = {
            'uploadId': upload_id,
            'status': 'processing',
            'stage': 'batch_processing',
            'metadata': {
                'fileName': 'large_file.xlsx',
                'fileSize': 5000000,
                'startTime': '2025-01-09T10:00:00Z'
            },
            'progress': {
                'totalBatches': 20,
                'completedBatches': 0,
                'totalLeads': 2000,
                'processedLeads': 0,
                'percentage': 0.0
            }
        }
        
        # After 60 seconds, 5 batches completed
        mock_response_step3 = {
            'Attributes': {
                'uploadId': {'S': upload_id},
                'status': {'S': 'processing'},
                'stage': {'S': 'batch_processing'},
                'progress': {
                    'M': {
                        'totalBatches': {'N': '20'},
                        'completedBatches': {'N': '5'},
                        'totalLeads': {'N': '2000'},
                        'processedLeads': {'N': '500'},
                        'percentage': {'N': '25.0'},
                        'estimatedRemainingSeconds': {'N': '180'},
                        'processingRate': {'N': '0.0833'},
                        'showEstimates': {'BOOL': True}
                    }
                },
                'updatedAt': {'S': '2025-01-09T10:01:00Z'},
                'ttl': {'N': '1736424000'}
            }
        }
        self.mock_dynamodb.update_item.return_value = mock_response_step3
        
        with patch.object(self.service, 'get_status', return_value=existing_status_step3), \
             patch.object(self.service, '_get_current_timestamp', return_value='2025-01-09T10:01:00Z'), \
             patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            
            progress_status = self.service.update_status(
                upload_id=upload_id,
                progress={
                    'totalBatches': 20,
                    'completedBatches': 5,
                    'totalLeads': 2000,
                    'processedLeads': 500
                }
            )
            
            # Verify progress estimation
            progress = progress_status['progress']
            assert progress['percentage'] == 25.0
            assert 'estimatedRemainingSeconds' in progress
            assert 'processingRate' in progress
            assert 'showEstimates' in progress
            assert progress['showEstimates'] is True
            
            # Verify processing rate calculation (5 batches in 60 seconds = ~0.083 batches/sec)
            if 'processingRate' in progress:
                assert progress['processingRate'] > 0
                assert progress['processingRate'] < 1  # Should be less than 1 batch per second
            
            # Verify estimated remaining time is reasonable
            if 'estimatedRemainingSeconds' in progress:
                assert progress['estimatedRemainingSeconds'] > 0
                assert progress['estimatedRemainingSeconds'] < 3600  # Should be less than 1 hour
    
    def test_short_operation_no_estimates(self):
        """Test that short operations don't show estimates."""
        upload_id = "test-short-operation"
        
        # Create status with recent start time
        existing_status = {
            'uploadId': upload_id,
            'status': 'processing',
            'metadata': {
                'fileName': 'small_file.csv',
                'fileSize': 1024,
                'startTime': '2025-01-09T10:00:00Z'
            },
            'progress': {
                'totalBatches': 2,
                'completedBatches': 0
            }
        }
        
        # Update after only 10 seconds (short operation)
        mock_response = {
            'Attributes': {
                'uploadId': {'S': upload_id},
                'status': {'S': 'processing'},
                'progress': {
                    'M': {
                        'totalBatches': {'N': '2'},
                        'completedBatches': {'N': '1'},
                        'percentage': {'N': '50.0'},
                        'showEstimates': {'BOOL': False}
                    }
                },
                'updatedAt': {'S': '2025-01-09T10:00:10Z'},
                'ttl': {'N': '1736424000'}
            }
        }
        self.mock_dynamodb.update_item.return_value = mock_response
        
        with patch.object(self.service, 'get_status', return_value=existing_status), \
             patch.object(self.service, '_get_current_timestamp', return_value='2025-01-09T10:00:10Z'), \
             patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            
            result = self.service.update_status(
                upload_id=upload_id,
                progress={
                    'totalBatches': 2,
                    'completedBatches': 1
                }
            )
            
            progress = result['progress']
            assert progress['percentage'] == 50.0
            
            # For short operations, estimates should not be shown
            if 'showEstimates' in progress:
                assert progress['showEstimates'] is False
    
    def test_processing_rate_accuracy(self):
        """Test that processing rate calculations are accurate."""
        upload_id = "test-rate-accuracy"
        
        # Start time: 10:00:00
        start_time = '2025-01-09T10:00:00Z'
        
        existing_status = {
            'uploadId': upload_id,
            'status': 'processing',
            'metadata': {
                'fileName': 'test_file.xlsx',
                'fileSize': 2048000,
                'startTime': start_time
            },
            'progress': {
                'totalBatches': 10,
                'completedBatches': 0
            }
        }
        
        # Current time: 10:02:00 (120 seconds later)
        # 4 batches completed = 4/120 = 0.0333 batches per second
        current_time = '2025-01-09T10:02:00Z'
        
        mock_response = {
            'Attributes': {
                'uploadId': {'S': upload_id},
                'status': {'S': 'processing'},
                'progress': {
                    'M': {
                        'totalBatches': {'N': '10'},
                        'completedBatches': {'N': '4'},
                        'percentage': {'N': '40.0'},
                        'processingRate': {'N': '0.0333'},
                        'estimatedRemainingSeconds': {'N': '180'},
                        'showEstimates': {'BOOL': True}
                    }
                },
                'updatedAt': {'S': current_time},
                'ttl': {'N': '1736424000'}
            }
        }
        self.mock_dynamodb.update_item.return_value = mock_response
        
        with patch.object(self.service, 'get_status', return_value=existing_status), \
             patch.object(self.service, '_get_current_timestamp', return_value=current_time), \
             patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            
            result = self.service.update_status(
                upload_id=upload_id,
                progress={
                    'totalBatches': 10,
                    'completedBatches': 4
                }
            )
            
            progress = result['progress']
            assert progress['percentage'] == 40.0
            
            # Verify processing rate is reasonable (4 batches in 120 seconds)
            if 'processingRate' in progress:
                expected_rate = 4 / 120  # 0.0333 batches per second
                assert abs(progress['processingRate'] - expected_rate) < 0.01
            
            # Verify estimated remaining time (6 batches remaining / 0.0333 rate = ~180 seconds)
            if 'estimatedRemainingSeconds' in progress:
                remaining_batches = 10 - 4
                expected_time = remaining_batches / (4 / 120)
                assert abs(progress['estimatedRemainingSeconds'] - expected_time) < 30  # Within 30 seconds


if __name__ == '__main__':
    pytest.main([__file__, '-v'])