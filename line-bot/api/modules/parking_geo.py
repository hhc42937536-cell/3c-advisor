"""Geographic helpers for parking lookups."""

from __future__ import annotations

import math


TW_CITY_BOXES = [
    (25.044, 25.210, 121.460, 121.666, "Taipei"),
    (25.091, 25.199, 121.677, 121.803, "Keelung"),
    (24.779, 24.852, 120.921, 121.018, "Hsinchu"),
    (24.679, 24.832, 120.893, 121.082, "HsinchuCounty"),
    (24.683, 24.870, 120.620, 120.982, "MiaoliCounty"),
    (24.820, 25.076, 121.139, 121.474, "Taoyuan"),
    (23.958, 24.389, 120.530, 121.100, "Taichung"),
    (23.750, 24.150, 120.309, 120.745, "ChanghuaCounty"),
    (23.308, 23.870, 120.440, 121.070, "NantouCounty"),
    (23.501, 23.830, 120.090, 120.722, "YunlinCounty"),
    (23.443, 23.521, 120.409, 120.520, "Chiayi"),
    (23.100, 23.580, 120.180, 120.795, "ChiayiCounty"),
    (22.820, 23.450, 120.020, 120.763, "Tainan"),
    (22.447, 23.140, 120.160, 120.780, "Kaohsiung"),
    (21.901, 22.809, 120.393, 120.904, "PingtungCounty"),
    (23.000, 24.500, 121.280, 121.720, "HualienCounty"),
    (22.200, 23.500, 120.851, 121.554, "TaitungCounty"),
    (23.200, 23.800, 119.300, 119.750, "PenghuCounty"),
    (24.300, 25.050, 121.500, 122.000, "YilanCounty"),
    (24.045, 25.176, 121.120, 122.075, "NewTaipei"),
]

TW_CITY_CENTERS = {
    "Taipei": (25.047, 121.517),
    "Keelung": (25.129, 121.740),
    "NewTaipei": (25.012, 121.465),
    "Taoyuan": (24.993, 121.301),
    "Hsinchu": (24.804, 120.971),
    "HsinchuCounty": (24.839, 121.017),
    "MiaoliCounty": (24.560, 120.820),
    "Taichung": (24.147, 120.674),
    "ChanghuaCounty": (24.052, 120.516),
    "NantouCounty": (23.960, 120.972),
    "YunlinCounty": (23.707, 120.431),
    "Chiayi": (23.480, 120.449),
    "ChiayiCounty": (23.459, 120.432),
    "Tainan": (22.999, 120.211),
    "Kaohsiung": (22.627, 120.301),
    "PingtungCounty": (22.674, 120.490),
    "YilanCounty": (24.700, 121.738),
    "HualienCounty": (23.991, 121.611),
    "TaitungCounty": (22.757, 121.144),
    "PenghuCounty": (23.571, 119.579),
}


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """Distance between two geo points in meters."""
    earth_radius_m = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return int(earth_radius_m * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def coords_to_tdx_city(lat: float, lon: float) -> str:
    """Map coordinates to a TDX city path name."""
    candidates = []
    for lat_min, lat_max, lon_min, lon_max, city in TW_CITY_BOXES:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            candidates.append(city)

    if not candidates:
        return "Taipei"
    if len(candidates) == 1:
        return candidates[0]

    best, best_d = candidates[0], float("inf")
    for city in candidates:
        center_lat, center_lon = TW_CITY_CENTERS.get(city, (25.047, 121.517))
        distance = (lat - center_lat) ** 2 + (lon - center_lon) ** 2
        if distance < best_d:
            best_d = distance
            best = city
    return best


def twd97tm2_to_wgs84(x: float, y: float):
    """Convert TWD97 TM2 Zone 121 coordinates to WGS84 lat/lon."""
    lat = y / 110540.0
    lat_rad = math.radians(lat)
    lon = 121.0 + (x - 250000.0) / (111320.0 * math.cos(lat_rad))
    return lat, lon
