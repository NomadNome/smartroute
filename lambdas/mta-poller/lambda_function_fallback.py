"""
SmartRoute MTA GTFS-RT Data Poller (Simplified)

Polls the MTA real-time transit API and streams data to:
- S3 (for archival)
- Kinesis (for real-time processing)
- DynamoDB (for current state)
"""

import json
import boto3
import os
import logging
from datetime import datetime, timezone
from typing import Dict, List, Tuple

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS SDK clients
s3_client = boto3.client('s3')
kinesis_client = boto3.client('kinesis')
dynamodb_resource = boto3.resource('dynamodb')
secretsmanager_client = boto3.client('secretsmanager')

# Environment variables
S3_BUCKET = os.environ.get('S3_BUCKET', 'smartroute-data-lake-069899605581')
KINESIS_STREAM_ARN = os.environ.get('KINESIS_STREAM_NAME', '')
KINESIS_STREAM_NAME = 'smartroute_transit_data_stream'  # Fallback name
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'smartroute_station_realtime_state')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
MTA_API_BASE = 'http://datamine.mta.info/mta_esi.php'

logger.setLevel(LOG_LEVEL)


def lambda_handler(event: Dict, context) -> Dict:
    """
    Main Lambda handler - triggered by EventBridge every minute

    Args:
        event: EventBridge event
        context: Lambda context

    Returns:
        Summary of processing results
    """

    try:
        logger.info(f"Starting MTA data poll at {datetime.now(timezone.utc).isoformat()}")

        # For testing, return sample data without API call
        vehicle_records = generate_sample_vehicle_data()
        alerts = []

        logger.info(f"Generated {len(vehicle_records)} sample vehicle records")

        # Write to all three destinations
        s3_result = write_to_s3(vehicle_records, alerts)
        kinesis_result = write_to_kinesis(vehicle_records, alerts)
        dynamodb_result = update_dynamodb(vehicle_records)

        result = {
            'statusCode': 200,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'records_processed': len(vehicle_records),
            'alerts_processed': len(alerts),
            's3_writes': s3_result.get('count', 0),
            'kinesis_records': kinesis_result.get('count', 0),
            'dynamodb_updates': dynamodb_result.get('count', 0)
        }

        logger.info(f"Processing complete: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in lambda handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


def generate_sample_vehicle_data() -> List[Dict]:
    """Generate sample vehicle data for testing"""

    lines = ['1', '2', '3', 'A', 'C', 'E', 'N', 'Q', 'R', 'W']
    stations = ['Times Square', 'Grand Central', '42 St-Herald Sq', '59 St-Columbus Circle', '125 St']

    records = []
    for i in range(5):
        records.append({
            'trip_id': f'trip_{i}_{datetime.now(timezone.utc).timestamp()}',
            'route_id': lines[i % len(lines)],
            'vehicle_id': f'vehicle_{i}',
            'current_stop': f'stop_{i % len(stations)}',
            'next_arrival_seconds': 60 + (i * 30),
            'headsign': stations[i % len(stations)],
            'timestamp': int(datetime.now(timezone.utc).timestamp())
        })

    return records


def write_to_s3(vehicle_records: List[Dict], alerts: List[Dict]) -> Dict:
    """Write raw data to S3 with date/hour partitioning"""

    try:
        now = datetime.now(timezone.utc)
        partition = f"raw/mta/realtime/year={now.year}/month={now.month:02d}/day={now.day:02d}/hour={now.hour:02d}"
        key = f"{partition}/data-{now.isoformat()}.json"

        data = {
            'timestamp': now.isoformat(),
            'vehicle_records': vehicle_records,
            'alerts': alerts
        }

        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(data),
            ContentType='application/json'
        )

        logger.info(f"✓ Wrote to S3: {key}")
        return {'count': 1, 'key': key}

    except Exception as e:
        logger.error(f"Error writing to S3: {str(e)}", exc_info=True)
        return {'count': 0, 'error': str(e)}


def write_to_kinesis(vehicle_records: List[Dict], alerts: List[Dict]) -> Dict:
    """Stream data to Kinesis for real-time processing"""

    try:
        count = 0

        # Put each vehicle record
        for record in vehicle_records:
            kinesis_client.put_record(
                StreamName=KINESIS_STREAM_NAME,
                Data=json.dumps(record),
                PartitionKey=record.get('route_id', 'default')
            )
            count += 1

        logger.info(f"✓ Wrote {count} records to Kinesis")
        return {'count': count}

    except Exception as e:
        logger.error(f"Error writing to Kinesis: {str(e)}", exc_info=True)
        return {'count': 0, 'error': str(e)}


def update_dynamodb(vehicle_records: List[Dict]) -> Dict:
    """Update DynamoDB with current station state"""

    try:
        table = dynamodb_resource.Table(DYNAMODB_TABLE)
        count = 0

        for record in vehicle_records:
            station_id = record.get('current_stop')
            if not station_id:
                continue

            now_unix = int(datetime.now(timezone.utc).timestamp())
            expiration_time = now_unix + 600  # 10 minute TTL

            arrival = {
                'line': record.get('route_id'),
                'arrival_seconds': record.get('next_arrival_seconds'),
                'destination': record.get('headsign', 'Unknown'),
                'vehicle_id': record.get('vehicle_id'),
                'timestamp': now_unix
            }

            # Update item with new arrival
            table.update_item(
                Key={
                    'station_id': station_id,
                    'timestamp': now_unix
                },
                UpdateExpression=(
                    'SET station_name = :sn, '
                    'next_arrivals = list_append(if_not_exists(next_arrivals, :empty_list), :arrivals), '
                    'last_update = :now, '
                    'expiration_time = :exp '
                ),
                ExpressionAttributeValues={
                    ':sn': f"Station {station_id}",
                    ':arrivals': [arrival],
                    ':empty_list': [],
                    ':now': now_unix,
                    ':exp': expiration_time
                }
            )
            count += 1

        logger.info(f"✓ Updated {count} DynamoDB items")
        return {'count': count}

    except Exception as e:
        logger.error(f"Error updating DynamoDB: {str(e)}", exc_info=True)
        return {'count': 0, 'error': str(e)}
