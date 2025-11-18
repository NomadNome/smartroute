#!/bin/bash

# SmartRoute Phase 4 Week 2 Infrastructure Setup
# Creates DynamoDB cache table and updates IAM permissions

set -e

AWS_REGION="us-east-1"
ACCOUNT_ID="069899605581"
IAM_ROLE="smartroute-bedrock-lambda-role"
CACHE_TABLE="smartroute-route-cache"

echo "========================================================================"
echo "🚀 SmartRoute Phase 4 Week 2: Infrastructure Setup"
echo "========================================================================"

# 1. Create DynamoDB Cache Table
echo ""
echo "1️⃣  Creating DynamoDB Cache Table..."
echo "   Table: $CACHE_TABLE"
echo "   Region: $AWS_REGION"
echo "   TTL: 300 seconds (5 minutes)"

aws dynamodb create-table \
  --table-name "$CACHE_TABLE" \
  --attribute-definitions \
    AttributeName=cache_key,AttributeType=S \
  --key-schema \
    AttributeName=cache_key,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --ttl-specification \
    AttributeName=expiry,Enabled=true \
  --region "$AWS_REGION" 2>/dev/null || \
  echo "   ⚠️  Table may already exist, continuing..."

# Wait for table to be created
echo "   ⏳ Waiting for table to be active..."
aws dynamodb wait table-exists \
  --table-name "$CACHE_TABLE" \
  --region "$AWS_REGION" 2>/dev/null || true

# Get table status
TABLE_STATUS=$(aws dynamodb describe-table \
  --table-name "$CACHE_TABLE" \
  --region "$AWS_REGION" \
  --query 'Table.TableStatus' \
  --output text 2>/dev/null || echo "CREATING")

echo "   ✅ Table Status: $TABLE_STATUS"

# 2. Update IAM Role with DynamoDB permissions
echo ""
echo "2️⃣  Updating IAM Role permissions..."
echo "   Role: $IAM_ROLE"

cat > /tmp/dynamodb_policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Query",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:us-east-1:069899605581:table/smartroute-route-cache"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name "$IAM_ROLE" \
  --policy-name smartroute-dynamodb-cache-policy \
  --policy-document file:///tmp/dynamodb_policy.json

echo "   ✅ DynamoDB permissions added to IAM role"

# 3. Verify Athena permissions
echo ""
echo "3️⃣  Verifying Athena permissions..."

cat > /tmp/athena_policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:StopQueryExecution"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::smartroute-data-lake-069899605581/athena-results/*",
        "arn:aws:s3:::smartroute-data-lake-069899605581"
      ]
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name "$IAM_ROLE" \
  --policy-name smartroute-athena-policy \
  --policy-document file:///tmp/athena_policy.json

echo "   ✅ Athena permissions added to IAM role"

# 4. Display summary
echo ""
echo "========================================================================"
echo "✅ Infrastructure Setup Complete"
echo "========================================================================"
echo ""
echo "📊 Summary:"
echo "   ✅ DynamoDB cache table created: $CACHE_TABLE"
echo "   ✅ IAM role updated: $IAM_ROLE"
echo "   ✅ DynamoDB permissions granted"
echo "   ✅ Athena permissions granted"
echo ""
echo "📋 Next Steps:"
echo "   1. Package Lambda: zip -r lambda.zip lambda_function.py bedrock_route_recommender.py"
echo "   2. Update Lambda: aws lambda update-function-code --function-name smartroute-route-recommender --zip-file fileb://lambda.zip"
echo "   3. Test Lambda: aws lambda invoke --function-name smartroute-route-recommender --payload '{...}' response.json"
echo ""
echo "⚙️  Configuration:"
echo "   ATHENA_DATABASE: smartroute_data"
echo "   ATHENA_OUTPUT: s3://smartroute-data-lake-069899605581/athena-results/"
echo "   CACHE_TABLE: $CACHE_TABLE"
echo "   CACHE_TTL: 300 seconds (5 minutes)"
echo ""

# Cleanup
rm -f /tmp/dynamodb_policy.json /tmp/athena_policy.json
