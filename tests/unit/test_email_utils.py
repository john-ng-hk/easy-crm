"""
Unit tests for email normalization utilities.

Tests cover email normalization, validation, and edge cases for duplicate
lead detection functionality.
"""

import pytest
import sys
import os

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lambda'))

from shared.email_utils import EmailNormalizer


class TestEmailNormalizer:
    """Test cases for EmailNormalizer class."""
    
    def test_normalize_email_basic_cases(self):
        """Test basic email normalization functionality."""
        # Standard email normalization
        assert EmailNormalizer.normalize_email("john@example.com") == "john@example.com"
        assert EmailNormalizer.normalize_email("JOHN@EXAMPLE.COM") == "john@example.com"
        assert EmailNormalizer.normalize_email("John.Doe@Example.Com") == "john.doe@example.com"
    
    def test_normalize_email_whitespace_handling(self):
        """Test whitespace trimming in email normalization."""
        # Leading and trailing whitespace
        assert EmailNormalizer.normalize_email("  john@example.com  ") == "john@example.com"
        assert EmailNormalizer.normalize_email("\tjohn@example.com\n") == "john@example.com"
        assert EmailNormalizer.normalize_email("   JOHN@EXAMPLE.COM   ") == "john@example.com"
        
        # Only whitespace
        assert EmailNormalizer.normalize_email("   ") == "N/A"
        assert EmailNormalizer.normalize_email("\t\n") == "N/A"
    
    def test_normalize_email_empty_values(self):
        """Test handling of empty and null-like values."""
        # None and empty string
        assert EmailNormalizer.normalize_email(None) == "N/A"
        assert EmailNormalizer.normalize_email("") == "N/A"
        
        # Various "N/A" representations
        assert EmailNormalizer.normalize_email("N/A") == "N/A"
        assert EmailNormalizer.normalize_email("n/a") == "N/A"
        assert EmailNormalizer.normalize_email("NA") == "N/A"
        assert EmailNormalizer.normalize_email("na") == "N/A"
        
        # Null-like values
        assert EmailNormalizer.normalize_email("null") == "N/A"
        assert EmailNormalizer.normalize_email("NULL") == "N/A"
        assert EmailNormalizer.normalize_email("none") == "N/A"
        assert EmailNormalizer.normalize_email("NONE") == "N/A"
        
        # Descriptive empty values
        assert EmailNormalizer.normalize_email("not available") == "N/A"
        assert EmailNormalizer.normalize_email("NOT AVAILABLE") == "N/A"
        assert EmailNormalizer.normalize_email("not provided") == "N/A"
        assert EmailNormalizer.normalize_email("NOT PROVIDED") == "N/A"
    
    def test_normalize_email_case_sensitivity(self):
        """Test case-insensitive normalization."""
        test_cases = [
            ("john@EXAMPLE.com", "john@example.com"),
            ("JOHN@example.COM", "john@example.com"),
            ("John.Doe@GMAIL.COM", "john.doe@gmail.com"),
            ("TEST.USER@Company.ORG", "test.user@company.org"),
        ]
        
        for input_email, expected in test_cases:
            assert EmailNormalizer.normalize_email(input_email) == expected
    
    def test_normalize_email_special_characters(self):
        """Test normalization with special characters in email."""
        # Valid special characters in email
        assert EmailNormalizer.normalize_email("user+tag@example.com") == "user+tag@example.com"
        assert EmailNormalizer.normalize_email("user.name@example.com") == "user.name@example.com"
        assert EmailNormalizer.normalize_email("user_name@example.com") == "user_name@example.com"
        assert EmailNormalizer.normalize_email("user-name@example.com") == "user-name@example.com"
        assert EmailNormalizer.normalize_email("user%test@example.com") == "user%test@example.com"
    
    def test_is_valid_email_format_valid_emails(self):
        """Test email format validation with valid emails."""
        valid_emails = [
            "john@example.com",
            "user.name@example.com",
            "user+tag@example.com",
            "user_name@example.com",
            "user-name@example.com",
            "test123@gmail.com",
            "user@subdomain.example.com",
            "user@example.co.uk",
            "a@b.co",
        ]
        
        for email in valid_emails:
            assert EmailNormalizer.is_valid_email_format(email), f"Email should be valid: {email}"
    
    def test_is_valid_email_format_invalid_emails(self):
        """Test email format validation with invalid emails."""
        invalid_emails = [
            "",  # Empty string
            "invalid-email",  # No @ symbol
            "@example.com",  # Missing local part
            "user@",  # Missing domain
            "user@@example.com",  # Double @
            "user@.com",  # Missing domain name
            "user@example.",  # Missing TLD
            "user@example",  # Missing TLD
            "user name@example.com",  # Space in local part
            "user@exam ple.com",  # Space in domain
            ".user@example.com",  # Leading dot
            "user.@example.com",  # Trailing dot
            "user@example..com",  # Double dot in domain
        ]
        
        for email in invalid_emails:
            assert not EmailNormalizer.is_valid_email_format(email), f"Email should be invalid: {email}"
    
    def test_is_valid_email_format_empty_values(self):
        """Test email format validation with empty and null-like values."""
        empty_values = [
            None,
            "",
            "N/A",
            "n/a",
            "null",
            "NULL",
            "none",
            "NONE",
            "not available",
            "not provided",
        ]
        
        for value in empty_values:
            assert not EmailNormalizer.is_valid_email_format(value), f"Empty value should be invalid: {value}"
    
    def test_is_valid_email_format_case_insensitive(self):
        """Test that email validation is case-insensitive."""
        test_cases = [
            "john@EXAMPLE.COM",
            "JOHN@example.com",
            "John.Doe@Gmail.COM",
            "TEST@COMPANY.ORG",
        ]
        
        for email in test_cases:
            assert EmailNormalizer.is_valid_email_format(email), f"Email should be valid regardless of case: {email}"
    
    def test_is_valid_email_format_whitespace_handling(self):
        """Test email validation with whitespace."""
        # Valid emails with whitespace (should be trimmed)
        assert EmailNormalizer.is_valid_email_format("  john@example.com  ")
        assert EmailNormalizer.is_valid_email_format("\tjohn@example.com\n")
        
        # Only whitespace (should be invalid)
        assert not EmailNormalizer.is_valid_email_format("   ")
        assert not EmailNormalizer.is_valid_email_format("\t\n")
    
    def test_is_empty_email(self):
        """Test empty email detection."""
        # Empty values
        empty_values = [
            None,
            "",
            "N/A",
            "n/a",
            "null",
            "none",
            "not available",
            "not provided",
            "  ",  # Only whitespace
        ]
        
        for value in empty_values:
            assert EmailNormalizer.is_empty_email(value), f"Should be treated as empty: {value}"
        
        # Non-empty values
        non_empty_values = [
            "john@example.com",
            "invalid-email",  # Invalid but not empty
            "@example.com",  # Invalid but not empty
            "test",  # Invalid but not empty
        ]
        
        for value in non_empty_values:
            assert not EmailNormalizer.is_empty_email(value), f"Should not be treated as empty: {value}"
    
    def test_normalize_email_edge_cases(self):
        """Test edge cases in email normalization."""
        # Very long email
        long_email = "a" * 50 + "@" + "b" * 50 + ".com"
        assert EmailNormalizer.normalize_email(long_email) == long_email.lower()
        
        # Email with numbers
        assert EmailNormalizer.normalize_email("user123@example456.com") == "user123@example456.com"
        
        # Email with mixed case and special chars
        mixed_email = "User.Name+Tag@Example-Domain.CO.UK"
        expected = "user.name+tag@example-domain.co.uk"
        assert EmailNormalizer.normalize_email(mixed_email) == expected
    
    def test_email_validation_edge_cases(self):
        """Test edge cases in email validation."""
        # Minimum valid email
        assert EmailNormalizer.is_valid_email_format("a@b.co")
        
        # Email with numbers
        assert EmailNormalizer.is_valid_email_format("user123@example456.com")
        
        # Email with hyphens
        assert EmailNormalizer.is_valid_email_format("user-name@example-domain.com")
        
        # International domain
        assert EmailNormalizer.is_valid_email_format("user@example.co.uk")
        
        # Subdomain
        assert EmailNormalizer.is_valid_email_format("user@mail.example.com")


