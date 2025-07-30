import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field
import uvicorn
from dotenv import load_dotenv
import asyncio
from contextlib import asynccontextmanager

from src.database import get_or_create_contact, log_message
from src.agent.core import chat_with_agent
from src.tools.ecla_whatsapp_tools import send_product_image, PRODUCT_IMAGES
from infobip_whatsapp_methods.client import WhatsAppClient
from src.config.settings import settings
from audio_transcriber.transcriber import transcribe_from_infobip_url
from image_processor.processor import process_image_from_url

# --- Configuration for Dynamic Worker Pool Scaling ---
MIN_WORKERS = 1
MAX_WORKERS = 10
BUSY_THRESHOLD = 5
CLEANUP_INTERVAL_SECONDS = 600
DEBOUNCE_SECONDS = 0.05

# --- Global State for the Worker Pool ---
GLOBAL_MESSAGE_QUEUE = asyncio.Queue()
WORKER_POOL: List[asyncio.Task] = []

# --- Global State for Debouncing ---
user_debounce_states: Dict[str, Dict[str, Any]] = {}

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Pydantic Models ---
class InboundMessageResult(BaseModel):
    message_id: str
    from_number: str
    to_number: str
    message_type: str
    text: Optional[str] = None
    contact_name: Optional[str] = None
    received_at: datetime

# --- Debouncing Logic ---
async def process_debounced_messages(user_id: str):
    """
    Waits for the debounce period, then processes all buffered messages for a user.
    """
    try:
        await asyncio.sleep(DEBOUNCE_SECONDS)

        state = user_debounce_states.get(user_id)
        if not state or not state.get('task'):
            logger.warning(f"Debounce task for {user_id} triggered but state is invalid.")
            return

        if not state['buffer']:
            logger.warning(f"Debounce task for {user_id} triggered with no messages.")
            # Clean up the task reference
            state['task'] = None
            return

        logger.info(f"⏰ Debounce timer expired for {user_id}. Processing {len(state['buffer'])} messages.")
        
        buffered_messages = state['buffer'].copy()  # Make a copy to avoid race conditions
        concatenated_text = " ".join([msg.text for msg in buffered_messages if msg.text]).strip()

        # Clear the buffer and task BEFORE processing to prevent re-processing
        state['buffer'] = []
        state['task'] = None

        if concatenated_text:
            last_message = buffered_messages[-1]
            combined_message = InboundMessageResult(
                message_id=last_message.message_id,
                from_number=last_message.from_number,
                to_number=last_message.to_number,
                message_type='text',
                text=concatenated_text,
                contact_name=last_message.contact_name,
                received_at=datetime.now()
            )
            await GLOBAL_MESSAGE_QUEUE.put(combined_message)
            logger.info(f"📬 Queued concatenated message for {user_id}: '{concatenated_text}'")
        else:
            logger.warning(f"No text content to process for user {user_id} after debouncing.")

    except asyncio.CancelledError:
        logger.info(f"Debounce task for {user_id} was cancelled.")
        # Clean up state when cancelled
        state = user_debounce_states.get(user_id)
        if state:
            state['task'] = None
    except Exception as e:
        logger.error(f"Error in debounce processing for {user_id}: {e}", exc_info=True)
        # Clean up state on error
        state = user_debounce_states.get(user_id)
        if state:
            state['buffer'] = []
            state['task'] = None


async def handle_incoming_message(message: InboundMessageResult):
    """
    Handles a new incoming message, managing the debouncing logic for the user.
    """
    user_id = message.from_number
    
    # Non-text messages (images, audio, etc.) are processed immediately
    if not message.text:
        logger.info(f"Message from {user_id} has no text, processing immediately.")
        await GLOBAL_MESSAGE_QUEUE.put(message)
        return

    # Initialize user state if it doesn't exist
    if user_id not in user_debounce_states:
        user_debounce_states[user_id] = {'buffer': [], 'task': None}
    
    state = user_debounce_states[user_id]

    # Cancel existing timer if it exists
    if state.get('task') and not state['task'].done():
        logger.info(f"🔄 Restarting debounce timer for {user_id}.")
        state['task'].cancel()
        try:
            await state['task']  # Wait for cancellation to complete
        except asyncio.CancelledError:
            pass

    # Add message to buffer
    state['buffer'].append(message)
    logger.info(f"📥 Message from {user_id} added to buffer. Buffer size: {len(state['buffer'])}")

    # Start new debounce timer
    logger.info(f"⏳ Starting {DEBOUNCE_SECONDS}-second debounce timer for {user_id}.")
    state['task'] = asyncio.create_task(process_debounced_messages(user_id))

