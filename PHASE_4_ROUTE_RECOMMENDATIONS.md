# SmartRoute Phase 4: Route Recommendation Engine with Claude Haiku 4.5

## 🎯 Overview

Build an intelligent route recommendation system that combines real-time MTA data, safety intelligence, and Claude Haiku 4.5 to suggest optimal transit routes. Users get three options:
- **SafeRoute**: Prioritize low crime + reliable transit
- **FastRoute**: Minimize delays, ignore safety
- **BalancedRoute**: Hybrid scoring

---

## 📐 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       User Frontend (Next.js)                   │
│                   (React components + TailwindCSS)              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ↓
          ┌──────────────────────────────┐
          │   API Gateway (REST)         │
          │   /routes/recommend          │
          │   POST {origin, destination} │
          └──────────────┬───────────────┘
                         │
                         ↓
          ┌──────────────────────────────────────┐
          │  Lambda: Route Orchestrator          │
          │  ├─ Query Athena for real-time data │
          │  ├─ Check DynamoDB cache            │
          │  ├─ Call Bedrock Claude Haiku 4.5   │
          │  └─ Return 3 route options          │
          └──────────────┬─────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ↓              ↓              ↓
      ┌────────┐    ┌────────┐    ┌─────────┐
      │ Athena │    │   MTA  │    │ DynamoDB│
      │ Crime/ │    │ Phase 1│    │ Cache   │
      │ Safety │    │ Delays │    │         │
      └────────┘    └────────┘    └─────────┘
          │              │              │
          └──────────────┼──────────────┘
                         │
                         ↓
          ┌──────────────────────────────────────┐
          │  AWS Bedrock: Claude Haiku 4.5       │
          │  ├─ Route scoring algorithm          │
          │  ├─ Natural language explanations    │
          │  └─ Real-time decision making        │
          └──────────────┬─────────────────────┘
                         │
                         ↓
          ┌──────────────────────────────────────┐
          │  Response to Frontend                │
          │  {                                   │
          │    routes: [                         │
          │      {name: "SafeRoute",             │
          │       stations: [...],               │
          │       explanation: "...",            │
          │       safetyScore: 9.2,              │
          │       reliabilityScore: 8.5,         │
          │       estimatedTime: 45}             │
          │    ]                                 │
          │  }                                   │
          └──────────────────────────────────────┘
```

---

## 🤖 Bedrock Claude Haiku 4.5 Integration

### Model Details
- **Model ID**: `anthropic.claude-3-5-haiku-20241022` (or latest)
- **Input Cost**: $0.80 per 1M tokens
- **Output Cost**: $0.40 per 1M output tokens
- **Latency**: ~200-500ms (very fast)
- **Context Window**: 200K tokens (plenty for routes + context)

### Prompt Engineering Strategy

#### System Prompt (Fixed)
```
You are SmartRoute, an intelligent NYC subway route recommendation system.
Your job is to recommend the BEST route from origin to destination considering:

1. SAFETY: Lower crime incidents near stations = safer
2. RELIABILITY: Higher on-time performance = more reliable
3. EFFICIENCY: Fewer transfers and less wait time = faster
4. BALANCE: Consider all factors for best overall experience

Always provide exactly THREE route options:
1. SafeRoute - Prioritizes safety (low crime, reliable lines)
2. FastRoute - Prioritizes speed (direct, fewer stops)
3. BalancedRoute - Best overall experience (compromise of all factors)

For each route, provide:
- List of stations in order
- Estimated travel time
- Why this route is best for this criteria
- Safety score (0-10)
- Reliability score (0-10)
- Efficiency score (0-10)

Be concise but helpful. NYC riders appreciate direct advice.
```

#### Context Injection (Dynamic)
```
REAL-TIME DATA:
- Current time: {current_time}
- Line 1 Status: {on_time_pct}% on time, avg delay {avg_delay}min
- Line 2 Status: {on_time_pct}% on time, avg delay {avg_delay}min
[... all subway lines ...]

