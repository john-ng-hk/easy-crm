# Lead Management System - Comprehensive Testing Suite

This directory contains a comprehensive testing suite for the lead management system, covering all aspects of functionality, performance, security, and integration.

## Test Structure

```
tests/
├── unit/                           # Unit tests for individual components
│   ├── test_file_upload.py        # File upload Lambda tests
│   ├── test_lead_splitter.py      # Lead splitter Lambda tests
│   ├── test_deepseek_caller.py    # DeepSeek caller Lambda tests
│   ├── test_lead_reader.py        # Lead reader Lambda tests
│   ├── test_lead_exporter.py      # Lead exporter Lambda tests
│   ├── test_chatbot.py            # Chatbot Lambda tests
│   └── test_auth.py               # Authentication tests
├── integration/                    # Integration tests with AWS services
│   ├── test_file_upload_integration.py
│   ├── test_lead_splitter_integration.py
│   ├── test_deepseek_caller_integration.py
│   ├── test_lead_reader_integration.py
│   ├── test_lead_exporter_integration.py
│   ├── test_chatbot_integration.py
│   ├── test_cognito_authentication.py
│   └── test_deepseek_api_integration.py
├── e2e/                           # End-to-end workflow tests
│   └── test_complete_workflow.py
├── performance/                   # Performance and load tests
│   └── test_performance.py
├── security/                      # Security and vulnerability tests
│   └── test_security.py
├── conftest.py                    # Pytest configuration and fixtures
├── validate_tests.py              # Test validation script
├── run_comprehensive_tests.py     # Comprehensive test runner
└── README.md                      # This file
```

## Test Categories

### 1. Unit Tests (`tests/unit/`)

Tests individual Lambda functions and components in isolation:

- **File Upload Tests**: Presigned URL generation, validation, error handling
- **Lead Splitter Tests**: CSV/Excel processing, batch creation, SQS integration
- **DeepSeek Caller Tests**: SQS message processing, DeepSeek integration, DynamoDB operations
- **Lead Reader Tests**: Filtering, sorting, pagination, single lead retrieval
- **Lead Exporter Tests**: CSV generation, filtering integration, response formatting
- **Chatbot Tests**: Natural language processing, query generation, response formatting
- **Authentication Tests**: JWT validation, token handling, security

**Coverage**: All Lambda functions, shared utilities, error handling

### 2. Integration Tests (`tests/integration/`)

Tests component interactions with real AWS services (mocked):

- **AWS Service Integration**: S3, DynamoDB, API Gateway interactions
- **DeepSeek API Integration**: Real API calls with actual data processing
- **Authentication Flow**: Cognito integration and JWT validation
- **Cross-Service Communication**: Lambda-to-Lambda interactions

**Coverage**: API endpoints, database operations, external service integration

### 3. End-to-End Tests (`tests/e2e/`)

Tests complete user workflows from start to finish:

- **Complete CSV Workflow**: Upload → Process → Store → Retrieve
- **Complete Excel Workflow**: Excel processing with export functionality
- **Chatbot Integration**: Natural language queries with data retrieval
- **Error Handling**: End-to-end error scenarios
- **Real Test File Processing**: Using the actual `easy-crm-test.xlsx` file

**Coverage**: Full system workflows, user scenarios, data integrity

### 4. Performance Tests (`tests/performance/`)

Tests system performance under various conditions:

- **Large File Processing**: 10k+ row CSV/Excel files
- **Concurrent Operations**: Multiple simultaneous uploads and queries
- **Database Performance**: Batch operations, pagination, filtering
- **Memory Usage**: Memory consumption with large datasets
- **Response Times**: API response times under load
- **Rate Limiting**: DeepSeek API rate limiting behavior

**Coverage**: Scalability, resource usage, response times

### 5. Security Tests (`tests/security/`)

Tests security measures and vulnerability protection:

- **Authentication Security**: JWT validation, token expiration, missing auth
- **Input Validation**: SQL injection, XSS, path traversal attempts
- **Data Protection**: Sensitive data handling, logging security
- **File Upload Security**: File type validation, size limits, filename sanitization
- **API Security**: CORS headers, rate limiting, request validation
- **Database Security**: Parameterized queries, access patterns

**Coverage**: Authentication, authorization, input validation, data protection

### 6. DeepSeek API Integration Tests

Tests actual DeepSeek API integration:

- **Real API Calls**: Actual data standardization with DeepSeek
- **Error Handling**: API failures, rate limiting, invalid responses
- **Data Accuracy**: Verification of standardization quality
- **Performance**: API response times and batch processing
- **Concurrent Requests**: Multiple simultaneous API calls

**Coverage**: External API integration, data standardization accuracy

## Running Tests

### Prerequisites

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables** (for DeepSeek tests):
   ```bash
   export DEEPSEEK_API_KEY="your-api-key"
   ```

### Quick Test Commands

