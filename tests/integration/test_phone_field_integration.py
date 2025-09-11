"""
Integration test for phone field functionality in DeepSeek Caller.
Tests that phone field is properly processed through the entire pipeline.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch, Mock
import boto3
from moto import mock_aws

# Add lambda paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'deepseek-caller'))

from lambda_function import DeepSeekClient, process_batch_with_deepseek
from validation import LeadValidator
from dynamodb_utils import DynamoDBUtils


class TestPhoneFieldIntegration(unittest.TestCase):
    """Integration tests for phone field processing."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_batch_with_phone = {
            'batch_id': 'phone-test-batch',
            'source_file': 'phone_test.csv',
            'batch_number': 1,
            'total_batches': 1,
            'leads': [
                {
                    'Name': 'Alice Johnson',
                    'Company': 'Phone Corp',
                    'Email': 'alice@phonecorp.com',
                    'Phone': '+1-555-123-4567',
                    'Title': 'Phone Manager'
                },
                {
                    'Full Name': 'Bob Wilson',
                    'Organization': 'No Phone Inc',
                    'Email Address': 'bob@nophone.com',
                    'Job Title': 'Director'
                    # No phone field
                }
            ]
        }
    
    @patch('requests.post')
    def test_deepseek_phone_field_processing(self, mock_post):
        """Test that DeepSeek properly processes phone fields."""
        # Mock DeepSeek response with phone field
        mock_deepseek_response = [
            {
                'firstName': 'Alice',
                'lastName': 'Johnson',
                'company': 'Phone Corp',
                'email': 'alice@phonecorp.com',
                'phone': '+1-555-123-4567',
                'title': 'Phone Manager',
                'remarks': 'N/A'
            },
            {
                'firstName': 'Bob',
                'lastName': 'Wilson',
                'company': 'No Phone Inc',
                'email': 'bob@nophone.com',
                'phone': 'N/A',
                'title': 'Director',
                'remarks': 'N/A'
            }
        ]
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': json.dumps(mock_deepseek_response)
                }
            }]
        }
        mock_post.return_value = mock_response
        
        # Test DeepSeek client
        client = DeepSeekClient('test-api-key')
        result = client.standardize_leads(self.test_batch_with_phone['leads'])
        
        # Verify phone field is included in results
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['phone'], '+1-555-123-4567')
        self.assertEqual(result[1]['phone'], 'N/A')
        
        # Verify the prompt includes phone field
        call_args = mock_post.call_args
        prompt_content = call_args[1]['json']['messages'][1]['content']
        self.assertIn('phone', prompt_content.lower())
    
    def test_phone_validation_integration(self):
        """Test phone validation in the validation pipeline."""
        # Test valid phone
        valid_lead_with_phone = {
            'firstName': 'Test',
            'lastName': 'User',
            'company': 'Test Corp',
            'email': 'test@test.com',
            'phone': '+1-555-123-4567',
            'title': 'Tester',
            'remarks': 'N/A'
        }
        
        is_valid, errors = LeadValidator.validate_lead_data(valid_lead_with_phone)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Test invalid phone
        invalid_lead_with_phone = {
            'firstName': 'Test',
            'lastName': 'User',
            'company': 'Test Corp',
            'email': 'test@test.com',
            'phone': 'invalid-phone-format',
            'title': 'Tester',
            'remarks': 'N/A'
        }
        
        is_valid, errors = LeadValidator.validate_lead_data(invalid_lead_with_phone)
        self.assertFalse(is_valid)
        self.assertTrue(any('phone' in error.lower() for error in errors))
    
    @mock_aws
    def test_phone_field_storage_integration(self):
        """Test that phone field is properly stored in DynamoDB."""
        # Setup DynamoDB mock
        dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
        table = dynamodb.create_table(
            TableName='test-phone-leads',
            KeySchema=[{'AttributeName': 'leadId', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'leadId', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Test data with phone
        lead_data = {
            'firstName': 'Phone',
            'lastName': 'Test',
            'company': 'Phone Corp',
            'email': 'phone@test.com',
            'phone': '+1-555-987-6543',
            'title': 'Phone Tester',
            'remarks': 'Test lead with phone'
        }
        
        # Create DynamoDB utils and store lead
        db_utils = DynamoDBUtils('test-phone-leads', 'ap-southeast-1')
        lead_id = db_utils.create_lead(lead_data, 'phone_test.csv')
        
        # Retrieve and verify
        stored_lead = db_utils.get_lead(lead_id)
        self.assertIsNotNone(stored_lead)
        self.assertEqual(stored_lead['phone'], '+1-555-987-6543')
        self.assertEqual(stored_lead['firstName'], 'Phone')
    
    def test_phone_field_in_batch_processing(self):
        """Test phone field processing in complete batch workflow."""
        with patch.dict(os.environ, {
            'LEADS_TABLE': 'test-leads',
            'DEEPSEEK_API_KEY': 'test-key',
            'AWS_REGION': 'ap-southeast-1'
        }):
            with patch('lambda_function.DEEPSEEK_API_KEY', 'test-key'):
                with patch('lambda_function.DeepSeekClient') as mock_client_class:
                    with patch('lambda_function.DynamoDBUtils') as mock_db_class:
                        # Mock DeepSeek response with phone
                        mock_deepseek_response = [
                            {
                                'firstName': 'Alice',
                                'lastName': 'Johnson',
                                'company': 'Phone Corp',
                                'email': 'alice@phonecorp.com',
                                'phone': '+1-555-123-4567',
                                'title': 'Phone Manager',
                                'remarks': 'N/A'
                            }
                        ]
                        
                        mock_client = Mock()
                        mock_client.standardize_leads.return_value = mock_deepseek_response
                        mock_client_class.return_value = mock_client
                        
                        # Mock DynamoDB
                        mock_db = Mock()
                        mock_db.batch_create_leads.return_value = ['lead-id-1']
                        mock_db_class.return_value = mock_db
                        
                        # Process batch
                        result = process_batch_with_deepseek({
                            'batch_id': 'phone-batch',
                            'source_file': 'phone.csv',
                            'batch_number': 1,
                            'total_batches': 1,
                            'leads': [{
                                'Name': 'Alice Johnson',
                                'Phone': '+1-555-123-4567',
                                'Company': 'Phone Corp'
                            }]
                        })
                        
                        # Verify processing succeeded
                        self.assertEqual(result['batch_id'], 'phone-batch')
                        self.assertEqual(result['stored_leads'], 1)
                        
                        # Verify DynamoDB was called with phone field
                        mock_db.batch_create_leads.assert_called_once()
                        stored_leads = mock_db.batch_create_leads.call_args[0][0]
                        self.assertEqual(len(stored_leads), 1)
                        self.assertEqual(stored_leads[0]['phone'], '+1-555-123-4567')


if __name__ == '__main__':
    unittest.main()