SAFETY DATA (last 7 days):
- Grand Central: 3 incidents, Safety Score 7.2/10
- Times Square: 8 incidents, Safety Score 5.8/10
[... top crime stations ...]

ROUTE OPTIONS FROM {ORIGIN} TO {DESTINATION}:
Route A: {station1} → {station2} → {station3}
Route B: {station1} → {station4} → {station5}
Route C: {station1} → {station2} → {station4}

Recommend the best option for each criteria (Safe/Fast/Balanced).
```

---

## 💻 Lambda Function: Route Orchestrator

### File: `lambdas/bedrock-router/lambda_function.py`

```python
import json
import boto3
import os
from datetime import datetime
from typing import Dict, List

athena = boto3.client('athena')
bedrock_runtime = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')
cache_table = dynamodb.Table('smartroute_route_cache')

# Constants
BEDROCK_MODEL = "anthropic.claude-3-5-haiku-20241022"
CACHE_TTL = 300  # 5 minutes for route recommendations

def lambda_handler(event, context):
    """
    Main handler for route recommendation requests

    Expected event:
    {
        "origin": "Grand Central",
        "destination": "Times Square",
        "criterion": "balanced"  # safe, fast, or balanced
    }
    """
    try:
        origin = event.get('origin')
        destination = event.get('destination')
        criterion = event.get('criterion', 'balanced')

        # Validate inputs
        if not origin or not destination:
            return error_response(400, "Missing origin or destination")

        # Check cache first
        cache_key = f"{origin}-{destination}-{criterion}"
        cached = get_from_cache(cache_key)
        if cached:
            return success_response(cached, from_cache=True)

        # Fetch real-time data from Athena
        print(f"Fetching real-time data for {origin} -> {destination}")
        real_time_data = fetch_real_time_data()

        # Build context for Bedrock
        system_prompt = build_system_prompt()
        user_message = build_user_message(origin, destination, real_time_data)

        # Call Claude Haiku via Bedrock
        print(f"Calling Bedrock Claude Haiku 4.5...")
        bedrock_response = call_bedrock(system_prompt, user_message)

        # Parse response
        routes = parse_bedrock_response(bedrock_response)

        # Cache the result
        put_in_cache(cache_key, routes)

        return success_response(routes, from_cache=False)

    except Exception as e:
        print(f"Error: {str(e)}")
        return error_response(500, f"Internal error: {str(e)}")


def fetch_real_time_data() -> Dict:
    """
    Fetch real-time MTA and safety data from Athena
    Returns dict with current conditions
    """
    queries = {
        'delays': """
            SELECT route_id,
                   AVG(delay_seconds) as avg_delay,
                   COUNT(*) as vehicles
            FROM smartroute_analytics.vehicles
            WHERE year = {year} AND month = {month} AND day = {day}
                  AND hour = {hour}
            GROUP BY route_id
        """,
        'safety': """
            SELECT station_name,
                   total_crimes,
                   unique_categories,
                   safety_score
            FROM smartroute_data.current_safety_scores
            ORDER BY safety_score ASC
            LIMIT 20
        """,
        'crowding': """
            SELECT stop_id, route_id, vehicle_count, frequency
            FROM smartroute_analytics.crowding_metrics
            WHERE year = {year} AND month = {month} AND day = {day}
                  AND hour = {hour}
            ORDER BY vehicle_count DESC
            LIMIT 10
        """
    }

    # Execute queries (simplified - use Athena client in production)
    results = {}
    for query_name, query in queries.items():
        # In production: use Athena start_query_execution + get_query_results
        # For now, mock the data
        results[query_name] = mock_query_results(query_name)

    return results


