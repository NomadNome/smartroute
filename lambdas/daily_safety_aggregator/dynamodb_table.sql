-- SmartRoute Safety Scores DynamoDB Table Creation
--
-- Purpose: Pre-computed safety scores for all NYC subway stations
--
-- This table eliminates synchronous Athena queries from the main route
-- recommendation Lambda. Safety scores are computed once per day and
-- cached in this table for instant lookups.
--
-- Schema:
--   Partition Key: station_name (String)
--   Attributes:
--     - safety_score (Number, 0-10)
--     - incident_count (Number)
--     - median_safety (Number)
--     - updated_at (String, ISO 8601)
--     - lookback_days (Number)
--
-- Performance:
--   - Read: ~1ms (GetItem)
--   - Write: Batch of 25 items = ~5ms
--   - Cost: Pay-per-request (on-demand pricing)

-- OPTION 1: Using AWS CLI
-- aws dynamodb create-table \
--   --table-name SmartRoute_Safety_Scores \
--   --attribute-definitions \
--     AttributeName=station_name,AttributeType=S \
--   --key-schema \
--     AttributeName=station_name,KeyType=HASH \
--   --billing-mode PAY_PER_REQUEST \
--   --region us-east-1 \
--   --tags Key=Project,Value=SmartRoute Key=Phase,Value=5

-- OPTION 2: Using Boto3 (Python)
import boto3

dynamodb = boto3.client('dynamodb', region_name='us-east-1')

table_name = 'SmartRoute_Safety_Scores'

try:
    response = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {
                'AttributeName': 'station_name',
                'KeyType': 'HASH'  # Partition Key
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'station_name',
                'AttributeType': 'S'  # String
            }
        ],
        BillingMode='PAY_PER_REQUEST',  # On-demand pricing
        Tags=[
            {'Key': 'Project', 'Value': 'SmartRoute'},
            {'Key': 'Phase', 'Value': '5-Production'},
            {'Key': 'Purpose', 'Value': 'Safety-Scores-Cache'}
        ]
    )

    print(f"✅ Table created: {table_name}")
    print(f"   Status: {response['TableDescription']['TableStatus']}")
    print(f"   ARN: {response['TableDescription']['TableArn']}")

except dynamodb.exceptions.ResourceInUseException:
    print(f"⚠️  Table already exists: {table_name}")

except Exception as e:
    print(f"❌ Error creating table: {e}")

-- OPTION 3: Using CloudFormation (Recommended for IaC)
AWSTemplateFormatVersion: '2010-09-09'
Description: 'SmartRoute Safety Scores DynamoDB Table'

Resources:
  SafetyScoresTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: SmartRoute_Safety_Scores
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: station_name
          AttributeType: S
      KeySchema:
        - AttributeName: station_name
          KeyType: HASH
      Tags:
        - Key: Project
          Value: SmartRoute
        - Key: Phase
          Value: '5-Production'
        - Key: Purpose
          Value: Safety-Scores-Cache

Outputs:
  TableName:
    Description: DynamoDB Table Name
    Value: !Ref SafetyScoresTable
    Export:
      Name: SmartRoute-Safety-Scores-Table

  TableArn:
    Description: DynamoDB Table ARN
    Value: !GetAtt SafetyScoresTable.Arn
    Export:
      Name: SmartRoute-Safety-Scores-Table-ARN

-- ============================================================================
-- TABLE SCHEMA DETAILS
-- ============================================================================

-- Partition Key: station_name (String)
--   Examples: "Times Square-42nd Street", "Grand Central-42nd Street"
--   Used for direct lookups from route recommender Lambda

-- Attributes:

--   safety_score (Number, 0-10)
--   - Composite score combining median_safety and incident_count
--   - Formula: median_safety - min(incident_count * 0.5, 5.0)
--   - Clamped to [0, 10]
--   - Example: 7.5

--   incident_count (Number)
--   - Number of crime incidents in 7-day rolling window
--   - Used as input to safety_score calculation
--   - Example: 12

--   median_safety (Number, 0-10)
--   - Direct output from Athena APPROX_PERCENTILE_CONT query
--   - Represents median safety score of incidents
--   - Example: 4.2

--   updated_at (String, ISO 8601)
--   - Timestamp of last aggregation run
--   - Format: "2025-11-18T02:00:00.000000Z"
--   - Useful for cache validation and troubleshooting

