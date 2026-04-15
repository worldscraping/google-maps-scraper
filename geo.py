import logging
import math

import requests

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {
    "User-Agent": "MagneticProxy-GoogleMapsScraper/1.0",
}


def geocode_city(city_name):
    params = {
        "q": city_name,
        "format": "json",
        "limit": 1,
    }
    response = requests.get(NOMINATIM_URL, params=params, headers=NOMINATIM_HEADERS, timeout=15)
    response.raise_for_status()

    results = response.json()
    if not results:
        raise ValueError(f"Could not geocode city: {city_name}")

    result = results[0]
    bbox = [float(x) for x in result["boundingbox"]]

    return {
        "lat": float(result["lat"]),
        "lon": float(result["lon"]),
        "display_name": result.get("display_name", city_name),
        "bbox": {
            "min_lat": bbox[0],
            "max_lat": bbox[1],
            "min_lon": bbox[2],
            "max_lon": bbox[3],
        },
    }


def generate_grid(bbox, cell_size_km=2.0):
    min_lat = bbox["min_lat"]
    max_lat = bbox["max_lat"]
    min_lon = bbox["min_lon"]
    max_lon = bbox["max_lon"]

    center_lat = (min_lat + max_lat) / 2
    lat_step = cell_size_km / 111.0
    lon_step = cell_size_km / (111.0 * math.cos(math.radians(center_lat)))

    # Overlap: reduce step by 15% so adjacent cells share edges
    lat_step *= 0.85
    lon_step *= 0.85

    viewport_meters = cell_size_km * 1000

    cells = []
    cell_id = 0
    lat = min_lat + lat_step / 2
    while lat < max_lat:
        lon = min_lon + lon_step / 2
        while lon < max_lon:
            cells.append({
                "cell_id": cell_id,
                "lat": round(lat, 6),
                "lng": round(lon, 6),
                "viewport_meters": viewport_meters,
            })
            cell_id += 1
            lon += lon_step
        lat += lat_step

    logger.info(
        "Generated grid: %d cells (%.1f km each) for bbox [%.4f,%.4f]-[%.4f,%.4f]",
        len(cells), cell_size_km, min_lat, min_lon, max_lat, max_lon,
    )
    return cells
