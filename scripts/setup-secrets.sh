#!/bin/bash
# Setup API Keys in AWS Secrets Manager
# Run this after Phase 0 CloudFormation deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="${PROJECT_NAME:-smartroute}"
AWS_REGION="${AWS_REGION:-us-east-1}"
SECRET_NAME="${PROJECT_NAME}/api-keys"

echo -e "${YELLOW}SmartRoute API Keys Setup${NC}"
echo "======================================"
echo "Project: $PROJECT_NAME"
echo "Region: $AWS_REGION"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}ERROR: AWS CLI is not installed${NC}"
    exit 1
fi

# Load .env if it exists
if [ -f ".env" ]; then
    echo -e "${GREEN}Loading .env file...${NC}"
    export $(cat .env | grep -v '#' | xargs)
fi

# Prompt for API keys if not set
if [ -z "$MTA_API_KEY" ]; then
    echo -e "${YELLOW}Enter your MTA API Key (get from http://new.mta.info/developers):${NC}"
    read -s MTA_API_KEY
    echo ""
fi

if [ -z "$GOOGLE_MAPS_API_KEY" ]; then
    echo -e "${YELLOW}Enter your Google Maps API Key:${NC}"
    read -s GOOGLE_MAPS_API_KEY
    echo ""
fi

# Validate that we have keys
if [ -z "$MTA_API_KEY" ] || [ -z "$GOOGLE_MAPS_API_KEY" ]; then
    echo -e "${RED}ERROR: Missing required API keys${NC}"
    exit 1
fi

# Create or update the secret
echo -e "${YELLOW}Updating Secrets Manager...${NC}"

SECRET_JSON=$(cat <<EOF
{
  "mta_api_key": "$MTA_API_KEY",
  "google_maps_api_key": "$GOOGLE_MAPS_API_KEY"
}
EOF
)

# Check if secret exists
if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region "$AWS_REGION" 2>/dev/null; then
    # Update existing secret
    echo -e "${YELLOW}Updating existing secret...${NC}"
    aws secretsmanager update-secret \
        --secret-id "$SECRET_NAME" \
        --secret-string "$SECRET_JSON" \
        --region "$AWS_REGION" \
        > /dev/null
else
    # Create new secret
    echo -e "${YELLOW}Creating new secret...${NC}"
    aws secretsmanager create-secret \
        --name "$SECRET_NAME" \
        --secret-string "$SECRET_JSON" \
        --region "$AWS_REGION" \
        > /dev/null
fi

echo -e "${GREEN}✓ API Keys successfully stored in Secrets Manager${NC}"
echo ""
echo "Verification:"
aws secretsmanager get-secret-value \
    --secret-id "$SECRET_NAME" \
    --region "$AWS_REGION" \
    --query SecretString \
    --output text | python3 -m json.tool | head -n 4

echo ""
echo -e "${GREEN}Setup complete!${NC}"
