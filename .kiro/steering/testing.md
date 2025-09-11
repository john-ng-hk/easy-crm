# Testing Guidelines

## Testing Philosophy

The Easy CRM project follows a comprehensive testing strategy with multiple layers of validation to ensure reliability, functionality, and performance across all components.

## Test Categories

### 1. Unit Tests (`tests/unit/`)

**Purpose**: Test individual functions and components in isolation

**Coverage Areas**:
- Lambda function logic
- Shared utilities (DynamoDB, validation, error handling)
- Phone field validation and processing
- Authentication mechanisms
- Data transformation functions

**Key Test Files**:
- `test_validation_phone.py` - Phone number validation (6 tests)
- `test_dynamodb_phone_utils.py` - DynamoDB phone operations (6 tests)
- `test_error_handling_phone.py` - Phone error handling (3 tests)
- `test_excel_multisheet.py` - Multi-worksheet Excel processing tests
- `test_email_utils.py` - Email normalization and validation tests
- `test_dynamodb_duplicate_utils.py` - Duplicate detection utilities tests
- `test_file_upload.py` - File upload functionality
- `test_lead_reader.py` - Lead retrieval logic
- `test_lead_exporter.py` - CSV export functionality
- `test_chatbot.py` - Natural language processing
- `test_auth.py` - Authentication logic

**Running Unit Tests**:
```bash
# All unit tests
python -m pytest tests/unit/ -v

# Phone field specific tests
python -m pytest tests/unit/test_*phone* -v

# Multi-worksheet Excel tests
python -m pytest tests/unit/test_excel_multisheet.py -v

# Email utilities tests
python -m pytest tests/unit/test_email_utils.py -v

# Duplicate handling utilities tests
python -m pytest tests/unit/test_dynamodb_duplicate_utils.py -v

# Specific test file
python -m pytest tests/unit/test_validation_phone.py -v
```

### 2. Integration Tests (`tests/integration/`)

**Purpose**: Test component interactions and API integrations

**Coverage Areas**:
- Lambda function integrations
- AWS service interactions
- DeepSeek API integration
- Cognito authentication flow
- Phone field integration across components

**Key Test Files**:
- `test_phone_field_integration.py` - Phone field integration (4 tests)
- `test_excel_multisheet_integration.py` - Multi-worksheet Excel integration tests
- `test_duplicate_handling_workflow.py` - Duplicate handling workflow integration
- `test_duplicate_detection_integration.py` - Duplicate detection integration tests
- `test_file_upload_integration.py` - S3 upload integration
- `test_lead_reader_integration.py` - DynamoDB query integration
- `test_deepseek_api_integration.py` - DeepSeek API integration
- `test_cognito_authentication.py` - Authentication integration

**Running Integration Tests**:
```bash
# All integration tests
python -m pytest tests/integration/ -v

# Phone field integration
python -m pytest tests/integration/test_phone_field_integration.py -v

# Multi-worksheet Excel integration
python -m pytest tests/integration/test_excel_multisheet_integration.py -v

# Duplicate handling integration
python -m pytest tests/integration/test_duplicate_handling_workflow.py -v
```

### 3. End-to-End Tests (`tests/e2e/`)

**Purpose**: Test complete user workflows and system functionality

**Coverage Areas**:
- Complete file upload and processing workflow
- Phone field end-to-end functionality
- User authentication flows
- Data export workflows

**Key Test Files**:
- `test_phone_field_final_report.py` - Comprehensive phone field E2E test
- `test_duplicate_handling_e2e.py` - Comprehensive duplicate handling E2E tests
- `test_complete_workflow.py` - Full system workflow test
- `test_phone_field_e2e.py` - Phone field specific E2E tests
- `test_progress_update_fix.py` - Progress indicator fixes validation (integration level)

**Running E2E Tests**:
```bash
# All E2E tests
python -m pytest tests/e2e/ -v

# Phone field E2E comprehensive test
python -m pytest tests/e2e/test_phone_field_final_report.py -v -s

# Duplicate handling E2E tests
python -m pytest tests/e2e/test_duplicate_handling_e2e.py -v -s

# Run comprehensive duplicate handling E2E suite
python tests/run_duplicate_handling_e2e_tests.py

# Test progress indicator fixes
python -m pytest tests/integration/test_progress_update_fix.py -v
```

### 4. Performance Tests (`tests/performance/`)

**Purpose**: Validate system performance under load

**Coverage Areas**:
- Lambda function performance
- DynamoDB query performance
- API response times
- Batch processing efficiency
- Duplicate detection performance impact
- Multi-worksheet processing performance

### 5. Security Tests (`tests/security/`)

**Purpose**: Validate security controls and access restrictions

**Coverage Areas**:
- Authentication and authorization
- Input validation and sanitization
- API security controls
- Data encryption validation

## Test Execution Strategies

### Comprehensive Test Suite

```bash
# Run all tests with coverage
python tests/run_comprehensive_tests.py

# Run authentication-specific tests
python tests/run_auth_tests.py

# Run duplicate handling E2E tests
python tests/run_duplicate_handling_e2e_tests.py

# Validate test configuration
python tests/validate_tests.py

# Validate duplicate handling integration
python tests/validate_duplicate_handling_integration.py
```

### Phone Field Testing

The phone field integration has been thoroughly tested with 31+ tests covering:

**Unit Level (26+ tests)**:
- Phone number format validation
- Phone field extraction and normalization
- DynamoDB phone operations
- Phone error handling

**Integration Level (4+ tests)**:
- DeepSeek phone field processing
- Phone field in batch processing workflow
- Phone field storage integration
- Cross-component phone validation

**E2E Level (1+ comprehensive test)**:
- Complete phone field workflow validation
- Frontend phone field integration
- API phone field functionality

