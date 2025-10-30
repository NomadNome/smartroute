#!/bin/bash
# Clean up AWS Resources
# WARNING: This will DELETE resources!

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="${PROJECT_NAME:-smartroute}"
AWS_REGION="${AWS_REGION:-us-east-1}"
PHASE="${1:-0}"
STACK_NAME="${PROJECT_NAME}-phase${PHASE}"

echo -e "${RED}╔════════════════════════════════════════╗${NC}"
echo -e "${RED}║   WARNING: RESOURCE CLEANUP             ║${NC}"
echo -e "${RED}║   This will DELETE AWS resources!       ║${NC}"
echo -e "${RED}╚════════════════════════════════════════╝${NC}"
echo ""

echo "This operation will delete:"
echo "  - CloudFormation Stack: $STACK_NAME"
echo "  - S3 Buckets (with data)"
echo "  - DynamoDB Tables"
echo "  - IAM Roles"
echo "  - CloudWatch Log Groups"
echo ""
echo -e "${RED}THIS IS IRREVERSIBLE!${NC}"
echo ""

# Confirm deletion
echo -n "Type 'DELETE' to confirm: "
read -r CONFIRM

if [ "$CONFIRM" != "DELETE" ]; then
    echo -e "${GREEN}Cleanup cancelled.${NC}"
    exit 0
fi

echo ""
echo -e "${YELLOW}Starting cleanup...${NC}"

# Check if stack exists
if ! aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" > /dev/null 2>&1; then
    echo -e "${YELLOW}Stack not found: $STACK_NAME${NC}"
else
    # Get account ID
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

    # Empty S3 buckets first (CloudFormation can't delete non-empty buckets)
    echo -e "${YELLOW}Emptying S3 buckets...${NC}"

    for BUCKET in "${PROJECT_NAME}-data-lake-${ACCOUNT_ID}" "${PROJECT_NAME}-logs-${ACCOUNT_ID}" "${PROJECT_NAME}-config-${ACCOUNT_ID}"; do
        if aws s3 ls "s3://$BUCKET" --region "$AWS_REGION" > /dev/null 2>&1; then
            echo "  Deleting objects in $BUCKET..."
            aws s3 rm "s3://$BUCKET" --recursive --region "$AWS_REGION" || true
        fi
    done

    echo ""
    echo -e "${YELLOW}Deleting CloudFormation Stack...${NC}"
    aws cloudformation delete-stack \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION"

    echo -e "${YELLOW}Waiting for stack deletion...${NC}"
    aws cloudformation wait stack-delete-complete \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION" 2>/dev/null || true

fi

echo ""
echo -e "${GREEN}✓ Cleanup complete${NC}"
echo ""
echo "Remaining manual cleanup (if needed):"
echo "  - Delete Secrets Manager secrets"
echo "  - Delete SNS topics"
echo "  - Clean up CloudWatch dashboards"
echo ""
