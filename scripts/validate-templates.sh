#!/bin/bash

# CloudFormation Template Validation Script
# This script validates all CloudFormation templates

set -e

# Configuration
REGION="ap-southeast-1"
PROFILE="nch-prod"

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

# Function to validate a template
validate_template() {
    local template_file=$1
    local template_name=$(basename ${template_file} .yaml)
    
    print_status "Validating ${template_name}..."
    
    if aws cloudformation validate-template \
        --template-body file://${template_file} \
        --profile ${PROFILE} \
        --region ${REGION} > /dev/null 2>&1; then
        print_status "✓ ${template_name} is valid"
    else
        print_error "✗ ${template_name} validation failed"
        aws cloudformation validate-template \
            --template-body file://${template_file} \
            --profile ${PROFILE} \
            --region ${REGION}
        return 1
    fi
}

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

print_status "Starting CloudFormation template validation..."

# Validate all templates
validate_template "infrastructure/main.yaml"
validate_template "infrastructure/storage.yaml"
validate_template "infrastructure/cognito.yaml"
validate_template "infrastructure/lambda.yaml"
validate_template "infrastructure/api-gateway.yaml"
validate_template "infrastructure/cloudfront.yaml"

print_status "All CloudFormation templates are valid!"