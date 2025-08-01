"""
Main ShopifyClient class for interacting with Shopify GraphQL Admin API.
"""

import json
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
import requests

from .exceptions import (
    ShopifyAPIError,
    RateLimitError,
    PermissionError,
    AuthenticationError,
    ValidationError,
    ConnectionError,
    GraphQLError,
    InventoryError,
    OrderError,
)
from .utils import format_graphql_id, extract_id_from_gid
from .constants import (
    DEFAULT_API_VERSION,
    MAX_RETRIES,
    RETRY_BASE_DELAY,
    REQUEST_TIMEOUT,
)


class ShopifyClient:
    """
    Main client for interacting with Shopify GraphQL Admin API.
    
    Provides methods for inventory management, order operations, product queries,
    customer management, and location operations.
    """
    
    def __init__(self, shop_domain: str, access_token: str, api_version: str = DEFAULT_API_VERSION):
        """
        Initialize the Shopify client.
        
        Args:
            shop_domain (str): Your Shopify shop domain (e.g., 'my-shop.myshopify.com')
            access_token (str): Shopify Admin API access token
            api_version (str): API version to use (default: '2024-10')
        """
        self.shop_domain = self._validate_shop_domain(shop_domain)
        self.access_token = access_token
        self.api_version = api_version
        self.base_url = f"https://{self.shop_domain}/admin/api/{api_version}/graphql.json"
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': access_token,
        })
        
        # API usage tracking
        self.api_calls_made = 0
        self.total_cost_used = 0
        self.last_call_cost = 0
        
        self.logger.info(f"ShopifyClient initialized for {shop_domain}")
    
    def _validate_shop_domain(self, shop_domain: str) -> str:
        """Validate and normalize shop domain."""
        if not shop_domain:
            raise ValidationError("Shop domain cannot be empty")
        
        # Remove protocol if present
        shop_domain = shop_domain.replace("https://", "").replace("http://", "")
        
        # Add .myshopify.com if not present
        if not shop_domain.endswith('.myshopify.com'):
            if '.' not in shop_domain:
                shop_domain = f"{shop_domain}.myshopify.com"
        
        return shop_domain
    
    def _make_graphql_request(self, query: str, variables: Optional[Dict[str, Any]] = None,
                             max_retries: int = MAX_RETRIES) -> Dict[str, Any]:
        """
        Make a GraphQL request to Shopify API with retry logic.
        
        Args:
            query (str): GraphQL query or mutation
            variables (Dict[str, Any], optional): Variables for the query
            max_retries (int): Maximum number of retry attempts
            
        Returns:
            Dict[str, Any]: Response data from the API
            
        Raises:
            Various ShopifyAPI exceptions based on error type
        """
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                self.logger.debug(f"Making GraphQL request (attempt {attempt + 1})")
                
                response = self.session.post(
                    self.base_url,
                    json=payload,
                    timeout=REQUEST_TIMEOUT
                )
                
                self.api_calls_made += 1
                
                # Handle HTTP errors
                if response.status_code == 401:
                    raise AuthenticationError("Invalid access token or expired")
                elif response.status_code == 403:
                    raise PermissionError("Insufficient permissions for this operation")
                elif response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    if attempt < max_retries:
                        self.logger.warning(f"Rate limited, retrying after {retry_after}s")
                        time.sleep(retry_after)
                        continue
                    raise RateLimitError("API rate limit exceeded", retry_after=retry_after)
                elif response.status_code >= 500:
                    if attempt < max_retries:
                        delay = RETRY_BASE_DELAY * (2 ** attempt)
                        self.logger.warning(f"Server error, retrying after {delay}s")
                        time.sleep(delay)
                        continue
                    raise ConnectionError(f"Server error: {response.status_code}")
                
                # Parse JSON response
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    raise ShopifyAPIError("Invalid JSON response from API")
                
                # Track API cost if available
                if 'extensions' in data and 'cost' in data['extensions']:
                    cost_info = data['extensions']['cost']
                    self.last_call_cost = cost_info.get('actualQueryCost', 0)
                    self.total_cost_used += self.last_call_cost
                
                # Handle GraphQL errors
                if 'errors' in data:
                    errors = data['errors']
                    error_messages = [error.get('message', str(error)) for error in errors]
                    
                    # Check for specific error types
                    for error in errors:
                        message = error.get('message', '').lower()
                        if 'access denied' in message or 'permission' in message:
                            raise PermissionError(f"Permission denied: {error_messages[0]}")
                        elif 'throttled' in message or 'rate limit' in message:
                            if attempt < max_retries:
                                time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
                                continue
                            raise RateLimitError(f"Rate limited: {error_messages[0]}")
                    
                    raise GraphQLError("GraphQL errors occurred", errors=error_messages)
                
                self.logger.debug(f"GraphQL request successful (cost: {self.last_call_cost})")
                return data
                
            except requests.exceptions.Timeout:
                last_exception = ConnectionError("Request timeout")
            except requests.exceptions.ConnectionError as e:
                last_exception = ConnectionError(f"Connection failed: {str(e)}")
            except (ShopifyAPIError, RateLimitError, PermissionError, AuthenticationError):
                # Re-raise our custom exceptions
                raise
            except Exception as e:
                last_exception = ShopifyAPIError(f"Unexpected error: {str(e)}")
            
            if attempt < max_retries:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                self.logger.warning(f"Request failed, retrying after {delay}s")
                time.sleep(delay)
        
        # If we get here, all retries failed
        if last_exception:
            raise last_exception
        else:
            raise ShopifyAPIError("Maximum retries exceeded")
    
    def _format_response(self, success: bool, data: Any = None, error: str = None, 
                        api_cost: int = None) -> Dict[str, Any]:
        """
        Format standardized response structure.
        
        Args:
            success (bool): Whether the operation was successful
            data (Any): Response data
            error (str): Error message if applicable
            api_cost (int): API cost of the operation
            
        Returns:
            Dict[str, Any]: Standardized response format
        """
        return {
            "success": success,
            "data": data,
            "error": error,
            "api_cost": api_cost or self.last_call_cost,
            "timestamp": datetime.now().isoformat(),
        }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check to validate connection and permissions.
        
        Returns:
            Dict[str, Any]: Health check results including shop info and permissions
        """
        query = """
        query {
            shop {
                id
                name
                email
                myshopifyDomain
                plan {
                    displayName
                }
            }
            app {
                id
                handle
            }
        }
        """
        
        try:
            response = self._make_graphql_request(query)
            shop_data = response.get('data', {}).get('shop', {})
            app_data = response.get('data', {}).get('app', {})
            
            health_info = {
                "connection": "healthy",
                "shop": {
                    "name": shop_data.get('name'),
                    "domain": shop_data.get('myshopifyDomain'),
                    "plan": shop_data.get('plan', {}).get('displayName'),
                },
                "app": {
                    "id": app_data.get('id'),
                    "handle": app_data.get('handle'),
                },
                "api_usage": {
                    "calls_made": self.api_calls_made,
                    "total_cost": self.total_cost_used,
                },
            }
            
            return self._format_response(True, health_info)
            
        except Exception as e:
            return self._format_response(False, error=str(e))
    
    def get_permissions(self) -> Dict[str, Any]:
        """
        Get available API permissions/scopes.
        
        Returns:
            Dict[str, Any]: Available permissions and app info
        """
        query = """
        query {
            app {
                id
                handle
                installation {
                    accessScopes {
                        description
                        handle
                    }
                }
            }
        }
        """
        
        try:
            response = self._make_graphql_request(query)
            app_data = response.get('data', {}).get('app', {})
            installation = app_data.get('installation', {})
            scopes = installation.get('accessScopes', [])
            
            permissions = {
                "app_id": app_data.get('id'),
                "app_handle": app_data.get('handle'),
                "scopes": [scope.get('handle') for scope in scopes],
                "scope_details": scopes,
            }
            
            return self._format_response(True, permissions)
            
        except Exception as e:
            return self._format_response(False, error=str(e))
    
    def get_api_usage(self) -> Dict[str, Any]:
        """
        Get API usage statistics.
        
        Returns:
            Dict[str, Any]: API usage information
        """
        usage_info = {
            "calls_made": self.api_calls_made,
            "total_cost_used": self.total_cost_used,
            "last_call_cost": self.last_call_cost,
            "average_cost_per_call": (
                self.total_cost_used / self.api_calls_made 
                if self.api_calls_made > 0 else 0
            ),
        }
        
        return self._format_response(True, usage_info)
    
    def __del__(self):
        """Clean up session when client is destroyed."""
        if hasattr(self, 'session'):
            self.session.close()
    
    # ===== INVENTORY MANAGEMENT METHODS =====
    
    def get_inventory(self, variant_id: Optional[str] = None, product_id: Optional[str] = None,
                     location_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get inventory information for product variants.
        
        Args:
            variant_id (str, optional): Specific variant ID to get inventory for
            product_id (str, optional): Product ID to get inventory for all variants
            location_id (str, optional): Specific location ID to filter by
            
        Returns:
            Dict[str, Any]: Inventory information
        """
        from .constants import PRODUCT_INVENTORY_QUERY
        from .utils import format_graphql_id, extract_edges_nodes
        
        try:
            if variant_id:
                # Get inventory for specific variant
                gid = format_graphql_id('variant', variant_id)
                response = self._make_graphql_request(PRODUCT_INVENTORY_QUERY, {"id": gid})
                
                variant_data = response.get('data', {}).get('productVariant', {})
                if not variant_data:
                    return self._format_response(False, error="Variant not found")
                
                inventory_levels = extract_edges_nodes(variant_data, ['inventoryItem', 'inventoryLevels'])
                
                # Filter by location if specified
                if location_id:
                    location_gid = format_graphql_id('location', location_id)
                    inventory_levels = [
                        level for level in inventory_levels 
                        if level.get('location', {}).get('id') == location_gid
                    ]
                
                # Format inventory data
                inventory_info = {
                    "variant_id": variant_data.get('id'),
                    "variant_title": variant_data.get('title'),
                    "product_title": variant_data.get('product', {}).get('title'),
                    "inventory_item_id": variant_data.get('inventoryItem', {}).get('id'),
                    "locations": []
                }
                
                for level in inventory_levels:
                    quantities = level.get('quantities', [])
                    available_qty = next(
                        (q['quantity'] for q in quantities if q['name'] == 'available'), 
                        0
                    )
                    
                    inventory_info["locations"].append({
                        "location_id": level.get('location', {}).get('id'),
                        "location_name": level.get('location', {}).get('name'),
                        "available": available_qty,
                        "inventory_level_id": level.get('id')
                    })
                
                return self._format_response(True, inventory_info)
                
            elif product_id:
                # Get inventory for all variants of a product
                # This would require a different query - simplified for now
                return self._format_response(False, error="Product-level inventory queries not implemented yet")
            
            else:
                return self._format_response(False, error="Either variant_id or product_id must be provided")
                
        except Exception as e:
            self.logger.error(f"Error getting inventory: {str(e)}")
            return self._format_response(False, error=str(e))
    
    def adjust_inventory(self, variant_id: str, quantity_change: int, reason: str = "correction",
                        location_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Adjust inventory quantity for a variant (increase or decrease).
        
        Args:
            variant_id (str): Variant ID to adjust inventory for
            quantity_change (int): Amount to change (positive to increase, negative to decrease)
            reason (str): Reason for adjustment (default: "correction")
            location_id (str, optional): Specific location ID (uses first location if not specified)
            
        Returns:
            Dict[str, Any]: Adjustment result
        """
        from .constants import INVENTORY_ADJUST_MUTATION, INVENTORY_REASONS
        from .utils import format_graphql_id, extract_id_from_gid
        
        try:
            # Validate inputs
            if not isinstance(quantity_change, int):
                return self._format_response(False, error="quantity_change must be an integer")
            
            # Get variant inventory info first
            inventory_info = self.get_inventory(variant_id=variant_id, location_id=location_id)
            if not inventory_info['success']:
                return inventory_info
            
            variant_data = inventory_info['data']
            locations = variant_data['locations']
            
            if not locations:
                return self._format_response(False, error="No inventory locations found for variant")
            
            # Use specified location or first available
            if location_id:
                target_location = next(
                    (loc for loc in locations if extract_id_from_gid(loc['location_id']) == str(location_id)),
                    None
                )
                if not target_location:
                    return self._format_response(False, error=f"Location {location_id} not found for variant")
            else:
                target_location = locations[0]
            
            # Prepare mutation variables
            inventory_item_id = variant_data['inventory_item_id']
            location_gid = target_location['location_id']
            
            # Map reason to Shopify constant
            shopify_reason = INVENTORY_REASONS.get(reason, reason)
            
            variables = {
                "input": {
                    "reason": shopify_reason,
                    "name": "available",
                    "referenceDocumentUri": f"shopify-method://adjustment/{variant_id}",
                    "changes": [
                        {
                            "delta": quantity_change,
                            "inventoryItemId": inventory_item_id,
                            "locationId": location_gid
                        }
                    ]
                }
            }
            
            response = self._make_graphql_request(INVENTORY_ADJUST_MUTATION, variables)
            
            # Check for user errors
            adjustment_data = response.get('data', {}).get('inventoryAdjustQuantities', {})
            user_errors = adjustment_data.get('userErrors', [])
            
            if user_errors:
                error_messages = [error.get('message', str(error)) for error in user_errors]
                return self._format_response(False, error=f"Adjustment failed: {'; '.join(error_messages)}")
            
            # Extract adjustment results
            adjustment_group = adjustment_data.get('inventoryAdjustmentGroup', {})
            changes = adjustment_group.get('changes', [])
            
            if changes:
                change = changes[0]
                result = {
                    "variant_id": variant_data['variant_id'],
                    "variant_title": variant_data['variant_title'],
                    "location_id": target_location['location_id'],
                    "location_name": target_location['location_name'],
                    "delta": change.get('delta'),
                    "quantity_after_change": change.get('quantityAfterChange'),
                    "previous_quantity": target_location['available'],
                    "reason": shopify_reason
                }
                
                return self._format_response(True, result)
            else:
                return self._format_response(False, error="No changes returned from adjustment")
                
        except Exception as e:
            self.logger.error(f"Error adjusting inventory: {str(e)}")
            return self._format_response(False, error=str(e))
    
    def set_inventory(self, variant_id: str, quantity: int, reason: str = "correction",
                     location_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Set absolute inventory quantity for a variant.
        
        This method is currently disabled due to GraphQL schema compatibility issues.
        Use adjust_inventory() instead to achieve the same result.
        
        Args:
            variant_id (str): Variant ID to set inventory for
            quantity (int): Absolute quantity to set
            reason (str): Reason for change (default: "correction")
            location_id (str, optional): Specific location ID
            
        Returns:
            Dict[str, Any]: Error response indicating method is disabled
        """
        return self._format_response(
            False, 
            error="set_inventory method is disabled due to GraphQL schema compatibility issues. Use adjust_inventory() instead."
        )
    
    # ===== ORDER MANAGEMENT METHODS =====
    
    def create_order(self, line_items: List[Dict[str, Any]], customer_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new order.
        
        Args:
            line_items (List[Dict[str, Any]]): List of line items for the order
            customer_info (Dict[str, Any], optional): Customer information
            
        Returns:
            Dict[str, Any]: Created order information
        """
        from .constants import ORDER_CREATE_MUTATION
        from .utils import validate_line_items, format_graphql_id
        
        try:
            # Validate line items
            if not validate_line_items(line_items):
                return self._format_response(False, error="Invalid line items provided")
            
            # Format line items for GraphQL
            formatted_line_items = []
            for item in line_items:
                formatted_item = {
                    "quantity": item.get('quantity', 1)
                }
                
                if 'variantId' in item:
                    formatted_item['variantId'] = format_graphql_id('variant', item['variantId'])
                elif 'productId' in item:
                    formatted_item['productId'] = format_graphql_id('product', item['productId'])
                
                if 'price' in item:
                    formatted_item['price'] = str(item['price'])
                
                formatted_line_items.append(formatted_item)
            
            # Prepare order input
            order_input = {
                "lineItems": formatted_line_items
            }
            
            # Add customer info if provided
            if customer_info:
                if 'email' in customer_info:
                    order_input['email'] = customer_info['email']
                if 'customerId' in customer_info:
                    order_input['customerId'] = format_graphql_id('customer', customer_info['customerId'])
            
            variables = {"order": order_input}
            
            response = self._make_graphql_request(ORDER_CREATE_MUTATION, variables)
            
            # Check for user errors
            order_data = response.get('data', {}).get('orderCreate', {})
            user_errors = order_data.get('userErrors', [])
            
            if user_errors:
                error_messages = [error.get('message', str(error)) for error in user_errors]
                return self._format_response(False, error=f"Order creation failed: {'; '.join(error_messages)}")
            
            # Extract order information
            order = order_data.get('order', {})
            if order:
                return self._format_response(True, order)
            else:
                return self._format_response(False, error="No order data returned")
                
        except Exception as e:
            self.logger.error(f"Error creating order: {str(e)}")
            return self._format_response(False, error=str(e))
    
    def create_draft_order(self, line_items: List[Dict[str, Any]], customer_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a draft order.
        
        Args:
            line_items (List[Dict[str, Any]]): List of line items for the draft order
            customer_info (Dict[str, Any], optional): Customer information
            
        Returns:
            Dict[str, Any]: Created draft order information
        """
        from .constants import DRAFT_ORDER_CREATE_MUTATION
        from .utils import validate_line_items, format_graphql_id
        
        try:
            # Validate line items
            if not validate_line_items(line_items):
                return self._format_response(False, error="Invalid line items provided")
            
            # Format line items for GraphQL
            formatted_line_items = []
            for item in line_items:
                formatted_item = {
                    "quantity": item.get('quantity', 1)
                }
                
                if 'variantId' in item:
                    formatted_item['variantId'] = format_graphql_id('variant', item['variantId'])
                elif 'productId' in item:
                    formatted_item['productId'] = format_graphql_id('product', item['productId'])
                
                if 'price' in item:
                    formatted_item['price'] = str(item['price'])
                
                formatted_line_items.append(formatted_item)
            
            # Prepare draft order input
            draft_order_input = {
                "lineItems": formatted_line_items,
                "useCustomerDefaultAddress": True
            }
            
            # Add customer info if provided
            if customer_info:
                if 'email' in customer_info:
                    draft_order_input['email'] = customer_info['email']
                if 'customerId' in customer_info:
                    draft_order_input['customerId'] = format_graphql_id('customer', customer_info['customerId'])
            
            variables = {"input": draft_order_input}
            
            response = self._make_graphql_request(DRAFT_ORDER_CREATE_MUTATION, variables)
            
            # Check for user errors
            draft_order_data = response.get('data', {}).get('draftOrderCreate', {})
            user_errors = draft_order_data.get('userErrors', [])
            
            if user_errors:
                error_messages = [error.get('message', str(error)) for error in user_errors]
                return self._format_response(False, error=f"Draft order creation failed: {'; '.join(error_messages)}")
            
            # Extract draft order information
            draft_order = draft_order_data.get('draftOrder', {})
            if draft_order:
                return self._format_response(True, draft_order)
            else:
                return self._format_response(False, error="No draft order data returned")
                
        except Exception as e:
            self.logger.error(f"Error creating draft order: {str(e)}")
            return self._format_response(False, error=str(e))
    
    def get_order_details(self, order_id: str) -> Dict[str, Any]:
        """
        Get detailed information about an order.
        
        Args:
            order_id (str): Order ID to retrieve details for
            
        Returns:
            Dict[str, Any]: Order details
        """
        from .utils import format_graphql_id
        
        query = """
        query getOrder($id: ID!) {
            order(id: $id) {
                id
                name
                email
                phone
                totalPrice
                subtotalPrice
                totalTax
                processedAt
                createdAt
                updatedAt
                lineItems(first: 20) {
                    edges {
                        node {
                            id
                            title
                            quantity
                            originalUnitPrice
                            variant {
                                id
                                title
                                sku
                            }
                            product {
                                id
                                title
                            }
                        }
                    }
                }
                customer {
                    id
                    firstName
                    lastName
                    email
                }
                shippingAddress {
                    firstName
                    lastName
                    address1
                    address2
                    city
                    province
                    country
                    zip
                }
            }
        }
        """
        
        try:
            gid = format_graphql_id('order', order_id)
            response = self._make_graphql_request(query, {"id": gid})
            
            order_data = response.get('data', {}).get('order', {})
            if not order_data:
                return self._format_response(False, error="Order not found")
            
            return self._format_response(True, order_data)
            
        except Exception as e:
            self.logger.error(f"Error getting order details: {str(e)}")
            return self._format_response(False, error=str(e))
    
    # ===== PRODUCT MANAGEMENT METHODS =====
    
    def get_product(self, product_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a product.
        
        Args:
            product_id (str): Product ID to retrieve
            
        Returns:
            Dict[str, Any]: Product details
        """
        from .constants import PRODUCT_DETAILS_QUERY
        from .utils import format_graphql_id, extract_edges_nodes
        
        try:
            gid = format_graphql_id('product', product_id)
            response = self._make_graphql_request(PRODUCT_DETAILS_QUERY, {"id": gid})
            
            product_data = response.get('data', {}).get('product', {})
            if not product_data:
                return self._format_response(False, error="Product not found")
            
            # Format the response to include variants and images as lists
            formatted_product = dict(product_data)
            formatted_product['variants'] = extract_edges_nodes(product_data, ['variants'])
            formatted_product['images'] = extract_edges_nodes(product_data, ['images'])
            
            return self._format_response(True, formatted_product)
            
        except Exception as e:
            self.logger.error(f"Error getting product: {str(e)}")
            return self._format_response(False, error=str(e))
    
    def get_products(self, limit: int = 10, search: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a list of products with optional search.
        
        Args:
            limit (int): Maximum number of products to return (default: 10)
            search (str, optional): Search query to filter products
            
        Returns:
            Dict[str, Any]: List of products
        """
        from .constants import PRODUCTS_LIST_QUERY
        from .utils import extract_edges_nodes, sanitize_search_query
        
        try:
            # Sanitize search query
            if search:
                search = sanitize_search_query(search)
                if not search:
                    return self._format_response(False, error="Invalid search query")
            
            variables = {
                "first": min(limit, 50),  # Limit to reasonable maximum
                "query": search
            }
            
            response = self._make_graphql_request(PRODUCTS_LIST_QUERY, variables)
            
            products_data = response.get('data', {}).get('products', {})
            products = extract_edges_nodes(products_data, [])
            page_info = products_data.get('pageInfo', {})
            
            # Format variants for each product
            for product in products:
                product['variants'] = extract_edges_nodes(product, ['variants'])
            
            result = {
                "products": products,
                "count": len(products),
                "has_next_page": page_info.get('hasNextPage', False),
                "search_query": search
            }
            
            return self._format_response(True, result)
            
        except Exception as e:
            self.logger.error(f"Error getting products: {str(e)}")
            return self._format_response(False, error=str(e))
    
    def get_product_variants(self, product_id: str) -> Dict[str, Any]:
        """
        Get all variants for a specific product.
        
        Args:
            product_id (str): Product ID to get variants for
            
        Returns:
            Dict[str, Any]: Product variants
        """
        from .utils import format_graphql_id, extract_edges_nodes
        
        query = """
        query getProductVariants($id: ID!) {
            product(id: $id) {
                id
                title
                handle
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
                            position
                            availableForSale
                            selectedOptions {
                                name
                                value
                            }
                            inventoryItem {
                                id
                            }
                        }
                    }
                }
            }
        }
        """
        
        try:
            gid = format_graphql_id('product', product_id)
            response = self._make_graphql_request(query, {"id": gid})
            
            product_data = response.get('data', {}).get('product', {})
            if not product_data:
                return self._format_response(False, error="Product not found")
            
            variants = extract_edges_nodes(product_data, ['variants'])
            
            result = {
                "product_id": product_data.get('id'),
                "product_title": product_data.get('title'),
                "product_handle": product_data.get('handle'),
                "variants": variants,
                "variant_count": len(variants)
            }
            
            return self._format_response(True, result)
            
        except Exception as e:
            self.logger.error(f"Error getting product variants: {str(e)}")
            return self._format_response(False, error=str(e)) 
    
    # ===== SPECIAL OPERATIONS =====
    
    def create_draft_order_with_inventory_adjustment(self, variant_id: str, quantity: int = 1,
                                                   customer_info: Optional[Dict[str, Any]] = None,
                                                   reason: str = "correction") -> Dict[str, Any]:
        """
        Create a draft order and automatically decrease inventory.
        
        This method performs both operations atomically - if either fails, 
        both are rolled back.
        
        Args:
            variant_id (str): Variant ID to create order for
            quantity (int): Quantity to order (default: 1)
            customer_info (Dict[str, Any], optional): Customer information
            reason (str): Reason for inventory adjustment (default: "correction")
            
        Returns:
            Dict[str, Any]: Combined result of draft order creation and inventory adjustment
        """
        try:
            self.logger.info(f"Creating draft order with inventory adjustment for variant {variant_id}")
            
            # Step 1: Check current inventory
            inventory_check = self.get_inventory(variant_id=variant_id)
            if not inventory_check['success']:
                return self._format_response(False, error=f"Inventory check failed: {inventory_check['error']}")
            
            inventory_data = inventory_check['data']
            locations = inventory_data['locations']
            
            if not locations:
                return self._format_response(False, error="No inventory locations found for variant")
            
            current_qty = locations[0]['available']
            if current_qty < quantity:
                return self._format_response(
                    False, 
                    error=f"Insufficient inventory: {current_qty} available, {quantity} requested"
                )
            
            # Step 2: Create draft order
            line_items = [{'variantId': variant_id, 'quantity': quantity}]
            draft_order_result = self.create_draft_order(line_items, customer_info)
            
            if not draft_order_result['success']:
                return self._format_response(
                    False, 
                    error=f"Draft order creation failed: {draft_order_result['error']}"
                )
            
            draft_order = draft_order_result['data']
            
            # Step 3: Adjust inventory (decrease)
            inventory_result = self.adjust_inventory(variant_id, -quantity, reason)
            
            if not inventory_result['success']:
                # If inventory adjustment fails, we should ideally cancel the draft order
                # For now, we'll log the issue and return an error
                self.logger.error(f"Inventory adjustment failed after draft order creation. Draft order: {draft_order['name']}")
                return self._format_response(
                    False, 
                    error=f"Draft order created ({draft_order['name']}) but inventory adjustment failed: {inventory_result['error']}"
                )
            
            # Step 4: Combine results
            combined_result = {
                "draft_order": {
                    "id": draft_order['id'],
                    "name": draft_order['name'],
                    "status": draft_order['status'],
                    "total_price": draft_order['totalPrice'],
                    "created_at": draft_order['createdAt']
                },
                "inventory_adjustment": {
                    "variant_id": inventory_result['data']['variant_id'],
                    "variant_title": inventory_result['data']['variant_title'],
                    "location_name": inventory_result['data']['location_name'],
                    "previous_quantity": current_qty,
                    "quantity_after_change": inventory_result['data']['quantity_after_change'],
                    "delta": inventory_result['data']['delta'],
                    "reason": reason
                },
                "operation_summary": {
                    "variant_id": variant_id,
                    "product_title": inventory_data['product_title'],
                    "quantity_ordered": quantity,
                    "inventory_reserved": quantity,
                    "draft_order_name": draft_order['name']
                }
            }
            
            self.logger.info(f"Successfully created draft order {draft_order['name']} and adjusted inventory")
            return self._format_response(True, combined_result)
            
        except Exception as e:
            self.logger.error(f"Error in create_draft_order_with_inventory_adjustment: {str(e)}")
            return self._format_response(False, error=str(e))
    
    def get_locations(self) -> Dict[str, Any]:
        """
        Get all store locations.
        
        Returns:
            Dict[str, Any]: List of store locations
        """
        from .constants import LOCATIONS_QUERY
        from .utils import extract_edges_nodes
        
        try:
            response = self._make_graphql_request(LOCATIONS_QUERY)
            
            locations_data = response.get('data', {}).get('locations', {})
            locations = extract_edges_nodes(locations_data, [])
            
            result = {
                "locations": locations,
                "count": len(locations)
            }
            
            return self._format_response(True, result)
            
        except Exception as e:
            self.logger.error(f"Error getting locations: {str(e)}")
            return self._format_response(False, error=str(e))
    
    def get_location_inventory(self, location_id: str, variant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get inventory for a specific location.
        
        Args:
            location_id (str): Location ID to get inventory for
            variant_id (str, optional): Specific variant ID to filter by
            
        Returns:
            Dict[str, Any]: Location inventory information
        """
        try:
            if variant_id:
                # Get inventory for specific variant at this location
                inventory_result = self.get_inventory(variant_id=variant_id, location_id=location_id)
                
                if inventory_result['success']:
                    inventory_data = inventory_result['data']
                    location_inventory = next(
                        (loc for loc in inventory_data['locations'] 
                         if loc['location_id'].endswith(f'/{location_id}')), 
                        None
                    )
                    
                    if location_inventory:
                        result = {
                            "location_id": location_inventory['location_id'],
                            "location_name": location_inventory['location_name'],
                            "variant": {
                                "variant_id": inventory_data['variant_id'],
                                "variant_title": inventory_data['variant_title'],
                                "product_title": inventory_data['product_title'],
                                "available": location_inventory['available']
                            }
                        }
                        return self._format_response(True, result)
                    else:
                        return self._format_response(False, error=f"Variant not found at location {location_id}")
                else:
                    return inventory_result
            else:
                # This would require a more complex query to get all inventory at a location
                return self._format_response(False, error="Getting all inventory for a location not implemented yet")
                
        except Exception as e:
            self.logger.error(f"Error getting location inventory: {str(e)}")
            return self._format_response(False, error=str(e))
    
    def bulk_adjust_inventory(self, adjustments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Perform bulk inventory adjustments.
        
        Args:
            adjustments (List[Dict[str, Any]]): List of adjustment specifications
                Each item should have: variant_id, quantity_change, reason (optional)
                
        Returns:
            Dict[str, Any]: Bulk adjustment results
        """
        from .constants import MAX_BULK_OPERATIONS
        from .utils import chunk_list
        
        try:
            if not adjustments or not isinstance(adjustments, list):
                return self._format_response(False, error="Invalid adjustments list")
            
            if len(adjustments) > MAX_BULK_OPERATIONS:
                return self._format_response(
                    False, 
                    error=f"Too many adjustments: {len(adjustments)} > {MAX_BULK_OPERATIONS}"
                )
            
            results = []
            failed_adjustments = []
            
            # Process adjustments in chunks if needed
            for adjustment in adjustments:
                if not isinstance(adjustment, dict):
                    failed_adjustments.append({"adjustment": adjustment, "error": "Invalid adjustment format"})
                    continue
                
                variant_id = adjustment.get('variant_id')
                quantity_change = adjustment.get('quantity_change')
                reason = adjustment.get('reason', 'correction')
                
                if not variant_id or quantity_change is None:
                    failed_adjustments.append({
                        "adjustment": adjustment, 
                        "error": "Missing variant_id or quantity_change"
                    })
                    continue
                
                # Perform individual adjustment
                result = self.adjust_inventory(variant_id, quantity_change, reason)
                
                if result['success']:
                    results.append({
                        "variant_id": variant_id,
                        "result": result['data']
                    })
                else:
                    failed_adjustments.append({
                        "variant_id": variant_id,
                        "adjustment": adjustment,
                        "error": result['error']
                    })
            
            # Compile final result
            bulk_result = {
                "successful_adjustments": results,
                "failed_adjustments": failed_adjustments,
                "total_requested": len(adjustments),
                "successful_count": len(results),
                "failed_count": len(failed_adjustments)
            }
            
            # Consider it successful if at least some adjustments worked
            success = len(results) > 0
            
            return self._format_response(success, bulk_result)
            
        except Exception as e:
            self.logger.error(f"Error in bulk inventory adjustment: {str(e)}")
            return self._format_response(False, error=str(e)) 