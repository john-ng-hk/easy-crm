# Implementation Plan

- [x] 1. Create email normalization utility module
  - Create `lambda/shared/email_utils.py` with EmailNormalizer class
  - Implement `normalize_email()` method with case-insensitive, whitespace trimming logic
  - Implement `is_valid_email_format()` method with regex validation
  - Add comprehensive unit tests for email normalization edge cases
  - _Requirements: 1.3, 1.4, 1.5_

- [x] 2. Enhance DynamoDB utilities with duplicate detection methods
  - Add `find_lead_by_email()` method to `lambda/shared/dynamodb_utils.py`
  - Implement EmailIndex GSI query logic with error handling
  - Add `upsert_lead()` method for single lead insert/update operations
  - Add `batch_upsert_leads()` method for batch operations with duplicate handling
  - Include comprehensive error handling for GSI unavailability and DynamoDB failures
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.1, 4.4_

- [x] 3. Implement batch-level duplicate detection logic
  - Create duplicate detection function in `lambda/shared/dynamodb_utils.py`
  - Implement within-batch duplicate resolution (last occurrence wins)
  - Add duplicate action logging structure and methods
  - Create performance tracking for duplicate detection operations
  - _Requirements: 2.6, 3.1, 3.2, 4.3_

- [x] 4. Update DeepSeek Caller Lambda with duplicate handling
  - Modify `lambda/deepseek-caller/lambda_function.py` to use new upsert methods
  - Replace `batch_create_leads()` calls with `batch_upsert_leads()`
  - Add duplicate detection step after DeepSeek standardization
  - Implement comprehensive logging for duplicate actions and statistics
  - Add error handling fallbacks for duplicate detection failures
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 3.3, 3.4_

- [x] 5. Create comprehensive unit tests for email utilities
  - Write tests for `EmailNormalizer.normalize_email()` with various input formats
  - Test case sensitivity, whitespace handling, and empty value scenarios
  - Test email format validation with valid and invalid email patterns
  - Create test cases for edge cases like null values and special characters
  - _Requirements: 7.1, 7.3_

- [x] 6. Create unit tests for enhanced DynamoDB utilities
  - Write tests for `find_lead_by_email()` with mocked DynamoDB responses
  - Test `upsert_lead()` for both new lead creation and existing lead updates
  - Test `batch_upsert_leads()` with mixed new and duplicate leads
  - Create tests for error scenarios (GSI unavailable, DynamoDB failures)
  - Test duplicate detection logic with various batch compositions
  - _Requirements: 7.1, 7.4_

- [x] 7. Create integration tests for duplicate handling workflow
  - Write end-to-end test for file upload with duplicate emails
  - Test batch processing with duplicate detection enabled
  - Verify that existing leads are updated and new leads are created appropriately
  - Test performance impact measurement and verify it's within acceptable limits
  - Create tests for SQS retry scenarios with duplicate handling
  - _Requirements: 7.2, 7.4, 5.5_

- [x] 8. Update deployment configuration for EmailIndex GSI
  - Verify EmailIndex GSI exists in `infrastructure/storage.yaml`
  - Ensure proper IAM permissions for EmailIndex queries in Lambda roles
  - Update environment variables if needed for duplicate handling configuration
  - Test deployment with enhanced Lambda functions
  - _Requirements: 4.1, 4.4_

- [x] 9. Create comprehensive end-to-end tests
  - Test complete workflow: file upload → duplicate detection → lead storage → frontend display
  - Verify frontend shows deduplicated leads with correct timestamps
  - Test CSV export functionality with deduplicated data
  - Create performance tests with large batches containing high duplicate percentages
  - Test error recovery scenarios and fallback behavior
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.2, 7.5_

- [x] 10. Update documentation and add deployment validation
  - Update README and technical documentation with duplicate handling information
  - Add duplicate handling section to batch processing architecture documentation
  - Create deployment validation script to test duplicate handling functionality
  - Update smoke tests to include duplicate detection verification
  - _Requirements: 3.1, 3.2_