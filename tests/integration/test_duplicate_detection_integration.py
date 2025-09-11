"""
Integration tests for duplicate detection functionality.

Tests the integration between email normalization, DynamoDB utilities,
and duplicate detection across the system components.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError
import sys
import os

# Add lambda paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))

from dynamodb_utils import DynamoDBUtils
from email_utils import EmailNormalizer


class TestDuplicateDetectionIntegration(unittest.TestCase):
    """Integration tests for duplicate detection functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.mock_table = Mock()
        self.db_utils = DynamoDBUtils('test-leads', 'us-east-1')
        self.db_utils.table = self.mock_table
    
    def test_end_to_end_duplicate_detection_workflow(self):
        """Test complete duplicate detection workflow from email normalization to database operations."""
        # Test data with various email formats
        batch_data = [
            {
                'firstName': 'John',
                'lastName': 'Doe',
                'email': '  JOHN.DOE@EXAMPLE.COM  ',  # Whitespace and uppercase
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
                'email': 'john.doe@example.com',  # Duplicate after normalization
                'company': 'Last Corp'
            },
            {
                'firstName': 'Bob',
                'lastName': 'Wilson',
                'email': '',  # Empty email
                'company': 'Bob Corp'
            }
        ]
        
        # Mock upsert responses
        with patch.object(self.db_utils, 'upsert_lead') as mock_upsert:
            mock_upsert.side_effect = [
                ('john-1', False),   # John (deduplicated)
                ('jane-1', False),   # Jane
                ('bob-1', False)     # Bob (empty email)
            ]
            
            result = self.db_utils.batch_upsert_leads(batch_data, 'test.csv')
        
        # Verify results
        self.assertEqual(len(result['created_leads']), 3)
        self.assertEqual(len(result['updated_leads']), 0)
        
        # Verify batch duplicate was detected and resolved
        batch_duplicates = [
            action for action in result['duplicate_actions']
            if action['action'] == 'batch_duplicate_resolved'
        ]
        self.assertEqual(len(batch_duplicates), 1)
        self.assertEqual(batch_duplicates[0]['email'], 'john.doe@example.com')
        
        # Verify upsert was called with normalized and deduplicated data
        self.assertEqual(mock_upsert.call_count, 3)
        
        # Check that the last occurrence of John's data was used
        john_call = mock_upsert.call_args_list[0][0][0]
        self.assertEqual(john_call['company'], 'Last Corp')
        self.assertEqual(john_call['email'], 'john.doe@example.com')  # Normalized
    
    def test_email_normalization_integration_with_gsi_query(self):
        """Test that email normalization works correctly with GSI queries."""
        # Mock GSI query response
        existing_lead = {
            'leadId': 'existing-1',
            'firstName': 'John',
            'lastName': 'Doe',
            'email': 'john.doe@example.com',  # Stored normalized
            'company': 'Old Corp'
        }
        
        self.mock_table.query.return_value = {
            'Items': [existing_lead]
        }
        
        # Test finding with various email formats
        test_emails = [
            'john.doe@example.com',
            'JOHN.DOE@EXAMPLE.COM',
            '  john.doe@example.com  ',
            'John.Doe@Example.Com'
        ]
        
        for email in test_emails:
            result = self.db_utils.find_lead_by_email(email)
            self.assertIsNotNone(result)
            self.assertEqual(result['leadId'], 'existing-1')
            
            # Verify query was called with normalized email
            expected_normalized = EmailNormalizer.normalize_email(email)
            self.mock_table.query.assert_called_with(
                IndexName='EmailIndex',
                KeyConditionExpression='email = :email',
                ExpressionAttributeValues={':email': expected_normalized},
                Limit=1
            )
            
            # Reset mock for next iteration
            self.mock_table.query.reset_mock()
            self.mock_table.query.return_value = {'Items': [existing_lead]}
    
    def test_duplicate_detection_with_gsi_failure_fallback(self):
        """Test that duplicate detection gracefully handles GSI failures."""
        # Mock GSI unavailable error
        self.mock_table.query.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'GSI not found'}},
            'Query'
        )
        
        lead_data = {
            'firstName': 'John',
            'lastName': 'Doe',
            'email': 'john.doe@example.com',
            'company': 'Test Corp'
        }
        
        # Should fall back to creating new lead
        lead_id, was_updated = self.db_utils.upsert_lead(lead_data, 'test.csv')
        
        self.assertIsNotNone(lead_id)
        self.assertFalse(was_updated)  # Should create new lead when GSI fails
        
        # Verify put_item was called (new lead created)
        self.mock_table.put_item.assert_called_once()
    
    def test_batch_processing_with_mixed_scenarios(self):
        """Test batch processing with mix of duplicates, new leads, and edge cases."""
        batch_data = [
            {'firstName': 'John', 'lastName': 'Doe', 'email': 'john@example.com', 'company': 'Corp 1'},
            {'firstName': 'Jane', 'lastName': 'Smith', 'email': 'jane@example.com', 'company': 'Corp 2'},
            {'firstName': 'John', 'lastName': 'Updated', 'email': 'JOHN@EXAMPLE.COM', 'company': 'Corp 3'},  # Batch duplicate
            {'firstName': 'Bob', 'lastName': 'Wilson', 'email': '', 'company': 'Corp 4'},  # Empty email
            {'firstName': 'Alice', 'lastName': 'Brown', 'email': 'N/A', 'company': 'Corp 5'},  # N/A email
        ]
        
        # Mock find_lead_by_email to return existing lead for Jane
        def mock_find_lead(email):
            normalized = EmailNormalizer.normalize_email(email)
            if normalized == 'jane@example.com':
                return {
                    'leadId': 'existing-jane',
                    'firstName': 'Jane',
                    'lastName': 'Old',
                    'email': 'jane@example.com',
                    'company': 'Old Corp',
                    'createdAt': '2025-01-01T00:00:00Z'
                }
            return None
        
        with patch.object(self.db_utils, 'find_lead_by_email', side_effect=mock_find_lead):
            # Mock put_item for upsert operations
            result = self.db_utils.batch_upsert_leads(batch_data, 'test.csv')
        
        # Verify processing stats
        stats = result['processing_stats']
        self.assertEqual(stats['total_leads_processed'], 5)
        self.assertEqual(stats['unique_leads_after_dedup'], 4)  # John deduplicated within batch
        
        # Verify batch duplicate resolution
        batch_duplicates = [
            action for action in result['duplicate_actions']
            if action['action'] == 'batch_duplicate_resolved'
        ]
        self.assertEqual(len(batch_duplicates), 1)  # John's duplicate
        
        # Verify put_item was called for each unique lead (4 calls)
        self.assertEqual(self.mock_table.put_item.call_count, 4)
    
    def test_performance_metrics_accuracy(self):
        """Test that performance metrics are accurately calculated."""
        batch_data = [
            {'firstName': 'John', 'lastName': 'Doe', 'email': 'john@example.com'},
            {'firstName': 'Jane', 'lastName': 'Smith', 'email': 'jane@example.com'}
        ]
        
        # Mock upsert to simulate one update and one create
        with patch.object(self.db_utils, 'upsert_lead') as mock_upsert:
            mock_upsert.side_effect = [
                ('john-1', True),    # Updated existing
                ('jane-1', False)    # Created new
            ]
            
            result = self.db_utils.batch_upsert_leads(batch_data, 'test.csv')
        
        stats = result['processing_stats']
        
        # Verify all required metrics are present
        required_metrics = [
            'total_leads_processed',
            'unique_leads_after_dedup',
            'leads_created',
            'leads_updated',
            'batch_duplicates_resolved',
            'processing_time_ms',
            'email_index_queries'
        ]
        
        for metric in required_metrics:
            self.assertIn(metric, stats)
        
        # Verify metric values
        self.assertEqual(stats['total_leads_processed'], 2)
        self.assertEqual(stats['unique_leads_after_dedup'], 2)
        self.assertEqual(stats['leads_created'], 1)
        self.assertEqual(stats['leads_updated'], 1)
        self.assertEqual(stats['batch_duplicates_resolved'], 0)
        self.assertEqual(stats['email_index_queries'], 2)
        self.assertGreaterEqual(stats['processing_time_ms'], 0)


if __name__ == '__main__':
    unittest.main()