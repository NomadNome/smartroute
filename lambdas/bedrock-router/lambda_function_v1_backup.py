#!/usr/bin/env python3
"""
AWS Lambda: SmartRoute Route Recommendation Engine
Integrates Bedrock Claude Haiku 4.5 with Athena safety data and DynamoDB caching
"""

import json
import os
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import boto3
from bedrock_route_recommender import BedrockRouteRecommender

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
athena_client = boto3.client('athena', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
s3_client = boto3.client('s3', region_name='us-east-1')

# Environment variables
ATHENA_DATABASE = os.environ.get('ATHENA_DATABASE', 'smartroute_data')
ATHENA_OUTPUT_LOCATION = os.environ.get('ATHENA_OUTPUT_LOCATION',
                                        's3://smartroute-data-lake-069899605581/athena-results/')
CACHE_TABLE_NAME = os.environ.get('CACHE_TABLE_NAME', 'smartroute-route-cache')
CACHE_TTL_SECONDS = int(os.environ.get('CACHE_TTL_SECONDS', '300'))  # 5 minutes

# Initialize DynamoDB table
try:
    cache_table = dynamodb.Table(CACHE_TABLE_NAME)
    cache_table.load()  # Verify table exists
    logger.info(f"✅ DynamoDB cache table initialized: {CACHE_TABLE_NAME}")
except Exception as e:
    logger.warning(f"⚠️  DynamoDB cache table not available: {e}")
    cache_table = None

# Initialize Bedrock recommender
recommender = BedrockRouteRecommender()


class AthenaDataFetcher:
    """Fetch real-time safety data from Athena"""

    def __init__(self):
        self.database = ATHENA_DATABASE
        self.output_location = ATHENA_OUTPUT_LOCATION

    def get_crime_data(self, station_name: str, days: int = 7) -> Dict:
        """
        Query Athena for crime incidents near a station

        Args:
            station_name: Station name to query
            days: Number of days of historical data

        Returns:
            Dictionary with crime counts and incident types
        """
        try:
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

            logger.info(f"📍 Querying Athena for crime data: {station_name}")
            query_id = self._execute_query(query)
            result = self._get_query_results(query_id)

            if result and len(result) > 1:  # Skip header row
                row = result[1]
                return {
                    "station_name": row[0],
                    "incident_count": int(row[1]) if row[1] else 0,
                    "median_safety_score": float(row[2]) if row[2] else 5.0
                }
            else:
                # No data found, return neutral defaults
                return {
                    "station_name": station_name,
                    "incident_count": 0,
                    "median_safety_score": 5.0
                }

        except Exception as e:
            logger.error(f"❌ Failed to fetch crime data for {station_name}: {e}")
            return {
                "station_name": station_name,
                "incident_count": 0,
                "median_safety_score": 5.0
            }

    def _execute_query(self, query: str) -> str:
        """Execute Athena query and return query ID"""
        try:
            response = athena_client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': self.database},
                ResultConfiguration={'OutputLocation': self.output_location}
            )
            return response['QueryExecutionId']
        except Exception as e:
            logger.error(f"Failed to execute Athena query: {e}")
            raise

    def _get_query_results(self, query_id: str, max_retries: int = 10) -> Optional[list]:
        """Get query results with polling"""
        import time

        for attempt in range(max_retries):
            try:
                response = athena_client.get_query_execution(QueryExecutionId=query_id)
                status = response['QueryExecution']['Status']['State']

                if status == 'SUCCEEDED':
                    # Get results
                    results_response = athena_client.get_query_results(
                        QueryExecutionId=query_id,
                        MaxResults=10
                    )

                    rows = []
                    for row in results_response['ResultSet']['Rows']:
                        rows.append([field.get('VarCharValue', '') for field in row['Data']])
                    return rows

                elif status in ['FAILED', 'CANCELLED']:
                    logger.error(f"Query {query_id} {status}")
                    return None

                # Still running, wait and retry
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Error polling query results: {e}")
                return None

        logger.error(f"Query {query_id} timed out after {max_retries} attempts")
        return None


def generate_cache_key(origin: str, destination: str, criterion: str) -> str:
    """Generate cache key from route parameters"""
    key_string = f"{origin}|{destination}|{criterion}".lower()
    return hashlib.md5(key_string.encode()).hexdigest()


def get_from_cache(cache_key: str) -> Optional[Dict]:
    """Retrieve cached route recommendation"""
    if not cache_table:
        return None

    try:
        response = cache_table.get_item(Key={'cache_key': cache_key})

        if 'Item' in response:
            item = response['Item']
            # Check if cache has expired
            if 'expiry' in item:
                if datetime.fromtimestamp(float(item['expiry'])) > datetime.utcnow():
                    logger.info(f"✅ Cache hit: {cache_key[:8]}...")
                    return item['data']
                else:
                    logger.info(f"⚠️  Cache expired: {cache_key[:8]}...")
                    return None

        return None

    except Exception as e:
        logger.warning(f"Error retrieving from cache: {e}")
        return None