class TestEmailNormalizerIntegration:
    """Integration tests for email normalization in duplicate detection context."""
    
    def test_duplicate_detection_scenario(self):
        """Test email normalization in a duplicate detection scenario."""
        # Simulate emails that should be considered duplicates
        duplicate_emails = [
            "john.doe@example.com",
            "JOHN.DOE@EXAMPLE.COM",
            "  john.doe@example.com  ",
            "John.Doe@Example.Com",
        ]
        
        # All should normalize to the same value
        normalized_emails = [EmailNormalizer.normalize_email(email) for email in duplicate_emails]
        assert all(email == "john.doe@example.com" for email in normalized_emails)
    
    def test_empty_email_handling_in_batch(self):
        """Test handling of empty emails in a batch processing context."""
        batch_emails = [
            "john@example.com",
            "",
            "jane@example.com",
            "N/A",
            "bob@example.com",
            None,
            "not available",
        ]
        
        normalized = [EmailNormalizer.normalize_email(email) for email in batch_emails]
        expected = [
            "john@example.com",
            "N/A",
            "jane@example.com", 
            "N/A",
            "bob@example.com",
            "N/A",
            "N/A",
        ]
        
        assert normalized == expected
    
    def test_validation_with_normalization(self):
        """Test that validation works correctly with normalized emails."""
        test_cases = [
            ("  john@example.com  ", True),  # Valid after normalization
            ("  JOHN@EXAMPLE.COM  ", True),  # Valid after normalization
            ("  invalid-email  ", False),    # Invalid even after normalization
            ("  @example.com  ", False),     # Invalid even after normalization
            ("  N/A  ", False),              # Empty after normalization
        ]
        
        for email, expected_valid in test_cases:
            # First normalize, then validate
            normalized = EmailNormalizer.normalize_email(email)
            if normalized == "N/A":
                # Empty emails are not valid
                assert not EmailNormalizer.is_valid_email_format(email)
            else:
                # Non-empty emails should match expected validation result
                assert EmailNormalizer.is_valid_email_format(email) == expected_valid
    
    def test_malformed_emails_for_duplicate_detection(self):
        """Test that malformed emails are still normalized for duplicate detection (Requirement 1.5)."""
        # These emails are invalid but should still be normalized consistently
        malformed_emails = [
            "invalid-email",
            "INVALID-EMAIL",
            "  invalid-email  ",
            "@example.com",
            "  @EXAMPLE.COM  ",
            "user@",
            "  USER@  ",
        ]
        
        # Each malformed email should normalize consistently
        assert EmailNormalizer.normalize_email("invalid-email") == "invalid-email"
        assert EmailNormalizer.normalize_email("INVALID-EMAIL") == "invalid-email"
        assert EmailNormalizer.normalize_email("  invalid-email  ") == "invalid-email"
        
        assert EmailNormalizer.normalize_email("@example.com") == "@example.com"
        assert EmailNormalizer.normalize_email("  @EXAMPLE.COM  ") == "@example.com"
        
        assert EmailNormalizer.normalize_email("user@") == "user@"
        assert EmailNormalizer.normalize_email("  USER@  ") == "user@"
    
    def test_unicode_and_international_emails(self):
        """Test handling of unicode and international email addresses."""
        # Test unicode characters (these should be handled gracefully)
        unicode_emails = [
            "user@exämple.com",  # Umlaut in domain
            "üser@example.com",  # Umlaut in local part
            "user@例え.テスト",    # Japanese characters
        ]
        
        for email in unicode_emails:
            # Should normalize without throwing errors
            normalized = EmailNormalizer.normalize_email(email)
            assert isinstance(normalized, str)
            assert normalized == email.lower()
    
    def test_very_long_emails(self):
        """Test handling of very long email addresses."""
        # Create a very long but valid email
        long_local = "a" * 60
        long_domain = "b" * 60 + ".com"
        long_email = f"{long_local}@{long_domain}"
        
        # Should normalize without issues
        normalized = EmailNormalizer.normalize_email(long_email)
        assert normalized == long_email.lower()
        
        # Should validate (basic format is correct)
        assert EmailNormalizer.is_valid_email_format(long_email)
    
    def test_emails_with_consecutive_dots(self):
        """Test handling of emails with consecutive dots (invalid pattern)."""
        invalid_dot_emails = [
            "user..name@example.com",  # Consecutive dots in local part
            "user@example..com",       # Consecutive dots in domain
            "user@.example.com",       # Leading dot in domain
            "user@example.com.",       # Trailing dot in domain
            ".user@example.com",       # Leading dot in local part
            "user.@example.com",       # Trailing dot in local part
        ]
        
        for email in invalid_dot_emails:
            # Should normalize consistently
            normalized = EmailNormalizer.normalize_email(email)
            assert normalized == email.lower()
            
            # Should be invalid
            assert not EmailNormalizer.is_valid_email_format(email)
    
    def test_emails_with_spaces(self):
        """Test handling of emails with spaces (invalid pattern)."""
        space_emails = [
            "user name@example.com",   # Space in local part
            "user@exam ple.com",       # Space in domain
            "user @example.com",       # Space before @
            "user@ example.com",       # Space after @
        ]
        
        for email in space_emails:
            # Should normalize (spaces preserved in middle)
            normalized = EmailNormalizer.normalize_email(email)
            assert normalized == email.lower()
            
            # Should be invalid
            assert not EmailNormalizer.is_valid_email_format(email)
    
    def test_non_string_input_handling(self):
        """Test handling of non-string inputs."""
        # Test integer input
        try:
            result = EmailNormalizer.normalize_email(123)
            # If it doesn't raise an error, it should handle gracefully
            assert isinstance(result, str)
        except (TypeError, AttributeError):
            # It's acceptable to raise an error for non-string input
            pass
        
        # Test boolean input
        try:
            result = EmailNormalizer.normalize_email(True)
            assert isinstance(result, str)
        except (TypeError, AttributeError):
            pass
        
        # Test list input
        try:
            result = EmailNormalizer.normalize_email(["email@example.com"])
            assert isinstance(result, str)
        except (TypeError, AttributeError):
            pass
        
        # Validation should handle non-string gracefully
        assert not EmailNormalizer.is_valid_email_format(123)
        assert not EmailNormalizer.is_valid_email_format(True)
        assert not EmailNormalizer.is_valid_email_format(["email@example.com"])