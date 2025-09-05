#!/usr/bin/env python3
"""
List the Admin API scopes configured for the current access token and probe a
few relevant REST endpoints to verify effective permissions.

Environment (fallback order):
- SHOPIFY_SHOP_DOMAIN or ASTROSOUKS_SHOPIFY_SHOP_DOMAIN
- SHOPIFY_ACCESS_TOKEN or ASTROSOUKS_SHOPIFY_TOKEN
- SHOPIFY_API_VERSION (optional; defaults to 2024-10)

Usage:
  python scripts/check_shopify_scopes.py
"""

import os
import sys
import json
from typing import Optional

import requests
from dotenv import load_dotenv

try:
    # Use the project client which already has get_permissions implemented
    from shopify_method.client import ShopifyClient
except Exception as e:
    print(f"Failed to import ShopifyClient: {e}")
    sys.exit(2)


def env_or(*keys: str, default: Optional[str] = None) -> Optional[str]:
    for k in keys:
        v = os.getenv(k)
        if v:
            return v
    return default


def probe_rest_endpoint(session: requests.Session, base_url: str, endpoint: str) -> int:
    url = f"{base_url}{endpoint}"
    try:
        resp = session.get(url, timeout=30)
        return resp.status_code
    except Exception:
        return -1


def main() -> int:
    load_dotenv()

    shop = env_or("SHOPIFY_SHOP_DOMAIN", "ASTROSOUKS_SHOPIFY_SHOP_DOMAIN")
    token = env_or("SHOPIFY_ACCESS_TOKEN", "ASTROSOUKS_SHOPIFY_TOKEN")
    version = env_or("SHOPIFY_API_VERSION", default="2024-10")

    if not shop or not token:
        print("Missing SHOPIFY_SHOP_DOMAIN/ASTROSOUKS_SHOPIFY_SHOP_DOMAIN or SHOPIFY_ACCESS_TOKEN/ASTROSOUKS_SHOPIFY_TOKEN.")
        return 1

    client = ShopifyClient(shop_domain=shop, access_token=token, api_version=version)

    # 1) GraphQL: list declared scopes
    perms = client.get_permissions()
    if not perms.get("success"):
        print(json.dumps({"success": False, "error": perms.get("error")}))
        return 2

    scope_list = perms["data"].get("scopes", [])
    scope_list_sorted = sorted(scope_list)

    # 2) REST probes for a few sensitive endpoints
    rest_base = f"https://{client.shop_domain}/admin/api/{client.api_version}"
    probes = {
        "price_rules": probe_rest_endpoint(client.session, rest_base, "/price_rules.json?limit=1"),
        "discount_codes": probe_rest_endpoint(client.session, rest_base, "/discount_codes/lookup.json?code=TEST"),
    }

    result = {
        "success": True,
        "shop": client.shop_domain,
        "api_version": client.api_version,
        "scopes": scope_list_sorted,
        "has_read_price_rules": "read_price_rules" in scope_list_sorted,
        "has_read_discounts": "read_discounts" in scope_list_sorted,
        "rest_probe": probes,
    }

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())


