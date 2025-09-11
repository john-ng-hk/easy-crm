#!/bin/bash

# Lambda Function Packaging and Deployment Script
# This script packages and deploys Lambda functions for Easy CRM

set -e

# Default Configuration
DEFAULT_REGION="ap-southeast-1"
DEFAULT_PROFILE="nch-prod"
DEFAULT_ENVIRONMENT="prod"

# Parse command line arguments
ENVIRONMENT=${1:-$DEFAULT_ENVIRONMENT}
REGION=""
PROFILE=""

# Function to load environment configuration
load_environment_config() {
    local env_file="config/environments/${ENVIRONMENT}.yaml"
    
    if [ ! -f "$env_file" ]; then
        print_error "Environment configuration file not found: $env_file"
        print_error "Available environments: dev, staging, prod"
        exit 1
    fi
    
    # Parse YAML configuration
    REGION=$(grep "^Region:" "$env_file" | cut -d' ' -f2)
    PROFILE=$(grep "^Profile:" "$env_file" | cut -d' ' -f2)
    
    # Set defaults if not found in config
    REGION=${REGION:-$DEFAULT_REGION}
    PROFILE=${PROFILE:-$DEFAULT_PROFILE}
}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Function to package and deploy a Lambda function
package_and_deploy() {
    local function_dir=$1
    local function_name=$2
    
    print_status "Packaging and deploying ${function_name}..."
    
    # Create temporary directory for packaging
    local temp_dir=$(mktemp -d)
    
    # Copy function code
    cp -r ${function_dir}/* ${temp_dir}/
    
    # Copy shared utilities
    cp -r lambda/shared/* ${temp_dir}/
    
    # Install dependencies if requirements.txt exists
    if [ -f "${function_dir}/requirements.txt" ]; then
        print_status "Installing dependencies for ${function_name}..."
        pip install -r ${function_dir}/requirements.txt -t ${temp_dir}/ --quiet
    fi
    
    # Create deployment package
    local zip_file="${function_name}.zip"
    cd ${temp_dir}
    zip -r ${zip_file} . -x "*.pyc" "__pycache__/*" "*.git*" > /dev/null
    
    # Deploy to Lambda
    aws lambda update-function-code \
        --function-name "easy-crm-${function_name}-${ENVIRONMENT}" \
        --zip-file fileb://${zip_file} \
        --region ${REGION} \
        --profile ${PROFILE} > /dev/null
    
    # Clean up
    cd - > /dev/null
    rm -rf ${temp_dir}
    
    print_status "Successfully deployed ${function_name}"
}

# Load environment configuration
load_environment_config

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

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    print_warning "Virtual environment not detected. Activating venv..."
    source venv/bin/activate
fi

print_status "Starting Lambda function deployment..."

# Package and deploy each Lambda function
package_and_deploy "lambda/file-upload" "file-upload"
package_and_deploy "lambda/lead-splitter" "lead-splitter"
package_and_deploy "lambda/deepseek-caller" "deepseek-caller"
package_and_deploy "lambda/lead-reader" "lead-reader"
package_and_deploy "lambda/lead-exporter" "lead-exporter"
package_and_deploy "lambda/chatbot" "chatbot"
package_and_deploy "lambda/status-reader" "status-reader"

print_status "All Lambda functions deployed successfully!"
print_warning "Remember to test each function to ensure they're working correctly."