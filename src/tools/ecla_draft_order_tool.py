#!/usr/bin/env python3
"""
ECLA Order Tool for the ECLA AI Customer Support Agent
Creates comprehensive real orders with all necessary customer, product, and shipping information
"""

import os
import sys
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig

# Add the shopify_method directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shopify_method'))

from shopify_method import ShopifyClient
from src.multi_tenant_database import db as local_db


class ECLAOrderManager:
    """
    ECLA Order Manager for creating comprehensive real orders
    Uses the Shopify API to create complete orders with all necessary information
    """
    
    def __init__(self):
        """Initialize the order manager with Shopify client"""
        load_dotenv()
        
        self.shop_domain = os.getenv('SHOPIFY_SHOP_DOMAIN')
        self.access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not self.shop_domain or not self.access_token:
            raise ValueError("Missing Shopify credentials in environment variables")
        
        # Initialize Shopify client
        self.client = ShopifyClient(
            shop_domain=self.shop_domain,
            access_token=self.access_token
        )
        
        # Predefined ECLA products with their variant IDs
        self.ecla_products = {
            "purple_corrector": {
                "name": "ECLA® Purple Corrector",
                "variant_id": "gid://shopify/ProductVariant/45009045881028",
                "price": 26.00,
                "handle": "ecla-purple-corrector"
            },
            "whitening_pen": {
                "name": "ECLA® Teeth Whitening Pen",
                "variant_id": "gid://shopify/ProductVariant/45009060724932",
                "price": 20.00,
                "handle": "ecla-teeth-whitening-pen"
            },
            "e20_bionic_kit": {
                "name": "ECLA® e20 Bionic⁺ Kit",
                "variant_id": "gid://shopify/ProductVariant/45009099423940",
                "price": 55.00,
                "handle": "ecla-e20-bionic-kit"
            }
        }
    
    def _build_items_from_input(self, line_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Map input line items to a normalized structure with product name and pricing."""
        normalized: List[Dict[str, Any]] = []
        for item in line_items:
            qty = int(item.get('quantity', 1))
            if 'product_key' in item:
                key = item['product_key']
                product = self.ecla_products.get(key)
                if not product:
                    raise ValueError(f"Unknown product: {key}. Available: {list(self.ecla_products.keys())}")
                price = float(product['price'])
                normalized.append({
                    'product_name': product['name'],
                    'quantity': qty,
                    'price': price,
                    'total': price * qty,
                    'variant_id': product['variant_id'],
                    'source': 'input_product_key'
                })
            elif 'variant_id' in item:
                # Custom variant; price may be provided optionally
                price = float(item.get('price', 0))
                normalized.append({
                    'product_name': item.get('product_name', 'Custom Product'),
                    'quantity': qty,
                    'price': price,
                    'total': price * qty,
                    'variant_id': item['variant_id'],
                    'source': 'input_variant_id'
                })
            else:
                raise ValueError("Each line item must have either 'product_key' or 'variant_id'")
        return normalized

    def create_comprehensive_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a comprehensive real order with all necessary details
        
        Args:
            order_data: Dictionary containing all order information
            
        Returns:
            Dictionary with order creation result
        """
        try:
            # Extract and validate required data
            customer_info = order_data.get('customer_info', {})
            line_items = order_data.get('line_items', [])
            shipping_address = order_data.get('shipping_address', {})
            billing_address = order_data.get('billing_address', {})
            order_notes = order_data.get('order_notes', '')
            
            # Validate required fields
            if not customer_info.get('email'):
                return {
                    "success": False,
                    "error": "Customer email is required"
                }
            
            if not line_items:
                return {
                    "success": False,
                    "error": "At least one line item is required"
                }
            
            if not shipping_address:
                return {
                    "success": False,
                    "error": "Shipping address is required"
                }
            
            # Normalize items from input to ensure we can save to DB even if Shopify response is sparse
            normalized_input_items = self._build_items_from_input(line_items)

            # Format line items for Shopify API
            formatted_line_items = []
            for item in normalized_input_items:
                formatted_line_items.append({
                    'variantId': item['variant_id'],
                    'quantity': item['quantity']
                })
            
            # Create real order using the Shopify client
            order_result = self.client.create_order(
                line_items=formatted_line_items,
                customer_info=customer_info,
                shipping_address=shipping_address,
                billing_address=billing_address,
                send_receipt=order_data.get('send_confirmation', True),
                send_fulfillment_receipt=False
            )
            
            if not order_result['success']:
                return {
                    "success": False,
                    "error": f"Failed to create order: {order_result['error']}"
                }
            
            order = order_result['data']
            
            # STEP 3: Adjust inventory after successful order creation
            inventory_adjustments = []
            inventory_errors = []
            
            self.client.logger.info(f"Adjusting inventory for order {order['name']}")
            
            for item in normalized_input_items:
                try:
                    variant_id = item['variant_id']
                    product_name = item['product_name']
                    quantity = item['quantity']
                    
                    # Remove "gid://shopify/ProductVariant/" prefix if present
                    clean_variant_id = variant_id.replace('gid://shopify/ProductVariant/', '')
                    
                    # Adjust inventory (decrease by ordered quantity)
                    inventory_result = self.client.adjust_inventory(
                        variant_id=clean_variant_id,
                        quantity_change=-quantity,
                        reason="correction"
                    )
                    
                    if inventory_result['success']:
                        adj_data = inventory_result['data']
                        inventory_adjustments.append({
                            "variant_id": variant_id,
                            "product_name": product_name,
                            "quantity_decreased": quantity,
                            "previous_quantity": adj_data['previous_quantity'],
                            "new_quantity": adj_data['quantity_after_change'],
                            "location_name": adj_data['location_name']
                        })
                        self.client.logger.info(f"Inventory adjusted for {product_name}: {adj_data['previous_quantity']} → {adj_data['quantity_after_change']}")
                    else:
                        inventory_errors.append({
                            "variant_id": variant_id,
                            "product_name": product_name,
                            "quantity": quantity,
                            "error": inventory_result['error']
                        })
                        self.client.logger.warning(f"Failed to adjust inventory for {product_name}: {inventory_result['error']}")
                        
                except Exception as e:
                    inventory_errors.append({
                        "variant_id": item.get('variant_id', "unknown"),
                        "product_name": item.get('product_name', "unknown"),
                        "quantity": item.get('quantity', 1),
                        "error": str(e)
                    })
                    self.client.logger.error(f"Error adjusting inventory for item: {str(e)}")
            
            # Calculate totals from input as authoritative fallback
            subtotal_amount = sum(i['price'] * i['quantity'] for i in normalized_input_items)
            # Prefer MoneyBag total from response if available
            total_amount = subtotal_amount
            try:
                price_set = order.get('totalPriceSet', {})
                shop_money = price_set.get('shopMoney', {}) if isinstance(price_set, dict) else {}
                amt = shop_money.get('amount')
                if amt is not None:
                    total_amount = float(amt)
            except Exception:
                total_amount = subtotal_amount
            currency = "USD"
            
            # Build enriched shipping address with aliases for frontend compatibility
            shipping = {
                'first_name': shipping_address.get('first_name', customer_info.get('first_name', '')),
                'last_name': shipping_address.get('last_name', customer_info.get('last_name', '')),
                'phone': shipping_address.get('phone', customer_info.get('phone', '')),
                'address1': shipping_address.get('address1'),
                'address2': shipping_address.get('address2'),
                'city': shipping_address.get('city'),
                'province': shipping_address.get('province'),
                'state': shipping_address.get('state') or shipping_address.get('province'),  # alias
                'country': shipping_address.get('country'),
                'zip': shipping_address.get('zip') or shipping_address.get('postal_code'),
                'postal_code': shipping_address.get('postal_code') or shipping_address.get('zip'),  # alias
            }
            billing = billing_address or shipping
            
            # Format comprehensive response to persist
            response = {
                "success": True,
                "order": {
                    "id": order.get('id'),
                    "name": order.get('name'),
                    "status": order.get('status', 'pending'),
                    "total_price": total_amount,
                    "created_at": order.get('createdAt')
                },
                "customer": {
                    "email": customer_info.get('email'),
                    "first_name": customer_info.get('first_name', ''),
                    "last_name": customer_info.get('last_name', ''),
                    "phone": customer_info.get('phone', ''),
                },
                # Prefer Shopify line items if available; otherwise, use input-derived normalized items
                "line_items": [],
                "addresses": {
                    "shipping": shipping,
                    "billing": billing,
                },
                "order_summary": {
                    "subtotal": subtotal_amount,
                    "total": total_amount,
                    "currency": currency,
                    "item_count": sum(i['quantity'] for i in normalized_input_items),
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
                "next_steps": [
                    "Order has been created successfully",
                    f"Order number: {order.get('name')}",
                    "Customer will receive order confirmation email",
                    "Order is ready for fulfillment",
                    "Payment processing will proceed automatically"
                ],
                "order_notes": order_notes,
            }
            
            # Populate response line_items with Shopify details if present; otherwise fallback to input
            order_line_items = order.get('lineItems')
            # Parse connection (edges -> node)
            if isinstance(order_line_items, dict) and 'edges' in order_line_items:
                for edge in order_line_items.get('edges', []):
                    node = (edge or {}).get('node', {})
                    if isinstance(node, dict):
                        price = 0.0
                        try:
                            oups = node.get('originalUnitPriceSet', {})
                            sm = oups.get('shopMoney', {}) if isinstance(oups, dict) else {}
                            if sm.get('amount') is not None:
                                price = float(sm.get('amount'))
                        except Exception:
                            price = 0.0
                        response["line_items"].append({
                            "product_name": node.get('title', 'Unknown Product'),
                            "quantity": node.get('quantity', 1),
                            "price": price,
                            "variant_id": (node.get('variant') or {}).get('id', ''),
                        })
            else:
                # Fallback to normalized input items
                for it in normalized_input_items:
                    response["line_items"].append({
                        "product_name": it['product_name'],
                        "quantity": it['quantity'],
                        "price": it['price'],
                        "variant_id": it['variant_id'],
                    })
            
            # --- Save order and items to Supabase database ---
            try:
                metadata = order_data.get('metadata', {})  # allow passing metadata directly too
            except Exception:
                metadata = {}
            
            db_user_id = metadata.get('user_id')
            db_contact_id = metadata.get('contact_id')
            
            # Backward compatibility: also check RunnableConfig metadata if available
            if not db_user_id or not db_contact_id:
                try:
                    # When called via tool(), order_data may not include metadata, but RunnableConfig might
                    pass
                except Exception:
                    pass
            
            if db_user_id and db_contact_id:
                db_order_id = local_db.create_order_and_items(
                    user_id=db_user_id,
                    contact_id=db_contact_id,
                    shopify_order_data=response
                )
                if db_order_id:
                    self.client.logger.info(f"✅ Successfully saved Shopify order to Supabase with ID: {db_order_id}")
                else:
                    self.client.logger.warning(f"⚠️ Failed to save Shopify order to Supabase for contact {db_contact_id}")
            else:
                self.client.logger.warning("⚠️ Missing user_id or contact_id in metadata, cannot save order to DB.")

            return response
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating order: {str(e)}"
            }
    
    def get_available_products(self) -> Dict[str, Any]:
        """
        Get list of available ECLA products
        
        Returns:
            Dictionary with available products
        """
        return {
            "success": True,
            "products": [
                {
                    "key": key,
                    "name": product["name"],
                    "price": product["price"],
                    "handle": product["handle"]
                }
                for key, product in self.ecla_products.items()
            ]
        }

# Initialize the order manager (singleton pattern)
_order_manager = None

def get_order_manager():
    """Get the global order manager instance"""
    global _order_manager
    if _order_manager is None:
        _order_manager = ECLAOrderManager()
    return _order_manager

@tool
def create_ecla_order(
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
    send_confirmation: bool = True,
    *,
    config: RunnableConfig
) -> str:
    """
    Create a comprehensive ECLA real order with all necessary customer and shipping information.
    
    This tool requires ALL the following information to create a complete order:
    
    CUSTOMER INFORMATION (Required):
    - customer_email: Customer's email address
    - customer_first_name: Customer's first name
    - customer_last_name: Customer's last name
    - customer_phone: Customer's phone number
    
    SHIPPING ADDRESS (Required):
    - shipping_address_line1: Street address line 1
    - shipping_address_line2: Street address line 2 (optional)
    - shipping_city: City
    - shipping_province: Province/State
    - shipping_country: Country
    - shipping_postal_code: Postal/ZIP code
    
    PRODUCT SELECTIONS (Required):
    - product_selections: JSON string with product selections, format:
      '[{"product_key": "purple_corrector", "quantity": 1}, {"product_key": "whitening_pen", "quantity": 2}]'
      Available product keys: purple_corrector, whitening_pen, e20_bionic_kit
    
    BILLING ADDRESS (Optional):
    - billing_same_as_shipping: Whether billing address is same as shipping (default: True)
    - billing_address_line1: Billing street address line 1 (if different from shipping)
    - billing_address_line2: Billing street address line 2 (if different from shipping)
    - billing_city: Billing city (if different from shipping)
    - billing_province: Billing province/state (if different from shipping)
    - billing_country: Billing country (if different from shipping)
    - billing_postal_code: Billing postal/ZIP code (if different from shipping)
    
    ADDITIONAL OPTIONS (Optional):
    - order_notes: Special instructions or notes for the order
    - send_confirmation: Whether to send confirmation email to customer (default: True)
    
    Returns:
        Comprehensive order creation result with order details and next steps
    """
    try:
        import json
        
        # Parse product selections
        try:
            line_items = json.loads(product_selections)
        except json.JSONDecodeError:
            return "❌ Error: Invalid product_selections format. Please provide a valid JSON string like: '[{\"product_key\": \"purple_corrector\", \"quantity\": 1}]'"
        
        # Validate required fields
        required_fields = {
            'customer_email': customer_email,
            'customer_first_name': customer_first_name,
            'customer_last_name': customer_last_name,
            'customer_phone': customer_phone,
            'shipping_address_line1': shipping_address_line1,
            'shipping_city': shipping_city,
            'shipping_province': shipping_province,
            'shipping_country': shipping_country,
            'shipping_postal_code': shipping_postal_code,
        }
        
        missing_fields = [field for field, value in required_fields.items() if not value or value.strip() == ""]
        
        if missing_fields:
            return f"❌ Error: Missing required information: {', '.join(missing_fields)}. Please provide all required customer and shipping details to create the order."
        
        # Prepare order data
        order_data = {
            'customer_info': {
                'email': customer_email.strip(),
                'first_name': customer_first_name.strip(),
                'last_name': customer_last_name.strip(),
                'phone': customer_phone.strip(),
            },
            'line_items': line_items,
            'shipping_address': {
                'address1': shipping_address_line1.strip(),
                'address2': shipping_address_line2.strip(),
                'city': shipping_city.strip(),
                'province': shipping_province.strip(),
                'country': shipping_country.strip(),
                'zip': shipping_postal_code.strip(),
                'postal_code': shipping_postal_code.strip(),  # alias for frontend
                'first_name': customer_first_name.strip(),
                'last_name': customer_last_name.strip(),
                'phone': customer_phone.strip(),
            },
            'order_notes': order_notes.strip(),
            'send_confirmation': send_confirmation,
            # Propagate metadata for DB save when called programmatically
            'metadata': config.get('metadata', {}) if hasattr(config, 'get') else {},
        }
        
        # Handle billing address
        if billing_same_as_shipping:
            order_data['billing_address'] = order_data['shipping_address'].copy()
        else:
            # Validate billing address fields if different from shipping
            if billing_address_line1 and billing_city and billing_province and billing_country and billing_postal_code:
                order_data['billing_address'] = {
                    'address1': billing_address_line1.strip(),
                    'address2': billing_address_line2.strip(),
                    'city': billing_city.strip(),
                    'province': billing_province.strip(),
                    'country': billing_country.strip(),
                    'zip': billing_postal_code.strip(),
                    'postal_code': billing_postal_code.strip(),
                    'first_name': customer_first_name.strip(),
                    'last_name': customer_last_name.strip(),
                    'phone': customer_phone.strip(),
                }
            else:
                return "❌ Error: When billing address is different from shipping, all billing address fields are required: billing_address_line1, billing_city, billing_province, billing_country, billing_postal_code"
        
        # Create order
        order_manager = get_order_manager()
        result = order_manager.create_comprehensive_order(order_data)
        
        if not result['success']:
            return f"❌ Error creating order: {result['error']}"

        # Format success response
        order = result['order']
        customer = result['customer']
        line_items = result['line_items']
        addresses = result['addresses']
        order_summary = result['order_summary']
        inventory_adjustments = result['inventory_adjustments']
        next_steps = result['next_steps']
        
        response = f"""✅ ECLA ORDER CREATED SUCCESSFULLY!

🧾 ORDER DETAILS:
• Order Number: {order['name']}
• Order ID: {order['id']}
• Status: {order['status']}
• Total Amount: ${order['total_price']}
• Created: {order['created_at']}

👤 CUSTOMER INFORMATION:
• Name: {customer['first_name']} {customer['last_name']}
• Email: {customer['email']}
• Phone: {customer['phone']}

📦 PRODUCTS ORDERED:
"""
        
        for item in line_items:
            response += f"• {item['product_name']}: {item['quantity']} × ${item['price']:.2f}\n"
        
        response += f"""
📍 SHIPPING ADDRESS:
• {addresses['shipping'].get('address1','')}
• {addresses['shipping'].get('address2','')}
• {addresses['shipping'].get('city','')}, {addresses['shipping'].get('province','') or addresses['shipping'].get('state','')} {addresses['shipping'].get('zip','') or addresses['shipping'].get('postal_code','')}
• {addresses['shipping'].get('country','')}

💰 ORDER SUMMARY:
• Subtotal: ${order_summary['subtotal']:.2f}
• Total Items: {order_summary['item_count']}
• Final Total: ${order_summary['total']}
• Currency: {order_summary['currency']}

📦 INVENTORY ADJUSTMENTS:
"""
        
        # Add inventory adjustment details
        if inventory_adjustments['summary']['total_adjustments'] > 0:
            response += "✅ Inventory successfully decreased for:\n"
            for adj in inventory_adjustments['successful']:
                response += f"• {adj['product_name']}: {adj['previous_quantity']} → {adj['new_quantity']} (-{adj['quantity_decreased']} units)\n"
        
        if inventory_adjustments['summary']['total_errors'] > 0:
            response += "\n⚠️ Inventory adjustment issues:\n"
            for error in inventory_adjustments['errors']:
                response += f"• {error['product_name']}: Failed to adjust inventory ({error['error']})\n"
        
        if inventory_adjustments['summary']['all_successful']:
            response += "\n🎉 All inventory levels updated successfully!"
        
        response += f"""

🔄 NEXT STEPS:
"""
        
        for step in next_steps:
            response += f"• {step}\n"
        
        return response
        
    except Exception as e:
        return f"❌ Error creating order: {str(e)}" 