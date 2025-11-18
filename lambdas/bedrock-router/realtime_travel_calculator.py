#!/usr/bin/env python3
"""
Real-time Travel Time Calculator for SmartRoute
Uses Phase 1's MTA GTFS-RT data from DynamoDB to calculate actual travel times
"""

import boto3
import logging
from typing import Dict, List, Optional, Tuple

# Import static station mappings
try:
    from station_mappings import get_stop_id_for_station as get_stop_id_static
except ImportError:
    get_stop_id_static = None

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
realtime_table = dynamodb.Table('smartroute_station_realtime_state')

# Cache for station name to MTA stop ID mappings
_station_name_cache = {}


def get_stop_id_for_station(station_name: str) -> Optional[str]:
    """
    Get MTA stop ID for a friendly station name
    Uses static mapping first (fast), falls back to DynamoDB scan
    """
    # Try static mapping first (primary source - reliable, no DynamoDB calls)
    if get_stop_id_static:
        try:
            stop_id = get_stop_id_static(station_name)
            if stop_id:
                logger.info(f"✅ Found stop ID from static mapping: {station_name} → {stop_id}")
                return stop_id
        except Exception as e:
            logger.warning(f"⚠️  Static mapping lookup failed: {e}")

    # Fall back to DynamoDB scan (for any unmapped stations from Phase 1)
    if not _station_name_cache:
        try:
            response = realtime_table.scan(
                ProjectionExpression='station_id,station_name'
            )
            for item in response.get('Items', []):
                station_name_db = item.get('station_name', '')
                stop_id = item.get('station_id', '')
                if station_name_db and stop_id:
                    _station_name_cache[station_name_db.lower()] = stop_id

            logger.info(f"✅ Built DynamoDB station mapping with {len(_station_name_cache)} entries")
        except Exception as e:
            logger.warning(f"⚠️  Failed to build DynamoDB mapping: {e}")

    # Check cache
    return _station_name_cache.get(station_name.lower())


def get_station_arrivals(stop_id: str) -> List[Dict]:
    """
    Get next arrivals for a station from real-time data
    Returns list of arrival dicts with: line, eta_seconds, delay_seconds, destination
    """
    try:
        response = realtime_table.query(
            KeyConditionExpression='station_id = :sid',
            ExpressionAttributeValues={':sid': stop_id},
            ScanIndexForward=False,  # Most recent first
            Limit=1
        )

        if not response.get('Items'):
            logger.warning(f"⚠️  No real-time data for stop {stop_id}")
            return []

        item = response['Items'][0]
        arrivals = item.get('next_arrivals', [])

        # Extract key info from each arrival
        processed_arrivals = []
        for arrival in arrivals:
            processed_arrivals.append({
                'line': arrival.get('line', 'Unknown'),
                'eta_seconds': int(arrival.get('arrival_seconds', 0)),
                'delay_seconds': int(arrival.get('delay_seconds', 0)),
                'destination': arrival.get('destination', 'Unknown'),
                'arrival_time': arrival.get('arrival_time')
            })

        return processed_arrivals

    except Exception as e:
        logger.error(f"❌ Error fetching arrivals for {stop_id}: {e}")
        return []


def calculate_route_travel_time(stations: List[str], lines: List[str]) -> Tuple[int, str]:
    """
    Calculate total travel time for a route based on real-time ETAs

    Args:
        stations: List of station names in order (e.g., ['Times Square', 'Herald Square', '34th St'])
        lines: Corresponding transit lines for each leg (e.g., ['1', '1', '1'])

    Returns:
        Tuple of (total_time_seconds, detailed_explanation)
    """
    try:
        if not stations or len(stations) < 2:
            return 0, "Single station - no travel needed"

        total_time_seconds = 0
        leg_details = []

        # Get the first leg's departure time
        first_stop_id = get_stop_id_for_station(stations[0])
        if not first_stop_id:
            logger.warning(f"⚠️  Could not find stop ID for {stations[0]}")
            return 0, f"Could not calculate time - station not found"

        first_arrivals = get_station_arrivals(first_stop_id)
        if not first_arrivals:
            logger.warning(f"⚠️  No arrival data for {stations[0]}")
            # Fallback to ~2 min per stop estimate
            estimated_time = (len(stations) - 1) * 120
            return estimated_time, f"Using estimated {estimated_time}s (~{estimated_time//60}m) based on {len(stations)-1} stops"

        # Find first arrival on the requested line
        first_departure = None
        for arrival in first_arrivals:
            if arrival['line'] == lines[0]:
                first_departure = arrival
                break

        if not first_departure:
            logger.warning(f"⚠️  No arrival on line {lines[0]} at {stations[0]}")
            # Use first available arrival
            first_departure = first_arrivals[0]

        # Time from origin to first station
        first_eta = first_departure['eta_seconds']
        leg_details.append(f"{stations[0]} → {stations[1]}: {first_eta}s (Line {first_departure['line']})")
        total_time_seconds += first_eta

        # For simplicity, add average time between remaining stations
        # In a more sophisticated version, we'd query each intermediate station
        if len(stations) > 2:
            # Estimate: ~2 minutes (120 seconds) per additional stop
            remaining_stops = len(stations) - 2
            remaining_time = remaining_stops * 120
            leg_details.append(f"{remaining_stops} additional stops: ~{remaining_time}s")
            total_time_seconds += remaining_time

        explanation = " → ".join(leg_details)

        logger.info(f"✅ Calculated route time: {total_time_seconds}s (~{total_time_seconds//60}m)")
        return total_time_seconds, explanation

    except Exception as e:
        logger.error(f"❌ Error calculating travel time: {e}")
        return 0, f"Error calculating real-time travel time: {str(e)}"


def get_eta_for_station_line(station_name: str, line: str) -> Optional[int]:
    """
    Get ETA in seconds for a specific station and line
    """
    try:
        stop_id = get_stop_id_for_station(station_name)
        if not stop_id:
            return None

        arrivals = get_station_arrivals(stop_id)
        for arrival in arrivals:
            if arrival['line'] == line:
                return arrival['eta_seconds']

        return None

    except Exception as e:
        logger.error(f"Error getting ETA: {e}")
        return None
