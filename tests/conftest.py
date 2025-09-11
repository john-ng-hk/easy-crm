"""
Pytest configuration and fixtures for the lead management system tests.

Provides common fixtures, test markers, and configuration for all test suites.
"""

import pytest
import os
import sys
import boto3
from moto import mock_aws
from unittest.mock import patch, Mock

# Add lambda paths to Python path for all tests
lambda_paths = [
    os.path.join(os.path.dirname(__file__), '..', 'lambda', 'shared'),
    os.path.join(os.path.dirname(__file__), '..', 'lambda', 'file-upload'),
    os.path.join(os.path.dirname(__file__), '..', 'lambda', 'lead-splitter'),
    os.path.join(os.path.dirname(__file__), '..', 'lambda', 'deepseek-caller'),
    os.path.join(os.path.dirname(__file__), '..', 'lambda', 'lead-reader'),
    os.path.join(os.path.dirname(__file__), '..', 'lambda', 'lead-exporter'),
    os.path.join(os.path.dirname(__file__), '..', 'lambda', 'chatbot')
]

for path in lambda_paths:
    if path not in sys.path:
        sys.path.append(path)

# Test markers
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "security: mark test as a security test"
    )
    config.addinivalue_line(
        "markers", "deepseek: mark test as requiring DeepSeek API"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )

# Common fixtures
@pytest.fixture
def mock_lambda_context():
    """Mock AWS Lambda context."""
    context = Mock()
    context.aws_request_id = 'test-request-id'
    context.function_name = 'test-function'
    context.memory_limit_in_mb = 256
    context.remaining_time_in_millis = lambda: 30000
    context.invoked_function_arn = 'arn:aws:lambda:ap-southeast-1:123456789012:function:test-function'
    return context

@pytest.fixture
def mock_jwt_token():
    """Mock JWT token validation."""
    with patch('validation.validate_jwt_token') as mock_validate:
        mock_validate.return_value = {
            'sub': 'test-user-123',
            'email': 'test@example.com',
            'exp': 9999999999  # Far future expiration
        }
        yield mock_validate

