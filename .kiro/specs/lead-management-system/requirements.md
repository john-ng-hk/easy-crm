# Requirements Document

## Introduction

This feature implements a web-based lead management system that allows users to upload CSV/Excel files containing lead data in various formats. The system uses DeepSeek AI to standardize the data format and provides a web interface for viewing, filtering, and exporting leads with natural language chat capabilities for data insights.

## Requirements

### Requirement 1

**User Story:** As a user, I want to upload CSV/Excel files with lead data, so that I can import leads into the system regardless of their original format.

#### Acceptance Criteria

1. WHEN a user accesses the upload interface THEN the system SHALL provide a file upload component that accepts CSV and Excel files
2. WHEN a user selects a file for upload THEN the system SHALL generate a presigned S3 URL for secure file upload
3. WHEN a file is successfully uploaded to S3 THEN the system SHALL trigger the lead splitter function automatically
4. IF the uploaded file is not CSV or Excel format THEN the system SHALL display an error message and reject the upload
5. WHEN the file upload is in progress THEN the system SHALL display upload progress to the user

### Requirement 2

**User Story:** As a user, I want the system to automatically standardize my uploaded lead data, so that all leads follow a consistent format regardless of the original file structure.

#### Acceptance Criteria

1. WHEN a file is uploaded to S3 THEN the system SHALL automatically trigger the lead splitter Lambda function
2. WHEN the lead splitter function processes a file THEN it SHALL split leads into batches and send them to SQS queue for processing
3. WHEN DeepSeek AI processes the lead data THEN it SHALL return standardized JSON with fields: firstName, lastName, title, company, email, phone, remarks
4. IF any standard field is missing from the original data THEN the system SHALL populate it with "N/A"
5. WHEN data doesn't fit standard fields THEN the system SHALL store it in the "remarks" attribute
6. WHEN formatting is complete THEN the system SHALL store the standardized leads in DynamoDB with unique leadId keys
7. IF the DeepSeek API call fails THEN the system SHALL retry up to 1 time before marking the file as failed

### Requirement 3

**User Story:** As a user, I want to view all my leads in a tabular format with filtering capabilities, so that I can easily find and manage specific leads.

#### Acceptance Criteria

1. WHEN a user accesses the leads page THEN the system SHALL display all leads in a paginated table format
2. WHEN the leads table loads THEN it SHALL show columns for firstName, lastName, title, company, email, phone, and remarks
3. WHEN a user wants to filter leads THEN the system SHALL provide filter controls for each column
4. WHEN a user applies filters THEN the system SHALL update the table to show only matching leads
5. WHEN a user wants to sort leads THEN the system SHALL allow sorting by any column in ascending or descending order
6. WHEN there are more than 50 leads THEN the system SHALL implement pagination with configurable page sizes
7. WHEN a user clicks on a lead row THEN the system SHALL display detailed lead information including the remarks field

### Requirement 4

**User Story:** As a user, I want to chat with an AI assistant about my lead data, so that I can get insights and answers using natural language queries.

#### Acceptance Criteria

1. WHEN a user accesses the leads page THEN the system SHALL display a chat interface alongside the leads table
2. WHEN a user types a natural language query about leads THEN the system SHALL send the query to the chatbot Lambda function
3. WHEN the chatbot function receives a query THEN it SHALL send the query to DeepSeek AI to generate appropriate DynamoDB queries
4. WHEN DeepSeek returns a query THEN the chatbot function SHALL execute it against DynamoDB and return results
5. WHEN the chatbot has results THEN it SHALL format them in a user-friendly response and display in the chat
6. IF a query cannot be understood THEN the system SHALL ask the user to rephrase their question
7. WHEN providing results THEN the system SHALL NOT send raw lead data to DeepSeek, only query structures

### Requirement 5

**User Story:** As a user, I want to export filtered lead data as CSV, so that I can use the data in other systems or share it with colleagues.

#### Acceptance Criteria

1. WHEN a user has applied filters to the leads table THEN the system SHALL provide an export button
2. WHEN a user clicks the export button THEN the system SHALL generate a CSV file containing only the leads that match the currently applied filters
3. WHEN no filters are applied THEN the export SHALL include all leads in the system
4. WHEN filters are applied THEN the export SHALL use the exact same filtering logic as the leads table display to ensure consistency
5. WHEN generating the export THEN the system SHALL include all standard fields: leadId, firstName, lastName, title, company, email, phone, remarks, sourceFile, createdAt, updatedAt
6. WHEN the export is ready THEN the system SHALL automatically download the CSV file to the user's device with a timestamp-based filename
7. IF no leads match the current filters THEN the system SHALL display a message indicating no data to export and not generate a file
8. WHEN exporting large datasets THEN the system SHALL show progress indication during file generation
9. WHEN the export request is sent THEN the system SHALL pass the current filter state from the frontend to the backend to ensure filter-aware export functionality

### Requirement 6

**User Story:** As a user, I want secure access to the system, so that my lead data is protected and only authorized users can access it.

#### Acceptance Criteria

1. WHEN a user accesses the application THEN the system SHALL require authentication via AWS Cognito
2. WHEN a user is not authenticated THEN the system SHALL redirect them to the Cognito login page
3. WHEN a user successfully authenticates THEN the system SHALL grant access to the lead management interface
4. WHEN making API calls THEN the system SHALL validate the user's JWT token for authorization
5. WHEN a user's session expires THEN the system SHALL automatically redirect to login
6. WHEN a user logs out THEN the system SHALL clear all session data and redirect to login

### Requirement 7

**User Story:** As a system administrator, I want the application deployed on AWS with proper SSL and CDN, so that it performs well and is secure for users.

#### Acceptance Criteria

1. WHEN the application is deployed THEN it SHALL be hosted on S3 as a static website
2. WHEN users access the application THEN it SHALL be served through CloudFront CDN for optimal performance
3. WHEN HTTPS requests are made THEN the system SHALL use the provided ACM certificate for SSL termination
4. WHEN API requests are made THEN they SHALL go through API Gateway with proper CORS configuration
5. WHEN Lambda functions are invoked THEN they SHALL have appropriate IAM roles and permissions
6. WHEN DynamoDB is accessed THEN it SHALL have proper read/write capacity configured for expected load
7. WHEN DynamoDB is accessed THEN it SHALL be configured with appropriate indexes for efficient querying