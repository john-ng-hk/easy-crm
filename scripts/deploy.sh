#!/bin/bash

# Easy CRM Deployment Script
# This script deploys the CloudFormation infrastructure for Easy CRM

set -e

# Default Configuration
DEFAULT_STACK_NAME="easy-crm"
DEFAULT_REGION="ap-southeast-1"
DEFAULT_PROFILE="nch-prod"
DEFAULT_ENVIRONMENT="prod"

# Parse command line arguments
ENVIRONMENT=${1:-$DEFAULT_ENVIRONMENT}
STACK_NAME=""
REGION=""
PROFILE=""

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
    echo -e "${BLUE}[DEPLOY]${NC} $1"
}

# Function to load environment configuration
load_environment_config() {
    local env_file="config/environments/${ENVIRONMENT}.yaml"
    
    if [ ! -f "$env_file" ]; then
        print_error "Environment configuration file not found: $env_file"
        print_error "Available environments: dev, staging, prod"
        exit 1
    fi
    
    print_status "Loading configuration for environment: $ENVIRONMENT"
    
    # Parse YAML configuration (simple key-value extraction)
    STACK_NAME=$(grep "^StackName:" "$env_file" | cut -d' ' -f2)
    REGION=$(grep "^Region:" "$env_file" | cut -d' ' -f2)
    PROFILE=$(grep "^Profile:" "$env_file" | cut -d' ' -f2)
    
    # Set defaults if not found in config
    STACK_NAME=${STACK_NAME:-$DEFAULT_STACK_NAME}
    REGION=${REGION:-$DEFAULT_REGION}
    PROFILE=${PROFILE:-$DEFAULT_PROFILE}
    
    print_status "Configuration loaded:"
    print_status "  Stack Name: $STACK_NAME"
    print_status "  Region: $REGION"
    print_status "  Profile: $PROFILE"
}

# Function to validate prerequisites
validate_prerequisites() {
    print_header "Validating Prerequisites"
    
    # Check if AWS CLI is installed
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if profile exists
    if ! aws configure list-profiles | grep -q "^${PROFILE}$"; then
        print_error "AWS profile '${PROFILE}' not found. Please configure it first."
        exit 1
    fi
    
    # Test AWS credentials
    print_status "Testing AWS credentials..."
    if ! aws sts get-caller-identity --profile ${PROFILE} --region ${REGION} > /dev/null 2>&1; then
        print_error "Failed to authenticate with AWS using profile '${PROFILE}'"
        exit 1
    fi
    
    # Check if required directories exist
    if [ ! -d "infrastructure" ]; then
        print_error "Infrastructure directory not found. Please run from project root."
        exit 1
    fi
    
    if [ ! -d "config/environments" ]; then
        print_error "Environment configuration directory not found."
        exit 1
    fi
    
    print_status "Prerequisites validation passed"
}

