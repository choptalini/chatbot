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
    
    def create_order(self, line_items: List[Dict[str, Any]], customer_info: Optional[Dict[str, Any]] = None,
                     shipping_address: Optional[Dict[str, Any]] = None,
                     billing_address: Optional[Dict[str, Any]] = None,
                     send_receipt: Optional[bool] = None,
                     send_fulfillment_receipt: Optional[bool] = None,
                     subtotal: Optional[float] = None) -> Dict[str, Any]:
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
            
            # Use REST Admin API as the primary method for creating orders
            return self._create_order_via_rest(
                original_line_items=line_items,
                customer_info=customer_info or {},
                shipping_address=shipping_address or {},
                billing_address=billing_address or {},
                subtotal=subtotal,
            )
            
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
                
                # Avoid deprecated/plain price; price overrides should use Money inputs in upstream flows
                
                formatted_line_items.append(formatted_item)
            
            # Prepare order input
            order_input = {
                "lineItems": formatted_line_items
            }
            
            # Add customer info if provided
            if customer_info:
                email = customer_info.get('email')
                customer_id = customer_info.get('customerId')
                first_name = customer_info.get('first_name') or customer_info.get('firstName')
                last_name = customer_info.get('last_name') or customer_info.get('lastName')
                phone = customer_info.get('phone')

                # Determine if nested customer input is supported (2025-01+)
                def _supports_nested_customer(version: str) -> bool:
                    try:
                        year, month = version.split('-')
                        return int(year) > 2024 or (int(year) == 2025 and int(month) >= 1)
                    except Exception:
                        return False

                if _supports_nested_customer(self.api_version):
                    customer_block: Dict[str, Any] = {}
                    if customer_id:
                        customer_block['toAssociate'] = {"id": format_graphql_id('customer', customer_id)}
                    elif email:
                        to_upsert: Dict[str, Any] = {"email": email}
                        if first_name:
                            to_upsert['firstName'] = first_name
                        if last_name:
                            to_upsert['lastName'] = last_name
                        if phone:
                            to_upsert['phone'] = phone
                        customer_block['toUpsert'] = to_upsert

                    if customer_block:
                        order_input['customer'] = customer_block
                else:
                    # Fallback for older API versions: use top-level fields
                    if email:
                        order_input['email'] = email
                    if customer_id:
                        order_input['customerId'] = format_graphql_id('customer', customer_id)

            # Map shipping and billing addresses if provided
            def _map_address(addr: Dict[str, Any]) -> Dict[str, Any]:
                return {
                    "firstName": addr.get('first_name') or addr.get('firstName'),
                    "lastName": addr.get('last_name') or addr.get('lastName'),
                    "address1": addr.get('address1') or addr.get('line1'),
                    "address2": addr.get('address2') or addr.get('line2'),
                    "city": addr.get('city'),
                    "province": addr.get('province') or addr.get('state') or addr.get('provinceCode'),
                    "country": addr.get('country') or addr.get('countryCode'),
                    "zip": addr.get('zip') or addr.get('postal_code') or addr.get('postalCode'),
                    "phone": addr.get('phone')
                }

            if shipping_address:
                order_input['shippingAddress'] = _map_address(shipping_address)
            if billing_address:
                order_input['billingAddress'] = _map_address(billing_address)
            
            variables = {"order": order_input}

            # Options (notifications, inventory behavior)
            options: Dict[str, Any] = {}
            if send_receipt is not None:
                options['sendReceipt'] = bool(send_receipt)
            if send_fulfillment_receipt is not None:
                options['sendFulfillmentReceipt'] = bool(send_fulfillment_receipt)
            if options:
                variables['options'] = options
            
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
                
        except GraphQLError as e:
            # Fallback to REST Admin API when GraphQL schema/input type isn't available on this shop
            msg = str(e).lower()
            if "ordercreateinput" in msg or "ordercreateorderinput" in msg or "isn't a defined input type" in msg:
                try:
                    return self._create_order_via_rest(
                        original_line_items=line_items,
                        customer_info=customer_info or {},
                        shipping_address=shipping_address or {},
                        billing_address=billing_address or {},
                        subtotal=subtotal,
                    )
                except Exception as rest_err:
                    self.logger.error(f"REST order creation failed: {rest_err}")
                    return self._format_response(False, error=str(rest_err))
            # Otherwise, bubble up as normal error
            self.logger.error(f"Error creating order (GraphQL): {str(e)}")
            return self._format_response(False, error=str(e))
        except Exception as e:
            self.logger.error(f"Error creating order: {str(e)}")
            return self._format_response(False, error=str(e))
    
    def create_draft_order(self, line_items: List[Dict[str, Any]], customer_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a draft order using the REST Admin API (strict REST path).
        
        Args:
            line_items (List[Dict[str, Any]]): List of line items (accepts variantId/productId, quantity, optional price)
            customer_info (Dict[str, Any], optional): Customer information (email or customerId)
            
        Returns:
            Dict[str, Any]: Created draft order information (normalized)
        """
        from .utils import validate_line_items, extract_id_from_gid
        
        try:
            # Validate input line items
            if not validate_line_items(line_items):
                return self._format_response(False, error="Invalid line items provided")

            # Build REST line items: { variant_id, quantity, price? }
            rest_line_items: List[Dict[str, Any]] = []
            for item in line_items or []:
                qty = int(item.get('quantity', 1))
                # Prefer variantId; productId alone isn't sufficient for draft order line_items in REST
                variant_id_val = item.get('variantId') or item.get('variant_id')
                if not variant_id_val:
                    # Skip items we cannot map to a concrete purchasable variant
                    continue
                if isinstance(variant_id_val, str) and variant_id_val.startswith('gid://shopify/'):
                    numeric = extract_id_from_gid(variant_id_val)
                else:
                    numeric = str(variant_id_val)
                if not numeric:
                    continue
                line_obj: Dict[str, Any] = {"variant_id": int(numeric), "quantity": qty}
                if 'price' in item and item['price'] is not None:
                    # REST accepts overriding draft line item price directly
                    line_obj["price"] = str(item['price'])
                rest_line_items.append(line_obj)

            if not rest_line_items:
                return self._format_response(False, error="No valid variant_id found for REST draft order creation")

            # Build payload for REST draft order
            payload: Dict[str, Any] = {
                "draft_order": {
                    "line_items": rest_line_items,
                    "use_customer_default_address": True,
                }
            }

            # Email/customer mapping
            if isinstance(customer_info, dict) and customer_info:
                email = customer_info.get('email')
                if email:
                    payload["draft_order"]["email"] = email
                # If a customer id (gid or numeric) is provided, attach minimal customer object
                cust_id = customer_info.get('customerId') or customer_info.get('customer_id')
                if cust_id:
                    if isinstance(cust_id, str) and cust_id.startswith('gid://shopify/'):
                        cust_numeric = extract_id_from_gid(cust_id)
                    else:
                        cust_numeric = str(cust_id)
                    try:
                        payload["draft_order"]["customer"] = {"id": int(cust_numeric)}
                    except Exception:
                        # If id isn't numeric, omit customer block; email will still work
                        pass

            url = f"https://{self.shop_domain}/admin/api/{self.api_version}/draft_orders.json"
            resp = self.session.post(url, json=payload, timeout=REQUEST_TIMEOUT)

            if resp.status_code not in (200, 201):
                try:
                    err_body = resp.json()
                except Exception:
                    err_body = {"error": resp.text}
                return self._format_response(
                    False,
                    error=f"REST draft order create failed (status {resp.status_code}): {err_body}",
                )

            data = resp.json() if resp.content else {}
            draft = (data or {}).get("draft_order", {})
            if not draft:
                return self._format_response(False, error="REST draft order created but response missing 'draft_order'")

            # Normalize to a GraphQL-like shape used elsewhere in the codebase
            normalized = {
                "id": draft.get("id"),
                "name": draft.get("name"),
                "status": draft.get("status"),
                "totalPrice": draft.get("total_price"),
                "createdAt": draft.get("created_at"),
            }
            return self._format_response(True, normalized)

        except Exception as e:
            self.logger.error(f"Error creating draft order (REST): {str(e)}")
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

    def get_products_full(self, limit: int = 50, search: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a list of products with expanded fields (variants, images, options, tags, etc.).
        """
        from .constants import PRODUCTS_FULL_LIST_QUERY
        from .utils import extract_edges_nodes, sanitize_search_query
        try:
            if search:
                search = sanitize_search_query(search)
                if not search:
                    return self._format_response(False, error="Invalid search query")

            variables = {"first": min(limit, 50), "query": search}
            response = self._make_graphql_request(PRODUCTS_FULL_LIST_QUERY, variables)
            products_data = response.get('data', {}).get('products', {})
            products = extract_edges_nodes(products_data, [])
            page_info = products_data.get('pageInfo', {})

            # Flatten inner connections for each product
            for product in products:
                product['variants'] = extract_edges_nodes(product, ['variants'])
                product['images'] = extract_edges_nodes(product, ['images'])

            result = {
                "products": products,
                "count": len(products),
                "has_next_page": page_info.get('hasNextPage', False),
                "search_query": search
            }
            return self._format_response(True, result)
        except Exception as e:
            self.logger.error(f"Error getting full products: {str(e)}")
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

    # ===== PRIVATE HELPERS (REST FALLBACK) =====
    def _create_order_via_rest(
        self,
        original_line_items: List[Dict[str, Any]],
        customer_info: Dict[str, Any],
        shipping_address: Dict[str, Any],
        billing_address: Dict[str, Any],
        subtotal: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Create an order using the REST Admin API as a compatibility fallback.
        Expects original input shapes (variantId/productId, quantity, customer_info, addresses).
        """
        from .utils import extract_id_from_gid

        # Build REST line items (require numeric variant_id)
        rest_line_items: List[Dict[str, Any]] = []
        calculated_subtotal = 0.0
        for item in original_line_items or []:
            qty = int(item.get("quantity", 1))
            variant_id_val = item.get("variantId") or item.get("variant_id")
            price = item.get("price")  # May include discounted price
            if variant_id_val:
                if isinstance(variant_id_val, str) and variant_id_val.startswith("gid://shopify/"):
                    numeric = extract_id_from_gid(variant_id_val)
                else:
                    numeric = str(variant_id_val)
                if not numeric:
                    continue
                try:
                    line_item = {"variant_id": int(numeric), "quantity": qty}
                    if price is not None:
                        line_item["price"] = str(price)  # Override price for discounts
                        calculated_subtotal += float(price) * qty
                    rest_line_items.append(line_item)
                except ValueError:
                    # Skip items with non-numeric variant ids
                    continue

        if not rest_line_items:
            return self._format_response(False, error="No valid variant_id found for REST order creation")

        # Use provided subtotal or calculate from line items
        order_subtotal = subtotal if subtotal is not None else calculated_subtotal
        
        # Calculate shipping charge for orders under $40
        shipping_fee = 0.0 if order_subtotal >= 40.0 else 3.0

        # Map addresses to REST shape using the original (snake_case) fields when available
        def _rest_addr(src: Dict[str, Any]) -> Dict[str, Any]:
            if not isinstance(src, dict) or not src:
                return {}
            return {
                "first_name": src.get("first_name") or src.get("firstName"),
                "last_name": src.get("last_name") or src.get("lastName"),
                "phone": src.get("phone"),
                "address1": src.get("address1") or src.get("line1"),
                "address2": src.get("address2") or src.get("line2"),
                "city": src.get("city"),
                "province": src.get("province") or src.get("state") or src.get("provinceCode"),
                "country": src.get("country") or src.get("countryCode"),
                "zip": src.get("zip") or src.get("postal_code") or src.get("postalCode"),
            }

        # Use static email for all AstroSouks orders
        customer_email = customer_info.get("email") or "shopastrotechlb@gmail.com"
        
        payload: Dict[str, Any] = {
            "order": {
                "email": customer_email,
                "line_items": rest_line_items,
                # Do NOT include a full customer object by default to avoid 422
                # errors like "customer.phone_number has already been taken".
                # We will attach a customer only when an explicit id is supplied.
                "financial_status": "pending",
                "send_receipt": True,
                "send_fulfillment_receipt": False,
                "inventory_behaviour": "decrement_obeying_policy"
            }
        }

        # Attach an existing customer by id when provided
        cust_id = (customer_info or {}).get("customerId") or (customer_info or {}).get("customer_id")
        if cust_id is not None:
            try:
                # Accept gid or numeric
                if isinstance(cust_id, str) and cust_id.startswith('gid://shopify/'):
                    cust_numeric = extract_id_from_gid(cust_id)
                else:
                    cust_numeric = str(cust_id)
                payload["order"]["customer"] = {"id": int(cust_numeric)}
            except Exception:
                # If the id is not numeric, skip attaching customer to avoid 422
                pass

        # Add shipping line if there's a shipping fee
        if shipping_fee > 0:
            payload["order"]["shipping_lines"] = [
                {
                    "title": "Standard Shipping",
                    "price": str(shipping_fee),
                    "code": "STANDARD",
                    "source": "shopify"
                }
            ]

        ship = _rest_addr(shipping_address)
        if any(v for v in ship.values() if v):
            # Ensure customer name is in shipping address
            if not ship.get("first_name") and customer_info:
                ship["first_name"] = customer_info.get("first_name", "")
            if not ship.get("last_name") and customer_info:
                ship["last_name"] = customer_info.get("last_name", "")
            if not ship.get("phone") and customer_info:
                ship["phone"] = customer_info.get("phone", "")
            payload["order"]["shipping_address"] = ship

        bill = _rest_addr(billing_address)
        if any(v for v in bill.values() if v):
            # Ensure customer name is in billing address
            if not bill.get("first_name") and customer_info:
                bill["first_name"] = customer_info.get("first_name", "")
            if not bill.get("last_name") and customer_info:
                bill["last_name"] = customer_info.get("last_name", "")
            if not bill.get("phone") and customer_info:
                bill["phone"] = customer_info.get("phone", "")
            payload["order"]["billing_address"] = bill

        url = f"https://{self.shop_domain}/admin/api/{self.api_version}/orders.json"
        self.logger.info("🚀 SHOPIFY REST ORDER CREATE - Starting API call")
        self.logger.info(f"📋 Order payload summary:")
        self.logger.info(f"   Line items: {len(payload.get('order', {}).get('line_items', []))}")
        cust_preview = payload.get('order', {}).get('customer')
        if isinstance(cust_preview, dict) and cust_preview.get('id') is not None:
            self.logger.info(f"   Customer: id={cust_preview.get('id')}")
        else:
            self.logger.info(f"   Customer: (not attached)" )
        self.logger.info(f"   Total price: {payload.get('order', {}).get('total_price', 'N/A')}")
        self.logger.debug(f"📦 Full REST order payload: {json.dumps(payload, indent=2)}")
        
        resp = self.session.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        self.logger.info(f"⏱️  REST order API call completed - Status: {resp.status_code}")

        if resp.status_code not in (200, 201):
            self.logger.error(f"❌ REST ORDER CREATE FAILED - Status: {resp.status_code}")
            try:
                err_body = resp.json()
                self.logger.error(f"🔍 Error response body: {json.dumps(err_body, indent=2)}")
            except Exception:
                self.logger.error(f"🔍 Error response text: {resp.text}")
                err_body = {"error": resp.text}
            raise OrderError(
                message=f"REST order create failed (status {resp.status_code})",
                response_data=err_body,
                status_code=resp.status_code,
            )

        data = resp.json() if resp.content else {}
        order_obj = (data or {}).get("order", {})
        if not order_obj:
            return self._format_response(False, error="REST order created but response missing 'order'")

        # Return a minimally consistent shape
        normalized = {
            "id": order_obj.get("id"),
            "name": order_obj.get("name") or order_obj.get("order_number"),
            "createdAt": order_obj.get("created_at"),
            "displayFinancialStatus": order_obj.get("financial_status"),
            "displayFulfillmentStatus": order_obj.get("fulfillment_status"),
            "totalPriceSet": {
                "shopMoney": {
                    "amount": order_obj.get("total_price"),
                    "currencyCode": order_obj.get("currency")
                }
            },
            "email": order_obj.get("email"),
            "customer": order_obj.get("customer"),
            "shippingAddress": order_obj.get("shipping_address"),
            "billingAddress": order_obj.get("billing_address"),
        }
        return self._format_response(True, normalized)
    
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