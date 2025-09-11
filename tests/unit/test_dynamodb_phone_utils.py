"""
Unit tests for phone field utilities in DynamoDBUtils.
Tests phone-specific database operations.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add lambda paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))

from dynamodb_utils import DynamoDBUtils
from botocore.exceptions import ClientError


class TestDynamoDBPhoneUtils(unittest.TestCase):
    """Test cases for phone field utilities in DynamoDB operations."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch('boto3.resource'):
            self.db_utils = DynamoDBUtils('test-table')
            self.db_utils.table = Mock()
    
    def test_search_leads_by_phone_exact_match(self):
        """Test searching leads by phone with exact match."""
        # Mock response
        mock_response = {
            'Items': [
                {
                    'leadId': 'test-id-1',
                    'firstName': 'John',
                    'lastName': 'Doe',
                    'phone': '+1-555-123-4567'
                }
            ]
        }
        
        self.db_utils.table.scan.return_value = mock_response
        
        results = self.db_utils.search_leads_by_phone('+1-555-123-4567', exact_match=True)
        
        # Verify scan was called with correct parameters
        self.db_utils.table.scan.assert_called_once()
        call_args = self.db_utils.table.scan.call_args[1]
        
        self.assertEqual(call_args['FilterExpression'], '#phone = :phone_value')
        self.assertEqual(call_args['ExpressionAttributeNames'], {'#phone': 'phone'})
        self.assertEqual(call_args['ExpressionAttributeValues'], {':phone_value': '+1-555-123-4567'})
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['phone'], '+1-555-123-4567')
    
    def test_search_leads_by_phone_partial_match(self):
        """Test searching leads by phone with partial match."""
        # Mock response
        mock_response = {
            'Items': [
                {
                    'leadId': 'test-id-1',
                    'firstName': 'John',
                    'lastName': 'Doe',
                    'phone': '+1-555-123-4567'
                },
                {
                    'leadId': 'test-id-2',
                    'firstName': 'Jane',
                    'lastName': 'Smith',
                    'phone': '555-123-9999'
                }
            ]
        }
        
        self.db_utils.table.scan.return_value = mock_response
        
        results = self.db_utils.search_leads_by_phone('555-123', exact_match=False)
        
        # Verify scan was called with correct parameters
        self.db_utils.table.scan.assert_called_once()
        call_args = self.db_utils.table.scan.call_args[1]
        
        self.assertEqual(call_args['FilterExpression'], 'contains(#phone, :phone_value)')
        self.assertEqual(call_args['ExpressionAttributeNames'], {'#phone': 'phone'})
        self.assertEqual(call_args['ExpressionAttributeValues'], {':phone_value': '555-123'})
        
        # Verify results
        self.assertEqual(len(results), 2)
    
    def test_search_leads_by_phone_with_pagination(self):
        """Test searching leads by phone with pagination."""
        # Mock multiple responses for pagination
        first_response = {
            'Items': [
                {
                    'leadId': 'test-id-1',
                    'firstName': 'John',
                    'lastName': 'Doe',
                    'phone': '+1-555-123-4567'
                }
            ],
            'LastEvaluatedKey': {'leadId': 'test-id-1'}
        }
        
        second_response = {
            'Items': [
                {
                    'leadId': 'test-id-2',
                    'firstName': 'Jane',
                    'lastName': 'Smith',
                    'phone': '555-123-9999'
                }
            ]
        }
        
        self.db_utils.table.scan.side_effect = [first_response, second_response]
        
        results = self.db_utils.search_leads_by_phone('555', exact_match=False)
        
        # Verify scan was called twice (pagination)
        self.assertEqual(self.db_utils.table.scan.call_count, 2)
        
        # Verify results from both pages
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['leadId'], 'test-id-1')
        self.assertEqual(results[1]['leadId'], 'test-id-2')
    
    def test_search_leads_by_phone_client_error(self):
        """Test handling of ClientError in phone search."""
        self.db_utils.table.scan.side_effect = ClientError(
            {'Error': {'Code': 'ValidationException', 'Message': 'Test error'}},
            'Scan'
        )
        
        with self.assertRaises(ClientError):
            self.db_utils.search_leads_by_phone('555-123-4567')
    
    def test_update_lead_phone_success(self):
        """Test successful phone number update."""
        mock_response = {
            'Attributes': {
                'phone': '+1-555-999-8888',
                'updatedAt': '2023-01-01T00:00:00'
            }
        }
        
        self.db_utils.table.update_item.return_value = mock_response
        
        result = self.db_utils.update_lead_phone('test-lead-id', '+1-555-999-8888')
        
        # Verify update_item was called with correct parameters
        self.db_utils.table.update_item.assert_called_once()
        call_args = self.db_utils.table.update_item.call_args[1]
        
        self.assertEqual(call_args['Key'], {'leadId': 'test-lead-id'})
        self.assertEqual(call_args['UpdateExpression'], 'SET phone = :phone, updatedAt = :updated')
        self.assertEqual(call_args['ExpressionAttributeValues'][':phone'], '+1-555-999-8888')
        self.assertIn(':updated', call_args['ExpressionAttributeValues'])
        
        # Verify result
        self.assertTrue(result)
    
    def test_update_lead_phone_client_error(self):
        """Test handling of ClientError in phone update."""
        self.db_utils.table.update_item.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Lead not found'}},
            'UpdateItem'
        )
        
        with self.assertRaises(ClientError):
            self.db_utils.update_lead_phone('nonexistent-lead', '+1-555-999-8888')
    
    def test_create_lead_with_phone(self):
        """Test creating lead with phone field."""
        lead_data = {
            'firstName': 'John',
            'lastName': 'Doe',
            'company': 'Acme Corp',
            'email': 'john@acme.com',
            'phone': '+1-555-123-4567',
            'title': 'Manager',
            'remarks': 'Test lead'
        }
        
        # Mock successful put_item
        self.db_utils.table.put_item.return_value = {}
        
        lead_id = self.db_utils.create_lead(lead_data, 'test-file.csv')
        
        # Verify put_item was called
        self.db_utils.table.put_item.assert_called_once()
        call_args = self.db_utils.table.put_item.call_args[1]
        
        # Verify phone field is included in the item
        item = call_args['Item']
        self.assertEqual(item['phone'], '+1-555-123-4567')
        self.assertIsNotNone(item['leadId'])
        self.assertEqual(item['sourceFile'], 'test-file.csv')
        
        # Verify lead_id is returned
        self.assertIsInstance(lead_id, str)
        self.assertTrue(len(lead_id) > 0)
    
    def test_batch_create_leads_with_phone(self):
        """Test batch creating leads with phone fields."""
        leads_data = [
            {
                'firstName': 'John',
                'lastName': 'Doe',
                'phone': '+1-555-123-4567',
                'email': 'john@example.com'
            },
            {
                'firstName': 'Jane',
                'lastName': 'Smith',
                'phone': '555-987-6543',
                'email': 'jane@example.com'
            }
        ]
        
        # Mock batch writer
        mock_batch = MagicMock()
        mock_context_manager = MagicMock()
        mock_context_manager.__enter__.return_value = mock_batch
        mock_context_manager.__exit__.return_value = None
        self.db_utils.table.batch_writer.return_value = mock_context_manager
        
        lead_ids = self.db_utils.batch_create_leads(leads_data, 'test-batch.csv')
        
        # Verify batch operations
        self.assertEqual(mock_batch.put_item.call_count, 2)
        
        # Verify phone fields in batch items
        call_args_list = mock_batch.put_item.call_args_list
        
        first_item = call_args_list[0][1]['Item']
        second_item = call_args_list[1][1]['Item']
        
        self.assertEqual(first_item['phone'], '+1-555-123-4567')
        self.assertEqual(second_item['phone'], '555-987-6543')
        
        # Verify lead IDs returned
        self.assertEqual(len(lead_ids), 2)
        self.assertTrue(all(isinstance(lead_id, str) for lead_id in lead_ids))


if __name__ == '__main__':
    unittest.main()