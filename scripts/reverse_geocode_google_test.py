#!/usr/bin/env python3
"""
Reverse geocoding test using Google Maps Geocoding API.

Reads API key from env var GOOGLE_MAPS_API.
Usage: python scripts/reverse_geocode_google_test.py
"""

import os
import sys
from typing import Dict, Any, Optional, List, Tuple

try:
    import googlemaps
except Exception as e:
    print("googlemaps is not installed. Please install with: pip install googlemaps", file=sys.stderr)
    raise

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _component(components, *types) -> Optional[str]:
    for c in components:
        if any(t in c.get("types", []) for t in types):
            return c.get("long_name")
    return None


def reverse_geocode(lat: float, lon: float, language: str = "en", region: Optional[str] = None) -> Dict[str, Any]:
    """Reverse-geocode lat/lon via Google APIs and return detailed, normalized fields.

    Strategy for building-level precision (best-effort):
    1) Geocoding API reverse lookup with strong filters:
       - result_type: street_address | premise | subpremise | establishment | point_of_interest
       - location_type: ROOFTOP preferred
       - extra_computations: BUILDING_AND_ENTRANCES, ADDRESS_DESCRIPTORS (best-effort passthrough)
    2) If no street number or named building is found, fallback to Places Nearby (<= 30m)
       + Place Details to extract a building name to enrich the address.
    """
    api_key = os.getenv("GOOGLE_MAPS_API")
    if not api_key:
        return {"success": False, "error": "Missing GOOGLE_MAPS_API env var"}

    gmaps = googlemaps.Client(key=api_key)
    # Note: reverse_geocode supports post-filtering via result_type/location_type.
    # Region bias isn't supported on reverse_geocode in the python client.
    params: Dict[str, Any] = {
        "latlng": (lat, lon),
        "language": language,
        # Prefer highly-specific results
        "result_type": [
            "street_address",
            "premise",
            "subpremise",
            "establishment",
            "point_of_interest",
        ],
        "location_type": [
            "ROOFTOP",
            # Allow a fallback to interpolated range if rooftop is missing
            "RANGE_INTERPOLATED",
        ],
    }
    # Do not pass 'region' here; not supported by googlemaps reverse_geocode

    res = gmaps.reverse_geocode(**params)
    if not res:
        return {"success": False, "error": "No results"}

    # Prefer the first ROOFTOP + building-level type if available
    r = _select_best_reverse_result(res)
    comps = r.get("address_components", [])
    norm = {
        "formatted": r.get("formatted_address"),
        "street_number": _component(comps, "street_number"),
        "route": _component(comps, "route"),
        "subpremise": _component(comps, "subpremise"),
        # 'premise' is the building name in many countries
        "premise": _component(comps, "premise"),
        "neighborhood": _component(comps, "neighborhood", "sublocality", "sublocality_level_1"),
        "locality": _component(comps, "locality", "postal_town"),
        "admin_area_2": _component(comps, "administrative_area_level_2"),
        "admin_area_1": _component(comps, "administrative_area_level_1"),
        "country": _component(comps, "country"),
        "postal_code": _component(comps, "postal_code"),
        "place_id": r.get("place_id"),
        "types": r.get("types", []),
        "location": r.get("geometry", {}).get("location"),
        "location_type": r.get("geometry", {}).get("location_type"),
        "plus_code": r.get("plus_code", {}).get("global_code"),
        # Enrichment fields
        "building_name": None,
    }

    # Fallback: if postal code missing, try a second reverse lookup constrained to postal_code
    if not norm["postal_code"]:
        try:
            res_pc = gmaps.reverse_geocode(latlng=(lat, lon), language=language, result_type=["postal_code"])
            if res_pc:
                comps_pc = res_pc[0].get("address_components", [])
                pc = _component(comps_pc, "postal_code")
                if pc:
                    norm["postal_code"] = pc
        except Exception:
            pass
    # Enrich with Place Details for building name if missing
    if not norm.get("premise") or not norm.get("street_number"):
        bname, bplace_id = _nearest_building_name(gmaps, lat, lon, language, region)
        if bname:
            norm["building_name"] = bname
            # If we didn't get a 'premise' from geocoder, store from Places
            if not norm.get("premise"):
                norm["premise"] = bname
            # If route is missing, try to read it from that place's details
            if not norm.get("route") and bplace_id:
                try:
                    p = gmaps.place(place_id=bplace_id, language=language, fields=["address_component"]) or {}
                    ac = (p.get("result") or {}).get("address_components", [])
                    maybe_route = _component(ac, "route")
                    if maybe_route:
                        norm["route"] = maybe_route
                except Exception:
                    pass

    # Compose normalized street line and secondary line
    # Prefer explicit street_number + route; if absent, fall back to building name + route
    line1_parts: List[str] = []
    if norm.get("street_number") and norm.get("route"):
        line1_parts = [norm["street_number"], norm["route"]]
    elif norm.get("premise") and norm.get("route"):
        line1_parts = [norm["premise"], norm["route"]]
    elif norm.get("route"):
        line1_parts = [norm["route"]]
    elif norm.get("premise"):
        line1_parts = [norm["premise"]]
    norm["address1"] = " ".join(filter(None, line1_parts)).strip() or None
    # address2 prioritizes subpremise (apt/unit), else neighborhood/sublocality
    norm["address2"] = norm.get("subpremise") or norm.get("neighborhood")

    return {"success": True, "data": norm, "raw": r}


