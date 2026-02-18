"""
Context enricher - adds real-time weather context to route recommendations
Uses Bedrock predictions based on historical data
"""

import boto3
import json
from datetime import datetime, timedelta
import logging
from bedrock_weather_predictor import get_weather_predictor

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class ContextEnricher:
    def __init__(self):
        """Initialize context enricher with DynamoDB and Bedrock"""
        self.dynamodb = boto3.resource('dynamodb')
        self.weather_table = self.dynamodb.Table('weather_state')
        self.predictor = get_weather_predictor()

    def get_latest_weather(self):
        """
        Fetch the most recent weather record from DynamoDB

        Returns:
        {
            'temperature': 55,
            'feels_like': 55,
            'conditions': 'Sunny',
            'wind_speed': 6,
            'precipitation': 0,
            'weather_impact': 'none',
            'timestamp': '2025-11-24T18:54:05.076910'
        }
        """
        try:
            response = self.weather_table.scan(Limit=1)

            if not response.get('Items'):
                logger.warning("❌ No weather data found in DynamoDB")
                return None

            item = response['Items'][0]

            # Convert DynamoDB format to readable format
            weather = {
                'temperature': int(item.get('temperature', {}).get('N', 0)) if 'N' in item.get('temperature', {}) else item.get('temperature'),
                'feels_like': int(item.get('feels_like', {}).get('N', 0)) if 'N' in item.get('feels_like', {}) else item.get('feels_like'),
                'humidity': int(item.get('humidity', {}).get('N', 0)) if 'N' in item.get('humidity', {}) else item.get('humidity'),
                'conditions': item.get('conditions', {}).get('S', 'Unknown') if 'S' in item.get('conditions', {}) else item.get('conditions'),
                'description': item.get('description', {}).get('S', 'unknown') if 'S' in item.get('description', {}) else item.get('description'),
                'wind_speed': float(item.get('wind_speed', {}).get('N', 0)) if 'N' in item.get('wind_speed', {}) else item.get('wind_speed'),
                'wind_gust': float(item.get('wind_gust', {}).get('N', 0)) if 'N' in item.get('wind_gust', {}) else item.get('wind_gust'),
                'precipitation': float(item.get('precipitation', {}).get('N', 0)) if 'N' in item.get('precipitation', {}) else item.get('precipitation'),
                'weather_impact': item.get('weather_impact', {}).get('S', 'none') if 'S' in item.get('weather_impact', {}) else item.get('weather_impact'),
                'timestamp': item.get('timestamp', {}).get('S', '') if 'S' in item.get('timestamp', {}) else item.get('timestamp')
            }

            logger.info(f"✅ Retrieved weather: {weather['conditions']}, {weather['temperature']}°F")
            return weather

        except Exception as e:
            logger.error(f"❌ Error fetching weather: {e}")
            return None

    def enrich_route_with_weather(self, route, weather):
        """
        Add weather context to a single route
        Uses Bedrock predictions based on historical data

        Returns enriched route with 'weather_context' field
        """
        if not weather:
            return route

        try:
            # Get Bedrock prediction based on historical data
            prediction = self.predictor.get_prediction_for_route(weather)

            # Determine weather impact on this route
            weather_context = {
                'current_weather': {
                    'temperature': weather['temperature'],
                    'feels_like': weather['feels_like'],
                    'conditions': weather['conditions'],
                    'wind_speed': weather['wind_speed'],
                    'precipitation': weather['precipitation']
                },
                'impact_level': weather['weather_impact'],
                'walking_route_impact': self._assess_walking_impact(weather),
                'prediction': prediction['prediction'],  # Bedrock analysis
                'recommendation': prediction['prediction'].get('recommendation', self._get_weather_recommendation(weather)),
                'timestamp': weather['timestamp']
            }

            route['weather_context'] = weather_context
            return route

        except Exception as e:
            logger.error(f"❌ Error enriching route: {e}")
            # Fall back to current weather only
            weather_context = {
                'current_weather': {
                    'temperature': weather['temperature'],
                    'feels_like': weather['feels_like'],
                    'conditions': weather['conditions'],
                    'wind_speed': weather['wind_speed'],
                    'precipitation': weather['precipitation']
                },
                'impact_level': weather['weather_impact'],
                'walking_route_impact': self._assess_walking_impact(weather),
                'recommendation': self._get_weather_recommendation(weather),
                'timestamp': weather['timestamp']
            }
            route['weather_context'] = weather_context
            return route

    def enrich_routes(self, routes, origin=None, destination=None):
        """
        Enrich multiple routes with weather context

        Takes a list of routes from Dijkstra router and adds weather context to each
        """
        logger.info("🌤️  Enriching routes with weather context...")

        # Get latest weather
        weather = self.get_latest_weather()

        # Enrich each route
        enriched_routes = []
        for route in routes:
            enriched = self.enrich_route_with_weather(route, weather)
            enriched_routes.append(enriched)

        logger.info(f"✅ Enriched {len(enriched_routes)} routes with weather")
        return enriched_routes

    def _assess_walking_impact(self, weather):
        """
        Assess how weather impacts walking portions of the route

        Returns: {
            'has_impact': True/False,
            'type': 'rain', 'wind', 'heat', 'cold', 'fog', etc,
            'severity': 'low', 'medium', 'high',
            'recommendation': 'umbrella', 'covered_route', 'bundle_up', etc
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
                    'message': f"Heavy rain ({weather['precipitation']} mm) - prefer covered walking routes"
                })
            elif weather['precipitation'] > 0.5:
                impacts.append({
                    'type': 'rain',
                    'severity': 'medium',
                    'recommendation': 'covered_route_preferred',
                    'message': f"Moderate rain ({weather['precipitation']} mm) - covered routes recommended"
                })
            else:
                impacts.append({
                    'type': 'rain',
                    'severity': 'low',
                    'recommendation': 'umbrella_recommended',
                    'message': f"Light rain - bring an umbrella"
                })

        # Wind check
        if weather['wind_speed'] > 20:
            impacts.append({
                'type': 'wind',
                'severity': 'high',
                'recommendation': 'watch_footing',
                'message': f"Strong wind ({weather['wind_speed']} mph) - watch your footing"
            })
        elif weather['wind_speed'] > 15:
            impacts.append({
                'type': 'wind',
                'severity': 'medium',
                'recommendation': 'steady_yourself',
                'message': f"Moderate wind ({weather['wind_speed']} mph) - can affect walking"
            })

        # Temperature extremes
        temp = weather['temperature']
        if temp > 90:
            impacts.append({
                'type': 'heat',
                'severity': 'high',
                'recommendation': 'stay_hydrated',
                'message': f"Extreme heat ({temp}°F) - stay hydrated, seek shade when possible"
            })
        elif temp > 85:
            impacts.append({
                'type': 'heat',
                'severity': 'medium',
                'recommendation': 'bring_water',
                'message': f"Hot ({temp}°F) - bring water"
            })
        elif temp < 20:
            impacts.append({
                'type': 'cold',
                'severity': 'high',
                'recommendation': 'bundle_up',
                'message': f"Extreme cold ({temp}°F) - bundle up well"
            })
        elif temp < 32:
            impacts.append({
                'type': 'cold',
                'severity': 'medium',
                'recommendation': 'wear_warm_clothes',
                'message': f"Below freezing ({temp}°F) - wear warm clothes"
            })

        if not impacts:
            return {
                'has_impact': False,
                'impacts': [],
                'overall_message': 'Weather is fine for walking'
            }

        return {
            'has_impact': True,
            'impacts': impacts,
            'overall_message': impacts[0]['message'] if impacts else 'Weather is fine for walking'
        }

    def _get_weather_recommendation(self, weather):
        """
        Get a brief recommendation based on weather conditions

        Returns: string recommendation
        """
        conditions = weather['conditions'].lower()

        if weather['precipitation'] > 0.5:
            return "☔ Bring umbrella or consider covered walking routes"
        elif weather['temperature'] > 90:
            return "☀️ Extreme heat - stay hydrated and wear sunscreen"
        elif weather['wind_speed'] > 20:
            return "💨 Strong winds - watch your footing"
        elif weather['temperature'] < 32:
            return "❄️ Below freezing - wear warm clothes"
        else:
            return f"🌤️ {weather['conditions']} - normal commute conditions"

    def get_weather_summary_for_response(self, weather):
        """
        Get a summary of weather to include in route response

        Returns: simple dict suitable for JSON response
        """
        if not weather:
            return None

        return {
            'temperature': weather['temperature'],
            'conditions': weather['conditions'],
            'wind_speed': weather['wind_speed'],
            'precipitation': weather['precipitation'],
            'impact': weather['weather_impact']
        }


# Global instance
_enricher = None

def get_context_enricher():
    """Get or create context enricher instance"""
    global _enricher
    if _enricher is None:
        _enricher = ContextEnricher()
    return _enricher
