"""
Lead Splitter Lambda Function
Processes uploaded CSV/Excel files, splits leads into batches of 10,
and sends them to SQS queue for DeepSeek processing.
Triggered by S3 PUT events.
"""

import json
import os
import boto3
import pandas as pd
from typing import Dict, List, Any
from urllib.parse import unquote_plus
import logging
from io import StringIO, BytesIO
import uuid
import hashlib
from datetime import datetime

# Import shared utilities
import sys
sys.path.append('/opt/python')  # Lambda layer path
sys.path.append(os.path.join(os.path.dirname(__file__), 'shared'))  # Shared folder in same directory

from error_handling import (
    setup_logging, lambda_handler_wrapper, FileProcessingError
)
from validation import LeadValidator
from dynamodb_utils import DynamoDBUtils
from status_service import ProcessingStatusService

# Initialize logger
logger = setup_logging()

# Initialize AWS clients
s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')

# Environment variables
PROCESSING_QUEUE_URL = os.environ.get('PROCESSING_QUEUE_URL')
PROCESSING_STATUS_TABLE = os.environ.get('PROCESSING_STATUS_TABLE')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'prod')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', f'easy-crm-leads-{ENVIRONMENT}')

# Initialize DynamoDB utils
dynamodb_utils = DynamoDBUtils(table_name=DYNAMODB_TABLE)

# Initialize status service
status_service = ProcessingStatusService(table_name=PROCESSING_STATUS_TABLE) if PROCESSING_STATUS_TABLE else None

class FileProcessor:
    """Handles CSV/Excel file processing."""
    
    @staticmethod
    def read_csv_file(file_content: bytes) -> List[Dict[str, Any]]:
        """
        Read CSV file content and return list of dictionaries.
        
        Args:
            file_content: Raw file content as bytes
            
        Returns:
            List[Dict[str, Any]]: List of lead dictionaries
            
        Raises:
            FileProcessingError: If file cannot be processed
        """
        try:
            # Try different encodings
            encodings = ['utf-8', 'latin-1', 'cp1252']
            
            for encoding in encodings:
                try:
                    content_str = file_content.decode(encoding)
                    df = pd.read_csv(StringIO(content_str))
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise FileProcessingError("Unable to decode CSV file with supported encodings")
            
            # Convert to list of dictionaries
            leads = df.to_dict('records')
            
            # Validate that we have some data
            if df.empty:
                raise FileProcessingError("CSV file contains no data")
            
            # Clean up NaN values
            cleaned_leads = []
            for lead in leads:
                cleaned_lead = {}
                for key, value in lead.items():
                    if pd.isna(value):
                        cleaned_lead[key] = ''
                    else:
                        cleaned_lead[key] = str(value).strip()
                cleaned_leads.append(cleaned_lead)
            
            logger.info(f"Successfully parsed CSV file with {len(cleaned_leads)} leads")
            return cleaned_leads
            
        except Exception as e:
            raise FileProcessingError(f"Failed to process CSV file: {str(e)}")
    
    @staticmethod
    def read_excel_file(file_content: bytes) -> List[Dict[str, Any]]:
        """
        Read Excel file content from all worksheets and return list of dictionaries.
        
        Args:
            file_content: Raw file content as bytes
            
        Returns:
            List[Dict[str, Any]]: List of lead dictionaries from all worksheets
            
        Raises:
            FileProcessingError: If file cannot be processed
        """
        try:
            # Read Excel file to get all sheet names
            excel_file = pd.ExcelFile(BytesIO(file_content))
            sheet_names = excel_file.sheet_names
            
            logger.info(f"Found {len(sheet_names)} worksheets: {sheet_names}")
            
            all_leads = []
            processed_sheets = []
            
            # Process each worksheet
            for sheet_name in sheet_names:
                try:
                    logger.info(f"Processing worksheet: {sheet_name}")
                    
                    # Read the specific worksheet
                    df = pd.read_excel(BytesIO(file_content), sheet_name=sheet_name)
                    
                    # Skip empty worksheets
                    if df.empty:
                        logger.warning(f"Worksheet '{sheet_name}' is empty, skipping")
                        continue
                    
                    # Convert to list of dictionaries
                    sheet_leads = df.to_dict('records')
                    
                    # Clean up NaN values and add worksheet info
                    cleaned_leads = []
                    for lead in sheet_leads:
                        cleaned_lead = {}
                        for key, value in lead.items():
                            if pd.isna(value):
                                cleaned_lead[key] = ''
                            else:
                                cleaned_lead[key] = str(value).strip()
                        
                        # Add worksheet source information
                        cleaned_lead['_worksheet'] = sheet_name
                        cleaned_leads.append(cleaned_lead)
                    
                    all_leads.extend(cleaned_leads)
                    processed_sheets.append(sheet_name)
                    
                    logger.info(f"Processed {len(cleaned_leads)} leads from worksheet '{sheet_name}'")
                    
                except Exception as sheet_error:
                    logger.warning(f"Failed to process worksheet '{sheet_name}': {str(sheet_error)}")
                    continue
            
            # Validate that we have some data
            if not all_leads:
                raise FileProcessingError("Excel file contains no processable data in any worksheet")
            
            logger.info(f"Successfully parsed Excel file with {len(all_leads)} total leads from {len(processed_sheets)} worksheets: {processed_sheets}")
            return all_leads
            
        except Exception as e:
            raise FileProcessingError(f"Failed to process Excel file: {str(e)}")

