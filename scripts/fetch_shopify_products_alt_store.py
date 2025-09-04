"""
Fetch all products from an alternate Shopify store (Admin GraphQL API) and save
them to a neatly formatted txt file.

Environment variables (the script will use the first available value):
  - SHOPIFY_NEW_SHOP_DOMAIN        | SHOPIFY_SHOP_DOMAIN_2
    ALT_SHOPIFY_SHOP_DOMAIN       | NEW_SHOPIFY_SHOP_DOMAIN
    SHOPIFY_SHOP_DOMAIN

  - SHOPIFY_NEW_ACCESS_TOKEN       | SHOPIFY_ACCESS_TOKEN_2
    ALT_SHOPIFY_ACCESS_TOKEN      | NEW_SHOPIFY_ACCESS_TOKEN
    SHOPIFY_ACCESS_TOKEN

Usage:
  1) Ensure your .env contains the alternate store domain/token under any of the
     names above.
  2) Run:  python scripts/fetch_shopify_products_alt_store.py
  3) Output file: shopify_products_<domain>.txt (in project root)
"""

import os
import sys
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv

# Import the typed client
from shopify_method import ShopifyClient


def _first_env(names: List[str], default: Optional[str] = None) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def _sanitize_filename_component(text: str) -> str:
    sanitized = (text or "").strip().lower()
    for ch in [" ", ".", "/", "\\", ":", "*", "?", "\"", "<", ">", "|"]:
        sanitized = sanitized.replace(ch, "_")
    sanitized = sanitized.replace("-", "_")
    return sanitized[:80] or "store"


PAGINATED_PRODUCTS_QUERY = """
query getAllProducts($first: Int!, $after: String) {
  products(first: $first, after: $after) {
    edges {
      cursor
      node {
        id
        title
        handle
        status
        vendor
        productType
        tags
        createdAt
        updatedAt
        images(first: 10) {
          edges { node { id src altText } }
        }
        variants(first: 50) {
          edges {
            node {
              id
              title
              price
              compareAtPrice
              sku
              barcode
              inventoryQuantity
              availableForSale
            }
          }
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


def _format_product(product: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# {product.get('title')}")
    lines.append(f"ID: {product.get('id')}  |  Handle: {product.get('handle')}  |  Status: {product.get('status')}")
    lines.append(f"Vendor: {product.get('vendor')}  |  Type: {product.get('productType')}  |  Tags: {', '.join(product.get('tags') or [])}")
    lines.append(f"Created: {product.get('createdAt')}  |  Updated: {product.get('updatedAt')}")

    # Images summary
    images_conn = product.get('images') or {}
    image_edges = images_conn.get('edges') or []
    lines.append(f"Images: {len(image_edges)}")

    # Variants table
    var_conn = product.get('variants') or {}
    var_edges = var_conn.get('edges') or []
    if var_edges:
        lines.append("Variants:")
        for edge in var_edges:
            node = (edge or {}).get('node') or {}
            lines.append(
                f"  - {node.get('title')} | id={node.get('id')} | price={node.get('price')} | sku={node.get('sku')} | inv={node.get('inventoryQuantity')} | available={node.get('availableForSale')}"
            )
    else:
        lines.append("Variants: none")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    load_dotenv()

    # Load AstroSouks-specific environment variables
    shop_domain = os.getenv("ASTROSOUKS_SHOPIFY_SHOP_DOMAIN")
    access_token = os.getenv("ASTROSOUKS_SHOPIFY_TOKEN")
    api_key = os.getenv("ASTROSOUKS_SHOPIFY_API_KEY")  # Not required for this script
    secret_key = os.getenv("ASTROSOUKS_SHOPIFY_SECRET_KEY")  # Not required for this script

    if not shop_domain or not access_token:
        print("ERROR: Missing env vars. Please set ASTROSOUKS_SHOPIFY_SHOP_DOMAIN and ASTROSOUKS_SHOPIFY_TOKEN in .env.")
        print("Optional (not required for this script): ASTROSOUKS_SHOPIFY_API_KEY, ASTROSOUKS_SHOPIFY_SECRET_KEY")
        sys.exit(1)

    client = ShopifyClient(shop_domain=shop_domain, access_token=access_token)

    all_products: List[Dict[str, Any]] = []
    first = 50
    after: Optional[str] = None

    while True:
        variables = {"first": first, "after": after}
        data = client._make_graphql_request(PAGINATED_PRODUCTS_QUERY, variables)
        products_conn = (data.get("data") or {}).get("products") or {}
        edges = products_conn.get("edges") or []
        for edge in edges:
            node = (edge or {}).get("node")
            if node:
                all_products.append(node)
        page_info = products_conn.get("pageInfo") or {}
        if page_info.get("hasNextPage"):
            after = page_info.get("endCursor")
        else:
            break

    # Prepare output
    domain_component = _sanitize_filename_component(shop_domain)
    out_path = os.path.join(os.path.dirname(__file__), f"../shopify_products_{domain_component}.txt")
    out_path = os.path.abspath(out_path)

    lines: List[str] = []
    lines.append(f"Shop Domain: {shop_domain}")
    lines.append(f"Total Products: {len(all_products)}")
    lines.append("")

    for product in all_products:
        lines.append(_format_product(product))

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Saved {len(all_products)} products to {out_path}")


if __name__ == "__main__":
    main()

