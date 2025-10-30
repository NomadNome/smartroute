# Phase 1: Real-Time Data Ingestion - Implementation Plan

**Status**: 🔄 In Progress
**Duration**: 3 weeks (Weeks 3-6)
**Effort**: ~63 hours
**Goal**: Real-time MTA data flowing to S3, Kinesis, and DynamoDB

---

## Phase 1 Overview

Phase 1 focuses on building the data ingestion pipeline - the critical foundation that feeds all downstream processing.

### Key Deliverables

1. **MTA Real-Time Data Poller** (Lambda)
   - Poll MTA GTFS-RT API every 30 seconds
   - Decode protobuf responses
   - Validate and deduplicate data
   - 99%+ uptime SLA

2. **Real-Time Data Stream** (Kinesis)
   - Ingest 30 requests/minute
   - Fan-out to multiple consumers
   - Enable sub-5-second latency updates

3. **DynamoDB Real-Time State**
   - Current station state (updated every 30 sec)
   - Auto-expire old records (TTL: 600s)
   - <10ms query latency for "current status"

4. **S3 Data Lake** (Raw Tier)
   - Archive raw API responses
   - Partitioned by date/hour
   - Immutable audit log

5. **GTFS Static Data Pipeline**
   - Daily download of GTFS schedule data
   - CSV parsing and validation
   - Parquet conversion for analytics

6. **Data Validation & Monitoring**
   - Schema validation
   - Anomaly detection
   - CloudWatch metrics and alarms
   - Error handling & DLQ

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│          MTA GTFS-RT API (Every 30 seconds)            │
│  - Vehicle positions                                    │
│  - Arrival predictions                                 │
│  - Service alerts                                      │
└─────────────────────┬─────────────────────────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │  EventBridge Rule           │
        │  Trigger: Every 30 seconds  │
        └──────────────┬──────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  Lambda: mta-poller                                    │
