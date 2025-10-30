"""
SmartRoute MTA GTFS-RT Data Poller

Polls the MTA real-time transit API every 30 seconds and streams
vehicle positions, arrival predictions, and service alerts to:
- S3 (for archival)
- Kinesis (for real-time processing)
- DynamoDB (for current state)
"""

import json
import boto3
import requests
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import logging
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes.kinesis_stream_event import KinesisStreamRecord

# Initialize AWS Lambda Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Initialize AWS SDK clients
s3_client = boto3.client('s3')
kinesis_client = boto3.client('kinesis')
dynamodb_resource = boto3.resource('dynamodb')
secretsmanager_client = boto3.client('secretsmanager')

# Environment variables
S3_BUCKET = os.environ.get('S3_BUCKET', 'smartroute-data-lake-069899605581')
KINESIS_STREAM = os.environ.get('KINESIS_STREAM_NAME', 'transit_data_stream')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'smartroute_station_realtime_state')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
MTA_API_BASE = 'http://datamine.mta.info/mta_esi.php'

# Configuration
MTA_FEEDS = {
    '1': 'subway',      # 1 = Subway (we care about this)
    '2': 'bus',         # 2 = Bus (optional)
    '3': 'lirr'         # 3 = LIRR/Metro-North (optional)
}

# Set logger level
logger.setLevel(LOG_LEVEL)

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_cold_start_metric
def lambda_handler(event: Dict, context: LambdaContext) -> Dict:
    """
    Main Lambda handler - triggered by EventBridge every 30 seconds

    Args:
        event: EventBridge event
        context: Lambda context

    Returns:
        Summary of processing results
    """

    logger.info(f"Starting MTA data poll at {datetime.now(timezone.utc).isoformat()}")

    try:
        # Get API key from Secrets Manager
        mta_api_key = get_secret('smartroute/api-keys')['mta_api_key']

        # Fetch data from MTA (we'll start with feed_id=1 for subway)
        mta_data = fetch_mta_data(mta_api_key, feed_id='1')

        if not mta_data:
            logger.warning("No data received from MTA API")
            metrics.add_metric(name="NoDataReceived", unit="Count", value=1)
            return {
                'statusCode': 200,
                'message': 'No data received from MTA API'
            }

        # Parse the raw response
        vehicle_records, alerts = parse_mta_response(mta_data)

        logger.info(f"Parsed {len(vehicle_records)} vehicle records and {len(alerts)} alerts")
        metrics.add_metric(name="VehicleRecordsParsed", unit="Count", value=len(vehicle_records))
        metrics.add_metric(name="AlertsParsed", unit="Count", value=len(alerts))

        # Write to all three destinations in parallel
        s3_result = write_to_s3(vehicle_records, alerts)
        kinesis_result = write_to_kinesis(vehicle_records, alerts)
        dynamodb_result = update_dynamodb(vehicle_records)

        # Compile results
        result = {
            'statusCode': 200,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'records_processed': len(vehicle_records),
            'alerts_processed': len(alerts),
            's3_writes': s3_result,
            'kinesis_records': kinesis_result,
            'dynamodb_updates': dynamodb_result,
            'message': 'MTA data successfully processed'
        }

        logger.info(f"Processing complete: {result}")
        metrics.add_metric(name="ProcessingSuccess", unit="Count", value=1)

        return result

    except Exception as e:
        logger.exception(f"Error processing MTA data: {str(e)}")
        metrics.add_metric(name="ProcessingError", unit="Count", value=1)

        # Still return 200 so EventBridge doesn't retry
        # The error is logged for investigation
        return {
            'statusCode': 200,
            'message': f'Error processing data (logged): {str(e)}',
            'error': str(e)
        }


def get_secret(secret_name: str) -> Dict:
    """
    Retrieve secret from AWS Secrets Manager

    Args:
        secret_name: Name of the secret

    Returns:
        Dictionary with secret key-value pairs
    """
    try:
        response = secretsmanager_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        logger.error(f"Failed to get secret {secret_name}: {str(e)}")
        raise


