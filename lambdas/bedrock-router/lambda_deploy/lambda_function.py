#!/usr/bin/env python3
"""
AWS Lambda: SmartRoute Phase 5 - Graph-Based Route Recommender
Uses Dijkstra's algorithm for accurate routing, Bedrock for explanations only.

Architecture:
1. Graph-based routing engine (Dijkstra's algorithm)
   - Ensures physically valid routes
   - Optimizes for Safety, Speed, or Balanced

2. Score calculation
   - Safety: Based on crime incidents
   - Reliability: Based on line on-time performance
   - Efficiency: Based on transfers and travel time

3. Bedrock explanation layer
   - Brief, contextual explanations only
   - No route generation (prevents hallucinations)
"""

import json
import os
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, List

import boto3
from decimal import Decimal

# Import graph-based routing components (NEW)
from subway_graph import SubwayGraph, SUBWAY_LINES, TRANSFER_POINTS, LINE_PERFORMANCE
from dijkstra_router import DijkstraRouter
from route_optimizer import RouteOptimizer
from score_calculator import ScoreCalculator

# Import Bedrock (for explanations only)
from bedrock_route_recommender import BedrockRouteRecommender

# Import utilities
from nyc_stations import get_station_by_coordinates, get_station_info, NYC_STATIONS

# Import address resolution (for station suggestions)
from address_resolver import get_address_resolver

# Import incidents handler
from incidents_handler import lambda_handler as incidents_handler

# ============================================================================
# LOGGING & AWS CLIENTS
# ============================================================================

logger = logging.getLogger()
logger.setLevel(logging.INFO)

