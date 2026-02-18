#!/usr/bin/env python3
"""
Address Resolver - Converts addresses to subway station suggestions
Uses Google Maps Geocoding API to convert addresses to coordinates,
then finds nearby subway stations using Haversine distance formula.
"""

import logging
import os
import json
import urllib.request
import urllib.parse
from typing import List, Dict, Optional
from math import radians, cos, sin, asin, sqrt

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Import station data
from nyc_stations import NYC_STATIONS, get_station_by_coordinates


class AddressResolver:
    """
    Resolves addresses to nearby subway stations.
    Supports both Google Maps Geocoding API (primary) and OpenStreetMap Nominatim API (fallback).
    """

    def __init__(self, google_maps_api_key: Optional[str] = None, use_nominatim_fallback: bool = True):
        """
        Initialize AddressResolver with optional Google Maps API key.

        Args:
            google_maps_api_key: Google Maps Geocoding API key (optional)
            use_nominatim_fallback: Use OpenStreetMap Nominatim as fallback if no Google key (default: True)
        """
        self.api_key = google_maps_api_key
        self.use_nominatim = use_nominatim_fallback or not google_maps_api_key

        if self.api_key:
            self.geocoding_url = "https://maps.googleapis.com/maps/api/geocode/json"
            self.provider = "Google Maps"
            logger.info("✅ AddressResolver initialized with Google Maps API")
        elif self.use_nominatim:
            self.geocoding_url = "https://nominatim.openstreetmap.org/search"
            self.provider = "OpenStreetMap Nominatim (free)"
            logger.info("✅ AddressResolver initialized with OpenStreetMap Nominatim (free fallback)")
        else:
            logger.warning("⚠️  AddressResolver initialized without geocoding provider")

    def resolve_address(self, address: str) -> Optional[Dict]:
        """
        Convert an address string to latitude/longitude coordinates.

        Args:
            address: Address string (e.g., "200 East 42nd Street, New York, NY")

        Returns:
            Dictionary with lat/lng, or None if geocoding fails
        """
        try:
            if self.api_key:
                return self._resolve_address_google(address)
            elif self.use_nominatim:
                return self._resolve_address_nominatim(address)
            else:
                logger.error("   ❌ No geocoding provider available")
                return None

        except Exception as e:
            logger.error(f"   ❌ Unexpected error during geocoding: {e}")
            return None

    def _resolve_address_google(self, address: str) -> Optional[Dict]:
        """Geocode using Google Maps API"""
        try:
            params = {
                "address": address,
                "key": self.api_key,
                "components": "country:US|administrative_area:NY"  # Bias to NY
            }

            query_string = urllib.parse.urlencode(params)
            url = f"{self.geocoding_url}?{query_string}"

            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))

            if data.get("status") != "OK" or not data.get("results"):
                logger.warning(f"   Geocoding failed for '{address}': {data.get('status')}")
                return None

            # Get first result (best match)
            location = data["results"][0]["geometry"]["location"]

            result = {
                "address": data["results"][0]["formatted_address"],
                "lat": location["lat"],
                "lng": location["lng"],
                "confidence": data["results"][0].get("geometry", {}).get("location_type", "UNKNOWN")
            }

            logger.info(f"   ✅ (Google) Geocoded '{address}' → ({result['lat']:.4f}, {result['lng']:.4f})")
            return result

        except Exception as e:
            logger.error(f"   ❌ Google Maps API error: {e}")
            return None

    def _resolve_address_nominatim(self, address: str) -> Optional[Dict]:
        """Geocode using OpenStreetMap Nominatim API (free fallback)"""
        try:
            # Nominatim API expects 'q' parameter
            params = {
                "q": f"{address}, New York, NY, USA",
                "format": "json",
                "limit": "1",
                "countrycodes": "us"
            }

            query_string = urllib.parse.urlencode(params)
            url = f"{self.geocoding_url}?{query_string}"

            # Nominatim requires User-Agent header
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "SmartRoute/1.0 (NYC Subway Route Recommender)"}
            )

            with urllib.request.urlopen(request, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))

            if not data or len(data) == 0:
                logger.warning(f"   Nominatim: No results for '{address}'")
                return None

            # Get first result
            result_data = data[0]

            result = {
                "address": result_data.get("display_name", address),
                "lat": float(result_data.get("lat")),
                "lng": float(result_data.get("lon")),
                "confidence": "ROOFTOP"  # Nominatim doesn't provide confidence
            }

            logger.info(f"   ✅ (Nominatim) Geocoded '{address}' → ({result['lat']:.4f}, {result['lng']:.4f})")
            return result

        except Exception as e:
            logger.error(f"   ❌ Nominatim API error: {e}")
            return None

    def find_nearby_stations(
        self,
        lat: float,
        lng: float,
        max_results: int = 3,
        max_distance_km: float = 1.0
    ) -> List[Dict]:
        """
        Find nearby subway stations for given coordinates.

        Args:
            lat: Latitude
            lng: Longitude
            max_results: Maximum number of suggestions to return (default: 3)
            max_distance_km: Maximum distance to search (default: 1.0 km)

        Returns:
            List of nearby stations sorted by distance, with walking time
        """

        def haversine(lat1, lng1, lat2, lng2) -> float:
            """Calculate distance between two coordinates in km"""
            lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
            dlat = lat2 - lat1
            dlng = lng2 - lng1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
            c = 2 * asin(sqrt(a))
            r = 6371  # Radius of Earth in km
            return c * r

        # Calculate distances to all stations
        distances = []
        for station_name, station_info in NYC_STATIONS.items():
            distance = haversine(
                lat, lng,
                station_info["lat"],
                station_info["lng"]
            )

            # Only include stations within max distance
            if distance <= max_distance_km:
                distances.append({
                    "station_name": station_name,
                    "distance_km": round(distance, 2),
                    "walking_time_minutes": max(1, int(distance * 13)),  # ~13 min per km walking speed
                    "lines": sorted(station_info["lines"])
                })

        # Sort by distance
        distances.sort(key=lambda x: x["distance_km"])

        # Return top N results
        results = distances[:max_results]

        logger.info(f"   Found {len(distances)} stations within {max_distance_km} km, "
                   f"returning top {len(results)}")

        return results

    def resolve_address_to_suggestions(
        self,
        address: str,
        max_results: int = 3,
        max_distance_km: float = 1.0
    ) -> Dict:
        """
        Complete address resolution pipeline:
        1. Geocode the address
        2. Find nearby stations
        3. Return formatted suggestions

        Args:
            address: Address string
            max_results: Maximum suggestions to return
            max_distance_km: Maximum distance to search

        Returns:
            Dictionary with suggestions or error message
        """
        logger.info(f"📍 Resolving address: '{address}'")

        # Step 1: Geocode the address
        geocoded = self.resolve_address(address)
        if not geocoded:
            logger.error(f"❌ Could not geocode address: {address}")
            return {
                "success": False,
                "error": "Could not locate that address",
                "suggestions": []
            }

        # Step 2: Find nearby stations
        nearby_stations = self.find_nearby_stations(
            geocoded["lat"],
            geocoded["lng"],
            max_results=max_results,
            max_distance_km=max_distance_km
        )

        logger.info(f"✅ Found {len(nearby_stations)} station suggestions")

        return {
            "success": True,
            "geocoded_address": geocoded["address"],
            "coordinates": {
                "lat": geocoded["lat"],
                "lng": geocoded["lng"]
            },
            "suggestions": nearby_stations
        }


def get_address_resolver() -> Optional[AddressResolver]:
    """
    Factory function to get AddressResolver instance.
    Reads API key from environment variables.
    Falls back to free OpenStreetMap Nominatim API if no API key configured.

    Returns:
        AddressResolver instance with either Google Maps or Nominatim
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")

    if api_key:
        logger.info("📍 Using Google Maps Geocoding API")
        return AddressResolver(google_maps_api_key=api_key, use_nominatim_fallback=False)
    else:
        logger.info("📍 Google Maps API key not set, using free OpenStreetMap Nominatim fallback")
        return AddressResolver(google_maps_api_key=None, use_nominatim_fallback=True)
