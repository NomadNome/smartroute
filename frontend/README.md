# SmartRoute Phase 1 Testing Dashboard

Real-time MTA transit data visualization dashboard for the SmartRoute project Phase 1 data pipeline.

## Overview

This dashboard provides a web-based interface to visualize and monitor real-time transit data flowing through Phase 1 of the SmartRoute architecture:

- **DynamoDB** - Real-time station state (current arrivals)
- **Kinesis** - Event stream of vehicle updates
- **S3** - Archived raw data with date/hour partitioning
- **Lambda** - Data processing pipeline execution metrics
- **CloudWatch** - System monitoring and alerting

## Quick Start

### 1. Start the Dashboard Server

```bash
# Option 1: Using the startup script
./scripts/start-dashboard.sh

# Option 2: Manual startup
cd frontend
npm install
npm start
```

The dashboard will be available at: **http://localhost:3001**

### 2. Ensure Phase 1 is Deployed and Running

Before starting the dashboard, make sure:

```bash
# Verify MTA Poller Lambda is deployed
aws lambda get-function-configuration \
  --function-name smartroute-mta-poller \
  --region us-east-1

# Verify DynamoDB table has data
aws dynamodb scan \
  --table-name smartroute_station_realtime_state \
  --limit 5 \
  --region us-east-1

# Verify S3 bucket has archived data
aws s3 ls \
  s3://smartroute-data-lake-069899605581/raw/mta/realtime/ \
  --recursive
```

### 3. Configure AWS Credentials

The Express backend uses AWS SDK v3 to connect to AWS services. Ensure credentials are available:

```bash
# Option 1: AWS CLI credentials (recommended)
aws configure
# Then set AWS_REGION
export AWS_REGION=us-east-1

# Option 2: Environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=us-east-1

# Option 3: AWS credentials file (~/.aws/credentials)
[default]
aws_access_key_id = your_access_key
aws_secret_access_key = your_secret_key
```

## Dashboard Components

### Statistics Cards
- **Active Stations**: Count of stations with recent data in DynamoDB
- **Data Files (S3)**: Number of raw data files archived
- **Kinesis Stream**: Real-time stream status
- **Lambda Status**: Function execution status

### Pipeline Status
Real-time view of data flowing through the system:
- DynamoDB station count with progress bar
- S3 files stored with progress bar
- Kinesis stream name and status

### Recent Stations
Live list of the 10 most recently updated stations with:
- Station ID
- Next arrival times for each line
- Destination and vehicle IDs
- Arrival countdown in seconds

### CloudWatch Metrics
- Lambda invocation count (last 1 hour)
- Kinesis record throughput
- Performance trends

### S3 Data Files
Recent archived data files with:
- File size in KB
- Last modified timestamp
- Storage class

## API Endpoints

The Express backend provides REST API endpoints:

```bash
# Health check
curl http://localhost:3001/api/health

# Get all stations (limit 50)
curl http://localhost:3001/api/stations?limit=50

# Get specific station
curl http://localhost:3001/api/station/stop_0

# Get CloudWatch metrics
curl http://localhost:3001/api/metrics

# List S3 data files
curl http://localhost:3001/api/data-files?maxKeys=20

# Get dashboard statistics
curl http://localhost:3001/api/dashboard-stats

# Get frontend configuration
curl http://localhost:3001/api/config
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│          Browser Dashboard (index.html)                 │
│  • Real-time visualization                              │
│  • 5-second auto-refresh                                │
│  • Responsive design (mobile-friendly)                  │
└─────────────────────────────────────────────────────────┘
                           ↓ (HTTP/REST)
┌─────────────────────────────────────────────────────────┐
│        Express Backend (server.js)                      │
│  • REST API endpoints                                   │
│  • AWS SDK v3 integration                               │
│  • CORS-enabled                                         │
└─────────────────────────────────────────────────────────┘
     ↓              ↓              ↓              ↓
  DynamoDB       S3           Kinesis        CloudWatch
   │             │              │              │
   └─────────────┴──────────────┴──────────────┘
            Phase 1 Data Pipeline
```

## Development

### Modify Dashboard UI

Edit `frontend/public/index.html` to customize:
- Styling (CSS in `<style>` tag)
- Layout and components
- JavaScript behavior in `<script>` tag

### Modify API Backend

Edit `frontend/server.js` to:
- Add new endpoints
- Change AWS service integrations
- Modify data transformations

### Install/Update Dependencies

```bash
cd frontend
npm install   # Install or update packages
npm update    # Update to latest versions
```

## Troubleshooting

### "Cannot find module 'express'"

Solution: Install dependencies
```bash
cd frontend
npm install
```

### "Access Denied" from AWS SDK

Solution: Configure AWS credentials
```bash
aws configure
export AWS_REGION=us-east-1
```

### Dashboard shows empty data

Check that:
1. Lambda functions are deployed: `aws lambda list-functions --region us-east-1`
2. DynamoDB table has data: `aws dynamodb scan --table-name smartroute_station_realtime_state --limit 5`
3. EventBridge rule is enabled: `aws events list-rules --region us-east-1`

### Server crashes with "listen EADDRINUSE"

Port 3001 is already in use. Either:
- Kill the existing process: `pkill -f "node server.js"`
- Use a different port: `PORT=3002 npm start`

## Performance

- **Data Update Interval**: 5 seconds (configurable in `index.html`)
- **Lambda Polling**: Every 1 minute (configured in CloudFormation)
- **DynamoDB Latency**: <10ms typical query time
- **S3 Listing**: Async, doesn't block UI updates

## Security Considerations

- The dashboard runs locally on `localhost:3001` (not exposed to internet)
- AWS credentials are required but used only on the backend
- CORS is enabled for local development
- No sensitive data is stored in the browser

## Next Steps

After validating Phase 1 with this dashboard:

1. **Phase 2 - Analytics & Historical Data**
   - Implement ETL pipeline with Glue
   - Setup Redshift data warehouse
   - Create Athena queries for analysis

2. **Phase 3 - GenAI Integration**
   - Add Amazon Bedrock for Claude integration
   - Create natural language route recommendations
   - Implement crowding prediction model

3. **Phase 4 - Frontend Web Application**
   - Build React/Next.js user-facing app
   - Deploy to CloudFront + S3
   - Implement authentication and user profiles

## Documentation

- Phase 1 Planning: `docs/PHASE1_PLAN.md`
- Phase 1 Deployment: `docs/PHASE1_DEPLOYMENT.md`
- Architecture Overview: `docs/ARCHITECTURE.md`
- Setup Guide: `docs/SETUP.md`

## Support

For issues or questions about the dashboard, refer to:
- AWS SDK v3 Docs: https://docs.aws.amazon.com/AWSJavaScriptSDK/v3/
- Express.js Docs: https://expressjs.com/
- DynamoDB Query Guide: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/
