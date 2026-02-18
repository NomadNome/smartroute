# SmartRoute: Technical Context Report for Production Planning
**Generated:** November 18, 2025
**Purpose:** Deep technical architecture scan for production phase transition
**Audience:** Engineering team planning IaC and architectural changes

---

## Executive Summary

SmartRoute is a fully functional route recommendation system integrating:
- **Real-time data:** MTA GTFS-RT feeds (1-minute polling)
- **AI intelligence:** Claude Haiku 4.5 via AWS Bedrock
- **Safety analytics:** Crime incident aggregation via Athena
- **Performance optimization:** DynamoDB caching (5-minute TTL, 80% hit rate)
- **Current cost:** ~$30/month for 1000 req/day

**Current deployment:** Manual (Lambda, API Gateway, DynamoDB)
**Next phase:** Infrastructure as Code + production hardening

---

## 1. DYNAMODB SCHEMAS

All 4 tables have been **converted to on-demand billing (PAY_PER_REQUEST)** as of Phase 4 Week 3.

### Table 1: `smartroute-route-cache` ⭐ PRIMARY
**Purpose:** Cache route recommendation results (Bedrock outputs)
**Billing:** On-demand
**Read/Write:** GetItem + PutItem pattern

| Attribute | Type | Role | Description |
|-----------|------|------|-------------|
| `cache_key` | String | **Partition Key** | MD5(origin\|destination\|criterion) |
| `data` | Map | Content | Full route response object |
| `expiry` | Number | TTL Attribute | Unix timestamp for auto-delete |
| `created_at` | String | Metadata | ISO 8601 timestamp |

**TTL Config:** 300 seconds (5 minutes)
**Expected Hit Rate:** 80% in production
**Creation Script:** `/lambdas/bedrock-router/setup_infrastructure.sh` (Lines 24-34)

```python
# Access pattern from lambda_function.py (Lines 272-290)
def get_from_cache(cache_key):
    response = cache_table.get_item(Key={'cache_key': cache_key})
    if 'Item' in response:
        item = response['Item']
        if int(item['expiry']) > time.time():
            return item['data']
    return None

def put_in_cache(cache_key, data):
    cache_table.put_item(Item={
        'cache_key': cache_key,
        'data': data,
        'expiry': int(time.time()) + CACHE_TTL_SECONDS,
        'created_at': datetime.utcnow().isoformat()
    })
```

---

### Table 2: `smartroute_station_realtime_state` 🔴 REALTIME DATA
**Purpose:** Real-time MTA train arrivals for each station
**Billing:** On-demand
**Read Pattern:** Query + ScanIndexForward for latest arrivals

| Attribute | Type | Role | Description |
|-----------|------|------|-------------|
| `station_id` | String | **Partition Key** | MTA stop ID (e.g., "127N") |
| `timestamp` | Number | **Sort Key** | Unix epoch (seconds) |
| `station_name` | String | Metadata | Human-readable name |
| `lines` | List<String> | Metadata | Line IDs serving this station |
| `next_arrivals` | List<Map> | Content | Array of upcoming trains |
| `crowding` | String | Metadata | LIGHT/MODERATE/HEAVY |
| `safety_score` | Number | Metadata | 0-10 aggregated safety |
| `alerts` | List<String> | Metadata | Active service alerts |
| `last_update` | Number | Metadata | When data was last refreshed |
| `expiration_time` | Number | TTL Attribute | Auto-delete after 10 min |

**TTL Config:** 600 seconds (10 minutes)
**Stream:** NEW_AND_OLD_IMAGES (for analytics pipeline)
**Source:** MTA Poller Lambda writes every minute

**Sample Item:**
```json
{
  "station_id": "127N",
  "timestamp": 1730300760,
  "station_name": "125 Street",
  "lines": ["1", "2", "3"],
  "next_arrivals": [
    {
      "line": "1",
      "arrival_seconds": 180,
      "destination": "Van Cortlandt Park",
      "vehicle_id": "1234",
      "delay_seconds": 45
    }
  ],
  "crowding": "MODERATE",
  "safety_score": 7.5,
  "expiration_time": 1730301360
}
```

