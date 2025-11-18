# SmartRoute Phase 2: Analytics & Enrichment - Implementation Summary

## 🎯 Phase 2 Objectives
Transform real-time MTA data into actionable analytics using AWS Glue and Athena for:
- Reliability metrics (on-time performance, delays)
- Crowding analysis and estimation
- Service quality insights
- Historical trend analysis

## ✅ What We Built

### 1. Infrastructure (CloudFormation)
- **Glue Database**: `smartroute_analytics` for catalog management
- **Glue Crawler**: Auto-discovers schema from raw S3 data (hourly schedule)
- **Athena WorkGroup**: `smartroute-analytics` with query result storage
- **S3 Buckets**: Dedicated Athena results bucket with 30-day retention
- **IAM Role**: Full permissions for Glue jobs and S3 access

**Stack Status**: ✅ CREATE_COMPLETE

### 2. Glue ETL Jobs

#### Job 1: JSON-to-Parquet Transformation
- **Name**: `smartroute-json-to-parquet`
- **Input**: Raw JSON from `s3://smartroute-data-lake-069899605581/raw/mta/realtime`
- **Output**: Parquet format at `s3://smartroute-data-lake-069899605581/processed/vehicles`
- **Transformations**:
  - Flattens nested vehicle_records array
  - Adds date/hour partitioning columns (year/month/day/hour)
  - Converts timestamps to proper datetime
  - Snappy compression for efficiency

#### Job 2: Metrics Aggregation
- **Name**: `smartroute-metrics-aggregation`
- **Input**: Parquet vehicle data from processed layer
- **Outputs**:
  - Delay metrics: `s3://smartroute-data-lake-069899605581/analytics/delay_metrics`
  - Crowding metrics: `s3://smartroute-data-lake-069899605581/analytics/crowding_metrics`
- **Calculations**:
  - **Delay Metrics**: avg/min/max delays, std deviation, on-time percentage
  - **Crowding Metrics**: vehicle count, unique trips, frequency per hour
  - **Grouping**: By route_id, stop_id, year/month/day/hour

### 3. Athena External Tables

Three external tables created for analytics:

#### Table 1: `smartroute_analytics.vehicles`
- Processed vehicle data (Parquet format)
- Columns: trip_id, route_id, stop_id, headsign, delays, timestamps
- Partitioned by: year, month, day, hour
- Location: `processed/vehicles/`

#### Table 2: `smartroute_analytics.delay_metrics`
- Aggregated reliability metrics
- Columns: route_id, total_vehicles, avg_delay_seconds, on_time_pct
- Partitioned by: year, month, day, hour
- Location: `analytics/delay_metrics/`

#### Table 3: `smartroute_analytics.crowding_metrics`
- Crowding and frequency data
- Columns: stop_id, route_id, vehicle_count, unique_trips, frequency
- Partitioned by: year, month, day, hour
- Location: `analytics/crowding_metrics/`

### 4. Analytics Queries

Five pre-built Athena SQL queries:

1. **On-Time Performance by Line** - Current hour reliability
2. **Most Crowded Stations** - Top 20 busiest stations
3. **Hourly Delay Trends** - Delay pattern for specific line
4. **Service Reliability Ranking** - Top 5 most reliable lines
5. **Station Vehicle Distribution** - Frequency patterns

## 📊 Data Flow Architecture

```
Real-time Lambda (Phase 1)
         ↓
Raw JSON → S3 (raw/mta/realtime)
         ↓
Glue Crawler (hourly)
         ↓
         ├─→ [Glue Job 1: JSON→Parquet]
         │        ↓
         │   Parquet Lake (processed/vehicles)
         │        ↓
         └─→ [Glue Job 2: Metrics Aggregation]
                  ↓
          ┌──────┴──────┐
          ↓             ↓
    Delay Metrics  Crowding Metrics
    (analytics/)   (analytics/)
          ↓             ↓
          └──────┬──────┘
                 ↓
          Athena External Tables
                 ↓
          SQL Analytics Queries
                 ↓
          Dashboard / Reporting
```

## 🚀 Next Steps (Phase 2.5)

### Execute and Test

1. **Run the Glue Crawler** (manually or wait for schedule):
   ```bash
   aws glue start-crawler --name smartroute-vehicle-data-crawler
   ```

2. **Run the ETL Jobs** (in sequence):
   ```bash
   # First job: Transform JSON to Parquet
   aws glue start-job-run \
     --job-name smartroute-json-to-parquet \
     --arguments '{"S3_INPUT_PATH":"s3://smartroute-data-lake-069899605581/raw/mta/realtime","S3_OUTPUT_PATH":"s3://smartroute-data-lake-069899605581/processed"}'
   
   # Second job: Aggregate metrics
   aws glue start-job-run \
     --job-name smartroute-metrics-aggregation \
     --arguments '{"S3_INPUT_PATH":"s3://smartroute-data-lake-069899605581/processed","S3_OUTPUT_PATH":"s3://smartroute-data-lake-069899605581/analytics"}'
   ```

3. **Create Athena Tables** (run athena_tables.sql in Athena console)

4. **Test Queries** (run sample queries to validate data)

## 💰 Cost Impact

**Phase 2 adds (~$10-25/month)**:
- Glue: ~$0.44 per DPU-hour (2 jobs × 2 DPU × 1 hour/day) = ~$12/mo
- Athena: ~$6/mo (5 query runs × 100 GB scans monthly)
- S3: ~$3/mo (processed + analytics storage)

**Total Phase 1+2: ~$75-90/month**

## 🔍 Key Insights to Monitor

Once data starts flowing:
1. **Reliability**: Which lines have highest delays?
2. **Crowding**: Which stations are busiest at what times?
3. **Trends**: Are delays increasing at certain hours?
4. **Frequency**: Is service frequency consistent?

## 📝 Files Created

- `infrastructure/glue/phase-2-analytics.yaml` - CloudFormation template
- `infrastructure/glue/athena_tables.sql` - Athena DDL and sample queries
- `scripts/glue_json_to_parquet.py` - Transformation ETL job
- `scripts/glue_metrics_aggregation.py` - Aggregation ETL job

## 🎓 AWS Data Engineer Concepts Covered

✅ **Glue Catalog**: Data discovery and metadata management
✅ **Glue ETL**: Apache Spark-based transformations (PySpark)
✅ **Data Formats**: JSON → Parquet conversion for efficiency
✅ **Partitioning**: Time-based partitioning for query performance
✅ **Athena**: SQL on S3 without data warehousing
✅ **Schema Management**: External tables pointing to S3 data
✅ **Query Optimization**: Partition pruning, file format selection

---

**Status**: Phase 2 infrastructure ready for testing and validation
**Next Phase**: Phase 2.5 (Test, Phase 3 (Safety Intelligence)