def fetch_mta_data(api_key: str, feed_id: str = '1') -> Optional[bytes]:
    """
    Fetch real-time data from MTA GTFS-RT API

    Args:
        api_key: MTA API key
        feed_id: Feed ID (1=Subway, 2=Bus, 3=LIRR)

    Returns:
        Raw protobuf response bytes or None if error
    """
    try:
        params = {
            'key': api_key,
            'feed_id': feed_id
        }

        logger.info(f"Fetching MTA feed {feed_id}")

        response = requests.get(
            MTA_API_BASE,
            params=params,
            timeout=30
        )

        if response.status_code == 200:
            metrics.add_metric(name="MTA_API_Success", unit="Count", value=1)
            return response.content
        else:
            logger.error(f"MTA API returned status {response.status_code}")
            metrics.add_metric(name="MTA_API_Error", unit="Count", value=1)
            return None

    except requests.Timeout:
        logger.error("MTA API request timeout")
        metrics.add_metric(name="MTA_API_Timeout", unit="Count", value=1)
        return None
    except Exception as e:
        logger.error(f"Error fetching MTA data: {str(e)}")
        metrics.add_metric(name="MTA_API_Exception", unit="Count", value=1)
        return None


def parse_mta_response(data: bytes) -> Tuple[List[Dict], List[Dict]]:
    """
    Parse protobuf GTFS-RT response into vehicle records and alerts

    NOTE: This is a placeholder. Full protobuf parsing requires:
    1. Download GTFS-RT protobuf descriptor from MTA
    2. Compile with protoc
    3. Use generated Python classes

    For now, returns empty lists. Full implementation in next commit.

    Args:
        data: Raw protobuf bytes from MTA API

    Returns:
        Tuple of (vehicle_records, alerts)
    """
    try:
        # TODO: Implement actual protobuf parsing
        # This requires:
        # - google.protobuf library
        # - gtfs-realtime-bindings Python package
        # - MTA GTFS-RT descriptor file

        logger.warning("Protobuf parsing not yet implemented - returning empty data")

        # For now, return sample structure for testing pipeline
        sample_vehicle = {
            'source': 'mta-poller',
            'feed_id': '1',
            'timestamp': int(datetime.now(timezone.utc).timestamp()),
            'trip_id': 'SAMPLE_TRIP',
            'vehicle_id': 'SAMPLE_VEH',
            'route_id': '1',
            'current_stop': 'S127N',
            'status': 'IN_TRANSIT_TO',
            'latitude': 40.8207,
            'longitude': -73.9654,
            'next_arrival_seconds': 180,
            'crowding_estimate': None
        }

        vehicle_records = [sample_vehicle]
        alerts = []

        return vehicle_records, alerts

    except Exception as e:
        logger.error(f"Error parsing MTA response: {str(e)}")
        metrics.add_metric(name="ParseError", unit="Count", value=1)
        return [], []


def write_to_s3(vehicles: List[Dict], alerts: List[Dict]) -> int:
    """
    Write raw data to S3 data lake with date/hour partitioning

    Args:
        vehicles: List of vehicle records
        alerts: List of alert records

    Returns:
        Number of records written
    """
    try:
        now = datetime.now(timezone.utc)

        # Build partitioned path: raw/mta/realtime/year=YYYY/month=MM/day=DD/hour=HH/
        partition_path = (
            f"raw/mta/realtime/"
            f"year={now.year:04d}/"
            f"month={now.month:02d}/"
            f"day={now.day:02d}/"
            f"hour={now.hour:02d}/"
        )

        filename = f"mta_realtime_{now.strftime('%Y%m%d_%H%M%S')}.jsonl"
        s3_key = partition_path + filename

        # Combine vehicle and alert data
        all_records = vehicles + alerts

        if not all_records:
            logger.warning("No records to write to S3")
            return 0

        # Write as JSON Lines (one JSON object per line)
        content = '\n'.join(json.dumps(record) for record in all_records)

        logger.info(f"Writing {len(all_records)} records to S3: s3://{S3_BUCKET}/{s3_key}")

        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=content.encode('utf-8'),
            ContentType='application/x-ndjson',
            ServerSideEncryption='AES256'
        )

        metrics.add_metric(name="S3_RecordsWritten", unit="Count", value=len(all_records))
        logger.info(f"Successfully wrote {len(all_records)} records to S3")

        return len(all_records)

    except Exception as e:
        logger.error(f"Error writing to S3: {str(e)}")
        metrics.add_metric(name="S3_WriteError", unit="Count", value=1)
        return 0


