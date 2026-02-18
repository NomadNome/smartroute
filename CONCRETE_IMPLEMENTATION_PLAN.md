# SmartRoute: Concrete Implementation Plan
## Specific APIs, Code, and Resources

**Date:** November 24, 2025
**Approach:** Pragmatic. Only build what's needed. Focus on data fusion that creates real value.

---

# What You Need to Acquire

## 1. MTA GTFS Real-Time Feed
**What it is:** Live NYC subway train positions and delays
**Where to get it:** https://new.mta.info/developers
**Cost:** FREE
**What you need to do:**
1. Sign up at https://new.mta.info/developers
2. Request API key (instant)
3. You'll get access to:
   - `http://datamall.transitchicago.com/lapi/dl/produce?key=YOUR_KEY` (example format)
   - NYC version: https://api-endpoint.mta.info/Dataservice/v2/MTA_GTFS_Realtime
4. Two endpoints you need:
   - Trip Updates (actual train positions, delays): `TripUpdate.pb2` (protocol buffers format)
   - Alerts (service changes): `Alert.pb2`

**Action:** Sign up now, test the API with curl to verify you have access

---

## 2. Google Places API & Maps APIs
**What it is:** You already have Google Maps API key. We need to confirm these specific APIs are enabled:
**Cost:** You're already paying (or within free tier for current usage)
**Check these are enabled in Google Cloud Console:**
- ✅ **Places API** (for venue recommendations) - $7 per 1000 requests
- ✅ **Routes API** (walking directions) - $5 per 1000 requests
- ✅ **Street View API** (walking route previews) - $7 per 1000 static images
- ✅ **Elevation API** (stairs detection) - $5 per 1000 requests

**Existing from Google Cloud project:**
1. Go to: https://console.cloud.google.com/
2. Project: Find your SmartRoute project
3. APIs & Services → Enabled APIs
4. Search for each API above, enable if not already on
5. Verify you have API quotas set appropriately

**Action:** Check Google Cloud console and verify these APIs are enabled. Screenshot confirmations.

---

## 3. Weather API
**You already have this** - verify which one:
- OpenWeatherMap: `https://openweathermap.org/`
- NOAA: `https://www.weather.gov/gis/` (free, US only)
- Or other?

**What we need:** Current conditions + 1-hour forecast
- Temperature, precipitation, wind, alerts

**Action:** Confirm which weather API you're using. Get/verify API key.

---

## 4. Cloud Resources (AWS - you already have these)
**DynamoDB Tables we'll create:**
1. `mta_realtime_state` - Stores current train positions and delays
   - PK: `line_id` (A, C, 1, 2, 3, 4, 5, etc.)
   - SK: `timestamp`
   - TTL: 5 minutes
   - Size: ~1 MB per minute (10 lines × 100 bytes avg per update)

2. `realtime_anomalies` - Unusual delays detected
   - PK: `anomaly_id`
   - SK: `timestamp`
   - TTL: 2 hours
   - Size: ~50 KB per hour (small)

3. `route_context_cache` - Cache context to avoid recomputation
   - PK: `route_hash` (MD5 of origin+destination)
   - SK: `timestamp`
   - TTL: 10 minutes
   - Size: ~100 KB

**Lambda Functions we'll create:**
1. `mta_gtfs_poller` - Polls MTA every 30 seconds
2. `weather_poller` - Polls weather every 5 minutes
3. `anomaly_detector` - Runs every 1 minute, compares current vs baseline
4. `context_enricher` - Called by recommend endpoint, adds real-time context
5. `explain_generator` - Called by context_enricher, generates natural language

**EventBridge Rules:**
- `mta_gtfs_trigger` - Triggers mta_gtfs_poller every 30 seconds
- `weather_trigger` - Triggers weather_poller every 5 minutes
- `anomaly_trigger` - Triggers anomaly_detector every 1 minute

**Estimated AWS Cost Increase:**
- DynamoDB reads/writes: ~$20/month
- Lambda invocations: ~$5/month
- Data storage: ~$2/month
- **Total: ~$30/month additional**

---

# What I (Claude Code) Will Build

## Phase 1: Real-Time Data Foundation (Week 1)

