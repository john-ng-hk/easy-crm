#!/bin/bash

# Deploy frontend to S3 bucket
# This script uploads the frontend files to the S3 website bucket

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

echo "🚀 Deploying Easy CRM Frontend..."

# Get the S3 website bucket name from CloudFormation outputs
echo "📋 Getting S3 bucket name from CloudFormation..."
BUCKET_NAME=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --profile $PROFILE \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`WebsiteBucketName`].OutputValue' \
    --output text)

if [ -z "$BUCKET_NAME" ]; then
    echo "❌ Error: Could not get S3 bucket name from CloudFormation stack"
    echo "   Make sure the infrastructure is deployed first"
    exit 1
fi

echo "📦 S3 Bucket: $BUCKET_NAME"

# Get API Gateway URL from CloudFormation outputs
echo "📋 Getting API Gateway URL from CloudFormation..."
API_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --profile $PROFILE \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayURL`].OutputValue' \
    --output text)

# Get Cognito User Pool ID from CloudFormation outputs
echo "📋 Getting Cognito configuration from CloudFormation..."
USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --profile $PROFILE \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
    --output text)

CLIENT_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --profile $PROFILE \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' \
    --output text)

# Update configuration file with actual values
echo "⚙️  Updating configuration..."
cat > frontend/config.json << EOF
{
  "api": {
    "baseUrl": "$API_URL"
  },
  "cognito": {
    "userPoolId": "$USER_POOL_ID",
    "clientId": "$CLIENT_ID",
    "region": "$REGION"
  },
  "app": {
    "name": "Easy CRM",
    "version": "1.0.0",
    "environment": "production"
  }
}
EOF

# Create a configuration injection script
echo "📝 Creating configuration injection script..."
cat > frontend/js/config-inject.js << EOF
// Auto-generated configuration injection
(function() {
    fetch('./config.json')
        .then(response => response.json())
        .then(config => {
            window.EasyCRM.Config.API.BASE_URL = config.api.baseUrl;
            window.EasyCRM.Config.COGNITO.USER_POOL_ID = config.cognito.userPoolId;
            window.EasyCRM.Config.COGNITO.CLIENT_ID = config.cognito.clientId;
            window.EasyCRM.Config.COGNITO.REGION = config.cognito.region;
            console.log('Configuration loaded from config.json');
        })
        .catch(error => {
            console.error('Failed to load configuration:', error);
        });
})();
EOF

# Sync frontend files to S3
echo "📤 Uploading frontend files to S3..."

# Upload HTML files
aws s3 cp frontend/index.html s3://$BUCKET_NAME/ \
    --profile $PROFILE \
    --content-type "text/html" \
    --cache-control "no-cache"

# Upload CSS files
aws s3 sync frontend/css/ s3://$BUCKET_NAME/css/ \
    --profile $PROFILE \
    --content-type "text/css" \
    --cache-control "max-age=86400"

# Upload JavaScript files
aws s3 sync frontend/js/ s3://$BUCKET_NAME/js/ \
    --profile $PROFILE \
    --content-type "application/javascript" \
    --cache-control "max-age=86400"

# Upload assets
if [ -d "frontend/assets" ]; then
    aws s3 sync frontend/assets/ s3://$BUCKET_NAME/assets/ \
        --profile $PROFILE \
        --cache-control "max-age=86400"
fi

# Upload configuration file
aws s3 cp frontend/config.json s3://$BUCKET_NAME/ \
    --profile $PROFILE \
    --content-type "application/json" \
    --cache-control "no-cache"

# Get CloudFront distribution ID and URL
CLOUDFRONT_DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --profile $PROFILE \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
    --output text 2>/dev/null || echo "")

CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --profile $PROFILE \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontUrl`].OutputValue' \
    --output text 2>/dev/null || echo "")

# Get S3 website URL
S3_WEBSITE_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --profile $PROFILE \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`WebsiteUrl`].OutputValue' \
    --output text)

# Create CloudFront invalidation to clear cache
if [ ! -z "$CLOUDFRONT_DISTRIBUTION_ID" ]; then
    echo "🔄 Creating CloudFront invalidation to clear cache..."
    INVALIDATION_ID=$(aws cloudfront create-invalidation \
        --distribution-id $CLOUDFRONT_DISTRIBUTION_ID \
        --paths "/*" \
        --profile $PROFILE \
        --query 'Invalidation.Id' \
        --output text)
    
    if [ ! -z "$INVALIDATION_ID" ]; then
        echo "✅ CloudFront invalidation created: $INVALIDATION_ID"
        echo "⏳ Cache invalidation is in progress (takes 1-5 minutes)"
    else
        echo "⚠️  Failed to create CloudFront invalidation"
    fi
else
    echo "⚠️  CloudFront distribution ID not found, skipping invalidation"
fi

echo ""
echo "✅ Frontend deployment completed successfully!"
echo ""
echo "📊 Deployment Summary:"
echo "   S3 Bucket: $BUCKET_NAME"
echo "   API Gateway: $API_URL"
echo "   User Pool ID: $USER_POOL_ID"
echo "   Client ID: $CLIENT_ID"
echo ""
echo "🌐 Access URLs:"
echo "   S3 Website: $S3_WEBSITE_URL"
if [ ! -z "$CLOUDFRONT_URL" ]; then
    echo "   CloudFront: $CLOUDFRONT_URL"
fi
echo ""
echo "📝 Next Steps:"
echo "   1. Test the application by visiting the URL above"
echo "   2. Create a Cognito user account if needed"
echo "   3. Upload a test CSV/Excel file to verify functionality"
echo ""

# Clean up temporary files
rm -f frontend/js/config-inject.js

echo "🎉 Deployment complete!"