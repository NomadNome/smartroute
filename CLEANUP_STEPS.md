# SmartRoute Phase 5 - Cleanup Steps Before SAM Deployment

## Overview
This document provides AWS CLI commands to clean up existing resources before deploying the new SAM template. This prevents CloudFormation conflicts and ensures a clean, repeatable deployment.

---

## Prerequisites
- AWS CLI installed and configured with appropriate credentials
- AWS region set to `us-east-1` (or update commands accordingly)
- Sufficient IAM permissions to delete Lambda, DynamoDB, IAM, EventBridge, and API Gateway resources

---

## Cleanup Steps

### 1. Delete EventBridge Rule & Associated Targets

```bash
# Delete the EventBridge rule that triggers the daily safety aggregator
aws events remove-targets \
  --rule smartroute-daily-safety-aggregation \
  --ids "1" \
  --region us-east-1

aws events delete-rule \
  --name smartroute-daily-safety-aggregation \
  --region us-east-1
```

**Expected Output:**
- No error if rule exists, or: `ResourceNotFoundException: An error occurred (ResourceNotFoundException) when calling the DeleteRule operation: Rule does not exist.`

---

### 2. Delete Lambda Functions

```bash
# Delete the Daily Safety Aggregator Lambda
aws lambda delete-function \
  --function-name daily_safety_aggregator \
  --region us-east-1

# Delete the Bedrock Route Recommender Lambda
aws lambda delete-function \
  --function-name smartroute-route-recommender \
  --region us-east-1
```

**Note:** CloudWatch log groups for Lambda functions must be deleted separately (see Step 6).

---

### 3. Delete API Gateway Resources

```bash
# Find the REST API ID for SmartRoute-API
API_ID=$(aws apigateway get-rest-apis \
  --query "items[?name=='SmartRoute-API'].id" \
  --output text \
  --region us-east-1)

if [ -n "$API_ID" ]; then
  # Delete the API Gateway
  aws apigateway delete-rest-api \
    --rest-api-id $API_ID \
    --region us-east-1
  echo "Deleted API Gateway: $API_ID"
else
  echo "No SmartRoute-API found"
fi

# Delete API Key (if exists)
API_KEY_ID=$(aws apigateway get-api-keys \
  --query "items[?name=='SmartRoute-API-Key'].id" \
  --output text \
  --region us-east-1)

if [ -n "$API_KEY_ID" ]; then
  aws apigateway delete-api-key \
    --api-key $API_KEY_ID \
    --region us-east-1
  echo "Deleted API Key: $API_KEY_ID"
else
  echo "No SmartRoute-API-Key found"
fi
```

---

### 4. Delete DynamoDB Tables

**⚠️ WARNING: This will permanently delete all data in these tables. Ensure backups exist if needed.**

```bash
# Delete Route Cache Table
aws dynamodb delete-table \
  --table-name smartroute-route-cache \
  --region us-east-1

# Delete Station Realtime State Table
aws dynamodb delete-table \
  --table-name smartroute_station_realtime_state \
  --region us-east-1

# Delete User Sessions Table
aws dynamodb delete-table \
  --table-name smartroute_user_sessions \
  --region us-east-1

# Delete Safety Scores Table
aws dynamodb delete-table \
  --table-name SmartRoute_Safety_Scores \
  --region us-east-1

echo "Submitted delete requests for 4 DynamoDB tables"
echo "Deletion typically takes 10-30 seconds per table"
```

**Monitor deletion status:**
```bash
aws dynamodb describe-table \
  --table-name SmartRoute_Safety_Scores \
  --region us-east-1 \
  --query 'Table.TableStatus'
```

---

### 5. Delete IAM Roles & Policies

