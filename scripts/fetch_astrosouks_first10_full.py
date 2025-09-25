"""
Fetch the first 10 products from the AstroSouks Shopify store with rich details
(including per-variant prices and compare-at prices to infer discounts) and save
them to a structured text file in the project root.

Env (from .env):
  - ASTROSOUKS_SHOPIFY_SHOP_DOMAIN (required)
  - ASTROSOUKS_SHOPIFY_TOKEN       (required)

Usage:
  python scripts/fetch_astrosouks_first10_full.py
"""

import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from shopify_method import ShopifyClient
from shopify_method.utils import extract_id_from_gid


def _sanitize_filename_component(text: str) -> str:
    sanitized = (text or "").strip().lower()
    for ch in [" ", ".", "/", "\\", ":", "*", "?", "\"", "<", ">", "|"]:
        sanitized = sanitized.replace(ch, "_")
    sanitized = sanitized.replace("-", "_")
    return sanitized[:80] or "store"


def _fmt_discount(price: Optional[Any], compare_at: Optional[Any]) -> str:
    try:
        if price is None or compare_at is None:
            return ""
        p = float(price)
        c = float(compare_at)
        if c > p and p > 0:
            pct = round((c - p) / c * 100.0, 2)
            return f" | discount={pct}%"
        return ""
    except Exception:
        return ""


def _strip_html(text: str) -> str:
    try:
        return re.sub(r"<[^>]+>", "", text)
    except Exception:
        return text


def _extract_description_from_product_dict(pd: Dict[str, Any]) -> str:
    for key in ("description", "descriptionHtml", "bodyHtml"):
        val = pd.get(key)
        if isinstance(val, str) and val.strip():
            return _strip_html(val).strip()
    return ""


def _format_product_block(p: Dict[str, Any], client: Optional[ShopifyClient] = None) -> str:
    lines: List[str] = []
    title = p.get("title") or p.get("handle") or "Unknown"
    lines.append(f"# {title}")
    lines.append(
        "ID: {id}  |  Handle: {handle}  |  Status: {status}  |  Vendor: {vendor}  |  Type: {ptype}".format(
            id=p.get("id"),
            handle=p.get("handle"),
            status=p.get("status"),
            vendor=p.get("vendor"),
            ptype=p.get("productType"),
        )
    )
    tags = p.get("tags") or []
    if isinstance(tags, list):
        lines.append(f"Tags: {', '.join(tags)}")
    created = p.get("createdAt")
    updated = p.get("updatedAt")
    lines.append(f"Created: {created}  |  Updated: {updated}")

    # Description (prefer inline; fallback to per-product API if missing)
    desc = _extract_description_from_product_dict(p)
    if not desc and client is not None:
        gid = p.get("id")
        try:
            numeric_id = extract_id_from_gid(gid) if gid else None
        except Exception:
            numeric_id = None
        if numeric_id:
            details = client.get_product(product_id=str(numeric_id))
            if details.get("success"):
                prod = details.get("data") or {}
                desc = _extract_description_from_product_dict(prod)
    if desc:
        lines.append("Description:")
        for ln in desc.splitlines():
            lines.append(f"  {ln}")

    # Images (limit to top 5 to keep concise)
    images_list = p.get("images") or []
    lines.append(f"Images (up to 5): {min(len(images_list), 5)} of {len(images_list)} total")
    for node in images_list[:5]:
        url = node.get("src") or node.get("url")
        alt = node.get("altText")
        if url:
            if alt:
                lines.append(f"  - {url}  (alt: {alt})")
            else:
                lines.append(f"  - {url}")

    # Variants
    var_list = p.get("variants") or []
    lines.append(f"Variants: {len(var_list)}")
    for node in var_list:
        price = node.get("price")
        compare = node.get("compareAtPrice")
        # Build a human-friendly price block: "was $X, now $Y (Z% off)" when discounted
        price_block = None
        try:
            if price is not None and compare is not None:
                p = float(price)
                c = float(compare)
                if c > p and p > 0:
                    pct = round((c - p) / c * 100.0, 2)
                    price_block = f"price: was ${c:.2f}, now ${p:.2f} ({pct}% off)"
                else:
                    price_block = f"price=${p:.2f} | compareAt=${c:.2f}"
            elif price is not None:
                p = float(price)
                price_block = f"price=${p:.2f}"
        except Exception:
            # Fallback plain values
            price_block = f"price={price} | compareAt={compare}" if (price is not None or compare is not None) else "price=N/A"
        sku = node.get("sku")
        barcode = node.get("barcode")
        inv = node.get("inventoryQuantity")
        avail = node.get("availableForSale")
        vtitle = node.get("title")
        vid = node.get("id")
        lines.append(
            "  - {vtitle} | {price_block} | id={vid} | sku={sku} | barcode={barcode} | inv={inv} | available={avail}".format(
                vtitle=vtitle,
                price_block=price_block or "price=N/A",
                vid=vid,
                sku=sku,
                barcode=barcode,
                inv=inv,
                avail=avail,
            )
        )
        # Variant selected options (if present)
        sel = node.get("selectedOptions")
        if isinstance(sel, list) and sel:
            try:
                opts = ", ".join([
                    f"{(o or {}).get('name')}: {(o or {}).get('value')}" for o in sel
                    if isinstance(o, dict)
                ])
                if opts.strip():
                    lines.append(f"    options: {opts}")
            except Exception:
                pass

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    load_dotenv()

    shop_domain = os.getenv("ASTROSOUKS_SHOPIFY_SHOP_DOMAIN") or os.getenv("SHOPIFY_SHOP_DOMAIN")
    access_token = os.getenv("ASTROSOUKS_SHOPIFY_TOKEN") or os.getenv("SHOPIFY_ACCESS_TOKEN")

    if not shop_domain or not access_token:
        print("ERROR: Missing env vars. Set ASTROSOUKS_SHOPIFY_SHOP_DOMAIN and ASTROSOUKS_SHOPIFY_TOKEN in .env.")
        return

    client = ShopifyClient(shop_domain=shop_domain, access_token=access_token)

    result = client.get_products_full(limit=10)
    if not result.get("success"):
        print(f"ERROR: {result.get('error')}")
        return

    data = result.get("data") or {}
    products = data.get("products") or []

    domain_component = _sanitize_filename_component(shop_domain)
    out_path = os.path.join(os.path.dirname(__file__), f"../astrosouks_first10_products_{domain_component}.txt")
    out_path = os.path.abspath(out_path)

    lines: List[str] = []
    lines.append(f"Shop Domain: {shop_domain}")
    lines.append(f"Product Count (requested 10): {len(products)}")
    lines.append("")

    for p in products:
        lines.append(_format_product_block(p))

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Saved first 10 products (full details) to {out_path}")


if __name__ == "__main__":
    main()