```bash
# Run all tests
python tests/run_comprehensive_tests.py --all

# Run specific test suites
python tests/run_comprehensive_tests.py --unit
python tests/run_comprehensive_tests.py --integration
python tests/run_comprehensive_tests.py --e2e
python tests/run_comprehensive_tests.py --performance
python tests/run_comprehensive_tests.py --security

# Run with coverage analysis
python tests/run_comprehensive_tests.py --coverage

# Run DeepSeek API tests (requires API key)
python tests/run_comprehensive_tests.py --deepseek

# Verbose output
python tests/run_comprehensive_tests.py --all --verbose
```

### Direct Pytest Commands

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests (excluding DeepSeek)
pytest tests/integration/ -v -m "not deepseek"

# Performance tests
pytest tests/performance/ -v -m performance

# Security tests
pytest tests/security/ -v -m security

# DeepSeek API tests (requires API key)
pytest tests/integration/test_deepseek_api_integration.py -v -m deepseek

# Run with coverage
pytest tests/unit/ tests/integration/ --cov=lambda --cov-report=html
```

### Test Validation

```bash
# Validate test structure and imports
python tests/validate_tests.py
```

## Test Configuration

### Pytest Configuration (`pytest.ini`)

- Test discovery patterns
- Marker definitions
- Output formatting
- Coverage settings
- Warning filters

### Fixtures (`conftest.py`)

- **AWS Environment**: Mock DynamoDB tables, S3 buckets
- **Authentication**: Mock JWT tokens and validation
- **Test Data**: Sample leads, API responses, events
- **Performance Monitoring**: Execution time and memory tracking

### Environment Variables

Required for full test execution:

```bash
# DeepSeek API (for integration tests)
DEEPSEEK_API_KEY=your-api-key

# AWS Configuration (automatically set by moto)
AWS_DEFAULT_REGION=ap-southeast-1
```

## Test Markers

Tests are organized using pytest markers:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests  
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.performance` - Performance tests
- `@pytest.mark.security` - Security tests
- `@pytest.mark.deepseek` - DeepSeek API tests
- `@pytest.mark.slow` - Slow running tests

## Coverage Analysis

Generate test coverage reports:

```bash
# Run tests with coverage
pytest tests/unit/ tests/integration/ --cov=lambda --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html
```

## Performance Benchmarks

Expected performance benchmarks:

- **CSV Processing**: <10s for 10k rows
- **Excel Processing**: <30s for 5k rows
- **API Response**: <1s average, <3s maximum
- **Database Operations**: <2s for pagination queries
- **Memory Usage**: <200MB increase for large files

## Security Test Coverage

Security tests cover:

- **OWASP Top 10** vulnerabilities
- **Input validation** for all user inputs
- **Authentication** and authorization flows
- **Data protection** and privacy measures
- **File upload** security measures
- **API security** headers and CORS

## Continuous Integration

For CI/CD integration:

```bash
# Fast test suite (unit + integration, no DeepSeek)
pytest tests/unit/ tests/integration/ -m "not deepseek and not performance and not slow"

# Full test suite with reports
python tests/run_comprehensive_tests.py --all --coverage
```

## Troubleshooting

### Common Issues

1. **Missing Dependencies**: Run `pip install -r requirements.txt`
2. **DeepSeek Tests Failing**: Set `DEEPSEEK_API_KEY` environment variable
3. **Import Errors**: Ensure lambda paths are in `PYTHONPATH`
4. **Slow Tests**: Use `-m "not slow"` to skip slow tests
5. **Memory Issues**: Reduce test data size in performance tests

### Debug Mode

Run tests with verbose output and no capture:

```bash
pytest tests/unit/test_file_upload.py -v -s --tb=long
```

### Test Reports

After running comprehensive tests, check:

- `test_report.json` - Machine-readable results
- `test_report.txt` - Human-readable summary
- `htmlcov/index.html` - Coverage report

## Contributing

When adding new tests:

1. Follow the existing naming conventions
2. Add appropriate pytest markers
3. Include docstrings explaining test purpose
4. Mock external dependencies appropriately
5. Validate tests with `python tests/validate_tests.py`

## Requirements Coverage

This testing suite addresses all requirements from task 12:

✅ **Unit tests for all Lambda functions using pytest**
- Complete unit test coverage for all 5 Lambda functions
- Comprehensive error handling and edge case testing
- Mock-based isolation testing

✅ **Integration tests for API Gateway endpoints**  
- All API endpoints tested with realistic scenarios
- Authentication and CORS testing
- Error response validation

✅ **End-to-end tests using the easy-crm-test file**
- Complete workflow testing from upload to retrieval
- Real test file processing validation
- Cross-component integration verification

✅ **DeepSeek API integration tests with actual API calls**
- Real API integration testing with various data formats
- Error handling and rate limiting tests
- Data standardization accuracy validation

✅ **Performance tests for file processing and database operations**
- Large file processing benchmarks (10k+ rows)
- Concurrent operation testing
- Memory usage and response time monitoring

✅ **Security tests for authentication and input validation**
- Comprehensive security vulnerability testing
- Authentication and authorization validation
- Input sanitization and injection prevention

The testing suite provides comprehensive coverage of all system components, ensuring reliability, performance, and security of the lead management system.