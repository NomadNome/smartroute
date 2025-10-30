# SmartRoute Phase 0: Foundation Setup Guide

Complete step-by-step guide to setting up SmartRoute Phase 0 infrastructure on AWS.

**Estimated Time: 30-45 minutes**

---

## Prerequisites

Before starting, ensure you have:

- [ ] AWS Account (free tier eligible)
- [ ] AWS CLI v2 installed ([install guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html))
- [ ] Python 3.11+ ([download](https://www.python.org/downloads/))
- [ ] Git installed ([download](https://git-scm.com/))
- [ ] Text editor (VS Code recommended)
- [ ] MTA API Key (free at [MTA Developer Resources](http://new.mta.info/developers))
- [ ] Google Maps API Key (free trial at [Google Cloud Console](https://console.cloud.google.com/))

### Verify Prerequisites

```bash
# Check AWS CLI
aws --version
# Expected: aws-cli/2.x.x

# Check Python
python3 --version
# Expected: Python 3.11.x

# Check Git
git --version
# Expected: git version 2.x.x
```

---

## Step 1: Configure AWS CLI

If you haven't already configured AWS CLI, do it now:

```bash
aws configure
```

You'll be prompted for:
- **AWS Access Key ID**: Get from IAM console
- **AWS Secret Access Key**: Get from IAM console
- **Default region**: `us-east-1` (recommended for NYC data)
- **Default output format**: `json`

### Verify AWS Credentials

```bash
aws sts get-caller-identity

# Output should show:
# {
#   "UserId": "...",
#   "Account": "123456789012",
#   "Arn": "arn:aws:iam::123456789012:user/your-user"
# }
```

---

## Step 2: Clone Repository and Install Dependencies

```bash
# Clone the project
git clone <repository-url> smartroute-project
cd smartroute-project

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate  # Windows

# Install Python dependencies
pip install -r requirements.txt
```

---

## Step 3: Configure Environment Variables

### Create .env File

```bash
# Copy the example file
cp .env.example .env

# Edit with your settings
nano .env
# (or use your preferred editor)
```

### Update .env with Your Details

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_PROFILE=default

# Get your account ID (don't edit this yet, we'll fill it in later)
AWS_ACCOUNT_ID=123456789012

# API Keys (get these from their respective services)
MTA_API_KEY=YOUR_MTA_KEY_HERE
GOOGLE_MAPS_API_KEY=YOUR_GOOGLE_MAPS_KEY_HERE

# Keep other values as defaults for now
```

### Get Your AWS Account ID

```bash
# Find your account ID
aws sts get-caller-identity --query Account --output text

# Update .env with this value
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
sed -i '' "s/AWS_ACCOUNT_ID=.*/AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID}/" .env
```

---

## Step 4: Deploy Phase 0 Infrastructure

### Review the CloudFormation Template

Before deploying, review what we're creating:

```bash
cat infrastructure/cloudformation/phase-0-foundation.yaml | head -50

# Key resources:
# - S3 Buckets (data-lake, logs, config)
# - DynamoDB Tables (station state, cached routes, user sessions)
# - IAM Roles (Lambda, Glue, EventBridge)
# - CloudWatch Log Groups
# - SNS Topics for alarms
```

### Run Deployment Script

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Deploy Phase 0
./scripts/deploy.sh 0 development

# This will:
# 1. Validate AWS credentials
# 2. Validate CloudFormation template
# 3. Create/update the CloudFormation stack
# 4. Wait for completion (5-10 minutes)
# 5. Display outputs
```

### Expected Output

```
SmartRoute CloudFormation Deployer

Configuration:
  Project Name: smartroute
  Stack Name: smartroute-phase0
  Phase: 0
  Environment: development
  Region: us-east-1
  Template: infrastructure/cloudformation/phase-0-foundation.yaml

Validating prerequisites...
✓ AWS CLI found
✓ AWS credentials configured
✓ AWS Account ID: 123456789012
✓ Template file found
✓ Template validation passed

Deploying CloudFormation Stack...

Stack does not exist. Creating...

Waiting for stack creation to complete...
✓ Stack creation complete

Retrieving stack outputs...

OutputKey              | OutputValue
-----------------------|-------------------------------------------
DataLakeBucketName    | smartroute-data-lake-123456789012
DataLakeBucketArn     | arn:aws:s3:::smartroute-data-lake-123456789012
LogsBucketName        | smartroute-logs-123456789012
...
```

---

## Step 5: Update .env with Stack Outputs

After deployment, update your .env file with the outputs:

```bash
# View the stack outputs again
aws cloudformation describe-stacks \
  --stack-name smartroute-phase0 \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table

# Update .env with these values
# S3_DATA_LAKE_BUCKET=smartroute-data-lake-123456789012
# S3_LOGS_BUCKET=smartroute-logs-123456789012
# etc.
```

---

## Step 6: Add API Keys to Secrets Manager

```bash
# Run the secrets setup script
./scripts/setup-secrets.sh

# Or manually if you prefer:
aws secretsmanager update-secret \
  --secret-id smartroute/api-keys \
  --secret-string '{
    "mta_api_key": "YOUR_KEY_HERE",
    "google_maps_api_key": "YOUR_KEY_HERE"
  }' \
  --region us-east-1

# Verify the secret was created
aws secretsmanager get-secret-value \
  --secret-id smartroute/api-keys \
  --region us-east-1 \
  --query SecretString \
  --output text | python3 -m json.tool
```

---

## Step 7: Validate Phase 0 Infrastructure

Run the validation script to ensure everything is set up correctly:

```bash
./scripts/validate-phase0.sh

# Expected output:
# ════════════════════════════════════════
# Phase 0 Validation Check
# ════════════════════════════════════════

# AWS Credentials:
# ✓ AWS CLI found
# ✓ AWS Identity
#   Account ID: 123456789012

# CloudFormation Stack:
# ✓ Stack Exists
#   Status: CREATE_COMPLETE

# S3 Buckets:
# ✓ Data Lake Bucket
# ✓ Logs Bucket
# ✓ Config Bucket

# DynamoDB Tables:
# ✓ Station Realtime Table
# ✓ Cached Routes Table
# ✓ User Sessions Table

# IAM Roles:
# ✓ Lambda Execution Role
# ✓ Glue Execution Role
# ✓ EventBridge Role

# ... and more

# ════════════════════════════════════════
# ✓ All checks passed!
# Phase 0 Infrastructure Status: HEALTHY
```

---

## Step 8: Commit to Git

Save your progress:

```bash
# Initialize git (if not already done)
git init

# Add files
git add .
git commit -m "Phase 0: Foundation infrastructure deployed

- Configured AWS CLI and credentials
- Created S3 data lake buckets
- Created DynamoDB tables
- Set up IAM roles
- Configured CloudWatch monitoring
- Added API keys to Secrets Manager"

# Optional: Push to remote
git remote add origin <your-repo-url>
git push -u origin main
```

---

## Troubleshooting

### CloudFormation Stack Creation Failed

**Problem**: Stack creation shows errors

**Solution**:
```bash
# View stack events
aws cloudformation describe-stack-events \
  --stack-name smartroute-phase0 \
  --region us-east-1 \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]' \
  --output table

# Common issues:
# - Role naming conflict: Choose different role names in template
# - IAM permissions: Ensure your user has iam:CreateRole, iam:PutRolePolicy
# - Resource already exists: Delete conflicting resources first
```

### AWS CLI Not Found

**Problem**: `aws: command not found`

**Solution**:
```bash
# Install AWS CLI v2
# macOS with Homebrew:
brew install awscli

# Or download from:
# https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

# Verify installation
aws --version
```

### AWS Credentials Not Configured

**Problem**: `Unable to locate credentials`

**Solution**:
```bash
# Configure credentials
aws configure

# Or set environment variables:
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

### S3 Bucket Already Exists

**Problem**: `BucketAlreadyOwnedByYou` error

**Solution**:
```bash
# S3 bucket names must be globally unique
# Change the bucket name in the template:
sed -i '' 's/${ProjectName}/${ProjectName}-unique123/' infrastructure/cloudformation/phase-0-foundation.yaml

# Or delete the existing bucket:
aws s3 rb s3://smartroute-data-lake-123456789012 --force --region us-east-1
```

### DynamoDB Table Creation Slow

**Problem**: DynamoDB table creation seems stuck

**Solution**:
```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name smartroute-phase0 \
  --region us-east-1 \
  --query 'Stacks[0].StackStatus'

# Check specific resource status
aws cloudformation list-stack-resources \
  --stack-name smartroute-phase0 \
  --region us-east-1
```

---

## What Was Created

### S3 Buckets
- `smartroute-data-lake-{ACCOUNT_ID}`: Main data lake for raw/processed data
- `smartroute-logs-{ACCOUNT_ID}`: Centralized logging
- `smartroute-config-{ACCOUNT_ID}`: Configuration files

**Lifecycle Policies**:
- Raw data → Standard-IA after 30 days
- Standard-IA → Glacier after 90 days
- Logs deleted after 90 days

### DynamoDB Tables
- `smartroute_station_realtime_state`: Real-time station data (TTL: 600s)
- `smartroute_cached_routes`: Cached route calculations (TTL: 3600s)
- `smartroute_user_sessions`: User session management (TTL: 86400s)

**Billing Mode**: On-demand (no minimum costs)

### IAM Roles
- **LambdaExecutionRole**: For Lambda functions
  - S3, DynamoDB, Kinesis, Bedrock, SecretsManager access
  - CloudWatch Logs
- **GlueExecutionRole**: For Glue ETL jobs
  - S3 access
- **EventBridgeRole**: For scheduled events
  - Lambda invocation

### Monitoring
- CloudWatch Log Groups for each Lambda function
- CloudWatch Alarms for S3 size and DynamoDB throttling
- SNS Topic for alarm notifications
- CloudWatch Dashboard overview

---

## Next Steps

Now that Phase 0 is complete:

1. **Review the architecture** in `docs/ARCHITECTURE.md`
2. **Start Phase 1** - Data ingestion pipeline
   - MTA API polling Lambda
   - S3 data lake integration
   - DynamoDB real-time updates
3. **Monitor costs** in AWS CloudFormation console

---

## Cost Estimate (Phase 0)

**Monthly Cost**: ~$0-5 (mostly within free tier)

- S3: ~$0 (< 1GB)
- DynamoDB: ~$0-1 (on-demand, minimal usage)
- Lambda: Free tier covers foundational usage
- CloudWatch: ~$1-3 (logs)
- Data Transfer: Free (within AWS)

**Total: Likely under $5/month during development**

Once Phase 1 and beyond are deployed, costs will increase to $65-1340/month depending on scale.

---

## Support & Resources

- **AWS CloudFormation Docs**: https://docs.aws.amazon.com/cloudformation/
- **AWS CLI Reference**: https://docs.aws.amazon.com/cli/
- **S3 Best Practices**: https://docs.aws.amazon.com/AmazonS3/latest/userguide/
- **DynamoDB Guide**: https://docs.aws.amazon.com/dynamodb/

---

**Phase 0 Complete! ✓**

Ready to proceed to Phase 1: Real-Time Data Ingestion