# --- Cleanup function to prevent stale state ---
async def cleanup_stale_debounce_states():
    """
    Periodically clean up stale debouncing states to prevent phantom messages.
    """
    logger.info("🧼 Starting debounce state cleanup service.")
    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            
            current_time = datetime.now()
            stale_users = []
            
            for user_id, state in user_debounce_states.items():
                # Check if there's a task that's been running too long or is done
                if state.get('task'):
                    if state['task'].done():
                        logger.info(f"Cleaning up completed task for user {user_id}")
                        state['task'] = None
                        state['buffer'] = []
                        stale_users.append(user_id)
                
                # Clean up users with empty buffers and no active tasks
                elif not state['buffer'] and not state.get('task'):
                    stale_users.append(user_id)
            
            # Remove stale user states
            for user_id in stale_users:
                if user_id in user_debounce_states:
                    del user_debounce_states[user_id]
                    logger.info(f"Removed stale debounce state for user {user_id}")
                    
        except Exception as e:
            logger.error(f"Error in debounce cleanup: {e}", exc_info=True)

# --- Worker Logic ---
async def agent_worker(worker_id: int, client: WhatsAppClient):
    """
    A generic asynchronous worker that processes messages from the global queue.
    """
    logger.info(f"🚀 Starting agent worker #{worker_id}. Pool size: {len(WORKER_POOL)}")
    
    while True:
        try:
            message = await GLOBAL_MESSAGE_QUEUE.get()
            
            logger.info(f"Worker #{worker_id} processing message for {message.from_number}...")

            contact_id, thread_id = get_or_create_contact(message.from_number)
            if not contact_id:
                logger.error(f"Could not get or create contact for {message.from_number}")
                continue

            log_message(
                contact_id=contact_id, message_id=message.message_id, direction='incoming',
                message_type=message.message_type.lower(), content_text=message.text, status='received'
            )

            if not message.text:
                logger.warning(f"No text content to process for message {message.message_id}")
                continue

            # In a multi-tenant setup, you would determine the agent_id based on the
            # incoming message, for example, by mapping message.to_number to a specific agent.
            # For this example, we'll use the default agent.
            agent_id = "ecla_sales_agent"

            agent_response = chat_with_agent(
                message.text, 
                thread_id, 
                from_number=message.from_number,
                agent_id=agent_id
            )
            
            response_text = agent_response.get("response")
            if response_text:
                sent_message = client.send_text_message(message.from_number, response_text)
                if sent_message.success:
                    log_message(
                        contact_id=contact_id, message_id=sent_message.message_id, direction='outgoing',
                        message_type='text', content_text=response_text, status=sent_message.status
                    )

            tool_calls = agent_response.get("tool_calls", [])
            for tool_call in tool_calls:
                if tool_call.get("name") == "send_product_image":
                    args = tool_call.get("args", {})
                    product_name = args.get("product_name")
                    send_location = args.get("send_jounieh_location", False)
                    tool_config = {"metadata": {"from_number": message.from_number}}

                    if send_location:
                        sent_message_result = send_product_image.invoke(
                            {"send_jounieh_location": True}, config=tool_config
                        )
                        if sent_message_result.get("success"):
                            log_message(
                                contact_id=contact_id,
                                message_id=sent_message_result.get("message_id"),
                                direction='outgoing',
                                message_type='location',
                                content_text="Jounieh Location",
                                status=sent_message_result.get("status")
                            )
                    elif product_name:
                        sent_message_result = send_product_image.invoke(
                            {"product_name": product_name}, config=tool_config
                        )
                        if sent_message_result.get("success"):
                            log_message(
                                contact_id=contact_id,
                                message_id=sent_message_result.get("message_id"),
                                direction='outgoing',
                                message_type='image',
                                content_url=PRODUCT_IMAGES.get(product_name),
                                status=sent_message_result.get("status")
                            )

            GLOBAL_MESSAGE_QUEUE.task_done()

        except asyncio.CancelledError:
            logger.info(f"✅ Worker #{worker_id} has been gracefully terminated.")
            break
        except Exception as e:
            logger.error(f"💥 Unhandled exception in worker #{worker_id}: {e}", exc_info=True)

# --- Janitor Service for Scaling Down ---
async def scale_down_workers():
    """
    Periodically checks if the system is idle and scales down the worker pool.
    """
    logger.info("🧹 Janitor service for worker pool scaling started.")
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        
        if GLOBAL_MESSAGE_QUEUE.empty() and len(WORKER_POOL) > MIN_WORKERS:
            logger.info(f"System is idle and has {len(WORKER_POOL)} workers. Scaling down.")
            worker_to_terminate = WORKER_POOL.pop()
            worker_to_terminate.cancel()
            try:
                await worker_to_terminate
            except asyncio.CancelledError:
                pass  # Expected
            logger.info(f"Successfully terminated one worker. Pool size: {len(WORKER_POOL)}")

