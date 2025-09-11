"""
Unit tests for phone field validation in LeadValidator.
Tests phone number validation and processing.
"""

import unittest
import sys
import os

# Add lambda paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared'))

from validation import LeadValidator


class TestPhoneValidation(unittest.TestCase):
    """Test cases for phone field validation."""
    
    def test_validate_phone_valid_formats(self):
        """Test validation of valid phone number formats."""
        valid_phones = [
            '+1-555-123-4567',
            '555-123-4567',
            '(555) 123-4567',
            '+44 20 7946 0958',
            '1234567890',
            '+1 555 123 4567',
            '555.123.4567',
            'N/A',
            '',
            None
        ]
        
        for phone in valid_phones:
            with self.subTest(phone=phone):
                self.assertTrue(LeadValidator.validate_phone(phone), 
                              f"Phone {phone} should be valid")
    
    def test_validate_phone_invalid_formats(self):
        """Test validation of invalid phone number formats."""
        invalid_phones = [
            '123',  # Too short
            'abc-def-ghij',  # Non-numeric
            '++1-555-123-4567',  # Double plus
            '555-123-456789012345',  # Too long
        ]
        
        for phone in invalid_phones:
            with self.subTest(phone=phone):
                self.assertFalse(LeadValidator.validate_phone(phone), 
                               f"Phone {phone} should be invalid")
    
    def test_validate_lead_data_with_phone(self):
        """Test lead validation with phone field."""
        # Valid lead with phone
        valid_lead = {
            'firstName': 'John',
            'lastName': 'Doe',
            'company': 'Acme Corp',
            'email': 'john@acme.com',
            'phone': '+1-555-123-4567',
            'title': 'Manager',
            'remarks': 'N/A'
        }
        
        is_valid, errors = LeadValidator.validate_lead_data(valid_lead)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_lead_data_invalid_phone(self):
        """Test lead validation with invalid phone field."""
        invalid_lead = {
            'firstName': 'John',
            'lastName': 'Doe',
            'company': 'Acme Corp',
            'email': 'john@acme.com',
            'phone': 'invalid-phone',
            'title': 'Manager',
            'remarks': 'N/A'
        }
        
        is_valid, errors = LeadValidator.validate_lead_data(invalid_lead)
        self.assertFalse(is_valid)
        self.assertTrue(any('Invalid phone format' in error for error in errors))
    
    def test_validate_lead_data_phone_na(self):
        """Test lead validation with phone field as N/A."""
        lead_with_na_phone = {
            'firstName': 'John',
            'lastName': 'Doe',
            'company': 'Acme Corp',
            'email': 'john@acme.com',
            'phone': 'N/A',
            'title': 'Manager',
            'remarks': 'N/A'
        }
        
        is_valid, errors = LeadValidator.validate_lead_data(lead_with_na_phone)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_phone_field_in_meaningful_fields(self):
        """Test that phone is considered a meaningful field."""
        # Lead with only phone field filled
        lead_with_only_phone = {
            'firstName': 'N/A',
            'lastName': 'N/A',
            'company': 'N/A',
            'email': 'N/A',
            'phone': '+1-555-123-4567',
            'title': 'N/A',
            'remarks': 'N/A'
        }
        
        is_valid, errors = LeadValidator.validate_lead_data(lead_with_only_phone)
        self.assertTrue(is_valid, "Lead with only phone should be valid")
    
    def test_transform_raw_data_with_phone(self):
        """Test transformation of raw data including phone field."""
        raw_data = {
            'Name': 'John Doe',
            'Company': 'Acme Corp',
            'Email': 'john@acme.com',
            'Phone': '+1-555-123-4567',
            'Job Title': 'Manager'
        }
        
        transformed = LeadValidator.transform_raw_data(raw_data)
        
        self.assertEqual(transformed['phone'], '+1-555-123-4567')
        self.assertEqual(transformed['firstName'], 'N/A')  # Name not split
        self.assertEqual(transformed['company'], 'Acme Corp')
        self.assertEqual(transformed['email'], 'john@acme.com')
    
    def test_phone_field_variations_mapping(self):
        """Test that various phone field names are mapped correctly."""
        phone_variations = [
            'phone',
            'phone_number',
            'telephone',
            'mobile',
            'cell',
            'contact_number',
            'tel'
        ]
        
        for variation in phone_variations:
            with self.subTest(variation=variation):
                raw_data = {
                    'Name': 'Test User',
                    variation: '+1-555-123-4567'
                }
                
                transformed = LeadValidator.transform_raw_data(raw_data)
                self.assertEqual(transformed['phone'], '+1-555-123-4567')
    
    def test_phone_field_length_validation(self):
        """Test phone field length validation."""
        # Phone too long (over 50 characters)
        long_phone = '+1-555-123-4567-extension-12345678901234567890'
        
        lead_with_long_phone = {
            'firstName': 'John',
            'lastName': 'Doe',
            'company': 'Acme Corp',
            'email': 'john@acme.com',
            'phone': long_phone,
            'title': 'Manager',
            'remarks': 'N/A'
        }
        
        is_valid, errors = LeadValidator.validate_lead_data(lead_with_long_phone)
        self.assertFalse(is_valid)
        # Should fail either due to invalid format or length - both are acceptable
        self.assertTrue(any('phone' in error.lower() for error in errors))
    
    def test_normalize_phone(self):
        """Test phone number normalization."""
        test_cases = [
            ('+1-555-123-4567', '+1-555-123-4567'),
            ('  555-123-4567  ', '555-123-4567'),
            ('N/A', 'N/A'),
            ('', 'N/A'),
            (None, 'N/A'),
            ('invalid-phone', 'N/A'),
            ('555   123   4567', '555 123 4567')  # Multiple spaces normalized
        ]
        
        for input_phone, expected in test_cases:
            with self.subTest(input_phone=input_phone):
                result = LeadValidator.normalize_phone(input_phone)
                self.assertEqual(result, expected)
    
    def test_extract_phone_digits(self):
        """Test extraction of digits from phone numbers."""
        test_cases = [
            ('+1-555-123-4567', '15551234567'),
            ('(555) 123-4567', '5551234567'),
            ('555.123.4567', '5551234567'),
            ('N/A', ''),
            ('', ''),
            (None, ''),
            ('abc-def-ghij', 'abcdefghij')  # Non-digits removed
        ]
        
        for input_phone, expected in test_cases:
            with self.subTest(input_phone=input_phone):
                result = LeadValidator.extract_phone_digits(input_phone)
                # For the last case, we expect only digits to remain
                if input_phone == 'abc-def-ghij':
                    self.assertEqual(result, '')  # No digits in this string
                else:
                    self.assertEqual(result, expected)
    
    def test_format_phone_for_display(self):
        """Test phone number formatting for display."""
        test_cases = [
            ('+1-555-123-4567', '+1-555-123-4567'),
            ('555-123-4567', '555-123-4567'),
            ('N/A', 'N/A'),
            ('', 'N/A'),
            (None, 'N/A'),
            ('invalid-phone', 'N/A'),
            ('  555-123-4567  ', '555-123-4567')  # Trimmed
        ]
        
        for input_phone, expected in test_cases:
            with self.subTest(input_phone=input_phone):
                result = LeadValidator.format_phone_for_display(input_phone)
                self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()