### 1.1 MTA GTFS Real-Time Poller
**File:** `mta_gtfs_poller.py` (~150 lines)

**What it does:**
```
Every 30 seconds:
1. Fetch MTA GTFS Real-Time TripUpdate data
2. Parse protocol buffers (using protobuf3 library)
3. Extract for each line:
   - Current train position (latitude, longitude)
   - Current delay (minutes behind schedule)
   - Next 3 stations
   - Occupancy (if available)
4. Compare vs last known state
5. If delay > 1.5x normal for this time, flag as "anomaly"
6. Store in mta_realtime_state DynamoDB table
7. Publish change event to EventBridge
```

**Code structure:**
```python
import urllib.request
import json
from google.protobuf import message
from datetime import datetime
import boto3

class MTAGTFSPoller:
    def __init__(self, api_key):
        self.api_key = api_key
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table('mta_realtime_state')

    def fetch_realtime_data(self):
        """Fetch MTA GTFS Real-Time trip updates"""
        url = f"https://api-endpoint.mta.info/Dataservice/v2/MTA_GTFS_Realtime?key={self.api_key}&feed_id=1"
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read()

    def parse_trip_updates(self, data):
        """Parse protocol buffer into usable format"""
        # Parse MTA feed (protobuf format)
        # Extract: line_id, current_delay, train_position
        # Return: dict of {line_id: {delay, position, timestamp}}

    def compare_to_baseline(self, current_state, baseline):
        """Compare current delays to historical baseline"""
        # baseline = "what is normal for this line at this time?"
        # current = actual delay now
        # Flag if current > 1.5x baseline

    def store_state(self, state):
        """Store in DynamoDB"""
        self.table.put_item(Item={
            'line_id': state['line_id'],
            'timestamp': state['timestamp'],
            'delay_minutes': state['delay_minutes'],
            'train_position': state['position'],
            'is_anomaly': state['is_anomaly']
        })

    def poll(self):
        """Main entry point"""
        data = self.fetch_realtime_data()
        state = self.parse_trip_updates(data)

        for line_id, line_state in state.items():
            baseline = self.get_baseline(line_id)
            line_state['is_anomaly'] = self.compare_to_baseline(
                line_state['delay_minutes'],
                baseline
            )
            self.store_state(line_state)

        return state
```

**What you need to provide:**
- MTA API key (from sign-up above)

**Testing:**
```bash
# Manual test: Call Lambda manually with test event
# Verify: Check DynamoDB table for new records
# Verify: Records have accurate delay data vs. actual MTA app
```

---

### 1.2 Weather Data Poller
**File:** `weather_poller.py` (~80 lines)

**What it does:**
```
Every 5 minutes:
1. Fetch current weather + 1-hour forecast
2. Extract: temperature, precipitation, wind, alerts
3. Store in DynamoDB (weather_state table)
4. Publish event if severe weather alert detected
```

**Code structure:**
```python
import urllib.request
import json
import boto3
from datetime import datetime

class WeatherPoller:
    def __init__(self, api_key, location="40.7128,-74.0060"):  # NYC coordinates
        self.api_key = api_key
        self.location = location
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table('weather_state')

    def fetch_weather(self):
        """Fetch from OpenWeatherMap or NOAA"""
        # Using OpenWeatherMap example:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat=40.7128&lon=-74.0060&appid={self.api_key}"
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())

    def parse_weather(self, data):
        """Extract relevant fields"""
        return {
            'temperature': data['main']['temp'],
            'precipitation': data.get('rain', {}).get('1h', 0),
            'wind_speed': data['wind']['speed'],
            'conditions': data['weather'][0]['main'],
            'alert': data.get('alerts', None)
        }

    def store_weather(self, weather):
        """Store in DynamoDB"""
        self.table.put_item(Item={
            'location': 'new_york_city',
            'timestamp': datetime.now().isoformat(),
            'temperature': weather['temperature'],
            'precipitation': weather['precipitation'],
            'wind_speed': weather['wind_speed'],
            'conditions': weather['conditions'],
            'has_alert': bool(weather['alert'])
        })

    def poll(self):
        data = self.fetch_weather()
        weather = self.parse_weather(data)
        self.store_weather(weather)
        return weather
```

