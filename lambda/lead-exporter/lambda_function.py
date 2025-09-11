"""
Lead Exporter Lambda Function

Handles CSV export of filtered lead data. Uses the same filtering logic as
the lead reader to ensure consistency, but retrieves all matching records
without pagination for complete export functionality.

Requirements covered:
- 5.1: Provide export button when filters are applied
- 5.2: Generate CSV file containing only filtered leads
- 5.3: Include all standard fields including remarks
- 5.4: Automatically download CSV file to user's device
- 5.5: Display message if no leads match current filters
"""

import json
import os
import sys
import csv
import io
import base64
from typing import Dict, Any, List
from datetime import datetime

# Add shared utilities to path
sys.path.append('/opt/python')
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from dynamodb_utils import DynamoDBUtils
from error_handling import (
    lambda_handler_wrapper, 
    create_success_response, 
    ValidationError,
    DatabaseError,
    validate_jwt_token,
    log_performance_metrics
)
from validation import LeadValidator

# Initialize DynamoDB utils with correct table name
table_name = os.environ.get('LEADS_TABLE', 'easy-crm-leads-prod')
dynamodb_utils = DynamoDBUtils(table_name=table_name)

# CSV field headers in the desired order
CSV_HEADERS = [
    'leadId',
    'firstName', 
    'lastName', 
    'title', 
    'company', 
    'email', 
    'phone',
    'remarks',
    'sourceFile',
    'createdAt',
    'updatedAt'
]

@lambda_handler_wrapper
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for lead export functionality.
    
    Args:
        event: API Gateway event containing filters in request body
        context: Lambda context object
        
    Returns:
        Dict: API Gateway response with base64-encoded CSV data
    """
    # Handle CORS preflight requests
    if event.get('httpMethod') == 'OPTIONS':
        return create_success_response({}, 200)
    
    # Validate authentication
    user_claims = validate_jwt_token(event)
    
    # Parse filters from request body (sent by frontend)
    try:
        body = event.get('body', '{}')
        if isinstance(body, str):
            request_data = json.loads(body)
        else:
            request_data = body or {}
    except (json.JSONDecodeError, TypeError) as e:
        raise ValidationError(f"Invalid request body: {str(e)}", "request_body")
    
    # Extract filter parameters from request body
    filters = request_data.get('filters', {})
    
    # Validate and clean filter values
    cleaned_filters = {}
    filter_fields = ['firstName', 'lastName', 'title', 'company', 'email', 'phone']
    
    for field in filter_fields:
        if field in filters:
            filter_value = filters[field]
            if filter_value and str(filter_value).strip():
                cleaned_filters[field] = str(filter_value).strip()
    
    filters = cleaned_filters
    
    try:
        # Get all leads matching the filters (no pagination for export)
        leads = get_filtered_leads_for_export(filters)
        
        # Check if any leads match the filters
        if not leads:
            return create_success_response({
                'message': 'No leads match the current filters',
                'leadCount': 0,
                'csvData': None
            })
        
        # Generate CSV data
        csv_data = generate_csv_data(leads)
        
        # Encode CSV as base64 for download
        csv_base64 = base64.b64encode(csv_data.encode('utf-8')).decode('utf-8')
        
        # Generate filename with timestamp
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"leads_export_{timestamp}.csv"
        
        return create_success_response({
            'message': f'Successfully exported {len(leads)} leads',
            'leadCount': len(leads),
            'csvData': csv_base64,
            'filename': filename,
            'filters': filters
        })
        
    except Exception as e:
        raise DatabaseError(f"Failed to export leads: {str(e)}", "export_leads")

@log_performance_metrics
def get_filtered_leads_for_export(filters: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Retrieve all leads matching the provided filters for export.
    Uses the same filtering logic as the lead reader function.
    
    Args:
        filters: Dictionary of field filters
        
    Returns:
        List[Dict]: All leads matching the filters
    """
    try:
        # Use the DynamoDB utils method for getting all leads with filters
        leads = dynamodb_utils.get_all_leads_for_export(filters)
        
        # Format leads for consistency (same as lead reader)
        formatted_leads = []
        for lead in leads:
            formatted_lead = {
                'leadId': lead.get('leadId', ''),
                'firstName': lead.get('firstName', 'N/A'),
                'lastName': lead.get('lastName', 'N/A'),
                'title': lead.get('title', 'N/A'),
                'company': lead.get('company', 'N/A'),
                'email': lead.get('email', 'N/A'),
                'phone': lead.get('phone', 'N/A'),
                'remarks': lead.get('remarks', 'N/A'),
                'sourceFile': lead.get('sourceFile', ''),
                'createdAt': lead.get('createdAt', ''),
                'updatedAt': lead.get('updatedAt', '')
            }
            formatted_leads.append(formatted_lead)
        
        return formatted_leads
        
    except Exception as e:
        raise DatabaseError(f"Failed to retrieve leads for export: {str(e)}", "get_filtered_leads")

