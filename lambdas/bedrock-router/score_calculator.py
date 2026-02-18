#!/usr/bin/env python3
"""
Score Calculator - Computes Safety, Reliability, and Efficiency scores for routes
Uses statistical baselines to provide meaningful, contextual scores.
"""

import logging
from typing import Dict, List, Optional
import statistics

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ScoreCalculator:
    """
    Calculates three scores (0-10 scale) for subway routes:
    - Safety Score: Based on crime incidents compared to NYC baseline
    - Reliability Score: Based on line on-time performance vs city average
    - Efficiency Score: Based on transfers and travel time
    """

    def __init__(
        self,
        crime_data: Optional[Dict] = None,
        line_performance: Optional[Dict] = None,
    ):
        """
        Initialize score calculator with reference data.

        Args:
            crime_data: Dict mapping station name to crime incident count
            line_performance: Dict mapping line to on-time performance %
        """
        self.crime_data = crime_data or {}
        self.line_performance = line_performance or {}

        # Calculate baselines for context-aware scoring
        self.crime_baseline = self._calculate_crime_baseline()
        self.reliability_baseline = self._calculate_reliability_baseline()

        logger.info(f"✅ Score calculator initialized")
        logger.info(f"   Crime baseline: {self.crime_baseline['mean']:.1f} incidents/station")
        logger.info(f"   Reliability baseline: {self.reliability_baseline['mean']:.1f}% on-time")

    def _calculate_crime_baseline(self) -> Dict:
        """
        Calculate crime statistics from all stations.

        Returns:
            Dict with mean, median, std_dev, min, max, percentiles
        """
        if not self.crime_data:
            return {
                'mean': 5,
                'median': 5,
                'std_dev': 2,
                'min': 0,
                'max': 20,
                'p25': 3,
                'p50': 5,
                'p75': 8,
            }

        crimes = list(self.crime_data.values())
        if not crimes:
            return {'mean': 5, 'median': 5, 'std_dev': 2, 'min': 0, 'max': 20}

        sorted_crimes = sorted(crimes)
        n = len(sorted_crimes)

        return {
            'mean': statistics.mean(crimes),
            'median': statistics.median(crimes),
            'std_dev': statistics.stdev(crimes) if len(crimes) > 1 else 0,
            'min': min(crimes),
            'max': max(crimes),
            'p25': sorted_crimes[int(n * 0.25)],
            'p50': sorted_crimes[int(n * 0.50)],
            'p75': sorted_crimes[int(n * 0.75)],
        }

    def _calculate_reliability_baseline(self) -> Dict:
        """
        Calculate line reliability statistics.

        Returns:
            Dict with mean, median, std_dev, min, max, percentiles
        """
        if not self.line_performance:
            return {
                'mean': 85,
                'median': 85,
                'std_dev': 3,
                'min': 77,
                'max': 92,
                'p25': 82,
                'p50': 85,
                'p75': 88,
            }

        # Extract percentages from line_performance dicts
        perf_values = []
        for line_data in self.line_performance.values():
            if isinstance(line_data, dict):
                perf = line_data.get('on_time_percent', 85)
            else:
                perf = line_data
            perf_values.append(perf)

        if not perf_values:
            return {'mean': 85, 'median': 85, 'std_dev': 3}

        sorted_perf = sorted(perf_values)
        n = len(sorted_perf)

        return {
            'mean': statistics.mean(perf_values),
            'median': statistics.median(perf_values),
            'std_dev': statistics.stdev(perf_values) if len(perf_values) > 1 else 0,
            'min': min(perf_values),
            'max': max(perf_values),
            'p25': sorted_perf[int(n * 0.25)],
            'p50': sorted_perf[int(n * 0.50)],
            'p75': sorted_perf[int(n * 0.75)],
        }

    def calculate_route_scores(self, route: Dict) -> Dict:
        """
        Calculate all three scores for a route.

        Args:
            route: Route dictionary with stations, lines, transfers, time

        Returns:
            Dictionary with safety_score, reliability_score, efficiency_score
        """
        safety_score = self.calculate_safety_score(route["stations"])
        reliability_score = self.calculate_reliability_score(route["lines"])
        efficiency_score = self.calculate_efficiency_score(
            route["total_transfers"], route["total_time_minutes"]
        )

        return {
            "safety_score": safety_score,
            "reliability_score": reliability_score,
            "efficiency_score": efficiency_score,
        }

    def calculate_safety_score(self, stations: List[str]) -> int:
        """
        Calculate Safety Score (0-10) based on percentile ranking.

        Higher score = safer route (fewer crimes than baseline)
        Uses percentile ranking: if route is in top 25% (lowest crime), score 9-10

        Scoring based on percentile:
        - 90th+ percentile (safest 10%): 10
        - 75-90th percentile: 8-9
        - 50-75th percentile: 6-7
        - 25-50th percentile: 4-5
        - <25th percentile (most dangerous): 2-3

        Args:
            stations: List of station names in route

        Returns:
            Integer score 0-10
        """
        if not stations:
            return 5

        # Get crime data for all stations
        crimes_list = [
            self.crime_data.get(station, self.crime_baseline['mean'])
            for station in stations
        ]

        route_avg_crime = sum(crimes_list) / len(crimes_list)

        # Calculate percentile: what % of stations have more crime than this route?
        all_crimes = list(self.crime_data.values()) if self.crime_data else []
        if all_crimes:
            crime_count = sum(1 for c in all_crimes if c >= route_avg_crime)
            percentile = (len(all_crimes) - crime_count) / len(all_crimes) * 100
        else:
            # Compare to baseline if no data
            percentile = 50 if route_avg_crime <= self.crime_baseline['mean'] else 30

        # Map percentile to 0-10 scale
        if percentile >= 90:
            safety_score = 10
        elif percentile >= 75:
            safety_score = 8 + (percentile - 75) / 15
        elif percentile >= 50:
            safety_score = 6 + (percentile - 50) / 25
        elif percentile >= 25:
            safety_score = 4 + (percentile - 25) / 25
        else:
            safety_score = 2 + (percentile / 25)

        logger.debug(
            f"   Safety: {len(stations)} stations, "
            f"avg {route_avg_crime:.1f} crimes (baseline: {self.crime_baseline['mean']:.1f}), "
            f"percentile {percentile:.0f}%, score {safety_score:.1f}"
        )

        return int(round(safety_score))

    def calculate_reliability_score(self, lines: List[str]) -> int:
        """
        Calculate Reliability Score (0-10) based on percentile ranking vs city average.

        Higher score = more reliable lines (higher on-time %)
        Uses percentile ranking: if route uses top-performing lines, score 9-10

        Scoring based on percentile:
        - 90th+ percentile (most reliable): 10
        - 75-90th percentile: 8-9
        - 50-75th percentile: 6-7 (city average)
        - 25-50th percentile: 4-5
        - <25th percentile (least reliable): 2-3

        Args:
            lines: List of transit line letters/numbers

        Returns:
            Integer score 0-10
        """
        if not lines:
            return 5

        # Get performance for all lines used
        performance_list = []
        for line in lines:
            if line in self.line_performance:
                line_data = self.line_performance[line]

                # Handle both dict format and plain int format
                if isinstance(line_data, dict):
                    perf = line_data.get("on_time_percent", self.reliability_baseline['mean'])
                else:
                    perf = line_data
            else:
                perf = self.reliability_baseline['mean']  # Use city average

            performance_list.append(perf)

        route_avg_performance = sum(performance_list) / len(performance_list)

        # Calculate percentile: what % of lines have lower on-time % than this route?
        all_perfs = []
        for line_data in self.line_performance.values():
            if isinstance(line_data, dict):
                all_perfs.append(line_data.get("on_time_percent", 85))
            else:
                all_perfs.append(line_data)

        if all_perfs:
            better_count = sum(1 for p in all_perfs if p < route_avg_performance)
            percentile = (better_count / len(all_perfs)) * 100
        else:
            # Compare to baseline if no data
            percentile = 50 if route_avg_performance >= self.reliability_baseline['mean'] else 30

        # Map percentile to 0-10 scale
        if percentile >= 90:
            reliability_score = 10
        elif percentile >= 75:
            reliability_score = 8 + (percentile - 75) / 15
        elif percentile >= 50:
            reliability_score = 6 + (percentile - 50) / 25
        elif percentile >= 25:
            reliability_score = 4 + (percentile - 25) / 25
        else:
            reliability_score = 2 + (percentile / 25)

        logger.debug(
            f"   Reliability: {len(lines)} lines, "
            f"avg {route_avg_performance:.1f}% on-time (baseline: {self.reliability_baseline['mean']:.1f}%), "
            f"percentile {percentile:.0f}%, score {reliability_score:.1f}"
        )

        return int(round(reliability_score))

    def calculate_efficiency_score(self, num_transfers: int, travel_time_minutes: int) -> int:
        """
        Calculate Efficiency Score (0-10).

        Higher score = faster route with fewer transfers

        Scale:
        - 10: Direct (0 transfers, shortest time)
        - 8-9: 1 transfer
        - 6-7: 2 transfers
        - 4-5: 3 transfers
        - 0-3: 4+ transfers

        Args:
            num_transfers: Number of line transfers in route
            travel_time_minutes: Total travel time in minutes

        Returns:
            Integer score 0-10
        """
        # Transfer penalty: -1.5 points per transfer
        transfer_penalty = min(num_transfers * 1.5, 10)

        efficiency_score = max(0, min(10, 10 - transfer_penalty))

        logger.debug(
            f"   Efficiency: {num_transfers} transfers, "
            f"{travel_time_minutes}min, score {efficiency_score:.1f}"
        )

        return int(round(efficiency_score))

    def update_crime_data(self, crime_data: Dict) -> None:
        """
        Update crime data used for scoring.

        Args:
            crime_data: Dictionary mapping station names to crime counts
        """
        self.crime_data = crime_data
        logger.info(f"✅ Updated crime data for {len(crime_data)} stations")

    def update_line_performance(self, line_performance: Dict) -> None:
        """
        Update line performance data used for scoring.

        Args:
            line_performance: Dictionary mapping line to on-time % or performance dict
        """
        self.line_performance = line_performance
        logger.info(f"✅ Updated performance data for {len(line_performance)} lines")

    @staticmethod
    def get_score_interpretation(score_type: str, score: int) -> str:
        """
        Get human-readable interpretation of a score.

        Args:
            score_type: "safety", "reliability", or "efficiency"
            score: Score value 0-10

        Returns:
            String description
        """
        if score_type == "safety":
            if score >= 9:
                return "Very safe"
            elif score >= 7:
                return "Safe"
            elif score >= 5:
                return "Moderate"
            elif score >= 3:
                return "Less safe"
            else:
                return "Avoid if possible"
        elif score_type == "reliability":
            if score >= 9:
                return "Excellent (95%+ on-time)"
            elif score >= 7:
                return "Good (90-95% on-time)"
            elif score >= 5:
                return "Average (85-90% on-time)"
            elif score >= 3:
                return "Poor (75-85% on-time)"
            else:
                return "Very unreliable (<75%)"
        elif score_type == "efficiency":
            if score >= 9:
                return "Direct (0 transfers)"
            elif score >= 7:
                return "Very efficient (1 transfer)"
            elif score >= 5:
                return "Efficient (2 transfers)"
            elif score >= 3:
                return "Multiple transfers (3)"
            else:
                return "Many transfers (4+)"
        else:
            return f"Score: {score}/10"
