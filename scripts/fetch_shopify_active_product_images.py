"""
Fetch all ACTIVE products from the AstroSouks Shopify store and save their images
to a neatly formatted txt file.

Environment variables (loaded from .env):
  - ASTROSOUKS_SHOPIFY_SHOP_DOMAIN  (required)
  - ASTROSOUKS_SHOPIFY_TOKEN        (required)
  - ASTROSOUKS_SHOPIFY_API_KEY      (optional, not used here)
  - ASTROSOUKS_SHOPIFY_SECRET_KEY   (optional, not used here)

Usage:
  python scripts/fetch_shopify_active_product_images.py

Output:
  shopify_active_product_images_<domain>.txt (in project root)
"""

import os
import sys
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
from shopify_method import ShopifyClient


def _sanitize_filename_component(text: str) -> str:
    sanitized = (text or "").strip().lower()
    for ch in [" ", ".", "/", "\\", ":", "*", "?", "\"", "<", ">", "|"]:
        sanitized = sanitized.replace(ch, "_")
    sanitized = sanitized.replace("-", "_")
    return sanitized[:80] or "store"


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
        vendor
        images(first: 50) {
          edges { node { id src altText } }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""


def _format_product_images(product: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# {product.get('title')}")
    lines.append(f"ID: {product.get('id')}  |  Handle: {product.get('handle')}  |  Status: {product.get('status')}  |  Vendor: {product.get('vendor')}")

    images_conn = product.get('images') or {}
    image_edges = images_conn.get('edges') or []
    lines.append(f"Images: {len(image_edges)}")
    for edge in image_edges:
        node = (edge or {}).get('node') or {}
        url = node.get('src')
        alt = node.get('altText')
        if alt:
            lines.append(f"  - {url}  (alt: {alt})")
        else:
            lines.append(f"  - {url}")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    load_dotenv()

    shop_domain = os.getenv("ASTROSOUKS_SHOPIFY_SHOP_DOMAIN")
    access_token = os.getenv("ASTROSOUKS_SHOPIFY_TOKEN")

    if not shop_domain or not access_token:
        print("ERROR: Missing env vars. Please set ASTROSOUKS_SHOPIFY_SHOP_DOMAIN and ASTROSOUKS_SHOPIFY_TOKEN in .env.")
        sys.exit(1)

    client = ShopifyClient(shop_domain=shop_domain, access_token=access_token)

    all_active_products: List[Dict[str, Any]] = []
    first = 50
    after: Optional[str] = None
    search_query = "status:active"

    while True:
        variables = {"first": first, "after": after, "query": search_query}
        data = client._make_graphql_request(PAGINATED_ACTIVE_PRODUCTS_QUERY, variables)
        products_conn = (data.get("data") or {}).get("products") or {}
        edges = products_conn.get("edges") or []
        for edge in edges:
            node = (edge or {}).get("node")
            if node:
                # Only ACTIVE products will be returned by the search query, but keep a defensive check
                if (node.get("status") or "").upper() == "ACTIVE":
                    all_active_products.append(node)
        page_info = products_conn.get("pageInfo") or {}
        if page_info.get("hasNextPage"):
            after = page_info.get("endCursor")
        else:
            break

    domain_component = _sanitize_filename_component(shop_domain)
    out_path = os.path.join(os.path.dirname(__file__), f"../shopify_active_product_images_{domain_component}.txt")
    out_path = os.path.abspath(out_path)

    lines: List[str] = []
    lines.append(f"Shop Domain: {shop_domain}")
    lines.append(f"Total ACTIVE Products: {len(all_active_products)}")
    lines.append("")

    for product in all_active_products:
        lines.append(_format_product_images(product))

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Saved ACTIVE product images for {len(all_active_products)} products to {out_path}")


if __name__ == "__main__":
    main()

