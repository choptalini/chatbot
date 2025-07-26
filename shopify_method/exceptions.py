"""
Custom exception classes for Shopify Method Library.

Provides specific exception types for different error scenarios when interacting
with the Shopify GraphQL Admin API.
"""

from typing import Dict, Any, Optional


class ShopifyAPIError(Exception):
    """Base exception for all Shopify API related errors."""
    
    def __init__(self, message: str, response_data: Optional[Dict[str, Any]] = None, 
                 status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.response_data = response_data or {}
        self.status_code = status_code
        
    def __str__(self):
        return f"ShopifyAPIError: {self.message}"


class RateLimitError(ShopifyAPIError):
    """Raised when API rate limits are exceeded."""
    
    def __init__(self, message: str = "API rate limit exceeded", 
                 retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after
        
    def __str__(self):
        base_msg = f"RateLimitError: {self.message}"
        if self.retry_after:
            base_msg += f" (retry after {self.retry_after}s)"
        return base_msg


class PermissionError(ShopifyAPIError):
    """Raised when the app lacks required permissions for an operation."""
    
    def __init__(self, message: str = "Insufficient permissions", 
                 required_scope: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.required_scope = required_scope
        
    def __str__(self):
        base_msg = f"PermissionError: {self.message}"
        if self.required_scope:
            base_msg += f" (requires: {self.required_scope})"
        return base_msg


class AuthenticationError(ShopifyAPIError):
    """Raised when authentication fails (invalid token, expired, etc.)."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, **kwargs)
        
    def __str__(self):
        return f"AuthenticationError: {self.message}"


class ValidationError(ShopifyAPIError):
    """Raised when input validation fails."""
    
    def __init__(self, message: str = "Validation failed", 
                 field: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.field = field
        
    def __str__(self):
        base_msg = f"ValidationError: {self.message}"
        if self.field:
            base_msg += f" (field: {self.field})"
        return base_msg


class ConnectionError(ShopifyAPIError):
    """Raised when connection to Shopify API fails."""
    
    def __init__(self, message: str = "Connection failed", **kwargs):
        super().__init__(message, **kwargs)
        
    def __str__(self):
        return f"ConnectionError: {self.message}"


class GraphQLError(ShopifyAPIError):
    """Raised when GraphQL query/mutation contains errors."""
    
    def __init__(self, message: str = "GraphQL error", 
                 errors: Optional[list] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.errors = errors or []
        
    def __str__(self):
        base_msg = f"GraphQLError: {self.message}"
        if self.errors:
            error_details = "; ".join([str(err) for err in self.errors])
            base_msg += f" (Details: {error_details})"
        return base_msg


class InventoryError(ShopifyAPIError):
    """Raised when inventory operations fail."""
    
    def __init__(self, message: str = "Inventory operation failed", 
                 variant_id: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.variant_id = variant_id
        
    def __str__(self):
        base_msg = f"InventoryError: {self.message}"
        if self.variant_id:
            base_msg += f" (variant: {self.variant_id})"
        return base_msg


class OrderError(ShopifyAPIError):
    """Raised when order operations fail."""
    
    def __init__(self, message: str = "Order operation failed", 
                 order_id: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.order_id = order_id
        
    def __str__(self):
        base_msg = f"OrderError: {self.message}"
        if self.order_id:
            base_msg += f" (order: {self.order_id})"
        return base_msg 