def build_system_prompt() -> str:
    """System prompt defining Claude's role"""
    return """You are SmartRoute, an intelligent NYC subway route recommendation system.

Your role is to recommend the BEST route from origin to destination considering:

1. SAFETY: Lower crime incidents near stations = safer
2. RELIABILITY: Higher on-time performance (%) = more reliable
3. EFFICIENCY: Fewer transfers and less wait time = faster
4. BALANCE: Consider all factors for best overall experience

You MUST provide exactly THREE distinct route options:
1. **SafeRoute** - Prioritizes safety (low crime stations, reliable lines)
2. **FastRoute** - Prioritizes speed (direct routing, minimum stops)
3. **BalancedRoute** - Best overall experience (good balance of all factors)

For EACH route, provide in JSON format:
{
  "name": "SafeRoute|FastRoute|BalancedRoute",
  "stations": ["station1", "station2", "station3"],
  "lines": ["1", "2", "3"],
  "estimated_time_minutes": 45,
  "transfers": 2,
  "explanation": "Why this route is best for this criteria",
  "safety_score": 8.5,
  "reliability_score": 8.2,
  "efficiency_score": 7.1,
  "key_benefits": ["Safe neighborhoods", "Frequent service"]
}

Always return a JSON array with exactly 3 routes. Be concise but helpful."""


def build_user_message(origin: str, destination: str, real_time_data: Dict) -> str:
    """Build the user message with real-time context"""

    current_time = datetime.now()
    hour = current_time.hour

    # Format real-time data
    delays_info = format_delays(real_time_data['delays'], hour)
    safety_info = format_safety(real_time_data['safety'])
    crowding_info = format_crowding(real_time_data['crowding'])

    message = f"""
CURRENT TIME: {current_time.strftime('%H:%M')}

REAL-TIME LINE STATUS (Current Hour):
{delays_info}

SAFETY DATA (Last 7 Days - Highest Risk Stations):
{safety_info}

CROWDING DATA (Current Hour):
{crowding_info}

USER REQUEST:
Find the best route from {origin} to {destination}.

Recommend:
1. SafeRoute (best safety)
2. FastRoute (best speed)
3. BalancedRoute (best overall)

Return as JSON array with exactly 3 route objects.
"""

    return message


def call_bedrock(system_prompt: str, user_message: str) -> str:
    """Call Claude Haiku 4.5 via Bedrock"""

    response = bedrock_runtime.converse(
        modelId=BEDROCK_MODEL,
        messages=[
            {
                "role": "user",
                "content": user_message
            }
        ],
        system=system_prompt,
        inferenceConfig={
            "maxTokens": 1024,  # Enough for 3 routes
            "temperature": 0.7  # Slightly creative, not random
        }
    )

    # Extract text from response
    text_content = response['output']['message']['content'][0]['text']
    print(f"Bedrock response (first 200 chars): {text_content[:200]}")

    return text_content


def parse_bedrock_response(response_text: str) -> List[Dict]:
    """Parse Claude's JSON response into route objects"""

    try:
        # Extract JSON from response (Claude may add explanation text)
        import re
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)

        if not json_match:
            print("Warning: No JSON found in response")
            return fallback_routes()

        routes = json.loads(json_match.group())

        # Validate structure
        if not isinstance(routes, list) or len(routes) != 3:
            print(f"Warning: Expected 3 routes, got {len(routes)}")
            return fallback_routes()

        return routes

    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        return fallback_routes()


def fallback_routes() -> List[Dict]:
    """Fallback if Bedrock parsing fails"""
    return [
        {
            "name": "SafeRoute",
            "stations": ["Grand Central", "5th Ave", "42nd St"],
            "explanation": "Safest option using low-crime stations",
            "safety_score": 8.5,
            "reliability_score": 8.2,
            "efficiency_score": 7.1
        },
        {
            "name": "FastRoute",
            "stations": ["Grand Central", "Times Square"],
            "explanation": "Fastest direct route",
            "safety_score": 7.0,
            "reliability_score": 7.5,
            "efficiency_score": 9.2
        },
        {
            "name": "BalancedRoute",
            "stations": ["Grand Central", "42nd St", "Times Square"],
            "explanation": "Best balance of speed and safety",
            "safety_score": 8.0,
            "reliability_score": 8.1,
            "efficiency_score": 8.2
        }
    ]


