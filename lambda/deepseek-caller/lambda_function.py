"""
DeepSeek Caller Lambda Function
Processes batches of leads from SQS queue using DeepSeek AI for standardization.
Stores processed leads in DynamoDB.
Triggered by SQS messages.
"""

import json
import os
import boto3
import requests
from datetime import datetime
from typing import Dict, List, Any
import logging

# Import shared utilities
import sys
sys.path.append('/opt/python')  # Lambda layer path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from dynamodb_utils import DynamoDBUtils
from error_handling import (
    setup_logging, lambda_handler_wrapper, FileProcessingError, 
    ExternalAPIError, DatabaseError
)
from validation import LeadValidator
from status_service import ProcessingStatusService
from atomic_status_service import AtomicStatusService

# Initialize logger
logger = setup_logging()

# Environment variables
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
DEEPSEEK_BASE_URL = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
DYNAMODB_TABLE_NAME = os.environ.get('LEADS_TABLE', 'leads')
PROCESSING_STATUS_TABLE = os.environ.get('PROCESSING_STATUS_TABLE')
AWS_REGION = os.environ.get('AWS_REGION', 'ap-southeast-1')

class DeepSeekClient:
    """Client for DeepSeek AI API integration."""
    
    def __init__(self, api_key: str, base_url: str = 'https://api.deepseek.com'):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
    
    def standardize_leads(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Send lead data to DeepSeek for standardization.
        
        Args:
            raw_data: List of raw lead dictionaries from CSV/Excel
            
        Returns:
            List[Dict[str, str]]: Standardized lead data
            
        Raises:
            ExternalAPIError: If DeepSeek API call fails
        """
        if not raw_data:
            return []
        
        # Prepare the prompt for DeepSeek
        prompt = self._create_standardization_prompt(raw_data)
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a data standardization expert focused on maximizing data extraction. Convert lead data to a consistent JSON format with fields: firstName, lastName, title, company, email, phone, remarks. MINIMIZE N/A VALUES - only use 'N/A' when absolutely no information exists. Extract names from emails, companies from domains, split full names, and preserve partial data. Put any data that doesn't fit standard fields into remarks. IMPORTANT: Return ONLY valid JSON array format. Do not include markdown code blocks, explanations, or any other text. Your response must start with '[' and end with ']'."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 4000
        }
        
        try:
            logger.info(f"Sending {len(raw_data)} leads to DeepSeek for standardization")
            
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code != 200:
                raise ExternalAPIError(
                    f"DeepSeek API returned status {response.status_code}: {response.text}",
                    api_name="DeepSeek"
                )
            
            result = response.json()
            
            if 'choices' not in result or not result['choices']:
                raise ExternalAPIError(
                    "Invalid response format from DeepSeek API",
                    api_name="DeepSeek"
                )
            
            content = result['choices'][0]['message']['content']
            
            # Clean the response - remove markdown code blocks if present
            cleaned_content = self._clean_deepseek_response(content)
            
            # Parse the JSON response
            try:
                standardized_data = json.loads(cleaned_content)
                if not isinstance(standardized_data, list):
                    raise ValueError("Expected list of leads")
                
                logger.info(f"Successfully standardized {len(standardized_data)} leads")
                return standardized_data
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse DeepSeek response: {content}")
                raise ExternalAPIError(
                    f"Invalid JSON response from DeepSeek: {str(e)}",
                    api_name="DeepSeek"
                )
                
        except requests.exceptions.RequestException as e:
            raise ExternalAPIError(
                f"Network error calling DeepSeek API: {str(e)}",
                api_name="DeepSeek"
            )
    
    def _create_standardization_prompt(self, raw_data: List[Dict[str, Any]]) -> str:
        """
        Create an enhanced prompt for DeepSeek to standardize lead data with minimal N/A values.
        
        Args:
            raw_data: Raw lead data from CSV/Excel
            
        Returns:
            str: Enhanced formatted prompt for DeepSeek
        """
        prompt = """Please standardize the following lead data into a JSON array. Each lead should have exactly these fields: firstName, lastName, title, company, email, phone, remarks.

CRITICAL INSTRUCTIONS FOR DATA EXTRACTION:
1. MINIMIZE N/A VALUES: Only use 'N/A' when absolutely no relevant information exists
2. EXTRACT CREATIVELY: Look for names in email addresses, company info in domains, etc.
3. SPLIT FULL NAMES: If you see "John Doe", split into firstName: "John", lastName: "Doe"
4. EXTRACT FROM EMAILS: If email is "john.doe@company.com", extract firstName: "John", lastName: "Doe", company: "Company"
5. USE PARTIAL DATA: If you only have partial information, use what you have rather than N/A
6. PRESERVE ORIGINAL: If data looks good as-is, keep it unchanged
7. COMBINE FIELDS: Put extra information in remarks rather than losing it
8. SMART EXTRACTION: Extract company names from email domains (gmail.com → leave company as is, but acme.com → "Acme")

EXAMPLES OF GOOD EXTRACTION:
- Email "j.smith@acme.com" → firstName: "J", lastName: "Smith", company: "Acme"
- Name "John" → firstName: "John", lastName: "" (empty, not N/A)
- Company "ABC Corp" → company: "ABC Corp"
- Phone "+1-555-123" → phone: "+1-555-123" (keep as-is even if incomplete)
- Full name "Sarah Johnson" → firstName: "Sarah", lastName: "Johnson"

AVOID THESE PATTERNS:
- Don't use N/A unless truly no information exists
- Don't lose data that could go in remarks
- Don't create records with mostly N/A values
- Don't ignore partial phone numbers or names

EMAIL HANDLING:
- Preserve original email format but ensure it's properly formatted (lowercase, no extra spaces)
- Extract names from email addresses when possible
- Use email domain for company name only if no other company info exists and domain is not generic (gmail, yahoo, etc.)

"""
        
        prompt += "Raw lead data:\n"
        for i, lead in enumerate(raw_data, 1):
            prompt += f"\nLead {i}:\n"
            for key, value in lead.items():
                if value and str(value).strip():
                    prompt += f"  {key}: {value}\n"
        
        prompt += "\nIMPORTANT: Return ONLY a valid JSON array starting with '[' and ending with ']'. Minimize N/A values by extracting as much meaningful data as possible. Do not include markdown formatting, code blocks, explanations, or any other text."
        
        return prompt
    
    def _clean_deepseek_response(self, content: str) -> str:
        """
        Clean DeepSeek response by removing markdown code blocks and extra formatting.
        
        Args:
            content: Raw response content from DeepSeek
            
        Returns:
            str: Cleaned JSON content
        """
        # Strip whitespace first
        content = content.strip()
        
        # Remove markdown code blocks
        if content.startswith('```json'):
            content = content[7:]  # Remove ```json
        elif content.startswith('```'):
            content = content[3:]   # Remove ```
        
        if content.endswith('```'):
            content = content[:-3]  # Remove trailing ```
        
        # Strip whitespace again
        content = content.strip()
        
        # Find JSON array boundaries if there's extra text
        start_idx = content.find('[')
        end_idx = content.rfind(']')
        
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            content = content[start_idx:end_idx + 1]
        
        return content

def log_duplicate_handling_summary(batch_id: str, source_file: str, batch_number: int, 
                                 total_batches: int, processed_leads: int, created_leads: int, 
                                 updated_leads: int, duplicate_actions: List[Dict[str, Any]], 
                                 processing_stats: Dict[str, Any]) -> None:
    """
    Log comprehensive duplicate handling statistics for monitoring and analysis.
    
    Args:
        batch_id: Unique batch identifier
        source_file: Source file name
        batch_number: Current batch number
        total_batches: Total number of batches
        processed_leads: Number of leads processed by DeepSeek
        created_leads: Number of new leads created
        updated_leads: Number of existing leads updated
        duplicate_actions: List of duplicate action logs
        processing_stats: Processing performance statistics
    """
    # Calculate duplicate statistics
    total_duplicates = updated_leads + len([action for action in duplicate_actions if action.get('action') == 'batch_duplicate_resolved'])
    duplicate_percentage = (total_duplicates / processed_leads * 100) if processed_leads > 0 else 0
    
    # Create comprehensive summary log
    summary_log = {
        'event': 'duplicate_handling_summary',
        'batch_id': batch_id,
        'source_file': source_file,
        'batch_number': batch_number,
        'total_batches': total_batches,
        'leads_processed': processed_leads,
        'leads_created': created_leads,
        'leads_updated': updated_leads,
        'total_stored': created_leads + updated_leads,
        'duplicates_detected': total_duplicates,
        'duplicate_percentage': round(duplicate_percentage, 2),
        'batch_duplicates': len([action for action in duplicate_actions if action.get('action') == 'batch_duplicate_resolved']),
        'database_duplicates': updated_leads,
        'processing_stats': processing_stats,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    # Log the summary
    logger.info(f"Duplicate handling summary: {json.dumps(summary_log)}")
    
    # Log individual duplicate actions for detailed tracking
    for action in duplicate_actions:
        if action.get('action') in ['lead_updated', 'batch_duplicate_resolved']:
            logger.info(f"Duplicate action: {json.dumps(action)}")
    
    # Log performance warnings if processing time exceeds thresholds
    processing_time_ms = processing_stats.get('processing_time_ms', 0)
    if processing_time_ms > 0:
        # Estimate baseline processing time (assuming 100ms per lead baseline)
        baseline_time_ms = processed_leads * 100
        time_increase_percentage = ((processing_time_ms - baseline_time_ms) / baseline_time_ms * 100) if baseline_time_ms > 0 else 0
        
        if time_increase_percentage > 20:  # Requirement 4.3: not more than 20% increase
            logger.warning(f"Duplicate detection processing time exceeded 20% threshold for batch {batch_id}: "
                          f"{time_increase_percentage:.1f}% increase over baseline "
                          f"({processing_time_ms}ms vs {baseline_time_ms}ms baseline)")

def process_batch_with_deepseek(batch_data: Dict[str, Any], db_utils: DynamoDBUtils, status_service: AtomicStatusService = None) -> Dict[str, Any]:
    """
    Process a batch of leads with DeepSeek and store in DynamoDB with duplicate handling.
    
    Args:
        batch_data: Batch data from SQS message
        
    Returns:
        Dict[str, Any]: Processing result with duplicate handling metrics
        
    Raises:
        ExternalAPIError: If DeepSeek processing fails
        DatabaseError: If DynamoDB operations fail
    """
    batch_id = batch_data.get('batch_id')
    upload_id = batch_data.get('upload_id')
    source_file = batch_data.get('source_file')
    batch_number = batch_data.get('batch_number')
    total_batches = batch_data.get('total_batches')
    raw_leads = batch_data.get('leads', [])
    
    logger.info(f"Processing batch {batch_id}: {batch_number}/{total_batches} from {source_file} with {len(raw_leads)} leads")
    
    # Check if processing has been cancelled before starting batch processing
    if status_service and upload_id:
        try:
            current_status = status_service.get_status(upload_id)
            if current_status.get('status') == 'cancelled':
                logger.info(f"Processing cancelled for upload {upload_id}, skipping batch {batch_id}")
                return {
                    'batch_id': batch_id,
                    'processed_leads': 0,
                    'stored_leads': 0,
                    'created_leads': 0,
                    'updated_leads': 0,
                    'duplicate_actions': [],
                    'status': 'cancelled',
                    'message': 'Processing was cancelled by user'
                }
        except Exception as e:
            logger.warning(f"Failed to check cancellation status for upload {upload_id}: {str(e)}")
            # Continue processing if status check fails
    
    if not raw_leads:
        logger.warning("No leads to process in batch")
        return {
            'batch_id': batch_id,
            'processed_leads': 0,
            'stored_leads': 0,
            'created_leads': 0,
            'updated_leads': 0,
            'duplicate_actions': [],
            'errors': ['No leads in batch']
        }
    
    # Initialize DeepSeek client
    if not DEEPSEEK_API_KEY:
        raise ExternalAPIError("DeepSeek API key not configured", api_name="DeepSeek")
    
    deepseek_client = DeepSeekClient(DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL)
    
    # Process with DeepSeek
    try:
        standardized_leads = deepseek_client.standardize_leads(raw_leads)
    except Exception as e:
        logger.error(f"DeepSeek processing failed for batch {batch_id}: {str(e)}")
        
        # Update status with error if status service is available and upload_id is provided
        if status_service and upload_id:
            try:
                status_service.set_error(
                    upload_id=upload_id,
                    error_message=f"DeepSeek processing failed for batch {batch_number}: {str(e)}",
                    error_code='DEEPSEEK_API_ERROR'
                )
                logger.info(f"Updated status with DeepSeek error for upload {upload_id}")
            except Exception as status_error:
                logger.warning(f"Failed to update error status for upload {upload_id}: {status_error}")
        
        raise ExternalAPIError(f"DeepSeek processing failed: {str(e)}", api_name="DeepSeek")
    
    # Validate standardized data
    valid_leads = []
    validation_errors = []
    
    for i, lead in enumerate(standardized_leads):
        try:
            is_valid, errors = LeadValidator.validate_lead_data(lead)
            if is_valid:
                valid_leads.append(lead)
            else:
                validation_errors.append(f"Lead {i+1}: {errors}")
                logger.warning(f"Lead {i+1} validation failed: {errors}")
        except Exception as e:
            validation_errors.append(f"Lead {i+1}: Validation error - {str(e)}")
            logger.warning(f"Error validating lead {i+1}: {str(e)}")
    
    if not valid_leads:
        error_msg = "No valid leads found after standardization"
        
        # Update status with error if status service is available and upload_id is provided
        if status_service and upload_id:
            try:
                status_service.set_error(
                    upload_id=upload_id,
                    error_message=f"Validation failed for batch {batch_number}: {error_msg}",
                    error_code='VALIDATION_ERROR'
                )
                logger.info(f"Updated status with validation error for upload {upload_id}")
            except Exception as status_error:
                logger.warning(f"Failed to update error status for upload {upload_id}: {status_error}")
        
        raise FileProcessingError(error_msg)
    
    logger.info(f"Validated {len(valid_leads)} out of {len(standardized_leads)} standardized leads")
    
    # Store in DynamoDB with duplicate handling
    try:
        # Use batch_upsert_leads instead of batch_create_leads for duplicate handling
        upsert_result = db_utils.batch_upsert_leads(valid_leads, source_file)
        
        # Extract results from upsert operation
        created_leads = upsert_result.get('created_leads', [])
        updated_leads = upsert_result.get('updated_leads', [])
        duplicate_actions = upsert_result.get('duplicate_actions', [])
        processing_stats = upsert_result.get('processing_stats', {})
        
        total_stored = len(created_leads) + len(updated_leads)
        
        # Log comprehensive duplicate handling statistics
        log_duplicate_handling_summary(
            batch_id=batch_id,
            source_file=source_file,
            batch_number=batch_number,
            total_batches=total_batches,
            processed_leads=len(standardized_leads),
            created_leads=len(created_leads),
            updated_leads=len(updated_leads),
            duplicate_actions=duplicate_actions,
            processing_stats=processing_stats
        )
        
        logger.info(f"Successfully processed batch {batch_id}: {len(created_leads)} created, {len(updated_leads)} updated")
        
        # Update processing status using atomic increment if status service is available and upload_id is provided
        if status_service and upload_id:
            try:
                # Use atomic increment to prevent race conditions
                updated_status = status_service.atomic_increment_batch_completion(
                    upload_id=upload_id,
                    leads_processed=len(standardized_leads)
                )
                
                progress = updated_status.get('progress', {})
                completed_batches = progress.get('completedBatches', 0)
                total_batches_count = progress.get('totalBatches', 0)
                
                if updated_status.get('status') == 'completed':
                    logger.info(f"Processing completed for upload {upload_id}: {progress.get('processedLeads', 0)} leads processed")
                else:
                    logger.info(f"Updated progress for upload {upload_id}: {completed_batches}/{total_batches_count} batches completed")
                    
            except Exception as status_error:
                logger.warning(f"Failed to update processing status for upload {upload_id}: {status_error}")
        
        return {
            'batch_id': batch_id,
            'upload_id': upload_id,
            'source_file': source_file,
            'batch_number': batch_number,
            'total_batches': total_batches,
            'processed_leads': len(standardized_leads),
            'stored_leads': total_stored,
            'created_leads': len(created_leads),
            'updated_leads': len(updated_leads),
            'duplicate_actions': duplicate_actions,
            'processing_stats': processing_stats,
            'validation_errors': validation_errors,
            'lead_ids': (created_leads + updated_leads)[:5]  # Return first 5 IDs for reference
        }
        
    except Exception as e:
        # Implement fallback behavior for duplicate detection failures
        logger.error(f"Duplicate handling failed for batch {batch_id}: {str(e)}")
        
        # Try fallback to original batch_create_leads method
        try:
            logger.warning(f"Falling back to batch_create_leads for batch {batch_id}")
            lead_ids = db_utils.batch_create_leads(valid_leads, source_file)
            
            
            # Log fallback action
            fallback_log = {
                'action': 'duplicate_detection_fallback',
                'batch_id': batch_id,
                'source_file': source_file,
                'fallback_reason': str(e),
                'leads_created': len(lead_ids),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.warning(f"Fallback successful for batch {batch_id}: {fallback_log}")
            
            # Update processing status for fallback case using atomic increment
            if status_service and upload_id:
                try:
                    # Use atomic increment to prevent race conditions (fallback case)
                    updated_status = status_service.atomic_increment_batch_completion(
                        upload_id=upload_id,
                        leads_processed=len(standardized_leads)
                    )
                    
                    progress = updated_status.get('progress', {})
                    completed_batches = progress.get('completedBatches', 0)
                    total_batches_count = progress.get('totalBatches', 0)
                    
                    if updated_status.get('status') == 'completed':
                        logger.info(f"Processing completed (fallback) for upload {upload_id}: {progress.get('processedLeads', 0)} leads processed")
                    else:
                        logger.info(f"Updated progress (fallback) for upload {upload_id}: {completed_batches}/{total_batches_count} batches completed")
                        
                except Exception as status_error:
                    logger.warning(f"Failed to update processing status (fallback) for upload {upload_id}: {status_error}")
            
            return {
                'batch_id': batch_id,
                'upload_id': upload_id,
                'source_file': source_file,
                'batch_number': batch_number,
                'total_batches': total_batches,
                'processed_leads': len(standardized_leads),
                'stored_leads': len(lead_ids),
                'created_leads': len(lead_ids),
                'updated_leads': 0,
                'duplicate_actions': [fallback_log],
                'processing_stats': {'fallback_used': True},
                'validation_errors': validation_errors,
                'lead_ids': lead_ids[:5],
                'fallback_used': True
            }
            
        except Exception as fallback_error:
            logger.error(f"Fallback also failed for batch {batch_id}: {str(fallback_error)}")
            
            # Update status with error if status service is available and upload_id is provided
            if status_service and upload_id:
                try:
                    status_service.set_error(
                        upload_id=upload_id,
                        error_message=f"Database storage failed for batch {batch_number}: {str(e)} | Fallback error: {str(fallback_error)}",
                        error_code='DATABASE_ERROR'
                    )
                    logger.info(f"Updated status with database error for upload {upload_id}")
                except Exception as status_error:
                    logger.warning(f"Failed to update error status for upload {upload_id}: {status_error}")
            
            raise DatabaseError(f"Failed to store leads in DynamoDB (duplicate handling and fallback both failed): {str(e)} | Fallback error: {str(fallback_error)}", operation="batch_upsert_with_fallback")

@lambda_handler_wrapper
def lambda_handler(event, context):
    """
    Lambda handler for SQS batch processing events with duplicate handling.
    
    Args:
        event: SQS event with batch messages
        context: Lambda context
        
    Returns:
        Dict: Processing result with duplicate handling metrics
    """
    logger.info("DeepSeek caller Lambda triggered with duplicate handling enabled")
    
    try:
        # Parse SQS event
        if 'Records' not in event:
            raise FileProcessingError("Invalid SQS event format")
        
        results = []
        total_created = 0
        total_updated = 0
        total_duplicates = 0
        
        # Initialize DynamoDB utils once for all batches
        db_utils = DynamoDBUtils(DYNAMODB_TABLE_NAME, AWS_REGION)
        
        # Initialize atomic status service if table is configured
        status_service = AtomicStatusService(table_name=PROCESSING_STATUS_TABLE) if PROCESSING_STATUS_TABLE else None
        
        for record in event['Records']:
            # Extract message body
            try:
                message_body = json.loads(record['body'])
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse SQS message body: {str(e)}")
                continue
            
            # Process the batch with duplicate handling
            try:
                result = process_batch_with_deepseek(message_body, db_utils, status_service)
                results.append(result)
                
                # Aggregate statistics across all batches
                total_created += result.get('created_leads', 0)
                total_updated += result.get('updated_leads', 0)
                total_duplicates += len(result.get('duplicate_actions', []))
                
                # Log success with duplicate handling metrics
                batch_id = result.get('batch_id', 'unknown')
                created_count = result.get('created_leads', 0)
                updated_count = result.get('updated_leads', 0)
                fallback_used = result.get('fallback_used', False)
                
                if fallback_used:
                    logger.warning(f"Batch {batch_id} processed with fallback: {created_count} leads created")
                else:
                    logger.info(f"Batch {batch_id} processed successfully: {created_count} created, {updated_count} updated")
                
            except Exception as e:
                batch_id = message_body.get('batch_id', 'unknown')
                upload_id = message_body.get('upload_id')
                batch_number = message_body.get('batch_number', 'unknown')
                
                logger.error(f"Failed to process batch {batch_id} with duplicate handling: {str(e)}")
                
                # Update status with error if status service is available and upload_id is provided
                if status_service and upload_id:
                    try:
                        status_service.set_error(
                            upload_id=upload_id,
                            error_message=f"Batch processing failed for batch {batch_number}: {str(e)}",
                            error_code='BATCH_PROCESSING_ERROR'
                        )
                        logger.info(f"Updated status with batch processing error for upload {upload_id}")
                    except Exception as status_error:
                        logger.warning(f"Failed to update error status for upload {upload_id}: {status_error}")
                
                # Log detailed error information for troubleshooting
                error_details = {
                    'event': 'batch_processing_error',
                    'batch_id': batch_id,
                    'upload_id': upload_id,
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'source_file': message_body.get('source_file', 'unknown'),
                    'batch_number': batch_number,
                    'timestamp': datetime.utcnow().isoformat()
                }
                logger.error(f"Batch processing error details: {json.dumps(error_details)}")
                
                # Re-raise to trigger SQS retry mechanism
                raise
        
        # Log overall processing summary
        overall_summary = {
            'event': 'lambda_execution_summary',
            'batches_processed': len(results),
            'total_leads_created': total_created,
            'total_leads_updated': total_updated,
            'total_duplicate_actions': total_duplicates,
            'duplicate_detection_enabled': True,
            'timestamp': datetime.utcnow().isoformat()
        }
        logger.info(f"Lambda execution summary: {json.dumps(overall_summary)}")
        
        return {
            'statusCode': 200,
            'body': {
                'message': 'Batch processing with duplicate handling completed successfully',
                'results': results,
                'summary': {
                    'batches_processed': len(results),
                    'total_created': total_created,
                    'total_updated': total_updated,
                    'total_duplicates': total_duplicates
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Batch processing with duplicate handling failed: {str(e)}")
        raise