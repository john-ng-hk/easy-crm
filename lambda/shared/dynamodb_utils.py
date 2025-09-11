"""
DynamoDB utilities for lead management operations.
Provides standardized CRUD operations and query functionality.
"""

import boto3
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from botocore.exceptions import ClientError
import logging
try:
    from .email_utils import EmailNormalizer
except ImportError:
    from email_utils import EmailNormalizer

logger = logging.getLogger(__name__)

class DynamoDBUtils:
    """Utility class for DynamoDB operations on leads table."""
    
    def __init__(self, table_name: str = 'leads', region: str = 'ap-southeast-1'):
        """
        Initialize DynamoDB client and table resource.
        
        Args:
            table_name: Name of the DynamoDB table
            region: AWS region for DynamoDB
        """
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name
    
    def create_lead(self, lead_data: Dict[str, Any], source_file: str) -> str:
        """
        Create a new lead in DynamoDB.
        
        Args:
            lead_data: Dictionary containing lead information
            source_file: Original filename for tracking
            
        Returns:
            str: The generated leadId
            
        Raises:
            ClientError: If DynamoDB operation fails
        """
        lead_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        item = {
            'leadId': lead_id,
            'firstName': lead_data.get('firstName', 'N/A'),
            'lastName': lead_data.get('lastName', 'N/A'),
            'title': lead_data.get('title', 'N/A'),
            'company': lead_data.get('company', 'N/A'),
            'email': lead_data.get('email', 'N/A'),
            'phone': lead_data.get('phone', 'N/A'),
            'remarks': lead_data.get('remarks', 'N/A'),
            'sourceFile': source_file,
            'createdAt': timestamp,
            'updatedAt': timestamp
        }
        
        try:
            self.table.put_item(Item=item)
            logger.info(f"Created lead with ID: {lead_id}")
            return lead_id
        except ClientError as e:
            logger.error(f"Failed to create lead: {e}")
            raise
    
    def batch_create_leads(self, leads_data: List[Dict[str, Any]], source_file: str) -> List[str]:
        """
        Create multiple leads in batch operation.
        
        Args:
            leads_data: List of lead dictionaries
            source_file: Original filename for tracking
            
        Returns:
            List[str]: List of generated leadIds
            
        Raises:
            ClientError: If batch operation fails
        """
        lead_ids = []
        timestamp = datetime.utcnow().isoformat()
        
        # DynamoDB batch_writer handles batching automatically
        try:
            with self.table.batch_writer() as batch:
                for lead_data in leads_data:
                    lead_id = str(uuid.uuid4())
                    lead_ids.append(lead_id)
                    
                    item = {
                        'leadId': lead_id,
                        'firstName': lead_data.get('firstName', 'N/A'),
                        'lastName': lead_data.get('lastName', 'N/A'),
                        'title': lead_data.get('title', 'N/A'),
                        'company': lead_data.get('company', 'N/A'),
                        'email': lead_data.get('email', 'N/A'),
                        'phone': lead_data.get('phone', 'N/A'),
                        'remarks': lead_data.get('remarks', 'N/A'),
                        'sourceFile': source_file,
                        'createdAt': timestamp,
                        'updatedAt': timestamp
                    }
                    
                    batch.put_item(Item=item)
            
            logger.info(f"Batch created {len(lead_ids)} leads")
            return lead_ids
            
        except ClientError as e:
            logger.error(f"Failed to batch create leads: {e}")
            raise
    
    def get_lead(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single lead by ID.
        
        Args:
            lead_id: The lead ID to retrieve
            
        Returns:
            Optional[Dict]: Lead data or None if not found
        """
        try:
            response = self.table.get_item(Key={'leadId': lead_id})
            return response.get('Item')
        except ClientError as e:
            logger.error(f"Failed to get lead {lead_id}: {e}")
            raise
    
    def query_leads(self, filters: Optional[Dict[str, str]] = None, 
                   sort_by: str = 'createdAt', sort_order: str = 'desc',
                   page_size: int = 50, last_evaluated_key: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Query leads with filtering, sorting, and pagination.
        
        Args:
            filters: Dictionary of field filters
            sort_by: Field to sort by
            sort_order: 'asc' or 'desc'
            page_size: Number of items per page
            last_evaluated_key: Pagination token from previous query
            
        Returns:
            Dict containing leads, pagination info, and total count
        """
        try:
            # Build scan parameters
            scan_kwargs = {
                'Limit': page_size
            }
            
            if last_evaluated_key:
                scan_kwargs['ExclusiveStartKey'] = last_evaluated_key
            
            # Build filter expression
            filter_expression_parts = []
            expression_attribute_names = {}
            expression_attribute_values = {}
            
            # Always exclude processing status records
            filter_expression_parts.append("NOT begins_with(#leadId, :processing_prefix)")
            expression_attribute_names['#leadId'] = 'leadId'
            expression_attribute_values[':processing_prefix'] = 'PROCESSING_STATUS#'
            
            # Add user filters if provided
            if filters:
                for field, value in filters.items():
                    if value and value.strip():  # Only add non-empty filters
                        attr_name = f"#{field}"
                        attr_value = f":{field}"
                        # Use contains for filtering (DynamoDB doesn't support lower() function)
                        filter_expression_parts.append(f"contains({attr_name}, {attr_value})")
                        expression_attribute_names[attr_name] = field
                        expression_attribute_values[attr_value] = value.strip()
            
            # Apply filter expression
            scan_kwargs['FilterExpression'] = ' AND '.join(filter_expression_parts)
            scan_kwargs['ExpressionAttributeNames'] = expression_attribute_names
            scan_kwargs['ExpressionAttributeValues'] = expression_attribute_values
            
            # Execute scan
            response = self.table.scan(**scan_kwargs)
            items = response.get('Items', [])
            
            # Sort results (DynamoDB scan doesn't support sorting)
            reverse = sort_order.lower() == 'desc'
            if sort_by in ['firstName', 'lastName', 'title', 'company', 'email', 'phone', 'createdAt', 'updatedAt']:
                # Handle sorting with proper null/empty value handling
                def sort_key(item):
                    value = item.get(sort_by, '')
                    if value == 'N/A' or not value:
                        return '' if not reverse else 'zzz'  # Sort empty values appropriately
                    return str(value).lower() if isinstance(value, str) else str(value)
                
                items.sort(key=sort_key, reverse=reverse)
            
            # Get total count for pagination (only if no pagination token provided)
            total_count = self._get_total_count(filters) if not last_evaluated_key else 0
            
            result = {
                'leads': items,
                'lastEvaluatedKey': response.get('LastEvaluatedKey'),
                'totalCount': total_count,
                'hasMore': 'LastEvaluatedKey' in response
            }
            
            return result
            
        except ClientError as e:
            logger.error(f"Failed to query leads: {e}")
            raise
    
    def _get_total_count(self, filters: Optional[Dict[str, str]] = None) -> int:
        """
        Get total count of leads matching filters (excludes processing status records).
        
        Args:
            filters: Dictionary of field filters
            
        Returns:
            int: Total count of matching leads
        """
        try:
            scan_kwargs = {'Select': 'COUNT'}
            filter_expression = []
            expression_attribute_names = {}
            expression_attribute_values = {}
            
            # Always exclude processing status records
            filter_expression.append("NOT begins_with(#leadId, :processing_prefix)")
            expression_attribute_names['#leadId'] = 'leadId'
            expression_attribute_values[':processing_prefix'] = 'PROCESSING_STATUS#'
            
            # Add user filters if provided
            if filters:
                for field, value in filters.items():
                    if value and value.strip():
                        attr_name = f"#{field}"
                        attr_value = f":{field}"
                        filter_expression.append(f"contains({attr_name}, {attr_value})")
                        expression_attribute_names[attr_name] = field
                        expression_attribute_values[attr_value] = value.strip()
            
            # Apply filter expression
            scan_kwargs['FilterExpression'] = ' AND '.join(filter_expression)
            scan_kwargs['ExpressionAttributeNames'] = expression_attribute_names
            scan_kwargs['ExpressionAttributeValues'] = expression_attribute_values
            
            response = self.table.scan(**scan_kwargs)
            return response.get('Count', 0)
            
        except ClientError as e:
            logger.error(f"Failed to get total count: {e}")
            return 0
    
    def get_all_leads_for_export(self, filters: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """
        Get all leads matching filters for export (no pagination).
        
        Args:
            filters: Dictionary of field filters
            
        Returns:
            List[Dict]: All matching leads (excludes processing status records)
        """
        try:
            scan_kwargs = {}
            filter_expression = []
            expression_attribute_names = {}
            expression_attribute_values = {}
            
            # Always exclude processing status records
            filter_expression.append("NOT begins_with(#leadId, :processing_prefix)")
            expression_attribute_names['#leadId'] = 'leadId'
            expression_attribute_values[':processing_prefix'] = 'PROCESSING_STATUS#'
            
            # Add user filters if provided
            if filters:
                for field, value in filters.items():
                    if value and value.strip():
                        attr_name = f"#{field}"
                        attr_value = f":{field}"
                        filter_expression.append(f"contains({attr_name}, {attr_value})")
                        expression_attribute_names[attr_name] = field
                        expression_attribute_values[attr_value] = value.strip()
            
            # Apply filter expression
            scan_kwargs['FilterExpression'] = ' AND '.join(filter_expression)
            scan_kwargs['ExpressionAttributeNames'] = expression_attribute_names
            scan_kwargs['ExpressionAttributeValues'] = expression_attribute_values
            
            # Scan all items (handle pagination automatically)
            all_items = []
            last_evaluated_key = None
            
            while True:
                if last_evaluated_key:
                    scan_kwargs['ExclusiveStartKey'] = last_evaluated_key
                
                response = self.table.scan(**scan_kwargs)
                all_items.extend(response.get('Items', []))
                
                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key:
                    break
            
            return all_items
            
        except ClientError as e:
            logger.error(f"Failed to get all leads for export: {e}")
            raise
    
    def get_all_leads_with_filters_and_sort(self, filters: Optional[Dict[str, str]] = None, 
                                          sort_by: str = 'createdAt', sort_order: str = 'desc') -> List[Dict[str, Any]]:
        """
        Get all leads matching filters with sorting applied (for page-based pagination).
        
        Args:
            filters: Dictionary of field filters
            sort_by: Field to sort by
            sort_order: 'asc' or 'desc'
            
        Returns:
            List[Dict]: All matching leads, sorted
        """
        try:
            # Get all leads matching filters
            all_items = self.get_all_leads_for_export(filters)
            
            # Sort results
            reverse = sort_order.lower() == 'desc'
            if sort_by in ['firstName', 'lastName', 'title', 'company', 'email', 'phone', 'createdAt', 'updatedAt']:
                # Handle sorting with proper null/empty value handling
                def sort_key(item):
                    value = item.get(sort_by, '')
                    if value == 'N/A' or not value:
                        return '' if not reverse else 'zzz'  # Sort empty values appropriately
                    return str(value).lower() if isinstance(value, str) else str(value)
                
                all_items.sort(key=sort_key, reverse=reverse)
            
            return all_items
            
        except ClientError as e:
            logger.error(f"Failed to get all leads with filters and sort: {e}")
            raise
    
    def search_leads_by_phone(self, phone_query: str, exact_match: bool = False) -> List[Dict[str, Any]]:
        """
        Search leads by phone number with flexible matching.
        
        Args:
            phone_query: Phone number or partial phone to search for
            exact_match: If True, requires exact match; if False, allows partial matches
            
        Returns:
            List[Dict]: Matching leads
        """
        try:
            scan_kwargs = {}
            
            if exact_match:
                # Exact match using equality
                scan_kwargs['FilterExpression'] = '#phone = :phone_value'
                scan_kwargs['ExpressionAttributeNames'] = {'#phone': 'phone'}
                scan_kwargs['ExpressionAttributeValues'] = {':phone_value': phone_query}
            else:
                # Partial match using contains
                scan_kwargs['FilterExpression'] = 'contains(#phone, :phone_value)'
                scan_kwargs['ExpressionAttributeNames'] = {'#phone': 'phone'}
                scan_kwargs['ExpressionAttributeValues'] = {':phone_value': phone_query}
            
            # Scan all items with phone filter
            all_items = []
            last_evaluated_key = None
            
            while True:
                if last_evaluated_key:
                    scan_kwargs['ExclusiveStartKey'] = last_evaluated_key
                
                response = self.table.scan(**scan_kwargs)
                all_items.extend(response.get('Items', []))
                
                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key:
                    break
            
            return all_items
            
        except ClientError as e:
            logger.error(f"Failed to search leads by phone: {e}")
            raise
    
    def update_lead_phone(self, lead_id: str, new_phone: str) -> bool:
        """
        Update phone number for a specific lead.
        
        Args:
            lead_id: The lead ID to update
            new_phone: New phone number value
            
        Returns:
            bool: True if update was successful
        """
        try:
            timestamp = datetime.utcnow().isoformat()
            
            response = self.table.update_item(
                Key={'leadId': lead_id},
                UpdateExpression='SET phone = :phone, updatedAt = :updated',
                ExpressionAttributeValues={
                    ':phone': new_phone,
                    ':updated': timestamp
                },
                ReturnValues='UPDATED_NEW'
            )
            
            logger.info(f"Updated phone for lead {lead_id}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to update phone for lead {lead_id}: {e}")
            raise
    
    def find_lead_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Find existing lead by email address using EmailIndex GSI.
        
        Args:
            email: Email address to search for (case-insensitive)
            
        Returns:
            Optional[Dict]: Existing lead data or None if not found
            
        Raises:
            ClientError: If DynamoDB operation fails
        """
        try:
            # Normalize email for consistent lookup
            normalized_email = EmailNormalizer.normalize_email(email)
            
            # Skip lookup for empty emails as they should always be treated as unique
            if EmailNormalizer.is_empty_email(normalized_email):
                return None
            
            # Query the EmailIndex GSI
            response = self.table.query(
                IndexName='EmailIndex',
                KeyConditionExpression='email = :email',
                ExpressionAttributeValues={
                    ':email': normalized_email
                },
                Limit=1  # We only need to know if one exists
            )
            
            items = response.get('Items', [])
            if items:
                logger.info(f"Found existing lead for email: {normalized_email}")
                return items[0]
            
            return None
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            
            if error_code == 'ResourceNotFoundException':
                logger.warning(f"EmailIndex GSI not available, cannot check for duplicates: {e}")
                return None
            else:
                logger.error(f"Failed to query EmailIndex for email {normalized_email}: {e}")
                raise
    
    def upsert_lead(self, lead_data: Dict[str, Any], source_file: str) -> Tuple[str, bool]:
        """
        Insert new lead or update existing lead based on email.
        
        Args:
            lead_data: Lead information including email
            source_file: Source filename for tracking
            
        Returns:
            Tuple[str, bool]: (leadId, was_updated)
                - leadId: The lead ID (existing or new)
                - was_updated: True if existing lead was updated, False if new lead created
                
        Raises:
            ClientError: If DynamoDB operation fails
        """
        try:
            email = lead_data.get('email', '')
            normalized_email = EmailNormalizer.normalize_email(email)
            
            # Check for existing lead by email
            existing_lead = self.find_lead_by_email(normalized_email)
            
            if existing_lead:
                # Update existing lead
                lead_id = existing_lead['leadId']
                timestamp = datetime.utcnow().isoformat()
                
                # Preserve original createdAt timestamp
                created_at = existing_lead.get('createdAt', timestamp)
                
                # Update all fields with new data
                updated_item = {
                    'leadId': lead_id,
                    'firstName': lead_data.get('firstName', 'N/A'),
                    'lastName': lead_data.get('lastName', 'N/A'),
                    'title': lead_data.get('title', 'N/A'),
                    'company': lead_data.get('company', 'N/A'),
                    'email': normalized_email,
                    'phone': lead_data.get('phone', 'N/A'),
                    'remarks': lead_data.get('remarks', 'N/A'),
                    'sourceFile': source_file,
                    'createdAt': created_at,
                    'updatedAt': timestamp
                }
                
                self.table.put_item(Item=updated_item)
                logger.info(f"Updated existing lead {lead_id} for email: {normalized_email}")
                return lead_id, True
                
            else:
                # Create new lead
                lead_id = str(uuid.uuid4())
                timestamp = datetime.utcnow().isoformat()
                
                new_item = {
                    'leadId': lead_id,
                    'firstName': lead_data.get('firstName', 'N/A'),
                    'lastName': lead_data.get('lastName', 'N/A'),
                    'title': lead_data.get('title', 'N/A'),
                    'company': lead_data.get('company', 'N/A'),
                    'email': normalized_email,
                    'phone': lead_data.get('phone', 'N/A'),
                    'remarks': lead_data.get('remarks', 'N/A'),
                    'sourceFile': source_file,
                    'createdAt': timestamp,
                    'updatedAt': timestamp
                }
                
                self.table.put_item(Item=new_item)
                logger.info(f"Created new lead {lead_id} for email: {normalized_email}")
                return lead_id, False
                
        except ClientError as e:
            logger.error(f"Failed to upsert lead for email {normalized_email}: {e}")
            raise
    
    def batch_upsert_leads(self, leads_data: List[Dict[str, Any]], source_file: str) -> Dict[str, Any]:
        """
        Batch upsert multiple leads with duplicate detection.
        
        Args:
            leads_data: List of lead dictionaries
            source_file: Source filename for tracking
            
        Returns:
            Dict containing:
                - created_leads: List of new lead IDs
                - updated_leads: List of updated lead IDs  
                - duplicate_actions: List of duplicate handling logs
                - processing_stats: Performance metrics
                
        Raises:
            ClientError: If DynamoDB operation fails
        """
        start_time = datetime.utcnow()
        created_leads = []
        updated_leads = []
        duplicate_actions = []
        
        try:
            # First, resolve duplicates within the batch (last occurrence wins)
            unique_leads, batch_duplicate_logs = self._detect_and_resolve_batch_duplicates(leads_data)
            duplicate_actions.extend(batch_duplicate_logs)
            
            # Process each unique lead
            for lead_data in unique_leads:
                try:
                    lead_id, was_updated = self.upsert_lead(lead_data, source_file)
                    
                    if was_updated:
                        updated_leads.append(lead_id)
                        # Log comprehensive duplicate action with original and new data
                        email = EmailNormalizer.normalize_email(lead_data.get('email', ''))
                        
                        # Get the original lead data for logging
                        original_lead = None
                        original_source_file = 'unknown'
                        try:
                            original_lead = self.find_lead_by_email(email)
                            original_source_file = original_lead.get('sourceFile', 'unknown') if original_lead else 'unknown'
                        except Exception:
                            original_source_file = 'unknown'
                        
                        # Create standardized duplicate action log
                        original_data = {
                            'firstName': original_lead.get('firstName', 'N/A'),
                            'lastName': original_lead.get('lastName', 'N/A'),
                            'title': original_lead.get('title', 'N/A'),
                            'company': original_lead.get('company', 'N/A'),
                            'phone': original_lead.get('phone', 'N/A'),
                            'remarks': original_lead.get('remarks', 'N/A')
                        } if original_lead else {}
                        
                        new_data = {
                            'firstName': lead_data.get('firstName', 'N/A'),
                            'lastName': lead_data.get('lastName', 'N/A'),
                            'title': lead_data.get('title', 'N/A'),
                            'company': lead_data.get('company', 'N/A'),
                            'phone': lead_data.get('phone', 'N/A'),
                            'remarks': lead_data.get('remarks', 'N/A')
                        }
                        
                        duplicate_action_log = self.create_duplicate_action_log(
                            action='lead_updated',
                            email=email,
                            lead_id=lead_id,
                            original_data=original_data,
                            new_data=new_data,
                            source_file=source_file,
                            original_source_file=original_source_file
                        )
                        duplicate_actions.append(duplicate_action_log)
                    else:
                        created_leads.append(lead_id)
                        
                except ClientError as e:
                    # Log individual lead failure but continue processing others
                    logger.error(f"Failed to process individual lead: {e}")
                    duplicate_actions.append({
                        'action': 'lead_failed',
                        'email': EmailNormalizer.normalize_email(lead_data.get('email', '')),
                        'error': str(e),
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    continue
            
            # Calculate processing statistics
            end_time = datetime.utcnow()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            processing_stats = {
                'total_leads_processed': len(leads_data),
                'unique_leads_after_dedup': len(unique_leads),
                'leads_created': len(created_leads),
                'leads_updated': len(updated_leads),
                'batch_duplicates_resolved': len(batch_duplicate_logs),
                'processing_time_ms': processing_time_ms,
                'email_index_queries': len(unique_leads)  # One query per unique lead
            }
            
            # Log comprehensive performance metrics
            total_duplicates = len(updated_leads) + len(batch_duplicate_logs)
            self.log_duplicate_detection_performance(
                batch_size=len(leads_data),
                duplicates_found=total_duplicates,
                processing_time_ms=processing_time_ms,
                email_queries=len(unique_leads)
            )
            
            logger.info(f"Batch upsert completed: {processing_stats}")
            
            return {
                'created_leads': created_leads,
                'updated_leads': updated_leads,
                'duplicate_actions': duplicate_actions,
                'processing_stats': processing_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to batch upsert leads: {e}")
            raise
    


    
    def _detect_and_resolve_batch_duplicates(self, leads_data: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Detect duplicates within batch and resolve conflicts.
        
        Args:
            leads_data: List of lead data from batch
            
        Returns:
            Tuple containing:
                - unique_leads: List of leads with duplicates resolved (last occurrence wins)
                - duplicate_logs: List of duplicate resolution actions for logging
        """
        start_time = datetime.utcnow()
        email_to_lead = {}
        duplicate_logs = []
        
        for i, lead in enumerate(leads_data):
            email = lead.get('email', '')
            normalized_email = EmailNormalizer.normalize_email(email)
            
            # Always treat empty emails as unique by giving them unique keys
            if EmailNormalizer.is_empty_email(normalized_email):
                unique_key = f"no_email_{i}"
                lead['_batch_index'] = i
                email_to_lead[unique_key] = lead
            else:
                if normalized_email in email_to_lead:
                    # Duplicate found within batch
                    previous_lead = email_to_lead[normalized_email]
                    duplicate_logs.append({
                        'action': 'batch_duplicate_resolved',
                        'email': normalized_email,
                        'previous_index': previous_lead.get('_batch_index', -1),
                        'current_index': i,
                        'resolution': 'last_occurrence_wins',
                        'previousData': {
                            'firstName': previous_lead.get('firstName', 'N/A'),
                            'lastName': previous_lead.get('lastName', 'N/A'),
                            'title': previous_lead.get('title', 'N/A'),
                            'company': previous_lead.get('company', 'N/A'),
                            'phone': previous_lead.get('phone', 'N/A'),
                            'remarks': previous_lead.get('remarks', 'N/A')
                        },
                        'newData': {
                            'firstName': lead.get('firstName', 'N/A'),
                            'lastName': lead.get('lastName', 'N/A'),
                            'title': lead.get('title', 'N/A'),
                            'company': lead.get('company', 'N/A'),
                            'phone': lead.get('phone', 'N/A'),
                            'remarks': lead.get('remarks', 'N/A')
                        },
                        'timestamp': datetime.utcnow().isoformat()
                    })
                
                lead['_batch_index'] = i
                email_to_lead[normalized_email] = lead
        
        # Remove batch index from final leads and filter out no_email entries
        unique_leads = []
        for key, lead in email_to_lead.items():
            if not key.startswith('no_email_'):
                # Remove the temporary batch index
                if '_batch_index' in lead:
                    del lead['_batch_index']
                unique_leads.append(lead)
            else:
                # For no_email entries, also remove batch index and add to unique leads
                if '_batch_index' in lead:
                    del lead['_batch_index']
                unique_leads.append(lead)
        
        # Log performance metrics for batch duplicate detection
        end_time = datetime.utcnow()
        detection_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        logger.info(f"Batch duplicate detection completed: {len(leads_data)} leads processed, "
                   f"{len(unique_leads)} unique leads after deduplication, "
                   f"{len(duplicate_logs)} duplicates resolved, "
                   f"processing time: {detection_time_ms}ms")
        
        return unique_leads, duplicate_logs
    
    def log_duplicate_detection_performance(self, batch_size: int, duplicates_found: int, 
                                          processing_time_ms: int, email_queries: int) -> None:
        """
        Log comprehensive performance metrics for duplicate detection operations.
        
        Args:
            batch_size: Number of leads in the batch
            duplicates_found: Number of duplicates detected
            processing_time_ms: Total processing time in milliseconds
            email_queries: Number of EmailIndex queries performed
        """
        performance_metrics = {
            'event': 'duplicate_detection_performance',
            'batch_size': batch_size,
            'duplicates_found': duplicates_found,
            'processing_time_ms': processing_time_ms,
            'email_index_queries': email_queries,
            'avg_time_per_lead_ms': processing_time_ms / batch_size if batch_size > 0 else 0,
            'duplicate_percentage': (duplicates_found / batch_size * 100) if batch_size > 0 else 0,
            'queries_per_lead': email_queries / batch_size if batch_size > 0 else 0,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Duplicate detection performance: {performance_metrics}")
        
        # Log warning if processing time exceeds 20% threshold (requirement 4.3)
        baseline_time_estimate = batch_size * 50  # Assume 50ms baseline per lead
        time_increase_percentage = ((processing_time_ms - baseline_time_estimate) / baseline_time_estimate * 100) if baseline_time_estimate > 0 else 0
        
        if time_increase_percentage > 20:
            logger.warning(f"Duplicate detection processing time exceeded 20% threshold: "
                          f"{time_increase_percentage:.1f}% increase over baseline")
    
    def create_duplicate_action_log(self, action: str, email: str, lead_id: str, 
                                  original_data: Optional[Dict[str, Any]] = None,
                                  new_data: Optional[Dict[str, Any]] = None,
                                  source_file: Optional[str] = None,
                                  original_source_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a standardized duplicate action log entry.
        
        Args:
            action: Type of duplicate action (e.g., 'lead_updated', 'batch_duplicate_resolved')
            email: Email address involved in the duplicate action
            lead_id: Lead ID involved in the action
            original_data: Original lead data (for updates)
            new_data: New lead data
            source_file: New source file name
            original_source_file: Original source file name
            
        Returns:
            Dict: Standardized log entry for duplicate actions
        """
        log_entry = {
            'action': action,
            'email': email,
            'leadId': lead_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if original_data:
            log_entry['originalData'] = original_data
        
        if new_data:
            log_entry['newData'] = new_data
            
        if source_file:
            log_entry['newSourceFile'] = source_file
            
        if original_source_file:
            log_entry['originalSourceFile'] = original_source_file
        
        return log_entry