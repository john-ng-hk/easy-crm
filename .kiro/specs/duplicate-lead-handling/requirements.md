# Requirements Document

## Introduction

This feature implements duplicate lead detection and handling for the Easy CRM lead management system. The system will use email addresses as the unique identifier to detect duplicate entries and automatically overwrite existing leads with the latest data when duplicates are found during file uploads or batch processing.

## Requirements

### Requirement 1

**User Story:** As a user, I want the system to detect duplicate leads based on email addresses, so that I don't have multiple entries for the same person in my database.

#### Acceptance Criteria

1. WHEN the system processes lead data THEN it SHALL use the email address as the unique identifier for duplicate detection
2. WHEN a lead has an empty or "N/A" email address THEN the system SHALL treat it as a unique lead and always create a new entry
3. WHEN comparing email addresses for duplicates THEN the system SHALL perform case-insensitive matching
4. WHEN comparing email addresses THEN the system SHALL trim whitespace before comparison
5. IF an email address is malformed or invalid THEN the system SHALL still use it for duplicate detection but log a validation warning

### Requirement 2

**User Story:** As a user, I want newer lead data to overwrite older entries when duplicates are found, so that my database always contains the most recent information for each contact.

#### Acceptance Criteria

1. WHEN a duplicate email is detected during batch processing THEN the system SHALL overwrite the existing lead with the new data
2. WHEN overwriting a lead THEN the system SHALL preserve the original `leadId` and `createdAt` timestamp
3. WHEN overwriting a lead THEN the system SHALL update the `updatedAt` timestamp to reflect the modification time
4. WHEN overwriting a lead THEN the system SHALL update the `sourceFile` field to indicate the latest file that provided the data
5. WHEN overwriting a lead THEN the system SHALL replace all field values (firstName, lastName, title, company, phone, remarks) with the new data
6. IF the new lead data has empty or "N/A" values for certain fields THEN the system SHALL still overwrite the existing values (no field-level merging)

### Requirement 3

**User Story:** As a user, I want to see clear logging and tracking of duplicate handling, so that I can understand what happened to my data during processing.

#### Acceptance Criteria

1. WHEN a duplicate is detected and overwritten THEN the system SHALL log the action with both the original and new lead data
2. WHEN logging duplicate actions THEN the system SHALL include the email address, original leadId, source files (old and new), and timestamp
3. WHEN batch processing completes THEN the system SHALL include duplicate handling statistics in the processing summary
4. WHEN duplicate handling occurs THEN the system SHALL track metrics including: total duplicates found, leads overwritten, and processing time impact
5. IF duplicate detection fails due to system errors THEN the system SHALL log the error and fall back to creating a new lead entry

### Requirement 4

**User Story:** As a system administrator, I want duplicate handling to be efficient and not significantly impact processing performance, so that large file uploads remain fast and reliable.

#### Acceptance Criteria

1. WHEN checking for duplicates THEN the system SHALL use the existing EmailIndex GSI for efficient email-based lookups
2. WHEN processing batches THEN the system SHALL perform duplicate checks in batch operations where possible to minimize DynamoDB calls
3. WHEN duplicate detection adds processing time THEN it SHALL not increase total batch processing time by more than 20%
4. WHEN the EmailIndex is unavailable or fails THEN the system SHALL fall back to creating new leads and log the issue
5. WHEN processing large batches THEN the duplicate detection SHALL not cause Lambda function timeouts

### Requirement 5

**User Story:** As a user, I want duplicate handling to work seamlessly with the existing batch processing architecture, so that my file uploads continue to work reliably with the new duplicate detection feature.

#### Acceptance Criteria

1. WHEN the DeepSeek Caller processes a batch THEN it SHALL check for duplicates before storing leads in DynamoDB
2. WHEN duplicate checking is performed THEN it SHALL happen after DeepSeek standardization but before DynamoDB storage
3. WHEN a batch contains multiple leads with the same email THEN the system SHALL use the last occurrence in the batch as the final data
4. WHEN duplicate handling fails for individual leads THEN it SHALL not prevent processing of other leads in the same batch
5. WHEN SQS retry occurs due to duplicate handling errors THEN the system SHALL handle idempotency to prevent data corruption

### Requirement 6

**User Story:** As a user, I want the frontend lead display to reflect the duplicate handling behavior, so that I can see the most current data and understand when leads have been updated.

#### Acceptance Criteria

1. WHEN viewing leads in the frontend table THEN the system SHALL display the most recent data for each unique email address
2. WHEN a lead has been updated due to duplicate handling THEN the `updatedAt` timestamp SHALL reflect the latest modification
3. WHEN exporting leads THEN the CSV SHALL contain only the most recent version of each lead (no duplicates)
4. WHEN searching or filtering leads THEN the system SHALL work with the deduplicated dataset
5. WHEN displaying lead details THEN the system SHALL show the `sourceFile` field indicating which file provided the current data

### Requirement 7

**User Story:** As a developer, I want comprehensive testing for duplicate handling functionality, so that the feature works reliably across different scenarios and edge cases.

#### Acceptance Criteria

1. WHEN testing duplicate handling THEN the system SHALL include unit tests for email comparison logic
2. WHEN testing batch processing THEN the system SHALL include integration tests with duplicate scenarios
3. WHEN testing edge cases THEN the system SHALL handle scenarios like: empty emails, malformed emails, case variations, and whitespace differences
4. WHEN testing performance THEN the system SHALL verify that duplicate detection doesn't cause significant processing delays
5. WHEN testing error scenarios THEN the system SHALL verify graceful fallback behavior when duplicate detection fails