def generate_csv_data(leads: List[Dict[str, Any]]) -> str:
    """
    Generate CSV data from leads list.
    
    Args:
        leads: List of lead dictionaries
        
    Returns:
        str: CSV data as string
        
    Raises:
        ValidationError: If leads data is invalid
    """
    if not isinstance(leads, list):
        raise ValidationError("Leads data must be a list", "leads")
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_HEADERS, quoting=csv.QUOTE_ALL)
    
    # Write header row
    writer.writeheader()
    
    # Write data rows
    for lead in leads:
        try:
            # Ensure all required fields are present
            row_data = {}
            for header in CSV_HEADERS:
                value = lead.get(header, 'N/A')
                # Handle None values and ensure string conversion
                if value is None:
                    value = 'N/A'
                elif not isinstance(value, str):
                    value = str(value)
                row_data[header] = value
            
            writer.writerow(row_data)
            
        except Exception as e:
            # Log the error but continue with other leads
            print(f"Error processing lead {lead.get('leadId', 'unknown')}: {str(e)}")
            continue
    
    csv_content = output.getvalue()
    output.close()
    
    return csv_content

def validate_export_request(filters: Dict[str, Any]) -> Dict[str, str]:
    """
    Validate export request filters.
    
    Args:
        filters: Filter dictionary from request body
        
    Returns:
        Dict[str, str]: Validated filters
        
    Raises:
        ValidationError: If validation fails
    """
    validated_filters = {}
    valid_filter_fields = ['firstName', 'lastName', 'title', 'company', 'email', 'phone']
    
    for field in valid_filter_fields:
        if field in filters:
            filter_value = filters[field]
            if filter_value and str(filter_value).strip():
                # Basic validation for filter values
                cleaned_value = str(filter_value).strip()
                if len(cleaned_value) > 100:  # Reasonable limit
                    raise ValidationError(f"Filter value for {field} is too long (max 100 characters)", field)
                validated_filters[field] = cleaned_value
    
    return validated_filters

# Additional handler for getting export preview (count only)
@lambda_handler_wrapper
def get_export_preview_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler for getting export preview (count of leads that would be exported).
    
    Args:
        event: API Gateway event containing filters in request body
        context: Lambda context object
        
    Returns:
        Dict: API Gateway response with lead count
    """
    # Handle CORS preflight requests
    if event.get('httpMethod') == 'OPTIONS':
        return create_success_response({}, 200)
    
    # Validate authentication
    user_claims = validate_jwt_token(event)
    
    # Parse filters from request body (same as main handler)
    try:
        body = event.get('body', '{}')
        if isinstance(body, str):
            request_data = json.loads(body)
        else:
            request_data = body or {}
    except (json.JSONDecodeError, TypeError) as e:
        raise ValidationError(f"Invalid request body: {str(e)}", "request_body")
    
    # Extract and validate filters
    raw_filters = request_data.get('filters', {})
    filters = validate_export_request(raw_filters)
    
    try:
        # Get count of leads that would be exported
        leads = get_filtered_leads_for_export(filters)
        lead_count = len(leads)
        
        return create_success_response({
            'leadCount': lead_count,
            'filters': filters,
            'message': f'{lead_count} leads match the current filters'
        })
        
    except Exception as e:
        raise DatabaseError(f"Failed to get export preview: {str(e)}", "export_preview")