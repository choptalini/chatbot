#!/usr/bin/env python3
"""
Script to setup Shopify webhooks for product events using GraphQL API.
This script creates webhook subscriptions for product create, update, and delete events.
"""

import os
import sys
import json
from typing import Dict, Any, Optional, List
import logging
from dotenv import load_dotenv

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shopify_method import ShopifyClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# GraphQL mutation for creating webhook subscriptions
WEBHOOK_SUBSCRIPTION_MUTATION = """
mutation webhookSubscriptionCreate($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {
  webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {
    userErrors {
      field
      message
    }
    webhookSubscription {
      id
      topic
      format
      endpoint {
        __typename
        ... on WebhookHttpEndpoint {
          callbackUrl
        }
      }
    }
  }
}
"""

# GraphQL query to list existing webhooks
LIST_WEBHOOKS_QUERY = """
query {
  webhookSubscriptions(first: 50) {
    edges {
      node {
        id
        topic
        format
        endpoint {
          __typename
          ... on WebhookHttpEndpoint {
            callbackUrl
          }
        }
      }
    }
  }
}
"""

# GraphQL mutation to delete webhook subscription
DELETE_WEBHOOK_MUTATION = """
mutation webhookSubscriptionDelete($id: ID!) {
  webhookSubscriptionDelete(id: $id) {
    userErrors {
      field
      message
    }
    deletedWebhookSubscriptionId
  }
}
"""

