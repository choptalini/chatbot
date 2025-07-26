#!/usr/bin/env python3
"""
WhatsApp Message Feed - Real-time feed using Server-Sent Events
Shows new messages as they arrive in real-time from the webhook
"""

import requests
import json
import time
from datetime import datetime

class WhatsAppRealtimeFeed:
    def __init__(self, webhook_url: str = "http://localhost:8000"):
        self.webhook_url = webhook_url
        self.stream_url = f"{webhook_url}/stream"
        
    def format_timestamp(self, timestamp: str) -> str:
        """Format timestamp for display"""
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime("%H:%M:%S")
        except:
            return timestamp
    
    def display_message(self, message_data):
        """Display a new message"""
        from_number = message_data.get('from_number', 'Unknown')
        text = message_data.get('text', 'No text')
        contact_name = message_data.get('contact_name', 'Unknown')
        timestamp = message_data.get('received_at', '')
        time_str = self.format_timestamp(timestamp)
        
        print(f"📱 [{time_str}] {contact_name} ({from_number}): {text}")
    
    def handle_sse_event(self, event_data):
        """Handle incoming Server-Sent Event"""
        try:
            data = json.loads(event_data)
            event_type = data.get('type')
            
            if event_type == 'new_message':
                message_data = data.get('data', {})
                self.display_message(message_data)
            elif event_type == 'heartbeat':
                # Optionally show heartbeat (commented out for cleaner output)
                # print("💓 Connection alive...")
                pass
            elif event_type == 'error':
                print(f"❌ Error: {data.get('message', 'Unknown error')}")
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse event data: {e}")
        except Exception as e:
            print(f"❌ Error handling event: {e}")
    
    def start_realtime_feed(self):
        """Start the real-time feed using Server-Sent Events"""
        print("🚀 WhatsApp Real-time Feed Started")
        print("=" * 60)
        print("📱 WhatsApp Number: 96179374241")
        print("💡 Send WhatsApp messages to see them appear here instantly!")
        print("🔗 Connected to real-time webhook stream")
        print("⏹️  Press Ctrl+C to stop")
        print("=" * 60)
        print("🔍 Waiting for messages...\n")
        
        retry_count = 0
        max_retries = 5
        
        while retry_count < max_retries:
            try:
                # Connect to the Server-Sent Events stream
                headers = {
                    'Accept': 'text/event-stream',
                    'Cache-Control': 'no-cache',
                }
                
                print(f"🔄 Connecting to {self.stream_url}...")
                
                with requests.get(self.stream_url, headers=headers, stream=True, timeout=None) as response:
                    if response.status_code == 200:
                        print("✅ Connected to real-time stream!\n")
                        retry_count = 0  # Reset retry count on successful connection
                        
                        for line in response.iter_lines(decode_unicode=True):
                            if line.startswith('data: '):
                                event_data = line[6:]  # Remove 'data: ' prefix
                                if event_data.strip():
                                    self.handle_sse_event(event_data)
                    else:
                        print(f"❌ Failed to connect: HTTP {response.status_code}")
                        retry_count += 1
                        
            except requests.exceptions.ConnectionError:
                retry_count += 1
                print(f"❌ Connection failed. Retrying in 5 seconds... (Attempt {retry_count}/{max_retries})")
                if retry_count >= max_retries:
                    print("❌ Max retries reached. Please check if the webhook server is running.")
                    break
                time.sleep(5)
                
            except KeyboardInterrupt:
                print("\n\n👋 Feed stopped. Goodbye!")
                break
                
            except Exception as e:
                retry_count += 1
                print(f"❌ Unexpected error: {e}")
                if retry_count >= max_retries:
                    print("❌ Max retries reached. Exiting.")
                    break
                print(f"🔄 Retrying in 5 seconds... (Attempt {retry_count}/{max_retries})")
                time.sleep(5)

def main():
    feed = WhatsAppRealtimeFeed()
    feed.start_realtime_feed()

if __name__ == "__main__":
    main() 