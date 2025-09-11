"""
Lead data validation and transformation utilities.
Handles data standardization and validation for lead management system.
"""

import re
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class LeadValidator:
    """Utility class for lead data validation and transformation."""
    
    # Standard field mappings for lead data
    STANDARD_FIELDS = {
        'firstName': ['first_name', 'firstname', 'first', 'fname', 'given_name'],
        'lastName': ['last_name', 'lastname', 'last', 'lname', 'surname', 'family_name'],
        'title': ['job_title', 'position', 'role', 'designation'],
        'company': ['company_name', 'organization', 'employer', 'business'],
        'email': ['email_address', 'e_mail', 'mail'],
        'phone': ['phone_number', 'telephone', 'mobile', 'cell', 'contact_number', 'tel'],
        'remarks': ['notes', 'comments', 'description', 'additional_info']
    }
    
    # Email validation regex
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    # Phone validation regex (flexible pattern for international formats)
    PHONE_PATTERN = re.compile(r'^[\+]?[1-9][\d\s\-\(\)\.]{7,15}$')
    
    @classmethod
    def validate_email(cls, email: str) -> bool:
        """
        Validate email format.
        
        Args:
            email: Email address to validate
            
        Returns:
            bool: True if valid email format
        """
        if not email or email == 'N/A':
            return True  # N/A is acceptable
        return bool(cls.EMAIL_PATTERN.match(email.strip()))
    
    @classmethod
    def validate_phone(cls, phone: str) -> bool:
        """
        Validate phone number format.
        
        Args:
            phone: Phone number to validate
            
        Returns:
            bool: True if valid phone format or N/A
        """
        if not phone or phone == 'N/A':
            return True  # N/A is acceptable
        
        phone = phone.strip()
        
        # Remove common separators and spaces for validation
        cleaned_phone = re.sub(r'[\s\-\(\)\.]+', '', phone)
        
        # Check basic requirements:
        # 1. Must contain only digits, spaces, hyphens, parentheses, dots, and optional leading +
        # 2. Must have at least 7 digits
        # 3. Must not be longer than 20 characters total
        # 4. Must not contain letters
        
        if len(phone) > 20:
            return False
        
        if re.search(r'[a-zA-Z]', phone):
            return False
        
        # Count digits only
        digits_only = re.sub(r'[^\d]', '', phone)
        
        if len(digits_only) < 7 or len(digits_only) > 15:
            return False
        
        # Check for valid characters only
        valid_chars_pattern = re.compile(r'^[\+]?[\d\s\-\(\)\.]+$')
        
        return bool(valid_chars_pattern.match(phone))
    
    @classmethod
    def normalize_phone(cls, phone: str) -> str:
        """
        Normalize phone number format for consistent storage.
        
        Args:
            phone: Phone number to normalize
            
        Returns:
            str: Normalized phone number or 'N/A'
        """
        if not phone or phone == 'N/A':
            return 'N/A'
        
        phone = phone.strip()
        
        # If validation fails, return N/A
        if not cls.validate_phone(phone):
            return 'N/A'
        
        # Basic normalization - remove extra spaces
        normalized = re.sub(r'\s+', ' ', phone)
        
        return normalized
    
    @classmethod
    def extract_phone_digits(cls, phone: str) -> str:
        """
        Extract only digits from phone number for comparison purposes.
        
        Args:
            phone: Phone number to process
            
        Returns:
            str: Digits only or empty string
        """
        if not phone or phone == 'N/A':
            return ''
        
        return re.sub(r'[^\d]', '', phone)
    
    @classmethod
    def format_phone_for_display(cls, phone: str) -> str:
        """
        Format phone number for consistent display.
        
        Args:
            phone: Phone number to format
            
        Returns:
            str: Formatted phone number
        """
        if not phone or phone == 'N/A':
            return 'N/A'
        
        # If it's already formatted nicely, return as-is
        if cls.validate_phone(phone):
            return phone.strip()
        
        return 'N/A'
    
    @classmethod
    def sanitize_text(cls, text: str, max_length: int = 255) -> str:
        """
        Sanitize text input by removing harmful characters and limiting length.
        
        Args:
            text: Text to sanitize
            max_length: Maximum allowed length
            
        Returns:
            str: Sanitized text
        """
        if not text:
            return 'N/A'
        
        # Remove control characters and excessive whitespace
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', str(text))
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].strip()
        
        return sanitized if sanitized else 'N/A'
    
    @classmethod
    def normalize_field_name(cls, field_name: str) -> Optional[str]:
        """
        Normalize field name to standard format.
        
        Args:
            field_name: Original field name from CSV/Excel
            
        Returns:
            Optional[str]: Standardized field name or None if not recognized
        """
        if not field_name:
            return None
        
        normalized = field_name.lower().strip().replace(' ', '_').replace('-', '_')
        
        # Check direct match first
        if normalized in cls.STANDARD_FIELDS:
            return normalized
        
        # Check against known variations
        for standard_field, variations in cls.STANDARD_FIELDS.items():
            if normalized in variations or normalized == standard_field:
                return standard_field
        
        return None
    
    @classmethod
    def validate_lead_data(cls, lead_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate lead data structure and content.
        
        Args:
            lead_data: Dictionary containing lead information
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required structure
        if not isinstance(lead_data, dict):
            errors.append("Lead data must be a dictionary")
            return False, errors
        
        # Validate email if provided
        email = lead_data.get('email', '')
        if email and email != 'N/A' and not cls.validate_email(email):
            errors.append(f"Invalid email format: {email}")
        
        # Validate phone if provided
        phone = lead_data.get('phone', '')
        if phone and phone != 'N/A' and not cls.validate_phone(phone):
            errors.append(f"Invalid phone format: {phone}")
        
        # Enhanced meaningful data check - require at least 2 meaningful fields for better data quality
        meaningful_fields = ['firstName', 'lastName', 'email', 'phone', 'company']
        meaningful_values = []
        
        for field in meaningful_fields:
            value = lead_data.get(field, '')
            # Check if value is meaningful (not empty, not N/A, not just whitespace, and has substance)
            if value and str(value).strip() and value != 'N/A' and len(str(value).strip()) > 1:
                meaningful_values.append(field)
        
        # Require at least 2 meaningful fields for better data quality
        if len(meaningful_values) < 2:
            errors.append(f"Lead must have at least 2 meaningful fields from: {meaningful_fields}. Found meaningful data in: {meaningful_values}")
        
        # Additional check for data quality - ensure we don't have too many N/A values
        all_values = [str(lead_data.get(field, '')) for field in meaningful_fields]
        na_count = sum(1 for v in all_values if v in ['N/A', 'n/a', 'NA', 'na', ''])
        
        if na_count >= 4:  # If 4 or more fields are N/A out of 5, reject
            errors.append(f"Lead has too many N/A values ({na_count}/5 fields). This indicates poor data quality.")
        
        # Validate field lengths
        field_limits = {
            'firstName': 100,
            'lastName': 100,
            'title': 150,
            'company': 200,
            'email': 255,
            'phone': 50,
            'remarks': 1000
        }
        
        for field, limit in field_limits.items():
            value = lead_data.get(field, '')
            if value and len(str(value)) > limit:
                errors.append(f"{field} exceeds maximum length of {limit} characters")
        
        return len(errors) == 0, errors
    
    @classmethod
    def transform_raw_data(cls, raw_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Transform raw CSV/Excel data to standardized lead format.
        
        Args:
            raw_data: Raw data dictionary from CSV/Excel
            
        Returns:
            Dict[str, str]: Standardized lead data
        """
        transformed = {
            'firstName': 'N/A',
            'lastName': 'N/A',
            'title': 'N/A',
            'company': 'N/A',
            'email': 'N/A',
            'phone': 'N/A',
            'remarks': 'N/A'
        }
        
        remarks_parts = []
        
        for original_field, value in raw_data.items():
            if not value:
                continue
            
            # Normalize the field name
            standard_field = cls.normalize_field_name(original_field)
            
            if standard_field:
                # Map to standard field
                transformed[standard_field] = cls.sanitize_text(str(value))
            else:
                # Add to remarks if not a standard field
                remarks_parts.append(f"{original_field}: {cls.sanitize_text(str(value))}")
        
        # Combine existing remarks with unmapped fields
        existing_remarks = transformed.get('remarks', '')
        if remarks_parts:
            if existing_remarks and existing_remarks != 'N/A':
                transformed['remarks'] = f"{existing_remarks}; {'; '.join(remarks_parts)}"
            else:
                transformed['remarks'] = '; '.join(remarks_parts)
        
        return transformed
    
    @classmethod
    def validate_file_type(cls, filename: str, content_type: str = None) -> bool:
        """
        Validate if file is CSV or Excel format.
        
        Args:
            filename: Name of the uploaded file
            content_type: MIME type of the file
            
        Returns:
            bool: True if file type is supported
        """
        if not filename:
            return False
        
        filename_lower = filename.lower()
        
        # Check file extension
        valid_extensions = ['.csv', '.xlsx', '.xls']
        has_valid_extension = any(filename_lower.endswith(ext) for ext in valid_extensions)
        
        # Check content type if provided
        valid_content_types = [
            'text/csv',
            'application/csv',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ]
        
        has_valid_content_type = True  # Default to true if not provided
        if content_type:
            has_valid_content_type = content_type in valid_content_types
        
        return has_valid_extension and has_valid_content_type
    
    @classmethod
    def validate_file_size(cls, file_size: int, max_size_mb: int = 10) -> bool:
        """
        Validate file size is within limits.
        
        Args:
            file_size: Size of file in bytes
            max_size_mb: Maximum allowed size in MB
            
        Returns:
            bool: True if file size is acceptable
        """
        max_size_bytes = max_size_mb * 1024 * 1024
        return file_size <= max_size_bytes
    
    @classmethod
    def prepare_deepseek_data(cls, raw_leads: List[Dict[str, Any]]) -> str:
        """
        Prepare lead data for DeepSeek API processing.
        
        Args:
            raw_leads: List of raw lead dictionaries
            
        Returns:
            str: Formatted data string for DeepSeek
        """
        if not raw_leads:
            return ""
        
        # Create a sample of the data structure for DeepSeek
        sample_size = min(5, len(raw_leads))
        sample_data = raw_leads[:sample_size]
        
        # Format as a structured string
        formatted_data = "Lead data to standardize:\n\n"
        
        for i, lead in enumerate(sample_data, 1):
            formatted_data += f"Lead {i}:\n"
            for key, value in lead.items():
                if value:  # Only include non-empty values
                    formatted_data += f"  {key}: {value}\n"
            formatted_data += "\n"
        
        if len(raw_leads) > sample_size:
            formatted_data += f"... and {len(raw_leads) - sample_size} more leads with similar structure\n"
        
        return formatted_data