```bash
# Delete Daily Safety Aggregator Role
# First, detach all inline policies
aws iam list-role-policies \
  --role-name SmartRoute-DailySafetyAggregator-Role \
  --query 'PolicyNames[]' \
  --output text | \
  xargs -I {} aws iam delete-role-policy \
    --role-name SmartRoute-DailySafetyAggregator-Role \
    --policy-name {}

# Then delete the role
aws iam delete-role \
  --role-name SmartRoute-DailySafetyAggregator-Role

# Delete Bedrock Route Recommender Role
# First, detach all inline policies
aws iam list-role-policies \
  --role-name SmartRoute-BedrockRouteRecommender-Role \
  --query 'PolicyNames[]' \
  --output text | \
  xargs -I {} aws iam delete-role-policy \
    --role-name SmartRoute-BedrockRouteRecommender-Role \
    --policy-name {}

# Then delete the role
aws iam delete-role \
  --role-name SmartRoute-BedrockRouteRecommender-Role

echo "Deleted IAM roles"
```

---

### 6. Delete CloudWatch Resources

```bash
# Delete CloudWatch Log Groups
aws logs delete-log-group \
  --log-group-name /aws/lambda/daily_safety_aggregator \
  --region us-east-1

aws logs delete-log-group \
  --log-group-name /aws/lambda/smartroute-route-recommender \
  --region us-east-1

# Delete CloudWatch Alarms
aws cloudwatch delete-alarms \
  --alarm-names "SmartRoute-DailySafetyAggregator-Failures" \
    "SmartRoute-RouteRecommender-HighLatency" \
    "SmartRoute-DynamoDB-UserErrors" \
  --region us-east-1

# Delete CloudWatch Dashboard
aws cloudwatch delete-dashboards \
  --dashboard-names SmartRoute-Phase5-Dashboard \
  --region us-east-1

echo "Deleted CloudWatch resources"
```

---

## Automated Cleanup Script

For convenience, here's a bash script that runs all cleanup steps:

```bash
#!/bin/bash
set -e

REGION="us-east-1"
echo "🧹 Starting SmartRoute cleanup..."

# 1. Delete EventBridge rule
echo "1/6 Deleting EventBridge rule..."
aws events remove-targets --rule smartroute-daily-safety-aggregation --ids "1" --region $REGION 2>/dev/null || true
aws events delete-rule --name smartroute-daily-safety-aggregation --region $REGION 2>/dev/null || true

# 2. Delete Lambda functions
echo "2/6 Deleting Lambda functions..."
aws lambda delete-function --function-name daily_safety_aggregator --region $REGION 2>/dev/null || true
aws lambda delete-function --function-name smartroute-route-recommender --region $REGION 2>/dev/null || true

# 3. Delete API Gateway
echo "3/6 Deleting API Gateway resources..."
API_ID=$(aws apigateway get-rest-apis --query "items[?name=='SmartRoute-API'].id" --output text --region $REGION 2>/dev/null || true)
if [ -n "$API_ID" ]; then
  aws apigateway delete-rest-api --rest-api-id $API_ID --region $REGION 2>/dev/null || true
fi
API_KEY_ID=$(aws apigateway get-api-keys --query "items[?name=='SmartRoute-API-Key'].id" --output text --region $REGION 2>/dev/null || true)
if [ -n "$API_KEY_ID" ]; then
  aws apigateway delete-api-key --api-key $API_KEY_ID --region $REGION 2>/dev/null || true
fi

# 4. Delete DynamoDB tables
echo "4/6 Deleting DynamoDB tables..."
aws dynamodb delete-table --table-name smartroute-route-cache --region $REGION 2>/dev/null || true
aws dynamodb delete-table --table-name smartroute_station_realtime_state --region $REGION 2>/dev/null || true
aws dynamodb delete-table --table-name smartroute_user_sessions --region $REGION 2>/dev/null || true
aws dynamodb delete-table --table-name SmartRoute_Safety_Scores --region $REGION 2>/dev/null || true

# 5. Delete IAM roles
echo "5/6 Deleting IAM roles..."
for ROLE in "SmartRoute-DailySafetyAggregator-Role" "SmartRoute-BedrockRouteRecommender-Role"; do
  aws iam list-role-policies --role-name $ROLE --query 'PolicyNames[]' --output text 2>/dev/null | \
    xargs -I {} aws iam delete-role-policy --role-name $ROLE --policy-name {} 2>/dev/null || true
  aws iam delete-role --role-name $ROLE 2>/dev/null || true
done

# 6. Delete CloudWatch resources
echo "6/6 Deleting CloudWatch resources..."
aws logs delete-log-group --log-group-name /aws/lambda/daily_safety_aggregator --region $REGION 2>/dev/null || true
aws logs delete-log-group --log-group-name /aws/lambda/smartroute-route-recommender --region $REGION 2>/dev/null || true
aws cloudwatch delete-alarms --alarm-names "SmartRoute-DailySafetyAggregator-Failures" \
  "SmartRoute-RouteRecommender-HighLatency" "SmartRoute-DynamoDB-UserErrors" --region $REGION 2>/dev/null || true
aws cloudwatch delete-dashboards --dashboard-names SmartRoute-Phase5-Dashboard --region $REGION 2>/dev/null || true

echo "✅ Cleanup completed!"
echo ""
echo "Next step: Deploy the SAM template"
echo "  sam deploy --template-file template.yaml --guided"
```

