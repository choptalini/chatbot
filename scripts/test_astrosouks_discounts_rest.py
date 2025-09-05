#!/usr/bin/env python3
"""
Diagnostic (REST-only): Strictly retrieve discounts/offers without creating orders.

Flow:
- Locate the product by title substring (default: "Bone Conduction").
- Attempt to fetch REST Price Rules that apply to the product/variants.
- If not permitted (403) or unavailable, inspect product/variant metafields and
  heuristically extract volume-pricing tiers (commonly used by discount apps).

Output: only discount information (tiers, value, prerequisites) and variant ids
needed to contextualize the discount. No orders are created.

Environment:
- ASTROSOUKS_SHOPIFY_SHOP_DOMAIN or SHOPIFY_SHOP_DOMAIN
- ASTROSOUKS_SHOPIFY_TOKEN       or SHOPIFY_ACCESS_TOKEN
- Optional: SHOPIFY_API_VERSION (defaults to 2024-10)

Usage:
  python scripts/test_astrosouks_discounts_rest.py
  python scripts/test_astrosouks_discounts_rest.py --query "Bone Conduction"
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import requests
from dotenv import load_dotenv


def _env(key: str, *fallbacks: str, default: Optional[str] = None) -> Optional[str]:
    for k in (key, *fallbacks):
        val = os.getenv(k)
        if val:
            return val
    return default


def _iso_active(starts_at: Optional[str], ends_at: Optional[str]) -> bool:
    """Return True if now is within [starts_at, ends_at] (if provided)."""
    now = datetime.now(timezone.utc)
    def _parse(dt: Optional[str]) -> Optional[datetime]:
        if not dt:
            return None
        try:
            # Shopify returns ISO8601 like "2024-11-30T12:00:00-05:00" or "...Z"
            return datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except Exception:
            return None

    s = _parse(starts_at)
    e = _parse(ends_at)
    if s and now < s:
        return False
    if e and now > e:
        return False
    return True


class RestClient:
    def __init__(self, shop: str, token: str, version: str = "2024-10"):
        self.shop = shop.replace("https://", "").replace("http://", "")
        if not self.shop.endswith(".myshopify.com") and "." not in self.shop:
            self.shop = f"{self.shop}.myshopify.com"
        self.version = version
        self.base = f"https://{self.shop}/admin/api/{self.version}"
        self.session = requests.Session()
        self.session.headers.update({
            "X-Shopify-Access-Token": token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        url = f"{self.base}{path}"
        return self.session.get(url, params=params, timeout=60)

    def iter_pages(self, path: str, root_key: str, params: Optional[Dict[str, Any]] = None):
        url = f"{self.base}{path}"
        while True:
            resp = self.session.get(url, params=params, timeout=60)
            if resp.status_code != 200:
                raise RuntimeError(f"GET {url} failed: {resp.status_code} {resp.text}")
            data = resp.json() if resp.content else {}
            items = data.get(root_key, [])
            for it in items:
                yield it

            link = resp.headers.get("Link")
            if link and 'rel="next"' in link:
                # Link header contains: <https://..../endpoint.json?page_info=...>; rel="next"
                next_url = None
                parts = [p.strip() for p in link.split(',')]
                for p in parts:
                    if 'rel="next"' in p:
                        start = p.find('<')
                        end = p.find('>')
                        if start != -1 and end != -1:
                            next_url = p[start+1:end]
                            break
                if not next_url:
                    break
                url = next_url
                params = None  # URL already has page_info
                # be polite
                time.sleep(0.2)
            else:
                break


def find_product_and_variants_rest(client: RestClient, query: str) -> Optional[Dict[str, Any]]:
    # Fetch products in pages, filter by title contains query (case-insensitive).
    for p in client.iter_pages("/products.json?limit=250", root_key="products"):
        title = (p.get("title") or "").lower()
        if query.lower() in title:
            return p
    return None


def list_price_rules_applying_to(client: RestClient, product_id: int, variant_ids: List[int]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    applicable: List[Dict[str, Any]] = []
    try:
        for rule in client.iter_pages("/price_rules.json?limit=250", root_key="price_rules"):
            # Active window check
            if not _iso_active(rule.get("starts_at"), rule.get("ends_at")):
                continue

            target_type = rule.get("target_type")  # e.g., 'line_item'
            target_selection = rule.get("target_selection")  # 'all' or 'entitled'
            value_type = rule.get("value_type")  # 'percentage' or 'fixed_amount'
            value = rule.get("value")  # negative number as string (e.g., "-10.0")
            allocation_method = rule.get("allocation_method")  # 'each' or 'across'

            entitled_products = set(rule.get("entitled_product_ids", []) or [])
            entitled_variants = set(rule.get("entitled_variant_ids", []) or [])

            applies = False
            if target_selection == "all":
                applies = True
            else:
                if product_id and product_id in entitled_products:
                    applies = True
                if not applies:
                    for vid in variant_ids:
                        if vid in entitled_variants:
                            applies = True
                            break

            if not applies:
                continue

            # Quantity/subtotal prerequisites
            prereq_qty = None
            if isinstance(rule.get("prerequisite_quantity_range"), dict):
                prereq_qty = rule["prerequisite_quantity_range"].get("greater_than_or_equal_to")

            prereq_subtotal = None
            if isinstance(rule.get("prerequisite_subtotal_range"), dict):
                prereq_subtotal = rule["prerequisite_subtotal_range"].get("greater_than_or_equal_to")

            # Normalize value
            discount_desc = None
            try:
                v = abs(float(value)) if value is not None else None
                if value_type == "percentage" and v is not None:
                    discount_desc = f"{v:.0f}% off"
                elif value_type == "fixed_amount" and v is not None:
                    discount_desc = f"${v:.2f} off"
            except Exception:
                discount_desc = str(value)

            applicable.append({
                "id": rule.get("id"),
                "title": rule.get("title"),
                "value_type": value_type,
                "value": value,
                "discount": discount_desc,
                "allocation_method": allocation_method,
                "prerequisite_quantity": prereq_qty,
                "prerequisite_subtotal": prereq_subtotal,
                "starts_at": rule.get("starts_at"),
                "ends_at": rule.get("ends_at"),
            })
    except Exception as e:
        return [], str(e)
    return applicable, None


def list_metafields(client: RestClient, owner: str, owner_id: int) -> List[Dict[str, Any]]:
    """owner in {"products", "variants"} -> GET /{owner}/{id}/metafields.json"""
    path = f"/{owner}/{owner_id}/metafields.json?limit=250"
    try:
        resp = client.get(path)
        if resp.status_code != 200:
            return []
        data = resp.json() if resp.content else {}
        return data.get("metafields", []) or []
    except Exception:
        return []


def extract_discount_tiers_from_metafields(metafields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Heuristically parse metafields likely created by volume-pricing apps.
    Look for namespaces/keys containing discount/volume/tier and JSON values with tiers.
    Expected tier shape examples:
      {"tiers": [{"min": 2, "percent": 10}, {"min": 3, "percent": 15}]}
    or [{"quantity": 2, "discount": {"type": "percentage", "value": 10}}, ...]
    """
    tiers: List[Dict[str, Any]] = []
    candidates: List[Tuple[str, str, str]] = []  # (namespace, key, value)
    for mf in metafields:
        ns = (mf.get("namespace") or "").lower()
        key = (mf.get("key") or "").lower()
        val = mf.get("value")
        if any(tok in ns for tok in ("discount", "volume", "tier")) or any(
            tok in key for tok in ("discount", "volume", "tier")
        ):
            if isinstance(val, str):
                candidates.append((ns, key, val))

    def _try_json(s: str) -> Optional[Any]:
        try:
            return json.loads(s)
        except Exception:
            return None

    for ns, key, val in candidates:
        obj = _try_json(val)
        if not obj:
            continue
        # Possible shapes
        if isinstance(obj, dict) and isinstance(obj.get("tiers"), list):
            for t in obj["tiers"]:
                q = t.get("min") or t.get("quantity") or t.get("qty")
                perc = None
                amt = None
                if isinstance(t.get("percent"), (int, float)):
                    perc = float(t["percent"])
                elif isinstance(t.get("discount"), dict):
                    d = t["discount"]
                    if d.get("type") == "percentage" and isinstance(d.get("value"), (int, float)):
                        perc = float(d["value"])
                    if d.get("type") == "amount" and isinstance(d.get("value"), (int, float)):
                        amt = float(d["value"])
                if q:
                    tiers.append({"min_quantity": int(q), "percentage": perc, "amount": amt, "source": f"{ns}/{key}"})
        elif isinstance(obj, list):
            for t in obj:
                if not isinstance(t, dict):
                    continue
                q = t.get("min") or t.get("quantity") or t.get("qty")
                perc = t.get("percent") or (t.get("discount", {}).get("value") if isinstance(t.get("discount"), dict) and t.get("discount", {}).get("type") == "percentage" else None)
                amt = t.get("amount")
                if q and (perc or amt):
                    try:
                        tiers.append({"min_quantity": int(q), "percentage": float(perc) if perc is not None else None, "amount": float(amt) if amt is not None else None, "source": f"{ns}/{key}"})
                    except Exception:
                        continue
    # Deduplicate/sort by min_quantity
    tiers = sorted({(t["min_quantity"], t.get("percentage"), t.get("amount"), t["source"]): t for t in tiers}.values(), key=lambda x: x["min_quantity"])
    return tiers


