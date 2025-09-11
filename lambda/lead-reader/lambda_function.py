"""
Lead Reader Lambda Function

Handles lead retrieval with filtering, sorting, and pagination capabilities.
Provides API endpoint for querying leads from DynamoDB with comprehensive
filtering options and proper pagination metadata.

Requirements covered:
- 3.1: Display all leads in paginated table format
- 3.2: Show columns for firstName, lastName, title, company, email, remarks
- 3.3: Provide filter controls for each column
- 3.4: Update table to show only matching leads when filters applied
- 3.5: Allow sorting by any column in ascending or descending order
- 3.6: Implement pagination with configurable page sizes
"""

import json
import os
import sys
from typing import Dict, Any, Optional

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

@lambda_handler_wrapper
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for lead reader functionality.
    
    Args:
        event: API Gateway event containing query parameters
        context: Lambda context object
        
    Returns:
        Dict: API Gateway response with leads data and pagination info
    """
    # Handle CORS preflight requests
    if event.get('httpMethod') == 'OPTIONS':
        return create_success_response({}, 200)
    
    # Validate authentication
    user_claims = validate_jwt_token(event)
    
    # Parse query parameters
    query_params = event.get('queryStringParameters') or {}
    
    # Extract pagination parameters
    page = int(query_params.get('page', 1))
    page_size = int(query_params.get('pageSize', 50))
    
    # Validate pagination parameters
    if page < 1:
        raise ValidationError("Page number must be greater than 0", "page")
    
    if page_size < 1 or page_size > 100:
        raise ValidationError("Page size must be between 1 and 100", "pageSize")
    
    # Extract sorting parameters
    sort_by = query_params.get('sortBy', 'createdAt')
    sort_order = query_params.get('sortOrder', 'desc')
    
    # Validate sorting parameters
    valid_sort_fields = ['firstName', 'lastName', 'title', 'company', 'email', 'phone', 'createdAt', 'updatedAt']
    if sort_by not in valid_sort_fields:
        raise ValidationError(f"Invalid sort field. Must be one of: {', '.join(valid_sort_fields)}", "sortBy")
    
    if sort_order not in ['asc', 'desc']:
        raise ValidationError("Sort order must be 'asc' or 'desc'", "sortOrder")
    
    # Extract filter parameters
    filters = {}
    filter_fields = ['firstName', 'lastName', 'title', 'company', 'email', 'phone']
    
    for field in filter_fields:
        filter_value = query_params.get(f'filter_{field}')
        if filter_value and filter_value.strip():
            filters[field] = filter_value.strip()
    
    # Handle pagination token
    last_evaluated_key = None
    if 'lastEvaluatedKey' in query_params and query_params['lastEvaluatedKey']:
        try:
            last_evaluated_key = json.loads(query_params['lastEvaluatedKey'])
        except json.JSONDecodeError:
            raise ValidationError("Invalid lastEvaluatedKey format", "lastEvaluatedKey")
    
    # Query leads from DynamoDB
    try:
        result = query_leads_with_pagination(
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
            last_evaluated_key=last_evaluated_key
        )
        
        return create_success_response(result)
        
    except Exception as e:
        raise DatabaseError(f"Failed to retrieve leads: {str(e)}", "query_leads")

@log_performance_metrics
def query_leads_with_pagination(
    filters: Dict[str, str],
    sort_by: str,
    sort_order: str,
    page: int,
    page_size: int,
    last_evaluated_key: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Query leads with filtering, sorting, and pagination.
    
    Args:
        filters: Dictionary of field filters
        sort_by: Field to sort by
        sort_order: 'asc' or 'desc'
        page: Page number (1-based)
        page_size: Number of items per page
        last_evaluated_key: Pagination token from previous query
        
    Returns:
        Dict containing leads data and pagination metadata
    """
    # For page-based pagination, we need to get all matching results and slice them
    # This is necessary because DynamoDB doesn't support offset-based pagination
    
    # Get all leads matching the filters and sort criteria
    all_leads = dynamodb_utils.get_all_leads_with_filters_and_sort(
        filters=filters,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    total_count = len(all_leads)
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
    
    # Calculate start and end indices for the requested page
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    
    # Slice the results for the current page
    page_leads = all_leads[start_index:end_index]
    
    # Format response with proper pagination metadata
    response = {
        'leads': format_leads_for_response(page_leads),
        'pagination': {
            'page': page,
            'pageSize': page_size,
            'totalCount': total_count,
            'totalPages': total_pages,
            'hasMore': page < total_pages,
            'lastEvaluatedKey': None  # Not used in page-based pagination
        },
        'filters': filters,
        'sorting': {
            'sortBy': sort_by,
            'sortOrder': sort_order
        }
    }
    
    return response

def format_leads_for_response(leads: list) -> list:
    """
    Format leads data for API response.
    
    Args:
        leads: List of lead dictionaries from DynamoDB
        
    Returns:
        List of formatted lead dictionaries
    """
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

def get_lead_by_id(lead_id: str) -> Dict[str, Any]:
    """
    Retrieve a single lead by ID.
    
    Args:
        lead_id: The lead ID to retrieve
        
    Returns:
        Dict containing lead data
        
    Raises:
        ValidationError: If lead_id is invalid
        DatabaseError: If lead not found or database error
    """
    if not lead_id or not lead_id.strip():
        raise ValidationError("Lead ID is required", "leadId")
    
    try:
        lead = dynamodb_utils.get_lead(lead_id.strip())
        
        if not lead:
            raise ValidationError(f"Lead not found: {lead_id}", "leadId")
        
        return format_leads_for_response([lead])[0]
        
    except Exception as e:
        raise DatabaseError(f"Failed to retrieve lead {lead_id}: {str(e)}", "get_lead")

# Additional handler for single lead retrieval (if needed)
@lambda_handler_wrapper
def get_single_lead_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler for retrieving a single lead by ID.
    
    Args:
        event: API Gateway event containing path parameters
        context: Lambda context object
        
    Returns:
        Dict: API Gateway response with single lead data
    """
    # Handle CORS preflight requests
    if event.get('httpMethod') == 'OPTIONS':
        return create_success_response({}, 200)
    
    # Validate authentication
    user_claims = validate_jwt_token(event)
    
    # Extract lead ID from path parameters
    path_params = event.get('pathParameters') or {}
    lead_id = path_params.get('leadId')
    
    if not lead_id:
        raise ValidationError("Lead ID is required in path", "leadId")
    
    # Retrieve and return the lead
    lead = get_lead_by_id(lead_id)
    
    return create_success_response({
        'lead': lead
    })