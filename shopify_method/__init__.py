"""
Shopify Method Library - A comprehensive Python library for Shopify GraphQL API integration.

This library provides a unified interface for interacting with Shopify stores through 
the GraphQL Admin API, with special focus on AI agent integration.
"""

from .client import ShopifyClient
from .exceptions import (
    ShopifyAPIError,
    RateLimitError,
    PermissionError,
    AuthenticationError,
    ValidationError,
    ConnectionError as ShopifyConnectionError,
)

__version__ = "0.1.0"
__author__ = "ECLA Development Team"
__description__ = "A comprehensive Python library for Shopify GraphQL API integration"

__all__ = [
    "ShopifyClient",
    "ShopifyAPIError",
    "RateLimitError", 
    "PermissionError",
    "AuthenticationError",
    "ValidationError",
    "ShopifyConnectionError",
] 