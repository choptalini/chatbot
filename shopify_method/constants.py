"""
Constants and configurations for Shopify Method Library.
"""

# API Configuration
DEFAULT_API_VERSION = "2024-10"
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1  # seconds
REQUEST_TIMEOUT = 30  # seconds
MAX_BULK_OPERATIONS = 100

# GraphQL Query Templates
SHOP_INFO_QUERY = """
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
}
"""

PRODUCT_INVENTORY_QUERY = """
query getProductInventory($id: ID!) {
    productVariant(id: $id) {
        id
        title
        inventoryItem {
            id
            inventoryLevels(first: 5) {
                edges {
                    node {
                        id
                        quantities(names: ["available"]) {
                            quantity
                            name
                        }
                        location {
                            id
                            name
                        }
                    }
                }
            }
        }
        product {
            title
        }
    }
}
"""

PRODUCT_DETAILS_QUERY = """
query getProduct($id: ID!) {
    product(id: $id) {
        id
        title
        handle
        description
        vendor
        productType
        tags
        status
        createdAt
        updatedAt
        variants(first: 10) {
            edges {
                node {
                    id
                    title
                    price
                    compareAtPrice
                    sku
                    barcode
                    inventoryQuantity
                }
            }
        }
        images(first: 5) {
            edges {
                node {
                    id
                    src
                    altText
                }
            }
        }
    }
}
"""

PRODUCTS_LIST_QUERY = """
query getProducts($first: Int!, $query: String) {
    products(first: $first, query: $query) {
        edges {
            node {
                id
                title
                handle
                status
                vendor
                productType
                createdAt
                variants(first: 3) {
                    edges {
                        node {
                            id
                            title
                            price
                            inventoryQuantity
                        }
                    }
                }
            }
        }
        pageInfo {
            hasNextPage
            hasPreviousPage
        }
    }
}
"""

# Rich product listing query with expanded fields (variants, images, options)
PRODUCTS_FULL_LIST_QUERY = """
query getProductsFull($first: Int!, $query: String) {
    products(first: $first, query: $query) {
        edges {
            node {
                id
                title
                handle
                description
                vendor
                productType
                tags
                status
                createdAt
                updatedAt
                options {
                    id
                    name
                    values
                }
                images(first: 50) {
                    edges {
                        node {
                            id
                            src
                            altText
                        }
                    }
                }
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
                            image {
                                id
                                src
                                altText
                            }
                            inventoryItem { id }
                        }
                    }
                }
            }
        }
        pageInfo {
            hasNextPage
            hasPreviousPage
        }
    }
}
"""

INVENTORY_ADJUST_MUTATION = """
mutation inventoryAdjustQuantities($input: InventoryAdjustQuantitiesInput!) {
    inventoryAdjustQuantities(input: $input) {
        inventoryAdjustmentGroup {
            reason
            changes {
                delta
                quantityAfterChange
                item {
                    id
                }
                location {
                    id
                    name
                }
            }
        }
        userErrors {
            field
            message
        }
    }
}
"""

DRAFT_ORDER_CREATE_MUTATION = """
mutation draftOrderCreate($input: DraftOrderInput!) {
    draftOrderCreate(input: $input) {
        draftOrder {
            id
            name
            status
            totalPrice
            createdAt
            lineItems(first: 10) {
                edges {
                    node {
                        id
                        title
                        quantity
                        variant {
                            id
                            title
                        }
                    }
                }
            }
        }
        userErrors {
            field
            message
        }
    }
}
"""

ORDER_CREATE_MUTATION = """
mutation orderCreate($order: OrderCreateOrderInput!, $options: OrderCreateOptionsInput) {
    orderCreate(order: $order, options: $options) {
        order {
            id
            name
            createdAt
            displayFinancialStatus
            displayFulfillmentStatus
            totalPriceSet {
                shopMoney { amount currencyCode }
            }
            email
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
            billingAddress {
                firstName
                lastName
                address1
                address2
                city
                province
                country
                zip
            }
            lineItems(first: 10) {
                edges {
                    node {
                        id
                        title
                        quantity
                        originalUnitPriceSet { shopMoney { amount currencyCode } }
                        variant { id title }
                        taxLines {
                            title
                            rate
                            priceSet { shopMoney { amount currencyCode } }
                        }
                    }
                }
            }
        }
        userErrors {
            field
            message
        }
    }
}
"""

CUSTOMER_CREATE_MUTATION = """
mutation customerCreate($input: CustomerInput!) {
    customerCreate(input: $input) {
        customer {
            id
            firstName
            lastName
            email
            phone
            createdAt
        }
        userErrors {
            field
            message
        }
    }
}
"""

CUSTOMER_QUERY = """
query getCustomer($id: ID!) {
    customer(id: $id) {
        id
        firstName
        lastName
        email
        phone
        createdAt
        updatedAt
        addresses {
            id
            firstName
            lastName
            address1
            address2
            city
            province
            country
            zip
        }
        orders(first: 5) {
            edges {
                node {
                    id
                    name
                    totalPrice
                    createdAt
                }
            }
        }
    }
}
"""

LOCATIONS_QUERY = """
query getLocations {
    locations(first: 20) {
        edges {
            node {
                id
                name
                address {
                    address1
                    address2
                    city
                    province
                    country
                    zip
                }
                fulfillsOnlineOrders
                hasActiveInventory
            }
        }
    }
}
"""

# Shopify GraphQL ID prefixes
GRAPHQL_ID_PREFIXES = {
    'product': 'gid://shopify/Product/',
    'variant': 'gid://shopify/ProductVariant/',
    'order': 'gid://shopify/Order/',
    'draft_order': 'gid://shopify/DraftOrder/',
    'customer': 'gid://shopify/Customer/',
    'location': 'gid://shopify/Location/',
    'inventory_item': 'gid://shopify/InventoryItem/',
    'inventory_level': 'gid://shopify/InventoryLevel/',
}

# Common error messages
ERROR_MESSAGES = {
    'invalid_id': 'Invalid ID format provided',
    'not_found': 'Resource not found',
    'permission_denied': 'Insufficient permissions for this operation',
    'validation_failed': 'Input validation failed',
    'rate_limited': 'API rate limit exceeded',
    'connection_failed': 'Failed to connect to Shopify API',
}

# Inventory reasons
INVENTORY_REASONS = {
    'correction': 'correction',
    'cycle_count': 'cycle_count_available',
    'damaged': 'damaged',
    'movement_created': 'movement_created',
    'movement_updated': 'movement_updated',
    'movement_received': 'movement_received',
    'movement_canceled': 'movement_canceled',
    'other': 'other',
    'promotion': 'promotion',
    'quality_control': 'quality_control',
    'received': 'received',
    'reservation_created': 'reservation_created',
    'reservation_deleted': 'reservation_deleted',
    'reservation_updated': 'reservation_updated',
    'restock': 'restock',
    'safety_stock': 'safety_stock',
    'shrinkage': 'shrinkage',
} 