**What you need to provide:**
- Weather API key (OpenWeatherMap or verify existing provider)

---

### 1.3 Lambda Handler for Pollers
**File:** `lambda_poller_handler.py` (~50 lines)

**What it does:**
- Entry point for EventBridge triggers
- Calls MTAGTFSPoller and WeatherPoller
- Handles errors gracefully

```python
import json
from mta_gtfs_poller import MTAGTFSPoller
from weather_poller import WeatherPoller
import os

mta_poller = None
weather_poller = None

def init_pollers():
    global mta_poller, weather_poller
    mta_poller = MTAGTFSPoller(api_key=os.getenv('MTA_API_KEY'))
    weather_poller = WeatherPoller(api_key=os.getenv('WEATHER_API_KEY'))

def lambda_handler(event, context):
    """
    Triggered by EventBridge every 30 sec (MTA) or 5 min (weather)
    """
    if not mta_poller:
        init_pollers()

    poller_type = event.get('source', 'mta')

    try:
        if 'mta' in poller_type:
            result = mta_poller.poll()
            return {'statusCode': 200, 'body': json.dumps(result)}
        elif 'weather' in poller_type:
            result = weather_poller.poll()
            return {'statusCode': 200, 'body': json.dumps(result)}
    except Exception as e:
        print(f"Error: {e}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
```

---

### 1.4 Baseline Historical Data
**File:** `historical_baselines.py` (~100 lines)

**What it does:**
- Provides "what is normal for this line at this time?"
- Queries DynamoDB to compute rolling averages
- Caches results (updated every hour)

```python
from datetime import datetime, timedelta
import boto3
from collections import defaultdict

class HistoricalBaselines:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.mta_table = self.dynamodb.Table('mta_realtime_state')
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour

    def get_baseline_for_line_and_time(self, line_id, hour_of_day, day_of_week):
        """
        Returns: {
            'normal_delay_minutes': 1.5,
            'p90_delay_minutes': 4.2,
            'p95_delay_minutes': 6.8
        }
        """
        # Query last 30 days of data for this line+time+day
        # Compute: mean, p90, p95 of delays
        # Return as percentile bands

        # INITIAL: Hardcoded defaults until we have 30 days of data
        defaults = {
            'normal_delay_minutes': 2.0,  # Most lines are 1-2 min late on average
            'p90_delay_minutes': 5.0,     # 90th percentile is ~5 min
            'p95_delay_minutes': 8.0      # 95th percentile is ~8 min
        }
        return defaults
```

**Note:** For now, use hardcoded baselines. After 30 days of data collection, query actual historical data.

---

## Phase 1 Deliverable
After Week 1, you'll have:
- ✅ Real-time MTA delays in DynamoDB
- ✅ Real-time weather in DynamoDB
- ✅ Ability to detect "unusual" delays (anomalies)
- ✅ Foundation to enrich routes with context

**Test it:** MTA data updated every 30 sec. Weather every 5 min. Visible in DynamoDB.

---

## Phase 2: Context Enrichment (Week 2)

### 2.1 Context Enricher Module
**File:** `context_enricher.py` (~200 lines)

**What it does:**
Called during route recommendation. Adds real-time context to each route.

```
Input: route (from Dijkstra), origin, destination, current_time
Process:
  1. Fetch current MTA state
  2. Fetch current weather
  3. For each LINE in route:
     - What's the current delay on this line?
     - Is this line experiencing anomaly?
     - How will weather affect this line's walking route?
  4. Compute: expected_time_range (min/likely/max)
  5. Return: enhanced route with context
Output: route + context object
```

