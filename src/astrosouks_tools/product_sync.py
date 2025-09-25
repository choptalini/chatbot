"""
AstroSouks product sync job.

Fetches all ACTIVE products from Shopify and writes a unified knowledge base file
`astrosouks_knowledgebase.txt` that other tools (CAG, WhatsApp tools, Order tool)
can consume as a single source of truth.

This module exposes a synchronous `perform_sync()` function and an async wrapper
`run_product_sync_once()` so the server can schedule it hourly.
"""

import os
import logging
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from shopify_method import ShopifyClient


logger = logging.getLogger(__name__)


# Paginated full products query with images, variants and status
PAGINATED_PRODUCTS_FULL_QUERY = """
query getAllProducts($first: Int!, $after: String, $query: String) {
  products(first: $first, after: $after, query: $query) {
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
        description
        descriptionHtml
        images(first: 10) {
          edges { node { id src altText } }
        }
        variants(first: 100) {
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
              selectedOptions { name value }
            }
          }
        }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def _sanitize_filename_component(text: str) -> str:
    sanitized = (text or "").strip().lower()
    for ch in [" ", ".", "/", "\\", ":", "*", "?", "\"", "<", ">", "|"]:
        sanitized = sanitized.replace(ch, "_")
    sanitized = sanitized.replace("-", "_")
    return sanitized[:80] or "store"


def _format_block(product: Dict[str, Any]) -> str:
    lines: List[str] = []
    title = product.get("title") or product.get("handle") or "Unknown"
    lines.append(f"#### **{title}**")

    # Info line
    info_parts: List[str] = []
    info_parts.append(f"ID: {product.get('id')}")
    info_parts.append(f"Handle: {product.get('handle')}")
    info_parts.append(f"Type: {product.get('productType') or ''}")
    info_parts.append(f"Vendor: {product.get('vendor') or ''}")
    tags = product.get("tags") or []
    info_parts.append(f"Tags: {', '.join(tags)}")
    info_parts.append(f"Status: {product.get('status')}")

    # Availability from summed variant inventory
    total_inv = 0
    var_edges = ((product.get("variants") or {}).get("edges") or [])
    for e in var_edges:
        node = (e or {}).get("node") or {}
        try:
            total_inv += int(node.get("inventoryQuantity") or 0)
        except Exception:
            pass
    availability = "in stock" if total_inv > 0 else "out of stock"
    info_parts.append(f"Availability: {availability}")
    lines.append(" |  ".join(info_parts))

    # Compute product-level price from variants
    prices: List[float] = []
    compares: List[float] = []
    for e in var_edges:
        node = (e or {}).get("node") or {}
        try:
            if node.get("price") is not None:
                prices.append(float(node.get("price")))
            if node.get("compareAtPrice") is not None:
                compares.append(float(node.get("compareAtPrice")))
        except Exception:
            pass
    cur_price = min(prices) if prices else None
    cmp_price = max(compares) if compares else None
    if cur_price is not None:
        lines.append(f"* **Price:** ${cur_price:.2f}")
    if cur_price is not None and cmp_price is not None and cmp_price > cur_price:
        lines.append(f"On sale from ${cmp_price:.2f}")

    # Description
    desc = product.get("description") or ""
    if desc:
        lines.append(f"**Description:** {desc.strip()}")

    # Single image (first)
    img_edges = ((product.get("images") or {}).get("edges") or [])
    if img_edges:
        url = ((img_edges[0] or {}).get("node") or {}).get("src")
        if url:
            lines.append(f"**Image:** {url}")

    # Variants
    if var_edges:
        lines.append("**Variants:**")
        for e in var_edges:
            node = (e or {}).get("node") or {}
            vtitle = node.get("title")
            sku = node.get("sku") or ""
            price = node.get("price")
            cmp = node.get("compareAtPrice")
            inv = node.get("inventoryQuantity")
            avail = node.get("availableForSale")
            lines.append(
                f"  - {vtitle} | sku={sku} | price=${price} | compareAt=${cmp} | inv={inv} | available={avail}"
            )

    lines.append("---")
    return "\n".join(lines)


def perform_sync() -> Optional[str]:
    """
    Fetch all ACTIVE products and write the unified KB file in-place.
    Returns the path to the written KB on success, None on failure.
    """
    try:
        load_dotenv()
        shop_domain = os.getenv("ASTROSOUKS_SHOPIFY_SHOP_DOMAIN")
        access_token = os.getenv("ASTROSOUKS_SHOPIFY_TOKEN")
        if not shop_domain or not access_token:
            logger.warning("AstroSouks Shopify credentials not found; skipping product sync")
            return None

        client = ShopifyClient(shop_domain=shop_domain, access_token=access_token)

        all_products: List[Dict[str, Any]] = []
        first = 100
        after: Optional[str] = None
        # Only ACTIVE
        query = "status:active"

        while True:
            variables = {"first": first, "after": after, "query": query}
            data = client._make_graphql_request(PAGINATED_PRODUCTS_FULL_QUERY, variables)
            products_conn = (data.get("data") or {}).get("products") or {}
            edges = products_conn.get("edges") or []
            for edge in edges:
                node = (edge or {}).get("node")
                if not node:
                    continue
                if (node.get("status") or "").upper() == "ACTIVE":
                    all_products.append(node)
            page_info = products_conn.get("pageInfo") or {}
            if page_info.get("hasNextPage"):
                after = page_info.get("endCursor")
            else:
                break

        # Compose KB
        lines: List[str] = []
        lines.append("### Products (auto-synced)\n")
        for p in all_products:
            lines.append(_format_block(p))

        kb_path = os.path.join(os.path.dirname(__file__), "astrosouks_knowledgebase.txt")
        with open(kb_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"AstroSouks KB updated with {len(all_products)} products: {kb_path}")
        return kb_path
    except Exception as e:
        logger.error(f"Product sync failed: {e}")
        return None


async def run_product_sync_once() -> Optional[str]:
    import asyncio
    return await asyncio.to_thread(perform_sync)