# --- FastAPI Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application's lifespan, starting up the worker pool and janitor.
    """
    client = WhatsAppClient(
        api_key=settings.infobip_api_key,
        base_url=settings.infobip_base_url,
        sender=settings.whatsapp_sender,
    )
    app.state.whatsapp_client = client

    # Start minimum number of workers
    for i in range(MIN_WORKERS):
        task = asyncio.create_task(agent_worker(i + 1, client))
        WORKER_POOL.append(task)
    
    # Start the janitor task
    janitor_task = asyncio.create_task(scale_down_workers())
    
    # Start the debounce state cleanup task
    cleanup_task = asyncio.create_task(cleanup_stale_debounce_states())
    
    yield
    
    # Clean up on shutdown
    logger.info("Shutting down application...")
    janitor_task.cancel()
    cleanup_task.cancel() # Cancel the cleanup task
    for task in WORKER_POOL:
        task.cancel()
    
    await asyncio.gather(janitor_task, cleanup_task, *WORKER_POOL, return_exceptions=True)
    logger.info("All workers and janitor service shut down.")

# --- Refactored Message Processing Logic ---
def _extract_message_data(result: Dict) -> Optional[InboundMessageResult]:
    try:
        message_id = result.get("messageId", "")
        from_number = result.get("from", "")
        to_number = result.get("to", "")
        message = result.get("message", {})
        message_type = message.get("type", "unknown").lower()
        text = message.get("text")
        media_url = message.get("url")
        contact = result.get("contact", {})
        contact_name = contact.get("name", "")

        if message_type == 'audio' and media_url:
            try:
                language, transcribed_text = transcribe_from_infobip_url(media_url)
                text = transcribed_text
                logger.info(f"Transcribed audio from {from_number} (lang: {language}): {text}")
            except Exception as e:
                logger.error(f"Failed to transcribe audio from {from_number}: {e}")
                text = "Failed to process audio."
        
        elif message_type == 'image' and media_url:
            try:
                analysis_result = process_image_from_url(media_url)
                text = analysis_result
                logger.info(f"Analyzed image from {from_number}: {text}")
            except Exception as e:
                logger.error(f"Failed to analyze image from {from_number}: {e}")
                text = "Failed to process image."

        return InboundMessageResult(
            message_id=message_id, from_number=from_number, to_number=to_number,
            message_type=message_type, text=text, contact_name=contact_name,
            received_at=datetime.now()
        )
    except Exception as e:
        logger.error(f"Error extracting message data: {e}")
        return None

def process_webhook_payload(payload: Dict[str, Any]) -> List[InboundMessageResult]:
    try:
        results = []
        if "results" in payload:
            for result in payload["results"]:
                message_data = _extract_message_data(result)
                if message_data:
                    results.append(message_data)
        return results
    except Exception as e:
        logger.error(f"Error processing webhook payload: {e}")
        return []

# --- FastAPI App and Endpoints ---
app = FastAPI(title="WhatsApp Message Fetcher", version="1.0.0", lifespan=lifespan)

@app.post("/webhook")
async def receive_whatsapp_message(request: Request):
    try:
        payload = await request.json()
        messages = process_webhook_payload(payload)

        for message in messages:
            await handle_incoming_message(message)

        # Scale-up logic
        if GLOBAL_MESSAGE_QUEUE.qsize() > BUSY_THRESHOLD and len(WORKER_POOL) < MAX_WORKERS:
            logger.info(f"Queue is busy (size: {GLOBAL_MESSAGE_QUEUE.qsize()}). Scaling up workers.")
            new_worker_id = len(WORKER_POOL) + 1
            new_task = asyncio.create_task(agent_worker(new_worker_id, app.state.whatsapp_client))
            WORKER_POOL.append(new_task)

        return {"status": "success", "processed_messages": len(messages)}

    except Exception as e:
        logger.error(f"Error in webhook endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred.")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "timestamp": datetime.now(),
        "active_workers": len(WORKER_POOL),
        "queued_messages": GLOBAL_MESSAGE_QUEUE.qsize()
    }

if __name__ == "__main__":
    uvicorn.run(
        "whatsapp_message_fetcher:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        proxy_headers=True,
        forwarded_allow_ips='*'
    ) 