def directions_links(lat: float, lon: float) -> Dict[str, str]:
    return {
        "google_maps_place": f"https://www.google.com/maps?q={lat},{lon}",
        "google_maps_directions": f"https://www.google.com/maps/dir/?api=1&destination={lat}%2C{lon}&travelmode=driving",
    }


def _select_best_reverse_result(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Choose the best reverse geocode result favoring building/rooftop precision."""
    if not results:
        return {}
    preferred_types = {"street_address", "premise", "subpremise"}

    def score(res: Dict[str, Any]) -> Tuple[int, int]:
        types = set(res.get("types", []))
        geom = res.get("geometry", {})
        loc_type = (geom.get("location_type") or "").upper()
        # Higher score for preferred types and for ROOFTOP
        type_score = 2 if types & preferred_types else (1 if "establishment" in types or "point_of_interest" in types else 0)
        rooftop_score = 1 if loc_type == "ROOFTOP" else 0
        return (type_score, rooftop_score)

    return max(results, key=score)


def _nearest_building_name(
    gmaps: "googlemaps.Client",
    lat: float,
    lon: float,
    language: str,
    region: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Search very close-by Places to infer a building name when street numbers are missing.

    Returns: (building_name, place_id)
    """
    try:
        nearby = gmaps.places_nearby(
            location=(lat, lon),
            radius=30,  # ~30m radius to keep only the building we're on
            language=language,
            # Avoid over-filtering; we'll score results below
        ) or {}
        candidates = nearby.get("results", [])
        if not candidates:
            return None, None

        # Prefer closer and with strong signals
        def nscore(place: Dict[str, Any]) -> Tuple[int, int, int]:
            types = set(place.get("types", []))
            # Favor places that look like buildings or establishments
            type_bonus = 2 if ("premise" in types or "point_of_interest" in types or "establishment" in types) else 0
            name_bonus = 1 if place.get("name") else 0
            rating_bonus = 1 if place.get("user_ratings_total", 0) > 0 else 0
            return (type_bonus, name_bonus, rating_bonus)

        best = max(candidates, key=nscore)
        bname = best.get("name")
        bpid = best.get("place_id")
        # Validate/expand via Place Details when available
        if bpid and not bname:
            try:
                details = gmaps.place(place_id=bpid, language=language, fields=["name"]) or {}
                bname = (details.get("result") or {}).get("name")
            except Exception:
                pass
        return (bname, bpid)
    except Exception:
        return None, None


def main() -> int:
    # Provided coordinates (DD): 33.8858647899, 35.5191179235
    lat, lon = 33.983569656899974, 35.624065640413

    print(f"Testing Google reverse geocode for: lat={lat}, lon={lon}")
    out = reverse_geocode(lat, lon, language="en", region="LB")
    if not out.get("success"):
        print("Error:", out.get("error"))
        return 1

    data = out["data"]
    print("\nGoogle formatted address:")
    print(data.get("formatted"))

    print("\nNormalized components:")
    for k in [
        "address1",
        "address2",
        "premise",
        "building_name",
        "locality",
        "admin_area_1",
        "postal_code",
        "country",
        "place_id",
        "location_type",
    ]:
        print(f"- {k}: {data.get(k)}")

    print("\nFull street address (normalized):")
    parts = [
        data.get("address1"),
        data.get("address2"),
        ", ".join(filter(None, [data.get("locality"), data.get("admin_area_1")])),
        data.get("postal_code"),
        data.get("country"),
    ]
    full_line = ", ".join([p for p in parts if p])
    print(full_line or data.get("formatted"))

    print("\nMap & directions:")
    links = directions_links(lat, lon)
    for name, url in links.items():
        print(f"- {name}: {url}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

