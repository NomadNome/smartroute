#!/usr/bin/env python3
"""
AWS Lambda: SmartRoute Enhanced Route Recommendation Engine
Accepts user addresses, converts to stations, fetches real-time train data, and generates AI recommendations
"""

import json
import os
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import boto3
from bedrock_route_recommender import BedrockRouteRecommender
from nyc_stations import get_station_by_coordinates, get_station_info, NYC_STATIONS
from realtime_travel_calculator import calculate_route_travel_time

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
REALTIME_TABLE_NAME = os.environ.get('REALTIME_TABLE_NAME', 'smartroute_station_realtime_state')
CACHE_TTL_SECONDS = int(os.environ.get('CACHE_TTL_SECONDS', '300'))  # 5 minutes

# Initialize DynamoDB tables
try:
    cache_table = dynamodb.Table(CACHE_TABLE_NAME)
    cache_table.load()
    logger.info(f"✅ DynamoDB cache table initialized: {CACHE_TABLE_NAME}")
except Exception as e:
    logger.warning(f"⚠️  DynamoDB cache table not available: {e}")
    cache_table = None

try:
    realtime_table = dynamodb.Table(REALTIME_TABLE_NAME)
    realtime_table.load()
    logger.info(f"✅ DynamoDB realtime table initialized: {REALTIME_TABLE_NAME}")
except Exception as e:
    logger.warning(f"⚠️  DynamoDB realtime table not available: {e}")
    realtime_table = None

# Initialize Bedrock recommender
recommender = BedrockRouteRecommender()


class AddressToStationMapper:
    """Map NYC addresses directly to subway stations without external APIs"""

    @staticmethod
    def find_nearest_station(address: str) -> Optional[Tuple[str, float]]:
        """
        Map address to nearest subway station using fuzzy matching and station database
        Returns (station_name, distance_km) tuple
        """
        try:
            logger.info(f"🔍 Mapping address to station: {address}")

            # Try exact substring matching first
            address_lower = address.lower()
            for station_name in NYC_STATIONS.keys():
                if station_name.lower() in address_lower or address_lower in station_name.lower():
                    logger.info(f"✅ Found exact match: {station_name}")
                    return (station_name, 0.0)

            # If no exact match, find nearby station using Haversine
            # Extract neighborhood/area keywords from address
            words = address.split()

            # Try matching common station keywords
            best_match = None
            best_score = 0

            for station_name in NYC_STATIONS.keys():
                station_words = station_name.lower().split()
                match_score = sum(1 for word in words if word.lower() in station_words)
                if match_score > best_score:
                    best_score = match_score
                    best_match = station_name

            if best_match and best_score > 0:
                logger.info(f"✅ Found fuzzy match: {best_match} (score: {best_score})")
                return (best_match, 0.05)  # Small walking distance for matched station

            # Fallback: return Times Square as default central location
            logger.warning(f"⚠️  No match found for {address}, using Times Square as default")
            return ("Times Square-42nd Street", 0.3)

        except Exception as e:
            logger.error(f"❌ Address mapping failed for {address}: {e}")
            return None


class RealtimeDataFetcher:
    """Fetch real-time train data from DynamoDB"""

    @staticmethod
    def get_next_arrivals(station_name: str, limit: int = 5) -> Dict:
        """
        Get next train arrivals for a station from real-time DynamoDB table
        Queries smartroute_station_realtime_state for current vehicle positions
        """
        if not realtime_table:
            logger.warning(f"❌ Realtime table not available")
            return {"status": "unavailable", "arrivals": []}

        try:
            # Query for station state - Phase 1 populates this every minute
            response = realtime_table.query(
                KeyConditionExpression='station_id = :sid',
                ExpressionAttributeValues={':sid': station_name},
                ScanIndexForward=False,  # Most recent first
                Limit=limit
            )

            items = response.get('Items', [])

            if items:
                logger.info(f"✅ Found {len(items)} real-time entries for {station_name}")
                arrivals = []

                for item in items:
                    arrivals.append({
                        "line": item.get('line', 'Unknown'),
                        "destination": item.get('destination', 'Unknown'),
                        "eta_seconds": item.get('eta_seconds', 0),
                        "eta_minutes": int(item.get('eta_seconds', 0) / 60),
                        "delay_seconds": item.get('delay_seconds', 0),
                        "timestamp": item.get('timestamp', '')
                    })

                return {
                    "status": "live",
                    "station": station_name,
                    "arrivals": arrivals
                }
            else:
                logger.info(f"⚠️  No real-time data for {station_name} - using static schedules")
                return {"status": "no_data", "arrivals": []}

        except Exception as e:
            logger.error(f"❌ Error fetching real-time data: {e}")
            return {"status": "error", "arrivals": []}


