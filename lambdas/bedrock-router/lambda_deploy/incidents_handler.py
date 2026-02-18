"""
Incidents Handler - Returns latest crime/311 incidents for frontend
Fetches from DynamoDB SmartRoute_Safety_Scores and recent incident data
"""

import boto3
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
safety_table = dynamodb.Table('SmartRoute_Safety_Scores')


def convert_decimals(obj):
    """Convert Decimal objects to float for JSON serialization"""
    if isinstance(obj, list):
        return [convert_decimals(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj) if obj % 1 else int(obj)
    return obj


def lambda_handler(event, context):
    """
    Handle incidents/latest request
    Returns most recent crime and 311 incidents
    """
    try:
        logger.info("📍 Incidents request received")

        # Get query parameters
        query_params = event.get('queryStringParameters') or {}
        limit = int(query_params.get('limit', '20'))
        incident_type = query_params.get('type', 'all')  # all, crime, 311

        # Fetch incidents
        incidents = get_latest_incidents(limit, incident_type)

        logger.info(f"✅ Fetched {len(incidents)} incidents")

        # Convert Decimals and return response
        response_data = {
            'success': True,
            'incidents': convert_decimals(incidents),
            'count': len(incidents),
            'timestamp': datetime.utcnow().isoformat()
        }

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps(response_data)
        }

    except Exception as e:
        logger.error(f"❌ Error in incidents handler: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }


def get_latest_incidents(limit=20, incident_type='all'):
    """
    Fetch latest incidents from DynamoDB
    Converts safety_scores into incident feed format
    """
    try:
        logger.info(f"📊 Fetching latest incidents (limit: {limit}, type: {incident_type})")

        # Scan SmartRoute_Safety_Scores table for stations with high incident counts
        response = safety_table.scan(
            Limit=100,  # Scan more than needed to have enough data
            ProjectionExpression='station_name,incident_count,safety_score,updated_at'
        )

        items = response.get('Items', [])

        # Convert to incident format
        incidents = []
        for item in items:
            # Convert Decimal to int for incident_count
            incident_count = int(item.get('incident_count', 0))

            # Only include stations with recent incidents
            if incident_count > 0:
                # Convert safety_score safely
                safety_score = item.get('safety_score', 0)
                if isinstance(safety_score, Decimal):
                    safety_score = float(safety_score)
                else:
                    safety_score = float(safety_score)

                # Create incident entry
                incident = {
                    'type': 'crime',
                    'location': item.get('station_name', 'Unknown Station'),
                    'station': item.get('station_name'),
                    'subtype': f'{incident_count} incident{"s" if incident_count > 1 else ""} reported',
                    'timestamp': item.get('updated_at'),
                    'incident_count': incident_count,
                    'safety_score': safety_score
                }

                # Filter by type
                if incident_type == 'all' or incident_type == 'crime':
                    incidents.append(incident)

        # Sort by incident count (most serious first)
        incidents.sort(key=lambda x: x['incident_count'], reverse=True)

        # Return top N incidents
        return incidents[:limit]

    except Exception as e:
        logger.error(f"❌ Error fetching incidents: {e}")
        return []


def handle_options(event, context):
    """Handle OPTIONS preflight requests for CORS"""
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        },
        'body': ''
    }
