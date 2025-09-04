"""
AstroSouks Inventory Tool

Fetches live quantities for AstroSouks ACTIVE products from Shopify (GraphQL Admin API).

Environment (from .env):
  - ASTROSOUKS_SHOPIFY_SHOP_DOMAIN (required)
  - ASTROSOUKS_SHOPIFY_TOKEN       (required)
"""

import os
import json
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
from langchain.tools import tool

from shopify_method import ShopifyClient


# GraphQL with pagination to fetch ACTIVE products including variant inventory
PAGINATED_ACTIVE_PRODUCTS_QUERY = """
query getActiveProducts($first: Int!, $after: String, $query: String) {
  products(first: $first, after: $after, query: $query) {
    edges {
      cursor
      node {
        id
        title
        handle
        status
        variants(first: 100) {
          edges { node { id title sku inventoryQuantity } }
        }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def _total_available_from_product(product: Dict[str, Any]) -> int:
    variants_conn = product.get("variants") or {}
    edges = variants_conn.get("edges") or []
    total = 0
    for edge in edges:
        node = (edge or {}).get("node") or {}
        try:
            qty = int(node.get("inventoryQuantity") or 0)
        except Exception:
            qty = 0
        total += qty
    return total


def _fetch_all_active_products(client: ShopifyClient) -> List[Dict[str, Any]]:
    all_products: List[Dict[str, Any]] = []
    first = 100
    after: Optional[str] = None
    query = "status:active"

    while True:
        variables = {"first": first, "after": after, "query": query}
        data = client._make_graphql_request(PAGINATED_ACTIVE_PRODUCTS_QUERY, variables)
        products_conn = (data.get("data") or {}).get("products") or {}
        edges = products_conn.get("edges") or []
        for edge in edges:
            node = (edge or {}).get("node")
            if node and (node.get("status") or "").upper() == "ACTIVE":
                all_products.append(node)
        page_info = products_conn.get("pageInfo") or {}
        if page_info.get("hasNextPage"):
            after = page_info.get("endCursor")
        else:
            break
    return all_products


def _ensure_client() -> ShopifyClient:
    load_dotenv()
    shop_domain = os.getenv("ASTROSOUKS_SHOPIFY_SHOP_DOMAIN")
    access_token = os.getenv("ASTROSOUKS_SHOPIFY_TOKEN")
    if not shop_domain or not access_token:
        raise ValueError("Missing ASTROSOUKS_SHOPIFY_SHOP_DOMAIN or ASTROSOUKS_SHOPIFY_TOKEN in environment.")
    return ShopifyClient(shop_domain=shop_domain, access_token=access_token)


@tool
def check_astrosouks_inventory(product_name: str = "all") -> str:
    """
    Check live inventory quantities for AstroSouks products (ACTIVE only).
    This tool provides stock levels per product, aggregated across variants.

    Args:
        product_name: Product name to check. Options:
            - "all" (default): Return all ACTIVE products with total quantity
            - Any partial product name (case-insensitive): Return the first matching ACTIVE product summary

    Returns:
        Plain text (txt-friendly) output:
          - For all: one line per product → "product: <Product Title> available in stock: <N>" or "product: <Product Title> sold out" when N==0
          - For a single match: same format as above
          - On error: "Error: <message>"
    """
    try:
        client = _ensure_client()
        products = _fetch_all_active_products(client)
        # Build simple text lines
        if not products:
            return ""

        if isinstance(product_name, str) and product_name.strip().lower() != "all":
            needle = product_name.strip().lower()
            match_idx = None
            for idx, p in enumerate(products):
                title = (p.get("title") or "").lower()
                handle = (p.get("handle") or "").lower()
                if needle in title or needle in handle:
                    match_idx = idx
                    break
            if match_idx is None:
                return f"Error: Product '{product_name}' not found among ACTIVE products."

            prod = products[match_idx]
            title = prod.get("title") or prod.get("handle") or "Unknown"
            total = _total_available_from_product(prod)
            if int(total) <= 0:
                return f"product: {title} sold out"
            return f"product: {title} available in stock: {total}"

        # Default: all — one line per product
        lines: List[str] = []
        for p in products:
            title = p.get("title") or p.get("handle") or "Unknown"
            total = _total_available_from_product(p)
            if int(total) <= 0:
                lines.append(f"product: {title} sold out")
            else:
                lines.append(f"product: {title} available in stock: {total}")
        return "\n".join(lines)

    except Exception as e:
        return f"Error: {str(e)}"