def get_from_cache(key: str) -> Dict or None:
    """Get cached route from DynamoDB"""
    try:
        response = cache_table.get_item(Key={'route_key': key})
        if 'Item' in response:
            item = response['Item']
            # Check if expired
            if item.get('ttl', 0) > datetime.now().timestamp():
                return item.get('routes')
    except Exception as e:
        print(f"Cache read error: {e}")

    return None


def put_in_cache(key: str, routes: List[Dict]):
    """Cache route results in DynamoDB"""
    try:
        from datetime import datetime, timedelta
        ttl = int((datetime.now() + timedelta(seconds=CACHE_TTL)).timestamp())

        cache_table.put_item(
            Item={
                'route_key': key,
                'routes': routes,
                'ttl': ttl,
                'created_at': datetime.now().isoformat()
            }
        )
    except Exception as e:
        print(f"Cache write error: {e}")


def success_response(data: Dict or List, from_cache: bool = False):
    """Format successful response"""
    return {
        'statusCode': 200,
        'body': json.dumps({
            'success': True,
            'data': data,
            'from_cache': from_cache,
            'timestamp': datetime.now().isoformat()
        }),
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        }
    }


def error_response(status_code: int, message: str):
    """Format error response"""
    return {
        'statusCode': status_code,
        'body': json.dumps({
            'success': False,
            'error': message,
            'timestamp': datetime.now().isoformat()
        }),
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        }
    }


# Helper formatting functions
def format_delays(delays: Dict, hour: int) -> str:
    """Format delay data for context"""
    # Simplified - in production, query actual Athena data
    return """
Line 1: 5 min avg delay, 92% on-time
Line 2: 3 min avg delay, 95% on-time
Line 3: 8 min avg delay, 88% on-time
"""


def format_safety(safety: Dict) -> str:
    """Format safety data for context"""
    return """
Times Square: 12 incidents, Score 5.2/10 (AVOID)
Herald Square: 4 incidents, Score 8.1/10
Grand Central: 5 incidents, Score 7.8/10
5th Avenue: 2 incidents, Score 9.1/10 (SAFEST)
"""


def format_crowding(crowding: Dict) -> str:
    """Format crowding data for context"""
    return """
Herald Square: Heavy (95 vehicles)
Times Square: Heavy (102 vehicles)
34th Street: Moderate (45 vehicles)
"""


def mock_query_results(query_name: str) -> Dict:
    """Mock Athena results for testing"""
    mocks = {
        'delays': {},
        'safety': {},
        'crowding': {}
    }
    return mocks[query_name]
```

---

## 🔌 API Design

### Endpoint: POST `/api/routes/recommend`

#### Request
```json
{
  "origin": "Grand Central Terminal",
  "destination": "Times Square",
  "criterion": "balanced"  // "safe" | "fast" | "balanced"
}
```

#### Response
```json
{
  "success": true,
  "from_cache": false,
  "routes": [
    {
      "name": "SafeRoute",
      "stations": [
        "Grand Central",
        "5th Avenue",
        "42nd Street",
        "Times Square"
      ],
      "lines": ["4", "5", "6", "N", "Q", "R", "W"],
      "estimated_time_minutes": 18,
      "transfers": 1,
      "explanation": "This route prioritizes safety by avoiding high-crime areas. Grand Central and 42nd Street have excellent NYPD presence and lighting. The 5-6 line has 94% on-time reliability.",
      "safety_score": 8.7,
      "reliability_score": 8.9,
      "efficiency_score": 7.2,
      "key_benefits": [
        "Well-lit stations with security",
        "Frequent service (every 3-4 min)",
        "Crowd support if needed"
      ],
      "warnings": ["Slightly longer route"]
    },
    {
      "name": "FastRoute",
      "stations": [
        "Grand Central",
        "Times Square"
      ],
      "lines": ["S", "N", "Q", "R"],
      "estimated_time_minutes": 7,
      "transfers": 0,
      "explanation": "Direct shuttle service is fastest. Times Square station can be crowded but well-staffed with transit police.",
      "safety_score": 6.8,
      "reliability_score": 8.2,
      "efficiency_score": 9.8,
      "key_benefits": [
        "Direct line, no transfers",
        "Extremely quick (7 min)",
        "High frequency service"
      ],
      "warnings": ["Times Square is busy and crowded"]
    },
    {
      "name": "BalancedRoute",
      "stations": [
        "Grand Central",
        "34th Street",
        "Times Square"
      ],
      "lines": ["4", "5", "6", "1", "2", "3"],
      "estimated_time_minutes": 12,
      "transfers": 1,
      "explanation": "Best overall choice. 34th Street is safer than Times Square, with good lighting and frequent service. One quick transfer to reach destination.",
      "safety_score": 8.1,
      "reliability_score": 8.6,
      "efficiency_score": 8.4,
      "key_benefits": [
        "Good safety + speed balance",
        "Reliable lines with frequent service",
        "Average crowding"
      ],
      "warnings": []
    }
  ],
  "timestamp": "2025-11-01T15:30:45Z"
}
```

---

## 🎨 Frontend Integration

### React Component: `components/RouteRecommender.tsx`

```typescript
import React, { useState } from 'react';
import { MapPin, Clock, Shield, AlertCircle } from 'lucide-react';

