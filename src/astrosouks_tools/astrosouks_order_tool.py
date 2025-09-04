#!/usr/bin/env python3
"""
AstroSouks Order Tool for the AstroSouks AI Agent

Creates real orders (no discount) or discounted draft orders (when a discount is requested)
using the Shopify GraphQL Admin API. Product and variant IDs are resolved live from the
AstroSouks store.

Env (from .env):
  - ASTROSOUKS_SHOPIFY_SHOP_DOMAIN (required)
  - ASTROSOUKS_SHOPIFY_TOKEN       (required)
"""

import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from dotenv import load_dotenv
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig

from shopify_method import ShopifyClient
from src.multi_tenant_database import db as local_db


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
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


@dataclass
class ResolvedVariant:
    product_id: str
    product_title: str
    variant_id: str
    variant_title: str
    unit_price: Optional[float]


class AstroSouksOrderManager:
    """
    AstroSouks Order Manager for creating orders with optional discount support.
    When a discount is provided, a Draft Order is created with discounted line-item prices.
    Otherwise, a real Order is created.
    """

    def __init__(self):
        load_dotenv()
        shop_domain = os.getenv("ASTROSOUKS_SHOPIFY_SHOP_DOMAIN")
        access_token = os.getenv("ASTROSOUKS_SHOPIFY_TOKEN")
        if not shop_domain or not access_token:
            raise ValueError("Missing AstroSouks Shopify credentials in environment variables")
        self.client = ShopifyClient(shop_domain=shop_domain, access_token=access_token)

    def _fetch_active_products(self) -> List[Dict[str, Any]]:
        all_products: List[Dict[str, Any]] = []
        first = 100
        after: Optional[str] = None
        query = "status:active"
        while True:
            data = self.client._make_graphql_request(
                PAGINATED_ACTIVE_PRODUCTS_QUERY, {"first": first, "after": after, "query": query}
            )
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

    def _resolve_variant(self, product_name: str, variant_title: Optional[str] = None) -> Optional[ResolvedVariant]:
        # Find product by title (case-insensitive contains)
        pname = (product_name or "").strip().lower()
        products = self._fetch_active_products()
        target = None
        for p in products:
            title = (p.get("title") or "").lower()
            handle = (p.get("handle") or "").lower()
            if pname in title or pname in handle:
                target = p
                break
        if not target:
            return None

        # Fetch variants with price using the helper method
        try:
            product_id_numeric = target.get("id")
            details = self.client.get_product_variants(product_id=product_id_numeric)
            if not details.get("success"):
                return None
            variants = details.get("data", {}).get("variants", [])
            chosen = None
            vtitle = (variant_title or "").strip().lower()
            if vtitle:
                for v in variants:
                    if (v.get("title") or "").lower() == vtitle:
                        chosen = v
                        break
            if chosen is None and variants:
                chosen = variants[0]
            if not chosen:
                return None
            price_val: Optional[float] = None
            try:
                if chosen.get("price") is not None:
                    price_val = float(chosen.get("price"))
            except Exception:
                price_val = None

            return ResolvedVariant(
                product_id=product_id_numeric,
                product_title=target.get("title") or product_name,
                variant_id=chosen.get("id"),
                variant_title=chosen.get("title") or "",
                unit_price=price_val,
            )
        except Exception:
            return None

    def _build_line_items(self, selections: List[Dict[str, Any]], discount_percent: float = 0.0) -> Dict[str, Any]:
        """
        Resolve variant IDs and build line items for either real order or draft order.
        For draft order (discount>0), include price overrides per line item.
        """
        resolved: List[Dict[str, Any]] = []
        errors: List[str] = []
        for item in selections:
            name = item.get("product_name") or item.get("name")
            qty = int(item.get("quantity", 1))
            vtitle = item.get("variant_title")
            if not name:
                errors.append("Missing product_name in selection")
                continue
            rv = self._resolve_variant(name, vtitle)
            if not rv:
                errors.append(f"Product not found or has no variants: {name}")
                continue
            entry: Dict[str, Any] = {
                "product_name": rv.product_title,
                "variant_title": rv.variant_title,
                "variant_id": rv.variant_id,
                "quantity": qty,
            }
            if discount_percent > 0 and rv.unit_price is not None:
                discounted = max(0.0, rv.unit_price * (1.0 - float(discount_percent) / 100.0))
                entry["price"] = round(discounted, 2)
            resolved.append(entry)
        return {"line_items": resolved, "errors": errors}

    def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create an AstroSouks order.
        - If discount_percent > 0: create a Draft Order with discounted prices.
        - Else: create a real Order and adjust inventory.
        """
        try:
            customer_info = order_data.get('customer_info', {})
            selections = order_data.get('line_items', [])
            shipping_address = order_data.get('shipping_address', {})
            billing_address = order_data.get('billing_address', {}) or shipping_address
            order_notes = order_data.get('order_notes', '')
            discount_percent = float(order_data.get('discount_percent') or 0)

            if not customer_info.get('email'):
                return {"success": False, "error": "Customer email is required"}
            if not selections:
                return {"success": False, "error": "At least one line item is required"}
            if discount_percent < 0 or discount_percent > 100:
                return {"success": False, "error": "discount_percent must be between 0 and 100"}

            # Resolve items
            built = self._build_line_items(selections, discount_percent=discount_percent)
            if built["errors"]:
                return {"success": False, "error": "; ".join(built["errors"]) }

            # Create Draft Order with discounted prices
            if discount_percent > 0:
                draft_items: List[Dict[str, Any]] = []
                for li in built["line_items"]:
                    entry = {
                        "variantId": li["variant_id"],
                        "quantity": li["quantity"],
                    }
                    if "price" in li:
                        entry["price"] = li["price"]
                    draft_items.append(entry)
                draft_result = self.client.create_draft_order(
                    line_items=draft_items,
                    customer_info={"email": customer_info.get('email')}
                )
                if not draft_result.get('success'):
                    return {"success": False, "error": f"Failed to create discounted draft order: {draft_result.get('error')}"}
                return {"success": True, "type": "draft_order", "data": draft_result.get('data'), "discount_percent": discount_percent}

            # Else create a real order (no discount)
            order_line_items = [{"variantId": li["variant_id"], "quantity": li["quantity"]} for li in built["line_items"]]
            result = self.client.create_order(
                line_items=order_line_items,
                customer_info=customer_info,
                shipping_address=shipping_address,
                billing_address=billing_address,
                send_receipt=True,
                send_fulfillment_receipt=False,
            )
            if not result.get('success'):
                return {"success": False, "error": f"Failed to create order: {result.get('error')}"}

            order = result.get('data')

            # Adjust inventory
            inventory_adjustments = []
            inventory_errors = []
            for li in built["line_items"]:
                try:
                    clean_variant_id = str(li["variant_id"]).replace('gid://shopify/ProductVariant/', '')
                    inv_res = self.client.adjust_inventory(
                        variant_id=clean_variant_id,
                        quantity_change=-int(li["quantity"]),
                        reason="correction"
                    )
                    if inv_res.get('success'):
                        inventory_adjustments.append(inv_res.get('data'))
                    else:
                        inventory_errors.append({"variant_id": li["variant_id"], "error": inv_res.get('error')})
                except Exception as e:
                    inventory_errors.append({"variant_id": li.get("variant_id"), "error": str(e)})

            # Optionally save order to DB when metadata present
            metadata = order_data.get('metadata', {}) if isinstance(order_data, dict) else {}
            db_user_id = metadata.get('user_id')
            db_contact_id = metadata.get('contact_id')
            if db_user_id and db_contact_id:
                try:
                    local_db.create_order_and_items(user_id=db_user_id, contact_id=db_contact_id, shopify_order_data={
                        "order": order,
                        "inventory_adjustments": {"successful": inventory_adjustments, "errors": inventory_errors},
                        "input_items": built["line_items"],
                    })
                except Exception:
                    pass

            return {"success": True, "type": "order", "data": order, "inventory": {"successful": inventory_adjustments, "errors": inventory_errors}}
        except Exception as e:
            return {"success": False, "error": f"Error creating AstroSouks order: {str(e)}"}


def _parse_product_selections_json(text: str) -> List[Dict[str, Any]]:
    import json
    try:
        arr = json.loads(text)
        if isinstance(arr, list):
            return arr
        return []
    except Exception:
        return []


@tool
def create_astrosouks_order(
    customer_email: str = "",
    customer_first_name: str = "",
    customer_last_name: str = "",
    customer_phone: str = "",
    shipping_address_line1: str = "",
    shipping_address_line2: str = "",
    shipping_city: str = "",
    shipping_province: str = "",
    shipping_country: str = "",
    shipping_postal_code: str = "",
    product_selections: str = "",
    billing_same_as_shipping: bool = True,
    billing_address_line1: str = "",
    billing_address_line2: str = "",
    billing_city: str = "",
    billing_province: str = "",
    billing_country: str = "",
    billing_postal_code: str = "",
    order_notes: str = "",
    discount_percent: float = 0.0,
    *,
    config: RunnableConfig
) -> str:
    """
    Create an AstroSouks order.

    - If discount_percent > 0, creates a discounted DRAFT ORDER (line-item prices overridden).
    - If no discount, creates a real ORDER and adjusts inventory.

    product_selections JSON example:
      '[{"product_name": "Food Vacuum Sealer", "quantity": 2, "variant_title": "10 Bags"}]'
    """
    try:
        # Validate required fields
        required = {
            'customer_email': customer_email,
            'shipping_address_line1': shipping_address_line1,
            'shipping_city': shipping_city,
            'shipping_province': shipping_province,
            'shipping_country': shipping_country,
            'shipping_postal_code': shipping_postal_code,
        }
        missing = [k for k, v in required.items() if not v or str(v).strip() == ""]
        if missing and discount_percent <= 0:
            return f"❌ Error: Missing required fields: {', '.join(missing)}"

        selections = _parse_product_selections_json(product_selections)
        if not selections:
            return "❌ Error: Invalid or empty product_selections JSON."

        om = AstroSouksOrderManager()
        order_data = {
            'customer_info': {
                'email': customer_email.strip(),
                'first_name': customer_first_name.strip(),
                'last_name': customer_last_name.strip(),
                'phone': customer_phone.strip(),
            },
            'line_items': selections,
            'shipping_address': {
                'address1': shipping_address_line1.strip(),
                'address2': shipping_address_line2.strip(),
                'city': shipping_city.strip(),
                'province': shipping_province.strip(),
                'country': shipping_country.strip(),
                'zip': shipping_postal_code.strip(),
                'postal_code': shipping_postal_code.strip(),
                'first_name': customer_first_name.strip(),
                'last_name': customer_last_name.strip(),
                'phone': customer_phone.strip(),
            },
            'billing_address': {
                'address1': (billing_address_line1 or shipping_address_line1).strip(),
                'address2': (billing_address_line2 or shipping_address_line2).strip(),
                'city': (billing_city or shipping_city).strip(),
                'province': (billing_province or shipping_province).strip(),
                'country': (billing_country or shipping_country).strip(),
                'zip': (billing_postal_code or shipping_postal_code).strip(),
                'postal_code': (billing_postal_code or shipping_postal_code).strip(),
                'first_name': customer_first_name.strip(),
                'last_name': customer_last_name.strip(),
                'phone': customer_phone.strip(),
            } if not billing_same_as_shipping else None,
            'order_notes': order_notes.strip(),
            'discount_percent': discount_percent,
            'metadata': config.get('metadata', {}) if hasattr(config, 'get') else {},
        }

        result = om.create_order(order_data)
        if not result.get('success'):
            return f"❌ Error creating AstroSouks order: {result.get('error')}"

        if result.get('type') == 'draft_order':
            draft = result.get('data', {})
            return (
                "✅ AstroSouks DISCOUNTED DRAFT ORDER CREATED\n\n"
                f"• Draft Order ID: {draft.get('id')}\n"
                f"• Status: {draft.get('status')}\n"
                f"• Discount Applied: {discount_percent}%\n"
                "• Next: Complete the draft order in Shopify to finalize the sale."
            )

        # Else real order
        order = result.get('data', {})
        return (
            "✅ AstroSouks ORDER CREATED SUCCESSFULLY!\n\n"
            f"• Order Number: {order.get('name')}\n"
            f"• Order ID: {order.get('id')}\n"
            f"• Status: {order.get('status', 'pending')}\n"
        )

    except Exception as e:
        return f"❌ Error creating AstroSouks order: {str(e)}"

