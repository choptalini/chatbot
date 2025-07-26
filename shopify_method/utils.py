"""
Utility functions for Shopify Method Library.

Provides helper functions for ID formatting, response processing, and data validation.
"""

import re
from typing import Union, Optional, Dict, Any, List
from .constants import GRAPHQL_ID_PREFIXES


def format_graphql_id(resource_type: str, resource_id: Union[str, int]) -> str:
    """
    Format a resource ID as a Shopify GraphQL Global ID.
    
    Args:
        resource_type (str): Type of resource (e.g., 'product', 'variant', 'order')
        resource_id (Union[str, int]): The numeric ID or existing GID
        
    Returns:
        str: Properly formatted GraphQL Global ID
        
    Examples:
        >>> format_graphql_id('product', 123)
        'gid://shopify/Product/123'
        >>> format_graphql_id('variant', 'gid://shopify/ProductVariant/456')
        'gid://shopify/ProductVariant/456'
    """
    if not resource_type or not resource_id:
        raise ValueError("Both resource_type and resource_id are required")
    
    # If it's already a GID, return as-is
    if isinstance(resource_id, str) and resource_id.startswith('gid://shopify/'):
        return resource_id
    
    # Convert to string and extract numeric part if needed
    id_str = str(resource_id)
    
    # Get the prefix for this resource type
    prefix = GRAPHQL_ID_PREFIXES.get(resource_type)
    if not prefix:
        raise ValueError(f"Unknown resource type: {resource_type}")
    
    return f"{prefix}{id_str}"


def extract_id_from_gid(gid: str) -> Optional[str]:
    """
    Extract the numeric ID from a Shopify GraphQL Global ID.
    
    Args:
        gid (str): Shopify GraphQL Global ID
        
    Returns:
        str: Numeric ID, or None if invalid GID
        
    Examples:
        >>> extract_id_from_gid('gid://shopify/Product/123')
        '123'
        >>> extract_id_from_gid('invalid')
        None
    """
    if not gid or not isinstance(gid, str):
        return None
    
    # Pattern to match Shopify GIDs
    pattern = r'gid://shopify/\w+/(\d+)'
    match = re.match(pattern, gid)
    
    if match:
        return match.group(1)
    return None


def extract_resource_type_from_gid(gid: str) -> Optional[str]:
    """
    Extract the resource type from a Shopify GraphQL Global ID.
    
    Args:
        gid (str): Shopify GraphQL Global ID
        
    Returns:
        str: Resource type, or None if invalid GID
        
    Examples:
        >>> extract_resource_type_from_gid('gid://shopify/Product/123')
        'Product'
        >>> extract_resource_type_from_gid('invalid')
        None
    """
    if not gid or not isinstance(gid, str):
        return None
    
    # Pattern to match Shopify GIDs
    pattern = r'gid://shopify/(\w+)/\d+'
    match = re.match(pattern, gid)
    
    if match:
        return match.group(1)
    return None


def validate_shop_domain(domain: str) -> bool:
    """
    Validate a Shopify shop domain format.
    
    Args:
        domain (str): Shop domain to validate
        
    Returns:
        bool: True if valid, False otherwise
        
    Examples:
        >>> validate_shop_domain('my-shop.myshopify.com')
        True
        >>> validate_shop_domain('invalid-domain')
        False
    """
    if not domain or not isinstance(domain, str):
        return False
    
    # Remove protocol if present
    domain = domain.replace('https://', '').replace('http://', '')
    
    # Pattern for valid Shopify domain
    pattern = r'^[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9]\.myshopify\.com$'
    return bool(re.match(pattern, domain))