**CloudFormation:** `/infrastructure/cloudformation/phase-0-foundation.yaml` (Lines 142-167)

---

### Table 3: `smartroute_cached_routes` 🟡 LEGACY
**Purpose:** Cache Google Maps API responses (Phase 2)
**Billing:** On-demand
**Status:** Present but deprecated by route-cache

| Attribute | Type | Role |
|-----------|------|------|
| `route_hash` | String | **Partition Key** |
| `timestamp` | Number | **Sort Key** |
| `expiration_time` | Number | TTL Attribute |

**TTL Config:** 3600 seconds (1 hour)

**CloudFormation:** `/infrastructure/cloudformation/phase-0-foundation.yaml` (Lines 168-191)

---

### Table 4: `smartroute_user_sessions` 👤 SESSIONS
**Purpose:** Web app user session storage
**Billing:** On-demand
**Usage:** Minimal (development/testing only)

| Attribute | Type | Role |
|-----------|------|------|
| `user_id` | String | **Partition Key** |
| `session_id` | String | **Sort Key** |
| `current_location` | Map | Coordinates + station |
| `preferences` | Map | User settings |
| `search_history` | List | Previous searches |
| `ttl` | Number | TTL Attribute (24h) |

**CloudFormation:** `/infrastructure/cloudformation/phase-0-foundation.yaml` (Lines 192-215)

---

## 2. ATHENA/S3 DATA STRUCTURE

### S3 Data Lake Architecture
**Bucket:** `smartroute-data-lake-069899605581` (AWS Account: 069899605581)

```
smartroute-data-lake-069899605581/
├── raw/
│   ├── mta/
│   │   ├── realtime/
│   │   │   └── year={YYYY}/month={MM}/day={DD}/hour={HH}/
│   │   │       └── vehicles-{timestamp}.json (protobuf decoded)
│   │   ├── gtfs_static/
│   │   └── service_status/
│   ├── crime/
│   │   ├── year={YYYY}/month={MM}/day={DD}/
│   │   └── incidents-{timestamp}.json (NYC Open Data)
│   └── 311/
│       ├── year={YYYY}/month={MM}/day={DD}/
│       └── complaints-{timestamp}.json (NYC Open Data)
│
├── processed/
│   ├── vehicles/ (Parquet, partitioned by year/month/day/hour)
│   ├── crime_by_station/ (Parquet, aggregated per station)
│   └── 311_by_station/ (Parquet, aggregated per station)
│
├── analytics/
│   ├── delay_metrics/ (Parquet, year/month/day/hour partitions)
│   └── crowding_metrics/ (Parquet, year/month/day/hour partitions)
│
├── athena-results/
│   └── [temporary query output files]
│
└── logs/
    └── [Lambda execution logs]
```

**S3 Lifecycle Rules:**
| Path | Storage Class | Duration |
|------|---------------|----------|
| `raw/` | STANDARD → IA | 30 days → 90 days, delete at 365 days |
| `processed/` | STANDARD → IA | 60 days → 180 days |
| `logs/` | STANDARD | Delete at 90 days |

**Partitioning Strategy:** Year/Month/Day/Hour for efficient Athena queries
**Format:** Parquet (compressed with Snappy)

---

### Athena Configuration
**Database:** `smartroute_analytics` (created by Glue)
**Database:** `smartroute_data` (for crime queries)
**WorkGroup:** `smartroute-analytics`
**Output Location:** `s3://smartroute-data-lake-069899605581/athena-results/`
**Query Timeout:** 30 minutes (default)
**Bytes Scanned Limit:** 10 GB per query

---

### Athena Table Schemas