def list_automatic_discounts_if_available(client: RestClient) -> List[Dict[str, Any]]:
    """Automatic discounts via REST are not always exposed. Try and be tolerant."""
    results: List[Dict[str, Any]] = []
    try:
        resp = client.get("/automatic_discounts.json")
        if resp.status_code != 200:
            print(f"automatic_discounts endpoint not available (status {resp.status_code}).")
            return results
        data = resp.json() if resp.content else {}
        for d in data.get("automatic_discounts", []) or []:
            results.append({
                "id": d.get("id"),
                "title": d.get("title"),
                "starts_at": d.get("starts_at"),
                "ends_at": d.get("ends_at"),
                "status": d.get("status"),
            })
    except Exception as e:
        print(f"Automatic discounts fetch failed: {e}")
    return results


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Inspect AstroSouks discounts via REST")
    parser.add_argument("--query", default="Bone Conduction", help="Title substring to match the product")
    args = parser.parse_args()

    shop = _env("ASTROSOUKS_SHOPIFY_SHOP_DOMAIN", "SHOPIFY_SHOP_DOMAIN")
    token = _env("ASTROSOUKS_SHOPIFY_TOKEN", "SHOPIFY_ACCESS_TOKEN")
    version = _env("SHOPIFY_API_VERSION", default="2024-10")

    if not shop or not token:
        print("Missing shop domain or token. Set ASTROSOUKS_SHOPIFY_SHOP_DOMAIN and ASTROSOUKS_SHOPIFY_TOKEN.")
        sys.exit(1)

    client = RestClient(shop, token, version)

    product = find_product_and_variants_rest(client, args.query)
    if not product:
        print(f"No product found matching title contains '{args.query}'.")
        sys.exit(2)

    product_id = product.get("id")
    variants = product.get("variants", []) or []
    variant_ids = [v.get("id") for v in variants if v.get("id")]

    # 1) Try REST price rules first
    rules, rules_err = list_price_rules_applying_to(client, int(product_id), [int(i) for i in variant_ids])
    if rules_err:
        # Surface scope error tersely
        if "read_price_rules" in rules_err:
            print("REST price rules: missing 'read_price_rules' scope.")
        else:
            print(f"REST price rules not available: {rules_err}")

    if rules:
        for r in rules:
            out = {
                "type": "price_rule",
                "id": r.get("id"),
                "title": r.get("title"),
                "discount": r.get("discount"),
                "value_type": r.get("value_type"),
                "allocation_method": r.get("allocation_method"),
                "min_quantity": r.get("prerequisite_quantity"),
                "min_subtotal": r.get("prerequisite_subtotal"),
                "starts_at": r.get("starts_at"),
                "ends_at": r.get("ends_at"),
                "variant_ids": variant_ids,
            }
            print(json.dumps(out))

    # 2) Fallback: inspect metafields for volume-pricing tiers
    product_mfs = list_metafields(client, "products", int(product_id))
    tiers = extract_discount_tiers_from_metafields(product_mfs)
    if not tiers:
        for vid in variant_ids:
            v_mfs = list_metafields(client, "variants", int(vid))
            tiers.extend(extract_discount_tiers_from_metafields(v_mfs))
    if tiers:
        print(json.dumps({
            "type": "metafield_volume_pricing",
            "product_id": product_id,
            "variant_ids": variant_ids,
            "tiers": tiers,
        }))
    else:
        # 3) Automatic discounts (best-effort; often unavailable on REST)
        autos = list_automatic_discounts_if_available(client)
        if autos:
            print(json.dumps({"type": "automatic_discounts", "discounts": autos, "variant_ids": variant_ids}))
        elif not rules:
            print(json.dumps({"type": "no_discounts_detected_rest", "reason": "no_price_rules_scope_or_endpoint", "variant_ids": variant_ids}))


if __name__ == "__main__":
    main()