**Code structure:**
```python
import boto3
from datetime import datetime
from mta_gtfs_poller import HistoricalBaselines

class ContextEnricher:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.mta_table = self.dynamodb.Table('mta_realtime_state')
        self.weather_table = self.dynamodb.Table('weather_state')
        self.anomaly_table = self.dynamodb.Table('realtime_anomalies')
        self.baselines = HistoricalBaselines()

    def get_current_mta_state(self):
        """Fetch latest MTA state from DynamoDB"""
        # Query: Get most recent item (by timestamp) for each line
        # Return: {line_id: {delay_minutes, is_anomaly, timestamp}}

    def get_current_weather(self):
        """Fetch latest weather from DynamoDB"""
        # Query: Get most recent weather record
        # Return: {temperature, precipitation, conditions, alert}

    def get_active_anomalies(self):
        """Fetch anomalies that occurred in last 30 minutes"""
        # Query: anomaly_table where timestamp > now - 30 min
        # Return: list of {line_id, type, severity, explanation}

    def compute_expected_time_range(self, route, mta_state):
        """
        Compute: min/likely/max time for this route

        route.total_time_minutes = 23 (normal condition)

        For each line in route:
          current_delay = mta_state[line].delay_minutes
          if current_delay > baseline:
            impact = current_delay - baseline
            add to total_time_minutes

        Return: {
            'min': 20,           # best case
            'likely': 25,        # most probable
            'max': 31,           # worst case
            'confidence': 0.92   # how confident we are
        }
        """

    def enrich_route(self, route, origin, destination, current_time):
        """Main entry point"""
        mta_state = self.get_current_mta_state()
        weather = self.get_current_weather()
        anomalies = self.get_active_anomalies()

        # Compute expected time range
        time_range = self.compute_expected_time_range(route, mta_state)

        # Identify which anomalies affect this route
        affected_anomalies = [
            a for a in anomalies
            if a['line_id'] in route['lines']
        ]

        # Weather impact on walking routes
        weather_impact = self.assess_weather_impact(route, weather)

        # Return enriched route
        return {
            **route,
            'context': {
                'expected_time_range': time_range,
                'current_mta_delays': mta_state,
                'weather': weather,
                'affected_anomalies': affected_anomalies,
                'weather_impact': weather_impact,
                'generated_at': datetime.now().isoformat()
            }
        }

    def assess_weather_impact(self, route, weather):
        """
        Determine if weather affects this route

        return: {
            'has_impact': True/False,
            'type': 'rain', 'heat', 'wind', etc,
            'severity': 'low', 'medium', 'high',
            'walking_route_recommendation': 'covered_route', 'normal', etc
        }
        """
```

---

### 2.2 Update lambda_function.py
**File:** `lambda_function.py` (modify existing)

**Changes:**
```python
from context_enricher import ContextEnricher

context_enricher = ContextEnricher()

def recommend_handler(event, context):
    """Enhanced with real-time context"""

    origin = event.get('origin')
    destination = event.get('destination')

    # EXISTING: Get routes from Dijkstra
    routes = dijkstra_router.find_routes(origin, destination)
    routes = route_optimizer.score_routes(routes)

    # NEW: Enrich with real-time context
    enriched_routes = []
    for route in routes:
        enriched = context_enricher.enrich_route(
            route=route,
            origin=origin,
            destination=destination,
            current_time=datetime.now()
        )
        enriched_routes.append(enriched)

    return success_response({
        'routes': enriched_routes,
        'generated_at': datetime.now().isoformat()
    })
```

---

### 2.3 Response Format Change
**Frontend will receive:**

```json
{
  "routes": [
    {
      "name": "Safe Route",
      "stations": [...],
      "lines": ["A", "4"],
      "total_time_minutes": 23,

      "context": {
        "expected_time_range": {
          "min": 20,
          "likely": 25,
          "max": 31,
          "confidence": 0.92
        },
        "current_mta_delays": {
          "A": {"delay_minutes": 2, "is_anomaly": false},
          "4": {"delay_minutes": 1, "is_anomaly": false}
        },
        "weather": {
          "temperature": 62,
          "precipitation": 0.2,
          "conditions": "light_rain"
        },
        "affected_anomalies": [],
        "weather_impact": {
          "has_impact": true,
          "type": "rain",
          "walking_route_recommendation": "covered_preferred"
        }
      }
    }
  ]
}
```

---

## Phase 2 Deliverable
After Week 2, you'll have:
- ✅ Routes enriched with real-time delays
- ✅ Expected time range (min/likely/max)
- ✅ Weather impact on routes
- ✅ Foundation for explanations

**Test it:** Route recommendations now show confidence intervals + weather impact

---

## Phase 3: Explanation Generation (Week 3)

### 3.1 Explanation Generator
**File:** `explanation_generator.py` (~150 lines)