**Save and run the script:**
```bash
chmod +x cleanup.sh
./cleanup.sh
```

---

## Deployment After Cleanup

Once cleanup is complete, deploy the new SAM template:

```bash
# From the project root directory
sam build

sam deploy \
  --template-file template.yaml \
  --stack-name smartroute-phase5 \
  --region us-east-1 \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    EnvironmentName=production \
    AthenaDatabase=smartroute_data \
    AthenaOutputBucket=smartroute-data-lake-069899605581 \
    ApiKeyEnabled=true \
    RateLimitPerDay=10000
```

**Or use guided mode:**
```bash
sam deploy --guided
```

---

## Post-Deployment Verification

After deployment, verify resources were created:

```bash
# List created stacks
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE \
  --region us-east-1 \
  --query 'StackSummaries[?StackName==`smartroute-phase5`]'

# Get CloudFormation outputs
aws cloudformation describe-stacks \
  --stack-name smartroute-phase5 \
  --region us-east-1 \
  --query 'Stacks[0].Outputs'

# Verify DynamoDB tables
aws dynamodb list-tables --region us-east-1

# Verify Lambda functions
aws lambda list-functions \
  --region us-east-1 \
  --query 'Functions[?contains(FunctionName, `smartroute`)]'
```

---

## Troubleshooting

### Issue: "Resource in use" error during deletion
**Solution:** Wait a few seconds and retry. Some AWS resources have dependencies that must be cleaned up first.

### Issue: IAM role still exists after deletion
**Solution:** Ensure all inline policies are deleted before deleting the role:
```bash
aws iam list-role-policies --role-name <RoleName>
aws iam delete-role-policy --role-name <RoleName> --policy-name <PolicyName>
aws iam delete-role --role-name <RoleName>
```

### Issue: DynamoDB table deletion takes too long
**Solution:** Deletion can take 10-30 seconds per table. Run the status check periodically:
```bash
aws dynamodb describe-table --table-name <TableName> --query 'Table.TableStatus'
```

### Issue: Lambda function deletion fails
**Solution:** Ensure all associated resources (log groups, EventBridge rules) are deleted first.

---

## Rollback Instructions

If you need to restore the previous environment:

1. **Keep manual backups** before running cleanup
2. **Use CloudFormation stack snapshots** if available in AWS Console
3. **Restore from S3 backups** if data persistence is critical

For critical production data, always:
- Enable DynamoDB Point-in-Time Recovery (PITR) before deletion
- Create on-demand backups before major changes
- Test cleanup procedures in development first

---

## Summary

| Resource | Cleanup Method | Impact | Reversible |
|----------|----------------|--------|-----------|
| EventBridge Rule | AWS CLI delete | Stops daily aggregation | No |
| Lambda Functions | AWS CLI delete | Removes serverless functions | No |
| API Gateway | AWS CLI delete | Breaks API endpoints | No |
| DynamoDB Tables | AWS CLI delete | **Deletes all data** | No* |
| IAM Roles | AWS CLI delete | Removes permissions | No |
| CloudWatch | AWS CLI delete | Removes monitoring | No |

*DynamoDB can be recovered if Point-in-Time Recovery (PITR) was enabled.

---

**Last Updated:** 2025-11-18
**Status:** Ready for SAM deployment
