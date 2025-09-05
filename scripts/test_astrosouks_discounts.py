#!/usr/bin/env python3
"""
Ad-hoc diagnostic script: Inspect discounts for AstroSouks product(s) without creating orders.

What it does:
- Uses Admin GraphQL via our ShopifyClient to find the "Bone Conduction Speaker" product
- Prints the variant ID(s) and price vs compareAtPrice
- If compareAtPrice > price, reports the implicit sale discount
- Optionally lists basic PriceRule info (best-effort) to help diagnose discount application

Environment (from .env):
- ASTROSOUKS_SHOPIFY_SHOP_DOMAIN (required)
- ASTROSOUKS_SHOPIFY_TOKEN       (required)
"""

import os
import sys
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv

# Ensure project root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from shopify_method import ShopifyClient  # noqa: E402
from shopify_method.utils import extract_id_from_gid  # noqa: E402


def _get_env_or_exit(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"ERROR: Missing required env var {name}")
        sys.exit(1)
    return value


def _find_bone_conduction_product(client: ShopifyClient) -> Optional[Dict[str, Any]]:
    """
    Search products for a title/handle that contains 'bone conduction'.
    Returns a product dict with variants/images, or None if not found.
    """
    try:
        # Use broad search to fetch products
        res = client.get_products_full(limit=50, search="bone conduction")
        if not res.get("success"):
            print(f"Failed to get products: {res.get('error')}")
            return None
        products = (res.get("data") or {}).get("products") or []
        # Fallback: some client versions put data top-level
        if not products and isinstance(res.get("data"), dict) is False:
            products = res.get("products", [])

        for p in products:
            title = (p.get("title") or "").lower()
            handle = (p.get("handle") or "").lower()
            if "bone conduction" in title or "bone-conduction" in handle:
                return p
        return None
    except Exception as e:
        print(f"Exception while searching products: {e}")
        return None


def _print_variant_pricing(product: Dict[str, Any]) -> None:
    variants = product.get("variants", []) or []
    if not variants:
        print("No variants found for product.")
        return

    print("\nVariants and pricing:")
    found_discount = False
    for v in variants:
        gid = v.get("id")
        variant_id = extract_id_from_gid(gid) or gid
        title = v.get("title") or "Default Title"
        try:
            price = float(v.get("price")) if v.get("price") is not None else None
        except Exception:
            price = None
        try:
            compare_at = float(v.get("compareAtPrice")) if v.get("compareAtPrice") is not None else None
        except Exception:
            compare_at = None

        line = f"  - Variant '{title}' | id={variant_id} | price={price}"
        if compare_at is not None:
            line += f" | compareAtPrice={compare_at}"
            if price is not None and compare_at > price:
                found_discount = True
                pct = round((compare_at - price) / compare_at * 100.0, 2)
                line += f" | SALE: -{pct}%"
        print(line)

    if not found_discount:
        print("No implicit sale (compareAtPrice > price) detected on listed variants.")


def _try_list_price_rules(client: ShopifyClient) -> None:
    """Best-effort: list PriceRule and AutomaticDiscount nodes to aid debugging."""
    print("\nAttempting to list PriceRules and AutomaticDiscounts (best-effort)...")
    price_rules_query = """
    query {
      priceRules(first: 20) {
        edges {
          node {
            id
            title
            valueV2 { __typename ... on MoneyV2 { amount currencyCode } ... on PricingPercentageValue { percentage } }
            startsAt
            endsAt
            targetType
            allocationMethod
            itemEntitlements {
              products(first: 5) { edges { node { id title } } }
              productVariants(first: 5) { edges { node { id title } } }
            }
          }
        }
      }
    }
    """

    auto_discounts_query = """
    query {
      automaticDiscountNodes(first: 20) {
        edges {
          node {
            id
            automaticDiscount {
              __typename
              ... on AutomaticBasicDiscount {
                title
                startsAt
                endsAt
              }
            }
          }
        }
      }
    }
    """
    try:
        pr = client._make_graphql_request(price_rules_query)
        edges = (pr.get("data") or {}).get("priceRules", {}).get("edges", [])
        if not edges:
            print("  No PriceRules returned or insufficient scope.")
        else:
            print("  PriceRules:")
            for e in edges:
                n = e.get("node") or {}
                print(f"    - {n.get('title')} (id={n.get('id')}) targetType={n.get('targetType')} allocation={n.get('allocationMethod')}")

        ad = client._make_graphql_request(auto_discounts_query)
        aedges = (ad.get("data") or {}).get("automaticDiscountNodes", {}).get("edges", [])
        if not aedges:
            print("  No AutomaticDiscounts returned or insufficient scope.")
        else:
            print("  AutomaticDiscounts:")
            for e in aedges:
                node = e.get("node") or {}
                adisc = node.get("automaticDiscount") or {}
                print(f"    - {adisc.get('__typename')} (id={node.get('id')})")
    except Exception as e:
        print(f"  Discount queries failed (possibly due to scopes/version): {e}")


def main() -> None:
    load_dotenv()
    shop_domain = _get_env_or_exit("ASTROSOUKS_SHOPIFY_SHOP_DOMAIN")
    access_token = _get_env_or_exit("ASTROSOUKS_SHOPIFY_TOKEN")

    client = ShopifyClient(shop_domain=shop_domain, access_token=access_token)
    product = _find_bone_conduction_product(client)

    if not product:
        print("Bone Conduction product not found via search.")
        sys.exit(1)

    print(f"Found product: {product.get('title')} (id={product.get('id')})")
    _print_variant_pricing(product)
    _try_list_price_rules(client)


if __name__ == "__main__":
    main()


