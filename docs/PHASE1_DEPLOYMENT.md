# Phase 1: Real-Time Data Ingestion - Deployment Guide

**Status**: Ready for deployment
**Prerequisites**: Phase 0 must be complete and healthy

---

## Quick Start (5 minutes)

```bash
# 1. Deploy Phase 1 CloudFormation
aws cloudformation create-stack \
  --stack-name smartroute-phase1 \
  --template-body file://infrastructure/cloudformation/phase-1-ingestion.yaml \
  --parameters ParameterKey=ProjectName,ParameterValue=smartroute \
  --region us-east-1

# 2. Wait for stack creation (5-10 minutes)
aws cloudformation wait stack-create-complete \
  --stack-name smartroute-phase1 \
  --region us-east-1

# 3. Package and upload Lambda code (TODO - see section below)

# 4. Verify data is flowing
aws dynamodb scan --table-name smartroute_station_realtime_state
```

---

## Detailed Deployment Steps

### Step 1: Deploy CloudFormation Stack

```bash
# Navigate to project root
cd smartroute-project

# Create the Phase 1 stack
aws cloudformation create-stack \
  --stack-name smartroute-phase1 \
  --template-body file://infrastructure/cloudformation/phase-1-ingestion.yaml \
  --parameters \
    ParameterKey=ProjectName,ParameterValue=smartroute \
    ParameterKey=Environment,ParameterValue=development \
    ParameterKey=LambdaMemory,ParameterValue=512 \
    ParameterKey=KinesisShards,ParameterValue=1 \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1

# Check status
aws cloudformation describe-stacks \
  --stack-name smartroute-phase1 \
  --region us-east-1 \
  --query 'Stacks[0].StackStatus'

# Wait for completion (5-10 minutes)
aws cloudformation wait stack-create-complete \
  --stack-name smartroute-phase1 \
  --region us-east-1
```

### Step 2: Build and Package Lambda Functions

```bash
# Create deployment package for MTA Poller
cd lambdas/mta-poller

# Create temp directory for dependencies
mkdir -p package
cd package

# Install dependencies
pip install -r ../requirements.txt -t .

# Copy Lambda code
cp ../lambda_function.py .

# Create zip
zip -r ../mta-poller.zip .
cd ..

# Get Lambda function name
LAMBDA_NAME=$(aws cloudformation describe-stacks \
  --stack-name smartroute-phase1 \
  --query 'Stacks[0].Outputs[?OutputKey==`MtaPollerFunctionName`].OutputValue' \
  --output text \
  --region us-east-1)

# Update Lambda code
aws lambda update-function-code \
  --function-name $LAMBDA_NAME \
  --zip-file fileb://mta-poller.zip \
  --region us-east-1

echo "✓ MTA Poller Lambda updated"

# Repeat for Real-Time Processor
cd ../realtime-processor
mkdir -p package
cd package
pip install boto3 aws-lambda-powertools -t .
cp ../lambda_function.py .
zip -r ../realtime-processor.zip .
cd ..

RT_LAMBDA=$(aws cloudformation describe-stacks \
  --stack-name smartroute-phase1 \
  --query 'Stacks[0].Outputs[?OutputKey==`RealtimeProcessorFunctionName`].OutputValue' \
  --output text \
  --region us-east-1)

aws lambda update-function-code \
  --function-name $RT_LAMBDA \
  --zip-file fileb://realtime-processor.zip \
  --region us-east-1

echo "✓ Real-Time Processor Lambda updated"
```

### Step 3: Test MTA Poller Manually

```bash
# Get the Lambda function name
POLLER=$(aws cloudformation describe-stacks \
  --stack-name smartroute-phase1 \
  --query 'Stacks[0].Outputs[?OutputKey==`MtaPollerFunctionName`].OutputValue' \
  --output text \
  --region us-east-1)

# Invoke manually
aws lambda invoke \
  --function-name $POLLER \
  --region us-east-1 \
  response.json

# Check response
cat response.json | python3 -m json.tool
```

### Step 4: Monitor the Pipeline

```bash
# Watch CloudWatch logs
aws logs tail /aws/lambda/smartroute-mta-poller \
  --follow \
  --region us-east-1

# Check Kinesis stream
aws kinesis describe-stream \
  --stream-name smartroute_transit_data_stream \
  --region us-east-1

# Query DynamoDB for recent updates
aws dynamodb scan \
  --table-name smartroute_station_realtime_state \
  --limit 5 \
  --region us-east-1
```