class AthenaDataFetcher:
    """Fetch crime/safety data from Athena"""

    def __init__(self):
        self.database = ATHENA_DATABASE
        self.output_location = ATHENA_OUTPUT_LOCATION

    def get_crime_data(self, station_name: str, days: int = 7) -> Dict:
        """Query Athena for crime incidents near a station"""
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

            if result and len(result) > 1:
                row = result[1]
                return {
                    "station_name": row[0],
                    "incident_count": int(row[1]) if row[1] else 0,
                    "median_safety_score": float(row[2]) if row[2] else 5.0
                }
            else:
                return {
                    "station_name": station_name,
                    "incident_count": 0,
                    "median_safety_score": 5.0
                }

        except Exception as e:
            logger.error(f"❌ Failed to fetch crime data: {e}")
            return {
                "station_name": station_name,
                "incident_count": 0,
                "median_safety_score": 5.0
            }

    def _execute_query(self, query: str) -> str:
        """Execute Athena query"""
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

                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Error polling query: {e}")
                return None

        logger.error(f"Query timeout after {max_retries} attempts")
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
            if 'expiry' in item:
                if datetime.fromtimestamp(float(item['expiry'])) > datetime.utcnow():
                    logger.info(f"✅ Cache hit: {cache_key[:8]}...")
                    return item['data']

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
            }
        )
        logger.info(f"✅ Cached result: {cache_key[:8]}...")
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

        origin_address = body.get('origin_address', '').strip()
        destination_address = body.get('destination_address', '').strip()
        criterion = body.get('criterion', 'balanced').lower()

        if not origin_address or not destination_address:
            return False, "Missing origin or destination address", {}

        if criterion not in ['safe', 'fast', 'balanced']:
            criterion = 'balanced'

        return True, None, {
            'origin_address': origin_address,
            'destination_address': destination_address,
            'criterion': criterion
        }

    except Exception as e:
        logger.error(f"Error validating request: {e}")
        return False, f"Invalid request: {str(e)}", {}