**What it does:**
Uses Bedrock Claude to generate natural language explanations for route context.

```python
import boto3
import json

class ExplanationGenerator:
    def __init__(self):
        self.bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

    def generate_route_explanation(self, route, context):
        """
        Input: route + context
        Output: Natural language explanation

        Example output:
        "Your usual route, but A line has unexpected delays today.
         Still your best choice given time constraints. Expect 25 ± 4 minutes."
        """

        prompt = f"""
Given this route data, provide a brief (1-2 sentence) explanation of why this route is recommended.

Route: {route['name']}
Lines: {', '.join(route['lines'])}
Normal time: {route['total_time_minutes']} min
Expected time range: {context['expected_time_range']['likely']} ± {context['expected_time_range']['likely'] - context['expected_time_range']['min']} min
Current delays: {context['current_mta_delays']}
Weather: {context['weather']['conditions']}
Anomalies: {context['affected_anomalies']}

Explain briefly why someone should take this route today.
"""

        response = self.bedrock.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20241022',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-06-01',
                'max_tokens': 100,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            })
        )

        result = json.loads(response['body'].read())
        return result['content'][0]['text']

    def generate_anomaly_alert(self, anomaly, context):
        """
        Generate alert message for anomalies

        Example output:
        "A line has unexpected 5-min delay. Likely signal problem.
         Consider B line (2 min longer but no delays)."
        """

        prompt = f"""
Generate a brief (1 sentence) alert message about this transit anomaly.

Anomaly: {anomaly['type']} on line {anomaly['line_id']}
Severity: {anomaly['severity']}
Detected: {anomaly['timestamp']}
Current delay: {context['current_mta_delays'].get(anomaly['line_id'], {}).get('delay_minutes', 'unknown')} minutes

Suggest what the user should do.
"""

        # Similar invoke_model call
```

---

### 3.2 Update Context Enricher
**File:** `context_enricher.py` (modify)

```python
from explanation_generator import ExplanationGenerator

class ContextEnricher:
    def __init__(self):
        # ... existing init ...
        self.explanation_generator = ExplanationGenerator()

    def enrich_route(self, route, origin, destination, current_time):
        # ... existing enrichment ...

        # NEW: Generate explanation
        explanation = self.explanation_generator.generate_route_explanation(
            route=route,
            context=enriched['context']
        )
        enriched['explanation'] = explanation

        return enriched
```

---

## Phase 3 Deliverable
After Week 3, you'll have:
- ✅ Routes enriched with real-time data
- ✅ Natural language explanations for each route
- ✅ Alerts for anomalies (also natural language)

**Test it:** Route cards now have explanations like: "Your usual route, but A line delayed today. Still best choice. Expect 25 ± 4 min."

---

## Phase 4: Anomaly Detection (Week 4)

### 4.1 Anomaly Detector
**File:** `anomaly_detector.py` (~150 lines)

**What it does:**
Runs every minute. Detects when something unusual is happening on a line.

```python
import boto3
from datetime import datetime, timedelta
from historical_baselines import HistoricalBaselines

class AnomalyDetector:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.mta_table = self.dynamodb.Table('mta_realtime_state')
        self.anomaly_table = self.dynamodb.Table('realtime_anomalies')
        self.baselines = HistoricalBaselines()

    def get_current_state(self):
        """Get most recent MTA state for all lines"""
        # Query mta_realtime_state, get latest timestamp
        # Return: {line_id: {delay_minutes, position, timestamp}}

    def detect_anomalies(self):
        """
        Compare current state to baseline.
        Flag as anomaly if:
          - delay > 2.0x baseline, OR
          - delay > 8 minutes (absolute threshold)
        """
        current = self.get_current_state()
        anomalies = []

        for line_id, state in current.items():
            hour = datetime.now().hour
            day = datetime.now().weekday()
            baseline = self.baselines.get_baseline_for_line_and_time(
                line_id, hour, day
            )

            if state['delay_minutes'] > baseline['normal_delay_minutes'] * 2.0:
                anomaly = {
                    'line_id': line_id,
                    'type': 'service_delay',
                    'current_delay': state['delay_minutes'],
                    'baseline_delay': baseline['normal_delay_minutes'],
                    'severity': 'high' if state['delay_minutes'] > 8 else 'medium',
                    'timestamp': datetime.now().isoformat(),
                    'detected_at': datetime.now().isoformat()
                }
                anomalies.append(anomaly)

        return anomalies

    def store_anomalies(self, anomalies):
        """Store in DynamoDB"""
        for anomaly in anomalies:
            self.anomaly_table.put_item(Item=anomaly)

    def detect(self):
        """Main entry point"""
        anomalies = self.detect_anomalies()
        if anomalies:
            self.store_anomalies(anomalies)
            print(f"Detected {len(anomalies)} anomalies")
        return anomalies
```

