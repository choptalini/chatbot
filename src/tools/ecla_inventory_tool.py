#!/usr/bin/env python3
"""
ECLA Inventory Tool for the ECLA AI Customer Support Agent
Gets live inventory quantities and product images for ECLA products using predefined variant IDs from Shopify
"""

import os
import sys
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
        
        # Predefined ECLA products with their variant IDs and product IDs
        self.ecla_products = {
            "purple_corrector": {
                "name": "ECLA® Purple Corrector",
                "product_id": "gid://shopify/Product/8311492116676",
                "variant_id": "gid://shopify/ProductVariant/45009045881028",
                "price": "$26.00",
                "handle": "ecla-purple-corrector"
            },
            "whitening_pen": {
                "name": "ECLA® Teeth Whitening Pen",
                "product_id": "gid://shopify/Product/8311493394628",
                "variant_id": "gid://shopify/ProductVariant/45009060724932",
                "price": "$20.00",
                "handle": "ecla-teeth-whitening-pen"
            },
            "e20_bionic_kit": {
                "name": "ECLA® e20 Bionic⁺ Kit",
                "product_id": "gid://shopify/Product/8311497916612",
                "variant_id": "gid://shopify/ProductVariant/45009099423940",
                "price": "$55.00",
                "handle": "ecla-e20-bionic-kit"
            }
        }
    
    def get_product_inventory(self, product_key: str) -> Dict[str, Any]:
        """
        Get live inventory and product images for a specific ECLA product
        
        Args:
            product_key: Key for the product (purple_corrector, whitening_pen, e20_bionic_kit)
            
        Returns:
            Dictionary with inventory and image information
        """
        if product_key not in self.ecla_products:
            return {
                "success": False,
                "error": f"Product '{product_key}' not found. Available: {list(self.ecla_products.keys())}"
            }
        
        product_info = self.ecla_products[product_key]
        
        try:
            # Get live inventory from Shopify
            inventory_result = self.client.get_inventory(variant_id=product_info["variant_id"])
            
            if not inventory_result['success']:
                return {
                    "success": False,
                    "error": f"Failed to get inventory: {inventory_result['error']}"
                }
            
            inventory_data = inventory_result['data']
            
            # Get product details including images
            product_result = self.client.get_product(product_id=product_info["product_id"])
            
            if not product_result['success']:
                return {
                    "success": False,
                    "error": f"Failed to get product details: {product_result['error']}"
                }
            
            product_data = product_result['data']
            
            # Calculate total available inventory
            total_available = sum(loc['available'] for loc in inventory_data['locations'])
            
            # Extract image information
            images = product_data.get('images', [])
            image_info = []
            
            for image in images:
                image_info.append({
                    "id": image.get('id'),
                    "url": image.get('src'),
                    "alt_text": image.get('altText', ''),
                })
            
            return {
                "success": True,
                "product_name": product_info["name"],
                "product_id": product_info["product_id"],
                "price": product_info["price"],
                "variant_id": product_info["variant_id"],
                "total_available": total_available,
                "locations": inventory_data['locations'],
                "images": image_info,
                "product_description": product_data.get('description', ''),
                "product_handle": product_data.get('handle', ''),
                "timestamp": inventory_result['timestamp']
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error checking inventory: {str(e)}"
            }
    
    def get_all_inventory(self) -> Dict[str, Any]:
        """
        Get live inventory and images for all ECLA products
        
        Returns:
            Dictionary with all products' inventory and image information
        """
        all_inventory = {}
        
        for product_key in self.ecla_products:
            inventory = self.get_product_inventory(product_key)
            all_inventory[product_key] = inventory
        
        return all_inventory
    
    def find_product_by_name(self, product_name: str) -> Optional[str]:
        """
        Find product key by name (case-insensitive, flexible matching)
        
        Args:
            product_name: Name to search for
            
        Returns:
            Product key if found, None otherwise
        """
        product_name_lower = product_name.lower()
        
        # Direct name matching
        for key, product in self.ecla_products.items():
            if product_name_lower in product["name"].lower():
                return key
        
        # Keyword matching
        if "purple" in product_name_lower or "corrector" in product_name_lower:
            return "purple_corrector"
        elif "pen" in product_name_lower or "whitening pen" in product_name_lower:
            return "whitening_pen"
        elif "e20" in product_name_lower or "bionic" in product_name_lower or "kit" in product_name_lower:
            return "e20_bionic_kit"
        
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
            # Get all products inventory
            all_inventory = inventory_manager.get_all_inventory()
            
            result = "🦷 ECLA PRODUCTS INVENTORY (Live)\n"
            result += "=" * 50 + "\n"
            
            total_items = 0
            for product_key, inventory in all_inventory.items():
                if inventory['success']:
                    result += f"📦 {inventory['product_name']}\n"
                    result += f"   💰 Price: {inventory['price']}\n"
                    result += f"   📊 Available: {inventory['total_available']} units\n"
                    # Safe access to location name
                    location_name = inventory.get('locations', [{}])[0].get('location_name', 'N/A')
                    result += f"   📍 Location: {location_name}\n\n"
                    
                    # NOTE: Image information is intentionally omitted from the response
                    # to encourage the agent to use the dedicated image sending tool.
                    
                    total_items += inventory['total_available']
                else:
                    result += f"❌ {inventory_manager.ecla_products[product_key]['name']}: {inventory['error']}\n\n"
            
            result += f"📊 TOTAL INVENTORY: {total_items} units across all products"
            return result
        
        else:
            # Find specific product
            product_key = inventory_manager.find_product_by_name(product_name)
            
            if not product_key:
                return f"❌ Product '{product_name}' not found. Available products: Purple Corrector, Whitening Pen, e20 Bionic Kit"
            
            inventory = inventory_manager.get_product_inventory(product_key)
            
            if not inventory['success']:
                return f"❌ Error checking inventory for '{product_name}': {inventory['error']}"
            
            result = f"🦷 {inventory['product_name']} - Live Inventory\n"
            result += "=" * 50 + "\n"
            result += f"💰 Price: {inventory['price']}\n"
            result += f"📊 Available: {inventory['total_available']} units\n"
            # Safe access to location name
            location_name = inventory.get('locations', [{}])[0].get('location_name', 'N/A')
            result += f"📍 Location: {location_name}\n"
            
            # NOTE: Image information is intentionally omitted from the response
            # to encourage the agent to use the dedicated image sending tool.
            
            result += f"🔄 Updated: {inventory['timestamp']}\n"
            
            # Add stock status
            if inventory['total_available'] > 10:
                result += "✅ Stock Status: In Stock (Good availability)"
            elif inventory['total_available'] > 0:
                result += "⚠️ Stock Status: Low Stock (Limited availability)"
            else:
                result += "❌ Stock Status: Out of Stock"
            
            return result
            
    except Exception as e:
        return f"❌ Error checking inventory: {str(e)}" 