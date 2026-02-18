# SmartRoute Score Meanings & Calculations

## Overview

SmartRoute provides three scores for each recommended route to help you make the best decision based on your priorities:

- **Safety Score** (🛡️) - Crime safety in the area
- **Reliability Score** (⏱️) - On-time performance of transit lines
- **Efficiency Score** (⚡) - Travel speed and directness

Each score ranges from **0-10**, where 10 is the best.

---

## 🛡️ Safety Score (0-10)

**What it measures:** The crime incident rate near subway stations on the route.

**How it's calculated:**
- **9-10 (Very Safe):** 0-2 crimes in the area during the last 7 days
- **7-8 (Safe):** 3-5 crimes in the area
- **5-6 (Moderate):** 6-10 crimes in the area
- **3-4 (Less Safe):** 11-20 crimes in the area
- **0-2 (Avoid):** 20+ crimes in the area

**Data source:** MTA crime statistics aggregated from Athena (7-day rolling window)

**Example:**
- Times Square (high foot traffic): Safety score 4-6 (moderate due to volume)
- Less busy local stations: Safety score 7-8

---

## ⏱️ Reliability Score (0-10)

**What it measures:** The on-time performance of the subway lines used in the route.

**How it's calculated:**
- **9-10 (Excellent):** 95%+ on-time performance
- **7-8 (Good):** 90-95% on-time
- **5-6 (Average):** 85-90% on-time
- **3-4 (Poor):** 75-85% on-time
- **0-2 (Very Unreliable):** <75% on-time

**Data source:** Historical MTA performance data and real-time delays

**Example:**
- A-line (well-maintained, frequent service): Reliability score 8-9
- Shuttle service with dedicated staff: Reliability score 9-10

---

## ⚡ Efficiency Score (0-10)

**What it measures:** How fast and direct the route is (travel time + number of transfers).

**How it's calculated:**
- **10 (Maximum):** Direct route with 0 transfers
- **8-9:** Route with 1 transfer
- **6-7:** Route with 2 transfers
- **4-5:** Route with 3 transfers
- **0-3:** Route with 4+ transfers

**Additional factors:**
- Estimated travel time in minutes
- Walking distance from origin address to first station

**Example:**
- Times Square → Grand Central via Shuttle (direct): Efficiency 10
- Times Square → Brooklyn Bridge via 2 transfers: Efficiency 6-7

---

## 🎯 Three Route Types

### 1. **SafeRoute** (Prioritizes Safety)
- Focuses on stations with low crime rates
- Prefers reliable, well-staffed lines
- May take longer but prioritizes your security
- Best for: Late night travel, unfamiliar routes, risk-averse travelers

### 2. **FastRoute** (Prioritizes Speed)
- Direct routes with minimal transfers
- Shortest estimated travel time
- Uses the most efficient subway lines
- Best for: Time-sensitive trips, commuting, efficiency-focused travelers

### 3. **BalancedRoute** (Recommended)
- Balances all three factors
- Good safety, reliable lines, reasonable travel time
- Best for: Most everyday trips, when you want the best overall experience

---

## 📊 Understanding Score Variations

**Why do scores differ between routes?**

For the same origin-destination pair, different routes may have:
- **Different stations:** Some neighborhoods have higher crime rates
- **Different lines:** Some lines have better on-time performance
- **Different numbers of transfers:** Direct routes are more efficient

**Example for Times Square → Grand Central:**
- SafeRoute via Shuttle: Safety 6, Reliability 9, Efficiency 10
- FastRoute via local lines: Safety 5, Reliability 8, Efficiency 9
- BalancedRoute via express: Safety 6, Reliability 9, Efficiency 8

---

## 💡 Tips for Using Scores

1. **Night Travel?** Prioritize SafeRoute (highest safety score)
2. **In a Hurry?** Prioritize FastRoute or BalancedRoute (highest efficiency)
3. **Avoiding Crowds?** Look for routes with high reliability and fewer transfers
4. **New to NYC?** Start with BalancedRoute recommendations

---

## 🔄 Real-Time Updates

Scores are recalculated based on:
- **Current delays:** Real-time MTA GTFS-RT feeds
- **Daily aggregations:** Fresh crime statistics (updated daily at 2 AM UTC)
- **User feedback:** Reliability ratings improve with more historical data

Results are cached for 5 minutes to improve performance.

---

## Questions or Feedback?

- Low scores in your area? Crime data comes from official MTA records
- Unreliable lines? Report to MTA directly
- Inaccurate station names? Help us improve by reporting issues

---

**Last Updated:** 2025-11-21
**Version:** Phase 5 Production
