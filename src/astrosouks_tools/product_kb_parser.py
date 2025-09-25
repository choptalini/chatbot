"""
Parser utilities for the Astrosouks unified product knowledge base file.

This module reads the text file (default: astrosouks_knowledgebase.txt) and extracts
structured product details for use by tools (WhatsApp, Order, CAG context helpers).

Expected product block pattern (robust to extra sections):

#### **<Product Name>**
ID: <gid> | Handle: <handle> | Type: <type> | Vendor: <vendor> | Tags: t1, t2 | Status: ACTIVE | Availability: in stock
* **Price:** $<current>
On sale from $<original>               # optional
**Image:** https://...                 # optional
**Variants:**                          # optional
  - <title> | sku=<sku> | price=$X | compareAt=$Y | inv=N | available=True
---

This parser is tolerant of the older KB style (without ID/Handle/Image lines). It
extracts at minimum: product_name, price_current, price_compare_at (if present), and
first image URL when provided.
"""

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


KB_FILENAME = os.path.join(os.path.dirname(__file__), "astrosouks_knowledgebase.txt")


@dataclass
class VariantRow:
    title: Optional[str]
    sku: Optional[str]
    price: Optional[float]
    compare_at: Optional[float]
    inventory_quantity: Optional[int]
    available: Optional[bool]


@dataclass
class ProductRecord:
    name: str
    id_gid: Optional[str]
    handle: Optional[str]
    product_type: Optional[str]
    vendor: Optional[str]
    tags: List[str]
    status: Optional[str]
    availability: Optional[str]
    price_current: Optional[float]
    price_compare_at: Optional[float]
    image_url: Optional[str]
    description: Optional[str]
    variants: List[VariantRow]


_re_header = re.compile(r"^#### \*\*(?P<name>.+)\*\*\s*$")
_re_idline = re.compile(r"ID:\s*(?P<id>[^|]+)")
_re_handle = re.compile(r"Handle:\s*(?P<handle>[^|]+)")
_re_type = re.compile(r"Type:\s*(?P<type>[^|]+)")
_re_vendor = re.compile(r"Vendor:\s*(?P<vendor>[^|]+)")
_re_tags = re.compile(r"Tags:\s*(?P<tags>[^|]+)")
_re_status = re.compile(r"Status:\s*(?P<status>[^|]+)")
_re_avail = re.compile(r"Availability:\s*(?P<availability>[^|]+)")
_re_price_line = re.compile(r"\*\s*\*\*Price:\*\*\s*\$?(?P<price>\d+(?:\.\d{1,2})?)", re.IGNORECASE)
_re_onsale = re.compile(r"On sale from\s*\$?(?P<orig>\d+(?:\.\d{1,2})?)", re.IGNORECASE)
_re_image = re.compile(r"\*\*Image:\*\*\s*(?P<url>https?://\S+)")
_re_variant_row = re.compile(
    r"^\s*-\s*(?P<title>[^|]+)\s*\|.*?sku=(?P<sku>[^|]*)\s*\|\s*price=\$?(?P<price>\d+(?:\.\d{1,2})?)\s*\|\s*compareAt=\$?(?P<cmp>\d+(?:\.\d{1,2})?)?\s*\|\s*inv=(?P<inv>-?\d+)\s*\|\s*available=(?P<avail>true|false)\s*$",
    re.IGNORECASE,
)


def _to_float(s: Optional[str]) -> Optional[float]:
    try:
        if s is None:
            return None
        return float(str(s).strip())
    except Exception:
        return None


def _parse_info_line(line: str) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {
        "id": None,
        "handle": None,
        "type": None,
        "vendor": None,
        "tags": None,
        "status": None,
        "availability": None,
    }
    m = _re_idline.search(line)
    if m:
        out["id"] = m.group("id").strip()
    m = _re_handle.search(line)
    if m:
        out["handle"] = m.group("handle").strip()
    m = _re_type.search(line)
    if m:
        out["type"] = m.group("type").strip()
    m = _re_vendor.search(line)
    if m:
        out["vendor"] = m.group("vendor").strip()
    m = _re_tags.search(line)
    if m:
        out["tags"] = m.group("tags").strip()
    m = _re_status.search(line)
    if m:
        out["status"] = m.group("status").strip()
    m = _re_avail.search(line)
    if m:
        out["availability"] = m.group("availability").strip()
    return out


