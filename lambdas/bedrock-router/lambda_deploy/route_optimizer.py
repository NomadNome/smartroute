#!/usr/bin/env python3
"""
Route Optimizer - Generates 3 optimized routes (Safe, Fast, Balanced)
Uses Dijkstra's algorithm with different weight functions for each route type.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class RouteOptimizer:
    """
    Generates 3 optimized routes between origin and destination:
    - SafeRoute: Minimizes crime exposure
    - FastRoute: Minimizes travel time
    - BalancedRoute: Balances all factors
    """

    def __init__(self, dijkstra_router, crime_data: Optional[Dict] = None):
        """
        Initialize the route optimizer.

        Args:
            dijkstra_router: DijkstraRouter instance
            crime_data: Dictionary mapping station names to crime incident counts
        """
        self.router = dijkstra_router
        self.crime_data = crime_data or {}
        logger.info("✅ Route optimizer initialized")

    def generate_routes(
        self,
        origin: str,
        destination: str,
        line_performance: Optional[Dict] = None,
    ) -> Optional[List[Dict]]:
        """
        Generate 3 optimized routes between origin and destination.

        Args:
            origin: Origin station name
            destination: Destination station name
            line_performance: Dictionary mapping line to on-time performance %

        Returns:
            List of 3 routes or None if no valid routes found:
            [
                {
                    "name": "SafeRoute",
                    "stations": [...],
                    "lines": [...],
                    ...
                },
                ...
            ]
        """
        logger.info(
            f"🚀 Generating 3 routes: {origin} → {destination}"
        )

        routes = []

        # 1. SafeRoute - Minimize crime exposure
        logger.info("📍 Generating SafeRoute (safety-optimized)")
        safe_route = self._generate_safe_route(origin, destination)
        if safe_route:
            safe_route["name"] = "SafeRoute"
            routes.append(safe_route)
            logger.info(f"   ✅ SafeRoute: {safe_route['total_stops']} stops, "
                       f"{safe_route['total_transfers']} transfers")
        else:
            logger.warning("   ⚠️ Could not generate SafeRoute")

        # 2. FastRoute - Minimize travel time
        logger.info("📍 Generating FastRoute (speed-optimized)")
        fast_route = self._generate_fast_route(origin, destination)
        if fast_route:
            fast_route["name"] = "FastRoute"
            routes.append(fast_route)
            logger.info(f"   ✅ FastRoute: {fast_route['total_stops']} stops, "
                       f"{fast_route['total_transfers']} transfers")
        else:
            logger.warning("   ⚠️ Could not generate FastRoute")

        # 3. BalancedRoute - Balance safety and speed
        logger.info("📍 Generating BalancedRoute (balanced)")
        balanced_route = self._generate_balanced_route(origin, destination)
        if balanced_route:
            balanced_route["name"] = "BalancedRoute"
            routes.append(balanced_route)
            logger.info(f"   ✅ BalancedRoute: {balanced_route['total_stops']} stops, "
                       f"{balanced_route['total_transfers']} transfers")
        else:
            logger.warning("   ⚠️ Could not generate BalancedRoute")

        if not routes:
            logger.error(f"❌ Could not generate any routes")
            return None

        logger.info(f"✅ Generated {len(routes)} routes")
        return routes

    def _generate_safe_route(self, origin: str, destination: str) -> Optional[Dict]:
        """
        Generate SafeRoute: Penalize stations with high crime + transfers.

        Weight = (travel_time * crime_multiplier) + transfer_penalty

        Transfer penalty: 5 minutes
        (Avoids unnecessary transfers even when optimizing for safety)
        """

        def weight_safe(current: str, next_station: str, current_line: str, next_line: str, travel_time: int, is_transfer: bool) -> float:
            """Weight function for safety-optimized routing."""
            crimes = self.crime_data.get(next_station, 5)

            # Crime multiplier: 0 crimes = 1.0x, 20 crimes = 3.0x
            crime_multiplier = 1.0 + (min(crimes, 20) / 10.0)
            weight = float(travel_time * crime_multiplier)

            # Add transfer penalty to avoid unnecessary transfers
            if is_transfer:
                weight += 5.0

            return weight

        route = self.router.find_shortest_path(origin, destination, weight_func=weight_safe)
        return route

    def _generate_fast_route(self, origin: str, destination: str) -> Optional[Dict]:
        """
        Generate FastRoute: Minimize travel time with realistic transfer penalties.

        Weight = travel_time + transfer_penalty

        Transfer penalty accounts for:
        - Walking time between platforms (2 min)
        - Average waiting for next train (5-7 min)
        - Inconvenience/complexity (1 min)
        Total: ~8 minutes per transfer (realistic NYC experience)

        This prevents algorithm from treating transfers as "free" and ensures
        routes with fewer transfers are preferred when travel time is similar.
        """

        def weight_fast(current: str, next_station: str, current_line: str, next_line: str, travel_time: int, is_transfer: bool) -> float:
            """Weight function for speed-optimized routing.
            Includes transfer penalties to prefer direct/fewer-transfer routes."""
            # Base travel time
            weight = float(travel_time)

            # Transfer penalty: realistic cost of changing lines
            # Average wait time for NYC subway: 5-7 minutes
            # Walking between platforms: 2 minutes
            # Total: 8 minutes (conservative estimate)
            # This is still lower than safe route (5) to favor speed
            if is_transfer:
                weight += 8.0  # 8 minute transfer penalty

            return weight

        route = self.router.find_shortest_path(origin, destination, weight_func=weight_fast)
        return route

    def _generate_balanced_route(self, origin: str, destination: str) -> Optional[Dict]:
        """
        Generate BalancedRoute: Balance safety, speed, and transfers.

        Weight = (travel_time * 0.5) + (crime_penalty * 0.35) + (transfer_penalty * 0.15)

        Balanced approach:
        - 50% weight on travel time (still prioritize speed)
        - 35% weight on crime avoidance (secondary priority)
        - 15% weight on avoiding transfers (practical consideration)
        """

        def weight_balanced(
            current: str, next_station: str, current_line: str, next_line: str, travel_time: int, is_transfer: bool
        ) -> float:
            """Weight function for balanced routing."""
            crimes = self.crime_data.get(next_station, 5)

            # Crime cost: 0 crimes = 0, 20 crimes = 10
            crime_cost = min(crimes, 20) * 0.5

            # Transfer cost: penalize but not as heavily as safe route
            transfer_cost = 6.0 if is_transfer else 0

            # Balanced: 50% time, 35% crime, 15% transfers
            weight = (travel_time * 0.5) + (crime_cost * 0.35) + (transfer_cost * 0.15)

            return float(weight)

        route = self.router.find_shortest_path(origin, destination, weight_func=weight_balanced)
        return route

    def update_crime_data(self, crime_data: Dict) -> None:
        """
        Update crime data used for route weighting.

        Args:
            crime_data: Dictionary mapping station names to crime incident counts
        """
        self.crime_data = crime_data
        logger.info(f"✅ Updated crime data for {len(crime_data)} stations")

    def rank_routes_by_criterion(self, routes: List[Dict], criterion: str) -> List[Dict]:
        """
        Re-rank routes based on user preference.

        Args:
            routes: List of route dictionaries
            criterion: "safe", "fast", or "balanced"

        Returns:
            Routes re-ordered by relevance to criterion
        """
        if criterion == "safe":
            # Sort by fewest crime incidents on the route
            return sorted(
                routes,
                key=lambda r: sum(
                    self.crime_data.get(station, 5) for station in r["stations"]
                ),
            )
        elif criterion == "fast":
            # Sort by shortest time
            return sorted(routes, key=lambda r: r["total_time_minutes"])
        elif criterion == "balanced":
            # Sort by transfers (fewer transfers = simpler)
            return sorted(routes, key=lambda r: r["total_transfers"])
        else:
            return routes
