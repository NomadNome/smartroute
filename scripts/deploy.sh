#!/bin/bash
# Deploy Phase 0 CloudFormation Stack
# Usage: ./deploy.sh [phase] [environment]

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
PHASE="${1:-0}"
ENVIRONMENT="${2:-development}"
ACCOUNT_ID="${ACCOUNT_ID:-}"

# Derived values
STACK_NAME="${PROJECT_NAME}-phase${PHASE}"
TEMPLATE_FILE="infrastructure/cloudformation/phase-${PHASE}-foundation.yaml"

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   SmartRoute CloudFormation Deployer   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo "  Project Name: $PROJECT_NAME"
echo "  Stack Name: $STACK_NAME"
echo "  Phase: $PHASE"
echo "  Environment: $ENVIRONMENT"
echo "  Region: $AWS_REGION"
echo "  Template: $TEMPLATE_FILE"
echo ""

# Validate prerequisites
echo -e "${YELLOW}Validating prerequisites...${NC}"

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}✗ AWS CLI is not installed${NC}"
    echo "  Install from: https://aws.amazon.com/cli/"
    exit 1
fi
echo -e "${GREEN}✓ AWS CLI found${NC}"

# Check AWS credentials
if ! aws sts get-caller-identity --region "$AWS_REGION" > /dev/null 2>&1; then
    echo -e "${RED}✗ AWS credentials not configured${NC}"
    echo "  Run: aws configure"
    exit 1
fi
echo -e "${GREEN}✓ AWS credentials configured${NC}"

# Get Account ID if not provided
if [ -z "$ACCOUNT_ID" ]; then
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
fi
echo -e "${GREEN}✓ AWS Account ID: $ACCOUNT_ID${NC}"

# Check if template exists
if [ ! -f "$TEMPLATE_FILE" ]; then
    echo -e "${RED}✗ Template file not found: $TEMPLATE_FILE${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Template file found${NC}"

# Validate CloudFormation template
echo -e "${YELLOW}Validating CloudFormation template...${NC}"
if aws cloudformation validate-template \
    --template-body file://"$TEMPLATE_FILE" \
    --region "$AWS_REGION" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Template validation passed${NC}"
else
    echo -e "${RED}✗ Template validation failed${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Deploying CloudFormation Stack...${NC}"
echo ""

# Deploy or update stack
if aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" > /dev/null 2>&1; then

    echo -e "${YELLOW}Stack exists. Updating...${NC}"

    aws cloudformation update-stack \
        --stack-name "$STACK_NAME" \
        --template-body file://"$TEMPLATE_FILE" \
        --parameters \
            ParameterKey=ProjectName,ParameterValue="$PROJECT_NAME" \
            ParameterKey=Environment,ParameterValue="$ENVIRONMENT" \
            ParameterKey=AccountId,ParameterValue="$ACCOUNT_ID" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$AWS_REGION"

    # Wait for update to complete
    echo -e "${YELLOW}Waiting for stack update to complete...${NC}"
    aws cloudformation wait stack-update-complete \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION"

    echo -e "${GREEN}✓ Stack update complete${NC}"

else
    echo -e "${YELLOW}Stack does not exist. Creating...${NC}"

    aws cloudformation create-stack \
        --stack-name "$STACK_NAME" \
        --template-body file://"$TEMPLATE_FILE" \
        --parameters \
            ParameterKey=ProjectName,ParameterValue="$PROJECT_NAME" \
            ParameterKey=Environment,ParameterValue="$ENVIRONMENT" \
            ParameterKey=AccountId,ParameterValue="$ACCOUNT_ID" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$AWS_REGION"

    # Wait for creation to complete
    echo -e "${YELLOW}Waiting for stack creation to complete...${NC}"
    aws cloudformation wait stack-create-complete \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION"

    echo -e "${GREEN}✓ Stack creation complete${NC}"
fi

echo ""
echo -e "${YELLOW}Retrieving stack outputs...${NC}"
echo ""

# Display outputs
aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Deployment Successful! ✓            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""

# Next steps
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Update your .env file with the output values"
echo "  2. Add your API keys: ./scripts/setup-secrets.sh"
echo "  3. Proceed to Phase 1 deployment"
echo ""
