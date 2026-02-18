"""
Bedrock Weather Predictor - analyzes historical weather data to make predictions
Uses Bedrock Claude to identify patterns and predict weather impacts on routes
"""

import boto3
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class BedrockWeatherPredictor:
    def __init__(self, region: str = 'us-east-1', account_id: str = '069899605581'):
        """Initialize weather predictor with Bedrock and DynamoDB"""
        self.bedrock = boto3.client('bedrock-runtime', region_name=region)
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.weather_table = self.dynamodb.Table('weather_state')
        # Use inference profile ARN (same as route recommender)
        self.model_arn = f"arn:aws:bedrock:{region}:{account_id}:inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0"
        logger.info(f"✅ Bedrock Weather Predictor initialized")
        logger.info(f"   Model ARN: {self.model_arn}")

    def get_historical_weather(self, days=7):
        """
        Fetch historical weather data from DynamoDB (last N days)

        Returns list of weather records sorted by time
        """
        try:
            logger.info(f"📊 Fetching {days} days of historical weather...")

            # Scan the weather_state table
            response = self.weather_table.scan()

            items = response.get('Items', [])

            if not items:
                logger.warning("❌ No historical weather data found")
                return []

            # Convert Decimal types to float for JSON
            converted_items = []
            for item in items:
                converted = {
                    'timestamp': item.get('timestamp'),
                    'temperature': float(item.get('temperature', 0)) if 'N' not in str(type(item.get('temperature', 0))) else item.get('temperature'),
                    'conditions': item.get('conditions'),
                    'wind_speed': float(item.get('wind_speed', 0)) if 'N' not in str(type(item.get('wind_speed', 0))) else item.get('wind_speed'),
                    'precipitation': float(item.get('precipitation', 0)) if 'N' not in str(type(item.get('precipitation', 0))) else item.get('precipitation'),
                    'weather_impact': item.get('weather_impact')
                }
                converted_items.append(converted)

            logger.info(f"✅ Found {len(converted_items)} historical weather records")
            return converted_items

        except Exception as e:
            logger.error(f"❌ Error fetching historical weather: {e}")
            return []

    def analyze_patterns_with_bedrock(self, current_weather, historical_data):
        """
        Use Bedrock to analyze weather patterns and make predictions

        Returns: {
            'pattern_analysis': 'description of patterns found',
            'prediction': 'what weather is coming',
            'impact_on_commute': 'how it affects transit',
            'confidence': 'high/medium/low',
            'recommendation': 'what user should do'
        }
        """
        try:
            logger.info("🤖 Analyzing weather patterns with Bedrock...")

            # Prepare historical data summary for Bedrock
            if not historical_data:
                logger.warning("⚠️  No historical data available for prediction")
                return self._get_default_prediction(current_weather)

            # Format historical data for Bedrock
            history_summary = self._format_historical_data(historical_data)

            # Create prompt for Bedrock
            prompt = f"""You are a weather analyst for NYC transit commuters. Analyze the following weather data and make a prediction.

CURRENT CONDITIONS:
- Temperature: {current_weather.get('temperature')}°F
- Conditions: {current_weather.get('conditions')}
- Wind Speed: {current_weather.get('wind_speed')} mph
- Precipitation: {current_weather.get('precipitation')} mm
- Impact Level: {current_weather.get('weather_impact')}

HISTORICAL WEATHER (Last 7 Days):
{history_summary}

Based on this data:
1. Identify 1-2 weather patterns you see
2. Predict what the weather will be like in the next 2-4 hours
3. Describe how this affects NYC subway commuting (crowding, delays, walking conditions)
4. Rate your confidence (high/medium/low)
5. Give one specific recommendation for commuters

Keep your analysis concise and practical. Focus on what matters for transit riders.

Format your response as JSON with these keys:
- pattern_analysis: Brief description of weather patterns
- prediction: What weather is coming
- impact_on_commute: How it affects transit
- confidence: high/medium/low
- recommendation: Specific advice for commuters"""

            response = self.bedrock.invoke_model(
                modelId=self.model_arn,
                body=json.dumps({
                    'anthropic_version': 'bedrock-2023-05-31',
                    'max_tokens': 500,
                    'messages': [
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ]
                })
            )

            result = json.loads(response['body'].read())
            response_text = result['content'][0]['text']

            logger.info(f"✅ Bedrock analysis received")

            # Try to parse JSON from response (may be wrapped in markdown code fence)
            try:
                # Remove markdown code fence if present
                if '```json' in response_text:
                    json_start = response_text.find('```json') + 7
                    json_end = response_text.rfind('```')
                    response_text = response_text[json_start:json_end].strip()
                elif '```' in response_text:
                    json_start = response_text.find('```') + 3
                    json_end = response_text.rfind('```')
                    response_text = response_text[json_start:json_end].strip()

                analysis = json.loads(response_text)
            except Exception as parse_error:
                logger.warning(f"⚠️  Could not parse JSON, using text: {parse_error}")
                # If not valid JSON, parse the text response
                analysis = {
                    'pattern_analysis': response_text[:200],
                    'prediction': 'Unable to parse prediction',
                    'impact_on_commute': 'Use current conditions',
                    'confidence': 'low',
                    'recommendation': 'Check current weather before commuting'
                }

            return analysis

        except Exception as e:
            logger.error(f"❌ Error in Bedrock analysis: {e}")
            return self._get_default_prediction(current_weather)

    def _format_historical_data(self, historical_data):
        """Format historical data for Bedrock analysis"""
        if not historical_data:
            return "No historical data available"

        # Get last 7 entries (assuming 1 per hour or less frequent)
        recent = historical_data[-7:] if len(historical_data) > 7 else historical_data

        formatted = []
        for entry in recent:
            line = f"- {entry.get('timestamp')}: {entry.get('temperature')}°F, {entry.get('conditions')}, Wind {entry.get('wind_speed')} mph"
            formatted.append(line)

        return "\n".join(formatted)

    def _get_default_prediction(self, current_weather):
        """Return default prediction when Bedrock is unavailable"""
        return {
            'pattern_analysis': f"Current conditions: {current_weather.get('conditions')} at {current_weather.get('temperature')}°F",
            'prediction': 'Weather conditions expected to continue',
            'impact_on_commute': self._assess_current_impact(current_weather),
            'confidence': 'medium',
            'recommendation': 'Check weather before departing'
        }

    def _assess_current_impact(self, weather):
        """Quick assessment of current weather impact"""
        conditions = weather.get('conditions', '').lower()
        impact = weather.get('weather_impact', 'none')

        if 'rain' in conditions:
            return "Potential for crowded platforms due to weather. Bring umbrella."
        elif 'snow' in conditions:
            return "Snow may cause service delays. Allow extra time."
        elif weather.get('wind_speed', 0) > 15:
            return "Strong winds may affect walking routes."
        elif weather.get('temperature', 70) > 90:
            return "Hot weather - stay hydrated on walking portions."
        elif weather.get('temperature', 70) < 32:
            return "Cold weather - bundle up for walking."
        else:
            return "Normal weather conditions for transit."

    def get_prediction_for_route(self, current_weather, historical_data=None):
        """
        Get weather prediction and impact for route planning

        Returns prediction suitable for including in route response
        """
        if not historical_data:
            historical_data = self.get_historical_weather(days=7)

        prediction = self.analyze_patterns_with_bedrock(current_weather, historical_data)

        return {
            'current': {
                'temperature': current_weather.get('temperature'),
                'conditions': current_weather.get('conditions'),
                'wind_speed': current_weather.get('wind_speed'),
                'precipitation': current_weather.get('precipitation')
            },
            'prediction': prediction,
            'generated_at': datetime.now().isoformat()
        }


# Global instance
_predictor = None

def get_weather_predictor():
    """Get or create weather predictor instance"""
    global _predictor
    if _predictor is None:
        _predictor = BedrockWeatherPredictor()
    return _predictor