---

### 4.2 Lambda Handler for Anomaly Detector
**File:** `lambda_anomaly_handler.py` (~30 lines)

```python
from anomaly_detector import AnomalyDetector
import json

detector = AnomalyDetector()

def lambda_handler(event, context):
    """Triggered by EventBridge every minute"""
    anomalies = detector.detect()
    return {
        'statusCode': 200,
        'body': json.dumps({
            'anomalies_detected': len(anomalies),
            'anomalies': anomalies
        })
    }
```

---

## Phase 4 Deliverable
After Week 4, you'll have:
- ✅ Real-time anomaly detection
- ✅ Natural language explanations for context
- ✅ Complete data fusion: MTA + Weather + Baselines → Route Recommendations

**Test it:** When there's a real MTA delay, you'll see it in route explanations within 1-2 minutes.

---

# AWS Infrastructure You Need to Set Up

## CloudFormation / SAM Template Updates

```yaml
# Add these to your SAM template.yaml

Resources:
  MTARealtimeStateTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: mta_realtime_state
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: line_id
          AttributeType: S
        - AttributeName: timestamp
          AttributeType: S
      KeySchema:
        - AttributeName: line_id
          KeyType: HASH
        - AttributeName: timestamp
          KeyType: RANGE
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true

  RealtimeAnomaliesTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: realtime_anomalies
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: anomaly_id
          AttributeType: S
        - AttributeName: timestamp
          AttributeType: S
      KeySchema:
        - AttributeName: anomaly_id
          KeyType: HASH
        - AttributeName: timestamp
          KeyType: RANGE
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true

  WeatherStateTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: weather_state
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: location
          AttributeType: S
        - AttributeName: timestamp
          AttributeType: S
      KeySchema:
        - AttributeName: location
          KeyType: HASH
        - AttributeName: timestamp
          KeyType: RANGE
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true

  MTAPollerFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: mta_gtfs_poller
      CodeUri: lambdas/pollers/mta_poller/
      Handler: lambda_poller_handler.lambda_handler
      Runtime: python3.11
      Timeout: 30
      Environment:
        Variables:
          MTA_API_KEY: !Ref MTAAPIKey
          DYNAMODB_TABLE: mta_realtime_state
      Policies:
        - DynamoDBCrudPolicy:
            TableName: mta_realtime_state

  WeatherPollerFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: weather_poller
      CodeUri: lambdas/pollers/weather_poller/
      Handler: lambda_poller_handler.lambda_handler
      Runtime: python3.11
      Timeout: 15
      Environment:
        Variables:
          WEATHER_API_KEY: !Ref WeatherAPIKey
          DYNAMODB_TABLE: weather_state
      Policies:
        - DynamoDBCrudPolicy:
            TableName: weather_state

  AnomalyDetectorFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: anomaly_detector
      CodeUri: lambdas/detectors/anomaly_detector/
      Handler: lambda_anomaly_handler.lambda_handler
      Runtime: python3.11
      Timeout: 30
      Policies:
        - DynamoDBCrudPolicy:
            TableName: mta_realtime_state
        - DynamoDBCrudPolicy:
            TableName: realtime_anomalies

  MTAPollerSchedule:
    Type: AWS::Events::Rule
    Properties:
      ScheduleExpression: rate(30 seconds)
      State: ENABLED
      Targets:
        - Arn: !GetAtt MTAPollerFunction.Arn
          RoleArn: !GetAtt EventBridgeRole.Arn

  WeatherPollerSchedule:
    Type: AWS::Events::Rule
    Properties:
      ScheduleExpression: rate(5 minutes)
      State: ENABLED
      Targets:
        - Arn: !GetAtt WeatherPollerFunction.Arn
          RoleArn: !GetAtt EventBridgeRole.Arn

  AnomalyDetectorSchedule:
    Type: AWS::Events::Rule
    Properties:
      ScheduleExpression: rate(1 minute)
      State: ENABLED
      Targets:
        - Arn: !GetAtt AnomalyDetectorFunction.Arn
          RoleArn: !GetAtt EventBridgeRole.Arn
```