#### Table 1: `smartroute_analytics.vehicles` (Real-time MTA Data)
**Source:** `/infrastructure/glue/athena_tables.sql` (Lines 8-24)

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS smartroute_analytics.vehicles (
    batch_timestamp BIGINT,
    trip_id STRING,
    route_id STRING,
    stop_id STRING,
    arrival_time BIGINT,
    arrival_delay_seconds BIGINT,
    next_arrival_seconds BIGINT,
    headsign STRING,
    vehicle_id STRING,
    timestamp BIGINT,
    feed_path STRING
)
PARTITIONED BY (year INT, month INT, day INT, hour INT)
STORED AS PARQUET
LOCATION 's3://smartroute-data-lake-069899605581/processed/vehicles/'
TBLPROPERTIES ('parquet.compression'='snappy');
```

**Record Format (sample):**
```json
{
  "batch_timestamp": 1730300760000,
  "trip_id": "012500_1..N",
  "route_id": "1",
  "stop_id": "127N",
  "arrival_time": 1730300940,
  "arrival_delay_seconds": 45,
  "next_arrival_seconds": 180,
  "headsign": "Van Cortlandt Park-242 St",
  "vehicle_id": "1234",
  "timestamp": 1730300760,
  "feed_path": "nyct/gtfs"
}
```

---

#### Table 2: `smartroute_analytics.delay_metrics` (Aggregated Metrics)
**Source:** `/infrastructure/glue/athena_tables.sql` (Lines 27-39)

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS smartroute_analytics.delay_metrics (
    route_id STRING,
    total_vehicles BIGINT,
    avg_delay_seconds DOUBLE,
    max_delay_seconds BIGINT,
    min_delay_seconds BIGINT,
    stddev_delay_seconds DOUBLE,
    on_time_pct DOUBLE
)
PARTITIONED BY (year INT, month INT, day INT, hour INT)
STORED AS PARQUET
LOCATION 's3://smartroute-data-lake-069899605581/analytics/delay_metrics/'
TBLPROPERTIES ('parquet.compression'='snappy');
```

---

#### Table 3: `smartroute_analytics.crowding_metrics` (Station Traffic)
**Source:** `/infrastructure/glue/athena_tables.sql` (Lines 42-52)

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS smartroute_analytics.crowding_metrics (
    stop_id STRING,
    route_id STRING,
    vehicle_count BIGINT,
    unique_trips BIGINT,
    vehicle_frequency_per_hour BIGINT
)
PARTITIONED BY (year INT, month INT, day INT, hour INT)
STORED AS PARQUET
LOCATION 's3://smartroute-data-lake-069899605581/analytics/crowding_metrics/'
TBLPROPERTIES ('parquet.compression'='snappy');
```

---

#### Table 4: `smartroute_data.crime_by_station` (Safety Intelligence)
**Purpose:** 7-day rolling window of NYC crime incidents aggregated by station
**Source:** Phase 3 Glue job (scheduled daily)

```sql
-- Inferred schema from Lambda query pattern
CREATE EXTERNAL TABLE smartroute_data.crime_by_station (
    station_name STRING,
    incident_date VARCHAR(10),       -- YYYY-MM-DD format
    safety_score DOUBLE,             -- 0-10, lower = more incidents
    incident_count BIGINT,
    precinct_code STRING,
    incident_category STRING,
    incident_type STRING
)
LOCATION 's3://smartroute-data-lake-069899605581/processed/crime_by_station/'
STORED AS PARQUET
```

---

### Crime Data Query (Used in Production)
**Location:** `/lambdas/bedrock-router/lambda_function.py` (Lines 115-153)

**Current Query:**
```sql
SELECT
    station_name,
    COUNT(*) as incident_count,
    APPROX_PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY safety_score) as median_safety
FROM smartroute_data.crime_by_station
WHERE station_name = '{station_name}'
  AND incident_date >= CAST(CURRENT_DATE - INTERVAL '1' DAY * 7 AS VARCHAR)