@pytest.fixture
def aws_credentials():
    """Mock AWS credentials for testing."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'ap-southeast-1'

@pytest.fixture
def mock_dynamodb_table():
    """Create a mock DynamoDB table for testing."""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-1')
        
        table = dynamodb.create_table(
            TableName='test-leads',
            KeySchema=[
                {'AttributeName': 'leadId', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'leadId', 'AttributeType': 'S'},
                {'AttributeName': 'company', 'AttributeType': 'S'},
                {'AttributeName': 'email', 'AttributeType': 'S'},
                {'AttributeName': 'createdAt', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'CompanyIndex',
                    'KeySchema': [
                        {'AttributeName': 'company', 'KeyType': 'HASH'},
                        {'AttributeName': 'createdAt', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'BillingMode': 'PAY_PER_REQUEST'
                },
                {
                    'IndexName': 'EmailIndex',
                    'KeySchema': [
                        {'AttributeName': 'email', 'KeyType': 'HASH'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'BillingMode': 'PAY_PER_REQUEST'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        yield table

@pytest.fixture
def mock_s3_bucket():
    """Create a mock S3 bucket for testing."""
    with mock_aws():
        s3_client = boto3.client('s3', region_name='ap-southeast-1')
        bucket_name = 'test-bucket'
        
        s3_client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': 'ap-southeast-1'}
        )
        
        yield s3_client, bucket_name

@pytest.fixture
def sample_leads_data():
    """Sample leads data for testing."""
    return [
        {
            'leadId': 'test-lead-1',
            'firstName': 'John',
            'lastName': 'Doe',
            'title': 'Software Engineer',
            'company': 'Tech Corp',
            'email': 'john.doe@techcorp.com',
            'remarks': 'Interested in cloud solutions',
            'sourceFile': 'test.csv',
            'createdAt': '2024-01-15T10:00:00Z',
            'updatedAt': '2024-01-15T10:00:00Z'
        },
        {
            'leadId': 'test-lead-2',
            'firstName': 'Jane',
            'lastName': 'Smith',
            'title': 'Product Manager',
            'company': 'Innovation Inc',
            'email': 'jane.smith@innovation.com',
            'remarks': 'Looking for automation tools',
            'sourceFile': 'test.csv',
            'createdAt': '2024-01-16T10:00:00Z',
            'updatedAt': '2024-01-16T10:00:00Z'
        }
    ]

@pytest.fixture
def mock_deepseek_response():
    """Mock DeepSeek API response."""
    return [
        {
            'firstName': 'John',
            'lastName': 'Doe',
            'title': 'Software Engineer',
            'company': 'Tech Corp',
            'email': 'john.doe@techcorp.com',
            'remarks': 'Interested in cloud solutions'
        },
        {
            'firstName': 'Jane',
            'lastName': 'Smith',
            'title': 'Product Manager',
            'company': 'Innovation Inc',
            'email': 'jane.smith@innovation.com',
            'remarks': 'Looking for automation tools'
        }
    ]

@pytest.fixture
def mock_api_gateway_event():
    """Mock API Gateway event."""
    def _create_event(method='GET', path_params=None, query_params=None, body=None, headers=None):
        event = {
            'httpMethod': method,
            'headers': headers or {'Authorization': 'Bearer test-token'},
            'pathParameters': path_params or {},
            'queryStringParameters': query_params or {},
            'requestContext': {
                'requestId': 'test-request-id',
                'stage': 'test',
                'httpMethod': method
            }
        }
        
        if body:
            event['body'] = body if isinstance(body, str) else json.dumps(body)
        
        return event
    
    return _create_event

# Test environment setup
@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    test_env_vars = {
        'UPLOAD_BUCKET': 'test-upload-bucket',
        'DYNAMODB_TABLE_NAME': 'test-leads',
        'MAX_FILE_SIZE_MB': '10',
        'PRESIGNED_URL_EXPIRATION': '3600',
        'DEEPSEEK_API_KEY': 'test-deepseek-key',
        'AWS_DEFAULT_REGION': 'ap-southeast-1'
    }
    
    with patch.dict(os.environ, test_env_vars):
        yield

# Skip conditions
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add skip conditions."""
    # Skip DeepSeek tests if API key not available
    deepseek_api_key = os.environ.get('DEEPSEEK_API_KEY')
    
    for item in items:
        # Skip DeepSeek integration tests if no API key
        if 'deepseek' in item.keywords and not deepseek_api_key:
            item.add_marker(pytest.mark.skip(reason="DEEPSEEK_API_KEY not set"))
        
        # Skip performance tests in CI unless explicitly requested
        if 'performance' in item.keywords and os.environ.get('CI') and not config.getoption('--run-performance'):
            item.add_marker(pytest.mark.skip(reason="Performance tests skipped in CI"))

def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-performance",
        action="store_true",
        default=False,
        help="Run performance tests"
    )
    parser.addoption(
        "--run-deepseek",
        action="store_true",
        default=False,
        help="Run DeepSeek API integration tests"
    )
    parser.addoption(
        "--run-security",
        action="store_true",
        default=False,
        help="Run security tests"
    )

# Cleanup fixtures
@pytest.fixture
def cleanup_test_files():
    """Clean up any test files created during testing."""
    test_files = []
    
    yield test_files
    
    # Clean up files after test
    for file_path in test_files:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Warning: Could not clean up test file {file_path}: {e}")

# Performance monitoring
@pytest.fixture
def performance_monitor():
    """Monitor test performance."""
    import time
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    
    start_time = time.time()
    start_memory = process.memory_info().rss / (1024 * 1024)  # MB
    
    yield
    
    end_time = time.time()
    end_memory = process.memory_info().rss / (1024 * 1024)  # MB
    
    execution_time = end_time - start_time
    memory_delta = end_memory - start_memory
    
    # Log performance metrics for slow tests
    if execution_time > 5.0:  # Tests taking more than 5 seconds
        print(f"\nPerformance Warning:")
        print(f"  Execution time: {execution_time:.2f} seconds")
        print(f"  Memory delta: {memory_delta:.2f} MB")

# Error handling
@pytest.fixture
def capture_errors():
    """Capture and log errors for debugging."""
    errors = []
    
    yield errors
    
    if errors:
        print(f"\nCaptured {len(errors)} errors during test:")
        for i, error in enumerate(errors, 1):
            print(f"  Error {i}: {error}")