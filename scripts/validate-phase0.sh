#!/bin/bash
# Validate Phase 0 Infrastructure Deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="${PROJECT_NAME:-smartroute}"
AWS_REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${PROJECT_NAME}-phase0"

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Phase 0 Validation Check             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

ERRORS=0
WARNINGS=0

# Function to check item
check_resource() {
    local description=$1
    local command=$2

    echo -n "Checking $description... "
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        return 0
    else
        echo -e "${RED}✗${NC}"
        ((ERRORS++))
        return 1
    fi
}

# Function to check with warning
check_optional() {
    local description=$1
    local command=$2

    echo -n "Checking $description... "
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠${NC}"
        ((WARNINGS++))
        return 1
    fi
}

echo -e "${YELLOW}AWS Credentials:${NC}"
check_resource "AWS CLI" "aws --version"
check_resource "AWS Identity" "aws sts get-caller-identity --region $AWS_REGION"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "  Account ID: $ACCOUNT_ID"
echo ""

echo -e "${YELLOW}CloudFormation Stack:${NC}"
check_resource "Stack Exists" "aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION"

STACK_STATUS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

echo "  Status: $STACK_STATUS"
echo ""

echo -e "${YELLOW}S3 Buckets:${NC}"
check_resource "Data Lake Bucket" "aws s3 ls ${PROJECT_NAME}-data-lake-${ACCOUNT_ID} --region $AWS_REGION"
check_resource "Logs Bucket" "aws s3 ls ${PROJECT_NAME}-logs-${ACCOUNT_ID} --region $AWS_REGION"
check_resource "Config Bucket" "aws s3 ls ${PROJECT_NAME}-config-${ACCOUNT_ID} --region $AWS_REGION"

# List bucket contents
echo "  Data Lake contents:"
aws s3 ls "s3://${PROJECT_NAME}-data-lake-${ACCOUNT_ID}/" --region "$AWS_REGION" | sed 's/^/    /'
echo ""

echo -e "${YELLOW}DynamoDB Tables:${NC}"
check_resource "Station Realtime Table" "aws dynamodb describe-table --table-name ${PROJECT_NAME}_station_realtime_state --region $AWS_REGION"
check_resource "Cached Routes Table" "aws dynamodb describe-table --table-name ${PROJECT_NAME}_cached_routes --region $AWS_REGION"
check_resource "User Sessions Table" "aws dynamodb describe-table --table-name ${PROJECT_NAME}_user_sessions --region $AWS_REGION"
echo ""

echo -e "${YELLOW}IAM Roles:${NC}"
check_resource "Lambda Execution Role" "aws iam get-role --role-name ${PROJECT_NAME}-lambda-execution-role"
check_resource "Glue Execution Role" "aws iam get-role --role-name ${PROJECT_NAME}-glue-execution-role"
check_resource "EventBridge Role" "aws iam get-role --role-name ${PROJECT_NAME}-eventbridge-role"
echo ""

echo -e "${YELLOW}CloudWatch Log Groups:${NC}"
check_optional "MTA Poller Logs" "aws logs describe-log-groups --log-group-name-prefix /aws/lambda/${PROJECT_NAME}/mta-poller --region $AWS_REGION"
check_optional "Route Handler Logs" "aws logs describe-log-groups --log-group-name-prefix /aws/lambda/${PROJECT_NAME}/route-handler --region $AWS_REGION"
echo ""

echo -e "${YELLOW}Secrets Manager:${NC}"
check_optional "API Keys Secret" "aws secretsmanager describe-secret --secret-id ${PROJECT_NAME}/api-keys --region $AWS_REGION"
echo ""

echo -e "${YELLOW}SNS Topics:${NC}"
check_resource "Alarm Topic" "aws sns list-topics --region $AWS_REGION | grep -q ${PROJECT_NAME}-alarms"
echo ""

echo -e "${YELLOW}CloudWatch Dashboards:${NC}"
check_optional "Phase 0 Dashboard" "aws cloudwatch get-dashboard --dashboard-name ${PROJECT_NAME}-phase0-overview --region $AWS_REGION"
echo ""

# Summary
echo -e "${BLUE}════════════════════════════════════════${NC}"

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo -e "${YELLOW}Phase 0 Infrastructure Status: HEALTHY${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ $WARNINGS warnings found${NC}"
    echo ""
    echo -e "${YELLOW}Phase 0 Infrastructure Status: MOSTLY HEALTHY${NC}"
    exit 0
else
    echo -e "${RED}✗ $ERRORS errors found, $WARNINGS warnings${NC}"
    echo ""
    echo -e "${RED}Phase 0 Infrastructure Status: UNHEALTHY${NC}"
    echo ""
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo "  1. Check CloudFormation events: aws cloudformation describe-stack-events --stack-name $STACK_NAME"
    echo "  2. Check CloudWatch logs for errors"
    echo "  3. Ensure all prerequisites are installed"
    exit 1
fi