GROUP BY station_name
```

**Execution Pattern:**
```python
# From lambda_function.py (Lines 164-202)
def get_crime_data(self, station_name: str, days: int = 7) -> Dict:
    query = f"""
    SELECT
        station_name,
        COUNT(*) as incident_count,
        APPROX_PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY safety_score) as median_safety
    FROM {self.database}.crime_by_station
    WHERE station_name = '{station_name}'
      AND incident_date >= CAST(CURRENT_DATE - INTERVAL '1' DAY * {days} AS VARCHAR)
    GROUP BY station_name
    """

    query_id = self._execute_query(query)
    result = self._get_query_results(query_id, max_retries=10)

    if result and len(result) > 1:
        row = result[1]  # Skip header
        return {
            "station_name": row[0],
            "incident_count": int(row[1]) if row[1] else 0,
            "median_safety_score": float(row[2]) if row[2] else 5.0
        }
```

**Performance:**
- Query time: 2-5 seconds (depends on data size)
- Data scanned: ~5-50 MB per query
- Cost: ~$0.000025-0.0001 per query
- Timeout: 10 retries of 0.5s each = 5 second limit

---

## 3. MTA DATA & MOCKS

### Real MTA GTFS-RT Feeds (Public URLs)

**API Base:** `https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds`
**Authentication:** Free (MTA API Key in `.env`, optional for testing)
**Update Frequency:** Real-time (1 second) from MTA
**Polling Interval:** Every 1 minute via EventBridge + Lambda

**Feed Distribution (6 separate feeds):**
```python
MTA_FEEDS = {
    '1': 'arn:aws:s3:::smartroute-data-lake/raw/mta/realtime/1.pb',
    '2/3': 'arn:aws:s3:::smartroute-data-lake/raw/mta/realtime/2-3.pb',
    '4/5': 'arn:aws:s3:::smartroute-data-lake/raw/mta/realtime/4-5.pb',
    '6': 'arn:aws:s3:::smartroute-data-lake/raw/mta/realtime/6.pb',
    'NQRW': 'arn:aws:s3:::smartroute-data-lake/raw/mta/realtime/NQRW.pb',
    'ACE': 'arn:aws:s3:::smartroute-data-lake/raw/mta/realtime/ACE.pb'
}
```

**Source:** `/lambdas/mta-poller/lambda_function.py` (Lines 42-54)

---

### Station Data Structure (Expected Format)

**From DynamoDB (`smartroute_station_realtime_state`):**
```json
{
  "station_id": "127N",
  "timestamp": 1730300760,
  "station_name": "125 Street",
  "lines": ["1", "2", "3"],
  "next_arrivals": [
    {
      "line": "1",
      "arrival_seconds": 180,
      "destination": "Van Cortlandt Park",
      "vehicle_id": "1234",
      "arrival_time": 1730300940,
      "delay_seconds": 45,
      "timestamp": 1730300760
    },
    {
      "line": "2",
      "arrival_seconds": 450,
      "destination": "Flatbush-Brooklyn College",
      "vehicle_id": "5678",
      "arrival_time": 1730301210,
      "delay_seconds": 120,
      "timestamp": 1730300760
    }
  ],
  "crowding": "MODERATE",
  "safety_score": 7.5,
  "alerts": [],
  "last_update": 1730300760,
  "expiration_time": 1730301360
}
```

**From Lambda Input (to route recommender):**
```json
{
  "origin_station": "Times Square-42nd Street",
  "destination_station": "Grand Central-42nd Street",
  "criterion": "balanced",
  "next_arrivals_origin": [
    {
      "line": "1",
      "arrival_seconds": 120,
      "destination": "Van Cortlandt",
      "delay_seconds": 30
    }
  ],
  "next_arrivals_destination": [
    {
      "line": "1",
      "arrival_seconds": 300,
      "destination": "South Ferry",
      "delay_seconds": 15
    }
  ]
}
```

---

### NYC Stations Database

**File:** `/lambdas/bedrock-router/nyc_stations.py`
**Format:** Python dictionary
**Total Stations:** 50+ major NYC subway stations

**Sample Data:**
```python
NYC_STATIONS = {
    "Times Square-42nd Street": {
        "lat": 40.7580,
        "lng": -73.9855,
        "lines": ["1", "2", "3", "S"]
    },
    "Grand Central-42nd Street": {
        "lat": 40.7527,
        "lng": -73.9772,
        "lines": ["4", "5", "6", "7", "S"]
    },
    "Brooklyn Bridge-City Hall": {
        "lat": 40.7127,
        "lng": -74.0059,
        "lines": ["4", "5", "6"]
    },
    "Wall Street": {
        "lat": 40.7074,
        "lng": -74.0113,
        "lines": ["4", "5"]
    },
    # ... 46+ more stations
}
```

**Lookup Pattern:**
```python
def resolve_station(address_or_station: str) -> Tuple[Optional[str], float]:
    """
    1. Try exact match (case-insensitive)
    2. Try partial match ("times" → "Times Square-42nd Street")
    3. Return None if no match
    """
    for station_name in NYC_STATIONS.keys():
        if station_name.lower() == address_or_station.lower():
            return station_name, 0.0

    normalized_input = address_or_station.lower()
    for station_name in NYC_STATIONS.keys():
        if normalized_input in station_name.lower():
            return station_name, 0.0

    return None, 0.0
