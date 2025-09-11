#!/usr/bin/env python3
"""
Create a discounted Draft Order using an EXISTING discount code (REST Admin API).

This script:
- Finds a product and variant via REST by title substring and optional variant title
- Verifies that a provided discount code exists beneath a Price Rule
- Creates a Draft Order with that discount applied (order-level applied_discount)
- Optionally completes the draft order into a finalized order (payment pending)

Requirements (OAuth scopes):
- read_products
- read_price_rules
- write_draft_orders

Environment:
- ASTROSOUKS_SHOPIFY_SHOP_DOMAIN or SHOPIFY_SHOP_DOMAIN
- ASTROSOUKS_SHOPIFY_TOKEN       or SHOPIFY_ACCESS_TOKEN
- Optional: SHOPIFY_API_VERSION (defaults to 2024-10)

Usage examples:
  python scripts/test_create_draft_order_with_existing_discount_rest.py \
    --query "Bone Conduction" --quantity 2 --discount-code "BONE10" --email "shopastrotechlb@gmail.com" \
    --complete

Notes:
- This uses REST /draft_orders.json with "applied_discount" to reflect the existing price rule code.
- No new discount is created; we read the rule+code and mirror its value on the draft.
- If you also want to finalize, pass --complete to call /draft_orders/{id}/complete.json.
"""

import os
import sys
import json
import time
import argparse
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv


def _env(key: str, *fallbacks: str, default: Optional[str] = None) -> Optional[str]:
    for k in (key, *fallbacks):
        val = os.getenv(k)
        if val:
            return val
    return default


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

    def post(self, path: str, payload: Dict[str, Any]) -> requests.Response:
        url = f"{self.base}{path}"
        return self.session.post(url, json=payload, timeout=60)

    def put(self, path: str, payload: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        url = f"{self.base}{path}"
        return self.session.put(url, json=payload, params=params, timeout=60)

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
                params = None
                time.sleep(0.2)
            else:
                break


def find_product_and_variant(client: RestClient, query: str, variant_title: Optional[str]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    product = None
    for p in client.iter_pages("/products.json?limit=250", root_key="products"):
        title = (p.get("title") or "").lower()
        if query.lower() in title:
            product = p
            break
    if not product:
        return None, None

    chosen = None
    variants = product.get("variants", []) or []
    if variant_title:
        vt = variant_title.strip().lower()
        for v in variants:
            if (v.get("title") or "").lower() == vt:
                chosen = v
                break
    if chosen is None and variants:
        chosen = variants[0]
    return product, chosen


def lookup_discount_code(client: RestClient, code: str) -> Optional[Dict[str, Any]]:
    target_code = (code or "").strip().lower()
    if not target_code:
        return None

    for rule in client.iter_pages("/price_rules.json?limit=250", root_key="price_rules"):
        rid = rule.get("id")
        if not rid:
            continue
        # Search codes beneath this rule
        path = f"/price_rules/{rid}/discount_codes.json?limit=250"
        try:
            for dc in client.iter_pages(path, root_key="discount_codes"):
                if (dc.get("code") or "").strip().lower() == target_code:
                    # Attach rule context
                    out = dict(dc)
                    out["_rule"] = rule
                    return out
        except RuntimeError:
            # Some shops limit listing codes; continue
            continue
    return None


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Create discounted Draft Order using an existing discount code (REST)")
    parser.add_argument("--query", required=True, help="Product title substring to match")
    parser.add_argument("--variant-title", default=None, help="Exact variant title to match (optional)")
    parser.add_argument("--quantity", type=int, default=1, help="Quantity to order")
    parser.add_argument("--discount-code", required=True, help="Existing discount code to apply (must exist under a price rule)")
    parser.add_argument("--email", default="shopastrotechlb@gmail.com", help="Customer email for draft order")
    parser.add_argument("--complete", action="store_true", help="Complete the draft order into a finalized order (payment pending)")

    args = parser.parse_args()

    shop = _env("ASTROSOUKS_SHOPIFY_SHOP_DOMAIN", "SHOPIFY_SHOP_DOMAIN")
    token = _env("ASTROSOUKS_SHOPIFY_TOKEN", "SHOPIFY_ACCESS_TOKEN")
    version = _env("SHOPIFY_API_VERSION", default="2024-10")

    if not shop or not token:
        print("Missing shop domain or token. Set ASTROSOUKS_SHOPIFY_SHOP_DOMAIN and ASTROSOUKS_SHOPIFY_TOKEN.")
        sys.exit(1)

    client = RestClient(shop, token, version)

    # 1) Resolve product and variant
    product, variant = find_product_and_variant(client, args.query, args.variant_title)
    if not product or not variant:
        print("Product/variant not found.")
        sys.exit(2)

    variant_id = variant.get("id")
    if not variant_id:
        print("Variant lacks an id.")
        sys.exit(3)

    # 2) Verify discount code exists and get rule details
    dc = lookup_discount_code(client, args.discount_code)
    if not dc:
        print(f"Discount code '{args.discount_code}' not found under any price rule.")
        sys.exit(4)

    rule = dc.get("_rule") or {}
    value_type = rule.get("value_type")  # 'percentage' | 'fixed_amount'
    # Shopify stores rule.value as negative string like '-10.0'
    try:
        raw_value = rule.get("value")
        value = abs(float(raw_value)) if raw_value is not None else None
    except Exception:
        value = None

    if not value or value <= 0 or value_type not in ("percentage", "fixed_amount"):
        print("Rule value missing/invalid; cannot apply.")
        sys.exit(5)

    # 3) Build draft order payload with applied_discount mirroring the rule
    line_items = [{"variant_id": int(variant_id), "quantity": int(args.quantity)}]

    applied_discount: Dict[str, Any] = {
        "title": dc.get("code"),
        "description": f"Applied existing code {dc.get('code')} (rule: {rule.get('title')})",
        "value_type": value_type,
        "value": f"{value}",
    }

    draft_payload = {
        "draft_order": {
            "email": args.email,
            "line_items": line_items,
            "applied_discount": applied_discount,
            "use_customer_default_address": True,
        }
    }

    resp = client.post("/draft_orders.json", draft_payload)
    if resp.status_code not in (200, 201):
        print(f"Draft order create failed: {resp.status_code} {resp.text}")
        sys.exit(6)

    draft = (resp.json() or {}).get("draft_order") or {}
    draft_id = draft.get("id")
    draft_name = draft.get("name")
    print(json.dumps({
        "status": "draft_created",
        "id": draft_id,
        "name": draft_name,
        "discount": {"code": dc.get("code"), "type": value_type, "value": value},
    }))

    # 4) Optionally complete the draft order
    if args.complete and draft_id:
        complete_resp = client.put(f"/draft_orders/{draft_id}/complete.json", params={"payment_pending": "true"}, payload={})
        if complete_resp.status_code not in (200, 201):
            print(f"Draft order complete failed: {complete_resp.status_code} {complete_resp.text}")
            sys.exit(7)
        order = (complete_resp.json() or {}).get("order") or {}
        print(json.dumps({
            "status": "order_completed",
            "order_id": order.get("id"),
            "order_name": order.get("name"),
            "financial_status": order.get("financial_status"),
        }))


if __name__ == "__main__":
    main()