def error_response(status_code: int, message: str) -> Dict:
    """Format error response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'POST,OPTIONS'
        },
        'body': json.dumps({
            'error': message,
            'timestamp': datetime.utcnow().isoformat()
        })
    }


def success_response(data: Dict) -> Dict:
    """Format success response"""
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'POST,OPTIONS'
        },
        'body': json.dumps(data)
    }


def lambda_handler(event, context):
    """
    Lambda entry point for address-based route recommendation

    Expected request body:
    {
        "origin_address": "123 Main St, NYC",
        "destination_address": "456 Park Ave, NYC",
        "criterion": "balanced"  # safe, fast, or balanced
    }
    """
    logger.info(f"📍 Address-based route request received")

    # Validate request
    is_valid, error, params = validate_request(event)
    if not is_valid:
        logger.error(f"❌ Validation failed: {error}")
        return error_response(400, error)

    origin_address = params['origin_address']
    destination_address = params['destination_address']
    criterion = params['criterion']

    logger.info(f"   Origin: {origin_address}")
    logger.info(f"   Destination: {destination_address}")
    logger.info(f"   Criterion: {criterion}")

    # Step 1: Map addresses to stations
    logger.info(f"📍 Mapping addresses to stations...")
    mapper = AddressToStationMapper()
    origin_result = mapper.find_nearest_station(origin_address)
    dest_result = mapper.find_nearest_station(destination_address)

    if not origin_result or not dest_result:
        return error_response(400, "Could not map addresses to stations")

    origin_station = origin_result[0]
    dest_station = dest_result[0]
    origin_distance = origin_result[1]
    dest_distance = dest_result[1]

    logger.info(f"   Origin: {origin_station} ({origin_distance:.2f} km away)")
    logger.info(f"   Destination: {dest_station} ({dest_distance:.2f} km away)")

    # Step 3: Generate cache key
    cache_key = generate_cache_key(origin_station, dest_station, criterion)

    # Step 4: Check cache
    cached_result = get_from_cache(cache_key)
    if cached_result:
        logger.info(f"✅ Returning cached recommendation")
        return success_response(cached_result)

    # Step 5: Fetch real-time train data
    logger.info(f"⏱️  Fetching real-time train data...")
    realtime_fetcher = RealtimeDataFetcher()
    origin_trains = realtime_fetcher.get_next_arrivals(origin_station, limit=3)
    dest_trains = realtime_fetcher.get_next_arrivals(dest_station, limit=3)

    logger.info(f"   Origin trains: {len(origin_trains.get('arrivals', []))} upcoming")
    logger.info(f"   Destination trains: {len(dest_trains.get('arrivals', []))} upcoming")

    # Step 6: Fetch crime/safety data
    logger.info(f"📊 Fetching safety data from Athena...")
    athena_fetcher = AthenaDataFetcher()

    try:
        origin_crime = athena_fetcher.get_crime_data(origin_station)
        dest_crime = athena_fetcher.get_crime_data(dest_station)
        logger.info(f"   {origin_station}: {origin_crime['incident_count']} incidents")
        logger.info(f"   {dest_station}: {dest_crime['incident_count']} incidents")
    except Exception as e:
        logger.warning(f"⚠️  Error fetching crime data: {e}")
        origin_crime = {"station_name": origin_station, "incident_count": 0, "median_safety_score": 5.0}
        dest_crime = {"station_name": dest_station, "incident_count": 0, "median_safety_score": 5.0}

    # Step 7: Build context for Bedrock
    context = {
        "crime_incidents": {
            origin_station: origin_crime['incident_count'],
            dest_station: dest_crime['incident_count']
        },
        "safety_scores": {
            origin_station: origin_crime['median_safety_score'],
            dest_station: dest_crime['median_safety_score']
        },
        "real_time_data": {
            origin_station: origin_trains,
            dest_station: dest_trains
        },
        "walking_distances": {
            "origin_km": origin_distance,
            "destination_km": dest_distance
        }
    }

    # Step 8: Get route recommendations from Bedrock
    logger.info(f"🤖 Requesting route recommendations from Bedrock...")
    try:
        result = recommender.get_route_recommendations(
            origin=origin_station,
            destination=dest_station,
            context=context
        )

        logger.info(f"✅ Routes generated successfully")

        # Enhance routes with real-time travel time estimates
        logger.info(f"⏱️  Calculating real-time travel times...")
        try:
            for route in result.get('routes', []):
                stations = route.get('stations', [])
                lines = route.get('lines', [])

                if stations and len(stations) >= 2:
                    # Calculate actual travel time from real-time data
                    travel_time_seconds, explanation = calculate_route_travel_time(stations, lines)
                    travel_time_minutes = round(travel_time_seconds / 60, 1) if travel_time_seconds else 0

                    # Update route with real travel times
                    route['estimated_time_minutes'] = travel_time_minutes
                    route['travel_time_explanation'] = explanation
                    logger.info(f"   {route.get('name', 'Route')}: {travel_time_minutes} minutes (from real-time data)")
        except Exception as e:
            logger.warning(f"⚠️  Error calculating real-time travel times: {e}. Using Claude estimates.")

        # Add metadata
        response_data = {
            **result,
            "origin_address": origin_address,
            "destination_address": destination_address,
            "origin_station": origin_station,
            "destination_station": dest_station,
            "criterion": criterion,
            "walking_distances": context["walking_distances"],
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
            'origin_address': '123 Main St, Times Square, NYC',
            'destination_address': '456 Park Ave, Brooklyn Bridge, NYC',
            'criterion': 'balanced'
        })
    }

    response = lambda_handler(test_event, None)
    print(json.dumps(response, indent=2))
