# Easy CRM - Lead Management System

A serverless web application that enables users to upload CSV/Excel files containing lead data in various formats. The system automatically standardizes the data using DeepSeek AI and provides a web interface for viewing, filtering, exporting, and querying leads through natural language chat.

## 🔐 Security Notice

This repository has been sanitized for public release. All sensitive information including API keys, production URLs, and AWS account details have been removed or replaced with placeholders. See [SECURITY_CHECKLIST.md](SECURITY_CHECKLIST.md) for details.

## 🚀 Quick Start

### Prerequisites
- AWS CLI configured with appropriate permissions
- DeepSeek API key
- ACM certificate (for custom domain)

### Setup
1. **Clone and configure:**
   ```bash
   git clone <repository-url>
   cd easy-crm
   cp frontend/config.json.example frontend/config.json
   # Edit frontend/config.json with your values
   ```

2. **Set environment variables:**
   ```bash
   export DEEPSEEK_API_KEY="your-deepseek-api-key"
   export CERTIFICATE_ARN="your-acm-certificate-arn"
   ```

3. **Deploy:**
   ```bash
   ./scripts/deploy.sh
   ```

## Key Features

- **File Upload & Processing**: Drag-and-drop CSV/Excel upload with automatic format standardization
- **Real-Time Processing Status**: Live status indicator showing upload and processing progress with cancellation support
- **Multi-Worksheet Excel Support**: Automatically processes ALL worksheets in Excel files (not just the first one)
- **Duplicate Lead Handling**: Automatic detection and handling of duplicate leads based on email addresses
- **Lead Management**: Sortable, filterable table view with pagination for lead data
- **Phone Field Integration**: Complete phone number support with validation, formatting, and clickable tel: links
- **Natural Language Chat**: AI-powered chat interface for querying lead data using plain English
- **Data Export**: CSV export functionality with filter-aware data selection
- **Batch Processing**: Scalable file processing architecture using SQS queues for large files
- **Secure Access**: AWS Cognito authentication with JWT token validation

## Recent Updates

### Pagination Fix ✅
- **Fixed Table Pagination**: Lead table pagination now works correctly when clicking Next/Previous buttons
- **Page-Based Implementation**: Backend now uses proper page-based pagination instead of token-based
- **Consistent Performance**: Pagination works reliably across all dataset sizes with 134 leads across 27 pages
- **Enhanced Debugging**: Added comprehensive debug logging for troubleshooting pagination issues

### Multi-Worksheet Excel Processing ✅
- **Enhanced Excel Support**: Now processes ALL worksheets in Excel files automatically
- **Worksheet Tracking**: Each lead includes a `_worksheet` field to track its source
- **Field Preservation**: Maintains original field names from each worksheet
- **Empty Sheet Handling**: Gracefully skips empty worksheets
- **Backward Compatibility**: Single-worksheet files continue to work as before

### Duplicate Lead Handling ✅
- **Email-Based Detection**: Uses email addresses as unique identifiers for duplicate detection
- **Automatic Overwriting**: Newer lead data automatically overwrites existing entries
- **Batch-Level Processing**: Handles duplicates within uploaded batches efficiently
- **Performance Optimized**: Uses EmailIndex GSI for fast duplicate lookups
- **Comprehensive Logging**: Detailed tracking of all duplicate handling actions

### Processing Status Indicator ✅
- **Real-Time Status Updates**: Live progress tracking during file upload and processing
- **Multi-Batch Support**: Progress indicators work correctly for files split into multiple batches
- **Visual Progress Bar**: Shows batch processing progress with estimated completion time
- **Processing Cancellation**: Users can cancel long-running operations
- **Automatic Lead Table Refresh**: Table updates automatically when processing completes
- **Error State Handling**: Clear error messages with recovery options
- **Cost Optimization**: Polling reduced to 10-second intervals with 5-minute timeout to control API costs

### Architecture Improvements ✅
- **Batch Processing**: SQS-based architecture for improved scalability and reliability
- **AWS Pandas Layer**: Eliminates numpy conflicts for Excel processing
- **Dead Letter Queue**: Handles failed message processing
- **Type Safety**: Fixed DynamoDB boolean value validation errors for progress updates
- **Cost Controls**: Implemented smart polling with automatic timeout to prevent high API costs
- **Status Tracking System**: DynamoDB-based status persistence with TTL auto-expiration
- **Comprehensive Testing**: 31+ tests covering all functionality including status tracking

## Technology Stack

- **Backend**: Python 3.13, AWS Lambda, DynamoDB, S3, SQS
- **Frontend**: Vanilla HTML5, CSS, JavaScript with Tailwind CSS
- **Infrastructure**: CloudFormation nested stacks
- **AI Integration**: DeepSeek AI API for data standardization
- **Authentication**: AWS Cognito (User Pool + Identity Pool)
- **CDN**: CloudFront with SSL certificate

## Quick Start

### Prerequisites
- AWS CLI configured with `nch-prod` profile
- Python 3.13 with virtual environment
- DeepSeek API key

