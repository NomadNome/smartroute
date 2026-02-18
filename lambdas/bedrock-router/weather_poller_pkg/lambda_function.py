"""
Lambda handler for weather polling - triggered by EventBridge every 5 minutes
"""

import json
import logging
from weather_poller import WeatherPoller

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Triggered by EventBridge every 5 minutes
    Polls NOAA weather and stores in DynamoDB (no API key needed)
    """
    try:
        logger.info("🌤️  Weather poller Lambda triggered")
        logger.info(f"Event: {json.dumps(event)}")

        # Get poller instance (no API key needed for NOAA)
        poller = get_weather_poller_noaa()

        # Poll weather
        result = poller.poll()

        if result['success']:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Weather polling successful',
                    'weather': {
                        'temperature': result['weather']['temperature'],
                        'conditions': result['weather']['conditions'],
                        'precipitation': result['weather']['precipitation'],
                        'wind_speed': result['weather']['wind_speed']
                    },
                    'impact': result['weather_impact']['overall_impact']
                })
            }
        else:
            logger.error(f"Weather polling failed: {result['error']}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': result['error']
                })
            }

    except Exception as e:
        logger.error(f"❌ Lambda error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }


# Global instance (Lambda reuses warm containers)
_poller = None

def get_weather_poller_noaa():
    """Get or create weather poller instance (NOAA - no API key needed)"""
    global _poller
    if _poller is None:
        _poller = WeatherPoller()  # No API key needed for NOAA
    return _poller
