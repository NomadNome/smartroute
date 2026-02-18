# SmartRoute Phase 5: Graph-Based Routing Architecture

## Executive Summary

This document outlines the transition from **Bedrock-only route generation** to a **hybrid approach** using:
- **Graph-based pathfinding** (Dijkstra's algorithm) for accurate route calculation
- **Bedrock AI** for intelligent explanations and contextual guidance
- **Weighted graph edges** based on safety, reliability, and efficiency metrics

**Problem Being Solved:**
Previously, Bedrock was generating impossible routes (e.g., Jay Street → Grand Central via 22-minute Flatbush detour with 20 duplicate line entries). This architecture ensures physically valid, optimized routes while keeping AI for natural language explanations.

---

## Architecture Overview

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      API Request                                 │
│         Origin: "Jay Street"                                     │
│         Destination: "Grand Central"                             │
│         Criterion: "balanced"                                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│              1. Station Resolution Layer                          │
│  - Resolve address/station name to canonical station name       │
│  - Validate station exists in graph                             │
│  Output: ("Jay Street-MetroTech", "Grand Central-42nd Street")   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│              2. Graph Routing Engine (NEW)                        │
│  ┌────────────────────────────────────────────────────────┐      │
│  │ SafeRoute: Dijkstra with safety-weighted edges         │      │
│  │ FastRoute: Dijkstra with time-weighted edges           │      │
│  │ BalancedRoute: Dijkstra with combined weight           │      │
│  └────────────────────────────────────────────────────────┘      │
│  Output: 3 routes with stations, lines, transfer points         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│         3. Score Calculation Layer                               │
│  - Compute safety score from crime data                         │
│  - Compute reliability score from line performance              │
│  - Compute efficiency score from transfers + time               │
│  Output: scores for each route                                  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│         4. Bedrock Explanation Layer                             │
│  - Generate natural language explanations for each route        │
│  - Explain WHY each route is best in its category              │
│  - Keep brief, context-aware, user-focused                     │
│  Output: "This route is safest because..."                     │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│            Final Response (JSON)                                 │
│  {                                                               │
│    "origin": "Jay Street-MetroTech",                            │
│    "destination": "Grand Central-42nd Street",                  │
│    "routes": [                                                   │
│      {                                                           │
│        "name": "SafeRoute",                                     │
│        "stations": [...],              ← VALID sequence        │
│        "lines": ["A", "6"],            ← Minimal, accurate      │
│        "estimated_time_minutes": 14,   ← Realistic             │
│        "safety_score": 6,              ← From crime data       │
│        "reliability_score": 8,         ← From performance      │
│        "efficiency_score": 8,          ← From transfers        │
│        "explanation": "..."            ← From Bedrock         │
│      },                                                         │
│      ...                                                         │
│    ]                                                             │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Subway Network Graph (`subway_graph.py`)

**Purpose:** Represent the NYC subway system as a directed graph with proper topology and weights

**Data Structure:**

```python
subway_graph = {
    "Jay Street-MetroTech": {
        "A": {
            "stations": ["Spring Street", "Canal Street", ...],
            "travel_time_minutes": [2, 3, ...],
            "accessibility": True
        },
        "C": {
            "stations": ["Spring Street", "Canal Street", ...],
            "travel_time_minutes": [2, 3, ...],
            "accessibility": True
        },
        "F": {...},
        "R": {...}
    },
    "Spring Street": {
        "A": {...},
        "C": {...},
        ...
    },
    ...
}

# Transfers (connections between lines at same/adjacent stations)
transfers = {
    ("Canal Street", "1"): [  # From Canal Street Line 1 to:
        ("Canal Street", "2", 2),    # Canal Street Line 2 - 2 min walk
        ("Canal Street", "A", 2),
        ("Canal Street", "C", 2),
        ("Canal Street", "4", 1),
        ...
    ]
}
```

**Key Features:**
- Real adjacency lists (not randomly guessed)
- Actual travel times between stops
- Transfer points with walking time costs
- Line information (express vs local)
- Accessibility flags

**Data Source:**
- GTFS (General Transit Feed Specification) from MTA
- Manual validation against real subway map

---

### 2. Route Optimizer (`route_optimizer.py`)

**Purpose:** Generate 3 optimized routes using Dijkstra's algorithm with different weightings

**Algorithm: Dijkstra's Shortest Path**

```
Function: dijkstra(graph, start, end, weight_func):
  Input:
    - graph: Subway network
    - start: Origin station
    - end: Destination station
    - weight_func: Function to calculate edge weight

  Process:
    1. Initialize distances[all stations] = infinity
    2. distances[start] = 0
    3. Create priority queue with (distance, station)
    4. While priority queue not empty:
       a. Pop station with minimum distance
       b. If station == end: return path
       c. For each adjacent station via line L:
          - Calculate new_distance = current + weight(edge)
          - If new_distance < distances[adjacent]:
             Update distances[adjacent]
             Add to priority queue
    5. Return shortest path with stations and lines

  Output:
    {
      "stations": [start, ..., end],
      "lines": [line_1, line_2, ...],
      "total_time": minutes,
      "transfers": count
    }
```

**Time Complexity:** O((V + E) log V) where V = stations, E = connections
**Space Complexity:** O(V + E)

---

### 3. Route Weighting Strategies

**SafeRoute: Crime-Based Weighting**

```python
def weight_for_safety(edge, safety_scores, crime_data):
    """
    Lower crime = easier to traverse
    Uses inverse of crime incidents as multiplier
    """
    station = edge["destination"]
    crimes = crime_data.get(station, 10)  # Default: moderate

    # Base travel time
    base_time = edge["travel_time"]

    # Safety multiplier: 1.0 to 3.0
    # 0 crimes = 1.0x (fast)
    # 20+ crimes = 3.0x (avoid)
    safety_multiplier = 1.0 + (crimes / 10.0)

    return base_time * safety_multiplier
```

**FastRoute: Time-Based Weighting**

```python
def weight_for_speed(edge, transfers_made):
    """
    Minimize travel time + transfer penalty
    """
    base_time = edge["travel_time"]
    transfer_penalty = 5 if transfers_made > 0 else 0

    return base_time + transfer_penalty
```

**BalancedRoute: Combined Weighting**

```python
def weight_for_balance(edge, safety_scores, transfers_made):
    """
    Balance safety + speed
    50% time, 30% crime, 20% transfers
    """
    base_time = edge["travel_time"]
    crimes = crime_data.get(edge["destination"], 10)
    transfer_penalty = 3 if transfers_made > 0 else 0

    weight = (
        (base_time * 0.5) +
        ((crimes / 10.0) * 5 * 0.3) +
        (transfer_penalty * 0.2)
    )

    return weight
```

---

### 4. Score Calculation (`score_calculator.py`)

After routes are determined, calculate final scores:

**Safety Score (0-10):**
```python
def calculate_safety_score(route_stations, crime_data):
    """
    Average crime incidents across all stations
    Inverse mapped to 0-10 scale
    """
    total_crimes = sum(
        crime_data.get(station, 5)
        for station in route_stations
    )
    avg_crimes = total_crimes / len(route_stations)

    # Map: 0 crimes = 10, 20+ crimes = 0
    safety_score = max(0, min(10, 10 - (avg_crimes * 0.5)))

    return int(safety_score)
```

**Reliability Score (0-10):**
```python
def calculate_reliability_score(route_lines, line_performance):
    """
    Average on-time performance of lines used
    """
    reliabilities = [
        line_performance.get(line, 85)  # Default 85%
        for line in route_lines
    ]
    avg_reliability = sum(reliabilities) / len(reliabilities)

    # Map: 95%+ = 10, <75% = 0
    reliability_score = max(0, min(10,
        (avg_reliability - 75) / 2
    ))

    return int(reliability_score)
```

**Efficiency Score (0-10):**
```python
def calculate_efficiency_score(num_transfers, travel_time):
    """
    Direct routes = 10, more transfers = lower
    """
    transfer_penalty = num_transfers * 1.5

    # Base: 10 - transfers
    efficiency = max(0, min(10, 10 - transfer_penalty))

    return int(efficiency)
```

---

### 5. Bedrock Explanation Layer (Minimal)

**Purpose:** Generate 1-2 sentence explanations (NOT route generation)

**Prompt:**

```
You are a NYC subway route explainer. Given a route, explain concisely
why it's good for its category.

Route details:
- Category: SafeRoute / FastRoute / BalancedRoute
- Stations: [list]
- Lines: [list]
- Transfers: N
- Time: M minutes
- Safety incidents: X
- Line reliability: Y%

Write ONE sentence explaining why this route is best for its category.
Example for SafeRoute: "This route prioritizes safety by using the
well-monitored 4/5/6 lines and avoiding high-crime areas."

Keep it factual, concise, and helpful.
```

**Key Changes:**
- Bedrock only EXPLAINS routes, doesn't GENERATE them
- Routes are pre-calculated and validated
- Explanation uses hard data (stations, lines, transfers)
- No hallucination possible (data is factual)

---

## Implementation Plan

### Phase 1: Graph Construction (2 hours)

**Files to Create:**

1. **`lambdas/bedrock-router/subway_graph.py`** (400 lines)
   - `subway_graph` dictionary with all stations and connections
   - `transfer_points` dictionary with walking times
   - `line_metadata` with performance data
   - Helper functions: `get_adjacent_stations()`, `validate_station()`

2. **`lambdas/bedrock-router/gtfs_parser.py`** (200 lines, optional)
   - Parse real GTFS data if using official MTA data
   - Convert to our graph format
   - Validate connectivity

### Phase 2: Routing Algorithm (3 hours)

**Files to Create:**

1. **`lambdas/bedrock-router/dijkstra_router.py`** (300 lines)
   - `DijkstraRouter` class
   - Methods:
     - `find_shortest_path(start, end, weight_func)`
     - `find_all_lines_between(start, end)`
     - `backtrack_path(prev_stations, end)`
   - Priority queue implementation (use `heapq`)

2. **`lambdas/bedrock-router/route_optimizer.py`** (250 lines)
   - `RouteOptimizer` class
   - Methods:
     - `generate_safe_route(origin, dest, safety_scores)`
     - `generate_fast_route(origin, dest)`
     - `generate_balanced_route(origin, dest, safety_scores)`
   - Weight function implementations

3. **`lambdas/bedrock-router/score_calculator.py`** (150 lines)
   - `ScoreCalculator` class
   - Methods:
     - `calculate_safety_score(route_stations)`
     - `calculate_reliability_score(route_lines)`
     - `calculate_efficiency_score(num_transfers, time)`

### Phase 3: Integration (2 hours)

**Files to Modify:**

1. **`lambdas/bedrock-router/lambda_function.py`**
   - Replace Bedrock route generation with graph routing
   - Keep Bedrock explanation layer
   - Update error handling
   - Cache results with proper invalidation

2. **`lambdas/bedrock-router/bedrock_route_recommender.py`**
   - Simplify to explanation-only
   - Remove route generation logic
   - Update system prompt to focus on explanations

### Phase 4: Testing & Validation (1 hour)

**Test Cases:**

1. **Jay Street → Grand Central**
   - Should return: A/C → 6 transfer
   - Time: ~14 minutes
   - Stations: ~8

2. **Times Square → Brooklyn Bridge**
   - Should return: multiple options
   - All should be logically valid

3. **Edge Cases:**
   - Same station (origin = destination)
   - Stations with many line options (34th St Herald Square)
   - Long distances (Flushing → Far Rockaway)

---

## Data Structures

### Graph Node Format

```python
{
    "station_name": "Jay Street-MetroTech",
    "latitude": 40.6938,
    "longitude": -73.9866,
    "lines_available": ["A", "C", "F", "R"],
    "accessibility": True,
    "nearby_transfers": [
        ("High Street-Brooklyn Bridge", "A", 0.1),  # 100m, A line
        ("Borough Hall", "4", 0.3)  # 300m, 4 line
    ]
}
```

### Edge Format

```python
{
    "source": "Jay Street-MetroTech",
    "destination": "Spring Street",
    "line": "A",
    "travel_time_minutes": 2,
    "accessibility": True,
    "is_express": False,
    "stops": ["Jay Street-MetroTech", "Spring Street"]
}
```

### Route Format (Output)

```python
{
    "name": "SafeRoute",
    "stations": [
        "Jay Street-MetroTech",
        "Spring Street",
        "Canal Street",
        "Canal Street",  # Transfer point
        "Brooklyn Bridge-City Hall",
        "Park Place",
        "Chambers Street",
        "Franklin Street",
        "Canal Street",
        "14th Street",
        "23rd Street",
        "28th Street",
        "33rd Street",
        "Grand Central-42nd Street"
    ],
    "lines": ["A", "6"],  # Simple, accurate
    "segments": [
        {
            "line": "A",
            "from": "Jay Street-MetroTech",
            "to": "Canal Street",
            "stops": 3,
            "time_minutes": 6
        },
        {
            "type": "transfer",
            "from": "Canal Street (A)",
            "to": "Canal Street (6)",
            "time_minutes": 2,
            "walking": True
        },
        {
            "line": "6",
            "from": "Canal Street",
            "to": "Grand Central-42nd Street",
            "stops": 8,
            "time_minutes": 8
        }
    ],
    "total_time_minutes": 14,
    "total_transfers": 1,
    "total_stops": 11,
    "safety_score": 6,
    "reliability_score": 8,
    "efficiency_score": 8,
    "explanation": "This route prioritizes your safety..."
}
```

---

## Key Improvements Over Current System

| Aspect | Before | After |
|--------|--------|-------|
| **Route Validity** | ❌ Impossible routes | ✅ Graph-enforced |
| **Station Sequence** | ❌ Random/hallucinatory | ✅ Real subway topology |
| **Line Accuracy** | ❌ Duplicate lines (A,A,A) | ✅ Actual line transfers |
| **Travel Time** | ❌ Unrealistic (22min for 14min) | ✅ Based on real stops |
| **Transfer Points** | ❌ Not validated | ✅ Validated transfers |
| **Reproducibility** | ❌ Changes every request | ✅ Deterministic algorithm |
| **Debuggability** | ❌ Hard to understand | ✅ Clear path tracing |
| **Scalability** | ⚠️ Limited to Bedrock | ✅ Pure algorithm |
| **Real-time Updates** | ❌ Not supported | ✅ Easy to add delays |

---

## Future Enhancements

1. **Real-time Delay Integration**
   - Weight edges dynamically based on current MTA delays
   - Update `weight_func` to query live delay API

2. **Accessibility Routing**
   - Add `accessible_only` parameter
   - Filter to wheelchair-accessible stations

3. **Express/Local Optimization**
   - Prefer express trains on long distances
   - Weight local trains lower for short hops

4. **Crowdedness Factor**
   - MTA real-time crowdedness API
   - Avoid popular lines during peak hours

5. **Multi-objective Optimization**
   - Pareto frontier: routes with different time/safety tradeoffs
   - Return 5+ routes instead of 3

---

## Success Criteria

- ✅ Jay Street → Grand Central returns 14-minute route, not 22
- ✅ Lines array shows actual transfers: ["A", "6"], not ["A"]*7 + ["C"]*11
- ✅ Station sequence follows real subway topology
- ✅ All 3 routes are physically valid
- ✅ Bedrock explanations are brief and accurate
- ✅ Consistent results across repeated requests
- ✅ Performance: <500ms for route calculation
- ✅ Handles all major NYC subway lines (1-6, A-Z)

---

## Timeline

- **Day 1 (Today):** Phase 1 (Graph) + Phase 2 (Routing)
- **Day 2:** Phase 3 (Integration) + Phase 4 (Testing)
- **Total Effort:** ~8 hours of focused development

---

**Status:** Ready to build 🚀
**Last Updated:** 2025-11-21
**Version:** Phase 5.1 (Graph Routing)