```

---

### Realtime Travel Calculator

**File:** `/lambdas/bedrock-router/realtime_travel_calculator.py`

**Key Functions:**
```python
def get_stop_id_for_station(station_name: str) -> Optional[str]:
    """Convert friendly name to MTA stop ID"""
    # Returns: "127N", "42ST", etc.

def get_station_arrivals(stop_id: str) -> List[Dict]:
    """Query DynamoDB for next arrivals (most recent timestamp)"""
    # Returns: [{"line": "1", "arrival_seconds": 120, ...}, ...]

def calculate_route_travel_time(stations: List[str], lines: List[str]) -> Tuple[int, str]:
    """Calculate total travel time using real-time ETAs"""
    # Returns: (total_seconds, "~5 minutes")
```

**Data Flow:**
1. User provides: origin → destination
2. resolve_station(): "Times Square" → "Times Square-42nd Street"
3. get_station_arrivals(): Query DynamoDB for realtime state
4. calculate_route_travel_time(): Sum ETAs across stations
5. Fallback: 2 min/stop if no realtime data available

---

## 4. CURRENT IAM ROLE & PERMISSIONS

### Lambda Execution Role: `smartroute-bedrock-lambda-role`

**ARN:** `arn:aws:iam::069899605581:role/smartroute-bedrock-lambda-role`
**Used By:** `smartroute-route-recommender` Lambda function
**Created:** Phase 4 Week 1
**Trust Policy:**
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

---

### Attached Policies

#### 1. AWS Managed: `AWSLambdaBasicExecutionRole`
**ARN:** `arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:069899605581:*"
    }
  ]
}
```

**Purpose:** CloudWatch Logs for Lambda execution logging

---

#### 2. Custom Inline: `smartroute-dynamodb-cache-policy`

**Source:** `/lambdas/bedrock-router/setup_infrastructure.sh` (Lines 56-72)

```json
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
      "Resource": [
        "arn:aws:dynamodb:us-east-1:069899605581:table/smartroute-route-cache",
        "arn:aws:dynamodb:us-east-1:069899605581:table/smartroute_station_realtime_state",
        "arn:aws:dynamodb:us-east-1:069899605581:table/smartroute_cached_routes",
        "arn:aws:dynamodb:us-east-1:069899605581:table/smartroute_user_sessions"
      ]
    }
  ]
}
```

**Operations Allowed:**
- `GetItem` - Fetch route from cache
- `PutItem` - Store new route in cache
- `Query` - Scan station realtime state
- `UpdateItem` - Update existing items

**Note:** Scan operations NOT included (would be needed for full table scans)

---

#### 3. Custom Inline: `smartroute-athena-policy`

**Source:** `/lambdas/bedrock-router/setup_infrastructure.sh` (Lines 85-112)

```json
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
        "arn:aws:s3:::smartroute-data-lake-069899605581",
        "arn:aws:s3:::smartroute-data-lake-069899605581/processed/*"
      ]
    }
  ]
}
```

**Operations Allowed:**
- Athena: Start query, get status, fetch results, cancel query
- S3: Read/write athena-results, list buckets, read processed data

**Cost Implication:**
- Athena queries charged by bytes scanned (10GB limit)
- S3 GetObject/PutObject cost minimal for this workload

---

#### 4. Custom Inline: `smartroute-bedrock-policy`

**Source:** `/infrastructure/cloudformation/phase-0-foundation.yaml` (referenced)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "arn:aws:bedrock:us-east-1::inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0"
    }
  ]
}
```

