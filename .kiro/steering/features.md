# Advanced Features Guide

## Multi-Worksheet Excel Processing

### Overview

The Easy CRM system now supports automatic processing of ALL worksheets in Excel files, not just the first one. This feature allows users to upload complex Excel files with multiple data sources and have all worksheets processed automatically.

### Key Features

- **Automatic Worksheet Detection**: Detects and processes all worksheets in Excel files
- **Worksheet Tracking**: Each lead includes a `_worksheet` field indicating its source
- **Field Preservation**: Maintains original field names from each worksheet
- **Empty Sheet Handling**: Gracefully skips empty worksheets
- **Backward Compatibility**: Single-worksheet files continue to work as before

### Technical Implementation

**Lead Splitter Enhancement**:
- Uses pandas `pd.read_excel()` with `sheet_name=None` to read all worksheets
- Iterates through all worksheets and processes each one
- Adds `_worksheet` field to track data source
- Combines all worksheet data into unified batches

**Example Processing**:
```python
# Excel file with multiple worksheets
Sales_Leads.xlsx
├── Sales Team (3 leads)
├── Marketing Contacts (2 leads)
└── Partner Referrals (1 lead)

# Results in 6 total leads with worksheet tracking
[
  {"name": "John Doe", "email": "john@example.com", "_worksheet": "Sales Team"},
  {"name": "Jane Smith", "email": "jane@example.com", "_worksheet": "Marketing Contacts"},
  ...
]
```

### Testing Coverage

**Unit Tests** (`tests/unit/test_excel_multisheet.py`):
- Worksheet detection and enumeration
- Data extraction from multiple worksheets
- Field mapping and normalization
- Error handling for corrupted worksheets

**Integration Tests** (`tests/integration/test_excel_multisheet_integration.py`):
- End-to-end multi-worksheet processing
- Batch creation from multiple worksheets
- DeepSeek processing with worksheet tracking

### Usage Guidelines

1. **File Preparation**: No special preparation needed - upload Excel files as normal
2. **Worksheet Naming**: Use descriptive worksheet names for better tracking
3. **Data Format**: Each worksheet should follow standard lead data format
4. **Empty Worksheets**: Empty worksheets are automatically skipped

## Duplicate Lead Handling

### Overview

The system automatically detects and handles duplicate leads based on email addresses. When duplicates are found, the system overwrites existing leads with the latest data, ensuring the database always contains the most current information.

### Key Features

- **Email-Based Detection**: Uses email addresses as unique identifiers
- **Automatic Overwriting**: Newer lead data overwrites existing entries
- **Batch-Level Processing**: Handles duplicates within uploaded batches
- **Performance Optimized**: Uses EmailIndex GSI for fast lookups
- **Comprehensive Logging**: Detailed tracking of all duplicate actions

### Technical Implementation

**Email Normalization**:
```python
# Email normalization for consistent duplicate detection
"  John.Doe@EXAMPLE.COM  " → "john.doe@example.com"
"" → "N/A"
"N/A" → "N/A"
None → "N/A"
```

**Duplicate Detection Process**:
1. Normalize email addresses in batch
2. Detect duplicates within batch (last occurrence wins)
3. Query existing leads using EmailIndex GSI
4. Perform upsert operations (insert new or update existing)
5. Log all duplicate actions with timestamps

**DynamoDB Operations**:
- **EmailIndex GSI**: Efficient email-based lookups
- **Upsert Logic**: Preserves original `leadId` and `createdAt`
- **Update Tracking**: Updates `updatedAt` and `sourceFile` fields

### Data Integrity

**Preserved Fields**:
- `leadId`: Original lead ID maintained
- `createdAt`: Original creation timestamp preserved

**Updated Fields**:
- `updatedAt`: Set to current timestamp
- `sourceFile`: Updated to latest upload file
- All lead data fields: Completely replaced with new data

### Testing Coverage

**Unit Tests**:
- Email normalization and validation (`test_email_utils.py`)
- Duplicate detection logic (`test_dynamodb_duplicate_utils.py`)
- DynamoDB upsert operations

**Integration Tests**:
- Complete duplicate handling workflow (`test_duplicate_handling_workflow.py`)
- EmailIndex GSI integration (`test_duplicate_detection_integration.py`)
- Batch-level duplicate processing

**E2E Tests**:
- End-to-end duplicate scenarios (`test_duplicate_handling_e2e.py`)
- Performance with high duplicate percentages
- Error recovery and fallback behavior

### Performance Considerations

**Processing Impact**:
- Additional 10-20% processing time for duplicate detection
- EmailIndex GSI queries: ~1-5ms latency per lookup
- Memory overhead: <5% increase for duplicate tracking

**Optimization Strategies**:
- Batch email queries where possible
- In-memory deduplication before database queries
- Caching for recently queried emails

### Error Handling

**Fallback Behavior**:
- EmailIndex GSI unavailable: Fall back to creating new leads
- Duplicate detection timeout: Process as new leads
- Individual lead failures: Continue processing other leads

**Monitoring**:
- CloudWatch metrics for duplicate detection performance
- Structured logging for all duplicate actions
- Dead Letter Queue monitoring for failed operations

## Usage Best Practices

### Multi-Worksheet Excel Files

1. **Organize Data**: Use separate worksheets for different data sources
2. **Consistent Headers**: Use similar field names across worksheets when possible
3. **Descriptive Names**: Name worksheets descriptively for better tracking
4. **Data Quality**: Ensure each worksheet contains valid lead data

### Duplicate Management

1. **Email Quality**: Ensure email addresses are accurate and properly formatted
2. **Data Updates**: Upload newer files to automatically update existing leads
3. **Monitoring**: Review duplicate handling logs to understand data changes
4. **Testing**: Test with sample files before uploading large datasets

### Performance Optimization

1. **Batch Size**: Use appropriate batch sizes for your data volume
2. **File Size**: Consider splitting very large Excel files if processing times are long
3. **Monitoring**: Monitor CloudWatch metrics for performance insights
4. **Cleanup**: Regularly review and clean up old or invalid data

## Troubleshooting

### Multi-Worksheet Issues

**Symptoms**: Not all worksheets processed
**Solutions**:
- Check worksheet names for special characters
- Verify worksheets contain data (empty sheets are skipped)
- Review CloudWatch logs for processing errors

**Symptoms**: Field mapping issues
**Solutions**:
- Ensure consistent field names across worksheets
- Check for merged cells or complex formatting
- Validate data types in each worksheet

### Duplicate Handling Issues

**Symptoms**: Duplicates not detected
**Solutions**:
- Verify email addresses are properly formatted
- Check EmailIndex GSI configuration
- Review email normalization logic

**Symptoms**: Performance degradation
**Solutions**:
- Monitor EmailIndex GSI usage and performance
- Check batch sizes and processing times
- Review duplicate detection metrics

**Symptoms**: Data integrity issues
**Solutions**:
- Verify upsert logic preserves required fields
- Check timestamp handling for created/updated fields
- Review audit logs for duplicate actions

This advanced features guide ensures users can effectively leverage the multi-worksheet Excel processing and duplicate lead handling capabilities while maintaining system performance and data integrity.