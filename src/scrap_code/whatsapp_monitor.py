#!/usr/bin/env python3
"""
Real-time WhatsApp Message Monitor
Displays incoming messages in your terminal as they arrive
"""

import requests
import json
import time
import os
from datetime import datetime
from typing import Dict, List, Optional

class WhatsAppMonitor:
    def __init__(self, webhook_url: str = "http://localhost:8000"):
        self.webhook_url = webhook_url
        self.last_message_id = None
        self.seen_messages = set()
        
    def clear_screen(self):
        """Clear the terminal screen"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def format_timestamp(self, timestamp: str) -> str:
        """Format timestamp for display"""
        try:
            # Parse ISO timestamp
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime("%H:%M:%S")
        except:
            return timestamp
    
    def format_message(self, message: Dict) -> str:
        """Format a message for display"""
        msg_id = message.get('messageId', 'N/A')
        from_number = message.get('from', 'Unknown')
        to_number = message.get('to', 'Unknown')
        
        # Get message content
        msg_content = message.get('message', {})
        if isinstance(msg_content, dict):
            text = msg_content.get('text', 'No text')
            msg_type = msg_content.get('type', 'text')
        else:
            text = str(msg_content)
            msg_type = 'text'
        
        # Get contact name
        contact = message.get('contact', {})
        if isinstance(contact, dict):
            contact_name = contact.get('name', 'Unknown')
        else:
            contact_name = 'Unknown'
        
        # Get timestamp
        timestamp = message.get('stored_at', message.get('receivedAt', ''))
        time_str = self.format_timestamp(timestamp)
        
        # Format the message
        return f"""
┌─────────────────────────────────────────────────────────────────
│ 📱 New WhatsApp Message [{time_str}]
├─────────────────────────────────────────────────────────────────
│ From: {contact_name} ({from_number})
│ To: {to_number}
│ Type: {msg_type}
│ Message: {text}
│ ID: {msg_id}
└─────────────────────────────────────────────────────────────────
"""
    
    def get_messages(self) -> Optional[List[Dict]]:
        """Fetch messages from the webhook server"""
        try:
            response = requests.get(f"{self.webhook_url}/messages", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('messages', [])
            else:
                print(f"❌ Error fetching messages: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return None
    
    def check_server_health(self) -> bool:
        """Check if the webhook server is running"""
        try:
            response = requests.get(f"{self.webhook_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def display_header(self, total_messages: int):
        """Display the monitor header"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("=" * 80)
        print("🚀 WhatsApp Message Monitor - Real-time Incoming Messages")
        print("=" * 80)
        print(f"📊 Total Messages: {total_messages}")
        print(f"⏰ Last Updated: {current_time}")
        print(f"🔗 Webhook URL: {self.webhook_url}")
        print(f"📱 WhatsApp Number: 96179374241")
        print("=" * 80)
        print("💡 Send a WhatsApp message to 96179374241 to see it appear here!")
        print("=" * 80)
    
    def monitor_messages(self, refresh_interval: int = 3):
        """Monitor messages in real-time"""
        print("🚀 Starting WhatsApp Message Monitor...")
        print("💡 Press Ctrl+C to stop monitoring")
        print()
        
        # Check server health
        if not self.check_server_health():
            print("❌ Webhook server is not running!")
            print("💡 Please start the server with: python whatsapp_message_fetcher.py")
            return
        
        try:
            while True:
                # Get current messages
                messages = self.get_messages()
                
                if messages is None:
                    time.sleep(refresh_interval)
                    continue
                
                # Clear screen and show header
                self.clear_screen()
                self.display_header(len(messages))
                
                # Show recent messages (last 10)
                recent_messages = messages[:10]
                
                if recent_messages:
                    print("\n📨 Recent Messages:")
                    for i, message in enumerate(recent_messages, 1):
                        msg_id = message.get('messageId', '')
                        
                        # Check if this is a new message
                        is_new = msg_id not in self.seen_messages
                        if is_new:
                            self.seen_messages.add(msg_id)
                            print(f"🆕 {self.format_message(message)}")
                        else:
                            # Show older messages with less emphasis
                            from_number = message.get('from', 'Unknown')
                            text = message.get('message', {}).get('text', 'No text')
                            timestamp = message.get('stored_at', '')
                            time_str = self.format_timestamp(timestamp)
                            print(f"    {i}. [{time_str}] {from_number}: {text}")
                else:
                    print("\n📭 No messages yet. Send a WhatsApp message to 96179374241 to test!")
                
                print(f"\n🔄 Refreshing every {refresh_interval} seconds... (Ctrl+C to stop)")
                time.sleep(refresh_interval)
                
        except KeyboardInterrupt:
            print("\n\n👋 Stopping monitor. Goodbye!")
        except Exception as e:
            print(f"\n❌ Error in monitor: {e}")

def main():
    """Main function"""
    print("🚀 WhatsApp Message Monitor")
    print("=" * 50)
    
    # Initialize monitor
    monitor = WhatsAppMonitor()
    
    # Start monitoring
    monitor.monitor_messages(refresh_interval=3)

if __name__ == "__main__":
    main() 