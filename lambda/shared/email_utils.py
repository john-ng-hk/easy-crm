"""
Email normalization and validation utilities for duplicate lead detection.

This module provides utilities for normalizing email addresses to ensure
consistent duplicate detection across the lead management system.
"""

import re
from typing import Optional


class EmailNormalizer:
    """Utility class for email address normalization and validation."""
    
    # Basic email validation regex pattern
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    # Values that should be treated as "no email"
    EMPTY_EMAIL_VALUES = {'', 'n/a', 'null', 'none', 'na', 'not available', 'not provided'}
    
    @staticmethod
    def normalize_email(email: Optional[str]) -> str:
        """
        Normalize email address for consistent duplicate detection.
        
        Performs the following normalization steps:
        1. Handle None/null values
        2. Strip whitespace
        3. Convert to lowercase
        4. Treat empty or "N/A" values as 'N/A'
        
        Args:
            email: Raw email address (can be None)
            
        Returns:
            str: Normalized email address or 'N/A' for empty values
            
        Examples:
            >>> EmailNormalizer.normalize_email("  John.Doe@EXAMPLE.COM  ")
            'john.doe@example.com'
            >>> EmailNormalizer.normalize_email("")
            'N/A'
            >>> EmailNormalizer.normalize_email("N/A")
            'N/A'
            >>> EmailNormalizer.normalize_email(None)
            'N/A'
        """
        if email is None:
            return 'N/A'
        
        # Strip whitespace and convert to lowercase
        normalized = email.strip().lower()
        
        # Check if the normalized email is in the empty values set
        if normalized in EmailNormalizer.EMPTY_EMAIL_VALUES:
            return 'N/A'
        
        return normalized
    
    @staticmethod
    def is_valid_email_format(email: str) -> bool:
        """
        Basic email format validation using regex.
        
        Validates that the email follows a basic email format pattern.
        This is not a comprehensive validation but checks for basic structure.
        
        Args:
            email: Email address to validate
            
        Returns:
            bool: True if email format appears valid, False otherwise
            
        Examples:
            >>> EmailNormalizer.is_valid_email_format("john@example.com")
            True
            >>> EmailNormalizer.is_valid_email_format("invalid-email")
            False
            >>> EmailNormalizer.is_valid_email_format("@example.com")
            False
            >>> EmailNormalizer.is_valid_email_format("john@")
            False
        """
        if not email or not isinstance(email, str):
            return False
        
        # Normalize the email first (strip whitespace, lowercase)
        normalized_email = email.strip().lower()
        
        # Check if it's an empty value
        if normalized_email in EmailNormalizer.EMPTY_EMAIL_VALUES:
            return False
        
        # Basic regex validation
        if not EmailNormalizer.EMAIL_PATTERN.match(normalized_email):
            return False
        
        # Additional validation checks
        local_part, domain_part = normalized_email.split('@', 1)
        
        # Check for invalid patterns in local part
        if (local_part.startswith('.') or 
            local_part.endswith('.') or 
            '..' in local_part or
            ' ' in local_part):
            return False
        
        # Check for invalid patterns in domain part
        if (domain_part.startswith('.') or 
            domain_part.endswith('.') or 
            '..' in domain_part or
            ' ' in domain_part or
            domain_part.startswith('-') or
            domain_part.endswith('-')):
            return False
        
        return True
    
    @staticmethod
    def is_empty_email(email: Optional[str]) -> bool:
        """
        Check if an email should be treated as empty/missing.
        
        Args:
            email: Email address to check
            
        Returns:
            bool: True if email should be treated as empty
            
        Examples:
            >>> EmailNormalizer.is_empty_email("")
            True
            >>> EmailNormalizer.is_empty_email("N/A")
            True
            >>> EmailNormalizer.is_empty_email("john@example.com")
            False
        """
        normalized = EmailNormalizer.normalize_email(email)
        return normalized == 'N/A'