### Deployment
```bash
# Deploy infrastructure
./scripts/deploy.sh

# Deploy Lambda functions
./scripts/package-lambdas.sh

# Deploy frontend
./scripts/deploy-frontend.sh

# Validate deployment
./scripts/validate-deployment.sh
```

### Testing
```bash
# Run all tests
python -m pytest tests/ -v

# Test multi-worksheet functionality
python -m pytest tests/unit/test_excel_multisheet.py -v

# Run comprehensive test suite
python tests/run_comprehensive_tests.py
```

## File Processing Capabilities

### Supported Formats
- **CSV files**: All standard CSV formats with various encodings
- **Excel files**: .xlsx and .xls formats with multi-worksheet support

### Multi-Worksheet Processing
When you upload an Excel file with multiple worksheets:
1. **All worksheets are processed** automatically
2. **Each lead gets a `_worksheet` field** indicating its source
3. **Original field names are preserved** from each worksheet
4. **Empty worksheets are skipped** gracefully
5. **Data is combined** into a single batch for processing

### Example Multi-Worksheet File
```
Sales_Leads.xlsx
├── Sales Team (3 leads)
│   ├── Full Name, Email, Phone Number, Company Name
├── Marketing Contacts (2 leads)
│   ├── Name, Work Email, Mobile, Organization
└── Partner Referrals (1 lead)
    ├── Contact Name, Email Address, Phone, Company
```

Results in 6 total leads, each with a `_worksheet` field indicating the source.

## Architecture

### Batch Processing Workflow
```
Excel Upload → Lead Splitter → SQS Queue → DeepSeek Caller → Duplicate Detection → DynamoDB
     ↓              ↓              ↓              ↓                    ↓
Multi-Worksheet  Batch Creation  Message Queue  AI Processing    Email-Based
  Processing                                                      Deduplication
     ↓              ↓              ↓              ↓                    ↓
Status: Upload  Status: Process  Status: Queue  Status: AI Proc   Status: Complete
```

### Processing Status Tracking
```
Frontend Polling ← Status API ← DynamoDB Status Table
     ↓                 ↓              ↓
Progress Display   Authentication   TTL Auto-Expire
Cancel Button      Rate Limiting    Error Recovery
```

### Duplicate Handling Process
1. **Email Normalization**: Converts emails to lowercase and trims whitespace
2. **Batch-Level Detection**: Identifies duplicates within the same batch (last occurrence wins)
3. **Database Lookup**: Queries existing leads using EmailIndex GSI
4. **Upsert Operations**: Creates new leads or updates existing ones
5. **Audit Logging**: Records all duplicate handling actions with timestamps

### Lambda Functions
- **File Upload**: Generates presigned S3 URLs and creates initial status records
- **Lead Splitter**: Processes files and creates batches (supports multi-worksheet) with status updates
- **DeepSeek Caller**: AI-powered data standardization with batch progress tracking
- **Lead Reader**: Retrieval with filtering and pagination
- **Lead Exporter**: CSV export functionality
- **Status Reader**: Real-time status polling with authentication
- **Chatbot**: Natural language query processing

## Current Status

✅ **Infrastructure**: Fully deployed and operational
✅ **Lambda Functions**: All 6 functions deployed with batch processing
✅ **Frontend**: Working authentication, lead management, and phone field support
✅ **Multi-Worksheet Support**: Complete Excel multi-worksheet processing
✅ **Testing Suite**: Comprehensive unit, integration, and E2E tests (36+ tests passing)
✅ **Documentation**: Updated with all recent improvements

## Documentation

### User Guides
- **[Processing Status Guide](docs/processing-status-guide.md)**: Complete user guide for the real-time status indicator
- **[Authentication Guide](docs/authentication.md)**: User authentication and security documentation

### Technical Documentation
- **[Status API Documentation](docs/status-api-documentation.md)**: Complete API reference for status endpoints
- **[Batch Processing Architecture](docs/batch-processing-architecture.md)**: Technical guide to the batch processing system
- **[Infrastructure Guide](infrastructure/README.md)**: CloudFormation templates and deployment architecture
- **[Deployment Guide](docs/deployment-guide.md)**: Comprehensive deployment instructions

### Validation and Testing
- **[Processing Status Final Validation](docs/processing-status-final-validation.md)**: Complete feature validation report
- **[Deployment Troubleshooting](docs/deployment-troubleshooting.md)**: Common issues and solutions

### Recent Fixes and Updates
- **[Status Tracking Fix Summary](STATUS_TRACKING_FIX_SUMMARY.md)**: Upload ID mismatch resolution (December 2025)
- **[Progress Indicator Fixes Summary](PROGRESS_INDICATOR_FIXES_SUMMARY.md)**: Multi-batch progress and cost optimization fixes (January 2025)

## Contributing

1. Follow the testing guidelines in `.kiro/steering/testing.md`
2. Use the batch processing architecture documented in `.kiro/steering/batch-processing.md`
3. Maintain phone field support across all components
4. Test multi-worksheet functionality with various Excel file formats
5. Ensure status tracking integration for new features

## License

See LICENSE file for details.

