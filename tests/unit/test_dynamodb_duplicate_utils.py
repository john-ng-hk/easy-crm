"""
Unit tests for DynamoDB duplicate detection utilities.

Tests the enhanced DynamoDB utilities with duplicate detection methods
including find_lead_by_email, upsert_lead, and batch_upsert_leads.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from botocore.exceptions import ClientError

# Import the modules to test
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))

from dynamodb_utils import DynamoDBUtils
from email_utils import EmailNormalizer


class TestDynamoDBDuplicateUtils(unittest.TestCase):
    """Test class for DynamoDB duplicate detection utilities."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create mock DynamoDB utils with mocked table
        self.mock_table = Mock()
        self.db_utils = DynamoDBUtils('test-leads', 'us-east-1')
        self.db_utils.table = self.mock_table
    
    def test_find_lead_by_email_existing_lead(self):
        """Test finding an existing lead by email."""
        # Mock DynamoDB query response
        test_lead = {
            'leadId': 'test-lead-1',
            'firstName': 'John',
            'lastName': 'Doe',
            'email': 'john.doe@example.com',
            'company': 'Test Corp',
            'createdAt': '2025-01-01T00:00:00Z'
        }
        
        self.mock_table.query.return_value = {
            'Items': [test_lead]
        }
        
        # Test finding the lead
        result = self.db_utils.find_lead_by_email('john.doe@example.com')
        
        self.assertIsNotNone(result)
        self.assertEqual(result['leadId'], 'test-lead-1')
        self.assertEqual(result['email'], 'john.doe@example.com')
        
        # Verify query was called correctly
        self.mock_table.query.assert_called_once_with(
            IndexName='EmailIndex',
            KeyConditionExpression='email = :email',
            ExpressionAttributeValues={':email': 'john.doe@example.com'},
            Limit=1
        )
    
    def test_find_lead_by_email_case_insensitive(self):
        """Test that email lookup is case-insensitive."""
        # Mock DynamoDB query response
        test_lead = {
            'leadId': 'test-lead-1',
            'firstName': 'John',
            'lastName': 'Doe',
            'email': 'john.doe@example.com',
            'company': 'Test Corp',
            'createdAt': '2025-01-01T00:00:00Z'
        }
        
        self.mock_table.query.return_value = {
            'Items': [test_lead]
        }
        
        # Test finding with uppercase email
        result = self.db_utils.find_lead_by_email('JOHN.DOE@EXAMPLE.COM')
        
        self.assertIsNotNone(result)
        self.assertEqual(result['leadId'], 'test-lead-1')
        
        # Verify query was called with normalized email
        self.mock_table.query.assert_called_once_with(
            IndexName='EmailIndex',
            KeyConditionExpression='email = :email',
            ExpressionAttributeValues={':email': 'john.doe@example.com'},
            Limit=1
        )
    
    def test_find_lead_by_email_whitespace_handling(self):
        """Test that email lookup handles whitespace correctly."""
        # Mock DynamoDB query response
        test_lead = {
            'leadId': 'test-lead-1',
            'firstName': 'John',
            'lastName': 'Doe',
            'email': 'john.doe@example.com',
            'company': 'Test Corp',
            'createdAt': '2025-01-01T00:00:00Z'
        }
        
        self.mock_table.query.return_value = {
            'Items': [test_lead]
        }
        
        # Test finding with whitespace
        result = self.db_utils.find_lead_by_email('  john.doe@example.com  ')
        
        self.assertIsNotNone(result)
        self.assertEqual(result['leadId'], 'test-lead-1')
        
        # Verify query was called with normalized email (whitespace trimmed)
        self.mock_table.query.assert_called_once_with(
            IndexName='EmailIndex',
            KeyConditionExpression='email = :email',
            ExpressionAttributeValues={':email': 'john.doe@example.com'},
            Limit=1
        )
    
    def test_find_lead_by_email_not_found(self):
        """Test finding a non-existent lead by email."""
        self.mock_table.query.return_value = {'Items': []}
        
        result = self.db_utils.find_lead_by_email('nonexistent@example.com')
        self.assertIsNone(result)
    
    def test_find_lead_by_email_empty_email(self):
        """Test that empty emails return None (treated as unique)."""
        result = self.db_utils.find_lead_by_email('')
        self.assertIsNone(result)
        
        result = self.db_utils.find_lead_by_email('N/A')
        self.assertIsNone(result)
        
        result = self.db_utils.find_lead_by_email(None)
        self.assertIsNone(result)
        
        # Verify no DynamoDB queries were made for empty emails
        self.mock_table.query.assert_not_called()
    
    def test_find_lead_by_email_gsi_unavailable(self):
        """Test handling when EmailIndex GSI is unavailable."""
        # Simulate GSI not found error
        self.mock_table.query.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'GSI not found'}},
            'Query'
        )
        
        result = self.db_utils.find_lead_by_email('test@example.com')
        self.assertIsNone(result)
    
    def test_find_lead_by_email_other_error(self):
        """Test handling of other DynamoDB errors."""
        # Simulate other DynamoDB error
        self.mock_table.query.side_effect = ClientError(
            {'Error': {'Code': 'ValidationException', 'Message': 'Invalid request'}},
            'Query'
        )
        
        with self.assertRaises(ClientError):
            self.db_utils.find_lead_by_email('test@example.com')
    
    @patch.object(DynamoDBUtils, 'find_lead_by_email')
    def test_upsert_lead_new_lead(self, mock_find_lead):
        """Test upserting a new lead (insert)."""
        # Mock no existing lead found
        mock_find_lead.return_value = None
        
        lead_data = {
            'firstName': 'Jane',
            'lastName': 'Smith',
            'email': 'jane.smith@example.com',
            'company': 'New Corp',
            'phone': '+1-555-123-4567'
        }
        
        lead_id, was_updated = self.db_utils.upsert_lead(lead_data, 'test.csv')
        
        self.assertIsNotNone(lead_id)
        self.assertFalse(was_updated)
        
        # Verify put_item was called for new lead
        self.mock_table.put_item.assert_called_once()
        call_args = self.mock_table.put_item.call_args[1]['Item']
        self.assertEqual(call_args['email'], 'jane.smith@example.com')
        self.assertEqual(call_args['sourceFile'], 'test.csv')
        self.assertEqual(call_args['firstName'], 'Jane')
    
    @patch.object(DynamoDBUtils, 'find_lead_by_email')
    def test_upsert_lead_existing_lead(self, mock_find_lead):
        """Test upserting an existing lead (update)."""
        # Mock existing lead found
        existing_lead = {
            'leadId': 'existing-lead-1',
            'firstName': 'John',
            'lastName': 'Doe',
            'email': 'john.doe@example.com',
            'company': 'Old Corp',
            'phone': '+1-555-999-9999',
            'sourceFile': 'old.csv',
            'createdAt': '2025-01-01T00:00:00Z',
            'updatedAt': '2025-01-01T00:00:00Z'
        }
        mock_find_lead.return_value = existing_lead
        
        # Update with new data
        updated_data = {
            'firstName': 'John',
            'lastName': 'Doe',
            'email': 'john.doe@example.com',
            'company': 'New Corp',
            'phone': '+1-555-123-4567',
            'title': 'Senior Engineer'
        }
        
        lead_id, was_updated = self.db_utils.upsert_lead(updated_data, 'new.csv')
        
        self.assertEqual(lead_id, 'existing-lead-1')
        self.assertTrue(was_updated)
        
        # Verify put_item was called for update
        self.mock_table.put_item.assert_called_once()
        call_args = self.mock_table.put_item.call_args[1]['Item']
        self.assertEqual(call_args['leadId'], 'existing-lead-1')
        self.assertEqual(call_args['company'], 'New Corp')
        self.assertEqual(call_args['phone'], '+1-555-123-4567')
        self.assertEqual(call_args['title'], 'Senior Engineer')
        self.assertEqual(call_args['sourceFile'], 'new.csv')
        self.assertEqual(call_args['createdAt'], '2025-01-01T00:00:00Z')  # Preserved
    
    def test_upsert_lead_empty_email(self):
        """Test upserting leads with empty emails (should always create new)."""
        lead_data1 = {
            'firstName': 'John',
            'lastName': 'Doe',
            'email': '',
            'company': 'Corp 1'
        }
        
        lead_data2 = {
            'firstName': 'Jane',
            'lastName': 'Smith',
            'email': 'N/A',
            'company': 'Corp 2'
        }
        
        # Both should create new leads (empty emails don't trigger duplicate lookup)
        lead_id1, was_updated1 = self.db_utils.upsert_lead(lead_data1, 'test1.csv')
        lead_id2, was_updated2 = self.db_utils.upsert_lead(lead_data2, 'test2.csv')
        
        self.assertFalse(was_updated1)
        self.assertFalse(was_updated2)
        self.assertNotEqual(lead_id1, lead_id2)
        
        # Verify put_item was called twice (once for each lead)
        self.assertEqual(self.mock_table.put_item.call_count, 2)
    
    @patch.object(DynamoDBUtils, 'upsert_lead')
    def test_batch_upsert_leads_mixed_new_and_existing(self, mock_upsert):
        """Test batch upsert with mix of new and existing leads."""
        # Mock upsert responses: first is update, second is create
        mock_upsert.side_effect = [
            ('existing-1', True),   # Updated existing lead
            ('new-1', False)        # Created new lead
        ]
        
        # Batch data with new and existing leads
        batch_data = [
            {
                'firstName': 'John',
                'lastName': 'Doe',
                'email': 'john.doe@example.com',  # Existing
                'company': 'Updated Corp'
            },
            {
                'firstName': 'Jane',
                'lastName': 'Smith',
                'email': 'jane.smith@example.com',  # New
                'company': 'New Corp'
            }
        ]
        
        result = self.db_utils.batch_upsert_leads(batch_data, 'batch.csv')
        
        self.assertEqual(len(result['created_leads']), 1)
        self.assertEqual(len(result['updated_leads']), 1)
        self.assertEqual(result['updated_leads'][0], 'existing-1')
        self.assertEqual(result['created_leads'][0], 'new-1')
        
        # Verify processing stats
        stats = result['processing_stats']
        self.assertEqual(stats['total_leads_processed'], 2)
        self.assertEqual(stats['leads_created'], 1)
        self.assertEqual(stats['leads_updated'], 1)
    
    def test_batch_upsert_leads_within_batch_duplicates(self):
        """Test batch upsert with duplicates within the same batch."""
        batch_data = [
            {
                'firstName': 'John',
                'lastName': 'Doe',
                'email': 'john.doe@example.com',
                'company': 'First Corp'
            },
            {
                'firstName': 'Jane',
                'lastName': 'Smith',
                'email': 'jane.smith@example.com',
                'company': 'Jane Corp'
            },
            {
                'firstName': 'John',
                'lastName': 'Doe',
                'email': 'JOHN.DOE@EXAMPLE.COM',  # Duplicate (case different)
                'company': 'Last Corp'  # This should win
            }
        ]
        
        # Mock upsert to return new leads
        with patch.object(self.db_utils, 'upsert_lead') as mock_upsert:
            mock_upsert.side_effect = [
                ('john-1', False),   # John (last occurrence)
                ('jane-1', False)    # Jane
            ]
            
            result = self.db_utils.batch_upsert_leads(batch_data, 'batch.csv')
        
        # Should create 2 unique leads (John and Jane)
        self.assertEqual(len(result['created_leads']), 2)
        self.assertEqual(len(result['updated_leads']), 0)
        
        # Should have batch duplicate resolution log
        batch_duplicates = [
            action for action in result['duplicate_actions'] 
            if action['action'] == 'batch_duplicate_resolved'
        ]
        self.assertEqual(len(batch_duplicates), 1)
        
        # Verify upsert was called only twice (for unique leads after dedup)
        self.assertEqual(mock_upsert.call_count, 2)
        
        # Verify the last occurrence data was used
        john_call = mock_upsert.call_args_list[0][0][0]  # First call's lead_data
        self.assertEqual(john_call['company'], 'Last Corp')
    
    def test_batch_upsert_leads_empty_emails(self):
        """Test batch upsert with empty emails (should create separate leads)."""
        batch_data = [
            {
                'firstName': 'John',
                'lastName': 'Doe',
                'email': '',
                'company': 'Corp 1'
            },
            {
                'firstName': 'Jane',
                'lastName': 'Smith',
                'email': 'N/A',
                'company': 'Corp 2'
            },
            {
                'firstName': 'Bob',
                'lastName': 'Wilson',
                'email': '',
                'company': 'Corp 3'
            }
        ]
        
        # Mock upsert to return new leads for all
        with patch.object(self.db_utils, 'upsert_lead') as mock_upsert:
            mock_upsert.side_effect = [
                ('john-1', False),
                ('jane-1', False),
                ('bob-1', False)
            ]
            
            result = self.db_utils.batch_upsert_leads(batch_data, 'batch.csv')
        
        # All should create new leads (no duplicates for empty emails)
        self.assertEqual(len(result['created_leads']), 3)
        self.assertEqual(len(result['updated_leads']), 0)
        self.assertEqual(mock_upsert.call_count, 3)
    
    def test_batch_upsert_leads_individual_failure(self):
        """Test batch upsert handling individual lead failures."""
        batch_data = [
            {
                'firstName': 'John',
                'lastName': 'Doe',
                'email': 'john.doe@example.com',
                'company': 'Good Corp'
            },
            {
                'firstName': 'Jane',
                'lastName': 'Smith',
                'email': 'jane.smith@example.com',
                'company': 'Also Good Corp'
            }
        ]
        
        # Mock a failure for one lead
        def mock_upsert(lead_data, source_file):
            if lead_data.get('email') == 'jane.smith@example.com':
                raise ClientError(
                    {'Error': {'Code': 'ValidationException', 'Message': 'Mock error'}},
                    'PutItem'
                )
            return ('john-1', False)
        
        with patch.object(self.db_utils, 'upsert_lead', side_effect=mock_upsert):
            result = self.db_utils.batch_upsert_leads(batch_data, 'batch.csv')
        
        # Should have one success and one failure
        self.assertEqual(len(result['created_leads']), 1)
        
        # Should have failure logged
        failed_actions = [
            action for action in result['duplicate_actions']
            if action['action'] == 'lead_failed'
        ]
        self.assertEqual(len(failed_actions), 1)
        self.assertEqual(failed_actions[0]['email'], 'jane.smith@example.com')
    
    def test_detect_and_resolve_batch_duplicates(self):
        """Test internal batch duplicate detection method."""
        leads_data = [
            {'email': 'john@example.com', 'firstName': 'John', 'company': 'First'},
            {'email': 'jane@example.com', 'firstName': 'Jane', 'company': 'Jane Corp'},
            {'email': 'JOHN@EXAMPLE.COM', 'firstName': 'John', 'company': 'Last'},  # Duplicate
            {'email': '', 'firstName': 'Empty1', 'company': 'Empty Corp 1'},
            {'email': 'N/A', 'firstName': 'Empty2', 'company': 'Empty Corp 2'}
        ]
        
        unique_leads, duplicate_logs = self.db_utils._detect_and_resolve_batch_duplicates(leads_data)
        
        # Should have 4 unique leads (john, jane, empty1, empty2)
        self.assertEqual(len(unique_leads), 4)
        
        # Should have 1 duplicate resolution log
        self.assertEqual(len(duplicate_logs), 1)
        self.assertEqual(duplicate_logs[0]['action'], 'batch_duplicate_resolved')
        self.assertEqual(duplicate_logs[0]['email'], 'john@example.com')
        
        # Verify last occurrence wins for John (check by normalized email)
        john_lead = None
        for lead in unique_leads:
            if EmailNormalizer.normalize_email(lead.get('email', '')) == 'john@example.com':
                john_lead = lead
                break
        
        self.assertIsNotNone(john_lead)
        self.assertEqual(john_lead['company'], 'Last')
        
        # Verify empty emails are preserved as separate leads
        empty_leads = [lead for lead in unique_leads if EmailNormalizer.is_empty_email(lead.get('email'))]
        self.assertEqual(len(empty_leads), 2)
    
    def test_batch_upsert_performance_metrics(self):
        """Test that batch upsert returns proper performance metrics."""
        batch_data = [
            {'firstName': 'John', 'lastName': 'Doe', 'email': 'john@example.com'},
            {'firstName': 'Jane', 'lastName': 'Smith', 'email': 'jane@example.com'}
        ]
        
        # Mock upsert to return new leads
        with patch.object(self.db_utils, 'upsert_lead') as mock_upsert:
            mock_upsert.side_effect = [
                ('john-1', False),
                ('jane-1', False)
            ]
            
            result = self.db_utils.batch_upsert_leads(batch_data, 'test.csv')
        
        stats = result['processing_stats']
        self.assertIn('total_leads_processed', stats)
        self.assertIn('unique_leads_after_dedup', stats)
        self.assertIn('leads_created', stats)
        self.assertIn('leads_updated', stats)
        self.assertIn('processing_time_ms', stats)
        self.assertIn('email_index_queries', stats)
        
        self.assertEqual(stats['total_leads_processed'], 2)
        self.assertEqual(stats['unique_leads_after_dedup'], 2)
        self.assertGreaterEqual(stats['processing_time_ms'], 0)  # Allow 0 for fast tests
    
    def test_upsert_lead_dynamodb_error(self):
        """Test upsert_lead handling DynamoDB errors."""
        # Mock find_lead_by_email to return None (new lead)
        with patch.object(self.db_utils, 'find_lead_by_email', return_value=None):
            # Mock put_item to raise DynamoDB error
            self.mock_table.put_item.side_effect = ClientError(
                {'Error': {'Code': 'ValidationException', 'Message': 'Mock DynamoDB error'}},
                'PutItem'
            )
            
            lead_data = {
                'firstName': 'John',
                'lastName': 'Doe',
                'email': 'john@example.com',
                'company': 'Test Corp'
            }
            
            with self.assertRaises(ClientError):
                self.db_utils.upsert_lead(lead_data, 'test.csv')
    
    def test_batch_upsert_leads_all_duplicates(self):
        """Test batch upsert with all leads being duplicates."""
        batch_data = [
            {
                'firstName': 'John',
                'lastName': 'Doe',
                'email': 'john@example.com',
                'company': 'Updated Corp 1'
            },
            {
                'firstName': 'Jane',
                'lastName': 'Smith',
                'email': 'jane@example.com',
                'company': 'Updated Corp 2'
            }
        ]
        
        # Mock upsert to return all updates
        with patch.object(self.db_utils, 'upsert_lead') as mock_upsert:
            with patch.object(self.db_utils, 'find_lead_by_email') as mock_find:
                # Mock existing leads for duplicate action logging
                mock_find.side_effect = [
                    {'leadId': 'john-1', 'firstName': 'John', 'lastName': 'Doe', 'sourceFile': 'old.csv'},
                    {'leadId': 'jane-1', 'firstName': 'Jane', 'lastName': 'Smith', 'sourceFile': 'old.csv'}
                ]
                
                mock_upsert.side_effect = [
                    ('john-1', True),   # Updated existing lead
                    ('jane-1', True)    # Updated existing lead
                ]
                
                result = self.db_utils.batch_upsert_leads(batch_data, 'new.csv')
        
        # All should be updates
        self.assertEqual(len(result['created_leads']), 0)
        self.assertEqual(len(result['updated_leads']), 2)
        
        # Should have duplicate action logs for updates
        update_actions = [
            action for action in result['duplicate_actions']
            if action['action'] == 'lead_updated'
        ]
        self.assertEqual(len(update_actions), 2)
    
    def test_batch_upsert_leads_complex_batch_duplicates(self):
        """Test batch upsert with complex duplicate scenarios."""
        batch_data = [
            {'firstName': 'John', 'lastName': 'Doe', 'email': 'john@example.com', 'company': 'First'},
            {'firstName': 'Jane', 'lastName': 'Smith', 'email': 'jane@example.com', 'company': 'Jane Corp'},
            {'firstName': 'John', 'lastName': 'Doe', 'email': 'JOHN@EXAMPLE.COM', 'company': 'Second'},  # Duplicate
            {'firstName': 'Bob', 'lastName': 'Wilson', 'email': 'bob@example.com', 'company': 'Bob Corp'},
            {'firstName': 'John', 'lastName': 'Doe', 'email': '  john@example.com  ', 'company': 'Third'},  # Another duplicate
            {'firstName': 'Empty1', 'lastName': 'User', 'email': '', 'company': 'Empty Corp 1'},
            {'firstName': 'Empty2', 'lastName': 'User', 'email': 'N/A', 'company': 'Empty Corp 2'}
        ]
        
        # Mock upsert to return new leads
        with patch.object(self.db_utils, 'upsert_lead') as mock_upsert:
            mock_upsert.side_effect = [
                ('john-1', False),   # John (last occurrence should win)
                ('jane-1', False),   # Jane
                ('bob-1', False),    # Bob
                ('empty1-1', False), # Empty1
                ('empty2-1', False)  # Empty2
            ]
            
            result = self.db_utils.batch_upsert_leads(batch_data, 'complex.csv')
        
        # Should create 5 unique leads (john, jane, bob, empty1, empty2)
        self.assertEqual(len(result['created_leads']), 5)
        self.assertEqual(len(result['updated_leads']), 0)
        
        # Should have 2 batch duplicate resolution logs (for John's duplicates)
        batch_duplicates = [
            action for action in result['duplicate_actions']
            if action['action'] == 'batch_duplicate_resolved'
        ]
        self.assertEqual(len(batch_duplicates), 2)
        
        # Verify upsert was called 5 times (for unique leads after dedup)
        self.assertEqual(mock_upsert.call_count, 5)
        
        # Verify the last occurrence data was used for John
        john_call = None
        for call in mock_upsert.call_args_list:
            lead_data = call[0][0]
            if EmailNormalizer.normalize_email(lead_data.get('email', '')) == 'john@example.com':
                john_call = lead_data
                break
        
        self.assertIsNotNone(john_call)
        self.assertEqual(john_call['company'], 'Third')  # Last occurrence should win
    
    def test_log_duplicate_detection_performance(self):
        """Test performance logging method."""
        with patch('dynamodb_utils.logger') as mock_logger:
            self.db_utils.log_duplicate_detection_performance(
                batch_size=10,
                duplicates_found=3,
                processing_time_ms=150,
                email_queries=7
            )
            
            # Verify info log was called
            mock_logger.info.assert_called()
            log_call = mock_logger.info.call_args[0][0]
            self.assertIn('duplicate_detection_performance', log_call)
            
            # Should not trigger warning (under 20% threshold)
            mock_logger.warning.assert_not_called()
    
    def test_log_duplicate_detection_performance_warning(self):
        """Test performance logging with warning for slow processing."""
        with patch('dynamodb_utils.logger') as mock_logger:
            # Simulate slow processing (over 20% threshold)
            self.db_utils.log_duplicate_detection_performance(
                batch_size=10,
                duplicates_found=3,
                processing_time_ms=1000,  # Much slower than baseline
                email_queries=7
            )
            
            # Verify warning was logged
            mock_logger.warning.assert_called()
            warning_call = mock_logger.warning.call_args[0][0]
            self.assertIn('exceeded 20% threshold', warning_call)
    
    def test_create_duplicate_action_log(self):
        """Test duplicate action log creation."""
        original_data = {
            'firstName': 'John',
            'lastName': 'Doe',
            'company': 'Old Corp'
        }
        
        new_data = {
            'firstName': 'John',
            'lastName': 'Doe',
            'company': 'New Corp'
        }
        
        log_entry = self.db_utils.create_duplicate_action_log(
            action='lead_updated',
            email='john@example.com',
            lead_id='test-lead-1',
            original_data=original_data,
            new_data=new_data,
            source_file='new.csv',
            original_source_file='old.csv'
        )
        
        self.assertEqual(log_entry['action'], 'lead_updated')
        self.assertEqual(log_entry['email'], 'john@example.com')
        self.assertEqual(log_entry['leadId'], 'test-lead-1')
        self.assertEqual(log_entry['originalData'], original_data)
        self.assertEqual(log_entry['newData'], new_data)
        self.assertEqual(log_entry['newSourceFile'], 'new.csv')
        self.assertEqual(log_entry['originalSourceFile'], 'old.csv')
        self.assertIn('timestamp', log_entry)
    
    def test_create_duplicate_action_log_minimal(self):
        """Test duplicate action log creation with minimal data."""
        log_entry = self.db_utils.create_duplicate_action_log(
            action='batch_duplicate_resolved',
            email='test@example.com',
            lead_id='test-lead-1'
        )
        
        self.assertEqual(log_entry['action'], 'batch_duplicate_resolved')
        self.assertEqual(log_entry['email'], 'test@example.com')
        self.assertEqual(log_entry['leadId'], 'test-lead-1')
        self.assertIn('timestamp', log_entry)
        
        # Optional fields should not be present
        self.assertNotIn('originalData', log_entry)
        self.assertNotIn('newData', log_entry)
        self.assertNotIn('newSourceFile', log_entry)
        self.assertNotIn('originalSourceFile', log_entry)
    
    def test_find_lead_by_email_malformed_email(self):
        """Test finding lead with malformed email (should still attempt lookup)."""
        # Mock DynamoDB query response for malformed email
        self.mock_table.query.return_value = {'Items': []}
        
        # Test with malformed email (should still normalize and query)
        result = self.db_utils.find_lead_by_email('not-an-email')
        self.assertIsNone(result)
        
        # Verify query was still attempted with normalized email
        self.mock_table.query.assert_called_once_with(
            IndexName='EmailIndex',
            KeyConditionExpression='email = :email',
            ExpressionAttributeValues={':email': 'not-an-email'},
            Limit=1
        )
    
    def test_batch_upsert_leads_exception_handling(self):
        """Test batch upsert handling unexpected exceptions."""
        batch_data = [
            {'firstName': 'John', 'lastName': 'Doe', 'email': 'john@example.com'}
        ]
        
        # Mock upsert to raise unexpected exception
        with patch.object(self.db_utils, 'upsert_lead') as mock_upsert:
            mock_upsert.side_effect = Exception("Unexpected error")
            
            with self.assertRaises(Exception):
                self.db_utils.batch_upsert_leads(batch_data, 'test.csv')


if __name__ == '__main__':
    unittest.main()