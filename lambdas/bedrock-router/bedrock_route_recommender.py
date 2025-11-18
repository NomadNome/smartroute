#!/usr/bin/env python3
"""
SmartRoute Bedrock Integration
Mirrors Project Vista's Claude Sonnet 4 implementation using inference profiles
"""

import boto3
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)


class BedrockRouteRecommender:
    """Route recommendation engine using Claude via Bedrock inference profiles"""

    def __init__(self, region: str = 'us-east-1', account_id: str = '069899605581'):
        """
        Initialize Bedrock client with inference profile

        Args:
            region: AWS region
            account_id: AWS account ID
        """
        self.region = region
        self.account_id = account_id

        # Use Claude Haiku 4.5 inference profile (cost-effective and fast)
        # Inference profile ARN supports on-demand scaling
        self.model_arn = f"arn:aws:bedrock:{region}:{account_id}:inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0"

        self.client = boto3.client('bedrock-runtime', region_name=region)
        logger.info(f"🤖 Initialized Bedrock client with Claude Haiku 4.5 inference profile")
        logger.info(f"   Model ARN: {self.model_arn}")

    def invoke_bedrock(self, system_prompt: str, user_message: str, max_tokens: int = 1024) -> str:
        """
        Invoke Claude via Bedrock inference profile

        Args:
            system_prompt: System instructions for Claude
            user_message: User query
            max_tokens: Maximum output tokens

        Returns:
            Claude's response text
        """
        try:
            logger.info(f"📤 Invoking Bedrock with {len(user_message)} char message...")

            # Build payload using Project Vista's format
            payload = {
                "anthropic_version": "bedrock-2023-05-31",
                "system": system_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_message
                            }
                        ]
                    }
                ],
                "max_tokens": max_tokens,
                "temperature": 0.7
            }

            # Invoke the model
            response = self.client.invoke_model(
                modelId=self.model_arn,
                body=json.dumps(payload),
                contentType='application/json'
            )

            # Parse response - Claude Sonnet 4 returns message in response_body.content[0].text
            response_body = json.loads(response['body'].read())
            logger.info(f"📥 Response received from Bedrock")

            # Extract text from Claude response
            if 'content' in response_body and response_body['content']:
                for block in response_body['content']:
                    if block.get('type') == 'text':
                        text = block['text']
                        logger.debug(f"Response text length: {len(text)} chars")
                        return text

            raise ValueError("No text content in Bedrock response")

        except Exception as e:
            logger.error(f"❌ Bedrock invocation failed: {e}")
            raise

    def build_system_prompt(self) -> str:
        """Build system prompt for route recommendation"""
        return """You are SmartRoute, an intelligent NYC subway route recommendation system.
Your job is to recommend the BEST route from origin to destination considering:

1. SAFETY: Lower crime incidents near stations = safer routes
2. RELIABILITY: Higher on-time performance = more reliable
3. EFFICIENCY: Fewer transfers and less wait time = faster

Always provide exactly THREE route options in JSON format:
1. SafeRoute - Prioritizes safety (low crime areas, reliable lines)
2. FastRoute - Prioritizes speed (direct routes, fewer stops)
3. BalancedRoute - Best overall experience (balanced approach)

For each route, provide:
- stations: List of station names in order
- lines: List of transit line numbers/letters for each leg (e.g., ["1", "1", "A"] for two legs on Line 1, then Line A)
- estimated_time_minutes: Total travel time estimate in minutes
- explanation: Brief explanation of why this route is best
- safety_score: 0-10 score (10 = safest)
- reliability_score: 0-10 score (10 = most reliable)
- efficiency_score: 0-10 score (10 = fastest)

Format your response as valid JSON with no additional text."""

    def build_user_message(self, origin: str, destination: str, context: Optional[Dict] = None) -> str:
        """
        Build user message with route request and context

        Args:
            origin: Starting station
            destination: Ending station
            context: Optional context with safety data, real-time trains, and delays

        Returns:
            Formatted user message
        """
        message = f"""Route request:
- Origin: {origin}
- Destination: {destination}"""

        if context:
            # Real-time train data (Phase 1 - live MTA feeds)
            if 'real_time_data' in context:
                message += f"\n\nREAL-TIME TRAIN DATA (Live MTA GTFS-RT):"
                real_time = context['real_time_data']

                if origin in real_time and real_time[origin].get('arrivals'):
                    message += f"\n\n{origin} - Next Arrivals:"
                    for arr in real_time[origin]['arrivals'][:3]:
                        delay_info = ""
                        if arr.get('delay_seconds', 0) > 0:
                            delay_info = f" (DELAYED +{arr['delay_seconds']//60} min)"
                        message += f"\n  - Line {arr['line']} to {arr['destination']}: {arr['eta_minutes']} min{delay_info}"

                if destination in real_time and real_time[destination].get('arrivals'):
                    message += f"\n\n{destination} - Next Arrivals:"
                    for arr in real_time[destination]['arrivals'][:3]:
                        delay_info = ""
                        if arr.get('delay_seconds', 0) > 0:
                            delay_info = f" (DELAYED +{arr['delay_seconds']//60} min)"
                        message += f"\n  - Line {arr['line']} to {arr['destination']}: {arr['eta_minutes']} min{delay_info}"

            # Safety/crime data
            if 'crime_incidents' in context:
                message += f"\n\nCRIME & SAFETY DATA (Last 7 days):"
                for station, count in context['crime_incidents'].items():
                    safety_score = context.get('safety_scores', {}).get(station, 5.0)
                    message += f"\n  - {station}: {count} incidents, Safety Score: {safety_score:.1f}/10"

            # Walking distances
            if 'walking_distances' in context:
                message += f"\n\nWALKING DISTANCES FROM ADDRESSES:"
                message += f"\n  - Origin: {context['walking_distances'].get('origin_km', 0):.2f} km walk"
                message += f"\n  - Destination: {context['walking_distances'].get('destination_km', 0):.2f} km walk"

            # Legacy context support
            if 'delays' in context:
                message += f"\n\nService Status:"
                for line, delay_mins in context['delays'].items():
                    if delay_mins > 0:
                        message += f"\n  - Line {line}: +{delay_mins} minutes delay"
                    else:
                        message += f"\n  - Line {line}: Normal"

        message += "\n\nImportant: Factor in REAL-TIME train delays and arrivals when recommending routes. Prefer routes with shorter wait times."
        message += "\n\nRecommend 3 routes in the JSON format specified."
        return message

    def get_route_recommendations(
        self,
        origin: str,
        destination: str,
        context: Optional[Dict] = None
    ) -> Dict:
        """
        Get route recommendations from Bedrock Claude

        Args:
            origin: Starting station
            destination: Ending station
            context: Optional safety/delay data

        Returns:
            Dictionary with routes array
        """
        logger.info(f"🚀 Getting recommendations: {origin} → {destination}")

        start_time = time.time()

        # Build prompts
        system_prompt = self.build_system_prompt()
        user_message = self.build_user_message(origin, destination, context)

        # Invoke Bedrock
        response_text = self.invoke_bedrock(system_prompt, user_message)

        latency_ms = (time.time() - start_time) * 1000

        logger.info(f"⏱️  Latency: {latency_ms:.0f}ms")
        logger.info(f"Response preview: {response_text[:200]}...")

        # Parse JSON response - Claude may wrap in markdown code blocks
        try:
            json_text = response_text.strip()

            # Extract JSON if wrapped in markdown code blocks
            if '```json' in json_text:
                json_text = json_text.split('```json')[1].split('```')[0].strip()
            elif '```' in json_text:
                json_text = json_text.split('```')[1].split('```')[0].strip()

            # Parse the JSON
            routes_data = json.loads(json_text)

            # Handle different response formats from Claude
            # Could be {"routes": [...]} or {"SafeRoute": {...}, "FastRoute": {...}, ...}
            if 'routes' in routes_data:
                routes = routes_data['routes']
            else:
                # Convert from {"SafeRoute": {...}, "FastRoute": {...}, ...} format
                routes = [
                    {"name": key, **value}
                    for key, value in routes_data.items()
                ]

            logger.info(f"✅ Successfully parsed {len(routes)} routes")

            return {
                "origin": origin,
                "destination": destination,
                "routes": routes,
                "latency_ms": latency_ms,
                "timestamp": datetime.now().isoformat()
            }

        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse Bedrock response as JSON: {e}")
            logger.error(f"Response preview: {response_text[:500]}")
            raise
        except Exception as e:
            logger.error(f"❌ Error processing response: {e}")
            logger.error(f"Response: {response_text}")
            raise