def parse_products_from_text(kb_text: str) -> List[ProductRecord]:
    lines = kb_text.splitlines()
    products: List[ProductRecord] = []
    cur: Optional[ProductRecord] = None
    capture_desc = False
    for raw in lines:
        line = raw.rstrip("\n")
        m_header = _re_header.match(line.strip())
        if m_header:
            # Push previous
            if cur is not None:
                products.append(cur)
            cur = ProductRecord(
                name=m_header.group("name").strip(),
                id_gid=None,
                handle=None,
                product_type=None,
                vendor=None,
                tags=[],
                status=None,
                availability=None,
                price_current=None,
                price_compare_at=None,
                image_url=None,
                description=None,
                variants=[],
            )
            capture_desc = False
            continue

        if cur is None:
            continue

        # Info line
        if "ID:" in line and ("Handle:" in line or "Vendor:" in line or "Type:" in line):
            info = _parse_info_line(line)
            cur.id_gid = info.get("id")
            cur.handle = info.get("handle")
            cur.product_type = info.get("type")
            cur.vendor = info.get("vendor")
            if info.get("tags"):
                cur.tags = [t.strip() for t in (info["tags"] or "").split(",") if t.strip()]
            cur.status = info.get("status")
            cur.availability = info.get("availability")
            continue

        # Price line
        m_price = _re_price_line.search(line)
        if m_price:
            cur.price_current = _to_float(m_price.group("price"))
            # Next line might contain On sale from ... (but we also check this line)
            m_os = _re_onsale.search(line)
            if m_os:
                cur.price_compare_at = _to_float(m_os.group("orig"))
            capture_desc = False
            continue

        # On sale line possibly separated
        m_os2 = _re_onsale.search(line)
        if m_os2 and cur.price_compare_at is None:
            cur.price_compare_at = _to_float(m_os2.group("orig"))
            continue

        # Image line
        m_img = _re_image.search(line)
        if m_img:
            cur.image_url = m_img.group("url").strip()
            continue

        # Variants header
        if line.strip().startswith("**Variants**"):
            capture_desc = False
            continue

        # Variant rows
        m_v = _re_variant_row.match(line)
        if m_v:
            try:
                cur.variants.append(
                    VariantRow(
                        title=(m_v.group("title") or "").strip(),
                        sku=(m_v.group("sku") or "").strip() or None,
                        price=_to_float(m_v.group("price")),
                        compare_at=_to_float(m_v.group("cmp")),
                        inventory_quantity=int(m_v.group("inv")),
                        available=(m_v.group("avail").lower() == "true"),
                    )
                )
            except Exception:
                pass
            continue

        # Description capture: start when a line starts with '**Description:**'
        if line.strip().startswith("**Description:**"):
            cur.description = line.split("**Description:**", 1)[-1].strip()
            capture_desc = True
            continue

        # Continue capturing subsequent description lines until a delimiter or section header
        if capture_desc:
            if line.strip().startswith("**") or line.strip().startswith("#### ") or line.strip() == "---":
                capture_desc = False
            else:
                # Append to description
                cur.description = (cur.description or "") + ("\n" if cur.description else "") + line.strip()

        # End of product block
        if line.strip() == "---":
            capture_desc = False
            continue

    if cur is not None:
        products.append(cur)
    return products


def load_products_map(kb_path: Optional[str] = None) -> Dict[str, ProductRecord]:
    path = kb_path or KB_FILENAME
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return {}
    out: Dict[str, ProductRecord] = {}
    for rec in parse_products_from_text(text):
        out[rec.name.strip().lower()] = rec
    return out


def get_product_names(kb_path: Optional[str] = None) -> List[str]:
    return [rec.name for rec in load_products_map(kb_path).values()]


def get_image_url_for_product(name: str, kb_path: Optional[str] = None) -> Optional[str]:
    m = load_products_map(kb_path)
    rec = m.get(str(name).strip().lower())
    return rec.image_url if rec else None


def get_prices_for_product(name: str, kb_path: Optional[str] = None) -> Tuple[Optional[float], Optional[float]]:
    m = load_products_map(kb_path)
    rec = m.get(str(name).strip().lower())
    if not rec:
        return None, None
    return rec.price_current, rec.price_compare_at


