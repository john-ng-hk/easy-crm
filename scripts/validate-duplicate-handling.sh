#!/bin/bash

# Duplicate Lead Handling Deployment Validation Script
# Tests the duplicate detection and handling functionality

set -e

# Configuration
PROFILE="nch-prod"
REGION="ap-southeast-1"
STACK_NAME="easy-crm"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get stack outputs
get_stack_output() {
    local output_key=$1
    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --profile "$PROFILE" \
        --region "$REGION" \
        --query "Stacks[0].Outputs[?OutputKey=='$output_key'].OutputValue" \
        --output text 2>/dev/null || echo ""
}

# Test functions
test_email_normalization() {
    log_info "Testing email normalization functionality..."
    
    # Test the email utils module
    python3 -c "
import sys
sys.path.append('lambda/shared')
from email_utils import EmailNormalizer

# Test cases
test_cases = [
    ('  John.Doe@EXAMPLE.COM  ', 'john.doe@example.com'),
    ('', 'N/A'),
    ('N/A', 'N/A'),
    ('test@Test.COM', 'test@test.com'),
    ('   ', 'N/A')
]

for input_email, expected in test_cases:
    result = EmailNormalizer.normalize_email(input_email)
    if result == expected:
        print(f'✓ Email normalization test passed: \"{input_email}\" -> \"{result}\"')
    else:
        print(f'✗ Email normalization test failed: \"{input_email}\" -> \"{result}\" (expected \"{expected}\")')
        sys.exit(1)
"
    
    if [ $? -eq 0 ]; then
        log_success "Email normalization tests passed"
    else
        log_error "Email normalization tests failed"
        return 1
    fi
}

test_dynamodb_utils() {
    log_info "Testing DynamoDB utilities for duplicate handling..."
    
    # Check if the enhanced DynamoDB utils have the required methods
    python3 -c "
import sys
sys.path.append('lambda/shared')
from dynamodb_utils import DynamoDBUtils
import inspect

# Check for required methods
required_methods = [
    'find_lead_by_email',
    'upsert_lead', 
    'batch_upsert_leads'
]

utils_class = DynamoDBUtils
for method_name in required_methods:
    if hasattr(utils_class, method_name):
        print(f'✓ Method {method_name} exists in DynamoDBUtils')
    else:
        print(f'✗ Method {method_name} missing from DynamoDBUtils')
        sys.exit(1)
"
    
    if [ $? -eq 0 ]; then
        log_success "DynamoDB utilities validation passed"
    else
        log_error "DynamoDB utilities validation failed"
        return 1
    fi
}

test_emailindex_gsi() {
    log_info "Testing EmailIndex GSI configuration..."
    
    # Get the table name from stack outputs
    LEADS_TABLE=$(get_stack_output "LeadsTableName")
    
    if [ -z "$LEADS_TABLE" ]; then
        log_error "Could not retrieve leads table name from stack outputs"
        return 1
    fi
    
    log_info "Checking EmailIndex GSI on table: $LEADS_TABLE"
    
    # Check if EmailIndex GSI exists
    GSI_INFO=$(aws dynamodb describe-table \
        --table-name "$LEADS_TABLE" \
        --profile "$PROFILE" \
        --region "$REGION" \
        --query "Table.GlobalSecondaryIndexes[?IndexName=='EmailIndex']" \
        --output json 2>/dev/null)
    
    if [ "$GSI_INFO" = "[]" ] || [ "$GSI_INFO" = "null" ]; then
        log_error "EmailIndex GSI not found on table $LEADS_TABLE"
        return 1
    else
        log_success "EmailIndex GSI found and configured"
        
        # Check GSI status
        GSI_STATUS=$(echo "$GSI_INFO" | jq -r '.[0].IndexStatus' 2>/dev/null)
        if [ "$GSI_STATUS" = "ACTIVE" ]; then
            log_success "EmailIndex GSI is ACTIVE"
        else
            log_warning "EmailIndex GSI status: $GSI_STATUS"
        fi
    fi
}

test_lambda_environment_variables() {
    log_info "Testing Lambda function environment variables..."
    
    # Test DeepSeek Caller function (main function that handles duplicates)
    DEEPSEEK_FUNCTION=$(get_stack_output "DeepSeekCallerFunctionName")
    
    if [ -z "$DEEPSEEK_FUNCTION" ]; then
        log_error "Could not retrieve DeepSeek Caller function name"
        return 1
    fi
    
    log_info "Checking environment variables for function: $DEEPSEEK_FUNCTION"
    
    # Check required environment variables
    ENV_VARS=$(aws lambda get-function-configuration \
        --function-name "$DEEPSEEK_FUNCTION" \
        --profile "$PROFILE" \
        --region "$REGION" \
        --query "Environment.Variables" \
        --output json 2>/dev/null)
    
    if [ -z "$ENV_VARS" ] || [ "$ENV_VARS" = "null" ]; then
        log_error "Could not retrieve environment variables for $DEEPSEEK_FUNCTION"
        return 1
    fi
    
    # Check for required variables
    LEADS_TABLE_VAR=$(echo "$ENV_VARS" | jq -r '.LEADS_TABLE // empty')
    DEEPSEEK_API_KEY_VAR=$(echo "$ENV_VARS" | jq -r '.DEEPSEEK_API_KEY // empty')
    
    if [ -n "$LEADS_TABLE_VAR" ]; then
        log_success "LEADS_TABLE environment variable configured"
    else
        log_error "LEADS_TABLE environment variable missing"
        return 1
    fi
    
    if [ -n "$DEEPSEEK_API_KEY_VAR" ]; then
        log_success "DEEPSEEK_API_KEY environment variable configured"
    else
        log_error "DEEPSEEK_API_KEY environment variable missing"
        return 1
    fi
}

