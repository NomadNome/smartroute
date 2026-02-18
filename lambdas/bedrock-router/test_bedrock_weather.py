#!/usr/bin/env python3
"""
Test script for Bedrock weather predictor
Tests the weather prediction module with current DynamoDB data
"""

import json
import logging
from bedrock_weather_predictor import get_weather_predictor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_weather_prediction():
    """Test Bedrock weather prediction"""

    print("\n" + "="*60)
    print("🌤️  BEDROCK WEATHER PREDICTION TEST")
    print("="*60 + "\n")

    try:
        # Get predictor instance
        predictor = get_weather_predictor()
        logger.info("✅ Predictor initialized")

        # Fetch historical data
        logger.info("📊 Fetching historical weather data...")
        historical = predictor.get_historical_weather(days=7)
        logger.info(f"✅ Found {len(historical)} historical records")

        if not historical:
            logger.error("❌ No historical data available - run weather poller first")
            return False

        # Get current weather (last record)
        current = historical[-1] if historical else None
        if not current:
            logger.error("❌ No current weather available")
            return False

        logger.info(f"\n📍 Current Weather:")
        logger.info(f"   Temperature: {current.get('temperature')}°F")
        logger.info(f"   Conditions: {current.get('conditions')}")
        logger.info(f"   Wind: {current.get('wind_speed')} mph")
        logger.info(f"   Precipitation: {current.get('precipitation')} mm")

        # Get Bedrock prediction
        logger.info(f"\n🤖 Getting Bedrock prediction...")
        prediction = predictor.get_prediction_for_route(current, historical)

        logger.info(f"\n✅ PREDICTION RESULTS:")
        logger.info(f"   Pattern Analysis: {prediction['prediction'].get('pattern_analysis', 'N/A')[:100]}...")
        logger.info(f"   Prediction: {prediction['prediction'].get('prediction', 'N/A')[:100]}...")
        logger.info(f"   Impact: {prediction['prediction'].get('impact_on_commute', 'N/A')[:100]}...")
        logger.info(f"   Confidence: {prediction['prediction'].get('confidence', 'N/A')}")
        logger.info(f"   Recommendation: {prediction['prediction'].get('recommendation', 'N/A')}")

        logger.info(f"\n📋 Full Prediction:")
        print(json.dumps(prediction, indent=2))

        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = test_weather_prediction()
    exit(0 if success else 1)
