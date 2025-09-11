# Implementation Plan

- [x] 1. Set up development environment and project structure
  - Create Python virtual environment and activate it
  - Create project directory structure for Lambda functions, frontend, and infrastructure
  - Create requirements.txt with necessary Python dependencies
  - _Requirements: 7.1, 7.2_

- [x] 2. Implement core data models and utilities
  - Create shared Python modules for DynamoDB operations
  - Implement lead data validation and transformation utilities
  - Create error handling and logging utilities for Lambda functions
  - _Requirements: 2.3, 2.4, 2.5_

- [x] 3. Implement File Upload Lambda function
  - Create file-upload-lambda with presigned S3 URL generation
  - Implement file type validation (CSV/Excel only)
  - Add error handling for invalid requests and S3 failures
  - Write unit tests for presigned URL generation and validation
  - _Requirements: 1.1, 1.2, 1.4_

- [x] 4. Implement Lead Splitter and DeepSeek Caller Lambda functions
  - Create lead-splitter-lambda with S3 trigger configuration
  - Create deepseek-caller-lambda with SQS trigger configuration
  - Implement CSV/Excel file parsing functionality
  - Integrate DeepSeek API client for data standardization
  - Implement DynamoDB batch write operations for processed leads
  - Add error handling with single retry for DeepSeek API failures
  - Write unit tests with mock DeepSeek responses and actual API integration tests
  - _Requirements: 2.1, 2.2, 2.3, 2.6, 2.7_

- [x] 5. Implement Lead Reader Lambda function
  - Create lead-reader-lambda with pagination support
  - Implement DynamoDB query operations with filtering capabilities
  - Add sorting functionality for all lead fields
  - Implement response formatting with proper pagination metadata
  - Write unit tests for filtering, sorting, and pagination logic
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 6. Implement Lead Exporter Lambda function
  - Create lead-exporter-lambda for CSV generation
  - Implement filtered data retrieval using same logic as lead reader
  - Add CSV formatting and base64 encoding for file download
  - Implement error handling for large dataset exports
  - Write unit tests for CSV generation and filtering integration
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 7. Implement Chatbot Lambda function
  - Create chatbot-lambda with DeepSeek integration for NLP
  - Implement query parsing and DynamoDB query generation
  - Add result formatting for user-friendly chat responses
  - Implement security measures to prevent data leakage to DeepSeek
  - Write unit tests for query parsing and response formatting
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [x] 8. Create CloudFormation infrastructure templates
  - Create main CloudFormation template with parameters and outputs
  - Implement nested template for DynamoDB table with GSIs
  - Create S3 buckets template with proper lifecycle policies
  - Implement Lambda functions template with IAM roles and permissions (no VPC configuration)
  - Create API Gateway template with CORS and authentication
  - Implement Cognito template for user pool and identity pool
  - Create CloudFront template with SSL certificate integration
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 7.3, 7.4, 7.5, 7.6_

- [x] 9. Implement frontend web application
  - Create HTML structure with file upload, leads table, and chat interface
  - Implement CSS styling using Tailwind for responsive design
  - Create JavaScript modules for API communication and authentication
  - Implement file upload functionality with progress indication
  - Add leads table with sorting, filtering, and pagination
  - Create chat interface for natural language queries
  - Implement export functionality with filter awareness
  - _Requirements: 1.1, 1.5, 3.1, 3.2, 3.3, 3.4, 3.7, 4.1, 4.5, 5.1, 5.4, 6.1, 6.2, 6.3_

- [x] 10. Implement Cognito authentication integration
  - Configure AWS Cognito SDK in frontend JavaScript
  - Implement login/logout functionality with JWT token handling
  - Add authentication guards for protected API calls
  - Implement session management and automatic token refresh
  - Write integration tests for authentication flow
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 11. Create deployment scripts and configuration
  - Create deployment script using AWS CLI with nch-prod profile
  - Implement CloudFormation parameter configuration
  - Add deployment validation and smoke tests
  - Create environment-specific configuration files
  - Document deployment process and troubleshooting steps
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [x] 12. Implement comprehensive testing suite
  - Create unit tests for all Lambda functions using pytest
  - Implement integration tests for API Gateway endpoints
  - Add end-to-end tests using the easy-crm-test file
  - Create DeepSeek API integration tests with actual API calls
  - Implement performance tests for file processing and database operations
  - Add security tests for authentication and input validation
  - _Requirements: 1.4, 2.7, 3.6, 4.6, 5.5, 6.4, 6.5_

