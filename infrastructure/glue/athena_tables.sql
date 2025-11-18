-- SmartRoute Phase 2: Athena External Tables for Analytics
-- Run these in Athena console to create tables for analysis

-- Create database (if not exists)
CREATE DATABASE IF NOT EXISTS smartroute_analytics;

-- Vehicle data table (raw Parquet from Glue transformation)
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

-- Delay metrics table (aggregated)
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

-- Crowding metrics table (aggregated)
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

-- SAMPLE ANALYTICS QUERIES

-- Query 1: On-time performance by line (current hour)
SELECT 
    route_id,
    total_vehicles,
    ROUND(avg_delay_seconds, 2) as avg_delay_sec,
    ROUND(on_time_pct, 2) as on_time_percentage,
    year, month, day, hour
FROM smartroute_analytics.delay_metrics
WHERE year = YEAR(CURRENT_DATE) 
  AND month = MONTH(CURRENT_DATE)
  AND day = DAY(CURRENT_DATE)
ORDER BY on_time_pct ASC, route_id;

-- Query 2: Most crowded stations (vehicle frequency)
SELECT 
    stop_id,
    route_id,
    vehicle_frequency_per_hour,
    unique_trips,
    YEAR, month, day, hour
FROM smartroute_analytics.crowding_metrics
WHERE year = YEAR(CURRENT_DATE)
  AND month = MONTH(CURRENT_DATE)
  AND day = DAY(CURRENT_DATE)
ORDER BY vehicle_frequency_per_hour DESC
LIMIT 20;

-- Query 3: Hourly delay trend for a specific line
SELECT 
    hour,
    ROUND(avg(avg_delay_seconds), 2) as avg_delay_sec,
    ROUND(avg(on_time_pct), 2) as avg_on_time_pct,
    COUNT(*) as samples
FROM smartroute_analytics.delay_metrics
WHERE route_id = '1'
  AND year = YEAR(CURRENT_DATE)
  AND month = MONTH(CURRENT_DATE)
  AND day = DAY(CURRENT_DATE)
GROUP BY hour
ORDER BY hour;

-- Query 4: Service reliability comparison (top 5 most reliable lines)
SELECT 
    route_id,
    COUNT(*) as measurements,
    ROUND(avg(on_time_pct), 2) as avg_on_time_pct,
    ROUND(avg(avg_delay_seconds), 2) as avg_delay_sec,
    ROUND(max(max_delay_seconds), 2) as max_delay_sec
FROM smartroute_analytics.delay_metrics
WHERE year = YEAR(CURRENT_DATE)
  AND month = MONTH(CURRENT_DATE)
  AND day = DAY(CURRENT_DATE)
GROUP BY route_id
ORDER BY avg_on_time_pct DESC
LIMIT 5;

-- Query 5: Vehicle arrival distribution at top station
SELECT 
    stop_id,
    vehicle_frequency_per_hour,
    COUNT(*) as occurrence_count
FROM smartroute_analytics.crowding_metrics
WHERE year = YEAR(CURRENT_DATE)
  AND month = MONTH(CURRENT_DATE)
  AND day = DAY(CURRENT_DATE)
GROUP BY stop_id, vehicle_frequency_per_hour
ORDER BY occurrence_count DESC, vehicle_frequency_per_hour DESC
LIMIT 15;