def validate_email(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email (str): Email address to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not email or not isinstance(email, str):
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """
    Validate phone number format.
    
    Args:
        phone (str): Phone number to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not phone or not isinstance(phone, str):
        return False
    
    # Remove common formatting characters
    cleaned = re.sub(r'[\s\-\(\)\+\.]', '', phone)
    
    # Check if it's all digits and reasonable length
    return cleaned.isdigit() and 7 <= len(cleaned) <= 15


def extract_edges_nodes(graphql_response: Dict[str, Any], path: List[str]) -> List[Dict[str, Any]]:
    """
    Extract nodes from GraphQL edges structure.
    
    Args:
        graphql_response (Dict[str, Any]): GraphQL response data
        path (List[str]): Path to the edges field
        
    Returns:
        List[Dict[str, Any]]: List of node data
        
    Examples:
        >>> response = {'data': {'products': {'edges': [{'node': {'id': '1'}}]}}}
        >>> extract_edges_nodes(response, ['data', 'products'])
        [{'id': '1'}]
    """
    current = graphql_response
    
    # Navigate to the specified path
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return []
    
    # Extract nodes from edges
    if isinstance(current, dict) and 'edges' in current:
        edges = current['edges']
        if isinstance(edges, list):
            return [edge['node'] for edge in edges if isinstance(edge, dict) and 'node' in edge]
    
    return []


def format_money(amount: Union[str, float, int], currency: str = 'USD') -> str:
    """
    Format monetary amount for display.
    
    Args:
        amount (Union[str, float, int]): Amount to format
        currency (str): Currency code (default: 'USD')
        
    Returns:
        str: Formatted amount
        
    Examples:
        >>> format_money(123.45)
        '$123.45 USD'
        >>> format_money('99.99', 'CAD')
        '$99.99 CAD'
    """
    try:
        amount_float = float(amount)
        return f"${amount_float:.2f} {currency.upper()}"
    except (ValueError, TypeError):
        return f"${amount} {currency.upper()}"


def validate_inventory_quantity(quantity: Union[str, int]) -> bool:
    """
    Validate inventory quantity value.
    
    Args:
        quantity (Union[str, int]): Quantity to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        qty = int(quantity)
        return qty >= 0
    except (ValueError, TypeError):
        return False


def parse_graphql_errors(errors: List[Dict[str, Any]]) -> List[str]:
    """
    Parse GraphQL errors into human-readable messages.
    
    Args:
        errors (List[Dict[str, Any]]): List of GraphQL error objects
        
    Returns:
        List[str]: List of error messages
    """
    if not isinstance(errors, list):
        return []
    
    messages = []
    for error in errors:
        if isinstance(error, dict):
            message = error.get('message', str(error))
            # Add location information if available
            if 'locations' in error:
                locations = error['locations']
                if isinstance(locations, list) and locations:
                    loc = locations[0]
                    if isinstance(loc, dict) and 'line' in loc:
                        message += f" (line {loc['line']})"
            messages.append(message)
        else:
            messages.append(str(error))
    
    return messages


def validate_line_items(line_items: List[Dict[str, Any]]) -> bool:
    """
    Validate line items structure for orders.
    
    Args:
        line_items (List[Dict[str, Any]]): List of line items to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not isinstance(line_items, list) or not line_items:
        return False
    
    for item in line_items:
        if not isinstance(item, dict):
            return False
        
        # Check required fields
        if 'variantId' not in item and 'productId' not in item:
            return False
        
        # Validate quantity
        quantity = item.get('quantity', 1)
        if not validate_inventory_quantity(quantity):
            return False
    
    return True


def sanitize_search_query(query: str) -> str:
    """
    Sanitize search query for Shopify API.
    
    Args:
        query (str): Search query to sanitize
        
    Returns:
        str: Sanitized query
    """
    if not query or not isinstance(query, str):
        return ""
    
    # Remove potentially problematic characters
    sanitized = re.sub(r'[<>"\'\\\n\r\t]', '', query.strip())
    
    # Limit length
    return sanitized[:255]


def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split a list into chunks of specified size.
    
    Args:
        items (List[Any]): List to chunk
        chunk_size (int): Size of each chunk
        
    Returns:
        List[List[Any]]: List of chunks
    """
    if not isinstance(items, list) or chunk_size <= 0:
        return []
    
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)] 