# Function to run smoke tests
run_smoke_tests() {
    print_header "Running Smoke Tests"
    
    # Test API Gateway endpoint
    local api_url=$(aws cloudformation describe-stacks \
        --stack-name ${STACK_NAME} \
        --region ${REGION} \
        --profile ${PROFILE} \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    if [ ! -z "$api_url" ]; then
        print_status "Testing API Gateway endpoint..."
        if curl -s -f "${api_url}/health" > /dev/null 2>&1; then
            print_status "✓ API Gateway is responding"
        else
            print_warning "⚠ API Gateway health check failed (this may be expected if no health endpoint exists)"
        fi
    fi
    
    # Test DynamoDB table
    local table_name="easy-crm-leads-${ENVIRONMENT}"
    print_status "Testing DynamoDB table access..."
    if aws dynamodb describe-table \
        --table-name ${table_name} \
        --region ${REGION} \
        --profile ${PROFILE} > /dev/null 2>&1; then
        print_status "✓ DynamoDB table is accessible"
    else
        print_warning "⚠ DynamoDB table test failed"
    fi
    
    # Test Lambda functions
    print_status "Testing Lambda functions..."
    local functions=("file-upload" "lead-splitter" "deepseek-caller" "lead-reader" "lead-exporter" "chatbot" "status-reader")
    for func in "${functions[@]}"; do
        local func_name="easy-crm-${func}-${ENVIRONMENT}"
        if aws lambda get-function \
            --function-name ${func_name} \
            --region ${REGION} \
            --profile ${PROFILE} > /dev/null 2>&1; then
            print_status "✓ Lambda function ${func} exists"
        else
            print_warning "⚠ Lambda function ${func} not found"
        fi
    done
    
    print_status "Smoke tests completed"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [environment]"
    echo ""
    echo "Arguments:"
    echo "  environment    Target environment (dev, staging, prod) [default: prod]"
    echo ""
    echo "Examples:"
    echo "  $0              # Deploy to production"
    echo "  $0 dev          # Deploy to development"
    echo "  $0 staging      # Deploy to staging"
    echo ""
    echo "Environment configurations are loaded from config/environments/"
}

# Show usage if help requested
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    show_usage
    exit 0
fi

# Load environment configuration
load_environment_config

# Validate prerequisites
validate_prerequisites

# Get required parameters
print_header "Configuration Parameters"

# Get DeepSeek API Key from environment or prompt user
if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo -n "Enter DeepSeek API Key: "
    read -s DEEPSEEK_API_KEY
    echo
fi

if [ -z "$DEEPSEEK_API_KEY" ]; then
    print_error "DeepSeek API Key is required"
    exit 1
fi

print_status "Using provided DeepSeek API Key"

# Get ACM certificate ARN from environment or use default
if [ -z "$CERTIFICATE_ARN" ]; then
    CERTIFICATE_ARN="arn:aws:acm:us-east-1:YOUR_ACCOUNT_ID:certificate/YOUR_CERTIFICATE_ID"
    echo -n "Enter ACM Certificate ARN (or press Enter for default): "
    read user_cert_arn
    if [ ! -z "$user_cert_arn" ]; then
        CERTIFICATE_ARN="$user_cert_arn"
    fi
fi

print_status "Using ACM certificate: ${CERTIFICATE_ARN}"

# Create S3 bucket for CloudFormation templates
TEMPLATE_BUCKET="easy-crm-templates-$(aws sts get-caller-identity --profile ${PROFILE} --query Account --output text)"

print_header "Preparing CloudFormation Templates"
print_status "Creating S3 bucket for CloudFormation templates..."
aws s3 mb s3://${TEMPLATE_BUCKET} --region ${REGION} --profile ${PROFILE} 2>/dev/null || true

# Upload nested templates to S3
print_status "Uploading CloudFormation templates to S3..."
aws s3 cp infrastructure/storage.yaml s3://${TEMPLATE_BUCKET}/storage.yaml --profile ${PROFILE}
aws s3 cp infrastructure/cognito.yaml s3://${TEMPLATE_BUCKET}/cognito.yaml --profile ${PROFILE}
aws s3 cp infrastructure/lambda.yaml s3://${TEMPLATE_BUCKET}/lambda.yaml --profile ${PROFILE}
aws s3 cp infrastructure/api-gateway.yaml s3://${TEMPLATE_BUCKET}/api-gateway.yaml --profile ${PROFILE}
aws s3 cp infrastructure/cloudfront.yaml s3://${TEMPLATE_BUCKET}/cloudfront.yaml --profile ${PROFILE}

# Validate main template
print_header "Template Validation"
print_status "Validating CloudFormation template..."
if ! aws cloudformation validate-template \
    --template-body file://infrastructure/main.yaml \
    --profile ${PROFILE} \
    --region ${REGION} > /dev/null 2>&1; then
    print_error "CloudFormation template validation failed"
    aws cloudformation validate-template \
        --template-body file://infrastructure/main.yaml \
        --profile ${PROFILE} \
        --region ${REGION}
    exit 1
fi
print_status "Template validation passed"

# Prepare parameters
PARAMETERS="ParameterKey=Environment,ParameterValue=${ENVIRONMENT}"
PARAMETERS="${PARAMETERS} ParameterKey=DeepSeekApiKey,ParameterValue=${DEEPSEEK_API_KEY}"
PARAMETERS="${PARAMETERS} ParameterKey=CertificateArn,ParameterValue=${CERTIFICATE_ARN}"

# Debug: Print parameters (without sensitive values)
print_status "Parameters being passed:"
print_status "  Environment: ${ENVIRONMENT}"
print_status "  DeepSeekApiKey length: ${#DEEPSEEK_API_KEY}"
print_status "  DeepSeekApiKey starts with: ${DEEPSEEK_API_KEY:0:5}..."
print_status "  CertificateArn: ${CERTIFICATE_ARN}"

# Create parameter file
PARAM_FILE="/tmp/deployment-params-${STACK_NAME}.json"
cat > ${PARAM_FILE} << EOF
[
  {
    "ParameterKey": "Environment",
    "ParameterValue": "${ENVIRONMENT}"
  },
  {
    "ParameterKey": "DeepSeekApiKey",
    "ParameterValue": "${DEEPSEEK_API_KEY}"
  },
  {
    "ParameterKey": "CertificateArn",
    "ParameterValue": "${CERTIFICATE_ARN}"
  }
]
EOF

# Deploy the stack
print_header "CloudFormation Deployment"
print_status "Deploying CloudFormation stack: ${STACK_NAME}"
print_status "This may take several minutes..."

if aws cloudformation deploy \
    --template-file infrastructure/main.yaml \
    --stack-name ${STACK_NAME} \
    --parameter-overrides file://${PARAM_FILE} \
    --capabilities CAPABILITY_NAMED_IAM \
    --region ${REGION} \
    --profile ${PROFILE} \
    --tags Environment=${ENVIRONMENT} Application=EasyCRM; then
    print_status "CloudFormation deployment completed successfully"
    # Clean up parameter file
    rm -f ${PARAM_FILE}
else
    print_error "CloudFormation deployment failed"
    print_error "Check the CloudFormation console for detailed error information"
    print_error "Parameter file saved at: ${PARAM_FILE}"
    exit 1
fi

# Run smoke tests
run_smoke_tests

# Get stack outputs
print_header "Deployment Summary"
print_status "Getting stack outputs..."
aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --region ${REGION} \
    --profile ${PROFILE} \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

print_status "✅ Infrastructure deployment successful!"
echo ""
print_header "Next Steps"
print_warning "1. Deploy Lambda function code:"
print_warning "   ./scripts/package-lambdas.sh ${ENVIRONMENT}"
print_warning ""
print_warning "2. Deploy frontend files:"
print_warning "   ./scripts/deploy-frontend.sh ${ENVIRONMENT}"
print_warning ""
print_warning "3. Test the application functionality"
print_warning ""
print_status "For troubleshooting, see: docs/deployment-troubleshooting.md"