class ShopifyWebhookManager:
    """Manager for Shopify webhook operations."""
    
    def __init__(self, webhook_url: str):
        """
        Initialize the webhook manager.
        
        Args:
            webhook_url: The public URL where webhooks will be sent
        """
        # Get Shopify credentials from environment
        self.shop_domain = os.getenv('SHOPIFY_SHOP_DOMAIN')
        self.access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        self.webhook_url = webhook_url
        
        if not self.shop_domain or not self.access_token:
            raise ValueError("Missing SHOPIFY_SHOP_DOMAIN or SHOPIFY_ACCESS_TOKEN in environment variables")
            
        # Initialize Shopify client
        self.client = ShopifyClient(
            shop_domain=self.shop_domain,
            access_token=self.access_token
        )
        
        # Product topics we want to subscribe to
        self.product_topics = [
            "PRODUCTS_CREATE",
            "PRODUCTS_UPDATE", 
            "PRODUCTS_DELETE"
        ]
        
        logger.info(f"Initialized webhook manager for {self.shop_domain}")
        logger.info(f"Webhook URL: {self.webhook_url}")
    
    def list_existing_webhooks(self) -> List[Dict[str, Any]]:
        """List all existing webhook subscriptions."""
        try:
            response = self.client._make_graphql_request(LIST_WEBHOOKS_QUERY)
            
            if 'errors' in response:
                logger.error(f"GraphQL errors: {response['errors']}")
                return []
            
            webhooks = []
            edges = response.get('data', {}).get('webhookSubscriptions', {}).get('edges', [])
            
            for edge in edges:
                node = edge.get('node', {})
                webhook_info = {
                    'id': node.get('id'),
                    'topic': node.get('topic'),
                    'format': node.get('format'),
                    'callback_url': None
                }
                
                endpoint = node.get('endpoint', {})
                if endpoint.get('__typename') == 'WebhookHttpEndpoint':
                    webhook_info['callback_url'] = endpoint.get('callbackUrl')
                
                webhooks.append(webhook_info)
            
            return webhooks
            
        except Exception as e:
            logger.error(f"Error listing webhooks: {e}")
            return []
    
    def get_webhook_stats(self) -> Dict[str, Any]:
        """
        Compute statistics about existing webhook subscriptions, including duplicates.
        
        Returns:
            Dict with counts grouped by topic and callback URL, and duplicate pairs.
        """
        try:
            webhooks = self.list_existing_webhooks()
            total = len(webhooks)

            by_topic: Dict[str, int] = {}
            by_callback: Dict[str, int] = {}
            pair_counts: Dict[str, int] = {}

            for wh in webhooks:
                topic = wh.get('topic') or 'UNKNOWN'
                cb = wh.get('callback_url') or 'NONE'
                by_topic[topic] = by_topic.get(topic, 0) + 1
                by_callback[cb] = by_callback.get(cb, 0) + 1
                key = f"{topic}@@{cb}"
                pair_counts[key] = pair_counts.get(key, 0) + 1

            duplicates: List[Dict[str, Any]] = []
            duplicate_count = 0
            for key, cnt in pair_counts.items():
                if cnt > 1:
                    topic, cb = key.split('@@', 1)
                    duplicates.append({
                        'topic': topic,
                        'callback_url': cb,
                        'count': cnt
                    })
                    duplicate_count += cnt - 1

            return {
                'total': total,
                'by_topic': by_topic,
                'by_callback_url': by_callback,
                'duplicate_pairs': duplicates,
                'duplicate_excess': duplicate_count,
            }
        except Exception as e:
            logger.error(f"Error computing webhook stats: {e}")
            return {
                'total': 0,
                'by_topic': {},
                'by_callback_url': {},
                'duplicate_pairs': [],
                'duplicate_excess': 0,
                'error': str(e),
            }
    
    def create_webhook_subscription(self, topic: str) -> Optional[Dict[str, Any]]:
        """
        Create a webhook subscription for the given topic.
        
        Args:
            topic: The webhook topic (e.g., "PRODUCTS_CREATE")
            
        Returns:
            Dict with subscription info if successful, None otherwise
        """
        try:
            variables = {
                "topic": topic,
                "webhookSubscription": {
                    "callbackUrl": self.webhook_url,
                    "format": "JSON"
                }
            }
            
            response = self.client._make_graphql_request(WEBHOOK_SUBSCRIPTION_MUTATION, variables)
            
            if 'errors' in response:
                logger.error(f"GraphQL errors creating webhook for {topic}: {response['errors']}")
                return None
            
            data = response.get('data', {}).get('webhookSubscriptionCreate', {})
            user_errors = data.get('userErrors', [])
            
            if user_errors:
                logger.error(f"User errors creating webhook for {topic}: {user_errors}")
                return None
            
            subscription = data.get('webhookSubscription')
            if subscription:
                logger.info(f"✅ Created webhook subscription for {topic}")
                logger.info(f"   ID: {subscription.get('id')}")
                logger.info(f"   Callback URL: {subscription.get('endpoint', {}).get('callbackUrl')}")
                return subscription
            else:
                logger.error(f"No subscription returned for {topic}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating webhook for {topic}: {e}")
            return None
    
    def delete_webhook_subscription(self, webhook_id: str) -> bool:
        """
        Delete a webhook subscription.
        
        Args:
            webhook_id: The webhook subscription ID
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            variables = {"id": webhook_id}
            
            response = self.client._make_graphql_request(DELETE_WEBHOOK_MUTATION, variables)
            
            if 'errors' in response:
                logger.error(f"GraphQL errors deleting webhook {webhook_id}: {response['errors']}")
                return False
            
            data = response.get('data', {}).get('webhookSubscriptionDelete', {})
            user_errors = data.get('userErrors', [])
            
            if user_errors:
                logger.error(f"User errors deleting webhook {webhook_id}: {user_errors}")
                return False
            
            deleted_id = data.get('deletedWebhookSubscriptionId')
            if deleted_id:
                logger.info(f"✅ Deleted webhook subscription: {deleted_id}")
                return True
            else:
                logger.error(f"Failed to delete webhook {webhook_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting webhook {webhook_id}: {e}")
            return False
    
    def setup_product_webhooks(self, replace_existing: bool = False) -> Dict[str, Any]:
        """
        Setup webhooks for all product events.
        
        Args:
            replace_existing: If True, delete existing webhooks for our URL first
            
        Returns:
            Dict with results summary
        """
        results = {
            'existing_webhooks': [],
            'deleted_webhooks': [],
            'created_webhooks': [],
            'failed_creations': [],
            'success': False
        }
        
        # List existing webhooks
        logger.info("📋 Listing existing webhooks...")
        existing_webhooks = self.list_existing_webhooks()
        results['existing_webhooks'] = existing_webhooks
        
        if existing_webhooks:
            logger.info(f"Found {len(existing_webhooks)} existing webhooks:")
            for webhook in existing_webhooks:
                logger.info(f"  - {webhook['topic']}: {webhook['callback_url']} (ID: {webhook['id']})")
        
        # Delete existing webhooks for our URL if requested
        if replace_existing:
            logger.info("🗑️ Deleting existing webhooks for our URL...")
            for webhook in existing_webhooks:
                if webhook['callback_url'] == self.webhook_url:
                    if self.delete_webhook_subscription(webhook['id']):
                        results['deleted_webhooks'].append(webhook)
        
        # Create new webhooks for product topics
        logger.info("🔗 Creating new webhook subscriptions...")
        for topic in self.product_topics:
            subscription = self.create_webhook_subscription(topic)
            if subscription:
                results['created_webhooks'].append(subscription)
            else:
                results['failed_creations'].append(topic)
        
        # Check if setup was successful
        results['success'] = (
            len(results['created_webhooks']) == len(self.product_topics) and
            len(results['failed_creations']) == 0
        )
        
        return results
    
    def cleanup_webhooks(self) -> Dict[str, Any]:
        """
        Remove all webhooks pointing to our URL.
        
        Returns:
            Dict with cleanup results
        """
        results = {
            'deleted_webhooks': [],
            'failed_deletions': [],
            'success': False
        }
        
        logger.info("🧹 Cleaning up webhooks for our URL...")
        existing_webhooks = self.list_existing_webhooks()
        
        for webhook in existing_webhooks:
            if webhook['callback_url'] == self.webhook_url:
                if self.delete_webhook_subscription(webhook['id']):
                    results['deleted_webhooks'].append(webhook)
                else:
                    results['failed_deletions'].append(webhook)
        
        results['success'] = len(results['failed_deletions']) == 0
        return results

    def prune_webhooks_by_callback_substring(self, substring: str) -> Dict[str, Any]:
        """
        Delete webhook subscriptions where the callback URL contains the given substring.
        
        Args:
            substring: A substring to match within the callback URL.
        
        Returns:
            Dict with deletion results.
        """
        results = {
            'matched_webhooks': [],
            'deleted_webhooks': [],
            'failed_deletions': [],
            'success': False
        }
        try:
            logger.info(f"🔍 Pruning webhooks where callback URL contains: '{substring}'")
            existing_webhooks = self.list_existing_webhooks()
            for webhook in existing_webhooks:
                cb = webhook.get('callback_url') or ''
                if substring in cb:
                    results['matched_webhooks'].append(webhook)
                    if self.delete_webhook_subscription(webhook['id']):
                        results['deleted_webhooks'].append(webhook)
                    else:
                        results['failed_deletions'].append(webhook)
            results['success'] = len(results['failed_deletions']) == 0
            return results
        except Exception as e:
            logger.error(f"Error pruning webhooks: {e}")
            results['error'] = str(e)
            return results


def main():
    """Main function to setup Shopify webhooks."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Setup Shopify product webhooks')
    parser.add_argument('--webhook-url', 
                       default='https://your-app.onrender.com/webhook/shopify',
                       help='The public URL for webhook callbacks')
    parser.add_argument('--action', 
                       choices=['setup', 'list', 'cleanup', 'stats', 'prune'], 
                       default='setup',
                       help='Action to perform')
    parser.add_argument('--prune-contains',
                       default='your-actual-render-app-url.onrender.com',
                       help='Substring to match in callback URLs for prune action')
    parser.add_argument('--replace', 
                       action='store_true',
                       help='Replace existing webhooks for the same URL')
    
    args = parser.parse_args()
    
    try:
        # Initialize webhook manager
        manager = ShopifyWebhookManager(args.webhook_url)
        
        if args.action == 'list':
            # Just list existing webhooks
            webhooks = manager.list_existing_webhooks()
            print(f"\nFound {len(webhooks)} existing webhooks:")
            for webhook in webhooks:
                print(f"  - {webhook['topic']}: {webhook['callback_url']}")
                print(f"    ID: {webhook['id']}")
        
        elif args.action == 'cleanup':
            # Clean up webhooks for our URL
            results = manager.cleanup_webhooks()
            
            print(f"\nCleanup Results:")
            print(f"  Deleted: {len(results['deleted_webhooks'])} webhooks")
            print(f"  Failed: {len(results['failed_deletions'])} webhooks")
            print(f"  Success: {results['success']}")
        
        elif args.action == 'setup':
            # Setup product webhooks
            results = manager.setup_product_webhooks(replace_existing=args.replace)
            
            print(f"\nSetup Results:")
            print(f"  Existing webhooks: {len(results['existing_webhooks'])}")
            print(f"  Deleted webhooks: {len(results['deleted_webhooks'])}")
            print(f"  Created webhooks: {len(results['created_webhooks'])}")
            print(f"  Failed creations: {len(results['failed_creations'])}")
            print(f"  Overall success: {results['success']}")
            
            if results['created_webhooks']:
                print(f"\n✅ Successfully created webhooks:")
                for webhook in results['created_webhooks']:
                    print(f"  - {webhook['topic']}: {webhook['id']}")
            
            if results['failed_creations']:
                print(f"\n❌ Failed to create webhooks for:")
                for topic in results['failed_creations']:
                    print(f"  - {topic}")
        
        elif args.action == 'stats':
            stats = manager.get_webhook_stats()
            
            print("\nWebhook Stats:")
            print(f"  Total subscriptions: {stats.get('total')}")
            print("  By topic:")
            for topic, count in (stats.get('by_topic') or {}).items():
                print(f"    - {topic}: {count}")
            print("  By callback URL:")
            for cb, count in (stats.get('by_callback_url') or {}).items():
                print(f"    - {cb}: {count}")
            dups = stats.get('duplicate_pairs') or []
            print(f"  Duplicate pairs (same topic+URL >1): {len(dups)}")
            for d in dups:
                print(f"    - {d['topic']} @ {d['callback_url']}: {d['count']}")
        
        elif args.action == 'prune':
            results = manager.prune_webhooks_by_callback_substring(args.prune_contains)
            print("\nPrune Results:")
            print(f"  Matched: {len(results['matched_webhooks'])}")
            print(f"  Deleted: {len(results['deleted_webhooks'])}")
            print(f"  Failed: {len(results['failed_deletions'])}")
            print(f"  Success: {results['success']}")
            if results.get('matched_webhooks'):
                print("\n  Matched webhooks:")
                for wh in results['matched_webhooks']:
                    print(f"    - {wh['topic']}: {wh['callback_url']} (ID: {wh['id']})")
        
        # Final summary
        print(f"\n📊 Summary:")
        print(f"  Shop: {manager.shop_domain}")
        print(f"  Webhook URL: {manager.webhook_url}")
        print(f"  Action: {args.action}")
        
    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()