- [x] 13. Integrate and test complete system workflow
  - Deploy infrastructure using CloudFormation templates
  - Test complete file upload to lead display workflow
  - Validate DeepSeek integration with test data files
  - Test chat functionality with various natural language queries
  - Verify export functionality with different filter combinations
  - Perform user acceptance testing with multiple file formats
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 3.1, 4.1, 5.1, 6.1, 7.1_

## Phone Field Enhancement Tasks

- [x] 14. Update DeepSeek Caller Lambda to include phone field
  - Modify DeepSeek API prompt to request phone field in standardized output
  - Update lead data processing to handle phone field from DeepSeek response
  - Modify DynamoDB write operations to include phone attribute
  - Update validation logic to handle phone field (allow "N/A" for missing values)
  - Write unit tests for phone field processing and validation
  - _Requirements: 2.3_

- [x] 15. Update Lead Reader Lambda to support phone field filtering
  - Add phone field to DynamoDB query filter capabilities
  - Update response formatting to include phone field in lead objects
  - Modify sorting functionality to support phone field sorting
  - Update pagination logic to handle phone field in query operations
  - Write unit tests for phone field filtering and sorting
  - _Requirements: 3.2, 3.4, 3.5_

- [x] 16. Update Lead Exporter Lambda to include phone field
  - Modify CSV header generation to include phone column
  - Update lead data retrieval to include phone field in export data
  - Ensure phone field is properly formatted in CSV output
  - Update export filtering to support phone field filters
  - Write unit tests for phone field in CSV export functionality
  - _Requirements: 5.2, 5.3_

- [x] 17. Update Chatbot Lambda to handle phone field queries
  - Modify DeepSeek prompt to understand phone-related natural language queries
  - Update query generation logic to create phone field filters
  - Add phone field to result formatting and response generation
  - Ensure phone field data is not sent to DeepSeek (only query structures)
  - Write unit tests for phone field query parsing and response formatting
  - _Requirements: 4.2, 4.3, 4.4, 4.7_

- [x] 18. Update frontend to display and filter by phone field
  - Add phone column to leads table display
  - Implement phone field filter input in filter controls
  - Update table sorting to include phone field option
  - Modify lead detail view to show phone information
  - Update export functionality to include phone field in downloaded CSV
  - Ensure responsive design accommodates additional phone column
  - _Requirements: 3.2, 3.3, 3.4, 3.7, 5.4_

- [x] 19. Update validation and shared utilities for phone field
  - Add phone field validation to shared validation utilities
  - Update DynamoDB utility functions to handle phone field operations
  - Modify error handling to include phone field validation errors
  - Update data transformation utilities for phone field processing
  - Write unit tests for phone field validation and utility functions
  - _Requirements: 2.4, 2.5_

- [x] 20. Test phone field integration end-to-end
  - Test file upload with phone data using updated DeepSeek processing
  - Verify phone field appears correctly in leads table display
  - Test phone field filtering and sorting functionality
  - Validate phone field inclusion in CSV export
  - Test natural language queries involving phone field through chatbot
  - Perform regression testing to ensure existing functionality still works
  - _Requirements: 1.3, 2.1, 3.1, 4.1, 5.1_

## Filter-Aware Export Bug Fix

- [x] 21. Fix filter-aware export functionality
  - Identify and fix the mismatch between frontend filter passing (POST body) and backend filter parsing (query parameters)
  - Update Lead Exporter Lambda to correctly parse filters from POST request body instead of query parameters
  - Ensure the export function uses the exact same filtering logic as the Lead Reader Lambda for consistency
  - Test that exported CSV contains only the leads that match the currently applied filters in the frontend table
  - Verify that when no filters are applied, the export includes all leads
  - Write unit tests to validate filter parsing from POST body and integration tests for filter-aware export
  - _Requirements: 5.2, 5.4, 5.9_

