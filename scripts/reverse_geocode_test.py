#!/usr/bin/env python3
"""
Quick reverse-geocoding test using geopy + Nominatim.

Usage: python scripts/reverse_geocode_test.py
"""

import sys
from typing import Dict, Any

try:
    from geopy.geocoders import Nominatim
except Exception as e:
    print("geopy is not installed. Please install with: pip install geopy", file=sys.stderr)
    raise


def normalize_address(addr: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize Nominatim address dict to common fields."""
    def pick(*keys):
        for k in keys:
            v = addr.get(k)
            if v:
                return v
        return None

    # Compose street line using building/house number and preferred road-like keys
    address1 = " ".join(
        filter(
            None,
            [
                addr.get("building"),
                addr.get("house_number"),
                addr.get("road")
                or addr.get("residential")
                or addr.get("pedestrian")
                or addr.get("footway")
                or addr.get("path"),
            ],
        )
    ).strip()
    if not address1:
        address1 = pick("road", "residential", "pedestrian", "path", "footway", "cycleway")

    address2 = pick("neighbourhood", "suburb", "hamlet", "residential")
    city = pick("city", "town", "village", "municipality", "county")
    province = pick("state", "region")
    country = pick("country")
    postal_code = pick("postcode")

    return {
        "address1": address1,
        "address2": address2,
        "city": city,
        "province": province,
        "country": country,
        "postal_code": postal_code,
    }


def main() -> int:
    # Provided coordinates
    lat = 34.001084
    lon = 35.650442

    print(f"Testing reverse geocode for: lat={lat}, lon={lon}")

    geolocator = Nominatim(user_agent="swiftreplies-revgeo-test")
    # Request richer details from Nominatim
    location = geolocator.reverse(
        (lat, lon), language="en", timeout=15, addressdetails=True, namedetails=True, zoom=18
    )

    if not location:
        print("No result from Nominatim")
        return 1

    print("\nFull formatted (provider display_name):")
    print(location.address)

    addr = location.raw.get("address", {}) if isinstance(location.raw, dict) else {}
    norm = normalize_address(addr)

    print("\nNormalized components (street-level):")
    for k, v in norm.items():
        print(f"- {k}: {v}")

    # Build a human-friendly full street address line from normalized components
    parts = [
        norm.get("address1"),
        norm.get("address2"),
        ", ".join(filter(None, [norm.get("city"), norm.get("province")])),
        norm.get("postal_code"),
        norm.get("country"),
    ]
    full_street_address = ", ".join([p for p in parts if p])
    print("\nFull street address (normalized):")
    print(full_street_address or location.address)

    gmaps_place_url = f"https://www.google.com/maps?q={lat},{lon}"
    gmaps_dir_url = f"https://www.google.com/maps/dir/?api=1&destination={lat}%2C{lon}&travelmode=driving"
    osm_map_url = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}"
    print("\nMap & directions:")
    print(f"- Google Maps (place): {gmaps_place_url}")
    print(f"- Google Maps (directions to): {gmaps_dir_url}")
    print(f"- OpenStreetMap (map): {osm_map_url}")

    # Brief notes
    print("\nNotes:")
    print("- Nominatim is free but rate-limited; suitable for light usage/dev.")
    print("- For production/SLAs, consider Google Maps, OpenCage, Mapbox, or self-hosted Nominatim.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