### Step 5: View Dashboards

```bash
# View CloudWatch dashboard
echo "https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=smartroute-phase1-monitoring"

# View Lambda metrics
echo "https://console.aws.amazon.com/lambda/home?region=us-east-1#/functions/smartroute-mta-poller"
```

---

## Troubleshooting

### Lambda Returns "Placeholder" Response

**Problem**: Function returns the placeholder code

**Solution**:
```bash
# Make sure Lambda code was updated
aws lambda get-function-code --function-name smartroute-mta-poller

# Re-package and re-upload
cd lambdas/mta-poller
zip -r mta-poller.zip lambda_function.py requirements.txt
aws lambda update-function-code \
  --function-name smartroute-mta-poller \
  --zip-file fileb://mta-poller.zip
```

### "Secrets Manager Access Denied"

**Problem**: Lambda can't read API keys

**Solution**:
```bash
# Verify the Lambda role has permission
aws iam get-role-policy \
  --role-name smartroute-lambda-execution-role \
  --policy-name allow-secrets-manager

# If missing, add permission (should already be there from Phase 0)
```

### Kinesis "No Data in Stream"

**Problem**: Kinesis stream is empty

**Solution**:
```bash
# Check if EventBridge rule is enabled
aws events list-rules \
  --name-prefix smartroute-mta-poller \
  --region us-east-1

# Check if it triggered recently
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=PutRecord \
  --max-results 10 \
  --region us-east-1

# Check Lambda logs for errors
aws logs tail /aws/lambda/smartroute-mta-poller --follow
```

### DynamoDB Empty/Not Updating

**Problem**: DynamoDB table has no data

**Solution**:
```bash
# Check if Kinesis event source mapping is enabled
aws lambda list-event-source-mappings \
  --function-name smartroute-realtime-processor \
  --region us-east-1

# Check real-time processor logs
aws logs tail /aws/lambda/smartroute-realtime-processor --follow

# Test Kinesis consumption manually
# Put a test record
aws kinesis put-record \
  --stream-name smartroute_transit_data_stream \
  --data '{"test": "data"}' \
  --partition-key test \
  --region us-east-1

# Check DynamoDB for updates
aws dynamodb scan --table-name smartroute_station_realtime_state --limit 1
```

---

## Monitoring Checklist

After deployment, verify:

- [ ] CloudFormation stack status: CREATE_COMPLETE
- [ ] MTA Poller Lambda: Running every 30 seconds
- [ ] Kinesis stream: Receiving records
- [ ] DynamoDB: Being updated with latest arrivals
- [ ] CloudWatch dashboard: Showing metrics
- [ ] CloudWatch alarms: No active alarms
- [ ] CloudWatch logs: No ERROR level messages

---

## Performance Expectations

**Latency**:
- API call to Kinesis: ~2 seconds
- Kinesis to DynamoDB: <1 second
- **Total**: <3 seconds from API to searchable state

**Throughput**:
- 30 API calls per minute
- ~500 records per minute
- ~18,000 records per hour
- Kinesis: <100 KB/sec (well under 1 MB/sec limit)

**Costs**:
- Lambda: Free tier (well under 1M invocations)
- Kinesis: ~$26/month (1 shard)
- DynamoDB: ~$18/month (on-demand)
- **Total Phase 1**: ~$50-60/month

---

## Next Steps

Once Phase 1 is stable (24+ hours running):

1. **Start Phase 2**:
   - Create Glue ETL jobs for aggregation
   - Setup Redshift data warehouse
   - Create Athena queries

2. **Add Features**:
   - Implement real protobuf decoding
   - Add GTFS static data downloader
   - Implement crowding estimation

3. **Scale if Needed**:
   - Increase Kinesis shards
   - Add more Lambda consumers
   - Setup Lambda reserved concurrency

---

## Rollback

If you need to remove Phase 1:

```bash
# Delete the Phase 1 stack
aws cloudformation delete-stack \
  --stack-name smartroute-phase1 \
  --region us-east-1

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name smartroute-phase1 \
  --region us-east-1

echo "✓ Phase 1 stack deleted"
```

(Phase 0 stack will remain intact)

---

**Phase 1 is now ready for deployment!**

Use the Quick Start section above to get running in 5 minutes.
