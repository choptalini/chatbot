#!/usr/bin/env python3
"""
AstroSouks Order Tool for the AstroSouks AI Agent

Creates real orders (no discount) or discounted draft orders (when a discount is requested)
using Shopify Admin APIs: GraphQL is used for catalog lookups, while ALL order creation
(orders and draft orders) is performed via the REST Admin API for maximum compatibility.

Env (from .env):
  - ASTROSOUKS_SHOPIFY_SHOP_DOMAIN (required)
  - ASTROSOUKS_SHOPIFY_TOKEN       (required)
"""

import os
from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass
import json
import logging
import time
from datetime import datetime

from pydantic import BaseModel, ValidationError, field_validator

from dotenv import load_dotenv
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig

from shopify_method import ShopifyClient
from src.multi_tenant_database import db as local_db
from src.astrosouks_tools.product_kb_parser import get_product_names

# Set up logging for order tool
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# Dynamic product name validation derived from the KB
def _is_valid_product_name(name: str) -> bool:
    try:
        available = set(n.lower() for n in get_product_names())
        return name.strip().lower() in available
    except Exception:
        # If KB not available, fall back to allowing any string; downstream resolution will fail if not found
        return isinstance(name, str) and bool(name.strip())


class ProductSelection(BaseModel):
    """Pydantic model for validating product selections"""
    product_name: str
    quantity: int
    variant_title: str = ""
    
    @field_validator('quantity')
    @classmethod
    def quantity_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('quantity must be positive')
        return v