---

# Timeline & Effort

| Phase | What | Effort | Days | Code Files |
|-------|------|--------|------|-----------|
| 1 | MTA + Weather polling + anomaly detection | Medium | 5 | mta_gtfs_poller.py, weather_poller.py, historical_baselines.py, lambda_poller_handler.py |
| 2 | Context enrichment | Medium | 3 | context_enricher.py (update lambda_function.py) |
| 3 | Explanation generation | Low | 2 | explanation_generator.py (update context_enricher.py) |
| 4 | Anomaly detection logic | Low | 2 | anomaly_detector.py, lambda_anomaly_handler.py |
| | **Testing & Deployment** | Medium | 3 | SAM template updates, testing |
| | **TOTAL** | | **15 days (3 weeks)** | |

---

# What You Need to Do

## Before Week 1 Starts
1. **Sign up for MTA API:**
   - Go to https://new.mta.info/developers
   - Request API key
   - Confirm you can hit the endpoint (test with curl)
   - Provide me: MTA_API_KEY

2. **Verify Google Cloud APIs:**
   - Go to https://console.cloud.google.com/
   - Project: SmartRoute
   - APIs & Services → Enabled APIs
   - Confirm these are enabled:
     - Places API
     - Routes API
     - Street View API
   - Verify you have quota for ~100 req/day each

3. **Verify Weather API:**
   - Confirm which provider (OpenWeatherMap? NOAA?)
   - Get/verify API key
   - Test it (curl to verify it works)
   - Provide me: WEATHER_API_KEY

4. **AWS Permissions:**
   - Verify your AWS account has access to:
     - DynamoDB (create tables)
     - Lambda (create functions)
     - EventBridge (create schedules)
     - IAM (create roles)

## During Development (My Work)
- Write all code files above
- Deploy Lambda functions
- Test data ingestion
- Validate anomaly detection
- Package and deploy

## After Each Phase (Your Work)
- Verify data is flowing (check DynamoDB)
- Test against real conditions (manual MTA checks)
- Provide feedback on explanations/context

---

# Success Criteria

**Week 1 End:**
- [ ] MTA data flows to DynamoDB every 30 seconds
- [ ] Weather data flows to DynamoDB every 5 minutes
- [ ] You can query DynamoDB and see real train delays
- [ ] Anomaly detection identifies delays > 2x baseline

**Week 2 End:**
- [ ] Routes now include `context` object in response
- [ ] Time range shows min/likely/max with confidence
- [ ] Weather impact visible
- [ ] API response time still < 1 second

**Week 3 End:**
- [ ] Each route has natural language explanation
- [ ] Explanation mentions current delays or weather if relevant
- [ ] Explanation is 1-2 sentences (not too verbose)

**Week 4 End:**
- [ ] When real MTA delay happens, user sees it in explanation within 2 minutes
- [ ] Anomalies detected and explained
- [ ] Complete data fusion working end-to-end

---

# What This Gets You

After 3 weeks:
- **Real-time contextual routing** - Not generic "23 min," but "25 ± 4 min with explanation"
- **Data fusion in action** - MTA + Weather + Historical = smart decisions
- **Unique competitive advantage** - No other routing app explains delays this way
- **Foundation for future** - Can layer on personalization, predictions, etc.

---

# Questions For You

1. **MTA API:** Can you sign up and get the key by tomorrow?
2. **Weather:** Which provider do you use? Can you share the API key?
3. **Timeline:** 3 weeks—is this realistic for your goals?
4. **Google APIs:** Should I also add walking route context using Street View + Routes API in a future phase?

---

**Ready to start Week 1 once you have MTA + Weather API keys.**
