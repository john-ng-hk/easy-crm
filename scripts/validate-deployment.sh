#!/bin/bash

# Deployment Validation Script
# This script validates deployment prerequisites and configuration

set -e

# Default Configuration
DEFAULT_ENVIRONMENT="prod"

# Parse command line arguments
ENVIRONMENT=${1:-$DEFAULT_ENVIRONMENT}

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
    echo -e "${BLUE}[VALIDATE]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_failure() {
    echo -e "${RED}✗${NC} $1"
}

# Function to validate AWS CLI
validate_aws_cli() {
    print_header "Validating AWS CLI"
    
    if command -v aws &> /dev/null; then
        local aws_version=$(aws --version 2>&1 | cut -d/ -f2 | cut -d' ' -f1)
        print_success "AWS CLI is installed (version: $aws_version)"
        
        # Check if version is recent enough (2.0+)
        local major_version=$(echo $aws_version | cut -d. -f1)
        if [ "$major_version" -ge 2 ]; then
            print_success "AWS CLI version is supported"
        else
            print_warning "AWS CLI version is older than 2.0, consider upgrading"
        fi
        return 0
    else
        print_failure "AWS CLI is not installed"
        print_error "Please install AWS CLI v2: https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html"
        return 1
    fi
}

# Function to validate AWS profile
validate_aws_profile() {
    print_header "Validating AWS Profile"
    
    local env_file="config/environments/${ENVIRONMENT}.yaml"
    local profile=$(grep "^Profile:" "$env_file" | cut -d' ' -f2 2>/dev/null || echo "nch-prod")
    
    if aws configure list-profiles | grep -q "^${profile}$"; then
        print_success "AWS profile exists: $profile"
        
        # Test credentials
        if aws sts get-caller-identity --profile $profile > /dev/null 2>&1; then
            local account_id=$(aws sts get-caller-identity --profile $profile --query Account --output text)
            local user_arn=$(aws sts get-caller-identity --profile $profile --query Arn --output text)
            print_success "AWS credentials are valid"
            print_status "Account ID: $account_id"
            print_status "User/Role: $user_arn"
            return 0
        else
            print_failure "AWS credentials test failed"
            print_error "Please check your AWS credentials for profile: $profile"
            return 1
        fi
    else
        print_failure "AWS profile not found: $profile"
        print_error "Please configure AWS profile: aws configure --profile $profile"
        return 1
    fi
}