interface Route {
  name: string;
  stations: string[];
  estimated_time_minutes: number;
  explanation: string;
  safety_score: number;
  reliability_score: number;
  efficiency_score: number;
  key_benefits: string[];
  warnings: string[];
}

interface RecommendationResponse {
  success: boolean;
  from_cache: boolean;
  routes: Route[];
  timestamp: string;
}

export function RouteRecommender() {
  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [loading, setLoading] = useState(false);
  const [recommendations, setRecommendations] = useState<Route[]>([]);
  const [error, setError] = useState('');

  const handleRecommend = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!origin || !destination) {
      setError('Please enter both origin and destination');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/routes/recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ origin, destination, criterion: 'balanced' })
      });

      const data: RecommendationResponse = await response.json();

      if (data.success) {
        setRecommendations(data.routes);
      } else {
        setError('Failed to get recommendations');
      }
    } catch (err) {
      setError('Error connecting to route service');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <form onSubmit={handleRecommend} className="mb-8">
        <div className="flex gap-4 mb-4">
          <input
            type="text"
            placeholder="From (e.g., Grand Central)"
            value={origin}
            onChange={(e) => setOrigin(e.target.value)}
            className="flex-1 px-4 py-2 border rounded-lg"
          />
          <input
            type="text"
            placeholder="To (e.g., Times Square)"
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
            className="flex-1 px-4 py-2 border rounded-lg"
          />
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Finding routes...' : 'Get Routes'}
          </button>
        </div>
        {error && <div className="text-red-600 text-sm">{error}</div>}
      </form>

      {recommendations.length > 0 && (
        <div className="grid gap-4">
          {recommendations.map((route) => (
            <RouteCard key={route.name} route={route} />
          ))}
        </div>
      )}
    </div>
  );
}

