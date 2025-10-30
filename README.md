# SmartRoute: NYC Transit Intelligence Assistant

A production-ready data engineering project combining real-time MTA subway data, AWS services, and generative AI to provide intelligent transit recommendations for NYC.

## Project Overview

SmartRoute demonstrates enterprise data architecture patterns while helping NYC commuters navigate the subway system intelligently. The application integrates:

- **Real-time Data**: MTA GTFS-RT subway feed (updated every 30 seconds)
- **Analytics**: Historical transit patterns, reliability metrics, crowding estimates
- **Intelligence**: GenAI-powered route recommendations with safety and efficiency insights
- **AWS Services**: Lambda, S3, Kinesis, DynamoDB, Athena, Bedrock, and more

## Quick Start

### Prerequisites

- AWS Account (free tier eligible)
- AWS CLI v2 configured
- Python 3.11+
- Node.js 18+
- Git
- MTA API key (free at [MTA Developer Resources](http://new.mta.info/developers))
- Google Maps API key (free trial available)

### 1. Clone and Setup

```bash
cd smartroute-project
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate (Windows)
pip install -r requirements.txt
```

### 2. Configure AWS

```bash
# Set your AWS region (us-east-1 recommended for NYC)
export AWS_REGION=us-east-1
export AWS_PROFILE=default

# Verify AWS CLI access
aws sts get-caller-identity
```

### 3. Phase 0: Infrastructure Setup

```bash
cd infrastructure/cloudformation
aws cloudformation create-stack \
  --stack-name smartroute-phase0 \
  --template-body file://phase-0-foundation.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1

# Wait for stack creation (5-10 minutes)
aws cloudformation wait stack-create-complete \
  --stack-name smartroute-phase0 \
  --region us-east-1

echo "Phase 0 complete! ✅"
```

### 4. Add API Keys

```bash
# Create .env file with your API keys
cat > .env << EOF
AWS_REGION=us-east-1
MTA_API_KEY=your_mta_key_here
GOOGLE_MAPS_API_KEY=your_google_maps_key_here
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
EOF

# Add to AWS Secrets Manager
scripts/setup-secrets.sh
```

### 5. Deploy Phase 1 (Data Ingestion)

```bash
# Coming in Phase 1!
echo "Phase 1 coming soon..."
```

## Project Structure

```
smartroute-project/
├── docs/                          # Documentation
│   ├── ARCHITECTURE.md
│   ├── SCHEMA.md
│   ├── SETUP.md
│   └── OPERATIONS.md
├── infrastructure/
│   ├── cloudformation/           # CloudFormation templates
│   │   ├── phase-0-foundation.yaml
│   │   ├── phase-1-ingestion.yaml
│   │   └── parameters.yaml
│   └── terraform/               # Terraform (alternative)
├── lambdas/                      # Lambda function code
│   ├── mta-poller/
│   ├── route-handler/
│   ├── enrichment/
│   └── bedrock-router/
├── frontend/                     # Next.js application
├── notebooks/                    # Jupyter notebooks for exploration
├── tests/                        # Test suites
├── scripts/                      # Deployment and utility scripts
└── requirements.txt             # Python dependencies
```

## AWS Data Engineer Concepts Covered

This project covers ~80% of the AWS Certified Data Engineer - Associate exam:

✅ **Data Ingestion & Transformation** (Lambda, ETL, data validation)
✅ **Data Storage** (S3 partitioning, DynamoDB, Athena)
✅ **Data Processing** (Kinesis, Lambda, Glue, Step Functions)
✅ **Data Analysis** (Athena SQL, dimensional modeling)
✅ **Governance & Security** (IAM, encryption, Secrets Manager)
✅ **Optimization & Cost** (lifecycle policies, monitoring)

## Development Phases

| Phase | Focus | Duration | Status |
|-------|-------|----------|--------|
| **Phase 0** | Foundation & Infrastructure | 2 weeks | 🔄 In Progress |
| **Phase 1** | Real-time Data Ingestion | 3 weeks | Pending |
| **Phase 2** | Analytics & Enrichment | 5 weeks | Pending |
| **Phase 3** | GenAI Integration | 5 weeks | Pending |
| **Phase 4** | Production & Frontend | 6 weeks | Pending |

## Estimated Costs (US-East-1)

**Phase 1-2 (Development)**
- ~$65-120/month

**Phase 3-4 (Production)**
- ~$710-1340/month

See `docs/COST_TRACKING.md` for detailed breakdown.

## Key Features

### Real-Time Transit Intelligence
- Live subway delays and service alerts
- Next arrival predictions
- Station crowding estimates

### Safety & Intelligence
- 7-day crime incident aggregation by station
- 311 complaint tracking and trends
- Safety scoring algorithm

### Route Recommendations
- Multi-modal routing (via Google Maps)
- Safety-aware recommendations
- Crowding predictions
- Natural language explanations (via Claude)

## API Integrations

| API | Purpose | Rate Limit | Cost |
|-----|---------|-----------|------|
| **MTA GTFS-RT** | Real-time vehicle data | 100 req/min | Free |
| **MTA GTFS Static** | Schedule & station data | Daily | Free |
| **Google Maps Directions** | Route optimization | - | ~$5/1000 requests |
| **NYC Open Data** | Crime & 311 data | 5000 req/day | Free |
| **AWS Bedrock** | GenAI reasoning | - | ~$0.01 per 1000 input tokens |

## Getting Help

- **AWS Data Engineer Docs**: See `docs/EXAM_GUIDE.md`
- **Troubleshooting**: See `docs/OPERATIONS.md`
- **Architecture Questions**: See `docs/ARCHITECTURE.md`

## License

MIT License - See LICENSE file for details

## Contributing

1. Create a feature branch
2. Make changes
3. Test locally
4. Create pull request with description

---

**Built as a learning project for AWS Certified Data Engineer - Associate exam preparation.**

For feedback or issues, please check the git repository issue tracker.