### Multi-Worksheet Excel Testing

**Unit Level**:
- Excel file parsing with multiple worksheets
- Worksheet detection and enumeration
- Data extraction from each worksheet
- Worksheet field mapping and normalization

**Integration Level**:
- End-to-end multi-worksheet processing
- Batch creation from multiple worksheets
- DeepSeek processing with worksheet tracking

### Duplicate Handling Testing

**Unit Level**:
- Email normalization and validation
- Duplicate detection logic
- DynamoDB upsert operations
- Error handling for duplicate scenarios

**Integration Level**:
- Complete duplicate handling workflow
- EmailIndex GSI integration
- Batch-level duplicate processing

**E2E Level**:
- End-to-end duplicate handling scenarios
- Performance testing with high duplicate percentages
- Error recovery and fallback behavior

### Test Data Management

**Test Files**:
- `easy-crm-test.xlsx` - Excel test data with phone fields
- `test-leads-excel.csv` - CSV test data
- `conftest.py` - Shared test fixtures and configuration

**Mock Data**:
- Uses `moto` library for AWS service mocking
- Consistent test data across all test categories
- Phone number test data in various formats

## Test Configuration

### Pytest Configuration (`pytest.ini`)

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

### Test Fixtures (`tests/conftest.py`)

- AWS service mocking setup
- Test data generation
- Common test utilities
- Environment configuration

## Continuous Testing

### Pre-Deployment Testing

1. **Template Validation**: `./scripts/validate-templates.sh`
2. **Unit Tests**: All unit tests must pass
3. **Integration Tests**: All integration tests must pass
4. **Phone Field Tests**: All 31 phone field tests must pass
5. **Smoke Tests**: `./scripts/smoke-tests.sh`

### Test Coverage Requirements

- **Unit Tests**: Minimum 80% code coverage
- **Integration Tests**: All API endpoints covered
- **E2E Tests**: All user workflows covered
- **Phone Field**: 100% phone field functionality covered

### Test Reporting

**Coverage Reports**:
```bash
# Generate coverage report
python -m pytest tests/ --cov=lambda --cov-report=html

# View coverage data
open htmlcov/index.html
```

**Test Reports**:
- `test_report.json` - Machine-readable test results
- `test_report.txt` - Human-readable test summary
- `.coverage` - Coverage data file

## Testing Best Practices

### Test Organization

1. **Arrange-Act-Assert**: Structure all tests with clear setup, execution, and validation
2. **Isolation**: Each test should be independent and not rely on other tests
3. **Descriptive Names**: Test names should clearly describe what is being tested
4. **Mock External Dependencies**: Use mocking for AWS services and external APIs

### Phone Field Testing

1. **Format Validation**: Test all supported phone number formats
2. **Cross-Component Testing**: Verify phone field works across all Lambda functions
3. **Frontend Integration**: Test phone field display and interaction
4. **Error Handling**: Test invalid phone number handling

### Performance Testing

1. **Baseline Metrics**: Establish performance baselines for all functions
2. **Load Testing**: Test system behavior under expected load
3. **Batch Processing**: Validate batch processing performance with large files
4. **Memory Usage**: Monitor Lambda memory usage and optimization

### Security Testing

1. **Input Validation**: Test all input validation mechanisms
2. **Authentication**: Verify Cognito integration and JWT validation
3. **Authorization**: Test API access controls
4. **Data Sanitization**: Verify data sanitization in all components

## Troubleshooting Tests

### Common Test Failures

1. **AWS Credentials**: Ensure test environment has proper AWS credentials
2. **Mock Setup**: Verify moto mocking is properly configured
3. **Test Data**: Check test data files are available and properly formatted
4. **Environment Variables**: Ensure required environment variables are set

### Phone Field Test Issues

1. **Phone Validation**: Check phone number format validation logic
2. **DynamoDB Operations**: Verify phone field storage and retrieval
3. **Frontend Integration**: Check phone field display in UI components
4. **API Integration**: Verify phone field in API responses

### Debugging Test Failures

```bash
# Run tests with detailed output
python -m pytest tests/ -v -s --tb=long

# Run specific failing test
python -m pytest tests/unit/test_validation_phone.py::test_phone_validation -v -s

# Run tests with pdb debugging
python -m pytest tests/ --pdb
```

## Test Maintenance

### Regular Tasks

1. **Update Test Data**: Keep test data current with production data formats
2. **Review Test Coverage**: Ensure new code has appropriate test coverage
3. **Update Mocks**: Keep AWS service mocks current with API changes
4. **Performance Baselines**: Update performance baselines as system evolves

### Test Documentation

1. **Test Summaries**: Maintain test summary documents (like PHONE_FIELD_INTEGRATION_TEST_SUMMARY.md)
2. **Test Reports**: Generate and review test reports regularly
3. **Coverage Reports**: Monitor and improve test coverage over time
4. **Performance Reports**: Track performance trends over time

## Integration with CI/CD

### Pre-Commit Hooks

- Run unit tests before commits
- Validate code formatting and linting
- Check test coverage thresholds

### Deployment Pipeline

1. **Validate Templates**: CloudFormation template validation
2. **Unit Tests**: All unit tests must pass
3. **Integration Tests**: All integration tests must pass
4. **Security Tests**: Security validation tests
5. **Smoke Tests**: Post-deployment smoke tests
6. **Performance Tests**: Performance regression tests

### Quality Gates

- **Test Coverage**: Minimum 80% coverage required
- **Test Pass Rate**: 100% test pass rate required
- **Performance**: No performance regression allowed
- **Security**: All security tests must pass

This comprehensive testing strategy ensures the Easy CRM system maintains high quality, reliability, and performance across all components and features.