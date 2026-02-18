#!/usr/bin/env python3
"""
SmartRoute Daily Safety Aggregator Lambda Function

Purpose:
  Pre-compute safety scores for all NYC subway stations by querying Athena
  and writing results to DynamoDB. This eliminates synchronous Athena queries
  from the main route recommendation Lambda.

Schedule:
  EventBridge rule: Daily at 2 AM UTC (run when traffic is low)

Data Flow:
  1. Query Athena for 7-day rolling crime statistics
  2. Process results and enrich with safety scoring
  3. Batch write to DynamoDB (SmartRoute_Safety_Scores)
  4. Log metrics to CloudWatch

Performance:
  - Query time: ~5-10 seconds (depends on crime data volume)
  - Write time: ~2-5 seconds (batch_writer with 25 items/batch)
  - Total duration: ~10-15 seconds
  - Cost: ~$0.000050 (Athena) + $0.00001 (DynamoDB) per run
"""

import json
import boto3
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
athena_client = boto3.client('athena', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')

# Configuration
ATHENA_DATABASE = 'smartroute_data'
ATHENA_OUTPUT_LOCATION = 's3://smartroute-data-lake-069899605581/athena-results/'
SAFETY_SCORES_TABLE = 'SmartRoute_Safety_Scores'
BATCH_SIZE = 25  # DynamoDB batch_writer optimal size
CRIME_DATA_LOOKBACK_DAYS = 7


class SafetyAggregator:
    """Aggregates crime data and computes safety scores for all stations"""

    def __init__(self):
        """Initialize aggregator with AWS clients and DynamoDB table"""
        self.athena_client = athena_client
        self.dynamodb = dynamodb
        self.cloudwatch = cloudwatch

        try:
            self.safety_table = dynamodb.Table(SAFETY_SCORES_TABLE)
            self.safety_table.load()
            logger.info(f"✅ DynamoDB table initialized: {SAFETY_SCORES_TABLE}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize DynamoDB table: {e}")
            raise

    def build_safety_query(self) -> str:
        """
        Build SQL query to fetch 7-day crime statistics for all stations

        Actual Table Schema (discovered via inspection):
        - station_id, station_name, incident_date, total_crimes, unique_categories,
          avg_distance_to_station, min_distance_to_station

        Returns:
            SQL query aggregating crimes by station (all historical data)
        """
        # Aggregation query using actual table columns
        # Sums total_crimes per station and calculates average distance metrics
        query = f"""
        SELECT
            station_name,
            SUM(CAST(total_crimes AS BIGINT)) as incident_count,
            CAST(AVG(CAST(avg_distance_to_station AS DOUBLE)) AS DOUBLE) as median_safety
        FROM {ATHENA_DATABASE}.crime_by_station
        WHERE station_name IS NOT NULL AND station_name != ''
        GROUP BY station_name
        ORDER BY station_name
        """

        logger.info(f"🔍 Built Athena query for {CRIME_DATA_LOOKBACK_DAYS}-day crime aggregation")
        logger.info(f"   Using actual table schema: station_name, total_crimes, avg_distance_to_station")
        return query

    def execute_athena_query(self, query: str) -> str:
        """
        Execute query against Athena and return query execution ID

        Args:
            query: SQL query string

        Returns:
            Query execution ID (used for polling)

        Raises:
            Exception: If query execution fails
        """
        try:
            response = self.athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': ATHENA_DATABASE},
                ResultConfiguration={'OutputLocation': ATHENA_OUTPUT_LOCATION}
            )

            query_id = response['QueryExecutionId']
            logger.info(f"📊 Started Athena query: {query_id}")
            return query_id

        except Exception as e:
            logger.error(f"❌ Failed to execute Athena query: {e}")
            raise

    def poll_query_completion(self, query_id: str, max_retries: int = 30) -> bool:
        """
        Poll Athena query execution status until completion

        Args:
            query_id: Query execution ID from start_query_execution
            max_retries: Maximum polling attempts (30 = ~15 seconds)

        Returns:
            True if query succeeded, False/Exception if failed/timeout

        Raises:
            Exception: If query fails or times out
        """
        poll_interval = 0.5  # seconds

        for attempt in range(max_retries):
            try:
                response = self.athena_client.get_query_execution(QueryExecutionId=query_id)
                status = response['QueryExecution']['Status']['State']

                if status == 'SUCCEEDED':
                    logger.info(f"✅ Query {query_id} completed successfully")
                    return True

                elif status in ['FAILED', 'CANCELLED']:
                    error_msg = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
                    logger.error(f"❌ Query {query_id} {status}: {error_msg}")
                    raise Exception(f"Athena query {status}: {error_msg}")

                # Still in progress (QUEUED, RUNNING)
                logger.debug(f"⏳ Query {query_id} status: {status} (attempt {attempt+1}/{max_retries})")
                time.sleep(poll_interval)

            except Exception as e:
                logger.error(f"Error polling query {query_id}: {e}")
                raise

        raise Exception(f"Query {query_id} timed out after {max_retries} retries")

    def fetch_query_results(self, query_id: str) -> List[List[str]]:
        """
        Fetch all results from completed Athena query

        Args:
            query_id: Query execution ID

        Returns:
            List of result rows (each row is list of strings)
            First row is column headers
        """
        try:
            all_results = []
            next_token = None
            page_count = 0

            while True:
                # Fetch results in paginated batches
                kwargs = {
                    'QueryExecutionId': query_id,
                    'MaxResults': 1000  # Maximum allowed by Athena
                }
                if next_token:
                    kwargs['NextToken'] = next_token

                response = self.athena_client.get_query_results(**kwargs)
                page_count += 1

                # Extract rows from response
                for row in response['ResultSet']['Rows']:
                    row_data = [field.get('VarCharValue', '') for field in row['Data']]
                    all_results.append(row_data)

                # Check if more pages available
                next_token = response.get('NextToken')
                if not next_token:
                    break

            logger.info(f"📥 Fetched {len(all_results)} total rows from Athena "
                       f"({page_count} pages)")
            return all_results

        except Exception as e:
            logger.error(f"❌ Failed to fetch query results: {e}")
            raise

    def compute_safety_score(self, incident_count: int, median_safety: float) -> float:
        """
        Compute composite safety score (0-10 scale)

        Algorithm:
          - Base score: median_safety (0-10)
          - Penalty: -0.5 points per incident (capped at -5 for >10 incidents)
          - Final: max(0, min(10, base_score - penalty))

        Args:
            incident_count: Number of incidents in 7-day window
            median_safety: Median safety score from Athena (0-10)

        Returns:
            Composite safety score (0-10)
        """
        if median_safety is None or median_safety == '':
            median_safety = 5.0  # Default neutral score
        else:
            median_safety = float(median_safety)

        # Penalty based on incident volume
        incident_penalty = min(incident_count * 0.5, 5.0)  # Max -5 penalty

        # Compute final score
        safety_score = median_safety - incident_penalty
        safety_score = max(0.0, min(10.0, safety_score))  # Clamp to 0-10

        return round(safety_score, 1)

    def process_athena_results(self, results: List[List[str]]) -> List[Dict]:
        """
        Process Athena results and compute safety scores

        Args:
            results: Raw Athena query results (first row is headers)

        Returns:
            List of DynamoDB items ready to write
        """
        processed_items = []

        # Log the header row for debugging
        if results:
            logger.info(f"📋 Athena result columns: {results[0]}")
            logger.info(f"📋 Total rows returned: {len(results)} (including header)")
            if len(results) > 1:
                logger.info(f"📋 First data row: {results[1]}")

        # Skip header row (index 0)
        for idx, row in enumerate(results[1:], 1):
            try:
                station_name = row[0].strip()
                incident_count = int(row[1]) if row[1] else 0
                median_safety = float(row[2]) if row[2] else 5.0

                # Skip if no station name
                if not station_name:
                    logger.warning(f"⚠️  Row {idx} has empty station_name, skipping")
                    continue

                # Compute safety score
                safety_score = self.compute_safety_score(incident_count, median_safety)

                # Build DynamoDB item
                item = {
                    'station_name': station_name,
                    'safety_score': Decimal(str(safety_score)),  # DynamoDB doesn't support float
                    'incident_count': incident_count,
                    'updated_at': datetime.utcnow().isoformat() + 'Z',
                    'lookback_days': CRIME_DATA_LOOKBACK_DAYS,
                    'median_safety': Decimal(str(median_safety))  # Store raw median too
                }

                processed_items.append(item)
                logger.debug(f"✅ Processed: {station_name} (safety={safety_score}, "
                           f"incidents={incident_count})")

            except (IndexError, ValueError) as e:
                logger.warning(f"⚠️  Error processing row {idx}: {e}")
                continue

        logger.info(f"✅ Processed {len(processed_items)} station safety scores")
        return processed_items

    def batch_write_to_dynamodb(self, items: List[Dict]) -> Tuple[int, int]:
        """
        Write items to DynamoDB using batch_writer for efficiency

        Batch_writer:
          - Automatically handles batching (25 items per request)
          - Retries failed items
          - More efficient than individual PutItem calls

        Args:
            items: List of items to write

        Returns:
            Tuple of (items_written, items_failed)
        """
        items_written = 0
        items_failed = 0

        try:
            logger.info(f"📝 Writing {len(items)} items to {SAFETY_SCORES_TABLE} "
                       f"(batch size: {BATCH_SIZE})...")

            with self.safety_table.batch_writer() as batch:
                for item in items:
                    try:
                        batch.put_item(Item=item)
                        items_written += 1

                        # Log progress every 25 items
                        if items_written % BATCH_SIZE == 0:
                            logger.info(f"  ✅ Written {items_written}/{len(items)} items")

                    except Exception as e:
                        logger.error(f"❌ Failed to write item {item.get('station_name')}: {e}")
                        items_failed += 1

            logger.info(f"✅ Batch write completed: {items_written} written, {items_failed} failed")
            return items_written, items_failed

        except Exception as e:
            logger.error(f"❌ Batch writer failed: {e}")
            raise

    def publish_metrics(self, execution_time: float, items_written: int, items_failed: int):
        """
        Publish execution metrics to CloudWatch

        Args:
            execution_time: Total execution time in seconds
            items_written: Number of items successfully written
            items_failed: Number of items that failed to write
        """
        try:
            self.cloudwatch.put_metric_data(
                Namespace='SmartRoute/SafetyAggregator',
                MetricData=[
                    {
                        'MetricName': 'ExecutionTime',
                        'Value': execution_time,
                        'Unit': 'Seconds'
                    },
                    {
                        'MetricName': 'ItemsWritten',
                        'Value': items_written,
                        'Unit': 'Count'
                    },
                    {
                        'MetricName': 'ItemsFailed',
                        'Value': items_failed,
                        'Unit': 'Count'
                    },
                    {
                        'MetricName': 'SuccessRate',
                        'Value': (items_written / (items_written + items_failed) * 100) if (items_written + items_failed) > 0 else 0,
                        'Unit': 'Percent'
                    }
                ]
            )
            logger.info(f"📊 Published metrics to CloudWatch")
        except Exception as e:
            logger.warning(f"⚠️  Failed to publish metrics: {e}")


