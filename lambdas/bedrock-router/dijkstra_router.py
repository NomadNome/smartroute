#!/usr/bin/env python3
"""
Dijkstra's Shortest Path Algorithm for NYC Subway Network
Finds optimal routes between stations with customizable weight functions.
"""

import heapq
import logging
from typing import Dict, List, Tuple, Optional, Callable

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DijkstraRouter:
    """
    Dijkstra's algorithm implementation for subway routing.
    Uses a priority queue for efficient shortest path calculation.

    Time Complexity: O((V + E) log V) where V = stations, E = connections
    Space Complexity: O(V + E)
    """

    def __init__(self, graph):
        """
        Initialize the router with a subway graph.

        Args:
            graph: SubwayGraph instance
        """
        self.graph = graph
        logger.info("✅ Dijkstra router initialized")

    def find_shortest_path(
        self,
        start_station: str,
        end_station: str,
        weight_func: Optional[Callable] = None,
        max_transfers: int = 5,
    ) -> Optional[Dict]:
        """
        Find the shortest path between two stations using Dijkstra's algorithm.

        Args:
            start_station: Origin station name
            end_station: Destination station name
            weight_func: Custom weight function for edges. If None, uses travel time only.
                        Signature: weight_func(current_station, next_station, line, travel_time) -> weight
            max_transfers: Maximum number of transfers allowed (safety limit)

        Returns:
            Dictionary with route information or None if no path found:
            {
                "stations": [...],
                "lines": [...],
                "segments": [{"line": ..., "from": ..., "to": ..., "time": ...}, ...],
                "total_time_minutes": int,
                "total_transfers": int,
                "total_stops": int
            }
        """
        logger.info(f"🚀 Finding path: {start_station} → {end_station}")

        # Validate stations exist
        if not self.graph.validate_station(start_station):
            logger.error(f"❌ Start station not found: {start_station}")
            return None

        if not self.graph.validate_station(end_station):
            logger.error(f"❌ End station not found: {end_station}")
            return None

        # Handle same station
        if start_station == end_station:
            logger.info("🚀 Origin = Destination")
            return {
                "stations": [start_station],
                "lines": [],
                "segments": [],
                "total_time_minutes": 0,
                "total_transfers": 0,
                "total_stops": 1,
            }

        # Get all available lines at start station
        start_lines = self.graph.get_available_lines(start_station)
        if not start_lines:
            logger.error(f"❌ No lines at start station: {start_station}")
            return None

        # Run Dijkstra from each starting line
        best_path = None
        best_distance = float("inf")

        for start_line in start_lines:
            path = self._dijkstra(
                start_station,
                start_line,
                end_station,
                weight_func,
                max_transfers,
            )

            if path and path["total_distance"] < best_distance:
                best_path = path
                best_distance = path["total_distance"]

        if not best_path:
            logger.error(f"❌ No path found between {start_station} and {end_station}")
            return None

        # Extract route information
        route = self._extract_route(best_path)
        logger.info(
            f"✅ Path found: {route['total_stops']} stops, "
            f"{route['total_transfers']} transfers, "
            f"{route['total_time_minutes']} minutes"
        )

        return route

    def _dijkstra(
        self,
        start_station: str,
        start_line: str,
        end_station: str,
        weight_func: Optional[Callable],
        max_transfers: int,
    ) -> Optional[Dict]:
        """
        Dijkstra's algorithm implementation.

        Returns:
            Dictionary with path information or None
        """
        # Initialize distances and previous node tracking
        distances = {}
        previous = {}  # (station, line) -> ((prev_station, prev_line), travel_time)
        visited = set()

        # Priority queue: (distance, station, line, transfers)
        pq = [(0, start_station, start_line, 0)]
        distances[(start_station, start_line)] = 0

        while pq:
            current_dist, current_station, current_line, transfers = heapq.heappop(pq)

            # Skip if already visited
            if (current_station, current_line) in visited:
                continue

            visited.add((current_station, current_line))

            # Check if we reached the destination
            if current_station == end_station:
                logger.info(
                    f"   Found path with {transfers} transfers, distance {current_dist}"
                )
                return {
                    "start_station": start_station,
                    "end_station": end_station,
                    "total_distance": current_dist,
                    "visited": visited,
                    "previous": previous,
                    "end_state": (current_station, current_line),
                    "transfers": transfers,
                }

            # Skip if exceeds max transfers
            if transfers > max_transfers:
                continue

            # Explore adjacent stations
            adjacent = self.graph.get_adjacent_stations(current_station, current_line)

            for next_station, next_line, travel_time in adjacent:
                if (next_station, next_line) in visited:
                    continue

                # Check if this is a transfer (changing lines)
                is_transfer = next_line != current_line

                # Calculate weight (cost of this edge)
                if weight_func:
                    edge_weight = weight_func(
                        current_station, next_station, current_line, next_line, travel_time, is_transfer
                    )
                else:
                    edge_weight = travel_time

                new_distance = current_dist + edge_weight
                new_transfers = transfers + (1 if is_transfer else 0)

                # Update distance if this is a better path
                if (next_station, next_line) not in distances or new_distance < distances[
                    (next_station, next_line)
                ]:
                    distances[(next_station, next_line)] = new_distance
                    previous[(next_station, next_line)] = (
                        (current_station, current_line),
                        travel_time,
                        is_transfer,
                    )

                    heapq.heappush(pq, (new_distance, next_station, next_line, new_transfers))

        logger.error(f"   No path found starting from {start_station} on line {current_line}")
        return None

    def _extract_route(self, path_info: Dict) -> Dict:
        """
        Extract route information from Dijkstra result.

        Args:
            path_info: Result from _dijkstra()

        Returns:
            Route dictionary with stations, lines, and metadata
        """
        # Backtrack from end to start
        stations = []
        lines = []
        segments = []
        current = path_info["end_state"]
        total_time = 0
        total_transfers = 0

        while current in path_info["previous"]:
            prev, travel_time, is_transfer = path_info["previous"][current]
            stations.insert(0, current[0])
            lines.insert(0, current[1])
            total_time += travel_time
            if is_transfer:
                total_transfers += 1
            current = prev

        # Add start station
        stations.insert(0, current[0])
        lines.insert(0, current[1])

        # Remove duplicate lines (keep only unique line transitions)
        unique_lines = []
        for line in lines:
            if not unique_lines or unique_lines[-1] != line:
                unique_lines.append(line)

        # Build segments (line segments between transfers)
        segment_stations = [stations[0]]
        segment_line = lines[0]

        for i in range(1, len(stations)):
            if lines[i] != segment_line:
                # Transfer point
                segments.append(
                    {
                        "line": segment_line,
                        "from": segment_stations[0],
                        "to": segment_stations[-1],
                        "stops": len(segment_stations) - 1,
                        "time_minutes": sum(
                            [2] * (len(segment_stations) - 1)
                        ),  # Estimate 2 min per stop
                    }
                )
                segments.append(
                    {
                        "type": "transfer",
                        "station": stations[i],
                        "from_line": segment_line,
                        "to_line": lines[i],
                        "time_minutes": 2,
                    }
                )
                segment_stations = [stations[i]]
                segment_line = lines[i]
            else:
                segment_stations.append(stations[i])

        # Add final segment
        if segment_stations:
            segments.append(
                {
                    "line": segment_line,
                    "from": segment_stations[0],
                    "to": segment_stations[-1],
                    "stops": len(segment_stations) - 1,
                    "time_minutes": sum([2] * (len(segment_stations) - 1)),
                }
            )

        return {
            "stations": stations,
            "lines": unique_lines,
            "segments": segments,
            "total_time_minutes": total_time,
            "total_transfers": total_transfers,
            "total_stops": len(stations),
        }