def put_in_cache(cache_key: str, data: Dict) -> bool:
    """Store route recommendation in cache"""
    if not cache_table:
        return False

    try:
        expiry = datetime.utcnow() + timedelta(seconds=CACHE_TTL_SECONDS)

        cache_table.put_item(
            Item={
                'cache_key': cache_key,
                'data': data,
                'expiry': int(expiry.timestamp()),
                'created_at': datetime.utcnow().isoformat()
            },
            # TTL attribute for automatic cleanup
            TimeToLiveAttributeName='expiry'
        )

        logger.info(f"✅ Cached result: {cache_key[:8]}... (TTL: {CACHE_TTL_SECONDS}s)")
        return True

    except Exception as e:
        logger.warning(f"Error storing in cache: {e}")
        return False


def validate_request(event: Dict) -> Tuple[bool, Optional[str], Dict]:
    """Validate request parameters"""
    try:
        body = event.get('body', {})
        if isinstance(body, str):
            body = json.loads(body)

        origin = body.get('origin', '').strip()
        destination = body.get('destination', '').strip()
        criterion = body.get('criterion', 'balanced').lower()

        if not origin or not destination:
            return False, "Missing origin or destination", {}

        if criterion not in ['safe', 'fast', 'balanced']:
            criterion = 'balanced'

        return True, None, {
            'origin': origin,
            'destination': destination,
            'criterion': criterion
        }

    except Exception as e:
        logger.error(f"Error validating request: {e}")
        return False, f"Invalid request: {str(e)}", {}


def error_response(status_code: int, message: str) -> Dict:
    """Format error response"""
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            'error': message,
            'timestamp': datetime.utcnow().isoformat()
        })
    }


def success_response(data: Dict) -> Dict:
    """Format success response"""
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(data)
    }


def lambda_handler(event, context):
    """
    Lambda entry point for route recommendation requests

    Expected request body:
    {
        "origin": "Times Square",
        "destination": "Brooklyn Bridge",
        "criterion": "balanced"  # safe, fast, or balanced
    }
    """
    logger.info(f"📍 Route recommendation request received")

    # Validate request
    is_valid, error, params = validate_request(event)
    if not is_valid:
        logger.error(f"❌ Validation failed: {error}")
        return error_response(400, error)

    origin = params['origin']
    destination = params['destination']
    criterion = params['criterion']

    logger.info(f"   Origin: {origin} → Destination: {destination} (Criterion: {criterion})")

    # Generate cache key
    cache_key = generate_cache_key(origin, destination, criterion)

    # Check cache
    cached_result = get_from_cache(cache_key)
    if cached_result:
        logger.info(f"✅ Returning cached recommendation")
        return success_response(cached_result)

    # Fetch real-time safety data from Athena
    logger.info(f"📊 Fetching real-time safety data from Athena...")
    fetcher = AthenaDataFetcher()

    try:
        origin_crime = fetcher.get_crime_data(origin)
        destination_crime = fetcher.get_crime_data(destination)

        logger.info(f"   {origin}: {origin_crime['incident_count']} incidents")
        logger.info(f"   {destination}: {destination_crime['incident_count']} incidents")

    except Exception as e:
        logger.warning(f"⚠️  Error fetching crime data, continuing without real-time data: {e}")
        origin_crime = {"station_name": origin, "incident_count": 0, "median_safety_score": 5.0}
        destination_crime = {"station_name": destination, "incident_count": 0, "median_safety_score": 5.0}

    # Build context for Bedrock
    context = {
        "crime_incidents": {
            origin: origin_crime['incident_count'],
            destination: destination_crime['incident_count']
        },
        "safety_scores": {
            origin: origin_crime['median_safety_score'],
            destination: destination_crime['median_safety_score']
        }
    }

    # Get route recommendations from Bedrock
    logger.info(f"🤖 Requesting route recommendations from Bedrock...")
    try:
        result = recommender.get_route_recommendations(
            origin=origin,
            destination=destination,
            context=context
        )

        logger.info(f"✅ Routes generated successfully")
        logger.info(f"   Latency: {result['latency_ms']:.0f}ms")

        # Add metadata
        response_data = {
            **result,
            "origin": origin,
            "destination": destination,
            "criterion": criterion,
            "requested_at": datetime.utcnow().isoformat(),
            "cached": False
        }

        # Cache the result
        put_in_cache(cache_key, response_data)

        return success_response(response_data)

    except Exception as e:
        logger.error(f"❌ Bedrock recommendation failed: {e}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Failed to generate routes: {str(e)}")


# Local testing
if __name__ == "__main__":
    test_event = {
        'body': json.dumps({
            'origin': 'Times Square',
            'destination': 'Brooklyn Bridge',
            'criterion': 'balanced'
        })
    }

    response = lambda_handler(test_event, None)
    print(json.dumps(response, indent=2))