def write_to_kinesis(vehicles: List[Dict], alerts: List[Dict]) -> int:
    """
    Write records to Kinesis stream for real-time processing

    Args:
        vehicles: List of vehicle records
        alerts: List of alert records

    Returns:
        Number of records written
    """
    try:
        all_records = vehicles + alerts

        if not all_records:
            logger.warning("No records to write to Kinesis")
            return 0

        logger.info(f"Writing {len(all_records)} records to Kinesis stream: {KINESIS_STREAM}")

        # Write each record as separate Kinesis record
        # Using trip_id as partition key for ordering
        failed_records = []

        for record in all_records:
            try:
                partition_key = record.get('trip_id', 'DEFAULT')

                kinesis_client.put_record(
                    StreamName=KINESIS_STREAM,
                    Data=json.dumps(record),
                    PartitionKey=partition_key
                )
            except Exception as e:
                logger.error(f"Failed to write record to Kinesis: {str(e)}")
                failed_records.append(record)

        successful = len(all_records) - len(failed_records)
        metrics.add_metric(name="Kinesis_RecordsWritten", unit="Count", value=successful)

        if failed_records:
            logger.warning(f"{len(failed_records)} records failed to write to Kinesis")
            metrics.add_metric(name="Kinesis_WriteError", unit="Count", value=len(failed_records))

        logger.info(f"Successfully wrote {successful} records to Kinesis")

        return successful

    except Exception as e:
        logger.error(f"Error writing to Kinesis: {str(e)}")
        metrics.add_metric(name="Kinesis_StreamError", unit="Count", value=1)
        return 0


def update_dynamodb(vehicles: List[Dict]) -> int:
    """
    Update DynamoDB with current station states

    Args:
        vehicles: List of vehicle records

    Returns:
        Number of records updated
    """
    try:
        if not vehicles:
            logger.warning("No vehicle records to update in DynamoDB")
            return 0

        table = dynamodb_resource.Table(DYNAMODB_TABLE)

        logger.info(f"Updating DynamoDB table {DYNAMODB_TABLE} with {len(vehicles)} records")

        updated_count = 0

        # Group by station_id
        stations = {}
        for vehicle in vehicles:
            station_id = vehicle.get('current_stop', 'UNKNOWN')
            if station_id not in stations:
                stations[station_id] = []
            stations[station_id].append(vehicle)

        # Write aggregated state for each station
        now_unix = int(datetime.now(timezone.utc).timestamp())
        expiration_time = now_unix + 600  # 10 minutes from now (TTL)

        for station_id, vehicles_at_station in stations.items():
            try:
                # Build next_arrivals array
                next_arrivals = [
                    {
                        'line': v.get('route_id'),
                        'arrival_seconds': v.get('next_arrival_seconds'),
                        'destination': v.get('headsign', 'Unknown'),
                        'vehicle_id': v.get('vehicle_id')
                    }
                    for v in vehicles_at_station
                ]

                table.put_item(
                    Item={
                        'station_id': station_id,
                        'timestamp': now_unix,
                        'station_name': f"Station {station_id}",  # TODO: lookup from GTFS
                        'lines': list(set(v.get('route_id') for v in vehicles_at_station)),
                        'next_arrivals': next_arrivals,
                        'active_alerts': [],  # TODO: parse alerts
                        'crowding_estimate': 'UNKNOWN',  # TODO: estimate from ML
                        'last_update': now_unix,
                        'expiration_time': expiration_time
                    }
                )
                updated_count += 1

            except Exception as e:
                logger.error(f"Failed to update station {station_id}: {str(e)}")

        metrics.add_metric(name="DynamoDB_StationsUpdated", unit="Count", value=updated_count)
        logger.info(f"Successfully updated {updated_count} stations in DynamoDB")

        return updated_count

    except Exception as e:
        logger.error(f"Error updating DynamoDB: {str(e)}")
        metrics.add_metric(name="DynamoDB_UpdateError", unit="Count", value=1)
        return 0
