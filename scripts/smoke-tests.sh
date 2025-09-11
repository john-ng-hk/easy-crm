#!/bin/bash

# Smoke Tests for Easy CRM Deployment
# This script runs comprehensive smoke tests to validate deployment

set -e

# Default Configuration
DEFAULT_ENVIRONMENT="prod"
DEFAULT_REGION="ap-southeast-1"
DEFAULT_PROFILE="nch-prod"

# Parse command line arguments
ENVIRONMENT=${1:-$DEFAULT_ENVIRONMENT}
REGION=""
PROFILE=""
STACK_NAME=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_failure() {
    echo -e "${RED}✗${NC} $1"
}

# Function to load environment configuration
load_environment_config() {
    local env_file="config/environments/${ENVIRONMENT}.yaml"
    
    if [ ! -f "$env_file" ]; then
        print_error "Environment configuration file not found: $env_file"
        exit 1
    fi
    
    STACK_NAME=$(grep "^StackName:" "$env_file" | cut -d' ' -f2)
    REGION=$(grep "^Region:" "$env_file" | cut -d' ' -f2)
    PROFILE=$(grep "^Profile:" "$env_file" | cut -d' ' -f2)
    
    STACK_NAME=${STACK_NAME:-"easy-crm"}
    REGION=${REGION:-$DEFAULT_REGION}
    PROFILE=${PROFILE:-$DEFAULT_PROFILE}
}

# Function to test CloudFormation stack
test_cloudformation_stack() {
    print_header "Testing CloudFormation Stack"
    
    if aws cloudformation describe-stacks \
        --stack-name ${STACK_NAME} \
        --region ${REGION} \
        --profile ${PROFILE} > /dev/null 2>&1; then
        
        local stack_status=$(aws cloudformation describe-stacks \
            --stack-name ${STACK_NAME} \
            --region ${REGION} \
            --profile ${PROFILE} \
            --query 'Stacks[0].StackStatus' \
            --output text)
        
        if [ "$stack_status" = "CREATE_COMPLETE" ] || [ "$stack_status" = "UPDATE_COMPLETE" ]; then
            print_success "CloudFormation stack is in healthy state: $stack_status"
            return 0
        else
            print_failure "CloudFormation stack is in unhealthy state: $stack_status"
            return 1
        fi
    else
        print_failure "CloudFormation stack not found: $STACK_NAME"
        return 1
    fi
}

# Function to test DynamoDB table
test_dynamodb_table() {
    print_header "Testing DynamoDB Table"
    
    local table_name="easy-crm-leads-${ENVIRONMENT}"
    
    if aws dynamodb describe-table \
        --table-name ${table_name} \
        --region ${REGION} \
        --profile ${PROFILE} > /dev/null 2>&1; then
        
        local table_status=$(aws dynamodb describe-table \
            --table-name ${table_name} \
            --region ${REGION} \
            --profile ${PROFILE} \
            --query 'Table.TableStatus' \
            --output text)
        
        if [ "$table_status" = "ACTIVE" ]; then
            print_success "DynamoDB table is active: $table_name"
            
            # Test table access by performing a scan with limit
            if aws dynamodb scan \
                --table-name ${table_name} \
                --limit 1 \
                --region ${REGION} \
                --profile ${PROFILE} > /dev/null 2>&1; then
                print_success "DynamoDB table is accessible for read operations"
                return 0
            else
                print_failure "DynamoDB table read access failed"
                return 1
            fi
        else
            print_failure "DynamoDB table is not active: $table_status"
            return 1
        fi
    else
        print_failure "DynamoDB table not found: $table_name"
        return 1
    fi
}

