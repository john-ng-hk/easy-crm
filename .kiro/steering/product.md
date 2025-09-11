# Product Overview

## Easy CRM - Lead Management System

A serverless web application that enables users to upload CSV/Excel files containing lead data in various formats. The system automatically standardizes the data using DeepSeek AI and provides a web interface for viewing, filtering, exporting, and querying leads through natural language chat.

## Key Features

- **File Upload & Processing**: Drag-and-drop CSV/Excel upload with automatic format standardization via batch processing
- **Multi-Worksheet Excel Support**: Automatically processes ALL worksheets in Excel files with worksheet tracking
- **Duplicate Lead Handling**: Automatic detection and handling of duplicate leads based on email addresses
- **Lead Management**: Sortable, filterable table view with pagination for lead data including phone field support
- **Phone Field Integration**: Complete phone number support with validation, formatting, and clickable tel: links
- **Natural Language Chat**: AI-powered chat interface for querying lead data using plain English
- **Data Export**: CSV export functionality with filter-aware data selection including phone fields
- **Batch Processing**: Scalable file processing architecture using SQS queues for large files
- **Secure Access**: AWS Cognito authentication with JWT token validation

## Target Users

Business users who need to import, manage, and analyze lead data from various sources without technical expertise in data formatting or database queries.

## Business Value

Eliminates manual data cleaning and standardization work, provides intuitive data access through natural language, enables quick insights from lead data regardless of original format, and includes comprehensive phone number management for improved lead contact capabilities. The multi-worksheet Excel support allows processing complex spreadsheets with multiple data sources in a single upload. Automatic duplicate detection ensures data integrity and prevents duplicate entries, while the batch processing architecture ensures reliable handling of large datasets while maintaining cost efficiency.

## Infrastructure Overview

The system is built on AWS serverless architecture for scalability, cost-effectiveness, and minimal operational overhead:

- **Serverless Computing**: Lambda functions handle all business logic without server management
- **Managed Database**: DynamoDB provides fast, scalable NoSQL storage with automatic scaling
- **Global CDN**: CloudFront ensures fast loading times worldwide with SSL termination
- **Secure Authentication**: Cognito handles user management with JWT token validation
- **Cost Optimization**: Pay-per-use pricing model with automatic scaling based on demand

## Deployment Model

- **Infrastructure as Code**: Complete infrastructure defined in CloudFormation templates
- **Automated Deployment**: Scripts handle the entire deployment process with parameter prompts
- **Environment Separation**: Support for dev/staging/prod environments with isolated resources
- **Zero Downtime Updates**: Lambda functions can be updated without service interruption