│  ├─ Fetch from MTA API                                │
│  ├─ Decode protobuf (GTFS-RT)                         │
│  ├─ Validate schema                                   │
│  ├─ Deduplicate by trip_id                            │
│  └─ Output to 3 targets:                              │
└─────────┬───────────────┬───────────────┬──────────────┘
          │               │               │
          ▼               ▼               ▼
    ┌──────────┐   ┌──────────┐   ┌──────────────┐
    │ S3 Raw   │   │ Kinesis  │   │ DynamoDB     │
    │ (Archive)│   │(Streaming│   │(Real-time)   │
    │ JSON     │   │          │   │              │
    └──────────┘   └────┬─────┘   └──────────────┘
                        │
          ┌─────────────┴─────────────┐
          │                           │
          ▼                           ▼
    ┌──────────────┐          ┌──────────────────┐
    │  Lambda:     │          │  Lambda:         │
    │  Real-time   │          │  Error Handler   │
    │  Processor   │          │  (DLQ)           │
    │  (Phase 2)   │          │                  │
    └──────────────┘          └──────────────────┘
```

---

## Implementation Details

### 1. MTA API Poller Lambda

**File**: `lambdas/mta-poller/lambda_function.py`

#### Functionality
- Triggered by EventBridge every 30 seconds
- Fetch from MTA GTFS-RT API (3 feeds: 1=Subway, 2=Bus, 3=LIRR/Metro-North)
- Parse protobuf response (protocol buffer binary format)
- Extract vehicle positions, stop times, alerts
- Validate data schema
- Deduplicate by trip_id + vehicle_id
- Send to Kinesis, S3, and DynamoDB simultaneously

#### Python Code Structure
```
lambdas/mta-poller/
├── lambda_function.py          # Main handler
├── mta_client.py               # MTA API wrapper
├── protobuf_decoder.py         # GTFS-RT decoding
├── validators.py               # Schema validation
└── requirements.txt            # Dependencies
```

#### Key Dependencies
```
boto3                    # AWS SDK
protobuf>=4.24.0        # GTFS-RT decoding
requests                # HTTP client
aws-lambda-powertools   # Logging, tracing
```

#### Lambda Configuration
- **Runtime**: Python 3.11
- **Memory**: 512 MB (CPU scales with memory)
- **Timeout**: 60 seconds (30s API call + 30s buffer)
- **Reserved Concurrency**: 1 (schedule only allows 1 at a time)
- **Environment Variables**:
  ```
  MTA_API_KEY=<from Secrets Manager>
  KINESIS_STREAM_NAME=transit_data_stream
  S3_BUCKET=smartroute-data-lake-{ACCOUNT_ID}
  DYNAMODB_TABLE=smartroute_station_realtime_state
  LOG_LEVEL=INFO
  ```

#### Error Handling
- Retry logic with exponential backoff (AWS SDK built-in)
- DLQ for failed messages
- CloudWatch alarms for failures
- Graceful degradation (skip failed fields, process what's good)

---

### 2. Kinesis Stream

**Resource Name**: `transit_data_stream`

#### Configuration
- **Sharding**: 1 shard initially
  - Max throughput: 1 MB/sec, 1000 records/sec
  - MTA data: ~30 requests/min = ~500 records/sec (peak)
  - Capacity utilization: ~50% (good headroom)
- **Retention**: 24 hours (changeable to 365 days if needed)
- **Enhanced Fan-Out**: Disabled initially (enables multiple consumers at scale)
- **Encryption**: AWS managed key

#### Cost
- **Shard Hour**: $0.036/hour
- **12 shard-hours/day × 30 days = ~$13/month**
- **PUT Payload Unit**: Included in shard hour
- **GET Payload Unit**: Included in shard hour
- **Enhanced Fan-Out** (if enabled): $0.10/shard-hour = ~$72/month

#### Event Format
```json
{
  "source": "mta-poller",
  "timestamp": "2025-10-29T14:32:15Z",
  "trip_id": "20251029_L2340",
  "vehicle_id": "1234",
  "route_id": "1",
  "current_stop": "127N",
  "status": "IN_TRANSIT_TO",
  "latitude": 40.8207,
  "longitude": -73.9654,
  "next_arrival_seconds": 180,
  "crowding_estimate": null
}
```

#### Consumers
- **Phase 1**: Lambda for DynamoDB updates
- **Phase 2**: Glue job for aggregation
- **Phase 3**: Route enrichment pipeline

---

### 3. DynamoDB Real-Time State

**Table Name**: `smartroute_station_realtime_state`

#### Schema
```
PrimaryKey:
  - PartitionKey (HASH): station_id (String, e.g., "S127N")
  - SortKey (RANGE): timestamp (Number, unix epoch)

Attributes:
  - station_name: String
  - lines: List[String]
  - next_arrivals: List[Map]
    - line: String
    - arrival_seconds: Number
    - destination: String
    - vehicle_id: String
  - active_alerts: List[Map]
    - alert_id: String
    - severity: String (MINOR, MAJOR, SEVERE)
    - message: String
  - crowding_estimate: String (LIGHT, MODERATE, HEAVY, EXTREME)
  - last_update: Number (timestamp)
  - expiration_time: Number (unix epoch, for TTL)

TTL:
  - Attribute Name: expiration_time
  - Expiration: 600 seconds (10 minutes)
  - Auto-deletes expired records

GSI (if needed later):
  - Line-Station index for "all stations on Line X"
```

#### Query Patterns
```
Get current state of Times Square:
  Query(station_id="S127N", limit=1, ScanIndexForward=False)
  → Returns most recent state

Get all stations on Line 1:
  Query(line_id="1")  # GSI would enable this
```

#### On-Demand Billing
- No minimum cost
- Pay per 1M read units (~$1.25) and 1M write units (~$6.25)
- Expected: 30 writes/sec × 86400s = ~2.5M writes/day = ~$18/month

---

### 4. S3 Data Lake (Raw Tier)

**Bucket**: `smartroute-data-lake-{ACCOUNT_ID}`
**Partition Path**: `raw/mta/realtime/year=YYYY/month=MM/day=DD/hour=HH/`

#### File Format
- **Format**: JSON Lines (one JSON per line)
- **Compression**: None (or gzip if size becomes issue)
- **File Size**: ~100-200 MB per hour
- **Naming**: `mta_realtime_{timestamp}.json`

#### Example File
```
s3://smartroute-data-lake-069899605581/raw/mta/realtime/year=2025/month=10/day=29/hour=14/mta_realtime_20251029_1432.json

Contents (JSON Lines format):
{"vehicle_id":"1234","trip_id":"20251029_L2340",...}
{"vehicle_id":"5678","trip_id":"20251029_L2341",...}
```

#### Lifecycle Policy (Already Configured)
```
- raw/ prefix:
  - 30 days: STANDARD → STANDARD_IA
  - 90 days: STANDARD_IA → GLACIER
  - 365 days: DELETE
```

#### S3 Costs
- **Storage**:
  - STANDARD: $0.023/GB/month × 100 GB = $2.30/month
  - STANDARD_IA: $0.0125/GB/month (after 30 days)
  - GLACIER: $0.004/GB/month (after 90 days)
- **PUT requests**: $0.005/1000 = negligible
- **GET requests**: $0.0004/1000 = negligible

---

### 5. GTFS Static Data Pipeline

**File**: `lambdas/gtfs-downloader/lambda_function.py`

#### Functionality
- Triggered daily at 01:00 UTC (before business hours)
- Download GTFS static data from MTA
- Validate CSV schema
- Convert to Parquet format
- Store in S3 processed layer

#### Lambda Configuration
- **Runtime**: Python 3.11
- **Memory**: 256 MB (lightweight)
- **Timeout**: 300 seconds (5 minutes)
- **Trigger**: EventBridge rule (cron: `0 1 * * ? *`)

#### Tables Downloaded
```
stops.csv         → 500 subway stops
routes.csv        → 30 routes (1-A, S, GS, 7X, etc)
trips.csv         → 1000+ daily trips per route
stop_times.csv    → 100k+ stop time records
calendar.csv      → Schedule patterns (weekday/weekend/holiday)
transfers.csv     → Transfer points between lines
```

#### Processing
```
Download ZIP → Extract CSVs → Validate → Convert to Parquet
                                              ↓
                          S3: processed/gtfs_static/
```

#### Storage
- **Path**: `processed/gtfs_static/date=YYYY-MM-DD/`
- **Format**: Parquet (columnar, compressed)
- **Size**: ~50 MB per day
- **Retention**: Keep last 10 days (rotating)

---

## Implementation Roadmap (Weeks 3-6)

### Week 3: Core MTA Polling (20 hours)

#### Day 1-2: MTA API Integration
- [ ] Research MTA GTFS-RT API specification
- [ ] Setup local protobuf decoder testing
- [ ] Create `mta_client.py` wrapper for API calls
- [ ] Test API authentication and response parsing

#### Day 3-4: Lambda Function Development
- [ ] Create `mta-poller/lambda_function.py`
- [ ] Implement protobuf decoding
- [ ] Add error handling and retries
- [ ] Test locally with sam cli

#### Day 5: S3 Integration
- [ ] Implement S3 write to raw tier
- [ ] Add S3 partitioning logic
- [ ] Compress large responses
- [ ] Add S3 error handling

#### Day 6-7: Testing & Deployment
- [ ] Unit tests for each component
- [ ] Integration test (end-to-end)
- [ ] Deploy to AWS
- [ ] Monitor first 24 hours

### Week 4: Kinesis & Real-Time State (18 hours)

#### Day 1: Kinesis Setup (3 hours)
- [ ] Create Kinesis stream via CloudFormation
- [ ] Configure shard capacity
- [ ] Setup monitoring (iterator age, latency)

#### Day 2-3: DynamoDB Integration (8 hours)
- [ ] Create second Lambda: `kinesis-consumer`
- [ ] Read from Kinesis
- [ ] Transform to DynamoDB format
- [ ] Write to DynamoDB with error handling
- [ ] Implement TTL cleanup

#### Day 4-5: Testing & Monitoring (7 hours)
- [ ] Load test Kinesis throughput
- [ ] Verify DynamoDB state updates in real-time
- [ ] Setup CloudWatch dashboards
- [ ] Create alarms for failures

### Week 5: GTFS Static & Data Validation (15 hours)

#### Day 1-2: GTFS Downloader (8 hours)
- [ ] Create `gtfs-downloader/lambda_function.py`
- [ ] CSV parsing and validation
- [ ] Parquet conversion
- [ ] Schedule with EventBridge

#### Day 3-4: Data Validation (7 hours)
- [ ] Create validator Lambda
- [ ] Schema validation for MTA data
- [ ] Anomaly detection (missing fields, etc)
- [ ] DLQ for invalid records

### Week 6: Integration & Testing (10 hours)

#### Day 1-2: End-to-End Testing (6 hours)
- [ ] Verify data flows MTA → Kinesis → DynamoDB → S3
- [ ] Check data quality
- [ ] Monitor for 48 hours
- [ ] Document findings

#### Day 3: Documentation & Handoff (4 hours)
- [ ] Create Phase 1 runbook
- [ ] Document troubleshooting guide
- [ ] Write Phase 2 requirements
- [ ] Git commit and cleanup

---

## Key AWS Exam Concepts in Phase 1

### 1. **Data Ingestion Patterns**
- **Event-driven architecture**: EventBridge → Lambda
- **Streaming data**: Kinesis for real-time
- **Batch data**: S3 for immutable archive
- **Idempotency**: Handle duplicate API calls safely

### 2. **Data Partitioning** (CRITICAL)
- Year/Month/Day/Hour partitioning for S3
- Enables efficient Athena queries in Phase 2
- Cost optimization (partition pruning)
- This concept appears in ~15% of exam questions

### 3. **Lambda Best Practices**
- Timeouts vs long-running operations
- Concurrent execution limits
- Memory/CPU tradeoffs
- VPC vs public endpoint access

### 4. **Kinesis Architecture**
- Shard splitting and throughput scaling
- Consumer scaling (multiple Lambdas)
- Data retention and replay
- Enhanced Fan-Out for multiple consumers

### 5. **DynamoDB Design**
- Partition key selection (hotspotting avoidance)
- Sort key design for queries
- TTL for auto-deletion
- On-demand vs provisioned billing

### 6. **Error Handling & Resilience**
- DLQ for failed records
- Exponential backoff retries
- Circuit breaker patterns
- Graceful degradation

---

## AWS Services Used

| Service | Purpose | Configuration |
|---------|---------|---------------|
| **Lambda** | Polling and processing | 512 MB, 60s timeout |
| **EventBridge** | Scheduling | Every 30 seconds |
| **Kinesis** | Real-time streaming | 1 shard, 24h retention |
| **DynamoDB** | Real-time state | On-demand, 600s TTL |
| **S3** | Raw data archive | Partitioned by date/hour |
| **Secrets Manager** | API key storage | (From Phase 0) |
| **CloudWatch** | Monitoring | Logs + custom metrics |
| **IAM** | Access control | (From Phase 0) |

---

## Testing Strategy

### Unit Tests
- Test protobuf decoder with sample data
- Test S3 partitioning logic
- Test DynamoDB write operations

### Integration Tests
- Deploy to dev environment
- Send sample API requests
- Verify data appears in all 3 destinations
- Check for data loss or corruption

### Load Tests
- Simulate 1 month of data in 1 hour
- Verify Kinesis handles throughput
- Check DynamoDB latency under load
- Monitor S3 write performance

### Reliability Tests
- Kill Lambda mid-execution, verify retry
- Disconnect Kinesis, verify backoff
- Full 24-hour run monitoring

---

## Success Criteria

✅ Phase 1 is complete when:

1. **Data Ingestion**: MTA data flowing continuously for 24+ hours
2. **No Data Loss**: Every API response captured somewhere
3. **Real-Time Updates**: DynamoDB state <5 seconds from API
4. **S3 Archival**: 30+ days of raw data stored correctly
5. **GTFS Static**: Daily download and storage working
6. **Monitoring**: CloudWatch shows <1% error rate
7. **Documentation**: Runbook and troubleshooting guide created
8. **Ready for Phase 2**: Clean code, good test coverage

---

## Cost Breakdown (Phase 1)

| Service | Usage | Cost/Month |
|---------|-------|-----------|
| **Lambda** | 2.6M invocations/month | Free tier ($0) |
| **EventBridge** | 2.6M invocations | Free tier ($0) |
| **Kinesis** | 1 shard × 30 days | ~$26 |
| **DynamoDB** | ~2.5M writes/day | ~$18 |
| **S3** | ~100 GB storage | ~$2 |
| **CloudWatch** | Logs + metrics | ~$3-5 |
| **Data Transfer** | Within AWS | Free |
| **Secrets Manager** | 1 secret | ~$0.40 |
| **TOTAL** | — | **~$50-55/month** |

Phase 0 + Phase 1 combined: **~$52-60/month** ✅ Well within free tier!

---

## Common Pitfalls & Solutions

### 1. Protobuf Decoding Errors
**Problem**: "Invalid protobuf message"
**Solution**: Check MTA API response status, download latest GTFS-RT descriptor

### 2. DynamoDB Write Throttling
**Problem**: "ProvisionedThroughputExceededException"
**Solution**: We're using on-demand billing, so this shouldn't happen. If it does, add exponential backoff

### 3. S3 Partition Mismatches
**Problem**: Data in wrong time folder
**Solution**: Use Python's `datetime.utcnow()` consistently, handle timezone carefully

### 4. Memory Leaks in Lambda
**Problem**: Timeout errors on 3rd+ invocation
**Solution**: Explicitly close connections, use context managers

### 5. Kinesis Iterator Age High
**Problem**: Consumer lagging behind producer
**Solution**: Either increase shard count or increase Lambda concurrency

---

## Next Steps After Phase 1

Once Phase 1 is complete:
1. Begin **Phase 2**: Analytics pipeline (Glue, Athena, Redshift)
2. Start building fact tables from Phase 1 data
3. Create historical aggregations
4. Setup dashboards for operations team

---

## Resources

### Documentation
- [MTA GTFS-RT API Specification](http://datamine.mta.info/)
- [GTFS Realtime Reference](https://developers.google.com/transit/gtfs-realtime)
- [Kinesis Developer Guide](https://docs.aws.amazon.com/kinesis/)
- [DynamoDB Design Patterns](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/)

### Code References
- AWS Lambda Powertools: https://docs.aws.amazon.com/lambda/latest/dg/python-logging.html
- Protobuf Python: https://developers.google.com/protocol-buffers/docs/pythontutorial
- Boto3 Examples: https://boto3.amazonaws.com/v1/documentation/api/latest/index.html

---

**Phase 1 Status: 🔄 Ready to Begin Implementation**

Next: [Start building MTA poller Lambda →](./PHASE1_IMPLEMENTATION.md)
