import asyncio
import time
from typing import Dict, Any, List

# This simulates the shared state, mapping user_id to their specific state
user_states: Dict[str, Dict[str, Any]] = {}

async def process_concatenated_message(user_id: str, text: str):
    """Simulates the final processing step (e.g., calling the agent)."""
    print(f"[{time.time():.2f}] 🤖 AGENT PROCESSING for {user_id}: '{text}'")
    await asyncio.sleep(1)

async def handle_debounced_processing(user_id: str):
    """
    Waits for the debounce period, then processes all buffered messages.
    """
    debounce_period = 5
    await asyncio.sleep(debounce_period)
    
    state = user_states.get(user_id)
    if not state or not state['message_buffer']:
        return

    print(f"[{time.time():.2f}] ⏰ Debounce timer expired for {user_id}. Processing messages.")
    
    # Process and clear the buffer
    concatenated_text = " ".join(state['message_buffer'])
    state['message_buffer'] = []
    
    await process_concatenated_message(user_id, concatenated_text)

    state['debounce_task'] = None
    print(f"[{time.time():.2f}] ✨ Processing complete for {user_id}.")

async def message_arrival_handler(user_id: str, message: str):
    """
    Handles a new message arrival for a user, managing the debouncing logic.
    """
    if user_id not in user_states:
        user_states[user_id] = {"message_buffer": [], "debounce_task": None}
    
    state = user_states[user_id]
    
    # Cancel any existing debounce task
    if state.get('debounce_task'):
        print(f"[{time.time():.2f}] 🔄 Restarting debounce timer for {user_id}.")
        state['debounce_task'].cancel()

    # Add the new message to the buffer
    state['message_buffer'].append(message)
    print(f"[{time.time():.2f}] 📥 Message '{message}' added to buffer for {user_id}. Buffer: {state['message_buffer']}")

    # Start a new debounce task
    print(f"[{time.time():.2f}] ⏳ Starting 5-second debounce timer for {user_id}.")
    state['debounce_task'] = asyncio.create_task(handle_debounced_processing(user_id))

async def simulate_user_messages():
    """Simulates a user sending messages at different intervals."""
    user_id = "user_123"

    print("--- TEST CASE 1: Rapid Fire Messages ---")
    await message_arrival_handler(user_id, "Hello")
    await asyncio.sleep(1)
    await message_arrival_handler(user_id, "are you there?")
    await asyncio.sleep(2)
    await message_arrival_handler(user_id, "I have a question.")
    
    await asyncio.sleep(8)

    print("\n--- TEST CASE 2: Single Message ---")
    await message_arrival_handler(user_id, "Just one message.")
    
    await asyncio.sleep(8)

    print("\n--- TEST CASE 3: Messages with a long pause ---")
    await message_arrival_handler(user_id, "First message")
    await asyncio.sleep(7) # Pause is longer than debounce period
    await message_arrival_handler(user_id, "Second message")

    await asyncio.sleep(8)

async def main():
    """Main function to run the simulation."""
    await simulate_user_messages()
    print("\n--- Simulation finished ---")

if __name__ == "__main__":
    asyncio.run(main()) 