athena_client = boto3.client('athena', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
s3_client = boto3.client('s3', region_name='us-east-1')

# ============================================================================
# ENVIRONMENT VARIABLES
# ============================================================================

ATHENA_DATABASE = os.environ.get('ATHENA_DATABASE', 'smartroute_data')
ATHENA_OUTPUT_LOCATION = os.environ.get(
    'ATHENA_OUTPUT_LOCATION',
    's3://smartroute-data-lake-069899605581/athena-results/'
)
CACHE_TABLE_NAME = os.environ.get('CACHE_TABLE_NAME', 'smartroute-route-cache')
REALTIME_TABLE_NAME = os.environ.get('REALTIME_TABLE_NAME', 'smartroute_station_realtime_state')
SAFETY_SCORES_TABLE = os.environ.get('SAFETY_SCORES_TABLE', 'SmartRoute_Safety_Scores')
CACHE_TTL_SECONDS = int(os.environ.get('CACHE_TTL_SECONDS', '300'))

# ============================================================================
# DYNAMODB TABLE INITIALIZATION
# ============================================================================

# Cache table
try:
    cache_table = dynamodb.Table(CACHE_TABLE_NAME)
    cache_table.load()
    logger.info(f"✅ Cache table initialized: {CACHE_TABLE_NAME}")
except Exception as e:
    logger.warning(f"⚠️  Cache table unavailable: {e}")
    cache_table = None

# Real-time table
try:
    realtime_table = dynamodb.Table(REALTIME_TABLE_NAME)
    realtime_table.load()
    logger.info(f"✅ Real-time table initialized: {REALTIME_TABLE_NAME}")
except Exception as e:
    logger.warning(f"⚠️  Real-time table unavailable: {e}")
    realtime_table = None

# Safety scores table (populated by daily_safety_aggregator)
try:
    safety_table = dynamodb.Table(SAFETY_SCORES_TABLE)
    logger.info(f"✅ Safety scores table initialized: {SAFETY_SCORES_TABLE}")
except Exception as e:
    logger.warning(f"⚠️  Safety scores table unavailable: {e}")
    safety_table = None

# ============================================================================
# GRAPH-BASED ROUTING INITIALIZATION (NEW)
# ============================================================================

# Initialize subway graph
subway_graph = SubwayGraph()
logger.info(f"✅ Subway graph initialized with {len(subway_graph.all_stations)} stations")

# Initialize Dijkstra router
dijkstra_router = DijkstraRouter(subway_graph)
logger.info("✅ Dijkstra router initialized")

# Initialize route optimizer (will update crime data at request time)
route_optimizer = RouteOptimizer(dijkstra_router, crime_data={})
logger.info("✅ Route optimizer initialized")

# Initialize score calculator (will update data at request time)
score_calculator = ScoreCalculator(crime_data={}, line_performance=LINE_PERFORMANCE)
logger.info("✅ Score calculator initialized")

# Initialize Bedrock for explanations only
bedrock_recommender = BedrockRouteRecommender()
logger.info("✅ Bedrock recommender initialized (explanations only)")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def load_crime_data() -> Dict[str, int]:
    """
    Load crime data from DynamoDB safety scores table.

    Returns:
        Dictionary mapping station name to crime incident count
    """
    if not safety_table:
        logger.warning("⚠️  Safety table not available, using defaults")
        return {}

    try:
        response = safety_table.scan(Limit=1000)
        crime_data = {}

        for item in response.get('Items', []):
            station_name = item.get('station_name')
            incident_count = int(item.get('incident_count', 5))
            crime_data[station_name] = incident_count

        logger.info(f"✅ Loaded crime data for {len(crime_data)} stations")
        return crime_data

    except Exception as e:
        logger.warning(f"⚠️  Failed to load crime data: {e}")
        return {}


def resolve_station(address_or_station: str) -> Optional[str]:
    """
    Resolve an address or station name to a canonical station name.

    Args:
        address_or_station: User input (address or station name)

    Returns:
        Canonical station name or None
    """
    if not address_or_station:
        return None

    # Try exact match first
    if address_or_station in subway_graph.all_stations:
        return address_or_station

    # Try case-insensitive match
    normalized_input = address_or_station.lower()
    for station_name in subway_graph.all_stations:
        if normalized_input == station_name.lower():
            return station_name

    # Try partial match (e.g., "times square" matches "Times Square-42nd Street")
    for station_name in subway_graph.all_stations:
        if normalized_input in station_name.lower() or \
           station_name.lower().split('-')[0] in normalized_input:
            logger.info(f"✅ Found partial match: {station_name}")
            return station_name

    logger.error(f"❌ Station not found: {address_or_station}")
    return None


def validate_request(event: Dict) -> tuple:
    """
    Validate the API request.

    Returns:
        (is_valid, error_message, params)
    """
    try:
        body = json.loads(event.get('body', '{}'))
        origin = body.get('origin_address', '').strip()
        destination = body.get('destination_address', '').strip()
        criterion = body.get('criterion', 'balanced').lower()

        if not origin or not destination:
            return False, "Missing origin or destination address", {}

        if criterion not in ['safe', 'fast', 'balanced']:
            criterion = 'balanced'

        return True, None, {
            'origin_address': origin,
            'destination_address': destination,
            'criterion': criterion
        }

    except Exception as e:
        logger.error(f"Request validation error: {e}")
        return False, f"Invalid request: {str(e)}", {}


def error_response(status_code: int, message: str) -> Dict:
    """Format error response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, x-api-key'
        },
        'body': json.dumps({
            'error': message,
            'timestamp': datetime.utcnow().isoformat()
        })
    }


def success_response(data: Dict) -> Dict:
    """Format success response with CORS headers."""
    # Convert Decimal objects to float for JSON serialization
    def convert_decimals(obj):
        if isinstance(obj, list):
            return [convert_decimals(i) for i in obj]
        elif isinstance(obj, dict):
            return {k: convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, Decimal):
            return float(obj)
        return obj

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, x-api-key'
        },
        'body': json.dumps(convert_decimals(data), indent=2)
    }


def get_explanation(route_name: str, route_data: Dict, scores: Dict) -> str:
    """
    Get Bedrock explanation for a route with statistical context.

    Args:
        route_name: "SafeRoute", "FastRoute", or "BalancedRoute"
        route_data: Route dictionary
        scores: Dictionary with safety_score, reliability_score, efficiency_score

    Returns:
        Brief explanation string
    """
    try:
        # Get baseline context from score calculator
        crime_baseline = score_calculator.crime_baseline
        reliability_baseline = score_calculator.reliability_baseline

        # Determine score context
        safety_context = ""
        if scores['safety_score'] >= 8:
            safety_context = f"(top 25% safest - avg {crime_baseline['p25']:.0f} crimes/station)"
        elif scores['safety_score'] >= 6:
            safety_context = f"(better than city avg of {crime_baseline['mean']:.0f} crimes/station)"
        elif scores['safety_score'] >= 4:
            safety_context = f"(average - near city avg of {crime_baseline['mean']:.0f} crimes/station)"
        else:
            safety_context = f"(below average - more than city avg of {crime_baseline['mean']:.0f} crimes/station)"

        reliability_context = ""
        if scores['reliability_score'] >= 8:
            reliability_context = f"(top 25% most reliable - above {reliability_baseline['p75']:.0f}% on-time)"
        elif scores['reliability_score'] >= 6:
            reliability_context = f"(better than city avg of {reliability_baseline['mean']:.1f}% on-time)"
        elif scores['reliability_score'] >= 4:
            reliability_context = f"(near city avg of {reliability_baseline['mean']:.1f}% on-time)"
        else:
            reliability_context = f"(below city avg of {reliability_baseline['mean']:.1f}% on-time)"

        system_prompt = """You are a NYC subway route explainer with knowledge of NYC crime patterns and transit reliability.
Given a route's scores and statistical context, write ONE concise sentence explaining why this route is good for its category.

Use the provided baseline context to explain the scores meaningfully. For example, if Safety is 8 and it says "top 25% safest",
explain that the route avoids high-crime areas. If Reliability is 6 and it says "better than city average", note it uses
reliable lines compared to the city average.

Keep it factual, helpful, and under 160 characters.
Example: "This route is in the top 25% safest with excellent reliability, using the E line which performs above city average."
"""

        user_message = f"""Route: {route_name}
Origin→Destination: {route_data['stations'][0]} → {route_data['stations'][-1]}
Stations: {len(route_data['stations'])}
Transfers: {route_data['total_transfers']}
Travel Time: {route_data['total_time_minutes']} minutes

SCORES WITH CONTEXT:
- Safety Score: {scores['safety_score']}/10 {safety_context}
- Reliability Score: {scores['reliability_score']}/10 {reliability_context}
- Efficiency Score: {scores['efficiency_score']}/10 ({'direct' if route_data['total_transfers'] == 0 else f'{route_data["total_transfers"]} transfer(s)'})

Lines Used: {', '.join(route_data['lines'])}

Write ONE sentence explaining why this is a good {route_name.lower().replace('route', '')} route. Use the baseline context."""

        response = bedrock_recommender.invoke_bedrock(system_prompt, user_message, max_tokens=200)
        return response.strip()

    except Exception as e:
        logger.warning(f"Failed to get explanation from Bedrock: {e}")
        # Fallback explanation
        if "Safe" in route_name:
            return "This route prioritizes safety by avoiding high-crime stations and using reliable lines."
        elif "Fast" in route_name:
            return "This route minimizes travel time with direct paths and minimal transfers."
        else:
            return "This route balances safety, reliability, and travel time for an optimal NYC subway experience."


# ============================================================================
# STATION SUGGESTIONS HANDLER
# ============================================================================


def suggest_stations_handler(event, context) -> Dict:
    """
    Handle station suggestion requests.

    Accepts query parameter: ?address=<user_address>
    Returns: List of nearby stations sorted by distance
    """
    logger.info("🏙️  Station suggestion request received")

    try:
        # Extract address from query parameters
        query_params = event.get('queryStringParameters') or {}
        address = query_params.get('address', '').strip()

        if not address:
            return error_response(400, "Missing 'address' query parameter")

        # Get address resolver (uses Google Maps if configured, otherwise Nominatim free API)
        resolver = get_address_resolver()
        if not resolver:
            logger.error("❌ Address resolver initialization failed")
            return error_response(500, "Address resolution service unavailable")

        # Resolve address to station suggestions
        result = resolver.resolve_address_to_suggestions(
            address=address,
            max_results=3,  # Return top 3 suggestions
            max_distance_km=1.0
        )

        return success_response(result)

    except Exception as e:
        logger.error(f"❌ Error in suggest_stations: {e}")
        return error_response(500, f"Error processing address: {str(e)}")


# ============================================================================
# MAIN LAMBDA HANDLER
# ============================================================================


def lambda_handler(event, context):
    """
    Main Lambda entry point.
    Routes requests to appropriate handlers based on path.
    """
    # Determine which handler to use based on path
    path = event.get('path', '')
    http_method = event.get('httpMethod', 'OPTIONS')

    logger.info(f"📍 Request: {http_method} {path}")

    # Handle CORS preflight requests
    if http_method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, x-api-key'
            },
            'body': ''
        }

    # Route to appropriate handler
    if path.endswith('/stations/suggest') or 'suggest' in path:
        return suggest_stations_handler(event, context)
    elif path.endswith('/incidents') or 'incidents' in path:
        return incidents_handler(event, context)
    elif path.endswith('/recommend') or 'recommend' in path:
        return recommend_handler(event, context)
    else:
        logger.error(f"❌ Unknown path: {path}")
        return error_response(404, f"Path not found: {path}")


def recommend_handler(event, context):
    """
    Handle route recommendation requests.
    Generates 3 optimal routes using graph-based Dijkstra's algorithm,
    calculates scores, and provides Bedrock explanations.
    """
    logger.info("📍 Route recommendation request received")

    # Step 1: Validate request
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

    # Step 2: Resolve stations
    logger.info(f"📍 Resolving stations...")
    origin_station = resolve_station(origin_address)
    dest_station = resolve_station(destination_address)

    if not origin_station or not dest_station:
        return error_response(400, "Could not resolve origin or destination station")

    logger.info(f"   Origin station: {origin_station}")
    logger.info(f"   Destination station: {dest_station}")

    # Step 3: Load crime and performance data
    logger.info(f"📊 Loading data...")
    crime_data = load_crime_data()

    # Update optimizer and calculator with fresh data
    route_optimizer.update_crime_data(crime_data)
    score_calculator.update_crime_data(crime_data)
    score_calculator.update_line_performance(LINE_PERFORMANCE)

    # Step 4: Generate 3 routes using graph-based algorithm (CORE CHANGE)
    logger.info(f"🚀 Generating routes using Dijkstra's algorithm...")
    routes = route_optimizer.generate_routes(origin_station, dest_station, LINE_PERFORMANCE)

    if not routes or len(routes) == 0:
        logger.error(f"❌ Could not generate any valid routes")
        return error_response(500, "Could not find valid routes between stations")

    # Step 5: Calculate scores for each route
    logger.info(f"📈 Calculating scores...")
    for route in routes:
        scores = score_calculator.calculate_route_scores(route)
        route.update(scores)
        logger.info(f"   {route['name']}: Safety={route['safety_score']}, "
                   f"Reliability={route['reliability_score']}, "
                   f"Efficiency={route['efficiency_score']}")

    # Step 6: Get Bedrock explanations for each route
    logger.info(f"🤖 Generating explanations...")
    for route in routes:
        explanation = get_explanation(
            route['name'],
            route,
            {
                'safety_score': route['safety_score'],
                'reliability_score': route['reliability_score'],
                'efficiency_score': route['efficiency_score']
            }
        )
        route['explanation'] = explanation
        logger.info(f"   {route['name']}: {explanation[:60]}...")

    # Step 7: Build response
    logger.info(f"✅ Routes generated successfully")
    response_data = {
        'origin': origin_station,
        'destination': dest_station,
        'origin_address': origin_address,
        'destination_address': destination_address,
        'criterion': criterion,
        'routes': routes,
        'walking_distances': {
            'origin_km': 0.0,
            'destination_km': 0.0
        },
        'requested_at': datetime.utcnow().isoformat(),
        'cached': False
    }

    return success_response(response_data)


# ============================================================================
# LOCAL TESTING
# ============================================================================

if __name__ == "__main__":
    test_event = {
        'body': json.dumps({
            'origin_address': 'Jay Street',
            'destination_address': 'Grand Central',
            'criterion': 'balanced'
        })
    }

    response = lambda_handler(test_event, None)
    print(json.dumps(response, indent=2))
