#!/bin/bash

# CloudFront Cache Invalidation Script
# This script invalidates the CloudFront cache for Easy CRM

set -e

# Default Configuration
DEFAULT_PROFILE="nch-prod"
DEFAULT_REGION="ap-southeast-1"
DEFAULT_ENVIRONMENT="prod"

# Parse command line arguments
ENVIRONMENT=${1:-$DEFAULT_ENVIRONMENT}
PROFILE=""
REGION=""
STACK_NAME=""

# Function to load environment configuration
load_environment_config() {
    local env_file="config/environments/${ENVIRONMENT}.yaml"
    
    if [ ! -f "$env_file" ]; then
        echo "❌ Environment configuration file not found: $env_file"
        echo "   Available environments: dev, staging, prod"
        exit 1
    fi
    
    # Parse YAML configuration
    STACK_NAME=$(grep "^StackName:" "$env_file" | cut -d' ' -f2)
    REGION=$(grep "^Region:" "$env_file" | cut -d' ' -f2)
    PROFILE=$(grep "^Profile:" "$env_file" | cut -d' ' -f2)
    
    # Set defaults if not found in config
    STACK_NAME=${STACK_NAME:-"easy-crm"}
    REGION=${REGION:-$DEFAULT_REGION}
    PROFILE=${PROFILE:-$DEFAULT_PROFILE}
}

# Load environment configuration
load_environment_config

echo "🔄 Invalidating CloudFront cache for Easy CRM..."

# Get CloudFront distribution ID
CLOUDFRONT_DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --profile $PROFILE \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
    --output text 2>/dev/null || echo "")

if [ -z "$CLOUDFRONT_DISTRIBUTION_ID" ]; then
    echo "❌ CloudFront distribution ID not found"
    echo "   Make sure the infrastructure is deployed first"
    exit 1
fi

echo "📋 CloudFront Distribution ID: $CLOUDFRONT_DISTRIBUTION_ID"

# Create invalidation
echo "🔄 Creating invalidation for all paths (/*) ..."
INVALIDATION_ID=$(aws cloudfront create-invalidation \
    --distribution-id $CLOUDFRONT_DISTRIBUTION_ID \
    --paths "/*" \
    --profile $PROFILE \
    --query 'Invalidation.Id' \
    --output text)

if [ ! -z "$INVALIDATION_ID" ]; then
    echo "✅ CloudFront invalidation created successfully!"
    echo "📋 Invalidation ID: $INVALIDATION_ID"
    echo "⏳ Cache invalidation is in progress (typically takes 1-5 minutes)"
    echo ""
    echo "🌐 You can check the status at:"
    echo "   https://console.aws.amazon.com/cloudfront/home?region=us-east-1#distribution-settings:$CLOUDFRONT_DISTRIBUTION_ID"
    echo ""
    echo "💡 Tip: Wait a few minutes before testing your changes"
else
    echo "❌ Failed to create CloudFront invalidation"
    exit 1
fi