**Model Access:**
- Claude Haiku 4.5 via inference profile (on-demand, cross-region)
- Not hardcoded to specific model version (flexibility)

---

#### 5. Custom Inline: `smartroute-secrets-policy`

**Source:** `/infrastructure/cloudformation/phase-0-foundation.yaml` (Lines 275-282)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:069899605581:secret:smartroute/*"
    }
  ]
}
```

**Secrets Stored:**
- `smartroute/mta-api-key` - MTA GTFS-RT API key
- `smartroute/google-maps-key` - Google Maps API key
- `smartroute/bedrock-config` - Bedrock model preferences

---

### Alternative Role: `smartroute-lambda-execution-role`

**Used By:** Other Lambda functions (mta-poller, realtime-processor, enrichment)

**Additional Permissions:**
- S3: `DeleteObject` (for cleanup)
- Kinesis: `PutRecord`, `PutRecords`, `GetRecords`, `DescribeStream`
- DynamoDB: `Scan` (in addition to Query/GetItem/PutItem)
- SNS: `Publish` (for error notifications)
- SQS: `SendMessage`, `ReceiveMessage` (for queue-based processing)

---

## 5. BEDROCK INTEGRATION DETAILS

### Model Configuration

**Model:** Claude Haiku 4.5
**Model ID:** `arn:aws:bedrock:us-east-1::inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0`
**Inference Type:** Cross-region inference profile (on-demand)
**Fallback Model:** None configured (would require manual update)

**Source:** `/lambdas/bedrock-router/bedrock_route_recommender.py` (Line 37)

```python
INFERENCE_PROFILE_ARN = "arn:aws:bedrock:us-east-1::inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0"

def invoke_bedrock(self, message: str) -> str:
    response = self.bedrock_runtime.invoke_model(
        modelId=INFERENCE_PROFILE_ARN,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": message
                }
            ],
            "system": self.build_system_prompt()
        })
    )
```

**Advantages of Inference Profile:**
- Cross-region load balancing (auto-failover)
- On-demand scaling (no provisioned throughput)
- No cold starts
- Simpler pricing (PAYG)

---

### Prompt Engineering Strategy

**System Prompt:** (from `/lambdas/bedrock-router/bedrock_route_recommender.py`)
```
You are SmartRoute, an intelligent NYC subway route recommendation system.
Your job is to recommend the BEST route from origin to destination considering:

1. SAFETY: Lower crime incidents near stations = safer
2. RELIABILITY: Higher on-time performance = more reliable
3. EFFICIENCY: Fewer transfers and less wait time = faster
4. BALANCE: Consider all factors for best overall experience

Always provide exactly THREE route options:
1. SafeRoute - Prioritizes safety (low crime, reliable lines)
2. FastRoute - Prioritizes speed (direct, fewer stops)
3. BalancedRoute - Best overall experience (compromise of all factors)

For each route, provide:
- List of stations in order
- Estimated travel time (in minutes)
- Line(s) used
- Safety score (0-10)
- Reliability score (0-10)
- Efficiency score (0-10)
- Natural language explanation

Output as JSON with this structure:
{
  "SafeRoute": {"stations": [...], "lines": [...], ...},
  "FastRoute": {...},
  "BalancedRoute": {...}
}
```

**User Message Template:**
```
Route: {origin_station} → {destination_station}
Criterion: {criterion} (safe/fast/balanced)

Real-time data:
- Origin next arrivals: {json.dumps(origin_trains)}
- Destination next arrivals: {json.dumps(dest_trains)}

Safety data (7-day):
- {origin_station}: {incident_count} incidents, safety score {safety_score}/10
- {destination_station}: {incident_count} incidents, safety score {safety_score}/10

Walking distances:
- To origin: {distance_km} km
- To destination: {distance_km} km

Recommend best routes.
```

---

### Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| **Latency** | 3.9s | Cold (no cache) |
| **Token Usage (Input)** | ~500 tokens | Includes context data |
| **Token Usage (Output)** | ~200 tokens | JSON response |
| **Cost/Request** | $0.0001 | At current token rates |
| **Monthly Cost (1000 req/day)** | $3.00 | 80% cache hit rate |

**Model Costs (from Anthropic pricing):**
- Input: $0.80 per 1M tokens
- Output: $0.40 per 1M tokens

---

## 6. LAMBDA FUNCTION DETAILS

### Primary Function: `smartroute-route-recommender`

**Type:** HTTP API (REST)
**Runtime:** Python 3.11
**Memory:** 512 MB
**Timeout:** 60 seconds
**Ephemeral Storage:** 512 MB (default)

**Deployment Package:**
- Size: ~2.5 MB (after removing requests module)
- Contents:
  - `lambda_function.py` (~600 lines)
  - `bedrock_route_recommender.py` (~350 lines)
  - `nyc_stations.py` (~200 lines)
  - `realtime_travel_calculator.py` (~200 lines)
  - `station_mappings.py` (~100 lines)

**Environment Variables:**
```bash
ATHENA_DATABASE = "smartroute_data"
ATHENA_OUTPUT_LOCATION = "s3://smartroute-data-lake-069899605581/athena-results/"
CACHE_TABLE_NAME = "smartroute-route-cache"
REALTIME_TABLE_NAME = "smartroute_station_realtime_state"
CACHE_TTL_SECONDS = "300"
```

**Dependencies (all built-in to Python 3.11 Lambda runtime):**
- `boto3` (AWS SDK)
- `python-dateutil` (date handling)
- No external packages required!

---

### Request/Response Specification

**Input Format (from API Gateway):**
```json
{
  "body": {
    "origin_address": "Times Square",
    "destination_address": "Grand Central",
    "criterion": "balanced"
  }
}
```

**Validation Rules:**
- `origin_address`: Required, non-empty string
- `destination_address`: Required, non-empty string
- `criterion`: Optional, must be one of: "safe", "fast", "balanced" (defaults to "balanced")

**Success Response (200):**
```json
{
  "statusCode": 200,
  "headers": {"Content-Type": "application/json"},
  "body": "{...route recommendation JSON...}"
}
```

**Error Response (400/500):**
```json
{
  "statusCode": 400,
  "headers": {"Content-Type": "application/json"},
  "body": "{\"error\": \"Could not resolve origin/destination to stations\", \"timestamp\": \"2025-11-18T...\"}"
}
```

---

## 7. API GATEWAY CONFIGURATION

### Endpoint Details

**API ID:** `fm5gv3woye`
**Stage Name:** `prod`
**Region:** `us-east-1`
**Full URL:** `https://fm5gv3woye.execute-api.us-east-1.amazonaws.com/prod/recommend`

**Method:** POST
**Integration Type:** Lambda Proxy
**Lambda Target:** `smartroute-route-recommender`

---

### CORS Configuration

```json
{
  "AllowedOrigins": ["*"],
  "AllowedMethods": ["POST"],
  "AllowedHeaders": ["Content-Type", "Authorization"],
  "ExposedHeaders": ["x-amzn-RequestId"],
  "MaxAge": 86400,
  "AllowCredentials": false
}
```

---

### Request/Response Mapping

**Request Template:**
```
$input.json('$')
```

**Response Template:**
```
$input.path('$')
```

**Authorizer:** None (public endpoint)

---

## 8. PRODUCTION READINESS ASSESSMENT

### ✅ Ready for Production
- [x] DynamoDB on-demand billing configured
- [x] Lambda function tested and optimized
- [x] Bedrock integration working (Claude Haiku 4.5)
- [x] Athena queries functional
- [x] API Gateway deployed with CORS
- [x] Error handling implemented
- [x] 5-minute caching reducing cost 5x
- [x] CloudWatch logs enabled

### ⚠️ Needs Attention Before Production
- [ ] Real MTA data pipeline (Phase 1 - in progress)
- [ ] Crime data refresh automation (Phase 3 - Glue jobs need scheduling)
- [ ] SSL/TLS certificate for HTTPS
- [ ] Rate limiting on API Gateway
- [ ] DDoS protection (AWS Shield Standard)
- [ ] CloudWatch dashboards for monitoring
- [ ] X-Ray tracing enabled
- [ ] Cost monitoring/budgets set

### 🔴 Missing for Full Production
- [ ] Infrastructure as Code (IaC) - currently manual
- [ ] CI/CD pipeline
- [ ] Automated testing
- [ ] Load testing & capacity planning
- [ ] Disaster recovery/backup strategy
- [ ] Documentation for ops team
- [ ] Runbooks for troubleshooting

---

## 9. REFACTORING OPPORTUNITIES FOR PRODUCTION

### Data Optimization
**Current:** Athena queries on each request (with cache)
**Recommended:** Pre-compute crime statistics, cache in DynamoDB

**Current:** DynamoDB table scan for station lookups
**Recommended:** ElastiCache (Redis) for <1ms station lookups

### Architecture Improvements
**Current:** Synchronous Lambda → Bedrock → Athena
**Recommended:** Step Functions for complex workflows, SQS for async processing

**Current:** 4 separate DynamoDB tables
**Recommended:** Consolidate to 2-3 tables with GSI for flexibility

### API Enhancements
**Current:** REST API (stateless)
**Recommended:** GraphQL for flexible queries, WebSocket for real-time updates

### Infrastructure
**Current:** Manual deployment
**Recommended:** Terraform/CloudFormation pipeline with CI/CD

---

## 10. DEPENDENCY MAP

```
Frontend (React)
    ↓
Express.js (localhost:3001)
    ↓
API Gateway (fm5gv3woye)
    ↓
Lambda (smartroute-route-recommender)
    ├── DynamoDB
    │   ├── smartroute-route-cache (cache hits)
    │   └── smartroute_station_realtime_state (real-time data)
    │
    ├── Athena Query
    │   ├── smartroute_data.crime_by_station
    │   └── S3 (athena-results/)
    │
    ├── Bedrock
    │   └── Claude Haiku 4.5 (inference profile)
    │
    └── Secrets Manager
        ├── MTA API Key
        └── Google Maps Key

Real-time Data Sources:
    ├── MTA GTFS-RT (every 1 min)
    │   └── Lambda Poller → S3 → Athena
    │
    ├── NYC Crime Data (daily)
    │   └── NYC Open Data → S3 → Glue Job → Athena
    │
    └── NYC 311 Complaints (daily)
        └── NYC Open Data → S3 → Glue Job → Athena
```

---

## Appendix: Quick Reference

### Key File Locations
- **Lambda Code:** `/lambdas/bedrock-router/`
- **CloudFormation:** `/infrastructure/cloudformation/`
- **Glue Jobs:** `/infrastructure/glue/`
- **Frontend:** `/frontend/`
- **Phase Documentation:** `PHASE_*_*.md` files in root

### Critical ARNs
```
Role:      arn:aws:iam::069899605581:role/smartroute-bedrock-lambda-role
Lambda:    arn:aws:lambda:us-east-1:069899605581:function:smartroute-route-recommender
DynamoDB:  arn:aws:dynamodb:us-east-1:069899605581:table/smartroute-route-cache
Bedrock:   arn:aws:bedrock:us-east-1::inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0
S3 Bucket: arn:aws:s3:::smartroute-data-lake-069899605581
```

### Environment References
```
AWS Account: 069899605581
Region: us-east-1
API Endpoint: https://fm5gv3woye.execute-api.us-east-1.amazonaws.com/prod/recommend
Frontend Port: localhost:3001
```

---

**Report Generated:** November 18, 2025
**Next Action:** Begin Phase 5 Planning with this technical context