def extract_upload_id_from_s3_metadata(bucket: str, key: str) -> str:
    """
    Extract upload ID from S3 object metadata.
    Falls back to extracting from key path if metadata is not available.
    
    Args:
        bucket: S3 bucket name
        key: S3 object key
        
    Returns:
        str: Upload ID or generated UUID if not found
    """
    try:
        # First try to get upload_id from S3 object metadata
        response = s3_client.head_object(Bucket=bucket, Key=key)
        metadata = response.get('Metadata', {})
        
        # Check for upload-id in metadata (set by file upload Lambda)
        upload_id = metadata.get('upload-id')
        if upload_id:
            logger.info(f"Found upload_id in S3 metadata: {upload_id}")
            return upload_id
        
        logger.warning(f"No upload-id found in S3 metadata for {key}, falling back to key extraction")
        
        # Fallback: Try to extract from path like uploads/{file_id}/{filename}
        parts = key.split('/')
        if len(parts) >= 2 and parts[0] == 'uploads':
            file_id = parts[1]
            logger.info(f"Extracted file_id from key path: {file_id}")
            return file_id
        
        # Try to extract from filename if it contains UUID
        filename = parts[-1]
        if '_' in filename:
            # Look for UUID-like pattern in filename
            name_parts = filename.split('_')
            for part in name_parts:
                if len(part) == 36 and part.count('-') == 4:  # UUID format
                    logger.info(f"Found UUID in filename: {part}")
                    return part
        
        # If no upload_id found, generate one based on the key
        # This ensures consistency for the same file
        generated_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, key))
        logger.warning(f"Generated upload_id from key hash: {generated_id}")
        return generated_id
        
    except Exception as e:
        logger.error(f"Failed to extract upload_id from S3 metadata/key {key}: {e}")
        return str(uuid.uuid4())

def download_file_from_s3(bucket: str, key: str) -> bytes:
    """
    Download file from S3.
    
    Args:
        bucket: S3 bucket name
        key: S3 object key
        
    Returns:
        bytes: File content
        
    Raises:
        FileProcessingError: If download fails
    """
    try:
        logger.info(f"Downloading file from S3: s3://{bucket}/{key}")
        
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read()
        
        logger.info(f"Successfully downloaded file, size: {len(content)} bytes")
        return content
        
    except Exception as e:
        raise FileProcessingError(f"Failed to download file from S3: {str(e)}")

def split_leads_into_batches(leads: List[Dict[str, Any]], batch_size: int = 10) -> List[List[Dict[str, Any]]]:
    """
    Split leads into batches of specified size.
    
    Args:
        leads: List of lead dictionaries
        batch_size: Number of leads per batch
        
    Returns:
        List[List[Dict[str, Any]]]: List of lead batches
    """
    batches = []
    for i in range(0, len(leads), batch_size):
        batch = leads[i:i + batch_size]
        batches.append(batch)
    
    logger.info(f"Split {len(leads)} leads into {len(batches)} batches of up to {batch_size} leads each")
    return batches

def send_batch_to_sqs(batch: List[Dict[str, Any]], source_file: str, batch_number: int, total_batches: int, upload_id: str = None) -> str:
    """
    Send a batch of leads to SQS queue for processing.
    
    Args:
        batch: List of lead dictionaries
        source_file: Original filename
        batch_number: Current batch number (1-based)
        total_batches: Total number of batches
        upload_id: Upload identifier for status tracking
        
    Returns:
        str: SQS message ID
        
    Raises:
        FileProcessingError: If SQS send fails
    """
    try:
        # Create message payload
        message_body = {
            'batch_id': str(uuid.uuid4()),
            'upload_id': upload_id,
            'source_file': source_file,
            'batch_number': batch_number,
            'total_batches': total_batches,
            'leads': batch,
            'timestamp': datetime.utcnow().isoformat(),
            'environment': ENVIRONMENT
        }
        
        # Send message to SQS
        response = sqs_client.send_message(
            QueueUrl=PROCESSING_QUEUE_URL,
            MessageBody=json.dumps(message_body),
            MessageAttributes={
                'source_file': {
                    'StringValue': source_file,
                    'DataType': 'String'
                },
                'batch_number': {
                    'StringValue': str(batch_number),
                    'DataType': 'Number'
                },
                'lead_count': {
                    'StringValue': str(len(batch)),
                    'DataType': 'Number'
                }
            }
        )
        
        message_id = response['MessageId']
        logger.info(f"Sent batch {batch_number}/{total_batches} to SQS with {len(batch)} leads, MessageId: {message_id}")
        
        return message_id
        
    except Exception as e:
        raise FileProcessingError(f"Failed to send batch to SQS: {str(e)}")

