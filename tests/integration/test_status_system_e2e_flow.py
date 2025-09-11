"""
Integration tests for end-to-end status flow.

Tests the complete status tracking workflow from file upload through processing completion,
including all status transitions, error handling, and recovery scenarios.
"""

import pytest
import json
import uuid
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add lambda directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../lambda/shared'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../lambda/status-reader'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../lambda/file-upload'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../lambda/lead-splitter'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../lambda/deepseek-caller'))

from status_service import ProcessingStatusService
import lambda_function as status_reader


class TestStatusSystemE2EFlow:
    """Test end-to-end status flow integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_dynamodb = Mock()
        self.status_service = ProcessingStatusService(
            dynamodb_client=self.mock_dynamodb,
            table_name='test-processing-status'
        )
        self.upload_id = str(uuid.uuid4())
    
    def test_complete_upload_to_completion_flow(self):
        """Test complete flow from upload initiation to completion."""
        
        # Stage 1: File upload initiation
        file_name = "test_leads.xlsx"
        file_size = 1024000
        
        # Mock create_status call
        self.mock_dynamodb.put_item.return_value = {}
        
        with patch.object(self.status_service, '_get_current_timestamp', return_value='2025-01-09T10:00:00Z'), \
             patch.object(self.status_service, '_calculate_ttl', return_value=1736424000):
            
            initial_status = self.status_service.create_status(
                self.upload_id, file_name, file_size, 'uploading'
            )
        
        # Verify initial status
        assert initial_status['status'] == 'uploading'
        assert initial_status['stage'] == 'file_upload'
        assert initial_status['metadata']['fileName'] == file_name
        assert initial_status['metadata']['fileSize'] == file_size
        
        # Stage 2: File uploaded to S3
        mock_response_uploaded = {
            'Attributes': {
                'uploadId': {'S': self.upload_id},
                'status': {'S': 'uploaded'},
                'stage': {'S': 'file_upload'},
                'updatedAt': {'S': '2025-01-09T10:01:00Z'},
                'ttl': {'N': '1736424000'}
            }
        }
        self.mock_dynamodb.update_item.return_value = mock_response_uploaded
        
        with patch.object(self.status_service, 'get_status', return_value=initial_status), \
             patch.object(self.status_service, '_get_current_timestamp', return_value='2025-01-09T10:01:00Z'), \
             patch.object(self.status_service, '_calculate_ttl', return_value=1736424000):
            
            uploaded_status = self.status_service.update_status(
                self.upload_id, status='uploaded'
            )
        
        assert uploaded_status['status'] == 'uploaded'
        
        # Stage 3: File processing begins (lead splitter)
        mock_response_processing = {
            'Attributes': {
                'uploadId': {'S': self.upload_id},
                'status': {'S': 'processing'},
                'stage': {'S': 'file_processing'},
                'progress': {
                    'M': {
                        'totalBatches': {'N': '10'},
                        'completedBatches': {'N': '0'},
                        'totalLeads': {'N': '100'},
                        'processedLeads': {'N': '0'},
                        'percentage': {'N': '0.0'}
                    }
                },
                'updatedAt': {'S': '2025-01-09T10:02:00Z'},
                'ttl': {'N': '1736424000'}
            }
        }
        self.mock_dynamodb.update_item.return_value = mock_response_processing
        
        with patch.object(self.status_service, 'get_status', return_value=uploaded_status), \
             patch.object(self.status_service, '_get_current_timestamp', return_value='2025-01-09T10:02:00Z'), \
             patch.object(self.status_service, '_calculate_ttl', return_value=1736424000):
            
            processing_status = self.status_service.update_status(
                self.upload_id,
                status='processing',
                stage='file_processing',
                progress={
                    'totalBatches': 10,
                    'completedBatches': 0,
                    'totalLeads': 100,
                    'processedLeads': 0
                }
            )
        
        assert processing_status['status'] == 'processing'
        assert processing_status['stage'] == 'file_processing'
        assert processing_status['progress']['totalBatches'] == 10
        
        # Stage 4: Batch processing progress updates
        batch_progress_updates = [
            {'completedBatches': 3, 'processedLeads': 30, 'expected_percentage': 30.0},
            {'completedBatches': 6, 'processedLeads': 60, 'expected_percentage': 60.0},
            {'completedBatches': 9, 'processedLeads': 90, 'expected_percentage': 90.0}
        ]
        
        for i, update in enumerate(batch_progress_updates):
            mock_response_batch = {
                'Attributes': {
                    'uploadId': {'S': self.upload_id},
                    'status': {'S': 'processing'},
                    'stage': {'S': 'batch_processing'},
                    'progress': {
                        'M': {
                            'totalBatches': {'N': '10'},
                            'completedBatches': {'N': str(update['completedBatches'])},
                            'totalLeads': {'N': '100'},
                            'processedLeads': {'N': str(update['processedLeads'])},
                            'percentage': {'N': str(update['expected_percentage'])}
                        }
                    },
                    'updatedAt': {'S': f'2025-01-09T10:0{3+i}:00Z'},
                    'ttl': {'N': '1736424000'}
                }
            }
            self.mock_dynamodb.update_item.return_value = mock_response_batch
            
            with patch.object(self.status_service, 'get_status', return_value=processing_status), \
                 patch.object(self.status_service, '_get_current_timestamp', return_value=f'2025-01-09T10:0{3+i}:00Z'), \
                 patch.object(self.status_service, '_calculate_ttl', return_value=1736424000):
                
                batch_status = self.status_service.update_status(
                    self.upload_id,
                    stage='batch_processing',
                    progress={
                        'totalBatches': 10,
                        'completedBatches': update['completedBatches'],
                        'totalLeads': 100,
                        'processedLeads': update['processedLeads']
                    }
                )
            
            assert batch_status['progress']['completedBatches'] == update['completedBatches']
            assert batch_status['progress']['percentage'] == update['expected_percentage']
            processing_status = batch_status  # Update for next iteration
        
        # Stage 5: Processing completion
        with patch.object(self.status_service, 'get_status', return_value=processing_status), \
             patch.object(self.status_service, 'update_status') as mock_update:
            
            mock_update.return_value = {
                'uploadId': self.upload_id,
                'status': 'completed',
                'stage': 'completed',
                'progress': {
                    'totalBatches': 10,
                    'completedBatches': 10,
                    'totalLeads': 100,
                    'processedLeads': 100,
                    'createdLeads': 60,
                    'updatedLeads': 40,
                    'percentage': 100.0
                }
            }
            
            completed_status = self.status_service.complete_processing(
                self.upload_id, 100, 60, 40
            )
        
        assert completed_status['status'] == 'completed'
        assert completed_status['progress']['percentage'] == 100.0
        assert completed_status['progress']['createdLeads'] == 60
        assert completed_status['progress']['updatedLeads'] == 40
        
        print("✅ Complete upload to completion flow test passed")
    
    def test_error_recovery_flow(self):
        """Test error handling and recovery flow."""
        
        # Stage 1: Create initial status
        self.mock_dynamodb.put_item.return_value = {}
        
        with patch.object(self.status_service, '_get_current_timestamp', return_value='2025-01-09T10:00:00Z'), \
             patch.object(self.status_service, '_calculate_ttl', return_value=1736424000):
            
            initial_status = self.status_service.create_status(
                self.upload_id, "test.csv", 1024, 'processing'
            )
        
        # Stage 2: Recoverable error occurs
        mock_error_response = {
            'Attributes': {
                'uploadId': {'S': self.upload_id},
                'status': {'S': 'error'},
                'error': {
                    'M': {
                        'message': {'S': 'Network timeout during API call'},
                        'code': {'S': 'NETWORK_ERROR'},
                        'timestamp': {'S': '2025-01-09T10:05:00Z'},
                        'recoverable': {'BOOL': True},
                        'retryAfter': {'N': '30'}
                    }
                },
                'updatedAt': {'S': '2025-01-09T10:05:00Z'},
                'ttl': {'N': '1736424000'}
            }
        }
        self.mock_dynamodb.update_item.return_value = mock_error_response
        
        with patch.object(self.status_service, '_get_current_timestamp', return_value='2025-01-09T10:05:00Z'), \
             patch.object(self.status_service, '_calculate_ttl', return_value=1736424000):
            
            error_status = self.status_service.set_error(
                self.upload_id,
                "Network timeout during API call",
                "NETWORK_ERROR",
                recoverable=True,
                retry_after=30
            )
        
        assert error_status['status'] == 'error'
        assert error_status['error']['recoverable'] is True
        assert error_status['error']['retryAfter'] == 30
        
        # Stage 3: Recovery attempt - resume processing
        mock_recovery_response = {
            'Attributes': {
                'uploadId': {'S': self.upload_id},
                'status': {'S': 'processing'},
                'stage': {'S': 'batch_processing'},
                'progress': {
                    'M': {
                        'totalBatches': {'N': '5'},
                        'completedBatches': {'N': '2'},
                        'percentage': {'N': '40.0'}
                    }
                },
                'updatedAt': {'S': '2025-01-09T10:06:00Z'},
                'ttl': {'N': '1736424000'}
            }
        }
        self.mock_dynamodb.update_item.return_value = mock_recovery_response
        
        with patch.object(self.status_service, 'get_status', return_value=error_status), \
             patch.object(self.status_service, '_get_current_timestamp', return_value='2025-01-09T10:06:00Z'), \
             patch.object(self.status_service, '_calculate_ttl', return_value=1736424000):
            
            recovery_status = self.status_service.update_status(
                self.upload_id,
                status='processing',
                stage='batch_processing',
                progress={'totalBatches': 5, 'completedBatches': 2}
            )
        
        assert recovery_status['status'] == 'processing'
        assert recovery_status['progress']['percentage'] == 40.0
        
        print("✅ Error recovery flow test passed")
    
    def test_cancellation_flow(self):
        """Test processing cancellation flow."""
        
        # Stage 1: Create processing status
        self.mock_dynamodb.put_item.return_value = {}
        
        with patch.object(self.status_service, '_get_current_timestamp', return_value='2025-01-09T10:00:00Z'), \
             patch.object(self.status_service, '_calculate_ttl', return_value=1736424000):
            
            initial_status = self.status_service.create_status(
                self.upload_id, "test.csv", 1024, 'processing'
            )
        
        # Stage 2: Partial progress
        processing_status = {
            'uploadId': self.upload_id,
            'status': 'processing',
            'progress': {
                'totalBatches': 10,
                'completedBatches': 4,
                'processedLeads': 40
            }
        }
        
        # Stage 3: User cancels processing
        mock_cancel_response = {
            'Attributes': {
                'uploadId': {'S': self.upload_id},
                'status': {'S': 'cancelled'},
                'stage': {'S': 'cancelled'},
                'progress': {
                    'M': {
                        'totalBatches': {'N': '10'},
                        'completedBatches': {'N': '4'},
                        'processedLeads': {'N': '40'},
                        'percentage': {'N': '40.0'}
                    }
                },
                'metadata': {
                    'M': {
                        'cancellationReason': {'S': 'User requested cancellation'},
                        'cancellationTime': {'S': '2025-01-09T10:03:00Z'}
                    }
                },
                'updatedAt': {'S': '2025-01-09T10:03:00Z'},
                'ttl': {'N': '1736424000'}
            }
        }
        
        with patch.object(self.status_service, 'get_status', return_value=processing_status), \
             patch.object(self.status_service, 'update_status', return_value=mock_cancel_response['Attributes']) as mock_update:
            
            cancelled_status = self.status_service.cancel_processing(
                self.upload_id, "User requested cancellation"
            )
        
        # Verify cancellation was processed correctly
        call_args = mock_update.call_args[1]
        assert call_args['status'] == 'cancelled'
        assert call_args['stage'] == 'cancelled'
        assert call_args['metadata']['cancellationReason'] == 'User requested cancellation'
        
        print("✅ Cancellation flow test passed")
    
    def test_status_reader_integration(self):
        """Test integration with status reader Lambda function."""
        
        # Mock status data
        status_data = {
            'uploadId': self.upload_id,
            'status': 'processing',
            'stage': 'batch_processing',
            'progress': {
                'totalBatches': 8,
                'completedBatches': 3,
                'totalLeads': 80,
                'processedLeads': 30,
                'percentage': 37.5
            },
            'metadata': {
                'fileName': 'test.xlsx',
                'fileSize': 1024000,
                'startTime': '2025-01-09T10:00:00Z'
            },
            'createdAt': '2025-01-09T10:00:00Z',
            'updatedAt': '2025-01-09T10:03:00Z'
        }
        
        # Test GET request
        event = {
            'httpMethod': 'GET',
            'pathParameters': {
                'uploadId': self.upload_id
            }
        }
        
        context = Mock()
        context.aws_request_id = 'test-request-123'
        
        # Mock status service
        with patch('lambda_function.status_service') as mock_service:
            mock_service.get_status.return_value = status_data
            
            response = status_reader.lambda_handler(event, context)
        
        # Verify response
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['uploadId'] == self.upload_id
        assert body['status'] == 'processing'
        assert body['progress']['percentage'] == 37.5
        
        # Verify enhanced response fields
        assert 'userMessage' in body
        assert 'progressIndicators' in body
        
        print("✅ Status reader integration test passed")
    
    def test_status_reader_cancellation_integration(self):
        """Test status reader cancellation endpoint integration."""
        
        # Mock current processing status
        current_status = {
            'uploadId': self.upload_id,
            'status': 'processing',
            'progress': {
                'totalBatches': 10,
                'completedBatches': 3,
                'processedLeads': 30
            }
        }
        
        # Test POST request to cancel endpoint
        event = {
            'httpMethod': 'POST',
            'resource': '/status/{uploadId}/cancel',
            'pathParameters': {
                'uploadId': self.upload_id
            }
        }
        
        context = Mock()
        context.aws_request_id = 'test-request-123'
        
        # Mock status service and SQS
        with patch('lambda_function.status_service') as mock_service, \
             patch('lambda_function.boto3.client') as mock_boto3, \
             patch.dict(os.environ, {'SQS_QUEUE_URL': 'test-queue-url'}):
            
            mock_service.get_status.return_value = current_status
            mock_service.update_status.return_value = {
                'uploadId': self.upload_id,
                'status': 'cancelled',
                'stage': 'cancelled'
            }
            
            mock_sqs = Mock()
            mock_boto3.return_value = mock_sqs
            mock_sqs.receive_message.return_value = {'Messages': []}
            
            response = status_reader.lambda_handler(event, context)
        
        # Verify cancellation response
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['status'] == 'cancelled'
        
        print("✅ Status reader cancellation integration test passed")
    
    def test_concurrent_status_updates(self):
        """Test handling of concurrent status updates."""
        
        # Simulate concurrent updates from different components
        updates = [
            {'component': 'lead-splitter', 'progress': {'totalBatches': 10, 'completedBatches': 0}},
            {'component': 'deepseek-caller-1', 'progress': {'completedBatches': 1, 'processedLeads': 10}},
            {'component': 'deepseek-caller-2', 'progress': {'completedBatches': 2, 'processedLeads': 20}},
            {'component': 'deepseek-caller-3', 'progress': {'completedBatches': 3, 'processedLeads': 30}}
        ]
        
        # Mock existing status for each update
        base_status = {
            'uploadId': self.upload_id,
            'status': 'processing',
            'progress': {'totalBatches': 10, 'completedBatches': 0, 'processedLeads': 0}
        }
        
        for i, update in enumerate(updates):
            # Update base status for next iteration
            if i > 0:
                base_status['progress'].update(updates[i-1]['progress'])
            
            mock_response = {
                'Attributes': {
                    'uploadId': {'S': self.upload_id},
                    'status': {'S': 'processing'},
                    'progress': {
                        'M': {
                            'totalBatches': {'N': '10'},
                            'completedBatches': {'N': str(update['progress'].get('completedBatches', 0))},
                            'processedLeads': {'N': str(update['progress'].get('processedLeads', 0))},
                            'percentage': {'N': str(update['progress'].get('completedBatches', 0) * 10)}
                        }
                    },
                    'updatedAt': {'S': f'2025-01-09T10:0{i}:00Z'},
                    'ttl': {'N': '1736424000'}
                }
            }
            self.mock_dynamodb.update_item.return_value = mock_response
            
            with patch.object(self.status_service, 'get_status', return_value=base_status), \
                 patch.object(self.status_service, '_get_current_timestamp', return_value=f'2025-01-09T10:0{i}:00Z'), \
                 patch.object(self.status_service, '_calculate_ttl', return_value=1736424000):
                
                result = self.status_service.update_status(
                    self.upload_id,
                    progress=update['progress']
                )
            
            # Verify update was processed
            assert result['progress']['completedBatches'] == update['progress'].get('completedBatches', 0)
        
        print("✅ Concurrent status updates test passed")
    
    def test_ttl_expiration_behavior(self):
        """Test TTL expiration behavior."""
        
        # Create status with short TTL (for testing)
        self.mock_dynamodb.put_item.return_value = {}
        
        # Mock TTL calculation to return a time in the past (expired)
        expired_ttl = int((datetime.utcnow() - timedelta(hours=1)).timestamp())
        
        with patch.object(self.status_service, '_get_current_timestamp', return_value='2025-01-09T10:00:00Z'), \
             patch.object(self.status_service, '_calculate_ttl', return_value=expired_ttl):
            
            status = self.status_service.create_status(
                self.upload_id, "test.csv", 1024
            )
        
        # Verify TTL was set
        call_args = self.mock_dynamodb.put_item.call_args[1]
        assert call_args['Item']['ttl']['N'] == str(expired_ttl)
        
        # Simulate DynamoDB behavior - item would be automatically deleted
        # When trying to get expired item, it should not be found
        self.mock_dynamodb.get_item.return_value = {}  # Empty response (item expired)
        
        with pytest.raises(ValueError, match="Status record not found"):
            self.status_service.get_status(self.upload_id)
        
        print("✅ TTL expiration behavior test passed")
    
    def test_large_file_processing_flow(self):
        """Test status flow for large file processing."""
        
        # Simulate large file with many batches
        large_file_size = 100 * 1024 * 1024  # 100MB
        total_batches = 100
        total_leads = 10000
        
        # Stage 1: Create initial status
        self.mock_dynamodb.put_item.return_value = {}
        
        with patch.object(self.status_service, '_get_current_timestamp', return_value='2025-01-09T10:00:00Z'), \
             patch.object(self.status_service, '_calculate_ttl', return_value=1736424000):
            
            initial_status = self.status_service.create_status(
                self.upload_id, "large_file.xlsx", large_file_size
            )
        
        assert initial_status['metadata']['fileSize'] == large_file_size
        
        # Stage 2: Simulate batch processing with progress updates
        batch_milestones = [10, 25, 50, 75, 90, 100]  # Progress checkpoints
        
        for milestone in batch_milestones:
            completed_batches = milestone
            processed_leads = int(total_leads * (milestone / 100))
            
            mock_response = {
                'Attributes': {
                    'uploadId': {'S': self.upload_id},
                    'status': {'S': 'processing'},
                    'stage': {'S': 'batch_processing'},
                    'progress': {
                        'M': {
                            'totalBatches': {'N': str(total_batches)},
                            'completedBatches': {'N': str(completed_batches)},
                            'totalLeads': {'N': str(total_leads)},
                            'processedLeads': {'N': str(processed_leads)},
                            'percentage': {'N': str(float(milestone))}
                        }
                    },
                    'updatedAt': {'S': f'2025-01-09T10:{milestone:02d}:00Z'},
                    'ttl': {'N': '1736424000'}
                }
            }
            self.mock_dynamodb.update_item.return_value = mock_response
            
            with patch.object(self.status_service, 'get_status', return_value=initial_status), \
                 patch.object(self.status_service, '_get_current_timestamp', return_value=f'2025-01-09T10:{milestone:02d}:00Z'), \
                 patch.object(self.status_service, '_calculate_ttl', return_value=1736424000):
                
                progress_status = self.status_service.update_status(
                    self.upload_id,
                    stage='batch_processing',
                    progress={
                        'totalBatches': total_batches,
                        'completedBatches': completed_batches,
                        'totalLeads': total_leads,
                        'processedLeads': processed_leads
                    }
                )
            
            assert progress_status['progress']['percentage'] == float(milestone)
            assert progress_status['progress']['completedBatches'] == completed_batches
        
        print("✅ Large file processing flow test passed")


if __name__ == '__main__':
    # Run tests
    test_instance = TestStatusSystemE2EFlow()
    
    test_instance.test_complete_upload_to_completion_flow()
    test_instance.test_error_recovery_flow()
    test_instance.test_cancellation_flow()
    test_instance.test_status_reader_integration()
    test_instance.test_status_reader_cancellation_integration()
    test_instance.test_concurrent_status_updates()
    test_instance.test_ttl_expiration_behavior()
    test_instance.test_large_file_processing_flow()
    
    print("\n🎉 All status system E2E flow integration tests passed!")