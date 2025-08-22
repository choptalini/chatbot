"""
Lightweight geocoding helpers for reverse-geocoding coordinates and building
maps links. Wraps the same logic used in scripts/reverse_geocode_google_test.py
so production code can import without depending on the script path.
"""

from typing import Dict, Any, Optional, Tuple, List
import os


def _component(components, *types) -> Optional[str]:
    for c in components or []:
        if any(t in c.get("types", []) for t in types):
            return c.get("long_name")
    return None


def reverse_geocode(lat: float, lon: float, language: str = "en", region: Optional[str] = None) -> Dict[str, Any]:
    """Reverse-geocode lat/lon via Google Geocoding API and return normalized fields.

    Returns a dict with shape { success: bool, data?: {...}, error?: str }
    The data payload mirrors the test script, including address lines and props.
    """
    api_key = os.getenv("GOOGLE_MAPS_API")
    if not api_key:
        return {"success": False, "error": "Missing GOOGLE_MAPS_API env var"}

    try:
        import googlemaps  # Imported lazily
    except Exception as e:
        return {"success": False, "error": f"googlemaps import failed: {e}"}

    gmaps = googlemaps.Client(key=api_key)
    params: Dict[str, Any] = {
        "latlng": (lat, lon),
        "language": language,
        "result_type": [
            "street_address",
            "premise",
            "subpremise",
            "establishment",
            "point_of_interest",
        ],
        "location_type": [
            "ROOFTOP",
            "RANGE_INTERPOLATED",
        ],
    }

    try:
        results = gmaps.reverse_geocode(**params)
    except Exception as e:
        return {"success": False, "error": f"reverse_geocode error: {e}"}

    if not results:
        return {"success": False, "error": "No results"}

    r = _select_best_reverse_result(results)
    comps = r.get("address_components", [])
    norm = {
        "formatted": r.get("formatted_address"),
        "street_number": _component(comps, "street_number"),
        "route": _component(comps, "route"),
        "subpremise": _component(comps, "subpremise"),
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
        "building_name": None,
    }

    # Fallback postal code
    if not norm["postal_code"]:
        try:
            res_pc = gmaps.reverse_geocode(latlng=(lat, lon), language=language, result_type=["postal_code"]) or []
            if res_pc:
                comps_pc = res_pc[0].get("address_components", [])
                pc = _component(comps_pc, "postal_code")
                if pc:
                    norm["postal_code"] = pc
        except Exception:
            pass

    # Enrich with Place Details for building name if missing
    if not norm.get("premise") or not norm.get("street_number"):
        try:
            bname, bplace_id = _nearest_building_name(gmaps, lat, lon, language, region)
        except Exception:
            bname, bplace_id = (None, None)
        if bname:
            norm["building_name"] = bname
            if not norm.get("premise"):
                norm["premise"] = bname
            if not norm.get("route") and bplace_id:
                try:
                    p = gmaps.place(place_id=bplace_id, language=language, fields=["address_component"]) or {}
                    ac = (p.get("result") or {}).get("address_components", [])
                    maybe_route = _component(ac, "route")
                    if maybe_route:
                        norm["route"] = maybe_route
                except Exception:
                    pass

    # Compose address lines
    if norm.get("street_number") and norm.get("route"):
        address1_parts = [norm["street_number"], norm["route"]]
    elif norm.get("premise") and norm.get("route"):
        address1_parts = [norm["premise"], norm["route"]]
    elif norm.get("route"):
        address1_parts = [norm["route"]]
    elif norm.get("premise"):
        address1_parts = [norm["premise"]]
    else:
        address1_parts = []
    norm["address1"] = " ".join([p for p in address1_parts if p]).strip() or None
    norm["address2"] = norm.get("subpremise") or norm.get("neighborhood")

    return {"success": True, "data": norm, "raw": r}


def _select_best_reverse_result(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not results:
        return {}
    preferred_types = {"street_address", "premise", "subpremise", "establishment", "point_of_interest"}

    def score(res: Dict[str, Any]) -> Tuple[int, int]:
        types = set(res.get("types", []))
        geom = res.get("geometry", {})
        loc_type = (geom.get("location_type") or "").upper()
        type_score = 2 if types & preferred_types else 0
        rooftop_score = 1 if loc_type == "ROOFTOP" else 0
        return (type_score, rooftop_score)

    return max(results, key=score)


def directions_links(lat: float, lon: float) -> Dict[str, str]:
    return {
        "google_maps_place": f"https://www.google.com/maps?q={lat},{lon}",
        "google_maps_directions": f"https://www.google.com/maps/dir/?api=1&destination={lat}%2C{lon}&travelmode=driving",
    }


def _nearest_building_name(
    gmaps,
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
            radius=30,
            language=language,
        ) or {}
        candidates = nearby.get("results", [])
        if not candidates:
            return None, None

        def nscore(place: Dict[str, Any]) -> Tuple[int, int, int]:
            types = set(place.get("types", []))
            type_bonus = 2 if ("premise" in types or "point_of_interest" in types or "establishment" in types) else 0
            name_bonus = 1 if place.get("name") else 0
            rating_bonus = 1 if place.get("user_ratings_total", 0) > 0 else 0
            return (type_bonus, name_bonus, rating_bonus)

        best = max(candidates, key=nscore)
        bname = best.get("name")
        bpid = best.get("place_id")
        if bpid and not bname:
            try:
                details = gmaps.place(place_id=bpid, language=language, fields=["name"]) or {}
                bname = (details.get("result") or {}).get("name")
            except Exception:
                pass
        return (bname, bpid)
    except Exception:
        return None, None