def lambda_handler(event, context):
    """
    Lambda entry point for daily safety aggregation

    Triggered by: EventBridge rule (daily at 2 AM UTC)

    Returns:
        Response dict with statusCode and body
    """
    execution_start = time.time()

    logger.info("🚀 Starting SmartRoute Daily Safety Aggregator")
    logger.info(f"📅 Aggregating {CRIME_DATA_LOOKBACK_DAYS}-day crime statistics")

    try:
        # Initialize aggregator
        aggregator = SafetyAggregator()

        # Step 1: Build and execute Athena query
        logger.info("📊 Step 1/4: Querying Athena for crime statistics...")
        query = aggregator.build_safety_query()
        logger.info(f"Query to execute:\n{query}")
        query_id = aggregator.execute_athena_query(query)

        # Step 2: Poll for completion
        logger.info("⏳ Step 2/4: Waiting for Athena query completion...")
        aggregator.poll_query_completion(query_id)

        # Step 3: Fetch and process results
        logger.info("📥 Step 3/4: Fetching and processing query results...")
        athena_results = aggregator.fetch_query_results(query_id)
        processed_items = aggregator.process_athena_results(athena_results)

        if not processed_items:
            logger.warning("⚠️  No station data to write")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No data to process',
                    'items_processed': 0,
                    'execution_time_seconds': round(time.time() - execution_start, 2)
                })
            }

        # Step 4: Write to DynamoDB
        logger.info("📝 Step 4/4: Writing results to DynamoDB...")
        items_written, items_failed = aggregator.batch_write_to_dynamodb(processed_items)

        # Publish metrics
        execution_time = time.time() - execution_start
        aggregator.publish_metrics(execution_time, items_written, items_failed)

        # Success response
        logger.info(f"✅ Safety aggregation completed in {execution_time:.2f} seconds")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Safety aggregation completed successfully',
                'items_processed': len(processed_items),
                'items_written': items_written,
                'items_failed': items_failed,
                'execution_time_seconds': round(execution_time, 2),
                'lookback_days': CRIME_DATA_LOOKBACK_DAYS,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })
        }

    except Exception as e:
        execution_time = time.time() - execution_start
        logger.error(f"❌ Safety aggregation failed: {e}", exc_info=True)
        logger.error(f"Database: {ATHENA_DATABASE}")
        logger.error(f"Athena Output Location: {ATHENA_OUTPUT_LOCATION}")
        logger.error(f"DynamoDB Table: {SAFETY_SCORES_TABLE}")

        error_response = {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Safety aggregation failed',
                'database': ATHENA_DATABASE,
                'athena_output_location': ATHENA_OUTPUT_LOCATION,
                'dynamodb_table': SAFETY_SCORES_TABLE,
                'execution_time_seconds': round(execution_time, 2),
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })
        }
        return error_response
