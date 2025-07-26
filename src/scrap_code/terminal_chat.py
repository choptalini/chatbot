#!/usr/bin/env python3
"""
Simple terminal chat interface for testing the ECLA AI Customer Support Agent.
Allows interactive testing of the chatbot functionality.
"""

import os
import sys
import uuid
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Add src to path for imports
sys.path.append('src')

def print_banner():
    """Print welcome banner."""
    print("🦷 ECLA AI Customer Support Agent - Terminal Chat")
    print("=" * 50)
    print("Welcome! I'm here to help you with ECLA teeth whitening products.")
    print("Ask me about our products, pricing, usage instructions, or anything else!")
    print("Type 'exit', 'quit', or 'bye' to end the conversation.")
    print("Type 'help' for available commands.")
    print("=" * 50)

def print_help():
    """Print help information."""
    print("\n📋 Available Commands:")
    print("  help     - Show this help message")
    print("  clear    - Clear the screen")
    print("  stats    - Show agent statistics")
    print("  products - Show ECLA products")
    print("  exit     - Exit the chat")
    print("")

def print_products():
    """Print ECLA products information."""
    print("\n🦷 ECLA Products:")
    print("  1. ECLA® e20 Bionic⁺ Kit - $55.00 USD")
    print("     Professional LED whitening system")
    print("  2. ECLA® Purple Corrector - $26.00 USD")
    print("     Color correcting serum")
    print("  3. ECLA® Teeth Whitening Pen - $20.00 USD")
    print("     Portable whitening pen")
    print("")

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def setup_environment():
    """Setup basic environment variables if not already set."""
    # Set basic environment variables for testing
    if not os.getenv('OPENAI_API_KEY'):
        print("⚠️  OPENAI_API_KEY not set. Please set it in your environment or .env file.")
        return False
    
    if not os.getenv('DATABASE_URL'):
        # Use SQLite for testing if PostgreSQL not available
        os.environ['DATABASE_URL'] = 'sqlite:///./test_ecla_agent.db'
    
    if not os.getenv('CHROMA_PERSIST_DIRECTORY'):
        os.environ['CHROMA_PERSIST_DIRECTORY'] = './chroma_db'
    
    return True

def test_system_components():
    """Test system components before starting chat."""
    print("🔧 Testing system components...")
    
    try:
        # Test settings
        from src.config.settings import settings
        print("  ✅ Settings loaded")
        
        # Test knowledge base availability (will be initialized when first used)
        print("  📚 Knowledge base ready (will initialize on first use)")
        
        # Test tools
        from src.tools.rag_tool import rag_tool
        from src.tools.send_image_tool import send_image_tool
        print("  ✅ Tools loaded")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Component test failed: {e}")
        return False

def chat_with_agent_safe(message, thread_id):
    """Safely chat with agent with error handling."""
    try:
        from src.agent.core import chat_with_agent
        response = chat_with_agent(message, thread_id)
        return response
    except Exception as e:
        return {
            "response": f"❌ Error: {str(e)}. Please check your configuration.",
            "thread_id": thread_id,
            "error": True
        }

def format_response(response):
    """Format agent response for terminal display."""
    if response.get("error"):
        return f"🤖 Agent: {response['response']}"
    
    agent_response = response.get("response", "No response")
    
    # Check if tools were called
    tool_calls = response.get("tool_calls", [])
    if tool_calls:
        tools_used = ", ".join([tool.get("name", "Unknown") for tool in tool_calls])
        return f"🤖 Agent (used tools: {tools_used}): {agent_response}"
    
    return f"🤖 Agent: {agent_response}"

def main():
    """Main chat loop."""
    print_banner()
    
    # Setup environment
    if not setup_environment():
        print("❌ Environment setup failed. Please check your configuration.")
        return
    
    # Test system components
    if not test_system_components():
        print("❌ System component test failed. Some features may not work.")
        print("You can still try to chat, but expect errors.")
    
    # Generate unique thread ID for this session
    thread_id = str(uuid.uuid4())
    print(f"\n🆔 Session ID: {thread_id}")
    print("\nChat started! Type your message and press Enter:")
    
    message_count = 0
    
    try:
        while True:
            # Get user input
            try:
                user_input = input("\n👤 You: ").strip()
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            
            if not user_input:
                continue
            
            # Handle special commands
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("\n👋 Thank you for using ECLA AI Customer Support! Goodbye!")
                break
            
            elif user_input.lower() == 'help':
                print_help()
                continue
            
            elif user_input.lower() == 'clear':
                clear_screen()
                print_banner()
                continue
            
            elif user_input.lower() == 'products':
                print_products()
                continue
            
            elif user_input.lower() == 'stats':
                try:
                    from src.agent.core import get_agent
                    agent = get_agent()
                    stats = agent.get_stats()
                    print(f"\n📊 Agent Statistics:")
                    print(f"  Model: {stats.get('model_name', 'Unknown')}")
                    print(f"  Temperature: {stats.get('temperature', 'Unknown')}")
                    print(f"  Tools: {stats.get('tools_count', 0)}")
                    print(f"  Session Messages: {message_count}")
                    print("")
                except Exception as e:
                    print(f"❌ Could not get stats: {e}")
                continue
            
            # Process user message
            print("🤔 Agent is thinking...")
            
            start_time = datetime.now()
            response = chat_with_agent_safe(user_input, thread_id)
            end_time = datetime.now()
            
            # Display response
            print(format_response(response))
            
            # Show response time
            response_time = (end_time - start_time).total_seconds()
            print(f"⏱️  Response time: {response_time:.2f}s")
            
            message_count += 1
            
            # Show hint after first message
            if message_count == 1:
                print("\n💡 Tip: Try asking about 'ECLA products', 'pricing', or 'show me the e20 kit image'")
    
    except Exception as e:
        print(f"\n❌ Chat error: {e}")
        print("Please check your configuration and try again.")
    
    finally:
        print(f"\n📊 Session Summary:")
        print(f"  Messages exchanged: {message_count}")
        print(f"  Session ID: {thread_id}")
        print("  Thank you for using ECLA AI Customer Support!")

if __name__ == "__main__":
    main() 