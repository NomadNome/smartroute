# SmartRoute System Architecture

Complete system design documentation for SmartRoute project.

---

## Table of Contents

1. [High-Level Overview](#high-level-overview)
2. [Phase 0: Foundation](#phase-0-foundation)
3. [Phase 1-4: Full Architecture](#phase-1-4-full-architecture)
4. [Data Storage Layer](#data-storage-layer)
5. [Data Processing Layer](#data-processing-layer)
6. [Integration Points](#integration-points)

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      EXTERNAL DATA SOURCES                              │
├─────────────────────────────────────────────────────────────────────────┤
│  MTA GTFS-RT │ MTA GTFS Static │ Google Maps │ NYC Crime Data │ Weather │
└────────────────────┬──────────────────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │   AWS INGESTION LAYER      │
        │  - Lambda (API Polling)    │
        │  - EventBridge (Triggers)  │
        └────────────────┬───────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
    ┌─────────────┐ ┌──────────────┐ ┌──────────────┐
    │  S3 Raw    │ │  Kinesis    │ │  DynamoDB   │
    │  Data Lake │ │  Streams    │ │  Real-time  │
    │  (Archive) │ │  (Streaming)│ │  State      │
    └─────┬───────┘ └──────┬──────┘ └──────┬──────┘
          │                │               │
          └────────────────┼───────────────┘
                           │
                  ┌────────▼────────┐
                  │  PROCESSING     │
                  │  - Glue ETL     │
                  │  - Lambda Jobs  │
                  │  - SFN Workflow │
                  └────────┬────────┘
                           │
                     ┌─────▼─────┐
                     │ S3 Proc   │
                     │ (Analytics)
                     └──┬──────┬─┘
                        │      │
            ┌───────────┴─┐  ┌─┴──────────┐
            │             │  │            │
            ▼             ▼  ▼            ▼
        ┌────────┐   ┌─────────┐    ┌─────────┐
        │ Athena │   │Redshift │    │   RDS   │
        │(Ad-hoc)│   │(Analytics  │   │(History)│
        └────────┘   └─────────┘    └─────────┘
            │             │               │
            └─────────────┼───────────────┘
                          │
        ┌─────────────────┴────────────────┐
        │                                  │
        ▼                                  ▼
    ┌──────────────┐            ┌──────────────────┐
    │ CloudWatch   │            │ Bedrock (Claude) │
    │ Dashboards   │            │ GenAI Reasoning  │
    └──────────────┘            └────────┬─────────┘
                                         │
                                         ▼
                            ┌──────────────────────┐
                            │  Frontend App        │
                            │  (Next.js + Maps)    │
                            └──────────────────────┘
```

---

## Phase 0: Foundation

### Infrastructure Components

#### S3 Data Lake
```
smartroute-data-lake-{ACCOUNT_ID}/
├── raw/
│   ├── mta/
│   │   ├── realtime/
│   │   ├── gtfs_static/
│   │   └── service_status/
│   ├── google_maps/
│   │   └── directions/
│   └── nyc_data/
│       ├── crime/
│       └── 311_complaints/
└── processed/
    ├── station_realtime/
    ├── route_analysis/
    └── enriched_events/

Retention Policy:
- raw/ → STANDARD_IA after 30 days
- raw/ → GLACIER after 90 days (3-5 hour retrieval time, cheaper)
- processed/ → STANDARD_IA after 60 days
```

**Cost**: ~$0.023 per GB/month for Standard tier

#### DynamoDB Tables

**1. station_realtime_state**
```json
{
  "PK": "station_id (e.g., 'S127N')",
  "SK": "timestamp (unix epoch)",
  "GSI": "station_id, expiration_time",
  "TTL": 600 seconds (auto-delete old records),
  "BillingMode": "PAY_PER_REQUEST"
}

Example item:
{
  "station_id": "S127N",
  "timestamp": 1698600900,
  "station_name": "125 Street",
  "lines": ["1", "2"],
  "next_arrivals": [
    {
      "line": "1",
      "arrival_seconds": 180,
      "destination": "Van Cortlandt Park"
    }
  ],
  "alerts": [],
  "crowding": "MODERATE",
  "safety_score": 6.5,
  "expiration_time": 1698601500
}
```

**2. cached_routes**
```json
{
  "PK": "route_hash (SHA256 of origin+destination)",
  "SK": "timestamp",
  "TTL": 3600 seconds (1 hour),
  "BillingMode": "PAY_PER_REQUEST"
}

Purpose: Cache Google Maps API responses to reduce costs
```

**3. user_sessions**
```json
{
  "PK": "user_id",
  "SK": "session_id",
  "TTL": 86400 seconds (24 hours),
  "Attributes": {
    "current_location": {...},
    "preferences": {...},
    "search_history": [...]
  }
}

Purpose: Lightweight session storage for web app
```

**Cost**: ~$0 per month with on-demand billing (charged per read/write)

#### IAM Roles & Policies

**LambdaExecutionRole**
```
Permissions:
├── logs:CreateLogGroup
├── logs:CreateLogStream
├── logs:PutLogEvents        ← CloudWatch logging
├── s3:GetObject
├── s3:PutObject            ← S3 data lake access
├── dynamodb:GetItem
├── dynamodb:PutItem        ← DynamoDB operations
├── dynamodb:UpdateItem
├── kinesis:PutRecord       ← Kinesis stream writes
├── bedrock:InvokeModel     ← LLM access
└── secretsmanager:GetSecretValue ← API key retrieval
```

**Trust Relationship**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

#### CloudWatch Monitoring

**Log Groups**:
- `/aws/lambda/smartroute/mta-poller`
- `/aws/lambda/smartroute/route-handler`
- `/aws/lambda/smartroute/enrichment`
- `/aws/lambda/smartroute/bedrock-router`

**Retention**: 14 days (adjustable)

**Dashboard**: `smartroute-phase0-overview`
- S3 bucket size metrics
- DynamoDB read/write throughput
- Lambda invocation count and errors
- Log group activity

---

## Phase 1-4: Full Architecture

### Data Ingestion (Phase 1)

#### Real-Time MTA Polling

```
EventBridge Rule: Every 30 seconds
│
▼
Lambda: mta-poller
├── Fetches from MTA GTFS-RT API
├── Decodes protobuf response
├── Validates schema
├── Deduplicates by trip_id
└── Outputs:
    ├── S3: raw/mta/realtime/...json (archive)
    ├── Kinesis: transit_data (real-time)
    └── DynamoDB: station_realtime_state (current)
```

**Kinesis Stream**: `transit_data_stream`
- Shards: 1 (30 req/sec = 30 KB/sec, well under 1 MB/sec limit)
- Retention: 24 hours
- Billing: ~$30-50/month

#### Google Maps Integration (Phase 3)

```
User Request: GET /api/get-route
│
▼
Lambda: route-handler
├── Check DynamoDB cache
├── Call Google Maps Directions API (if cache miss)
├── Parse response
├── Cache result (1 hour TTL)
└── Return routes
```

**Cost Optimization**:
- 1000 users/day × 3 alternatives = 3000 requests/day
- Google Maps: $5 per 1000 requests
- Without caching: ~$45/month
- With 1-hour cache: ~$1.50/month (90% reduction)

### Data Processing (Phase 2)

#### ETL Pipeline

```
Triggers:
├── Scheduled: Daily at 02:00 UTC
├── Event-driven: When S3 objects arrive
└── Manual: On-demand via API

AWS Glue ETL Job:
├── Read: S3 raw/mta/realtime/*.json
├── Read: S3 raw/mta/gtfs_static/*.csv
├── Read: DynamoDB station_realtime_state
├── Transform:
│   ├── Join realtime + static data
│   ├── Aggregate by hour
│   ├── Calculate reliability metrics
│   └── Feature engineering
└── Output: S3 processed/parquet/...

Spark Executors: 2 (DPU, G.2X)
Cost: ~$10-15 per job run
```

#### Analytics Platform

**Athena** (Ad-hoc queries):
```sql
SELECT
  line_id,
  HOUR(timestamp) as hour,
  AVG(delay_minutes) as avg_delay,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY delay_minutes) as p95_delay
FROM smartroute.processed.station_realtime
WHERE date = CURRENT_DATE
GROUP BY line_id, HOUR(timestamp)
```

**Redshift** (BI/Dashboards):
```
Cluster: dc2.large × 2 nodes
├── Node Type: dc2.large (160 GB SSD storage)
├── Nodes: 2 (for HA)
├── Cost: ~$400-600/month
└── Schema:
    ├── Fact Tables:
    │   ├── fact_transit_events (1B+ rows)
    │   └── fact_service_alerts
    └── Dimension Tables:
        ├── dim_stations (500 stations)
        ├── dim_routes (30 routes)
        └── dim_time (date/hour lookups)
```

**Distribution & Sort Keys** (Redshift best practices):
```sql
CREATE TABLE fact_transit_events (
  event_id BIGINT,
  station_id VARCHAR(10),
  route_id VARCHAR(5),
  event_time TIMESTAMP,
  delay_minutes INT,
  crowding_level INT
)
DISTKEY(station_id)  -- Distribute on station_id for join efficiency
SORTKEY(event_time)  -- Sort by time for range queries
```

### GenAI Integration (Phase 3)

#### Bedrock LLM Prompting

```
Lambda: bedrock-router
│
├── 1. Gather context:
│   ├── Route options from Google Maps
│   ├── Safety scores from Athena
│   ├── Crowding from DynamoDB
│   └── Alerts from MTA
│
├── 2. Build prompt:
│   └── System: "You are a NYC transit expert..."
│       User: "Route A: 35 min, Line 1 (MAJOR_DELAY)
│               Route B: 42 min, Line 2 (GOOD_SERVICE)"
│
├── 3. Invoke Bedrock:
│   └── Model: claude-3-sonnet (or latest)
│       Input tokens: ~500-1000
│       Output tokens: ~200-400
│
└── 4. Parse response:
    └── Extract: recommendation + reasoning + station tips

Cost:
- Input: $3 per 1M tokens
- Output: $15 per 1M tokens
- 1000 users × 500 input tokens = $1.50/day
```

### Frontend (Phase 4)

```
Next.js Application (TypeScript)
├── Pages:
│   ├── / (landing)
│   ├── /route (main app)
│   ├── /dashboard (admin)
│   └── /api/* (backend routes)
├── Components:
│   ├── RouteMap (Google Maps integration)
│   ├── RouteCard (route recommendation display)
│   ├── ChatInterface (LLM conversation)
│   └── StationInfo (details panel)
└── State Management:
    ├── React Context for user location
    ├── TanStack Query for API calls
    └── Zustand for app state

Deployment:
├── Vercel (Next.js CDN)
├── CloudFront (static assets)
└── API Gateway → Lambda (backend)
```

---

## Data Storage Layer

### Storage Decision Matrix

| Use Case | Service | Why | Cost |
|----------|---------|-----|------|
| **Immutable Archive** | S3 (Standard) | Unlimited scale, durability | $0.023/GB/month |
| **Warm Data** | S3 (Intelligent-Tiering) | Auto-moves between tiers | $0.0125/GB/month |
| **Cold Archive** | Glacier | 3-5 hour retrieval | $0.004/GB/month |
| **Real-time Ops** | DynamoDB | Sub-10ms latency | Pay per request |
| **Analytics Cache** | ElastiCache | In-memory, fast | $0.017/GB/hour |
| **Time-series** | Redshift | Columnar, aggregation | $400-600/month |
| **Relational** | RDS Aurora | ACID transactions | $0.12/hour (t3.small) |

---

## Data Processing Layer

### Processing Decision Matrix

| Task | Service | Why | Cost |
|------|---------|-----|------|
| **Real-time (< 1 sec)** | Lambda | No wait time | Free tier covers ~1M invocations |
| **Streaming (< 5 sec)** | Kinesis | Managed, scalable | $30-50/month (1 shard) |
| **Batch ETL** | Glue | Spark, serverless | $0.44/DPU-hour |
| **Scheduled Jobs** | Lambda + EventBridge | Simple, cheap | Free |
| **Complex Workflows** | Step Functions | Visual, stateful | $0.000025 per transition |
| **ML Training** | SageMaker | Managed ML | $0.50+/hour (training) |

---

## Integration Points

### API Contracts

#### Lambda to Lambda (Event Bridge)

```json
// Event: Route Enrichment Request
{
  "source": "route-handler-lambda",
  "detail-type": "RouteEnrichmentRequest",
  "detail": {
    "route_id": "google_route_0",
    "origin": {"lat": 40.7580, "lng": -73.9855},
    "destination": {"lat": 40.6640, "lng": -73.9776},
    "user_preferences": {
      "avoid_crowding": true,
      "max_safety_risk": 5.0
    }
  }
}
```

#### S3 Event Notifications

```json
{
  "Records": [
    {
      "s3": {
        "bucket": {"name": "smartroute-data-lake-123456789012"},
        "object": {"key": "raw/mta/realtime/2025-10-29/14/32/file.json"}
      },
      "eventName": "ObjectCreated:Put"
    }
  ]
}
```

### CloudWatch Metrics

Custom metrics to monitor:

```python
# Example: Lambda monitoring
cloudwatch.put_metric_data(
    Namespace='SmartRoute',
    MetricData=[
        {
            'MetricName': 'RouteRecommendationLatency',
            'Value': latency_ms,
            'Unit': 'Milliseconds',
            'Dimensions': [
                {'Name': 'Service', 'Value': 'bedrock-router'},
                {'Name': 'Model', 'Value': 'claude-3-sonnet'}
            ]
        }
    ]
)
```

---

## Security Architecture

### Defense in Depth

```
┌─────────────────────────────────────────────┐
│ API Gateway (TLS 1.2+, API Keys)            │
├─────────────────────────────────────────────┤
│ AWS WAF (Rate limiting, IP filtering)       │
├─────────────────────────────────────────────┤
│ Lambda (VPC execution, security groups)     │
├─────────────────────────────────────────────┤
│ Secrets Manager (Encrypted API keys)        │
├─────────────────────────────────────────────┤
│ VPC (Private subnets, NACLs)                │
├─────────────────────────────────────────────┤
│ Encryption (S3 SSE, RDS KMS, DDB encryption)│
├─────────────────────────────────────────────┤
│ IAM (Least privilege, cross-account access) │
└─────────────────────────────────────────────┘
```

### Data Classification

| Level | Data | Encryption | Access |
|-------|------|-----------|--------|
| **Public** | Anonymous route recommendations | Not required | Unrestricted |
| **Internal** | Transit schedules, maps | In-transit | AWS services only |
| **Sensitive** | API keys, user preferences | At-rest + in-transit | Service roles only |
| **Confidential** | User location history | Encrypted, TDE | Owner + admin only |

---

## Disaster Recovery

### RTO/RPO Targets

| Component | RTO | RPO | Strategy |
|-----------|-----|-----|----------|
| **S3 Data Lake** | 1 hour | 1 hour | S3 cross-region replication |
| **DynamoDB** | 5 min | < 1 min | Point-in-time recovery |
| **Redshift** | 2 hours | 1 hour | Automated snapshots |
| **Lambda Code** | 5 min | 0 | Git + CodePipeline |
| **Frontend** | 1 min | 0 | Multi-region Vercel |

---

## Monitoring & Observability

### Key Dashboards

1. **Operational Dashboard**
   - Lambda invocations, errors
   - S3 request rates
   - DynamoDB consumed capacity
   - Kinesis iterator age

2. **Data Quality Dashboard**
   - Records ingested (vs expected)
   - Processing latency
   - Error rates by source
   - Schema violations

3. **Cost Dashboard**
   - Daily AWS spend by service
   - Forecast vs budget
   - Top cost drivers
   - Reserved capacity utilization

4. **Application Dashboard**
   - Route recommendation latency (p50, p95, p99)
   - LLM response quality
   - User satisfaction
   - API error rates

---

## Scalability Considerations

### Horizontal Scaling

| Component | Scaling Method | Max Capacity |
|-----------|--------|---|
| **Lambda** | Concurrent executions | 1000+ (with limit increase) |
| **Kinesis** | Shards | ~4000/account |
| **DynamoDB** | On-demand autoscaling | Unlimited (within quotas) |
| **S3** | Auto-scaling | Unlimited |
| **Redshift** | Node scaling | 128+ nodes |

### Vertical Scaling

| Component | Current | Max | Cost |
|-----------|---------|-----|------|
| **Lambda Memory** | 128 MB | 10 GB | More memory = more CPU |
| **Redshift Nodes** | dc2.large | dc2.8xlarge | Linear cost increase |
| **RDS Instance** | t3.small | r6i.16xlarge | Exponential cost |

---

## Cost Optimization Strategies

1. **Data Tiering**
   - Hot (S3 Standard): 30 days
   - Warm (S3-IA): 90 days
   - Cold (Glacier): > 90 days

2. **Reserved Capacity**
   - Redshift: -40% with 1-year commitment
   - DynamoDB: On-demand for unpredictable

3. **Spot Instances**
   - Glue (Spark): Use Spot workers
   - EC2: Use Spot for non-critical tasks

4. **Caching**
   - Google Maps: 1-hour cache (90% cost reduction)
   - Redshift: Materialized views for common queries
   - Lambda: Store computed values in DynamoDB

---

**For detailed Phase-specific architecture, see**:
- Phase 0: This document (Foundation)
- Phase 1: See SETUP.md (Data Ingestion)
- Phase 2-4: See ROADMAP.md (Implementation plan)