--   lookback_days (Number)
--   - Number of days of crime data included in aggregation
--   - Always 7 (rolling 7-day window)
--   - Can be adjusted without schema change

-- ============================================================================
-- SAMPLE ITEMS
-- ============================================================================

{
  "station_name": {"S": "Times Square-42nd Street"},
  "safety_score": {"N": "7.5"},
  "incident_count": {"N": "12"},
  "median_safety": {"N": "4.2"},
  "updated_at": {"S": "2025-11-18T02:00:00.000000Z"},
  "lookback_days": {"N": "7"}
}

{
  "station_name": {"S": "Grand Central-42nd Street"},
  "safety_score": {"N": "8.2"},
  "incident_count": {"N": "5"},
  "median_safety": {"S": "6.8"},
  "updated_at": {"S": "2025-11-18T02:00:00.000000Z"},
  "lookback_days": {"N": "7"}
}

{
  "station_name": {"S": "Wall Street"},
  "safety_score": {"N": "6.0"},
  "incident_count": {"N": "25"},
  "median_safety": {"S": "3.5"},
  "updated_at": {"S": "2025-11-18T02:00:00.000000Z"},
  "lookback_days": {"N": "7"}
}

-- ============================================================================
-- QUERY PATTERNS
-- ============================================================================

-- Pattern 1: Direct lookup (route recommender Lambda)
-- GET /smartroute-safety-scores/{station_name}
-- Latency: ~1ms
import boto3

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('SmartRoute_Safety_Scores')

response = table.get_item(
    Key={'station_name': 'Times Square-42nd Street'}
)

if 'Item' in response:
    safety_score = response['Item']['safety_score']  # 7.5
    print(f"Safety score: {safety_score}")

-- Pattern 2: Batch lookup (multiple stations)
response = dynamodb.batch_get_item(
    RequestItems={
        'SmartRoute_Safety_Scores': {
            'Keys': [
                {'station_name': 'Times Square-42nd Street'},
                {'station_name': 'Grand Central-42nd Street'},
                {'station_name': 'Wall Street'}
            ]
        }
    }
)

for item in response['Responses']['SmartRoute_Safety_Scores']:
    print(f"{item['station_name']}: {item['safety_score']}")

-- Pattern 3: Scan all stations (reporting/analytics)
-- ⚠️  Use sparingly! Scans are expensive
response = table.scan(
    ProjectionExpression='station_name, safety_score, incident_count'
)

for item in response['Items']:
    print(f"{item['station_name']}: {item['safety_score']}")

-- ============================================================================
-- MONITORING & METRICS
-- ============================================================================

-- CloudWatch Metrics Published:
--   - SmartRoute/SafetyAggregator/ExecutionTime (Seconds)
--   - SmartRoute/SafetyAggregator/ItemsWritten (Count)
--   - SmartRoute/SafetyAggregator/ItemsFailed (Count)
--   - SmartRoute/SafetyAggregator/SuccessRate (Percent)

-- CloudWatch Logs:
--   /aws/lambda/daily_safety_aggregator

-- ============================================================================
-- MIGRATION & TESTING
-- ============================================================================

-- Step 1: Create the table
-- Using: AWS CLI, boto3, or CloudFormation (see above)

-- Step 2: Test the daily_safety_aggregator Lambda
-- Invoke manually: aws lambda invoke --function-name daily_safety_aggregator /tmp/response.json
# View response: cat /tmp/response.json

-- Step 3: Verify data in DynamoDB
-- aws dynamodb get-item \
--   --table-name SmartRoute_Safety_Scores \
--   --key '{"station_name":{"S":"Times Square-42nd Street"}}'

-- Step 4: Update route_recommender Lambda to read from cache
-- Instead of: athena_fetcher.get_crime_data(station)
-- Use: safety_table.get_item(Key={'station_name': station})

-- Step 5: Set up EventBridge trigger
-- Schedule: "cron(0 2 * * ? *)"  # 2 AM UTC daily
-- Target: daily_safety_aggregator Lambda

-- ============================================================================
-- ROLLBACK PLAN
-- ============================================================================

-- If daily_safety_aggregator fails:
-- 1. Route recommender Lambda falls back to synchronous Athena query
-- 2. No user-facing impact (slower, but functional)
-- 3. Delete SmartRoute_Safety_Scores table when not needed
-- 4. Revert route_recommender to use athena_fetcher.get_crime_data()

-- Delete table:
-- aws dynamodb delete-table --table-name SmartRoute_Safety_Scores