# Function to validate IAM permissions
validate_iam_permissions() {
    print_header "Validating IAM Permissions"
    
    local env_file="config/environments/${ENVIRONMENT}.yaml"
    local profile=$(grep "^Profile:" "$env_file" | cut -d' ' -f2 2>/dev/null || echo "nch-prod")
    local region=$(grep "^Region:" "$env_file" | cut -d' ' -f2 2>/dev/null || echo "ap-southeast-1")
    
    local required_services=("cloudformation" "lambda" "dynamodb" "s3" "cognito-idp" "apigateway" "iam")
    local failed_services=()
    
    for service in "${required_services[@]}"; do
        case $service in
            "cloudformation")
                if aws cloudformation list-stacks --profile $profile --region $region > /dev/null 2>&1; then
                    print_success "CloudFormation access: OK"
                else
                    print_failure "CloudFormation access: FAILED"
                    failed_services+=($service)
                fi
                ;;
            "lambda")
                if aws lambda list-functions --profile $profile --region $region > /dev/null 2>&1; then
                    print_success "Lambda access: OK"
                else
                    print_failure "Lambda access: FAILED"
                    failed_services+=($service)
                fi
                ;;
            "dynamodb")
                if aws dynamodb list-tables --profile $profile --region $region > /dev/null 2>&1; then
                    print_success "DynamoDB access: OK"
                else
                    print_failure "DynamoDB access: FAILED"
                    failed_services+=($service)
                fi
                ;;
            "s3")
                if aws s3 ls --profile $profile > /dev/null 2>&1; then
                    print_success "S3 access: OK"
                else
                    print_failure "S3 access: FAILED"
                    failed_services+=($service)
                fi
                ;;
            "cognito-idp")
                if aws cognito-idp list-user-pools --max-results 1 --profile $profile --region $region > /dev/null 2>&1; then
                    print_success "Cognito access: OK"
                else
                    print_failure "Cognito access: FAILED"
                    failed_services+=($service)
                fi
                ;;
            "apigateway")
                if aws apigateway get-rest-apis --profile $profile --region $region > /dev/null 2>&1; then
                    print_success "API Gateway access: OK"
                else
                    print_failure "API Gateway access: FAILED"
                    failed_services+=($service)
                fi
                ;;
            "iam")
                if aws iam list-roles --max-items 1 --profile $profile > /dev/null 2>&1; then
                    print_success "IAM access: OK"
                else
                    print_failure "IAM access: FAILED"
                    failed_services+=($service)
                fi
                ;;
        esac
    done
    
    if [ ${#failed_services[@]} -eq 0 ]; then
        return 0
    else
        print_error "Missing permissions for services: ${failed_services[*]}"
        return 1
    fi
}

# Function to validate Python environment
validate_python_environment() {
    print_header "Validating Python Environment"
    
    # Check Python version
    if command -v python3 &> /dev/null; then
        local python_version=$(python3 --version | cut -d' ' -f2)
        print_success "Python 3 is installed (version: $python_version)"
        
        # Check if version is 3.8+
        local major_version=$(echo $python_version | cut -d. -f1)
        local minor_version=$(echo $python_version | cut -d. -f2)
        if [ "$major_version" -eq 3 ] && [ "$minor_version" -ge 8 ]; then
            print_success "Python version is supported"
        else
            print_warning "Python version should be 3.8 or higher"
        fi
    else
        print_failure "Python 3 is not installed"
        return 1
    fi
    
    # Check virtual environment
    if [ -d "venv" ]; then
        print_success "Virtual environment directory exists"
        
        if [ ! -z "$VIRTUAL_ENV" ]; then
            print_success "Virtual environment is activated"
        else
            print_warning "Virtual environment is not activated"
            print_status "Run: source venv/bin/activate"
        fi
    else
        print_warning "Virtual environment not found"
        print_status "Run: python3 -m venv venv"
    fi
    
    # Check pip
    if command -v pip &> /dev/null; then
        print_success "pip is available"
    else
        print_failure "pip is not available"
        return 1
    fi
    
    return 0
}

# Function to validate project structure
validate_project_structure() {
    print_header "Validating Project Structure"
    
    local required_dirs=("infrastructure" "lambda" "frontend" "scripts" "config/environments")
    local required_files=("requirements.txt" "infrastructure/main.yaml")
    
    # Check directories
    for dir in "${required_dirs[@]}"; do
        if [ -d "$dir" ]; then
            print_success "Directory exists: $dir"
        else
            print_failure "Directory missing: $dir"
            return 1
        fi
    done
    
    # Check files
    for file in "${required_files[@]}"; do
        if [ -f "$file" ]; then
            print_success "File exists: $file"
        else
            print_failure "File missing: $file"
            return 1
        fi
    done
    
    # Check environment configuration
    local env_file="config/environments/${ENVIRONMENT}.yaml"
    if [ -f "$env_file" ]; then
        print_success "Environment configuration exists: $env_file"
    else
        print_failure "Environment configuration missing: $env_file"
        return 1
    fi
    
    return 0
}

# Function to validate CloudFormation templates
validate_cloudformation_templates() {
    print_header "Validating CloudFormation Templates"
    
    local env_file="config/environments/${ENVIRONMENT}.yaml"
    local profile=$(grep "^Profile:" "$env_file" | cut -d' ' -f2 2>/dev/null || echo "nch-prod")
    local region=$(grep "^Region:" "$env_file" | cut -d' ' -f2 2>/dev/null || echo "ap-southeast-1")
    
    local templates=("main.yaml" "storage.yaml" "cognito.yaml" "lambda.yaml" "api-gateway.yaml" "cloudfront.yaml")
    local failed_templates=()
    
    for template in "${templates[@]}"; do
        local template_path="infrastructure/$template"
        if [ -f "$template_path" ]; then
            if aws cloudformation validate-template \
                --template-body file://$template_path \
                --profile $profile \
                --region $region > /dev/null 2>&1; then
                print_success "Template valid: $template"
            else
                print_failure "Template invalid: $template"
                failed_templates+=($template)
            fi
        else
            print_failure "Template missing: $template"
            failed_templates+=($template)
        fi
    done
    
    if [ ${#failed_templates[@]} -eq 0 ]; then
        return 0
    else
        print_error "Invalid templates: ${failed_templates[*]}"
        return 1
    fi
}

# Function to validate dependencies
validate_dependencies() {
    print_header "Validating Dependencies"
    
    # Check if requirements.txt exists and has content
    if [ -f "requirements.txt" ]; then
        print_success "Root requirements.txt exists"
        
        # Check if virtual environment has packages installed
        if [ ! -z "$VIRTUAL_ENV" ]; then
            local installed_packages=$(pip list --format=freeze | wc -l)
            if [ "$installed_packages" -gt 5 ]; then
                print_success "Dependencies appear to be installed ($installed_packages packages)"
            else
                print_warning "Few packages installed, run: pip install -r requirements.txt"
            fi
        fi
    else
        print_failure "Root requirements.txt missing"
        return 1
    fi
    
    # Check Lambda function requirements
    local lambda_dirs=("file-upload" "lead-splitter" "deepseek-caller" "lead-reader" "lead-exporter" "chatbot" "status-reader")
    for dir in "${lambda_dirs[@]}"; do
        local req_file="lambda/$dir/requirements.txt"
        if [ -f "$req_file" ]; then
            print_success "Lambda requirements exist: $dir"
        else
            print_warning "Lambda requirements missing: $dir"
        fi
    done
    
    return 0
}

# Function to validate duplicate handling setup
validate_duplicate_handling_setup() {
    print_header "Validating Duplicate Handling Setup"
    
    local success=0
    
    # Check if email_utils.py exists
    if [ -f "lambda/shared/email_utils.py" ]; then
        print_success "Email utilities module exists"
        
        # Test email normalization functionality
        if python3 -c "
import sys
sys.path.append('lambda/shared')
try:
    from email_utils import EmailNormalizer
    # Test basic functionality
    result = EmailNormalizer.normalize_email('  TEST@EXAMPLE.COM  ')
    assert result == 'test@example.com', f'Expected test@example.com, got {result}'
    
    # Test empty email handling
    result = EmailNormalizer.normalize_email('')
    assert result == 'N/A', f'Expected N/A for empty email, got {result}'
    
    print('Email normalization validation passed')
except Exception as e:
    print(f'Email normalization validation failed: {e}')
    sys.exit(1)
" 2>/dev/null; then
            print_success "Email normalization functionality validated"
        else
            print_failure "Email normalization functionality validation failed"
            success=1
        fi
    else
        print_failure "Email utilities module missing: lambda/shared/email_utils.py"
        success=1
    fi
    
    # Check if DynamoDB utils have duplicate handling methods
    if [ -f "lambda/shared/dynamodb_utils.py" ]; then
        print_success "DynamoDB utilities module exists"
        
        # Check for required methods
        if python3 -c "
import sys
sys.path.append('lambda/shared')
try:
    from dynamodb_utils import DynamoDBUtils
    import inspect
    
    required_methods = ['find_lead_by_email', 'upsert_lead', 'batch_upsert_leads']
    missing_methods = []
    
    for method in required_methods:
        if not hasattr(DynamoDBUtils, method):
            missing_methods.append(method)
    
    if missing_methods:
        print(f'Missing required methods: {missing_methods}')
        sys.exit(1)
    else:
        print('All duplicate handling methods found in DynamoDBUtils')
        
    # Check method signatures
    sig = inspect.signature(DynamoDBUtils.find_lead_by_email)
    if 'email' not in sig.parameters:
        print('find_lead_by_email method missing email parameter')
        sys.exit(1)
        
    sig = inspect.signature(DynamoDBUtils.upsert_lead)
    if 'lead_data' not in sig.parameters or 'source_file' not in sig.parameters:
        print('upsert_lead method missing required parameters')
        sys.exit(1)
        
    print('Method signatures validated')
        
except Exception as e:
    print(f'DynamoDB utilities validation failed: {e}')
    sys.exit(1)
" 2>/dev/null; then
            print_success "DynamoDB duplicate handling methods validated"
        else
            print_failure "DynamoDB duplicate handling methods validation failed"
            success=1
        fi
    else
        print_failure "DynamoDB utilities module missing: lambda/shared/dynamodb_utils.py"
        success=1
    fi
    
    # Check if DeepSeek Caller has been updated for duplicate handling
    if [ -f "lambda/deepseek-caller/lambda_function.py" ]; then
        print_success "DeepSeek Caller function exists"
        
        # Check if it imports the required modules
        if grep -q "from email_utils import EmailNormalizer" lambda/deepseek-caller/lambda_function.py 2>/dev/null; then
            print_success "DeepSeek Caller imports email utilities"
        else
            print_warning "DeepSeek Caller may not import email utilities (check implementation)"
        fi
        
        if grep -q "batch_upsert_leads\|upsert_lead" lambda/deepseek-caller/lambda_function.py 2>/dev/null; then
            print_success "DeepSeek Caller uses upsert methods"
        else
            print_warning "DeepSeek Caller may not use upsert methods (check implementation)"
        fi
    else
        print_failure "DeepSeek Caller function missing: lambda/deepseek-caller/lambda_function.py"
        success=1
    fi
    
    # Check if unit tests exist for duplicate handling
    local test_files=("tests/unit/test_email_utils.py" "tests/unit/test_dynamodb_duplicate_utils.py")
    local found_tests=0
    
    for test_file in "${test_files[@]}"; do
        if [ -f "$test_file" ]; then
            print_success "Test file exists: $(basename $test_file)"
            ((found_tests++))
        else
            print_warning "Test file missing: $test_file"
        fi
    done
    
    if [ $found_tests -gt 0 ]; then
        print_success "Duplicate handling tests are available"
    else
        print_warning "No duplicate handling tests found"
    fi
    
    # Check if integration tests exist
    if [ -f "tests/integration/test_duplicate_handling_workflow.py" ]; then
        print_success "Duplicate handling integration tests exist"
    else
        print_warning "Duplicate handling integration tests missing"
    fi
    
    # Validate that EmailIndex GSI is defined in infrastructure
    if [ -f "infrastructure/storage.yaml" ]; then
        if grep -q "EmailIndex" infrastructure/storage.yaml 2>/dev/null; then
            print_success "EmailIndex GSI defined in infrastructure"
        else
            print_failure "EmailIndex GSI not found in infrastructure/storage.yaml"
            success=1
        fi
    else
        print_failure "Storage infrastructure template missing"
        success=1
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
    echo "This script validates all prerequisites for deployment including:"
    echo "  - AWS CLI installation and configuration"
    echo "  - IAM permissions for required services"
    echo "  - Python environment and dependencies"
    echo "  - Project structure and files"
    echo "  - CloudFormation template syntax"
    echo "  - Duplicate handling setup and configuration"
}

# Main execution
main() {
    # Show usage if help requested
    if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        show_usage
        exit 0
    fi
    
    print_header "Deployment Validation for Environment: $ENVIRONMENT"
    echo ""
    
    local failed_validations=0
    
    # Run all validations
    validate_aws_cli || ((failed_validations++))
    echo ""
    
    validate_aws_profile || ((failed_validations++))
    echo ""
    
    validate_iam_permissions || ((failed_validations++))
    echo ""
    
    validate_python_environment || ((failed_validations++))
    echo ""
    
    validate_project_structure || ((failed_validations++))
    echo ""
    
    validate_cloudformation_templates || ((failed_validations++))
    echo ""
    
    validate_dependencies || ((failed_validations++))
    echo ""
    
    validate_duplicate_handling_setup || ((failed_validations++))
    echo ""
    
    # Summary
    print_header "Validation Summary"
    if [ $failed_validations -eq 0 ]; then
        print_success "All validations passed! ✅"
        print_status "You're ready to deploy to the $ENVIRONMENT environment."
        print_status "Run: ./scripts/deploy.sh $ENVIRONMENT"
        exit 0
    else
        print_failure "$failed_validations validation(s) failed! ❌"
        print_error "Please fix the issues above before deploying."
        exit 1
    fi
}

# Run main function
main "$@"