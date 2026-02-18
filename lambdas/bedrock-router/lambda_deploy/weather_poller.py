"""
Weather data poller - fetches current weather and stores in DynamoDB
Runs every 5 minutes via EventBridge

NYC coordinates: 40.7128, -74.0060
"""

import urllib.request
import urllib.parse
import json
import boto3
from datetime import datetime, timedelta
import logging
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class WeatherPoller:
    def __init__(self, api_key=None):
        """Initialize weather poller with NOAA (free, no API key needed)"""
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table('weather_state')
        self.nyc_lat = 40.7128
        self.nyc_lon = -74.0060

    def fetch_weather(self):
        """
        Fetch current weather from NOAA (National Weather Service)
        Free, no API key needed, accurate for NYC

        Returns:
        {
            'temperature': 62,
            'feels_like': 58,
            'humidity': 72,
            'wind_speed': 8.5,
            'wind_gust': 12.3,
            'clouds': 85,
            'visibility': 10000,
            'precipitation': 0.2,  # mm
            'conditions': 'Light Rain',
            'description': 'light rain',
            'code': 500,
            'alerts': []
        }
        """
        try:
            logger.info(f"📡 Fetching weather from NOAA...")

            # Step 1: Get grid point for NYC coordinates
            points_url = f"https://api.weather.gov/points/{self.nyc_lat},{self.nyc_lon}"
            request = urllib.request.Request(points_url)
            with urllib.request.urlopen(request, timeout=10) as response:
                points_data = json.loads(response.read().decode('utf-8'))

            # Extract forecast URL for this location
            forecast_url = points_data['properties']['forecast']

            # Step 2: Get actual forecast
            request = urllib.request.Request(forecast_url)
            with urllib.request.urlopen(request, timeout=10) as response:
                forecast_data = json.loads(response.read().decode('utf-8'))

            # Get the current (first) period
            current = forecast_data['properties']['periods'][0]

            logger.info(f"✅ Weather data received: {current.get('shortForecast')}")

            # Parse the response
            weather = {
                'temperature': current.get('temperature'),
                'feels_like': current.get('temperature'),  # NOAA doesn't provide feels_like
                'humidity': current.get('relativeHumidity', {}).get('value', 50),
                'wind_speed': self._parse_wind_speed(current.get('windSpeed', '0 mph')),
                'wind_gust': 0,  # NOAA doesn't provide gust in forecast
                'clouds': 50,  # NOAA doesn't provide cloud percentage in forecast
                'visibility': 10000,
                'precipitation': 0,  # Will be inferred from forecast text
                'conditions': current.get('shortForecast', 'Unknown'),
                'description': current.get('shortForecast', 'Unknown').lower(),
                'code': self._get_weather_code(current.get('shortForecast', '')),
                'alerts': []
            }

            return weather

        except urllib.error.URLError as e:
            logger.error(f"❌ Failed to fetch weather: {e}")
            raise Exception(f"Weather API error: {e}")
        except Exception as e:
            logger.error(f"❌ Error parsing weather data: {e}")
            raise

    def _parse_wind_speed(self, wind_string):
        """Parse wind speed from NOAA format (e.g., '10 mph' or '10 to 15 mph')"""
        try:
            # Extract first number
            import re
            match = re.search(r'(\d+)', wind_string)
            if match:
                return float(match.group(1))
            return 0
        except:
            return 0

    def _get_weather_code(self, forecast_text):
        """Map NOAA forecast text to weather code"""
        text = forecast_text.lower()
        if 'rain' in text and 'heavy' in text:
            return 502  # Heavy rain
        elif 'rain' in text:
            return 500  # Rain
        elif 'snow' in text:
            return 600  # Snow
        elif 'clear' in text or 'sunny' in text:
            return 800  # Clear
        elif 'cloudy' in text:
            return 801  # Cloudy
        elif 'wind' in text:
            return 900  # Windy
        else:
            return 0

    def classify_weather_impact(self, weather):
        """
        Classify weather impact level: 'none', 'low', 'medium', 'high'

        Returns: {
            'impact': 'low',
            'type': 'rain',  # rain, wind, heat, cold, fog
            'recommendation': 'covered_route_preferred',
            'details': 'Light rain, visible but manageable'
        }
        """
        impacts = []

        # Rain check
        if weather['precipitation'] > 0:
            if weather['precipitation'] > 2.0:
                impacts.append({
                    'type': 'rain',
                    'severity': 'high',
                    'recommendation': 'covered_route_required',
                    'details': f"Heavy rain ({weather['precipitation']} mm)"
                })
            elif weather['precipitation'] > 0.5:
                impacts.append({
                    'type': 'rain',
                    'severity': 'medium',
                    'recommendation': 'covered_route_preferred',
                    'details': f"Moderate rain ({weather['precipitation']} mm)"
                })
            else:
                impacts.append({
                    'type': 'rain',
                    'severity': 'low',
                    'recommendation': 'umbrella_recommended',
                    'details': f"Light rain ({weather['precipitation']} mm)"
                })

        # Wind check (sustained wind > 20 mph is strong)
        if weather['wind_speed'] > 20:
            impacts.append({
                'type': 'wind',
                'severity': 'high',
                'recommendation': 'watch_footing',
                'details': f"Strong wind ({weather['wind_speed']} mph)"
            })
        elif weather['wind_speed'] > 15:
            impacts.append({
                'type': 'wind',
                'severity': 'medium',
                'recommendation': 'steady_yourself',
                'details': f"Moderate wind ({weather['wind_speed']} mph)"
            })

        # Temperature extremes
        temp = weather['temperature']
        if temp > 90:
            impacts.append({
                'type': 'heat',
                'severity': 'high',
                'recommendation': 'stay_hydrated',
                'details': f"Extreme heat ({temp}°F)"
            })
        elif temp > 85:
            impacts.append({
                'type': 'heat',
                'severity': 'medium',
                'recommendation': 'bring_water',
                'details': f"Hot ({temp}°F)"
            })
        elif temp < 20:
            impacts.append({
                'type': 'cold',
                'severity': 'high',
                'recommendation': 'bundle_up',
                'details': f"Extreme cold ({temp}°F)"
            })
        elif temp < 32:
            impacts.append({
                'type': 'cold',
                'severity': 'medium',
                'recommendation': 'wear_warm_clothes',
                'details': f"Below freezing ({temp}°F)"
            })

        # Visibility check (< 1 km is fog)
        if weather['visibility'] < 1000:
            impacts.append({
                'type': 'fog',
                'severity': 'medium',
                'recommendation': 'watch_footing',
                'details': f"Limited visibility ({weather['visibility']} meters)"
            })

        # Overall impact level
        if not impacts:
            overall_impact = 'none'
        else:
            severities = [i['severity'] for i in impacts]
            if 'high' in severities:
                overall_impact = 'high'
            elif 'medium' in severities:
                overall_impact = 'medium'
            else:
                overall_impact = 'low'

        return {
            'overall_impact': overall_impact,
            'impacts': impacts,
            'timestamp': datetime.now().isoformat()
        }

    def store_weather(self, weather, weather_impact):
        """Store weather data in DynamoDB"""
        try:
            timestamp = datetime.now()
            ttl = int((timestamp + timedelta(hours=1)).timestamp())  # Keep for 1 hour

            item = {
                'location': 'new_york_city',
                'timestamp': timestamp.isoformat(),
                'temperature': Decimal(str(weather['temperature'])) if weather['temperature'] is not None else Decimal('0'),
                'feels_like': Decimal(str(weather['feels_like'])) if weather['feels_like'] is not None else Decimal('0'),
                'humidity': Decimal(str(weather['humidity'])) if weather['humidity'] is not None else Decimal('0'),
                'wind_speed': Decimal(str(weather['wind_speed'])) if weather['wind_speed'] is not None else Decimal('0'),
                'wind_gust': Decimal(str(weather['wind_gust'])) if weather['wind_gust'] is not None else Decimal('0'),
                'clouds': Decimal(str(weather['clouds'])) if weather['clouds'] is not None else Decimal('0'),
                'visibility': Decimal(str(weather['visibility'])) if weather['visibility'] is not None else Decimal('10000'),
                'precipitation': Decimal(str(weather['precipitation'])) if weather['precipitation'] is not None else Decimal('0'),
                'conditions': weather['conditions'],
                'description': weather['description'],
                'code': weather['code'],
                'weather_impact': weather_impact['overall_impact'],
                'impact_details': json.dumps(weather_impact),
                'ttl': ttl
            }

            self.table.put_item(Item=item)
            logger.info(f"✅ Weather stored in DynamoDB")
            return item

        except Exception as e:
            logger.error(f"❌ Error storing weather: {e}")
            raise

    def get_latest_weather(self):
        """Get the most recent weather record"""
        try:
            response = self.table.query(
                KeyConditionExpression='location = :location',
                ExpressionAttributeValues={':location': 'new_york_city'},
                ScanIndexForward=False,  # Sort descending (newest first)
                Limit=1
            )

            if response['Items']:
                return response['Items'][0]
            return None

        except Exception as e:
            logger.error(f"❌ Error querying weather: {e}")
            raise

    def poll(self):
        """
        Main entry point - fetch weather and store it
        """
        try:
            logger.info("🌤️  Weather polling started...")

            # Fetch weather
            weather = self.fetch_weather()

            # Classify impact
            weather_impact = self.classify_weather_impact(weather)

            # Store
            stored = self.store_weather(weather, weather_impact)

            logger.info(f"🌤️  Weather polling complete: {weather['conditions']}, {weather['temperature']}°F")

            return {
                'success': True,
                'weather': weather,
                'weather_impact': weather_impact,
                'stored': stored
            }

        except Exception as e:
            logger.error(f"❌ Weather polling failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Note: No global instance needed - NOAA poller is stateless
# Lambda will create new instance each time (lightweight)
