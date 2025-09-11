"""
Unit tests for phone field error handling.
Tests phone-specific error classes and handling.
"""

import unittest
import sys
import os

# Add lambda paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))

from error_handling import PhoneValidationError, ValidationError, create_error_response


class TestPhoneErrorHandling(unittest.TestCase):
    """Test cases for phone field error handling."""
    
    def test_phone_validation_error_creation(self):
        """Test creation of PhoneValidationError."""
        error = PhoneValidationError("Invalid phone format", phone_value="invalid-phone")
        
        self.assertEqual(error.message, "Invalid phone format")
        self.assertEqual(error.phone_value, "invalid-phone")
        self.assertEqual(error.field, "phone")
        self.assertEqual(error.status_code, 400)
        self.assertEqual(error.error_code, "VALIDATION_ERROR")
    
    def test_phone_validation_error_inheritance(self):
        """Test that PhoneValidationError inherits from ValidationError."""
        error = PhoneValidationError("Test error")
        
        self.assertIsInstance(error, ValidationError)
        self.assertIsInstance(error, Exception)
    
    def test_phone_validation_error_without_phone_value(self):
        """Test PhoneValidationError creation without phone_value."""
        error = PhoneValidationError("Phone is required")
        
        self.assertEqual(error.message, "Phone is required")
        self.assertIsNone(error.phone_value)
        self.assertEqual(error.field, "phone")
    
    def test_create_error_response_with_phone_error(self):
        """Test error response creation with PhoneValidationError."""
        error = PhoneValidationError("Invalid phone format: abc-def", phone_value="abc-def")
        response = create_error_response(error, request_id="test-request-123")
        
        self.assertEqual(response['statusCode'], 400)
        self.assertIn('application/json', response['headers']['Content-Type'])
        
        # Parse response body
        import json
        body = json.loads(response['body'])
        
        self.assertEqual(body['error']['code'], 'VALIDATION_ERROR')
        self.assertEqual(body['error']['message'], 'Invalid phone format: abc-def')
        self.assertEqual(body['error']['requestId'], 'test-request-123')
        self.assertIn('timestamp', body['error'])
    
    def test_phone_validation_error_str_representation(self):
        """Test string representation of PhoneValidationError."""
        error = PhoneValidationError("Invalid phone format", phone_value="+1-invalid")
        
        self.assertEqual(str(error), "Invalid phone format")
    
    def test_phone_validation_error_with_special_characters(self):
        """Test PhoneValidationError with special characters in phone value."""
        special_phone = "++1-555-123-4567!@#"
        error = PhoneValidationError("Phone contains invalid characters", phone_value=special_phone)
        
        self.assertEqual(error.phone_value, special_phone)
        self.assertEqual(error.field, "phone")
        self.assertIn("invalid characters", error.message)


if __name__ == '__main__':
    unittest.main()