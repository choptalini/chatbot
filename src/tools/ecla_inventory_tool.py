#!/usr/bin/env python3
"""
ECLA Inventory Tool for the ECLA AI Customer Support Agent
Gets live inventory quantities and product images for ECLA products using predefined variant IDs from Shopify
"""

import os
import sys
import json
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from langchain.tools import tool

# Add the shopify_method directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shopify_method'))

from shopify_method import ShopifyClient

class ECLAInventoryManager:
    """
    ECLA Inventory Manager for live inventory checking with image support
    Uses predefined variant IDs and product IDs from the Shopify store
    """
    
    def __init__(self):
        """Initialize the inventory manager with Shopify client"""
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
        
        # Cache for live products (optional; refreshed per request paths)
        self._live_products_cache = None

    def _fetch_live_products(self) -> Dict[str, Any]:
        """Fetch live products (first page up to 50) from Shopify."""
        try:
            products_result = self.client.get_products(limit=50)
            return products_result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _normalize_product_entry(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Create a simplified view of a product with totals from variants."""
        variants = product.get('variants', [])
        # Compute total available from variant inventoryQuantity if present
        total_available = 0
        for v in variants:
            try:
                qty = int(float(v.get('inventoryQuantity', 0)))
            except Exception:
                qty = 0
            total_available += qty
        # Prefer first variant price as a reference (if available)
        ref_price = None
        if variants:
            ref_price = variants[0].get('price')
        return {
            "product_id": product.get('id'),
            "product_name": product.get('title'),
            "handle": product.get('handle'),
            "variants": variants,
            "total_available": total_available,
            "ref_price": ref_price,
        }
    
    def get_product_inventory(self, product_key: str) -> Dict[str, Any]:
        """
        Get live inventory and product images for a specific ECLA product
        
        Args:
            product_key: Key for the product (purple_corrector, whitening_pen, e20_bionic_kit)
            
        Returns:
            Dictionary with inventory and image information
        """
        # Fetch live products and find a match by name/handle
        products_result = self._fetch_live_products()
        if not products_result.get('success'):
            return {"success": False, "error": f"Failed to get products: {products_result.get('error')}"}

        products = products_result.get('data', {}).get('products') or products_result.get('data', {}).get('products', [])
        # The client returns {success, data: {products, count, has_next_page, ...}}
        live_products = products_result.get('data', {}).get('products', []) if isinstance(products_result.get('data', {}), dict) else []
        if not live_products:
            # Some client versions return flat list in 'products'
            live_products = products if isinstance(products, list) else []

        # Find by case-insensitive partial match on title or handle
        target = None
        name_lower = product_key.lower()
        for p in live_products:
            title = (p.get('title') or '').lower()
            handle = (p.get('handle') or '').lower()
            if name_lower in title or name_lower in handle:
                target = p
                break

        if not target:
            available = ", ".join([(p.get('title') or p.get('handle') or 'Unknown') for p in live_products])
            return {"success": False, "error": f"Product '{product_key}' not found among live products: {available}"}

        simplified = self._normalize_product_entry(target)

        # Enrich with product details for images/description
        images_info = []
        product_description = ''
        product_handle = target.get('handle')
        try:
            details = self.client.get_product(product_id=target.get('id'))
            if details.get('success'):
                pdata = details.get('data', {})
                product_description = pdata.get('description', '')
                product_handle = pdata.get('handle', product_handle)
                for image in pdata.get('images', []) or []:
                    images_info.append({
                        "id": image.get('id'),
                        "url": image.get('src'),
                        "alt_text": image.get('altText', ''),
                    })
        except Exception:
            pass

        return {
            "success": True,
            "product_name": simplified["product_name"],
            "product_id": simplified["product_id"],
            "price": simplified["ref_price"],
            "variant_id": None,
            "total_available": simplified["total_available"],
            "locations": [],  # Not computed in bulk mode
            "images": images_info,
            "product_description": product_description,
            "product_handle": product_handle,
            "timestamp": products_result.get('timestamp'),
        }
    
    def get_all_inventory(self) -> Dict[str, Any]:
        """
        Fetch all products live from Shopify and return their full details
        (variants, images, options, tags, etc.).
        """
        try:
            products_result = self.client.get_products_full(limit=50)
            if not products_result.get('success'):
                return {"success": False, "error": f"Failed to get products: {products_result.get('error')}"}
            return {"success": True, "products": products_result.get('data', {}).get('products', []), "count": products_result.get('data', {}).get('count', 0)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def find_product_by_name(self, product_name: str) -> Optional[str]:
        """
        Find product key by name (case-insensitive, flexible matching)
        
        Args:
            product_name: Name to search for
            
        Returns:
            Product key if found, None otherwise
        """
        # Search live products by partial name or handle
        product_name_lower = product_name.lower()
        products_result = self._fetch_live_products()
        if not products_result.get('success'):
            return None
        live_products = products_result.get('data', {}).get('products', [])
        if not isinstance(live_products, list):
            live_products = []
        for p in live_products:
            title = (p.get('title') or '').lower()
            handle = (p.get('handle') or '').lower()
            if product_name_lower in title or product_name_lower in handle:
                # Return the title as key for get_product_inventory lookup
                return p.get('title') or p.get('handle')
        return None

# Initialize the inventory manager (singleton pattern)
_inventory_manager = None

def get_inventory_manager():
    """Get the global inventory manager instance"""
    global _inventory_manager
    if _inventory_manager is None:
        _inventory_manager = ECLAInventoryManager()
    return _inventory_manager

@tool
def check_ecla_inventory(product_name: str = "all") -> str:
    """
    Check live inventory quantities for ECLA products.
    This tool provides stock levels and prices, but it DOES NOT return images.
    To send an image, you must use the 'send_product_image' tool.
    
    Args:
        product_name: Product name to check. Can be:
            - "all" (default): Check all products
            - "purple corrector" or "purple": Check Purple Corrector
            - "whitening pen" or "pen": Check Whitening Pen  
            - "e20" or "bionic" or "kit": Check e20 Bionic Kit
            - Or any partial product name
    
    Returns:
        A formatted string with live inventory information (stock, price) for the requested product(s). It does not contain image URLs.
    """
    try:
        inventory_manager = get_inventory_manager()
        
        if product_name.lower() == "all":
            # Return raw product list as JSON string (full details)
            all_products = inventory_manager.get_all_inventory()
            if not all_products.get('success'):
                return f"{{\"success\": false, \"error\": \"{all_products.get('error')}\"}}"
            return json.dumps({"success": True, "count": all_products.get('count', 0), "products": all_products.get('products', [])}, ensure_ascii=False)
        
        else:
            # Find specific product
            product_key = inventory_manager.find_product_by_name(product_name)
            
            if not product_key:
                return f"❌ Product '{product_name}' not found. Available products: Purple Corrector, Whitening Pen, e20 Bionic Kit"
            
            # Return a single product's full details as JSON
            inventory = inventory_manager.get_product_inventory(product_key)
            if not inventory.get('success'):
                return json.dumps({"success": False, "error": inventory.get('error')}, ensure_ascii=False)
            # Enrich with full product details
            try:
                details = inventory_manager.client.get_product(product_id=inventory.get('product_id'))
                if details.get('success'):
                    return json.dumps({"success": True, "product": details.get('data')}, ensure_ascii=False)
            except Exception:
                pass
            # Fallback to simplified if details call fails
            return json.dumps({"success": True, "product": inventory}, ensure_ascii=False)
            
    except Exception as e:
        return f"❌ Error checking inventory: {str(e)}" 