@lambda_handler_wrapper
def lambda_handler(event, context):
    """
    Lambda handler for S3 file processing events.
    Splits leads into batches and sends to SQS queue.
    
    Args:
        event: S3 event notification
        context: Lambda context
        
    Returns:
        Dict: Processing result
    """
    logger.info("Lead splitter Lambda triggered")
    
    if not PROCESSING_QUEUE_URL:
        raise FileProcessingError("PROCESSING_QUEUE_URL environment variable not set")
    
    try:
        # Parse S3 event
        if 'Records' not in event:
            raise FileProcessingError("Invalid S3 event format")
        
        results = []
        
        for record in event['Records']:
            upload_id = None
            
            try:
                # Extract S3 information
                s3_info = record.get('s3', {})
                bucket = s3_info.get('bucket', {}).get('name')
                key = unquote_plus(s3_info.get('object', {}).get('key', ''))
                
                if not bucket or not key:
                    logger.error(f"Invalid S3 record: {record}")
                    continue
                
                logger.info(f"Processing file: s3://{bucket}/{key}")
                
                # Extract upload_id and filename for tracking
                upload_id = extract_upload_id_from_s3_metadata(bucket, key)
                source_file = key.split('/')[-1] if '/' in key else key
                
                logger.info(f"Extracted upload_id: {upload_id} for file: {source_file}")
                
                # Update status to processing if status service is available
                if status_service and upload_id:
                    try:
                        status_service.update_status(
                            upload_id=upload_id,
                            status='processing',
                            stage='file_processing'
                        )
                        logger.info(f"Updated status to 'processing' for upload {upload_id}")
                    except Exception as status_error:
                        logger.warning(f"Failed to update status to processing: {status_error}")
                
                # Validate file type
                if not LeadValidator.validate_file_type(source_file):
                    error_msg = f"Unsupported file type: {source_file}"
                    logger.error(error_msg)
                    
                    # Update status with error
                    if status_service and upload_id:
                        try:
                            status_service.set_error(upload_id, error_msg, 'INVALID_FILE_TYPE')
                        except Exception as status_error:
                            logger.warning(f"Failed to update error status: {status_error}")
                    continue
                
                # Download file from S3
                file_content = download_file_from_s3(bucket, key)
                
                # Process file based on type
                if source_file.lower().endswith('.csv'):
                    raw_leads = FileProcessor.read_csv_file(file_content)
                else:  # Excel files
                    raw_leads = FileProcessor.read_excel_file(file_content)
                
                if not raw_leads:
                    error_msg = f"No data found in file: {source_file}"
                    logger.warning(error_msg)
                    
                    # Update status with error
                    if status_service and upload_id:
                        try:
                            status_service.set_error(upload_id, error_msg, 'NO_DATA_FOUND')
                        except Exception as status_error:
                            logger.warning(f"Failed to update error status: {status_error}")
                    continue
                
                # Split leads into batches
                batches = split_leads_into_batches(raw_leads, batch_size=10)
                
                # Update status with batch information
                if status_service and upload_id:
                    try:
                        status_service.update_status(
                            upload_id=upload_id,
                            status='processing',
                            stage='batch_processing',
                            progress={
                                'totalBatches': len(batches),
                                'completedBatches': 0,
                                'totalLeads': len(raw_leads),
                                'processedLeads': 0
                            }
                        )
                        logger.info(f"Updated status with batch info: {len(batches)} batches, {len(raw_leads)} leads for upload {upload_id}")
                    except Exception as status_error:
                        logger.warning(f"Failed to update batch status: {status_error}")
                
                # Send each batch to SQS
                message_ids = []
                for i, batch in enumerate(batches, 1):
                    message_id = send_batch_to_sqs(batch, source_file, i, len(batches), upload_id)
                    message_ids.append(message_id)
                
                results.append({
                    'upload_id': upload_id,
                    'file': source_file,
                    'total_leads': len(raw_leads),
                    'batches_sent': len(batches),
                    'message_ids': message_ids[:5]  # Return first 5 message IDs for reference
                })
                
            except Exception as processing_error:
                error_msg = f"Failed to process file: {str(processing_error)}"
                logger.error(error_msg)
                
                # Update status with error if we have upload_id
                if status_service and upload_id:
                    try:
                        status_service.set_error(upload_id, error_msg, 'PROCESSING_ERROR')
                    except Exception as status_error:
                        logger.warning(f"Failed to update error status: {status_error}")
                
                # Re-raise the error to trigger Lambda failure
                raise processing_error
        
        return {
            'statusCode': 200,
            'body': {
                'message': 'Lead splitting completed successfully',
                'results': results
            }
        }
        
    except Exception as e:
        logger.error(f"Lead splitting failed: {str(e)}")
        raise