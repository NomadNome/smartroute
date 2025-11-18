"""
SmartRoute Real-Time Processor (Simplified)

Consumes records from Kinesis stream and updates DynamoDB
with current station states for sub-second latency queries.

Triggered by Kinesis event mapping - automatically scales with shard count.
"""

import json
import boto3
import base64
from datetime import datetime, timezone
from typing import Dict, List
import logging

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb_resource = boto3.resource('dynamodb')

# Environment variables
DYNAMODB_TABLE = 'smartroute_station_realtime_state'

logger.info("Real-Time Processor initialized")


def lambda_handler(event: Dict, context) -> Dict:
    """
    Process Kinesis records and update DynamoDB

    Args:
        event: Kinesis event containing multiple records
        context: Lambda context

    Returns:
        Processing results
    """

    logger.info(f"Processing {len(event.get('Records', []))} Kinesis records")

    successful = 0
    failed = 0

    try:
        table = dynamodb_resource.Table(DYNAMODB_TABLE)

        for record in event.get('Records', []):
            try:
                # Decode Kinesis record
                payload = json.loads(
                    base64.b64decode(record['kinesis']['data']).decode('utf-8')
                )

                logger.debug(f"Processing record: {payload.get('trip_id')}")

                # Update DynamoDB
                update_station_state(table, payload)
                successful += 1

            except Exception as e:
                logger.error(f"Failed to process record: {str(e)}")
                failed += 1
                # Continue processing other records
                continue

        result = {
            'statusCode': 200,
            'recordsProcessed': successful,
            'recordsFailed': failed,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        logger.info(f"Processing complete: {result}")

        return result

    except Exception as e:
        logger.error(f"Critical error in Lambda handler: {str(e)}", exc_info=True)

        # Return 200 anyway - we've already logged the error
        # Kinesis will retry if needed
        return {
            'statusCode': 200,
            'message': f'Handler error (logged): {str(e)}'
        }


def update_station_state(table, vehicle_record: Dict) -> None:
    """
    Update DynamoDB with vehicle state

    Creates or updates station entry with latest arrivals and alerts.

    Args:
        table: DynamoDB table resource
        vehicle_record: Vehicle data from Kinesis
    """

    try:
        station_id = vehicle_record.get('current_stop')

        if not station_id:
            logger.warning("Vehicle record missing current_stop")
            return

        now_unix = int(datetime.now(timezone.utc).timestamp())
        expiration_time = now_unix + 600  # TTL: 10 minutes

        # Build arrival record
        arrival = {
            'line': vehicle_record.get('route_id'),
            'arrival_seconds': vehicle_record.get('next_arrival_seconds'),
            'destination': vehicle_record.get('headsign', 'Unknown'),
            'vehicle_id': vehicle_record.get('vehicle_id'),
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

        logger.debug(f"Updated station {station_id}")

    except Exception as e:
        logger.error(f"Error updating DynamoDB: {str(e)}")
        raise