test_iam_permissions() {
    log_info "Testing IAM permissions for duplicate handling..."
    
    # Get Lambda execution role ARN
    DEEPSEEK_FUNCTION=$(get_stack_output "DeepSeekCallerFunctionName")
    
    if [ -z "$DEEPSEEK_FUNCTION" ]; then
        log_error "Could not retrieve DeepSeek Caller function name"
        return 1
    fi
    
    ROLE_ARN=$(aws lambda get-function-configuration \
        --function-name "$DEEPSEEK_FUNCTION" \
        --profile "$PROFILE" \
        --region "$REGION" \
        --query "Role" \
        --output text 2>/dev/null)
    
    if [ -z "$ROLE_ARN" ]; then
        log_error "Could not retrieve Lambda execution role"
        return 1
    fi
    
    ROLE_NAME=$(basename "$ROLE_ARN")
    log_info "Checking permissions for role: $ROLE_NAME"
    
    # Check if role has DynamoDB query permissions (needed for EmailIndex GSI)
    POLICIES=$(aws iam list-attached-role-policies \
        --role-name "$ROLE_NAME" \
        --profile "$PROFILE" \
        --query "AttachedPolicies[].PolicyArn" \
        --output text 2>/dev/null)
    
    if [ -n "$POLICIES" ]; then
        log_success "IAM policies attached to Lambda execution role"
        
        # Check for DynamoDB permissions in inline policies
        INLINE_POLICIES=$(aws iam list-role-policies \
            --role-name "$ROLE_NAME" \
            --profile "$PROFILE" \
            --query "PolicyNames" \
            --output text 2>/dev/null)
        
        if [ -n "$INLINE_POLICIES" ]; then
            log_success "Inline policies found (likely contains DynamoDB permissions)"
        else
            log_warning "No inline policies found - check attached policies for DynamoDB permissions"
        fi
    else
        log_error "No IAM policies attached to Lambda execution role"
        return 1
    fi
}

run_duplicate_handling_tests() {
    log_info "Running duplicate handling unit tests..."
    
    # Run the duplicate handling specific tests
    if [ -f "tests/unit/test_email_utils.py" ]; then
        python3 -m pytest tests/unit/test_email_utils.py -v
        if [ $? -eq 0 ]; then
            log_success "Email utils unit tests passed"
        else
            log_error "Email utils unit tests failed"
            return 1
        fi
    else
        log_warning "Email utils unit tests not found"
    fi
    
    if [ -f "tests/unit/test_dynamodb_duplicate_utils.py" ]; then
        python3 -m pytest tests/unit/test_dynamodb_duplicate_utils.py -v
        if [ $? -eq 0 ]; then
            log_success "DynamoDB duplicate utils unit tests passed"
        else
            log_error "DynamoDB duplicate utils unit tests failed"
            return 1
        fi
    else
        log_warning "DynamoDB duplicate utils unit tests not found"
    fi
    
    if [ -f "tests/integration/test_duplicate_handling_workflow.py" ]; then
        python3 -m pytest tests/integration/test_duplicate_handling_workflow.py -v
        if [ $? -eq 0 ]; then
            log_success "Duplicate handling integration tests passed"
        else
            log_error "Duplicate handling integration tests failed"
            return 1
        fi
    else
        log_warning "Duplicate handling integration tests not found"
    fi
}

# Main validation function
main() {
    log_info "Starting Duplicate Lead Handling Deployment Validation"
    log_info "Stack: $STACK_NAME, Profile: $PROFILE, Region: $REGION"
    echo
    
    # Check if required tools are available
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install AWS CLI."
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        log_error "jq not found. Please install jq for JSON parsing."
        exit 1
    fi
    
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 not found. Please install Python 3."
        exit 1
    fi
    
    # Run validation tests
    FAILED_TESTS=0
    
    test_email_normalization || ((FAILED_TESTS++))
    echo
    
    test_dynamodb_utils || ((FAILED_TESTS++))
    echo
    
    test_emailindex_gsi || ((FAILED_TESTS++))
    echo
    
    test_lambda_environment_variables || ((FAILED_TESTS++))
    echo
    
    test_iam_permissions || ((FAILED_TESTS++))
    echo
    
    run_duplicate_handling_tests || ((FAILED_TESTS++))
    echo
    
    # Summary
    if [ $FAILED_TESTS -eq 0 ]; then
        log_success "All duplicate handling validation tests passed! ✅"
        log_info "Duplicate lead handling is properly configured and ready for use."
    else
        log_error "Validation failed with $FAILED_TESTS test(s) failing ❌"
        log_info "Please review the errors above and fix the issues before using duplicate handling."
        exit 1
    fi
}

# Run main function
main "$@"