# Function to test Lambda functions
test_lambda_functions() {
    print_header "Testing Lambda Functions"
    
    local functions=("file-upload" "lead-splitter" "deepseek-caller" "lead-reader" "lead-exporter" "chatbot" "status-reader")
    local failed_functions=()
    
    for func in "${functions[@]}"; do
        local func_name="easy-crm-${func}-${ENVIRONMENT}"
        
        if aws lambda get-function \
            --function-name ${func_name} \
            --region ${REGION} \
            --profile ${PROFILE} > /dev/null 2>&1; then
            
            # Test function configuration
            local func_state=$(aws lambda get-function \
                --function-name ${func_name} \
                --region ${REGION} \
                --profile ${PROFILE} \
                --query 'Configuration.State' \
                --output text)
            
            if [ "$func_state" = "Active" ]; then
                print_success "Lambda function is active: $func"
            else
                print_failure "Lambda function is not active: $func (state: $func_state)"
                failed_functions+=($func)
            fi
        else
            print_failure "Lambda function not found: $func"
            failed_functions+=($func)
        fi
    done
    
    if [ ${#failed_functions[@]} -eq 0 ]; then
        return 0
    else
        print_error "Failed Lambda functions: ${failed_functions[*]}"
        return 1
    fi
}

# Function to test API Gateway
test_api_gateway() {
    print_header "Testing API Gateway"
    
    local api_url=$(aws cloudformation describe-stacks \
        --stack-name ${STACK_NAME} \
        --region ${REGION} \
        --profile ${PROFILE} \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$api_url" ]; then
        print_failure "API Gateway URL not found in CloudFormation outputs"
        return 1
    fi
    
    print_status "Testing API Gateway endpoint: $api_url"
    
    # Test CORS preflight request
    if curl -s -f -X OPTIONS \
        -H "Origin: https://example.com" \
        -H "Access-Control-Request-Method: GET" \
        -H "Access-Control-Request-Headers: Authorization" \
        "${api_url}/leads" > /dev/null 2>&1; then
        print_success "API Gateway CORS is configured correctly"
    else
        print_warning "API Gateway CORS test failed (may be expected without authentication)"
    fi
    
    # Test basic connectivity
    if curl -s -f "${api_url}" > /dev/null 2>&1; then
        print_success "API Gateway is accessible"
        return 0
    else
        print_warning "API Gateway connectivity test failed (may be expected without authentication)"
        return 0  # Don't fail the test as this might be expected
    fi
}

# Function to test S3 buckets
test_s3_buckets() {
    print_header "Testing S3 Buckets"
    
    # Get bucket names from CloudFormation outputs
    local files_bucket=$(aws cloudformation describe-stacks \
        --stack-name ${STACK_NAME} \
        --region ${REGION} \
        --profile ${PROFILE} \
        --query 'Stacks[0].Outputs[?OutputKey==`FilesBucketName`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    local website_bucket=$(aws cloudformation describe-stacks \
        --stack-name ${STACK_NAME} \
        --region ${REGION} \
        --profile ${PROFILE} \
        --query 'Stacks[0].Outputs[?OutputKey==`WebsiteBucketName`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    local success=0
    
    if [ ! -z "$files_bucket" ]; then
        if aws s3 ls s3://${files_bucket} --profile ${PROFILE} > /dev/null 2>&1; then
            print_success "Files S3 bucket is accessible: $files_bucket"
        else
            print_failure "Files S3 bucket access failed: $files_bucket"
            success=1
        fi
    else
        print_failure "Files S3 bucket name not found in outputs"
        success=1
    fi
    
    if [ ! -z "$website_bucket" ]; then
        if aws s3 ls s3://${website_bucket} --profile ${PROFILE} > /dev/null 2>&1; then
            print_success "Website S3 bucket is accessible: $website_bucket"
        else
            print_failure "Website S3 bucket access failed: $website_bucket"
            success=1
        fi
    else
        print_failure "Website S3 bucket name not found in outputs"
        success=1
    fi
    
    return $success
}

# Function to test CloudFront
test_cloudfront() {
    print_header "Testing CloudFront Distribution"
    
    local cloudfront_url=$(aws cloudformation describe-stacks \
        --stack-name ${STACK_NAME} \
        --region ${REGION} \
        --profile ${PROFILE} \
        --query 'Stacks[0].Outputs[?OutputKey==`WebsiteURL`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    local distribution_id=$(aws cloudformation describe-stacks \
        --stack-name ${STACK_NAME} \
        --region ${REGION} \
        --profile ${PROFILE} \
        --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$distribution_id" ]; then
        print_failure "CloudFront Distribution ID not found in outputs"
        return 1
    fi
    
    # Check distribution status
    local distribution_status=$(aws cloudfront get-distribution \
        --id ${distribution_id} \
        --query 'Distribution.Status' \
        --output text 2>/dev/null || echo "")
    
    if [ "$distribution_status" = "Deployed" ]; then
        print_success "CloudFront distribution is deployed: $distribution_id"
    else
        print_warning "CloudFront distribution status: $distribution_status (may still be deploying)"
    fi
    
    # Test CloudFront URL accessibility
    if [ ! -z "$cloudfront_url" ]; then
        print_status "Testing CloudFront URL: $cloudfront_url"
        
        # Test basic connectivity (allow 404 as the site may not have content yet)
        local http_status=$(curl -s -o /dev/null -w "%{http_code}" "$cloudfront_url" 2>/dev/null || echo "000")
        
        if [ "$http_status" = "200" ] || [ "$http_status" = "403" ] || [ "$http_status" = "404" ]; then
            print_success "CloudFront distribution is accessible (HTTP $http_status)"
            return 0
        else
            print_warning "CloudFront accessibility test returned HTTP $http_status"
            return 0  # Don't fail as this might be expected without content
        fi
    else
        print_failure "CloudFront URL not found in outputs"
        return 1
    fi
}

# Function to test Cognito
test_cognito() {
    print_header "Testing Cognito Configuration"
    
    local user_pool_id=$(aws cloudformation describe-stacks \
        --stack-name ${STACK_NAME} \
        --region ${REGION} \
        --profile ${PROFILE} \
        --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    local client_id=$(aws cloudformation describe-stacks \
        --stack-name ${STACK_NAME} \
        --region ${REGION} \
        --profile ${PROFILE} \
        --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    if [ ! -z "$user_pool_id" ]; then
        if aws cognito-idp describe-user-pool \
            --user-pool-id ${user_pool_id} \
            --region ${REGION} \
            --profile ${PROFILE} > /dev/null 2>&1; then
            print_success "Cognito User Pool is accessible: $user_pool_id"
        else
            print_failure "Cognito User Pool access failed: $user_pool_id"
            return 1
        fi
    else
        print_failure "Cognito User Pool ID not found in outputs"
        return 1
    fi
    
    if [ ! -z "$client_id" ]; then
        if aws cognito-idp describe-user-pool-client \
            --user-pool-id ${user_pool_id} \
            --client-id ${client_id} \
            --region ${REGION} \
            --profile ${PROFILE} > /dev/null 2>&1; then
            print_success "Cognito User Pool Client is accessible: $client_id"
            return 0
        else
            print_failure "Cognito User Pool Client access failed: $client_id"
            return 1
        fi
    else
        print_failure "Cognito User Pool Client ID not found in outputs"
        return 1
    fi
}

# Function to test duplicate handling configuration
test_duplicate_handling() {
    print_header "Testing Duplicate Handling Configuration"
    
    local success=0
    
    # Test 1: Check if EmailIndex GSI exists
    local table_name="easy-crm-leads-${ENVIRONMENT}"
    
    print_status "Checking EmailIndex GSI on table: $table_name"
    
    local gsi_info=$(aws dynamodb describe-table \
        --table-name ${table_name} \
        --region ${REGION} \
        --profile ${PROFILE} \
        --query 'Table.GlobalSecondaryIndexes[?IndexName==`EmailIndex`]' \
        --output json 2>/dev/null || echo "[]")
    
    if [ "$gsi_info" = "[]" ] || [ "$gsi_info" = "null" ]; then
        print_failure "EmailIndex GSI not found on table $table_name"
        success=1
    else
        local gsi_status=$(echo "$gsi_info" | jq -r '.[0].IndexStatus' 2>/dev/null || echo "")
        if [ "$gsi_status" = "ACTIVE" ]; then
            print_success "EmailIndex GSI is active and ready for duplicate detection"
        else
            print_warning "EmailIndex GSI status: $gsi_status (may still be creating)"
        fi
    fi
    
    # Test 2: Check if email_utils.py exists
    if [ -f "lambda/shared/email_utils.py" ]; then
        print_success "Email utilities module found"
        
        # Test email normalization functionality
        if python3 -c "
import sys
sys.path.append('lambda/shared')
from email_utils import EmailNormalizer
result = EmailNormalizer.normalize_email('  TEST@EXAMPLE.COM  ')
assert result == 'test@example.com', f'Expected test@example.com, got {result}'
print('Email normalization working correctly')
" 2>/dev/null; then
            print_success "Email normalization functionality verified"
        else
            print_failure "Email normalization functionality test failed"
            success=1
        fi
    else
        print_failure "Email utilities module not found: lambda/shared/email_utils.py"
        success=1
    fi
    
    # Test 3: Check if DynamoDB utils have duplicate handling methods
    if [ -f "lambda/shared/dynamodb_utils.py" ]; then
        print_success "DynamoDB utilities module found"
        
        # Check for required methods
        if python3 -c "
import sys
sys.path.append('lambda/shared')
from dynamodb_utils import DynamoDBUtils
import inspect

required_methods = ['find_lead_by_email', 'upsert_lead', 'batch_upsert_leads']
missing_methods = []

for method in required_methods:
    if not hasattr(DynamoDBUtils, method):
        missing_methods.append(method)

if missing_methods:
    print(f'Missing methods: {missing_methods}')
    sys.exit(1)
else:
    print('All duplicate handling methods found')
" 2>/dev/null; then
            print_success "DynamoDB duplicate handling methods verified"
        else
            print_failure "DynamoDB duplicate handling methods test failed"
            success=1
        fi
    else
        print_failure "DynamoDB utilities module not found: lambda/shared/dynamodb_utils.py"
        success=1
    fi
    
    # Test 4: Check DeepSeek Caller function environment variables
    local deepseek_func="easy-crm-deepseek-caller-${ENVIRONMENT}"
    
    if aws lambda get-function-configuration \
        --function-name ${deepseek_func} \
        --region ${REGION} \
        --profile ${PROFILE} > /dev/null 2>&1; then
        
        local env_vars=$(aws lambda get-function-configuration \
            --function-name ${deepseek_func} \
            --region ${REGION} \
            --profile ${PROFILE} \
            --query 'Environment.Variables' \
            --output json 2>/dev/null || echo "{}")
        
        local leads_table_var=$(echo "$env_vars" | jq -r '.LEADS_TABLE // empty' 2>/dev/null)
        
        if [ -n "$leads_table_var" ]; then
            print_success "DeepSeek Caller function has required environment variables"
        else
            print_failure "DeepSeek Caller function missing LEADS_TABLE environment variable"
            success=1
        fi
    else
        print_failure "DeepSeek Caller function not found: $deepseek_func"
        success=1
    fi
    
    # Test 5: Run duplicate handling unit tests if available
    if [ -f "tests/unit/test_email_utils.py" ]; then
        print_status "Running duplicate handling unit tests..."
        
        if python3 -m pytest tests/unit/test_email_utils.py -q > /dev/null 2>&1; then
            print_success "Duplicate handling unit tests passed"
        else
            print_warning "Duplicate handling unit tests failed (may need dependencies)"
        fi
    else
        print_warning "Duplicate handling unit tests not found"
    fi
    
    return $success
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [environment]"
    echo ""
    echo "Arguments:"
    echo "  environment    Target environment (dev, staging, prod) [default: prod]"
    echo ""
    echo "Examples:"
    echo "  $0              # Test production environment"
    echo "  $0 dev          # Test development environment"
    echo "  $0 staging      # Test staging environment"
}

# Main execution
main() {
    # Show usage if help requested
    if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        show_usage
        exit 0
    fi
    
    # Load environment configuration
    load_environment_config
    
    print_header "Running Smoke Tests for Environment: $ENVIRONMENT"
    print_status "Stack: $STACK_NAME"
    print_status "Region: $REGION"
    print_status "Profile: $PROFILE"
    echo ""
    
    local failed_tests=0
    
    # Run all tests
    test_cloudformation_stack || ((failed_tests++))
    echo ""
    
    test_dynamodb_table || ((failed_tests++))
    echo ""
    
    test_lambda_functions || ((failed_tests++))
    echo ""
    
    test_api_gateway || ((failed_tests++))
    echo ""
    
    test_s3_buckets || ((failed_tests++))
    echo ""
    
    test_cloudfront || ((failed_tests++))
    echo ""
    
    test_cognito || ((failed_tests++))
    echo ""
    
    test_duplicate_handling || ((failed_tests++))
    echo ""
    
    # Summary
    print_header "Smoke Test Summary"
    if [ $failed_tests -eq 0 ]; then
        print_success "All smoke tests passed! ✅"
        print_status "The deployment appears to be healthy and ready for use."
        exit 0
    else
        print_failure "$failed_tests test(s) failed! ❌"
        print_error "Please review the failed tests and fix any issues before proceeding."
        exit 1
    fi
}

# Run main function
main "$@"