"""
Chatbot Lambda Function

Handles natural language queries about lead data using DeepSeek AI integration.
Processes user queries, generates appropriate DynamoDB queries, and formats
results in user-friendly responses while maintaining data security.

Requirements covered:
- 4.1: Display chat interface alongside leads table
- 4.2: Send natural language queries to chatbot Lambda function
- 4.3: Send query to DeepSeek AI to generate DynamoDB queries
- 4.4: Execute generated query against DynamoDB and return results
- 4.5: Format results in user-friendly response and display in chat
- 4.6: Ask user to rephrase if query cannot be understood
- 4.7: Never send raw lead data to DeepSeek, only query structures
"""

import json
import os
import sys
import requests
from typing import Dict, Any, List, Optional, Tuple

# Add shared utilities to path
sys.path.append('/opt/python')
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from dynamodb_utils import DynamoDBUtils
from error_handling import (
    lambda_handler_wrapper, 
    create_success_response, 
    ValidationError,
    DatabaseError,
    ExternalAPIError,
    validate_jwt_token,
    log_performance_metrics,
    retry_with_backoff
)
from validation import LeadValidator

# Initialize DynamoDB utils with correct table name
table_name = os.environ.get('LEADS_TABLE', 'easy-crm-leads-prod')
dynamodb_utils = DynamoDBUtils(table_name=table_name)

# DeepSeek API configuration
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')

@lambda_handler_wrapper
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for chatbot functionality.
    
    Args:
        event: API Gateway event containing user query
        context: Lambda context object
        
    Returns:
        Dict: API Gateway response with chatbot response
    """
    # Handle CORS preflight requests
    if event.get('httpMethod') == 'OPTIONS':
        return create_success_response({}, 200)
    
    # Validate authentication
    user_claims = validate_jwt_token(event)
    user_id = user_claims.get('sub', 'unknown')
    
    # Parse request body
    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        raise ValidationError("Invalid JSON in request body")
    
    # Extract and validate query
    user_query = body.get('query', '').strip()
    if not user_query:
        raise ValidationError("Query is required", "query")
    
    if len(user_query) > 500:
        raise ValidationError("Query too long (max 500 characters)", "query")
    
    # Process the query and generate response
    try:
        response = process_natural_language_query(user_query, user_id)
        
        # Ensure response has required fields
        if not response or not isinstance(response, dict):
            response = {
                'response': "I'm sorry, I couldn't process your query. Please try rephrasing your question.",
                'type': 'error',
                'query': user_query
            }
        
        # Ensure response field exists
        if 'response' not in response or not response['response']:
            response['response'] = "I'm sorry, I couldn't understand your query. Could you please rephrase it? For example, you could ask 'Show me leads from tech companies' or 'How many leads do we have from Google?'"
            response['type'] = 'clarification'
        
        return create_success_response(response)
        
    except Exception as e:
        print(f"Chatbot error: {str(e)}")
        # Return user-friendly error message for chat interface
        error_response = {
            'response': "I'm sorry, I encountered an error processing your query. Please try rephrasing your question or contact support if the issue persists.",
            'type': 'error',
            'query': user_query
        }
        return create_success_response(error_response)

@log_performance_metrics
def process_natural_language_query(user_query: str, user_id: str) -> Dict[str, Any]:
    """
    Process natural language query and return formatted response.
    
    Args:
        user_query: User's natural language query
        user_id: User identifier for logging
        
    Returns:
        Dict containing chatbot response and metadata
    """
    # Step 1: Generate DynamoDB query using DeepSeek
    try:
        query_structure = generate_dynamodb_query(user_query)
    except Exception as e:
        print(f"DeepSeek query generation failed: {str(e)}")
        return {
            'response': "I'm sorry, I couldn't understand your query. Could you please rephrase it? For example, you could ask 'Show me leads from tech companies' or 'How many leads do we have from Google?'",
            'type': 'clarification',
            'query': user_query
        }
    
    if not query_structure:
        print(f"No query structure generated for: {user_query}")
        return {
            'response': "I'm sorry, I couldn't understand your query. Could you please rephrase it? For example, you could ask 'Show me leads from tech companies' or 'How many leads do we have from Google?'",
            'type': 'clarification',
            'query': user_query
        }
    
    # Step 2: Execute query against DynamoDB
    try:
        results = execute_query(query_structure)
    except Exception as e:
        return {
            'response': "I encountered an issue retrieving the data. Please try your query again.",
            'type': 'error',
            'query': user_query
        }
    
    # Step 3: Format results for user-friendly response
    formatted_response = format_query_results(user_query, query_structure, results)
    
    return {
        'response': formatted_response,
        'type': 'success',
        'query': user_query,
        'resultCount': len(results) if isinstance(results, list) else (results.get('count', 0) if isinstance(results, dict) else 0)
    }

def generate_dynamodb_query(user_query: str) -> Optional[Dict[str, Any]]:
    """
    Use DeepSeek AI to generate DynamoDB query structure from natural language.
    
    Args:
        user_query: User's natural language query
        
    Returns:
        Optional[Dict]: Query structure or None if cannot be parsed
    """
    if not DEEPSEEK_API_KEY:
        raise ExternalAPIError("DeepSeek API key not configured", "DeepSeek")
    
    # Create system prompt for query generation
    system_prompt = """You are a DynamoDB query generator for a lead management system. 
    
