#!/usr/bin/env python3
"""
Static mapping of NYC subway station names to MTA stop IDs
Used to bootstrap real-time travel time calculations while Phase 1 data loads
"""

# Comprehensive mapping of station names to MTA stop IDs
# Stop IDs follow pattern: line + direction + stop_code (e.g., "229S" = Line 2/3, South, Stop 229)
STATION_TO_STOP_ID = {
    # Line 1 (Red) - Local and Express
    "Van Cortlandt Park 242nd St": "101S",
    "231st St": "102S",
    "207th St": "103S",
    "Dyckman St": "104S",
    "125th St": "105S",
    "96th St": "106S",
    "72nd St": "107S",
    "Times Square-42nd St": "108S",
    "34th St-Penn Station": "109S",
    "14th St": "110S",
    "Franklin St": "111S",
    "Canal St": "112S",
    "Park Place": "113S",
    "Chambers St": "114S",
    "Fulton St": "115S",
    "Wall St": "116S",
    "Bowling Green": "117S",

    # Line 2/3 (Red) - Express/Local
    "Wakefield-241st St": "201S",
    "Pelham Parkway": "202S",
    "Hunts Point Ave": "203S",
    "149th St-Grand Concourse": "204S",
    "125th St": "205S",
    "96th St": "206S",
    "72nd St": "207S",
    "Times Square-42nd St": "208S",
    "34th St": "209S",
    "14th St": "210S",
    "Chambers St": "212S",
    "Fulton St": "213S",
    "Park Place": "214S",
    "Wall St": "215S",
    "Bowling Green": "216S",

    # Line 4/5 (Green) - Express/Local
    "Bowling Green": "401S",
    "Whitehall St-South Ferry": "402S",
    "Bowling Green": "403S",
    "Wall St": "404S",
    "Fulton St": "405S",
    "Park Place": "406S",
    "Chambers St": "407S",
    "Brooklyn Bridge-City Hall": "408S",
    "Canal St": "409S",
    "Franklin St": "410S",
    "Chambers St": "411S",
    "14th St": "412S",
    "34th St-Herald Sq": "413S",
    "42nd St-Port Authority": "414S",
    "72nd St": "415S",
    "96th St": "416S",
    "125th St": "417S",
    "145th St": "418S",
    "168th St": "419S",
    "Dyckman St": "420S",
    "Inwood-207th St": "421S",

    # Line A/C (Blue) - Local/Express
    "Inwood-207th St": "A01S",
    "Dyckman St": "A02S",
    "125th St": "A03S",
    "59th St-Columbus Circle": "A04S",
    "42nd St-Port Authority": "A05S",
    "34th St": "A06S",
    "14th St": "A07S",
    "Spring St": "A08S",
    "Canal St": "A09S",
    "Chambers St": "A10S",
    "Fulton St": "A11S",
    "Broadway-Nassau": "A12S",
    "High St-Brooklyn Bridge": "A13S",
    "Jay St-MetroTech": "A14S",
    "Hoyt-Schermerhorn Sts": "A15S",
    "Atlantic Av-Barclays Ctr": "A16S",

    # Line E (Blue) - Local
    "42nd St-Port Authority": "E01S",
    "34th St": "E02S",
    "23rd St": "E03S",
    "14th St": "E04S",
    "W4th St": "E05S",
    "Spring St": "E06S",
    "Canal St": "E07S",
    "Chambers St": "E08S",

    # Line N/Q/R/W (Yellow) - Local/Express
    "Astoria-Ditmars Blvd": "N01N",
    "30th Ave": "N02N",
    "Broadway": "N03N",
    "39th Ave": "N04N",
    "36th Ave": "N05N",
    "Queensboro Plaza": "N06N",
    "Lexington Ave-59th St": "N07N",
    "5th Ave": "N08N",
    "34th St-Herald Sq": "N09N",
    "23rd St": "N10N",
    "14th St": "N11N",
    "Canal St": "N12N",
    "Chambers St": "N13N",
    "Cortlandt St": "N14N",
    "Fulton St": "N15N",

    # Line S (42nd Street Shuttle)
    "42nd St-Grand Central": "S01N",
    "Times Square-42nd St": "S02N",

    # Line B/D (Orange) - Express/Local
    "205th St": "B01N",
    "181st St": "B02N",
    "Dyckman St": "B03N",
    "125th St": "B04N",
    "59th St-Columbus Circle": "B05N",
    "47th-50th Sts-Rockefeller Ctr": "B06N",
    "42nd St": "B07N",
    "34th St": "B08N",
    "23rd St": "B09N",
    "14th St": "B10N",
    "W4th St": "B11N",
    "Spring St": "B12N",
    "Broadway-Lafayette": "B13N",
    "Grand St": "B14N",

    # Line F/M (Orange) - Local
    "Jamaica-179th St": "F01N",
    "Parsons Blvd": "F02N",
    "Forest Hills-71 Ave": "F03N",
    "71st Ave": "F04N",
    "65th St": "F05N",
    "63rd Dr-Rego Park": "F06N",
    "57th St": "F07N",
    "Lexington Ave-53rd St": "F08N",
    "42nd St": "F09N",
    "34th St": "F10N",
    "23rd St": "F11N",
    "14th St": "F12N",
    "W4th St": "F13N",
    "Spring St": "F14N",
    "Broadway-Lafayette": "F15N",
    "Delancey St-Essex St": "F16N",

    # Line G (Light Green) - Local
    "Court Sq": "G01N",
    "Queensboro Plaza": "G02N",
    "Long Island City-Court Sq": "G03N",
    "Astoria Blvd": "G04N",
    "Ditmars Blvd": "G05N",
    "Nassau Ave": "G06N",
    "Metropolitan Ave": "G07N",
    "Broadway": "G08N",
    "Myrtle Ave": "G09N",
    "Myrtle-Willoughby Aves": "G10N",
    "Clinton-Washington Aves": "G11N",
    "Classon Ave": "G12N",
    "Atlantic Ave-Barclays Ctr": "G13N",
    "Hoyt-Schermerhorn Sts": "G14N",
    "Jay St-MetroTech": "G15N",

    # Line L (Gray) - Local
    "8th Ave": "L01N",
    "6th Ave": "L02N",
    "14th St": "L03N",
    "Union Sq-14th St": "L04N",
    "1st Ave": "L05N",
    "Avenue A": "L06N",
    "Lorimer St": "L07N",
    "Graham Ave": "L08N",
    "Jefferson St": "L09N",
    "Canarsie-Rockaway Pkwy": "L10N",

    # Line Z (Brown) - Express
    "Jamaica Center-Parsons/Archer": "Z01N",
    "Marcy Ave": "Z02N",
    "Myrtle Ave": "Z03N",
    "Broadway": "Z04N",

    # Additional shuttle and key transfer points
    "42nd St-Grand Central": "229N",
    "Times Square-42nd St": "229S",
    "Grand Central-42nd St": "225N",

    # AirTrain (connecting to JFK/Newark)
    "Jamaica Station": "AJ01N",
    "Howard Beach": "HB01N",
}


def get_stop_id_for_station(station_name: str) -> str:
    """
    Get MTA stop ID for a station name
    Supports both exact matches and fuzzy matching

    Args:
        station_name: User-provided station name

    Returns:
        MTA stop ID if found, else None
    """
    # First try exact match
    if station_name in STATION_TO_STOP_ID:
        return STATION_TO_STOP_ID[station_name]

    # Try case-insensitive match
    station_lower = station_name.lower()
    for name, stop_id in STATION_TO_STOP_ID.items():
        if name.lower() == station_lower:
            return stop_id

    # Try substring matching
    for name, stop_id in STATION_TO_STOP_ID.items():
        if station_lower in name.lower() or name.lower() in station_lower:
            return stop_id

    return None


def get_all_stations():
    """Get list of all mapped station names"""
    return list(STATION_TO_STOP_ID.keys())