def main():
    """Test the Bedrock route recommender"""
    print("\n" + "="*70)
    print("🚀 SmartRoute Bedrock Integration Test")
    print("="*70)

    # Initialize recommender
    recommender = BedrockRouteRecommender()

    # Test case 1: Basic recommendation
    print("\n📍 Test 1: Grand Central → Times Square")
    print("-" * 70)

    try:
        result = recommender.get_route_recommendations(
            origin="Grand Central Terminal",
            destination="Times Square Station",
            context={
                "crime_incidents": {
                    "Grand Central": 5,
                    "Times Square": 8,
                    "Herald Square": 3,
                    "34th Street": 2
                },
                "delays": {
                    "1": 2,
                    "2": 0,
                    "3": 0,
                    "N": 3,
                    "Q": 0,
                    "R": 1,
                    "W": 0
                },
                "crowding": {
                    "Grand Central": "Very Crowded",
                    "Times Square": "Extremely Crowded",
                    "Herald Square": "Moderate"
                }
            }
        )

        print(f"\n✅ Routes received:")
        for route in result.get('routes', []):
            if isinstance(route, dict):
                print(f"\n  {route.get('name', 'Unknown Route')}")
                print(f"    Stations: {' → '.join(route.get('stations', [])[:3])}...")
                print(f"    Time: {route.get('estimated_time_minutes', '?')} min")
                print(f"    Safety: {route.get('safety_score', '?')}/10")
                print(f"    Reliability: {route.get('reliability_score', '?')}/10")
                print(f"    Efficiency: {route.get('efficiency_score', '?')}/10")

        print(f"\n⏱️  Latency: {result['latency_ms']:.0f}ms")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

    # Test case 2: Different route
    print("\n\n📍 Test 2: Jamaica Station → Coney Island")
    print("-" * 70)

    try:
        result = recommender.get_route_recommendations(
            origin="Jamaica Station",
            destination="Coney Island",
            context={
                "crime_incidents": {
                    "Jamaica Station": 12,
                    "Coney Island": 6,
                    "Brighton Beach": 4
                },
                "delays": {
                    "A": 5,
                    "F": 2,
                    "Z": 0,
                    "Q": 0,
                    "D": 1
                }
            }
        )

        print(f"\n✅ Routes received:")
        for route in result.get('routes', []):
            if isinstance(route, dict):
                print(f"\n  {route.get('name', 'Unknown Route')}")
                print(f"    Time: {route.get('estimated_time_minutes', '?')} min")
                print(f"    Explanation: {route.get('explanation', 'N/A')}")

        print(f"\n⏱️  Latency: {result['latency_ms']:.0f}ms")

    except Exception as e:
        print(f"❌ Test failed: {e}")

    print("\n" + "="*70)
    print("✅ Bedrock Integration Tests Complete")
    print("="*70)


if __name__ == "__main__":
    main()
