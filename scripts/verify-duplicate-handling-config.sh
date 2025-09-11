#!/bin/bash

# Verify Duplicate Handling Configuration
# This script validates that all components are properly configured for duplicate handling

set -e

echo "[INFO] Verifying duplicate handling configuration..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
    fi
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

echo ""
echo "=== 1. Verifying EmailIndex GSI Configuration ==="

# Check if EmailIndex GSI exists in storage.yaml
if grep -q "IndexName: EmailIndex" infrastructure/storage.yaml; then
    print_status 0 "EmailIndex GSI defined in storage.yaml"
    
    # Verify GSI configuration
    if grep -A 10 "IndexName: EmailIndex" infrastructure/storage.yaml | grep -q "email"; then
        print_status 0 "EmailIndex GSI properly configured with email as partition key"
    else
        print_status 1 "EmailIndex GSI configuration incomplete"
    fi
else
    print_status 1 "EmailIndex GSI not found in storage.yaml"
fi

echo ""
echo "=== 2. Verifying IAM Permissions ==="

# Check if Lambda role has DynamoDB index permissions
if grep -A 20 "PolicyName: DynamoDBAccess" infrastructure/lambda.yaml | grep -q "table/\${LeadsTableName}/index/\*"; then
    print_status 0 "Lambda role has DynamoDB index permissions"
else
    print_status 1 "Lambda role missing DynamoDB index permissions"
fi

# Check if all required DynamoDB actions are included
required_actions=("dynamodb:Query" "dynamodb:PutItem" "dynamodb:UpdateItem" "dynamodb:BatchWriteItem")
missing_actions=()

for action in "${required_actions[@]}"; do
    if grep -A 15 "PolicyName: DynamoDBAccess" infrastructure/lambda.yaml | grep -q "$action"; then
        print_status 0 "IAM permission for $action found"
    else
        missing_actions+=("$action")
        print_status 1 "IAM permission for $action missing"
    fi
done

echo ""
echo "=== 3. Verifying Lambda Environment Variables ==="

# Check DeepSeek Caller environment variables
if grep -A 20 "DeepSeekCallerFunction:" infrastructure/lambda.yaml | grep -q "LEADS_TABLE"; then
    print_status 0 "DeepSeek Caller has LEADS_TABLE environment variable"
else
    print_status 1 "DeepSeek Caller missing LEADS_TABLE environment variable"
fi

if grep -A 20 "DeepSeekCallerFunction:" infrastructure/lambda.yaml | grep -q "DEEPSEEK_API_KEY"; then
    print_status 0 "DeepSeek Caller has DEEPSEEK_API_KEY environment variable"
else
    print_status 1 "DeepSeek Caller missing DEEPSEEK_API_KEY environment variable"
fi

echo ""
echo "=== 4. Verifying Duplicate Handling Implementation ==="

# Check if find_lead_by_email method exists
if grep -q "def find_lead_by_email" lambda/shared/dynamodb_utils.py; then
    print_status 0 "find_lead_by_email method implemented"
    
    # Check if it uses EmailIndex GSI
    if grep -A 20 "def find_lead_by_email" lambda/shared/dynamodb_utils.py | grep -q "EmailIndex"; then
        print_status 0 "find_lead_by_email uses EmailIndex GSI"
    else
        print_status 1 "find_lead_by_email does not use EmailIndex GSI"
    fi
else
    print_status 1 "find_lead_by_email method not found"
fi

# Check if batch_upsert_leads method exists
if grep -q "def batch_upsert_leads" lambda/shared/dynamodb_utils.py; then
    print_status 0 "batch_upsert_leads method implemented"
else
    print_status 1 "batch_upsert_leads method not found"
fi

# Check if EmailNormalizer is imported and used
if grep -q "from email_utils import EmailNormalizer" lambda/shared/dynamodb_utils.py; then
    print_status 0 "EmailNormalizer imported in DynamoDB utils"
else
    print_status 1 "EmailNormalizer not imported in DynamoDB utils"
fi

echo ""
echo "=== 5. Verifying DeepSeek Caller Integration ==="

# Check if DeepSeek Caller uses batch_upsert_leads
if grep -q "batch_upsert_leads" lambda/deepseek-caller/lambda_function.py; then
    print_status 0 "DeepSeek Caller uses batch_upsert_leads for duplicate handling"
else
    print_status 1 "DeepSeek Caller not using batch_upsert_leads"
fi

# Check if duplicate handling logging is implemented
if grep -q "log_duplicate_handling_summary" lambda/deepseek-caller/lambda_function.py; then
    print_status 0 "Duplicate handling logging implemented"
else
    print_status 1 "Duplicate handling logging not found"
fi

echo ""
echo "=== 6. Verifying Email Utilities ==="

# Check if email_utils.py exists
if [ -f "lambda/shared/email_utils.py" ]; then
    print_status 0 "email_utils.py exists"
    
    # Check if EmailNormalizer class exists
    if grep -q "class EmailNormalizer" lambda/shared/email_utils.py; then
        print_status 0 "EmailNormalizer class implemented"
    else
        print_status 1 "EmailNormalizer class not found"
    fi
    
    # Check if normalize_email method exists
    if grep -q "def normalize_email" lambda/shared/email_utils.py; then
        print_status 0 "normalize_email method implemented"
    else
        print_status 1 "normalize_email method not found"
    fi
else
    print_status 1 "email_utils.py not found"
fi

echo ""
echo "=== 7. Verifying Test Coverage ==="

# Check if duplicate handling tests exist
test_files=(
    "tests/unit/test_email_utils.py"
    "tests/unit/test_dynamodb_duplicate_utils.py"
    "tests/integration/test_duplicate_detection_integration.py"
    "tests/integration/test_duplicate_handling_workflow.py"
)

for test_file in "${test_files[@]}"; do
    if [ -f "$test_file" ]; then
        print_status 0 "Test file exists: $test_file"
    else
        print_status 1 "Test file missing: $test_file"
    fi
done

echo ""
echo "=== Configuration Verification Summary ==="

# Count issues
total_checks=0
passed_checks=0

# This is a simplified check - in a real implementation, we'd track each check result
echo ""
print_warning "Manual verification required for AWS deployment:"
echo "  1. Verify EmailIndex GSI exists in deployed DynamoDB table"
echo "  2. Test duplicate detection with sample data"
echo "  3. Verify Lambda function permissions in AWS Console"
echo "  4. Run integration tests to validate end-to-end functionality"

echo ""
echo "=== Next Steps ==="
echo "1. Run: aws sso login --profile nch-prod"
echo "2. Run: ./scripts/validate-templates.sh"
echo "3. Run: ./scripts/validate-deployment.sh"
echo "4. Run: python -m pytest tests/integration/test_duplicate_handling_workflow.py -v"

echo ""
echo "[INFO] Configuration verification completed."