class OrderValidationInput(BaseModel):
    """Pydantic model for validating order inputs"""
    product_selections: str  # JSON string of ProductSelection list
    
    @field_validator('product_selections')
    @classmethod
    def validate_product_selections(cls, v):
        try:
            selections_data = json.loads(v)
            if not isinstance(selections_data, list):
                raise ValueError('product_selections must be a JSON array')
            
            # Validate each selection using ProductSelection model
            validated_selections = []
            for item in selections_data:
                validated_item = ProductSelection(**item)
                # Dynamic product name validation
                if not _is_valid_product_name(validated_item.product_name):
                    raise ValueError(f"Unknown product name: {validated_selections and validated_selections[-1].product_name or validated_item.product_name}")
                validated_selections.append(validated_item)
            
            return v  # Return original JSON string
        except json.JSONDecodeError:
            raise ValueError('product_selections must be valid JSON')
        except ValidationError as e:
            raise ValueError(f'Invalid product selection: {e}')


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
        init_start_time = time.time()
        logger.info(f"🔧 INITIALIZING AstroSouksOrderManager at {datetime.now().isoformat()}")
        
        load_dotenv()
        shop_domain = os.getenv("ASTROSOUKS_SHOPIFY_SHOP_DOMAIN")
        access_token = os.getenv("ASTROSOUKS_SHOPIFY_TOKEN")
        
        logger.debug(f"📋 Shop domain: {shop_domain[:20]}..." if shop_domain else "❌ No shop domain")
        logger.debug(f"🔑 Access token: {'✅ Present' if access_token else '❌ Missing'}")
        
        if not shop_domain or not access_token:
            logger.error("❌ Missing AstroSouks Shopify credentials in environment variables")
            raise ValueError("Missing AstroSouks Shopify credentials in environment variables")
            
        logger.info(f"🚀 Creating ShopifyClient for domain: {shop_domain}")
        self.client = ShopifyClient(shop_domain=shop_domain, access_token=access_token)
        
        init_duration = time.time() - init_start_time
        logger.info(f"✅ AstroSouksOrderManager initialized in {init_duration:.3f}s")

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

    def _build_line_items(self, selections: List[Dict[str, Any]], forced_discount_percent: float = 0.0, enable_auto_volume: bool = True) -> Dict[str, Any]:
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
                "unit_price": rv.unit_price,
            }
            # Determine effective discount percent for this line
            # Priority: explicit forced_discount_percent; else volume tiers (2=>10%, 3+=>15%) if enabled
            effective_discount = 0.0
            try:
                if float(forced_discount_percent) > 0:
                    effective_discount = float(forced_discount_percent)
                elif enable_auto_volume:
                    if qty >= 3:
                        effective_discount = 15.0
                    elif qty == 2:
                        effective_discount = 10.0
            except Exception:
                effective_discount = 0.0

            if effective_discount > 0 and rv.unit_price is not None:
                discounted = max(0.0, rv.unit_price * (1.0 - effective_discount / 100.0))
                entry["price"] = round(discounted, 2)
                entry["applied_discount_percent"] = effective_discount
            resolved.append(entry)
        return {"line_items": resolved, "errors": errors}

    def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create an AstroSouks order.
        - If discount_percent > 0: create a Draft Order with discounted prices.
        - Else: create a real Order and adjust inventory.
        """
        order_start_time = time.time()
        order_id = f"ORDER_{int(time.time() * 1000)}"  # Unique ID for tracking
        
        logger.info(f"🛒 STARTING ORDER CREATION [{order_id}] at {datetime.now().isoformat()}")
        logger.debug(f"📦 Order data keys: {list(order_data.keys())}")
        
        try:
            customer_info = order_data.get('customer_info', {})
            selections = order_data.get('line_items', [])
            shipping_address = order_data.get('shipping_address', {})
            billing_address = order_data.get('billing_address', {}) or shipping_address
            order_notes = order_data.get('order_notes', '')
            forced_discount_percent = float(order_data.get('forced_discount_percent') or 0)
            enable_auto_volume = bool(order_data.get('enable_auto_volume', True))
            
            logger.info(f"👤 Customer: {customer_info.get('first_name', '')} {customer_info.get('last_name', '')}")
            logger.info(f"📱 Phone: {customer_info.get('phone', 'N/A')}")
            logger.info(f"🏠 Shipping: {shipping_address.get('city', '')}, {shipping_address.get('country', '')}")
            logger.info(f"🛍️  Line items count: {len(selections)}")
            logger.info(f"💰 Forced discount: {forced_discount_percent}%")
            logger.info(f"📝 Order notes: {order_notes[:50]}..." if len(order_notes) > 50 else f"📝 Order notes: {order_notes}")

            if not selections:
                logger.error(f"❌ [{order_id}] No line items provided")
                return {"success": False, "error": "At least one line item is required"}
            if forced_discount_percent < 0 or forced_discount_percent > 100:
                logger.error(f"❌ [{order_id}] Invalid discount percent: {forced_discount_percent}")
                return {"success": False, "error": "forced_discount_percent must be between 0 and 100"}

            # Log each line item in detail
            for i, selection in enumerate(selections):
                logger.info(f"🛍️  Item {i+1}: {selection.get('product_name', 'Unknown')} x{selection.get('quantity', 0)}")
                if selection.get('variant_title'):
                    logger.debug(f"   └─ Variant: {selection['variant_title']}")

            # Resolve items
            logger.info(f"🔍 [{order_id}] Building line items with discount: {forced_discount_percent}%, auto_volume: {enable_auto_volume}")
            build_start = time.time()
            built = self._build_line_items(selections, forced_discount_percent=forced_discount_percent, enable_auto_volume=enable_auto_volume)
            build_duration = time.time() - build_start
            logger.info(f"⚙️  [{order_id}] Line items built in {build_duration:.3f}s")
            
            if built["errors"]:
                logger.error(f"❌ [{order_id}] Line item errors: {built['errors']}")
                return {"success": False, "error": "; ".join(built["errors"]) }

            # Create Draft Order when any item has a price override (discount applied)
            has_any_discount = any("price" in li for li in built["line_items"])    
            logger.info(f"💸 [{order_id}] Has discount applied: {has_any_discount}")
            
            if has_any_discount:
                logger.info(f"📋 [{order_id}] CREATING DRAFT ORDER (discounted)")
                draft_items: List[Dict[str, Any]] = []
                total_discounted_value = 0.0
                
                for i, li in enumerate(built["line_items"]):
                    entry = {
                        "variantId": li["variant_id"],
                        "quantity": li["quantity"],
                    }
                    if "price" in li:
                        entry["price"] = li["price"]
                        total_discounted_value += float(li["price"]) * int(li["quantity"])
                        logger.debug(f"   Item {i+1}: {li.get('product_name')} @ ${li['price']:.2f} (discounted)")
                    else:
                        logger.debug(f"   Item {i+1}: {li.get('product_name')} @ regular price")
                    draft_items.append(entry)
                
                logger.info(f"💰 [{order_id}] Total discounted value: ${total_discounted_value:.2f}")
                logger.debug(f"📦 [{order_id}] Draft items payload: {json.dumps(draft_items, indent=2)}")
                
                # Email is optional for draft orders; only include if provided
                cust_info = {}
                if customer_info.get('email'):
                    cust_info['email'] = customer_info.get('email')
                    logger.debug(f"📧 [{order_id}] Customer email: {customer_info['email']}")
                else:
                    logger.debug(f"📧 [{order_id}] No customer email provided")
                
                logger.info(f"🚀 [{order_id}] Calling client.create_draft_order...")
                draft_start = time.time()
                draft_result = self.client.create_draft_order(
                    line_items=draft_items,
                    customer_info=cust_info or None
                )
                draft_duration = time.time() - draft_start
                logger.info(f"⏱️  [{order_id}] Draft order API call completed in {draft_duration:.3f}s")
                if not draft_result.get('success'):
                    # Fallback: if merchant hasn't granted write_draft_orders, create a REAL order via REST
                    err_msg = str(draft_result.get('error') or "")
                    logger.warning(f"⚠️  [{order_id}] Draft order failed: {err_msg}")
                    
                    if ('write_draft_orders' in err_msg) or ('status 403' in err_msg) or ('403' in err_msg):
                        logger.info(f"🔄 [{order_id}] FALLBACK: Creating real order via REST (permission issue)")
                        
                        # Build order line items including price overrides
                        order_line_items: List[Dict[str, Any]] = []
                        subtotal_override = 0.0
                        
                        logger.debug(f"📦 [{order_id}] Building fallback order line items...")
                        for i, li in enumerate(built["line_items"]):
                            oi: Dict[str, Any] = {
                                "variantId": li["variant_id"],
                                "quantity": li["quantity"],
                            }
                            if li.get("price") is not None:
                                oi["price"] = li["price"]
                                try:
                                    line_total = float(li["price"]) * int(li["quantity"])
                                    subtotal_override += line_total
                                    logger.debug(f"   Fallback Item {i+1}: {li.get('product_name')} @ ${li['price']:.2f} x{li['quantity']} = ${line_total:.2f}")
                                except Exception as e:
                                    logger.error(f"❌ [{order_id}] Error calculating line total for item {i+1}: {e}")
                            else:
                                logger.debug(f"   Fallback Item {i+1}: {li.get('product_name')} @ regular price x{li['quantity']}")
                            order_line_items.append(oi)
                        
                        logger.info(f"💰 [{order_id}] Fallback subtotal override: ${subtotal_override:.2f}")
                        logger.debug(f"📦 [{order_id}] Fallback order payload preview:")
                        logger.debug(f"   Customer: {customer_info}")
                        logger.debug(f"   Shipping: {shipping_address}")
                        logger.debug(f"   Line items count: {len(order_line_items)}")
                        logger.debug(f"   Full line items: {json.dumps(order_line_items, indent=2)}")

                        logger.info(f"🚀 [{order_id}] Calling client.create_order (FALLBACK)...")
                        fallback_start = time.time()
                        order_result = self.client.create_order(
                            line_items=order_line_items,
                            customer_info=customer_info,
                            shipping_address=shipping_address,
                            billing_address=billing_address,
                            send_receipt=True,
                            send_fulfillment_receipt=False,
                            subtotal=subtotal_override if subtotal_override > 0 else None,
                        )
                        fallback_duration = time.time() - fallback_start
                        logger.info(f"⏱️  [{order_id}] Fallback order API call completed in {fallback_duration:.3f}s")
                        
                        if not order_result.get('success'):
                            fallback_error = order_result.get('error', 'Unknown error')
                            logger.error(f"❌ [{order_id}] FALLBACK ORDER FAILED: {fallback_error}")
                            logger.error(f"🔍 [{order_id}] Final payload that failed:")
                            logger.error(f"   Line items: {json.dumps(order_line_items, indent=2)}")
                            logger.error(f"   Customer info: {json.dumps(customer_info, indent=2)}")
                            logger.error(f"   Shipping address: {json.dumps(shipping_address, indent=2)}")
                            return {"success": False, "error": f"Failed to create discounted order (fallback): {fallback_error}"}

                        order = order_result.get('data')
                        # Pricing breakdown using overridden prices
                        subtotal = 0.0
                        lines: List[Dict[str, Any]] = []
                        for li in built["line_items"]:
                            price_each = float(li.get("price") or 0)
                            qty = int(li.get("quantity") or 0)
                            line_total = round(price_each * qty, 2)
                            subtotal = round(subtotal + line_total, 2)
                            lines.append({
                                "name": li.get("product_name"),
                                "quantity": qty,
                                "price_each": price_each,
                                "line_total": line_total,
                            })
                        shipping_fee = 0.0 if subtotal >= 40.0 else 3.0
                        total = round(subtotal + shipping_fee, 2)

                        return {
                            "success": True,
                            "type": "order",
                            "data": order,
                            "pricing": {
                                "lines": lines,
                                "subtotal": subtotal,
                                "shipping_fee": shipping_fee,
                                "total": total,
                            }
                        }
                    draft_error = draft_result.get('error', 'Unknown error')
                    logger.error(f"❌ [{order_id}] DRAFT ORDER FAILED (no fallback): {draft_error}")
                    return {"success": False, "error": f"Failed to create discounted draft order: {draft_error}"}

                # Pricing breakdown (tool-side) using discounted line prices
                subtotal = 0.0
                lines: List[Dict[str, Any]] = []
                for li in built["line_items"]:
                    price_each = float(li.get("price") or 0)
                    qty = int(li.get("quantity") or 0)
                    line_total = round(price_each * qty, 2)
                    subtotal = round(subtotal + line_total, 2)
                    lines.append({
                        "name": li.get("product_name"),
                        "quantity": qty,
                        "price_each": price_each,
                        "line_total": line_total,
                    })
                shipping_fee = 0.0 if subtotal >= 40.0 else 3.0
                total = round(subtotal + shipping_fee, 2)

                return {
                    "success": True,
                    "type": "draft_order",
                    "data": draft_result.get('data'),
                    "pricing": {
                        "lines": lines,
                        "subtotal": subtotal,
                        "shipping_fee": shipping_fee,
                        "total": total,
                    }
                }

            # Else create a real order (no discount)
            logger.info(f"🛒 [{order_id}] CREATING REGULAR ORDER (no discount)")
            
            # Calculate subtotal for shipping logic
            subtotal = 0.0
            for li in built["line_items"]:
                if li.get("unit_price") is not None:
                    subtotal += float(li["unit_price"]) * int(li["quantity"])
            
            logger.info(f"💰 [{order_id}] Regular order subtotal: ${subtotal:.2f}")
            
            order_line_items = [{"variantId": li["variant_id"], "quantity": li["quantity"]} for li in built["line_items"]]
            logger.debug(f"📦 [{order_id}] Regular order line items: {json.dumps(order_line_items, indent=2)}")
            
            logger.info(f"🚀 [{order_id}] Calling client.create_order (REGULAR)...")
            regular_start = time.time()
            result = self.client.create_order(
                line_items=order_line_items,
                customer_info=customer_info,
                shipping_address=shipping_address,
                billing_address=billing_address,
                send_receipt=True,
                send_fulfillment_receipt=False,
                subtotal=subtotal,
            )
            regular_duration = time.time() - regular_start
            logger.info(f"⏱️  [{order_id}] Regular order API call completed in {regular_duration:.3f}s")
            
            if not result.get('success'):
                regular_error = result.get('error', 'Unknown error')
                logger.error(f"❌ [{order_id}] REGULAR ORDER FAILED: {regular_error}")
                logger.error(f"🔍 [{order_id}] Regular order context:")
                logger.error(f"   Line items: {json.dumps(order_line_items, indent=2)}")
                logger.error(f"   Customer: {json.dumps(customer_info, indent=2)}")
                logger.error(f"   Subtotal: ${subtotal:.2f}")
                return {"success": False, "error": f"Failed to create order: {regular_error}"}

            order = result.get('data')

            # Adjust inventory
            logger.info(f"📦 [{order_id}] Adjusting inventory for {len(built['line_items'])} items...")
            inventory_adjustments = []
            inventory_errors = []
            for i, li in enumerate(built["line_items"]):
                try:
                    clean_variant_id = str(li["variant_id"]).replace('gid://shopify/ProductVariant/', '')
                    quantity_change = -int(li["quantity"])
                    logger.debug(f"   Adjusting item {i+1}: variant {clean_variant_id} by {quantity_change}")
                    
                    inv_res = self.client.adjust_inventory(
                        variant_id=clean_variant_id,
                        quantity_change=quantity_change,
                        reason="correction"
                    )
                    if inv_res.get('success'):
                        inventory_adjustments.append(inv_res.get('data'))
                        logger.debug(f"   ✅ Inventory adjusted for variant {clean_variant_id}")
                    else:
                        inv_error = inv_res.get('error', 'Unknown inventory error')
                        inventory_errors.append({"variant_id": li["variant_id"], "error": inv_error})
                        logger.warning(f"   ⚠️  Inventory adjustment failed for variant {clean_variant_id}: {inv_error}")
                except Exception as e:
                    inventory_errors.append({"variant_id": li.get("variant_id"), "error": str(e)})
                    logger.error(f"   ❌ Exception adjusting inventory for variant {li.get('variant_id')}: {e}")
            
            logger.info(f"📊 [{order_id}] Inventory adjustments: {len(inventory_adjustments)} successful, {len(inventory_errors)} failed")

            # Optionally save order to DB when metadata present
            metadata = order_data.get('metadata', {}) if isinstance(order_data, dict) else {}
            db_user_id = metadata.get('user_id')
            db_contact_id = metadata.get('contact_id')
            logger.debug(f"💾 [{order_id}] DB metadata: user_id={db_user_id}, contact_id={db_contact_id}")
            
            if db_user_id and db_contact_id:
                try:
                    logger.info(f"💾 [{order_id}] Saving order to database...")
                    local_db.create_order_and_items(user_id=db_user_id, contact_id=db_contact_id, shopify_order_data={
                        "order": order,
                        "inventory_adjustments": {"successful": inventory_adjustments, "errors": inventory_errors},
                        "input_items": built["line_items"],
                    })
                    logger.info(f"✅ [{order_id}] Order saved to database successfully")
                except Exception as db_err:
                    logger.warning(f"⚠️  [{order_id}] DB save failed (non-fatal): {db_err}")
            else:
                logger.debug(f"⏭️  [{order_id}] Skipping DB save (no user_id/contact_id)")

            # Pricing breakdown (tool-side) using resolved unit prices
            subtotal = 0.0
            lines: List[Dict[str, Any]] = []
            for li in built["line_items"]:
                price_each = li.get("unit_price")
                if price_each is None:
                    continue
                price_each_f = float(price_each)
                qty = int(li.get("quantity") or 0)
                line_total = round(price_each_f * qty, 2)
                subtotal = round(subtotal + line_total, 2)
                lines.append({
                    "name": li.get("product_name"),
                    "quantity": qty,
                    "price_each": price_each_f,
                    "line_total": line_total,
                })
            shipping_fee = 0.0 if subtotal >= 40.0 else 3.0
            total = round(subtotal + shipping_fee, 2)

            # --- Persist order for AstroSouks tenant (user_id=6, chatbot_id=3) ---
            try:
                metadata = order_data.get('metadata', {}) if isinstance(order_data, dict) else {}
                from_number = (metadata.get('from_number') if isinstance(metadata, dict) else None) or \
                              shipping_address.get('phone') or customer_info.get('phone')
                contact_id = None
                if from_number:
                    # Create/find contact scoped to AstroSouks tenant
                    contact_id, _ = local_db.get_or_create_contact(from_number, user_id=6, name=(
                        (customer_info.get('first_name') or '') + ' ' + (customer_info.get('last_name') or '')
                    ).strip())
                if contact_id:
                    shopify_order_data = {
                        "success": True,
                        "tenant": {"user_id": 6, "chatbot_id": 3},
                        "order": {
                            "id": (order or {}).get('id'),
                            "name": (order or {}).get('name'),
                            "status": (order or {}).get('status', 'pending'),
                            "total_price": total,
                            "created_at": (order or {}).get('createdAt')
                        },
                        "customer": {
                            "first_name": customer_info.get('first_name', ''),
                            "last_name": customer_info.get('last_name', ''),
                            "phone": customer_info.get('phone', ''),
                        },
                        "line_items": [
                            {
                                "product_name": li.get('product_name'),
                                "quantity": int(li.get('quantity') or 0),
                                "price": float(li.get('unit_price') or 0.0),
                                "variant_id": li.get('variant_id'),
                            } for li in built["line_items"]
                        ],
                        "addresses": {
                            "shipping": {
                                "first_name": customer_info.get('first_name', ''),
                                "last_name": customer_info.get('last_name', ''),
                                "phone": shipping_address.get('phone') or customer_info.get('phone', ''),
                                "address1": shipping_address.get('address1'),
                                "address2": shipping_address.get('address2'),
                                "city": shipping_address.get('city'),
                                "province": shipping_address.get('province'),
                                "country": shipping_address.get('country'),
                                "zip": shipping_address.get('zip') or shipping_address.get('postal_code') or '1100',
                                "postal_code": shipping_address.get('postal_code') or shipping_address.get('zip') or '1100',
                            },
                            "billing": (billing_address or shipping_address),
                        },
                        "order_summary": {
                            "subtotal": subtotal,
                            "total": total,
                            "currency": ((order or {}).get('totalPriceSet') or {}).get('shopMoney', {}).get('currencyCode', 'USD'),
                            "item_count": sum(int(li.get('quantity') or 0) for li in built["line_items"]),
                        },
                        "inventory_adjustments": {
                            "successful": inventory_adjustments,
                            "errors": inventory_errors,
                            "summary": {
                                "total_adjustments": len(inventory_adjustments),
                                "total_errors": len(inventory_errors),
                                "all_successful": len(inventory_errors) == 0
                            }
                        },
                        "order_notes": order_notes,
                    }
                    local_db.create_order_and_items(
                        user_id=6,
                        contact_id=contact_id,
                        shopify_order_data=shopify_order_data,
                    )
            except Exception:
                # Do not fail order creation if DB save fails
                pass

            return {
                "success": True,
                "type": "order",
                "data": order,
                "inventory": {"successful": inventory_adjustments, "errors": inventory_errors},
                "pricing": {
                    "lines": lines,
                    "subtotal": subtotal,
                    "shipping_fee": shipping_fee,
                    "total": total,
                }
            }
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
    customer_first_name: str = "",
    customer_last_name: str = "",
    customer_phone: str = "",
    shipping_address_line1: str = "",
    shipping_address_line2: str = "",
    shipping_city: str = "",
    shipping_province: str = "",
    shipping_country: str = "",
    product_selections: str = "",
    billing_same_as_shipping: bool = True,
    billing_address_line1: str = "",
    billing_address_line2: str = "",
    billing_city: str = "",
    billing_province: str = "",
    billing_country: str = "",
    order_notes: str = "",
    offer_mode: str = "standard",
    *,
    config: RunnableConfig
) -> str:
    """
    Create an AstroSouks order.

    - Offer mode (select one):
        - "standard": no extra discount beyond the product's sale price
        - "10%": apply 10% off for eligible items
        - "15%": apply 15% off for eligible items
      Note: This promo applies only to select items (e.g., "Bone Conduction Speaker").
    - If a discount is applied, a discounted order is created (draft or fallback order) using REST.

    product_selections JSON example:
      '[{"product_name": "Food Vacuum Sealer", "quantity": 2, "variant_title": "10 Bags"}]'
    """
    request_id = f"REQ_{int(time.time() * 1000)}"
    logger.info(f"🎯 ASTROSOUKS ORDER REQUEST [{request_id}] at {datetime.now().isoformat()}")
    logger.info(f"📞 Customer: {customer_first_name} {customer_last_name} ({customer_phone})")
    logger.info(f"🏠 Location: {shipping_city}, {shipping_country}")
    logger.info(f"🎁 Offer mode: {offer_mode}")
    logger.debug(f"📦 Product selections raw: {product_selections}")
    
    try:
        # Validate product selections using Pydantic
        logger.debug(f"🔍 [{request_id}] Validating product selections with Pydantic...")
        try:
            validation_input = OrderValidationInput(product_selections=product_selections)
            logger.info(f"✅ [{request_id}] Product validation passed")
        except ValidationError as e:
            logger.error(f"❌ [{request_id}] Product validation failed: {e}")
            error_details = []
            for error in e.errors():
                if 'product_name' in str(error.get('loc', [])):
                    # Extract the invalid product name for a more helpful error
                    try:
                        selections_data = json.loads(product_selections)
                        invalid_products = []
                        for item in selections_data:
                            if isinstance(item, dict) and 'product_name' in item:
                                invalid_products.append(item['product_name'])
                        if invalid_products:
                            return f"❌ Error: Invalid product name(s): {', '.join(invalid_products)}. Please use exact product names from the catalog."
                    except:
                        pass
                error_details.append(str(error.get('msg', error)))
            return f"❌ Error: Invalid product selection: {'; '.join(error_details)}"
        
        # Validate required fields
        required = {
            'shipping_address_line1': shipping_address_line1,
            'shipping_city': shipping_city,
            'shipping_province': shipping_province,
            'shipping_country': shipping_country,
            # postal code is defaulted; no longer required from input
        }
        missing = [k for k, v in required.items() if not v or str(v).strip() == ""]
        if missing and offer_mode.strip().lower() == "standard":
            return f"❌ Error: Missing required fields: {', '.join(missing)}"

        logger.debug(f"🔍 [{request_id}] Parsing product selections JSON...")
        selections = _parse_product_selections_json(product_selections)
        if not selections:
            logger.error(f"❌ [{request_id}] Failed to parse product selections JSON")
            return "❌ Error: Invalid or empty product_selections JSON."

        logger.info(f"📦 [{request_id}] Parsed {len(selections)} product selections")

        logger.info(f"🔧 [{request_id}] Creating AstroSouksOrderManager...")
        manager_start = time.time()
        om = AstroSouksOrderManager()
        manager_duration = time.time() - manager_start
        logger.info(f"✅ [{request_id}] OrderManager created in {manager_duration:.3f}s")
        
        # Map offer_mode to explicit discount_percent and disable auto volume tiers
        omode = (offer_mode or "standard").strip().lower()
        logger.debug(f"🎁 [{request_id}] Processing offer mode: '{offer_mode}' -> '{omode}'")
        if omode not in ("standard", "none", "10%", "15%"):
            logger.error(f"❌ [{request_id}] Invalid offer mode: {omode}")
            return "❌ Error: offer_mode must be one of: standard/none, 10%, 15%."
        mapped_discount = 0.0
        if omode in ("10%",):
            mapped_discount = 10.0
        elif omode in ("15%",):
            mapped_discount = 15.0
        logger.info(f"💰 [{request_id}] Mapped discount: {mapped_discount}%")

        order_data = {
            'customer_info': {
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
                'zip': "1100",
                'postal_code': "1100",
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
                'zip': "1100",
                'postal_code': "1100",
                'first_name': customer_first_name.strip(),
                'last_name': customer_last_name.strip(),
                'phone': customer_phone.strip(),
            } if not billing_same_as_shipping else None,
            'order_notes': order_notes.strip(),
            'forced_discount_percent': mapped_discount,
            'enable_auto_volume': False,
            'metadata': config.get('metadata', {}) if hasattr(config, 'get') else {},
        }

        logger.info(f"🚀 [{request_id}] Calling om.create_order with assembled data...")
        logger.debug(f"📋 [{request_id}] Order data summary:")
        logger.debug(f"   Customer: {order_data['customer_info']}")
        logger.debug(f"   Line items count: {len(order_data['line_items'])}")
        logger.debug(f"   Discount: {order_data['forced_discount_percent']}%")
        logger.debug(f"   Auto volume: {order_data['enable_auto_volume']}")
        
        create_start = time.time()
        result = om.create_order(order_data)
        create_duration = time.time() - create_start
        logger.info(f"⏱️  [{request_id}] Order creation completed in {create_duration:.3f}s")
        
        if not result.get('success'):
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"❌ [{request_id}] ORDER CREATION FAILED: {error_msg}")
            total_duration = time.time() - (create_start - create_duration)
            logger.error(f"🕒 [{request_id}] Total request duration: {total_duration:.3f}s")
            return f"❌ Error creating AstroSouks order: {error_msg}"
        
        logger.info(f"✅ [{request_id}] ORDER CREATION SUCCESSFUL!")
        total_duration = time.time() - (create_start - create_duration)  
        logger.info(f"🕒 [{request_id}] Total request duration: {total_duration:.3f}s")

        if result.get('type') == 'draft_order':
            draft = result.get('data', {})
            pricing = result.get('pricing', {}) or {}
            lines = pricing.get('lines', []) or []
            subtotal = pricing.get('subtotal')
            shipping_fee = pricing.get('shipping_fee')
            total = pricing.get('total')

            summary_lines = [
                "✅ AstroSouks DISCOUNTED DRAFT ORDER CREATED\n",
                f"• Draft Order ID: {draft.get('id')}",
                f"• Status: {draft.get('status')}",
                "📦 Items:",
            ]
            for ln in lines:
                summary_lines.append(
                    f"  - {ln.get('name')} × {ln.get('quantity')} @ ${ln.get('price_each'):.2f} = ${ln.get('line_total'):.2f}"
                )
            if subtotal is not None and shipping_fee is not None and total is not None:
                summary_lines.extend([
                    "",
                    f"Subtotal: ${subtotal:.2f}",
                    f"Shipping: ${shipping_fee:.2f}",
                    f"Total: ${total:.2f}",
                ])
            summary_lines.append("\n• Next: Complete the draft order in Shopify to finalize the sale.")
            return "\n".join(summary_lines)

        # Else real order
        order = result.get('data', {})
        pricing = result.get('pricing', {}) or {}
        lines = pricing.get('lines', []) or []
        subtotal = pricing.get('subtotal')
        shipping_fee = pricing.get('shipping_fee')
        total = pricing.get('total')

        summary_lines = [
            "✅ AstroSouks ORDER CREATED SUCCESSFULLY!\n",
            f"• Order Number: {order.get('name')}",
            f"• Order ID: {order.get('id')}",
            f"• Status: {order.get('status', 'pending')}\n",
            "📦 Items:",
        ]
        for ln in lines:
            summary_lines.append(
                f"  - {ln.get('name')} × {ln.get('quantity')} @ ${ln.get('price_each'):.2f} = ${ln.get('line_total'):.2f}"
            )
        if subtotal is not None and shipping_fee is not None and total is not None:
            summary_lines.extend([
                "",
                f"Subtotal: ${subtotal:.2f}",
                f"Shipping: ${shipping_fee:.2f}",
                f"Total: ${total:.2f}",
            ])
        return "\n".join(summary_lines)

    except Exception as e:
        logger.error(f"💥 [{request_id}] UNEXPECTED ERROR in create_astrosouks_order: {type(e).__name__}: {str(e)}")
        logger.error(f"🔍 [{request_id}] Exception details:", exc_info=True)
        logger.error(f"📋 [{request_id}] Request context:")
        logger.error(f"   Customer: {customer_first_name} {customer_last_name}")
        logger.error(f"   Phone: {customer_phone}")
        logger.error(f"   Offer mode: {offer_mode}")
        logger.error(f"   Product selections: {product_selections}")
        return f"❌ Error creating AstroSouks order: {str(e)}"

