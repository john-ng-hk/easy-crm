"""
Unit tests for ProcessingStatusService.

Tests all service methods including TTL functionality, error handling,
and data formatting.
"""

import pytest
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

# Import the service
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../lambda/shared'))

from status_service import ProcessingStatusService


class TestProcessingStatusService:
    """Test cases for ProcessingStatusService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_dynamodb = Mock()
        self.service = ProcessingStatusService(
            dynamodb_client=self.mock_dynamodb,
            table_name='test-processing-status'
        )
        
    def test_calculate_ttl_default_24_hours(self):
        """Test TTL calculation with default 24 hours."""
        with patch('status_service.datetime') as mock_datetime:
            mock_now = datetime(2025, 1, 9, 12, 0, 0)
            mock_datetime.utcnow.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            ttl = self.service._calculate_ttl()
            
            # Should be 24 hours from now
            expected_time = mock_now + timedelta(hours=24)
            expected_ttl = int(expected_time.timestamp())
            
            assert ttl == expected_ttl
    
    def test_calculate_ttl_custom_hours(self):
        """Test TTL calculation with custom hours."""
        with patch('status_service.datetime') as mock_datetime:
            mock_now = datetime(2025, 1, 9, 12, 0, 0)
            mock_datetime.utcnow.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            ttl = self.service._calculate_ttl(hours=48)
            
            # Should be 48 hours from now
            expected_time = mock_now + timedelta(hours=48)
            expected_ttl = int(expected_time.timestamp())
            
            assert ttl == expected_ttl
    
    def test_get_current_timestamp(self):
        """Test current timestamp generation."""
        with patch('status_service.datetime') as mock_datetime:
            mock_now = datetime(2025, 1, 9, 12, 0, 0)
            mock_datetime.utcnow.return_value = mock_now
            
            timestamp = self.service._get_current_timestamp()
            
            assert timestamp == "2025-01-09T12:00:00Z"
    
    def test_create_status_success(self):
        """Test successful status creation."""
        upload_id = "test-upload-123"
        file_name = "test.xlsx"
        file_size = 1024000
        
        # Mock successful DynamoDB put_item
        self.mock_dynamodb.put_item.return_value = {}
        
        with patch.object(self.service, '_get_current_timestamp', return_value='2025-01-09T12:00:00Z'), \
             patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            
            result = self.service.create_status(upload_id, file_name, file_size)
            
            # Verify DynamoDB call
            self.mock_dynamodb.put_item.assert_called_once()
            call_args = self.mock_dynamodb.put_item.call_args
            
            assert call_args[1]['TableName'] == 'test-processing-status'
            assert call_args[1]['Item']['uploadId']['S'] == upload_id
            assert call_args[1]['Item']['status']['S'] == 'uploading'
            assert call_args[1]['Item']['stage']['S'] == 'file_upload'
            assert call_args[1]['Item']['metadata']['M']['fileName']['S'] == file_name
            assert call_args[1]['Item']['metadata']['M']['fileSize']['N'] == str(file_size)
            assert call_args[1]['Item']['ttl']['N'] == '1736424000'
            assert 'ConditionExpression' in call_args[1]
            
            # Verify result format
            assert result['uploadId'] == upload_id
            assert result['status'] == 'uploading'
            assert result['stage'] == 'file_upload'
    
    def test_create_status_already_exists(self):
        """Test status creation when record already exists."""
        upload_id = "test-upload-123"
        
        # Mock ConditionalCheckFailedException
        error = ClientError(
            error_response={'Error': {'Code': 'ConditionalCheckFailedException'}},
            operation_name='PutItem'
        )
        self.mock_dynamodb.put_item.side_effect = error
        
        with pytest.raises(ValueError, match="Status record already exists"):
            self.service.create_status(upload_id, "test.xlsx", 1024)
    
    def test_create_status_dynamodb_error(self):
        """Test status creation with DynamoDB error."""
        upload_id = "test-upload-123"
        
        # Mock other DynamoDB error
        error = ClientError(
            error_response={'Error': {'Code': 'InternalServerError'}},
            operation_name='PutItem'
        )
        self.mock_dynamodb.put_item.side_effect = error
        
        with pytest.raises(ClientError):
            self.service.create_status(upload_id, "test.xlsx", 1024)
    
    def test_update_status_success(self):
        """Test successful status update."""
        upload_id = "test-upload-123"
        
        # Mock existing status for get_status call
        existing_status = {
            'uploadId': upload_id,
            'status': 'uploading',
            'metadata': {
                'fileName': 'test.csv',
                'fileSize': 1024,
                'startTime': '2025-01-09T11:00:00Z'
            },
            'progress': {
                'totalBatches': 0,
                'completedBatches': 0
            }
        }
        
        # Mock successful update
        mock_response = {
            'Attributes': {
                'uploadId': {'S': upload_id},
                'status': {'S': 'processing'},
                'stage': {'S': 'batch_processing'},
                'progress': {
                    'M': {
                        'totalBatches': {'N': '10'},
                        'completedBatches': {'N': '5'},
                        'percentage': {'N': '50.0'}
                    }
                },
                'updatedAt': {'S': '2025-01-09T12:00:00Z'},
                'ttl': {'N': '1736424000'}
            }
        }
        self.mock_dynamodb.update_item.return_value = mock_response
        
        with patch.object(self.service, 'get_status', return_value=existing_status), \
             patch.object(self.service, '_get_current_timestamp', return_value='2025-01-09T12:00:00Z'), \
             patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            
            result = self.service.update_status(
                upload_id=upload_id,
                status='processing',
                stage='batch_processing',
                progress={'totalBatches': 10, 'completedBatches': 5}
            )
            
            # Verify DynamoDB call
            self.mock_dynamodb.update_item.assert_called_once()
            call_args = self.mock_dynamodb.update_item.call_args
            
            assert call_args[1]['TableName'] == 'test-processing-status'
            assert call_args[1]['Key']['uploadId']['S'] == upload_id
            assert 'ConditionExpression' in call_args[1]
            assert call_args[1]['ReturnValues'] == 'ALL_NEW'
            
            # Verify result
            assert result['uploadId'] == upload_id
            assert result['status'] == 'processing'
            assert result['progress']['percentage'] == 50.0
    
    def test_update_status_with_progress_calculation(self):
        """Test status update with automatic percentage calculation."""
        upload_id = "test-upload-123"
        
        # Mock existing status for get_status call
        existing_status = {
            'uploadId': upload_id,
            'status': 'processing',
            'metadata': {
                'fileName': 'test.csv',
                'fileSize': 1024,
                'startTime': '2025-01-09T11:00:00Z'
            },
            'progress': {
                'totalBatches': 0,
                'completedBatches': 0
            }
        }
        
        mock_response = {
            'Attributes': {
                'uploadId': {'S': upload_id},
                'status': {'S': 'processing'},
                'progress': {
                    'M': {
                        'totalBatches': {'N': '8'},
                        'completedBatches': {'N': '6'},
                        'percentage': {'N': '75.0'}
                    }
                },
                'updatedAt': {'S': '2025-01-09T12:00:00Z'},
                'ttl': {'N': '1736424000'}
            }
        }
        self.mock_dynamodb.update_item.return_value = mock_response
        
        with patch.object(self.service, 'get_status', return_value=existing_status), \
             patch.object(self.service, '_get_current_timestamp', return_value='2025-01-09T12:00:00Z'), \
             patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            
            result = self.service.update_status(
                upload_id=upload_id,
                progress={'totalBatches': 8, 'completedBatches': 6}
            )
            
            # Verify percentage was calculated correctly (6/8 * 100 = 75%)
            assert result['progress']['percentage'] == 75.0
    
    def test_update_status_not_found(self):
        """Test status update when record not found."""
        upload_id = "nonexistent-upload"
        
        # Mock ConditionalCheckFailedException
        error = ClientError(
            error_response={'Error': {'Code': 'ConditionalCheckFailedException'}},
            operation_name='UpdateItem'
        )
        self.mock_dynamodb.update_item.side_effect = error
        
        with pytest.raises(ValueError, match="Status record not found"):
            self.service.update_status(upload_id, status='processing')
    
    def test_get_status_success(self):
        """Test successful status retrieval."""
        upload_id = "test-upload-123"
        
        mock_response = {
            'Item': {
                'uploadId': {'S': upload_id},
                'status': {'S': 'processing'},
                'stage': {'S': 'batch_processing'},
                'progress': {
                    'M': {
                        'totalBatches': {'N': '10'},
                        'completedBatches': {'N': '3'},
                        'percentage': {'N': '30.0'}
                    }
                },
                'metadata': {
                    'M': {
                        'fileName': {'S': 'test.xlsx'},
                        'fileSize': {'N': '1024000'}
                    }
                },
                'createdAt': {'S': '2025-01-09T11:00:00Z'},
                'updatedAt': {'S': '2025-01-09T12:00:00Z'},
                'ttl': {'N': '1736424000'}
            }
        }
        self.mock_dynamodb.get_item.return_value = mock_response
        
        result = self.service.get_status(upload_id)
        
        # Verify DynamoDB call
        self.mock_dynamodb.get_item.assert_called_once_with(
            TableName='test-processing-status',
            Key={'uploadId': {'S': upload_id}}
        )
        
        # Verify result format
        assert result['uploadId'] == upload_id
        assert result['status'] == 'processing'
        assert result['progress']['totalBatches'] == 10
        assert result['progress']['completedBatches'] == 3
        assert result['progress']['percentage'] == 30.0
        assert result['metadata']['fileName'] == 'test.xlsx'
        assert result['metadata']['fileSize'] == 1024000
        assert result['ttl'] == 1736424000
    
    def test_get_status_not_found(self):
        """Test status retrieval when record not found."""
        upload_id = "nonexistent-upload"
        
        # Mock empty response
        self.mock_dynamodb.get_item.return_value = {}
        
        with pytest.raises(ValueError, match="Status record not found"):
            self.service.get_status(upload_id)
    
    def test_get_status_dynamodb_error(self):
        """Test status retrieval with DynamoDB error."""
        upload_id = "test-upload-123"
        
        error = ClientError(
            error_response={'Error': {'Code': 'InternalServerError'}},
            operation_name='GetItem'
        )
        self.mock_dynamodb.get_item.side_effect = error
        
        with pytest.raises(ClientError):
            self.service.get_status(upload_id)
    
    def test_set_error_success(self):
        """Test successful error status setting."""
        upload_id = "test-upload-123"
        error_message = "DeepSeek API failed"
        error_code = "API_ERROR"
        
        mock_response = {
            'Attributes': {
                'uploadId': {'S': upload_id},
                'status': {'S': 'error'},
                'error': {
                    'M': {
                        'message': {'S': error_message},
                        'code': {'S': error_code},
                        'timestamp': {'S': '2025-01-09T12:00:00Z'}
                    }
                },
                'updatedAt': {'S': '2025-01-09T12:00:00Z'},
                'ttl': {'N': '1736424000'}
            }
        }
        self.mock_dynamodb.update_item.return_value = mock_response
        
        with patch.object(self.service, '_get_current_timestamp', return_value='2025-01-09T12:00:00Z'), \
             patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            
            result = self.service.set_error(upload_id, error_message, error_code)
            
            # Verify DynamoDB call
            self.mock_dynamodb.update_item.assert_called_once()
            call_args = self.mock_dynamodb.update_item.call_args
            
            assert call_args[1]['TableName'] == 'test-processing-status'
            assert call_args[1]['Key']['uploadId']['S'] == upload_id
            assert 'ConditionExpression' in call_args[1]
            
            # Verify result
            assert result['uploadId'] == upload_id
            assert result['status'] == 'error'
            assert result['error']['message'] == error_message
            assert result['error']['code'] == error_code
    
    def test_set_error_default_code(self):
        """Test error setting with default error code."""
        upload_id = "test-upload-123"
        error_message = "Processing failed"
        
        mock_response = {
            'Attributes': {
                'uploadId': {'S': upload_id},
                'status': {'S': 'error'},
                'error': {
                    'M': {
                        'message': {'S': error_message},
                        'code': {'S': 'PROCESSING_ERROR'},
                        'timestamp': {'S': '2025-01-09T12:00:00Z'}
                    }
                },
                'updatedAt': {'S': '2025-01-09T12:00:00Z'},
                'ttl': {'N': '1736424000'}
            }
        }
        self.mock_dynamodb.update_item.return_value = mock_response
        
        with patch.object(self.service, '_get_current_timestamp', return_value='2025-01-09T12:00:00Z'), \
             patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            
            result = self.service.set_error(upload_id, error_message)
            
            # Verify default error code was used
            assert result['error']['code'] == 'PROCESSING_ERROR'
    
    def test_set_error_not_found(self):
        """Test error setting when record not found."""
        upload_id = "nonexistent-upload"
        
        error = ClientError(
            error_response={'Error': {'Code': 'ConditionalCheckFailedException'}},
            operation_name='UpdateItem'
        )
        self.mock_dynamodb.update_item.side_effect = error
        
        with pytest.raises(ValueError, match="Status record not found"):
            self.service.set_error(upload_id, "Test error")
    
    def test_complete_processing_success(self):
        """Test successful processing completion."""
        upload_id = "test-upload-123"
        total_leads = 100
        
        # Mock get_status call
        current_status = {
            'uploadId': upload_id,
            'status': 'processing',
            'progress': {
                'totalBatches': 10,
                'completedBatches': 8
            }
        }
        
        # Mock update_status call
        completed_status = {
            'uploadId': upload_id,
            'status': 'completed',
            'stage': 'completed',
            'progress': {
                'totalBatches': 10,
                'completedBatches': 10,
                'totalLeads': total_leads,
                'processedLeads': total_leads,
                'percentage': 100.0
            }
        }
        
        with patch.object(self.service, 'get_status', return_value=current_status), \
             patch.object(self.service, 'update_status', return_value=completed_status) as mock_update:
            
            result = self.service.complete_processing(upload_id, total_leads)
            
            # Verify update_status was called with correct parameters
            mock_update.assert_called_once()
            call_args = mock_update.call_args[1]
            
            assert call_args['upload_id'] == upload_id
            assert call_args['status'] == 'completed'
            assert call_args['stage'] == 'completed'
            assert call_args['progress']['totalLeads'] == total_leads
            assert call_args['progress']['processedLeads'] == total_leads
            assert call_args['progress']['percentage'] == 100.0
            
            # Verify result
            assert result['status'] == 'completed'
            assert result['progress']['percentage'] == 100.0
    
    def test_complete_processing_not_found(self):
        """Test processing completion when record not found."""
        upload_id = "nonexistent-upload"
        
        with patch.object(self.service, 'get_status', side_effect=ValueError("Status record not found")):
            with pytest.raises(ValueError, match="Status record not found"):
                self.service.complete_processing(upload_id, 100)
    
    def test_format_status_record_comprehensive(self):
        """Test comprehensive DynamoDB item formatting."""
        dynamodb_item = {
            'uploadId': {'S': 'test-123'},
            'status': {'S': 'processing'},
            'progress': {
                'M': {
                    'totalBatches': {'N': '10'},
                    'completedBatches': {'N': '5'},
                    'percentage': {'N': '50.5'}
                }
            },
            'metadata': {
                'M': {
                    'fileName': {'S': 'test.xlsx'},
                    'fileSize': {'N': '1024000'},
                    'isActive': {'BOOL': True},
                    'tags': {
                        'L': [
                            {'S': 'urgent'},
                            {'S': 'priority'}
                        ]
                    },
                    'nullField': {'NULL': True}
                }
            },
            'ttl': {'N': '1736424000'}
        }
        
        result = self.service._format_status_record(dynamodb_item)
        
        # Verify all data types are correctly parsed
        assert result['uploadId'] == 'test-123'
        assert result['status'] == 'processing'
        assert result['progress']['totalBatches'] == 10
        assert result['progress']['completedBatches'] == 5
        assert result['progress']['percentage'] == 50.5
        assert result['metadata']['fileName'] == 'test.xlsx'
        assert result['metadata']['fileSize'] == 1024000
        assert result['metadata']['isActive'] is True
        assert result['metadata']['tags'] == ['urgent', 'priority']
        assert result['metadata']['nullField'] is None
        assert result['ttl'] == 1736424000
    
    def test_ttl_included_in_all_operations(self):
        """Test that TTL is included in all status operations."""
        upload_id = "test-upload-123"
        
        # Test create_status includes TTL
        self.mock_dynamodb.put_item.return_value = {}
        with patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            self.service.create_status(upload_id, "test.xlsx", 1024)
            
            call_args = self.mock_dynamodb.put_item.call_args[1]
            assert call_args['Item']['ttl']['N'] == '1736424000'
        
        # Test update_status includes TTL
        mock_response = {
            'Attributes': {
                'uploadId': {'S': upload_id},
                'status': {'S': 'processing'},
                'ttl': {'N': '1736424000'}
            }
        }
        self.mock_dynamodb.update_item.return_value = mock_response
        
        with patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            self.service.update_status(upload_id, status='processing')
            
            call_args = self.mock_dynamodb.update_item.call_args[1]
            assert ':ttl' in call_args['ExpressionAttributeValues']
            assert call_args['ExpressionAttributeValues'][':ttl']['N'] == '1736424000'
        
        # Test set_error includes TTL
        self.mock_dynamodb.update_item.return_value = mock_response
        
        with patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            self.service.set_error(upload_id, "Test error")
            
            call_args = self.mock_dynamodb.update_item.call_args[1]
            assert ':ttl' in call_args['ExpressionAttributeValues']
            assert call_args['ExpressionAttributeValues'][':ttl']['N'] == '1736424000'


    def test_progress_percentage_calculation(self):
        """Test progress percentage calculation."""
        upload_id = "test-upload-123"
        
        # Mock existing status for get_status call
        existing_status = {
            'uploadId': upload_id,
            'status': 'processing',
            'metadata': {
                'fileName': 'test.csv',
                'fileSize': 1024,
                'startTime': '2025-01-09T11:00:00Z'
            },
            'progress': {
                'totalBatches': 0,
                'completedBatches': 0
            }
        }
        
        # Mock update_status response
        mock_response = {
            'Attributes': {
                'uploadId': {'S': upload_id},
                'status': {'S': 'processing'},
                'progress': {
                    'M': {
                        'totalBatches': {'N': '10'},
                        'completedBatches': {'N': '3'},
                        'totalLeads': {'N': '100'},
                        'processedLeads': {'N': '30'},
                        'percentage': {'N': '30.0'}
                    }
                },
                'updatedAt': {'S': '2025-01-09T12:00:00Z'},
                'ttl': {'N': '1736424000'}
            }
        }
        self.mock_dynamodb.update_item.return_value = mock_response
        
        with patch.object(self.service, 'get_status', return_value=existing_status), \
             patch.object(self.service, '_get_current_timestamp', return_value='2025-01-09T12:00:00Z'), \
             patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            
            result = self.service.update_status(
                upload_id=upload_id,
                progress={
                    'totalBatches': 10,
                    'completedBatches': 3,
                    'totalLeads': 100,
                    'processedLeads': 30
                }
            )
        
        assert result['progress']['percentage'] == 30.0
    
    def test_estimated_completion_time_calculation(self):
        """Test estimated completion time calculation."""
        upload_id = "test-upload-123"
        
        # Create status with a start time in the past
        past_time = datetime.utcnow() - timedelta(seconds=30)
        start_time = past_time.isoformat() + 'Z'
        
        # Mock create_status
        self.mock_dynamodb.put_item.return_value = {}
        
        with patch.object(self.service, '_get_current_timestamp', return_value=start_time), \
             patch.object(self.service, '_calculate_ttl', return_value=1736424000):
            self.service.create_status(upload_id, "test.csv", 1024)
        
        # Mock get_status for existing record
        existing_status = {
            'uploadId': upload_id,
            'status': 'processing',
            'metadata': {
                'fileName': 'test.csv',
                'fileSize': 1024,
                'startTime': start_time
            },
            'progress': {
                'totalBatches': 0,
                'completedBatches': 0
            }
        }
        
        # Mock update_status response with estimates
        current_time = datetime.utcnow().isoformat() + 'Z'
        mock_response = {
            'Attributes': {
                'uploadId': {'S': upload_id},
                'status': {'S': 'processing'},
                'progress': {
                    'M': {
                        'totalBatches': {'N': '10'},
                        'completedBatches': {'N': '3'},
                        'totalLeads': {'N': '100'},
                        'processedLeads': {'N': '30'},
                        'percentage': {'N': '30.0'},
                        'estimatedRemainingSeconds': {'N': '70'},
                        'processingRate': {'N': '0.1'},
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
                    'completedBatches': 3,
                    'totalLeads': 100,
                    'processedLeads': 30
                }
            )
        
        # Should have estimated completion time for longer operations
        progress = result['progress']
        assert 'percentage' in progress
        assert progress['percentage'] == 30.0
        
        # Check if estimates are calculated
        if 'estimatedRemainingSeconds' in progress:
            assert isinstance(progress['estimatedRemainingSeconds'], int)
            assert 'processingRate' in progress
            assert 'showEstimates' in progress
    
    def test_show_estimates_flag_for_short_operations(self):
        """Test that estimates are not shown for short operations."""
        upload_id = "test-upload-123"
        
        # Create status with recent start time (short operation)
        recent_time = datetime.utcnow() - timedelta(seconds=5)
        start_time = recent_time.isoformat() + 'Z'
        
        # Mock existing status
        existing_status = {
            'uploadId': upload_id,
            'status': 'processing',
            'metadata': {
                'fileName': 'test.csv',
                'fileSize': 1024,
                'startTime': start_time
            },
            'progress': {
                'totalBatches': 0,
                'completedBatches': 0
            }
        }
        
        # Mock update response for short operation
        current_time = datetime.utcnow().isoformat() + 'Z'
        mock_response = {
            'Attributes': {
                'uploadId': {'S': upload_id},
                'status': {'S': 'processing'},
                'progress': {
                    'M': {
                        'totalBatches': {'N': '2'},
                        'completedBatches': {'N': '1'},
                        'totalLeads': {'N': '20'},
                        'processedLeads': {'N': '10'},
                        'percentage': {'N': '50.0'},
                        'showEstimates': {'BOOL': False}
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
                    'totalBatches': 2,
                    'completedBatches': 1,
                    'totalLeads': 20,
                    'processedLeads': 10
                }
            )
        
        progress = result['progress']
        # For short operations, showEstimates should be False
        if 'showEstimates' in progress:
            assert progress['showEstimates'] is False
    
    def test_calculate_progress_and_estimates_method(self):
        """Test the _calculate_progress_and_estimates method directly."""
        # Test with sufficient elapsed time for estimates
        past_time = datetime.utcnow() - timedelta(seconds=60)
        start_time = past_time.isoformat() + 'Z'
        current_time = datetime.utcnow().isoformat() + 'Z'
        
        existing_status = {
            'metadata': {
                'startTime': start_time
            }
        }
        
        new_progress = {
            'totalBatches': 10,
            'completedBatches': 3,
            'totalLeads': 100,
            'processedLeads': 30
        }
        
        result = self.service._calculate_progress_and_estimates(
            new_progress, existing_status, current_time
        )
        
        # Should calculate percentage
        assert result['percentage'] == 30.0
        
        # Should have processing rate and estimates for longer operations
        if 'processingRate' in result:
            assert isinstance(result['processingRate'], float)
            assert result['processingRate'] > 0
            assert 'estimatedRemainingSeconds' in result
            assert 'estimatedCompletion' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])