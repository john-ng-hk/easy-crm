"""
Unit tests for DeepSeek Caller Lambda function.
Tests SQS message processing and DeepSeek integration.
"""

import json
import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
import boto3
from moto import mock_aws

# Add lambda paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'deepseek-caller'))

from lambda_function import (
    lambda_handler,
    DeepSeekClient,
    process_batch_with_deepseek
)
from error_handling import ExternalAPIError


class TestDeepSeekCaller(unittest.TestCase):
    """Test cases for DeepSeek Caller Lambda function."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_batch_data = {
            'batch_id': 'test-batch-123',
            'source_file': 'test.csv',
            'batch_number': 1,
            'total_batches': 1,
            'leads': [
                {
                    'Name': 'John Doe',
                    'Company': 'Acme Corp',
                    'Email': 'john@acme.com',
                    'Phone': '555-1234',
                    'Title': 'Sales Manager'
                }
            ]
        }
        
        self.mock_deepseek_response = [
            {
                'firstName': 'John',
                'lastName': 'Doe',
                'company': 'Acme Corp',
                'email': 'john@acme.com',
                'phone': '555-1234',
                'title': 'Sales Manager',
                'remarks': 'N/A'
            }
        ]
    
    def test_deepseek_client_initialization(self):
        """Test DeepSeek client initialization."""
        client = DeepSeekClient('test-api-key')
        self.assertEqual(client.api_key, 'test-api-key')
        self.assertEqual(client.base_url, 'https://api.deepseek.com')
    
    @patch('requests.post')
    def test_deepseek_standardization_success(self, mock_post):
        """Test successful DeepSeek API call."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': json.dumps(self.mock_deepseek_response)
                }
            }]
        }
        mock_post.return_value = mock_response
        
        client = DeepSeekClient('test-api-key')
        result = client.standardize_leads(self.test_batch_data['leads'])
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['firstName'], 'John')
        self.assertEqual(result[0]['lastName'], 'Doe')
        self.assertEqual(result[0]['phone'], '555-1234')
    
    @patch('requests.post')
    def test_deepseek_api_error(self, mock_post):
        """Test DeepSeek API error handling."""
        # Mock API error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = 'Bad Request'
        mock_post.return_value = mock_response
        
        client = DeepSeekClient('test-api-key')
        
        with self.assertRaises(ExternalAPIError):
            client.standardize_leads(self.test_batch_data['leads'])
    
    def test_process_batch_success(self):
        """Test successful batch processing with duplicate handling."""
        with patch.dict(os.environ, {
            'LEADS_TABLE': 'test-leads',
            'DEEPSEEK_API_KEY': 'test-key',
            'AWS_REGION': 'ap-southeast-1'
        }):
            with patch('lambda_function.DEEPSEEK_API_KEY', 'test-key'):
                with patch('lambda_function.DeepSeekClient') as mock_client_class:
                    with patch('lambda_function.DynamoDBUtils') as mock_db_class:
                        # Mock DeepSeek client
                        mock_client = Mock()
                        mock_client.standardize_leads.return_value = self.mock_deepseek_response
                        mock_client_class.return_value = mock_client
                        
                        # Mock DynamoDB utils with duplicate handling
                        mock_db = Mock()
                        mock_upsert_result = {
                            'created_leads': ['lead-id-1'],
                            'updated_leads': [],
                            'duplicate_actions': [],
                            'processing_stats': {
                                'total_leads_processed': 1,
                                'leads_created': 1,
                                'leads_updated': 0,
                                'processing_time_ms': 150
                            }
                        }
                        mock_db.batch_upsert_leads.return_value = mock_upsert_result
                        mock_db_class.return_value = mock_db
                        
                        result = process_batch_with_deepseek(self.test_batch_data, mock_db)
                
                self.assertEqual(result['batch_id'], 'test-batch-123')
                self.assertEqual(result['stored_leads'], 1)
                self.assertEqual(result['created_leads'], 1)
                self.assertEqual(result['updated_leads'], 0)
                self.assertIn('duplicate_actions', result)
                self.assertIn('processing_stats', result)
    
    def test_sqs_event_processing(self):
        """Test SQS event processing with duplicate handling."""
        sqs_event = {
            'Records': [{
                'body': json.dumps(self.test_batch_data)
            }]
        }
        
        with patch.dict(os.environ, {
            'LEADS_TABLE': 'test-leads',
            'DEEPSEEK_API_KEY': 'test-key'
        }):
            with patch('lambda_function.process_batch_with_deepseek') as mock_process:
                mock_process.return_value = {
                    'batch_id': 'test-batch-123',
                    'stored_leads': 1,
                    'created_leads': 1,
                    'updated_leads': 0,
                    'duplicate_actions': []
                }
                
                response = lambda_handler(sqs_event, {})
                
                self.assertEqual(response['statusCode'], 200)
                self.assertIn('summary', response['body'])
                self.assertEqual(response['body']['summary']['total_created'], 1)
                self.assertEqual(response['body']['summary']['total_updated'], 0)
                mock_process.assert_called_once()
    
    def test_invalid_sqs_message(self):
        """Test handling of invalid SQS messages."""
        sqs_event = {
            'Records': [{
                'body': 'invalid-json'
            }]
        }
        
        response = lambda_handler(sqs_event, {})
        
        # Should handle gracefully and return success
        self.assertEqual(response['statusCode'], 200)
    
    def test_missing_api_key(self):
        """Test handling of missing DeepSeek API key."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('lambda_function.DynamoDBUtils') as mock_db_class:
                mock_db = Mock()
                mock_db_class.return_value = mock_db
                
                with self.assertRaises(ExternalAPIError):
                    process_batch_with_deepseek(self.test_batch_data, mock_db)
    
    @patch('requests.post')
    def test_phone_field_processing(self, mock_post):
        """Test that phone field is properly processed from DeepSeek response."""
        # Mock DeepSeek response with phone field
        deepseek_response_with_phone = [
            {
                'firstName': 'Jane',
                'lastName': 'Smith',
                'company': 'Tech Corp',
                'email': 'jane@techcorp.com',
                'phone': '+1-555-987-6543',
                'title': 'Developer',
                'remarks': 'N/A'
            }
        ]
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': json.dumps(deepseek_response_with_phone)
                }
            }]
        }
        mock_post.return_value = mock_response
        
        client = DeepSeekClient('test-api-key')
        result = client.standardize_leads([{
            'Name': 'Jane Smith',
            'Company': 'Tech Corp',
            'Email': 'jane@techcorp.com',
            'Phone': '+1-555-987-6543',
            'Title': 'Developer'
        }])
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['phone'], '+1-555-987-6543')
    
    @patch('requests.post')
    def test_phone_field_missing_value(self, mock_post):
        """Test that missing phone field defaults to N/A."""
        deepseek_response_no_phone = [
            {
                'firstName': 'Bob',
                'lastName': 'Johnson',
                'company': 'No Phone Corp',
                'email': 'bob@nophone.com',
                'phone': 'N/A',
                'title': 'Manager',
                'remarks': 'N/A'
            }
        ]
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': json.dumps(deepseek_response_no_phone)
                }
            }]
        }
        mock_post.return_value = mock_response
        
        client = DeepSeekClient('test-api-key')
        result = client.standardize_leads([{
            'Name': 'Bob Johnson',
            'Company': 'No Phone Corp',
            'Email': 'bob@nophone.com',
            'Title': 'Manager'
        }])
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['phone'], 'N/A')
    
    def test_deepseek_prompt_includes_phone(self):
        """Test that DeepSeek prompt includes phone field."""
        client = DeepSeekClient('test-api-key')
        prompt = client._create_standardization_prompt([{
            'Name': 'Test User',
            'Phone': '123-456-7890'
        }])
        
        # Check that prompt mentions phone field
        self.assertIn('phone', prompt.lower())
        self.assertIn('firstName, lastName, title, company, email, phone, remarks', prompt)
    
    def test_process_batch_with_duplicates(self):
        """Test batch processing with duplicate leads."""
        with patch.dict(os.environ, {
            'LEADS_TABLE': 'test-leads',
            'DEEPSEEK_API_KEY': 'test-key',
            'AWS_REGION': 'ap-southeast-1'
        }):
            with patch('lambda_function.DEEPSEEK_API_KEY', 'test-key'):
                with patch('lambda_function.DeepSeekClient') as mock_client_class:
                    with patch('lambda_function.DynamoDBUtils') as mock_db_class:
                        # Mock DeepSeek client
                        mock_client = Mock()
                        mock_client.standardize_leads.return_value = self.mock_deepseek_response
                        mock_client_class.return_value = mock_client
                        
                        # Mock DynamoDB utils with duplicate detection
                        mock_db = Mock()
                        mock_upsert_result = {
                            'created_leads': [],
                            'updated_leads': ['existing-lead-id-1'],
                            'duplicate_actions': [{
                                'action': 'lead_updated',
                                'email': 'john@acme.com',
                                'leadId': 'existing-lead-id-1',
                                'timestamp': '2025-01-20T10:00:00Z'
                            }],
                            'processing_stats': {
                                'total_leads_processed': 1,
                                'leads_created': 0,
                                'leads_updated': 1,
                                'processing_time_ms': 200
                            }
                        }
                        mock_db.batch_upsert_leads.return_value = mock_upsert_result
                        mock_db_class.return_value = mock_db
                        
                        result = process_batch_with_deepseek(self.test_batch_data, mock_db)
                
                self.assertEqual(result['batch_id'], 'test-batch-123')
                self.assertEqual(result['stored_leads'], 1)
                self.assertEqual(result['created_leads'], 0)
                self.assertEqual(result['updated_leads'], 1)
                self.assertEqual(len(result['duplicate_actions']), 1)
                self.assertEqual(result['duplicate_actions'][0]['action'], 'lead_updated')
    
    def test_process_batch_with_fallback(self):
        """Test batch processing fallback when duplicate handling fails."""
        with patch.dict(os.environ, {
            'LEADS_TABLE': 'test-leads',
            'DEEPSEEK_API_KEY': 'test-key',
            'AWS_REGION': 'ap-southeast-1'
        }):
            with patch('lambda_function.DEEPSEEK_API_KEY', 'test-key'):
                with patch('lambda_function.DeepSeekClient') as mock_client_class:
                    with patch('lambda_function.DynamoDBUtils') as mock_db_class:
                        # Mock DeepSeek client
                        mock_client = Mock()
                        mock_client.standardize_leads.return_value = self.mock_deepseek_response
                        mock_client_class.return_value = mock_client
                        
                        # Mock DynamoDB utils with upsert failure and successful fallback
                        mock_db = Mock()
                        mock_db.batch_upsert_leads.side_effect = Exception("EmailIndex GSI unavailable")
                        mock_db.batch_create_leads.return_value = ['fallback-lead-id-1']
                        mock_db_class.return_value = mock_db
                        
                        result = process_batch_with_deepseek(self.test_batch_data, mock_db)
                
                self.assertEqual(result['batch_id'], 'test-batch-123')
                self.assertEqual(result['stored_leads'], 1)
                self.assertEqual(result['created_leads'], 1)
                self.assertEqual(result['updated_leads'], 0)
                self.assertTrue(result['fallback_used'])
                self.assertEqual(len(result['duplicate_actions']), 1)
                self.assertEqual(result['duplicate_actions'][0]['action'], 'duplicate_detection_fallback')


if __name__ == '__main__':
    unittest.main()