# ============================================================================
# DEFAULT WEIGHT FUNCTIONS
# ============================================================================


def weight_time_only(current: str, next_station: str, current_line: str, next_line: str, travel_time: int, is_transfer: bool) -> float:
    """
    Weight function: minimize travel time only.
    Returns the travel time as the edge weight.
    """
    return float(travel_time)


def weight_with_transfer_penalty(
    current: str, next_station: str, current_line: str, next_line: str, travel_time: int, is_transfer: bool, penalty: float = 5.0
) -> float:
    """
    Weight function: minimize travel time + transfer penalty.
    """
    weight = float(travel_time)
    if is_transfer:
        weight += penalty
    return weight


def weight_with_crime(
    current: str,
    next_station: str,
    current_line: str,
    next_line: str,
    travel_time: int,
    is_transfer: bool,
    crime_data: Dict[str, int],
) -> float:
    """
    Weight function: penalize high-crime stations and transfers.

    Args:
        crime_data: Dictionary mapping station name to crime incident count
        is_transfer: Whether this edge involves a line transfer
    """
    crimes = crime_data.get(next_station, 5)
    crime_multiplier = 1.0 + (crimes / 10.0)  # 0 crimes = 1.0x, 10 crimes = 2.0x
    weight = float(travel_time * crime_multiplier)

    if is_transfer:
        weight += 5.0  # Penalize transfers

    return weight