function RouteCard({ route }: { route: Route }) {
  return (
    <div className="border rounded-lg p-6 hover:shadow-lg transition">
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-xl font-bold text-blue-600">{route.name}</h3>
        <div className="text-3xl font-bold text-gray-700">
          {route.estimated_time_minutes}
          <span className="text-sm text-gray-500"> min</span>
        </div>
      </div>

      {/* Stations */}
      <div className="flex items-center gap-2 mb-4">
        <MapPin className="w-5 h-5 text-gray-400" />
        <div className="flex gap-2 flex-wrap">
          {route.stations.map((station, i) => (
            <React.Fragment key={station}>
              <span className="px-3 py-1 bg-gray-100 rounded">{station}</span>
              {i < route.stations.length - 1 && (
                <span className="text-gray-400">→</span>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Explanation */}
      <p className="text-gray-700 mb-4">{route.explanation}</p>

      {/* Scores */}
      <div className="grid grid-cols-3 gap-4 mb-4">
        <ScoreBar
          label="Safety"
          score={route.safety_score}
          icon={<Shield className="w-4 h-4" />}
        />
        <ScoreBar
          label="Reliability"
          score={route.reliability_score}
          icon={<Clock className="w-4 h-4" />}
        />
        <ScoreBar
          label="Efficiency"
          score={route.efficiency_score}
          icon={<Clock className="w-4 h-4" />}
        />
      </div>

      {/* Benefits & Warnings */}
      {route.key_benefits.length > 0 && (
        <div className="mb-3">
          <h4 className="font-semibold text-green-700 mb-2">Benefits:</h4>
          <ul className="text-sm text-gray-700 space-y-1">
            {route.key_benefits.map((benefit) => (
              <li key={benefit}>✓ {benefit}</li>
            ))}
          </ul>
        </div>
      )}

      {route.warnings.length > 0 && (
        <div>
          <h4 className="font-semibold text-orange-700 mb-2 flex items-center gap-2">
            <AlertCircle className="w-4 h-4" /> Considerations:
          </h4>
          <ul className="text-sm text-gray-700 space-y-1">
            {route.warnings.map((warning) => (
              <li key={warning}>⚠ {warning}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ScoreBar({
  label,
  score,
  icon
}: {
  label: string;
  score: number;
  icon: React.ReactNode;
}) {
  const percentage = (score / 10) * 100;
  const color =
    score >= 8.5 ? 'bg-green-500' : score >= 7 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-xs font-semibold text-gray-700">{label}</span>
        <span className="text-xs text-gray-500">{score.toFixed(1)}/10</span>
      </div>
      <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} transition-all`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
```

---

## 📋 Implementation Roadmap

### Week 1: Bedrock Integration & Prompt Engineering
- [ ] **Day 1-2**: Set up Bedrock access and test Claude Haiku 4.5
  - Create IAM role for Lambda → Bedrock access
  - Test converse API locally
  - Benchmark latency (target: <500ms)

- [ ] **Day 3-4**: Design and iterate on prompts
  - Write system prompt for route recommendations
  - Create context injection templates
  - Test with 10+ sample routes
  - Measure token usage (optimize for cost)

- [ ] **Day 5**: DynamoDB cache setup
  - Create route cache table (TTL: 5 min)
  - Add cache read/write logic
  - Test cache hit ratio

### Week 2: Lambda & API Development
- [ ] **Day 1-2**: Build Route Orchestrator Lambda
  - Fetch real-time data from Athena
  - Integrate Bedrock calling
  - Error handling & fallbacks

- [ ] **Day 3-4**: API Gateway setup
  - Create REST endpoint: `/api/routes/recommend`
  - Add request validation
  - Rate limiting (10 req/user/min)
  - CORS configuration

- [ ] **Day 5**: Load testing
  - Test latency with concurrent requests
  - Measure Bedrock token usage
  - Optimize caching strategy

### Week 3: Frontend Integration
- [ ] **Day 1-2**: Build RouteRecommender component
  - Input form (origin/destination)
  - Route cards with scores
  - Loading states

- [ ] **Day 3-4**: UI Polish
  - Add map visualization (Google Maps API)
  - Real-time updates (Pusher/Socket.io)
  - Mobile responsiveness

- [ ] **Day 5**: User testing
  - Gather feedback on route recommendations
  - Iterate on explanations (make more helpful)
  - Test on mobile devices

### Week 4: Optimization
- [ ] **Day 1-2**: Performance tuning
  - Measure end-to-end latency
  - Optimize Athena queries
  - Profile Lambda execution

- [ ] **Day 3**: Cost optimization
  - Review Bedrock token usage
  - Adjust cache TTL
  - Consider prompt compression

- [ ] **Day 4-5**: Production hardening
  - Add monitoring/alerting
  - Create runbook for issues
  - Deploy to prod (blue-green)

### Week 5-6: Polish & Deployment
- [ ] Documentation
- [ ] Staff training
- [ ] Marketing rollout
- [ ] Monitor production metrics

---

## 💰 Cost Breakdown

### Bedrock (Claude Haiku 4.5)
- **Input tokens**: ~300 per request (context + prompt)
- **Output tokens**: ~150 per request (3 routes)
- **Total per request**: 450 tokens
- **Requests/day**: Assume 1,000 (conservative for MVP)
- **Daily cost**: (450 × 1,000) / 1,000,000 × ($0.80 + $0.40) = **$0.54/day**
- **Monthly cost**: **~$16/month**

### Lambda
- **Invocations**: 1,000/day = 30,000/month
- **Execution time**: ~800ms average (free tier includes first 1M)
- **Cost**: Free tier covers this ✅

### DynamoDB Cache
- **Writes**: 1,000/day = 30,000/month
- **Reads**: 500/day (cache hits) = 15,000/month (hypothetical)
- **On-demand pricing**: ~$6.25 per 1M writes
- **Monthly cost**: **~$0.20/month**

### API Gateway
- **Requests**: 30,000/month
- **Cost**: $0.35 per 1M requests
- **Monthly cost**: **~$0.01/month**

### S3 (Athena results)
- **Negligible** (results cached in DynamoDB)

### **TOTAL PHASE 4 MONTHLY COST: ~$16.25/month** 💰

---

## 🧪 Testing Strategy

### Unit Tests
```python
# Test Bedrock integration
def test_bedrock_response_parsing():
    mock_response = """[{"name": "SafeRoute", ...}]"""
    routes = parse_bedrock_response(mock_response)
    assert len(routes) == 3
    assert routes[0]['name'] == 'SafeRoute'

# Test cache logic
def test_cache_hit():
    put_in_cache('key1', routes)
    cached = get_from_cache('key1')
    assert cached == routes

# Test prompt building
def test_user_message_format():
    msg = build_user_message('GC', 'TS', {})
    assert 'Grand Central' in msg
    assert 'Times Square' in msg
```

### Integration Tests
```python
# End-to-end test
def test_full_route_recommendation():
    event = {
        'origin': 'Grand Central',
        'destination': 'Times Square'
    }
    response = lambda_handler(event, None)
    assert response['statusCode'] == 200
    data = json.loads(response['body'])
    assert len(data['data']) == 3
```

### Load Testing
```bash
# Using Apache Bench
ab -n 1000 -c 10 \
  -p request.json \
  https://api.smartroute.com/api/routes/recommend

# Expected: <2 second response time (p99)
```

---

## 📊 Monitoring & Observability

### CloudWatch Metrics
```python
import cloudwatch

# Log invocation
cloudwatch.put_metric_data(
    Namespace='SmartRoute/Phase4',
    MetricData=[
        {
            'MetricName': 'BedrockLatency',
            'Value': bedrock_duration_ms,
            'Unit': 'Milliseconds'
        },
        {
            'MetricName': 'CacheHitRate',
            'Value': (cache_hits / total_requests) * 100,
            'Unit': 'Percent'
        }
    ]
)
```

### Alarms
- **Bedrock Error Rate** > 5% → PagerDuty alert
- **Lambda Duration** > 3 seconds → Investigate
- **Cache Hit Rate** < 20% → Adjust TTL

---

## 🎓 Key Learning Points

This phase demonstrates:
- **Large Language Models (LLMs)**: Using Claude Haiku for real-time decision-making
- **Prompt Engineering**: Designing effective prompts for specific tasks
- **Real-time Data Integration**: Combining multiple data sources (Athena + DynamoDB)
- **API Design**: Building RESTful endpoints for LLM applications
- **Cost Optimization**: Using a small model (Haiku) for high-frequency tasks

---

## 🚀 Success Criteria

Phase 4 is complete when:

1. ✅ Claude Haiku 4.5 recommends 3 distinct routes per request
2. ✅ Recommendations combine MTA delays + crime data + reliability scores
3. ✅ API responds in <2 seconds (p99 latency)
4. ✅ Natural language explanations are helpful and accurate
5. ✅ Frontend displays routes with scores and benefits
6. ✅ Cost is <$20/month for recommendation engine
7. ✅ 95%+ uptime over 1 week of production monitoring
8. ✅ User satisfaction score > 4.0/5.0 (initial feedback)

---

**Phase 4 Ready for Implementation! 🚀**