The leads table has these fields:
- leadId (string, primary key)
- firstName (string)
- lastName (string) 
- title (string)
- company (string)
- email (string)
- phone (string)
- remarks (string)
- createdAt (string, ISO timestamp)
- updatedAt (string, ISO timestamp)
- sourceFile (string)

Convert natural language queries into JSON query structures. Return ONLY valid JSON with these possible structures:

For filtering leads:
{
  "type": "filter",
  "filters": {
    "firstName": "value",
    "lastName": "value", 
    "company": "value",
    "title": "value",
    "email": "value",
    "phone": "value"
  },
  "limit": 50
}

For counting leads:
{
  "type": "count",
  "filters": {
    "company": "value"
  }
}

For aggregation by field:
{
  "type": "aggregate",
  "groupBy": "company",
  "filters": {}
}

Rules:
- Use partial matching for text fields (contains)
- Only use fields that exist in the schema
- If query is unclear, return null
- Never include sensitive data in the response
- Limit results to reasonable numbers (max 50 for lists)
- For phone queries, understand various formats: phone number, contact, mobile, telephone

Examples:
"Show me leads from Google" -> {"type": "filter", "filters": {"company": "Google"}, "limit": 50}
"How many leads do we have?" -> {"type": "count", "filters": {}}
"List leads with title manager" -> {"type": "filter", "filters": {"title": "manager"}, "limit": 50}
"Group leads by company" -> {"type": "aggregate", "groupBy": "company", "filters": {}}
"Find leads with phone number 555" -> {"type": "filter", "filters": {"phone": "555"}, "limit": 50}
"Show me leads with mobile numbers" -> {"type": "filter", "filters": {"phone": ""}, "limit": 50}
"Who has contact information" -> {"type": "filter", "filters": {"phone": ""}, "limit": 50}
"""

    user_prompt = f"Convert this query to DynamoDB structure: {user_query}"
    
    try:
        def make_api_call():
            response = requests.post(
                DEEPSEEK_API_URL,
                headers={
                    'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'deepseek-chat',
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt}
                    ],
                    'temperature': 0.1,
                    'max_tokens': 500
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        
        # Use retry mechanism for API calls
        api_response = retry_with_backoff(make_api_call, max_retries=1)
        
        # Extract and parse the response
        content = api_response['choices'][0]['message']['content'].strip()
        
        # Try to parse as JSON
        try:
            query_structure = json.loads(content)
            
            # Validate the structure
            if validate_query_structure(query_structure):
                return query_structure
            else:
                return None
                
        except json.JSONDecodeError:
            # If not valid JSON, try to extract JSON from the response
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                try:
                    query_structure = json.loads(json_match.group())
                    if validate_query_structure(query_structure):
                        return query_structure
                except json.JSONDecodeError:
                    pass
            
            return None
    
    except requests.exceptions.RequestException as e:
        raise ExternalAPIError(f"DeepSeek API request failed: {str(e)}", "DeepSeek")
    except Exception as e:
        raise ExternalAPIError(f"DeepSeek API error: {str(e)}", "DeepSeek")

def validate_query_structure(query_structure: Dict[str, Any]) -> bool:
    """
    Validate that the query structure is safe and well-formed.
    
    Args:
        query_structure: Query structure from DeepSeek
        
    Returns:
        bool: True if structure is valid
    """
    if not isinstance(query_structure, dict):
        return False
    
    query_type = query_structure.get('type')
    if query_type not in ['filter', 'count', 'aggregate']:
        return False
    
    # Validate filters if present
    filters = query_structure.get('filters', {})
    if not isinstance(filters, dict):
        return False
    
    # Check that filter fields are valid
    valid_fields = ['firstName', 'lastName', 'title', 'company', 'email', 'phone']
    for field in filters.keys():
        if field not in valid_fields:
            return False
    
    # Validate aggregate groupBy field
    if query_type == 'aggregate':
        group_by = query_structure.get('groupBy')
        if group_by not in valid_fields:
            return False
    
    # Validate limit
    limit = query_structure.get('limit', 50)
    if not isinstance(limit, int) or limit < 1 or limit > 100:
        query_structure['limit'] = 50
    
    return True

def execute_query(query_structure: Dict[str, Any]) -> Any:
    """
    Execute the generated query against DynamoDB.
    
    Args:
        query_structure: Validated query structure
        
    Returns:
        Query results (list or dict depending on query type)
    """
    query_type = query_structure['type']
    filters = query_structure.get('filters', {})
    
    try:
        if query_type == 'filter':
            # Get filtered leads
            limit = query_structure.get('limit', 50)
            result = dynamodb_utils.query_leads(
                filters=filters,
                sort_by='createdAt',
                sort_order='desc',
                page_size=limit
            )
            return result['leads']
        
        elif query_type == 'count':
            # Get count of matching leads
            if filters:
                # Use the existing query method and count results
                result = dynamodb_utils.query_leads(
                    filters=filters,
                    page_size=1000  # Get a large sample to count
                )
                return {'count': result['totalCount']}
            else:
                # Count all leads
                all_leads = dynamodb_utils.get_all_leads_for_export()
                return {'count': len(all_leads)}
        
        elif query_type == 'aggregate':
            # Group leads by specified field
            group_by = query_structure['groupBy']
            all_leads = dynamodb_utils.get_all_leads_for_export(filters)
            
            # Group by the specified field
            groups = {}
            for lead in all_leads:
                key = lead.get(group_by, 'N/A')
                if key not in groups:
                    groups[key] = 0
                groups[key] += 1
            
            # Sort by count descending
            sorted_groups = sorted(groups.items(), key=lambda x: x[1], reverse=True)
            return {'groups': sorted_groups[:20]}  # Limit to top 20 groups
        
        else:
            raise ValidationError(f"Unsupported query type: {query_type}")
    
    except Exception as e:
        raise DatabaseError(f"Failed to execute query: {str(e)}", "execute_query")

def format_query_results(user_query: str, query_structure: Dict[str, Any], results: Any) -> str:
    """
    Format query results into user-friendly response.
    
    Args:
        user_query: Original user query
        query_structure: The query structure used
        results: Results from DynamoDB
        
    Returns:
        str: Formatted response for the user
    """
    query_type = query_structure['type']
    
    try:
        if query_type == 'filter':
            if not results:
                return "I didn't find any leads matching your criteria."
            
            count = len(results)
            if count == 1:
                lead = results[0]
                phone_info = ""
                if lead.get('phone') and lead.get('phone') != 'N/A':
                    phone_info = f", phone: {lead.get('phone')}"
                return f"I found 1 lead: {lead.get('firstName', 'N/A')} {lead.get('lastName', 'N/A')} from {lead.get('company', 'N/A')} ({lead.get('title', 'N/A')}){phone_info}."
            else:
                # Show summary of results
                companies = set()
                titles = set()
                phone_count = 0
                for lead in results[:10]:  # Sample first 10
                    if lead.get('company') and lead.get('company') != 'N/A':
                        companies.add(lead.get('company'))
                    if lead.get('title') and lead.get('title') != 'N/A':
                        titles.add(lead.get('title'))
                    if lead.get('phone') and lead.get('phone') != 'N/A':
                        phone_count += 1
                
                response = f"I found {count} leads"
                if companies:
                    company_list = ', '.join(list(companies)[:3])
                    if len(companies) > 3:
                        company_list += f" and {len(companies) - 3} others"
                    response += f" from companies like {company_list}"
                
                if titles:
                    title_list = ', '.join(list(titles)[:3])
                    if len(titles) > 3:
                        title_list += f" and {len(titles) - 3} others"
                    response += f" with titles like {title_list}"
                
                # Add phone information if relevant to the query
                filters = query_structure.get('filters', {})
                if 'phone' in filters or phone_count > 0:
                    if phone_count > 0:
                        response += f", {phone_count} of which have phone numbers"
                
                response += "."
                return response
        
        elif query_type == 'count':
            count = results.get('count', 0)
            filters = query_structure.get('filters', {})
            
            if not filters:
                return f"You have {count} total leads in your database."
            else:
                filter_desc = []
                for field, value in filters.items():
                    filter_desc.append(f"{field} containing '{value}'")
                
                filter_text = " and ".join(filter_desc)
                return f"You have {count} leads with {filter_text}."
        
        elif query_type == 'aggregate':
            groups = results.get('groups', [])
            group_by = query_structure['groupBy']
            
            if not groups:
                return f"I couldn't find any data to group by {group_by}."
            
            response = f"Here's the breakdown by {group_by}:\n"
            for i, (group_name, count) in enumerate(groups[:10]):
                response += f"• {group_name}: {count} leads\n"
            
            if len(groups) > 10:
                response += f"... and {len(groups) - 10} more groups"
            
            return response.strip()
        
        else:
            return "I processed your query but couldn't format the results properly."
    
    except Exception as e:
        return "I found some results but had trouble formatting them. Please try rephrasing your query."

# Health check endpoint
@lambda_handler_wrapper  
def health_check_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Health check endpoint for the chatbot service.
    
    Args:
        event: API Gateway event
        context: Lambda context object
        
    Returns:
        Dict: Health status response
    """
    return create_success_response({
        'status': 'healthy',
        'service': 'chatbot',
        'deepseek_configured': bool(DEEPSEEK_API_KEY)
    })