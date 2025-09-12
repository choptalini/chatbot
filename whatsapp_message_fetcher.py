"""
Multi-Tenant WhatsApp Message Fetcher for SwiftReplies.ai
Updated version that supports the new multi-tenant database architecture
"""

import asyncio
import logging
import os
import time
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from infobip_whatsapp_methods.client import WhatsAppClient
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import functools

# Import our new multi-tenant database module
from src.multi_tenant_database import (
    db, get_user_by_phone_number, track_message_usage, 
    check_message_limits, create_action_request
)
from src.agent.core import chat_with_agent
from src.tools.ecla_whatsapp_tools import send_product_image, PRODUCT_IMAGES
from src.astrosouks_tools.astrosouks_whatsapp_tools import astrosouks_send_product_image
from src.config.settings import settings
from src.analytics import analytics_processor
from audio_transcriber.transcriber import transcribe_from_infobip_url
from image_processor.processor import process_image_from_url
from src.supabase_storage import upload_media_to_supabase
from src.agent.core import set_thread_instructions_for_thread
from src.geocoding import reverse_geocode as reverse_geocode_location, directions_links as maps_directions_links
from src.multi_tenant_config import MultiTenantConfig

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
MIN_WORKERS = 1
MAX_WORKERS = 10
BUSY_THRESHOLD = 5
CLEANUP_INTERVAL_SECONDS = 600
DEBOUNCE_SECONDS = 0.01

# Shopify OAuth/webhook configuration removed per request

# --- Global State ---
user_debounce_states: Dict[str, Dict] = {}
GLOBAL_MESSAGE_QUEUE = asyncio.Queue()
WORKER_POOL = []
MANUAL_MESSAGE_LISTENER_TASK = None

# Per-user async locks to protect debounce state from race conditions
user_state_locks: Dict[str, asyncio.Lock] = {}

def _get_user_lock(user_id: str) -> asyncio.Lock:
    lock = user_state_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        user_state_locks[user_id] = lock
    return lock

class InboundMessageResult(BaseModel):
    message_id: str
    from_number: str
    to_number: str
    message_type: str
    text: Optional[str] = None
    contact_name: Optional[str] = None
    content_url: Optional[str] = None
    received_at: datetime
    # Internal retry counter for transient worker failures
    retries: int = 0
    # Optional location enrichments
    location_latitude: Optional[float] = None
    location_longitude: Optional[float] = None
    location_details: Optional[Dict[str, Any]] = None

async def process_debounced_messages(user_id: str):
    """
    Processes all buffered messages for a user after the debounce period.
    Updated for multi-tenant support.
    """
    try:
        # Wait for the debounce period
        await asyncio.sleep(DEBOUNCE_SECONDS)
        
        # Snapshot and clear buffer under lock to avoid races
        lock = _get_user_lock(user_id)
        async with lock:
            state = user_debounce_states.get(user_id)
            if not state:
                logger.warning(f"No debounce state found for {user_id}")
                return

            buffered_messages: List[InboundMessageResult] = list(state.get('buffer', []))
            state['buffer'] = []
            state['task'] = None

        if not buffered_messages:
            logger.info(f"No messages to process for {user_id}")
            return

        logger.info(f"⚡ Processing {len(buffered_messages)} debounced message(s) for {user_id}")

        # Combine all message texts
        combined_text = "\n".join([msg.text for msg in buffered_messages if msg.text])

        if combined_text:
            # Prefer a media message as template to preserve media metadata for storage upload
            media_types = {"image", "audio", "video", "document"}
            template = next((m for m in buffered_messages if (m.message_type or "").lower() in media_types and m.content_url), buffered_messages[0])
            # Create a fresh message object to avoid mutating original references
            representative_message = InboundMessageResult(
                message_id=template.message_id,
                from_number=template.from_number,
                to_number=template.to_number,
                message_type=template.message_type,  # preserve original type so media handling works
                text=combined_text,
                contact_name=template.contact_name,
                content_url=template.content_url,
                received_at=datetime.now(),
            )

            # Add to global queue for processing
            await GLOBAL_MESSAGE_QUEUE.put(representative_message)

    except asyncio.CancelledError:
        logger.info(f"Debounce processing cancelled for {user_id}")
    except Exception as e:
        logger.error(f"Error in process_debounced_messages for {user_id}: {e}", exc_info=True)
        
        # Clean up state on error
        if user_id in user_debounce_states:
            state = user_debounce_states[user_id]
            state['buffer'] = []
            state['task'] = None

async def handle_incoming_message(message: InboundMessageResult):
    """
    Handles a new incoming message with multi-tenant awareness.
    Updated to support user identification via phone number.
    """
    user_id = message.from_number
    
    # Non-text messages (images, audio, etc.) are processed immediately
    if not message.text:
        logger.info(f"Message from {user_id} has no text, processing immediately.")
        await GLOBAL_MESSAGE_QUEUE.put(message)
        return

    # Protect per-user debounce state with a lock
    lock = _get_user_lock(user_id)
    async with lock:
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

async def cleanup_stale_debounce_states():
    """Clean up stale debounce states periodically."""
    logger.info("🧼 Starting debounce state cleanup service.")
    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            current_time = time.time()
            stale_users = []
            
            for user_id, state in user_debounce_states.items():
                task = state.get('task')
                if task and task.done():
                    stale_users.append(user_id)
            
            for user_id in stale_users:
                del user_debounce_states[user_id]
                logger.info(f"🧹 Cleaned up stale state for {user_id}")
                
        except Exception as e:
            logger.error(f"Error in debounce cleanup: {e}", exc_info=True)

async def agent_worker(worker_id: int, clients: Dict[str, WhatsAppClient]):
    """
    Updated agent worker with multi-tenant support and usage tracking.
    """
    logger.info(f"🚀 Starting multi-tenant agent worker #{worker_id}")
    
    while True:
        message: Optional[InboundMessageResult] = None
        try:
            message = await GLOBAL_MESSAGE_QUEUE.get()
            logger.info(f"Worker #{worker_id} processing message for {message.from_number}...")

            # 1. Determine routing (prefer destination-based using multi-tenant configuration)
            routing = MultiTenantConfig.get_routing_for_destination(getattr(message, 'to_number', None))
            if routing:
                user_id = routing['user_id']
                chatbot_id = routing['chatbot_id']
                agent_id = routing.get('agent_id', 'ecla_sales_agent')  # Default fallback
                logger.info(f"Destination-based routing: to_number={message.to_number} -> user_id={user_id}, chatbot_id={chatbot_id}, agent_id={agent_id}")
            else:
                # Fallback: legacy mapping by customer phone number
                user_info = get_user_by_phone_number(message.from_number)
                user_id = user_info['user_id']
                chatbot_id = user_info['chatbot_id']
                # Determine agent based on chatbot_id
                agent_id = "astrosouks_sales_agent" if chatbot_id == 3 else "ecla_sales_agent"
                logger.info(f"Legacy phone-based routing: from_number={message.from_number} -> user_id={user_id}, chatbot_id={chatbot_id}, agent_id={agent_id}")
            
            logger.info(f"Final routing: user_id={user_id}, chatbot_id={chatbot_id}, agent_id={agent_id}")
            
            # Select appropriate WhatsApp client based on routing
            if chatbot_id == 3:  # AstroSouks
                client = clients.get('astrosouks', clients.get('ecla'))  # Fallback to ecla if astrosouks not available
                logger.info(f"Using AstroSouks WhatsApp client for chatbot_id={chatbot_id}")
            else:  # ECLA/SwiftReplies
                client = clients.get('ecla')
                logger.info(f"Using ECLA WhatsApp client for chatbot_id={chatbot_id}")
            
            # 2. Check usage limits before processing
            usage_check = await asyncio.to_thread(check_message_limits, user_id)
            if not usage_check['within_limits']:
                logger.warning(f"User {user_id} has exceeded usage limits")
                
                # Send limit exceeded message
                limit_message = "⚠️ You've reached your daily message limit. Please upgrade your plan or try again tomorrow."
                try:
                    await asyncio.to_thread(client.send_text_message, message.from_number, limit_message)
                except Exception as e:
                    logger.error(f"Failed to send limit exceeded message: {e}")
                continue
            
            # 3. Get or create contact (now user-aware)
            contact_id, thread_id = await asyncio.to_thread(
                db.get_or_create_contact, message.from_number, user_id, message.contact_name
            )
            if not contact_id:
                logger.error(f"Could not get or create contact for {message.from_number}")
                continue

            # 4. Upload media (if any) to Supabase Storage to obtain public URL
            media_public_url = message.content_url
            if message.message_type.lower() in { 'image', 'audio', 'video', 'document' } and message.content_url:
                try:
                    # Use synchronous upload (previous reliable behavior) for maximum compatibility
                    media_public_url = upload_media_to_supabase(
                        message.content_url,
                        user_id=user_id,
                        contact_id=contact_id,
                        message_id=message.message_id,
                        message_type=message.message_type.lower(),
                    ) or message.content_url
                    if media_public_url and media_public_url != message.content_url:
                        logger.info(f"📦 Stored media for {message.message_type} to Supabase: {media_public_url}")
                except Exception as e:
                    logger.warning(f"Media upload to storage failed: {e}")

            # 5. Log incoming message (now with chatbot_id). For location, store metadata
            incoming_metadata = None
            if (message.message_type or '').lower() == 'location':
                incoming_metadata = {
                    "location": {
                        "latitude": message.location_latitude,
                        "longitude": message.location_longitude,
                        **(message.location_details or {}),
                    }
                }

            await asyncio.to_thread(
                db.log_message,
                contact_id,
                message.message_id,
                'incoming',
                message.message_type.lower(),
                chatbot_id,
                # Save analysis/transcription/geocoded summary for agent processing
                message.text,
                media_public_url if message.message_type.lower() in { 'image', 'audio', 'video', 'document' } else None,
                'received',
                incoming_metadata,
                False,
                None,
                None,
            )
            
            # 5. Update contact interaction timestamp
            await asyncio.to_thread(db.update_contact_interaction, contact_id)

            # Proceed to AI processing even for media (image/audio) if we have analysis/transcription text
            if not message.text:
                logger.warning(f"No text content to process for message {message.message_id}")
                continue

            # 6. Check if conversation is paused before AI processing
            is_paused = await asyncio.to_thread(db.is_conversation_paused, contact_id)
            if is_paused:
                logger.info(f"Conversation is paused for contact {contact_id} - skipping AI processing")
                # Message is already logged above with ai_processed=False
                continue

            # 7. Process with AI agent (using thread_id for chat memory)
            # Agent selection is already determined in step 1 routing logic
            
            start_time = time.time()
            # Run the synchronous agent in a separate thread to prevent blocking
            agent_response = await asyncio.to_thread(
                chat_with_agent,
                message.text, 
                thread_id,
                from_number=message.from_number,
                agent_id=agent_id,
                contact_id=contact_id,
                user_id=user_id  # Pass user_id to the agent
            )

            processing_duration = int((time.time() - start_time) * 1000)  # Convert to milliseconds
            
            response_text = agent_response.get("response")
            if response_text:
                # 8. Send response via WhatsApp
                try:
                    sent_message = await asyncio.to_thread(
                        client.send_text_message, message.from_number, response_text
                    )
                    if sent_message.success:
                        # Log outgoing message (with AI processing metadata)
                        await asyncio.to_thread(
                            db.log_message,
                            contact_id,
                            sent_message.message_id,
                            'outgoing',
                            'text',
                            chatbot_id,
                            response_text,
                            None,
                            sent_message.status,
                            None,
                            True,
                            agent_response.get('confidence_score'),
                            processing_duration,
                        )
                        
                        # 9. Track usage for billing/limits
                        await asyncio.to_thread(track_message_usage, user_id)
                        
                        # 10. Launch analytics processing in the background (fire-and-forget)
                        final_state = agent_response.get('final_state')
                        if final_state and final_state.get('messages'):
                            # Construct the analytics state with the required fields
                            analytics_state = {
                                'conversation_id': thread_id,
                                'contact_id': contact_id,
                                'messages': final_state.get('messages', [])
                            }
                            asyncio.create_task(analytics_processor.run_analytics_task(analytics_state))
                        
                        logger.info(f"✅ Response sent and logged for user {user_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to send message: {e}")
                    
                    # Log failed message attempt
                    await asyncio.to_thread(
                        db.log_message,
                        contact_id,
                        f"failed_{int(time.time())}",
                        'outgoing',
                        'text',
                        chatbot_id,
                        response_text,
                        None,
                        'failed',
                        {'error': str(e)},
                        True,
                        None,
                        processing_duration,
                    )
            
            # 11. Check if agent requested human intervention
            if agent_response.get('requires_human_action'):
                action_id = await asyncio.to_thread(
                    create_action_request,
                    user_id,
                    chatbot_id,
                    contact_id,
                    agent_response.get('action_type', 'general_assistance'),
                    agent_response.get('action_details', 'Human assistance requested'),
                    agent_response.get('action_data', {}),
                    agent_response.get('priority', 'medium'),
                )
                
                if action_id:
                    logger.info(f"🙋 Action request created: {action_id} for user {user_id}")

            # 12. Handle tool calls (product images, location, etc.)
            tool_calls = agent_response.get("tool_calls", [])
            for tool_call in tool_calls:
                if tool_call.get("name") == "send_product_image":
                    args = tool_call.get("args", {})
                    product_name = args.get("product_name")
                    send_location = args.get("send_jounieh_location", False)
                    tool_config = {
                        "metadata": {
                            "from_number": message.from_number,
                            "user_id": user_id,
                            "chatbot_id": chatbot_id,
                            "contact_id": contact_id
                        }
                    }

                    if send_location:
                        sent_message_result = await asyncio.to_thread(
                            functools.partial(
                                send_product_image.invoke,
                                {"send_jounieh_location": True},
                                config=tool_config,
                            )
                        )
                        if sent_message_result.get("success"):
                            await asyncio.to_thread(
                                db.log_message,
                                contact_id,
                                sent_message_result.get("message_id"),
                                'outgoing',
                                'location',
                                chatbot_id,
                                "Jounieh Location",
                                None,
                                sent_message_result.get("status"),
                                {
                                    "tool": "send_product_image",
                                    "location": {"preset": "jounieh"},
                                    "provider_result": sent_message_result,
                                },
                                False,
                                None,
                                None,
                            )
                    elif product_name:
                        sent_message_result = await asyncio.to_thread(
                            functools.partial(
                                send_product_image.invoke,
                                {"product_name": product_name},
                                config=tool_config,
                            )
                        )
                        if sent_message_result.get("success"):
                            await asyncio.to_thread(
                                db.log_message,
                                contact_id,
                                sent_message_result.get("message_id"),
                                'outgoing',
                                'image',
                                chatbot_id,
                                product_name,
                                PRODUCT_IMAGES.get(product_name),
                                sent_message_result.get("status"),
                                {
                                    "tool": "send_product_image",
                                    "product_name": product_name,
                                    "provider_result": sent_message_result,
                                },
                                False,
                                None,
                                None,
                            )
                elif tool_call.get("name") == "astrosouks_send_product_image":
                    args = tool_call.get("args", {})
                    product_name = args.get("product_name")
                    tool_config = {
                        "metadata": {
                            "from_number": message.from_number,
                            "user_id": user_id,
                            "chatbot_id": chatbot_id,
                            "contact_id": contact_id
                        }
                    }
                    if product_name:
                        # Invoke AstroSouks image tool (it logs messages internally on success)
                        _ = await asyncio.to_thread(
                            functools.partial(
                                astrosouks_send_product_image.invoke,
                                {"product_name": product_name},
                                config=tool_config,
                            )
                        )
        except asyncio.CancelledError:
            logger.info(f"✅ Worker #{worker_id} has been gracefully terminated.")
            break
        except Exception as e:
            logger.error(f"💥 Unhandled exception in worker #{worker_id}: {e}", exc_info=True)
            # Attempt limited requeue for transient failures
            try:
                if message is not None:
                    next_retries = getattr(message, "retries", 0) + 1
                    if next_retries <= 3:
                        requeued = message.copy(update={"retries": next_retries})
                        GLOBAL_MESSAGE_QUEUE.put_nowait(requeued)
                        logger.warning(
                            f"🔁 Requeued message {message.message_id} from {message.from_number} (retry {next_retries}/3)"
                        )
                    else:
                        logger.error(
                            f"🛑 Dropping message {message.message_id} after {next_retries - 1} retries"
                        )
            except Exception as requeue_err:
                logger.error(f"Failed to requeue message after error: {requeue_err}", exc_info=True)

        finally:
            # Ensure the queue slot is always marked done to prevent deadlocks
            if message is not None:
                try:
                    GLOBAL_MESSAGE_QUEUE.task_done()
                except Exception:
                    pass

def _extract_message_data(result: Dict) -> Optional[InboundMessageResult]:
    try:
        message_id = result.get("messageId", "")
        from_number = result.get("from", "")
        to_number = result.get("to", "")
        message = result.get("message", {})
        message_type = message.get("type", "unknown").lower()
        text = message.get("text")
        media_url = message.get("url")
        # Location may arrive either as message["location"] or top-level fields inside message
        location_obj = None
        if isinstance(message, dict):
            if isinstance(message.get("location"), dict):
                location_obj = message.get("location")
            elif message_type == 'location' and ("latitude" in message or "longitude" in message):
                # Normalize into a location object
                location_obj = {
                    "latitude": message.get("latitude"),
                    "longitude": message.get("longitude"),
                    "name": message.get("name"),
                    "address": message.get("address"),
                    "url": message.get("url"),
                }
        # Try multiple locations for contact name to support different provider envelopes
        contact = result.get("contact", {})
        contact_name = contact.get("name") if isinstance(contact, dict) else None

        if not contact_name:
            # Meta Cloud / On-Prem style: contacts[0].profile.name
            contacts_arr = result.get("contacts") or result.get("contactes")  # tolerate typos
            if isinstance(contacts_arr, list) and contacts_arr:
                first_contact = contacts_arr[0] or {}
                profile = first_contact.get("profile", {}) if isinstance(first_contact, dict) else {}
                cn = profile.get("name") if isinstance(profile, dict) else None
                contact_name = cn or contact_name

        if not contact_name:
            # Some aggregators include sender.name
            sender_obj = result.get("sender")
            if isinstance(sender_obj, dict):
                cn = sender_obj.get("name")
                contact_name = cn or contact_name

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
                # Analyze image for agent processing (will not be shown in frontend)
                analysis_result = process_image_from_url(media_url)
                text = analysis_result
                logger.info(f"Analyzed image from {from_number}: {text}")
            except Exception as e:
                logger.error(f"Failed to analyze image from {from_number}: {e}")
                text = None

        elif isinstance(location_obj, dict):
            try:
                lat = float(location_obj.get('latitude')) if location_obj.get('latitude') is not None else None
                lon = float(location_obj.get('longitude')) if location_obj.get('longitude') is not None else None
                if lat is None or lon is None:
                    raise ValueError("Missing latitude/longitude in location payload")
                geocode_out = reverse_geocode_location(lat, lon, language="en", region=None)
                if geocode_out.get("success"):
                    data = geocode_out["data"]
                    # Compose a rich, agent-friendly description with full details
                    address1 = data.get("address1")
                    address2 = data.get("address2")
                    locality = data.get("locality")
                    admin1 = data.get("admin_area_1")
                    postal = data.get("postal_code")
                    country = data.get("country")
                    premise = data.get("premise") or data.get("building_name")
                    loc_type = (data.get("location_type") or "").upper()
                    plus_code = data.get("plus_code")

                    line_components = [
                        address1,
                        address2,
                        ", ".join(filter(None, [locality, admin1])),
                        postal,
                        country,
                    ]
                    normalized_line = ", ".join([p for p in line_components if p]) or data.get("formatted")
                    links = maps_directions_links(lat, lon)

                    near_phrase = f"near {premise}" if premise else (
                        f"on {data.get('route')}" if data.get('route') else ""
                    )
                    loc_precision = " (ROOFTOP)" if loc_type == "ROOFTOP" else (
                        " (Approximate)" if loc_type else ""
                    )

                    details_lines = [
                        f"Address: {normalized_line}",
                    ]
                    if plus_code:
                        details_lines.append(f"Plus code: {plus_code}")
                    if data.get("place_id"):
                        details_lines.append(f"Place ID: {data.get('place_id')}")
                    details_lines.append(f"Location type: {loc_type or 'N/A'}")
                    details_lines.append(f"Maps: {links.get('google_maps_place')}")
                    details_lines.append(f"Directions: {links.get('google_maps_directions')}")

                    # Agent-facing summary including "near ..." phrasing
                    text = (
                        "User shared a location" + loc_precision + ".\n" +
                        (f"This location is {near_phrase}.\n" if near_phrase else "") +
                        "\n".join(details_lines)
                    )
                    location_details = {
                        "normalized": data,
                        "links": links,
                        "original": {
                            "name": location_obj.get("name"),
                            "address": location_obj.get("address"),
                            "url": location_obj.get("url"),
                        },
                    }
                else:
                    links = maps_directions_links(lat, lon)
                    text = (
                        "User shared a location.\n"
                        f"Directions: {links.get('google_maps_directions')}"
                    )
                    location_details = {
                        "normalized": None,
                        "links": links,
                        "original": {
                            "name": location_obj.get("name"),
                            "address": location_obj.get("address"),
                            "url": location_obj.get("url"),
                        },
                        "error": geocode_out.get("error"),
                    }
            except Exception as e:
                logger.error(f"Failed to process location from {from_number}: {e}")
                location_details = {
                    "normalized": None,
                    "links": maps_directions_links(location_obj.get('latitude'), location_obj.get('longitude')) if location_obj and location_obj.get('latitude') and location_obj.get('longitude') else {},
                    "original": location_obj or {},
                    "error": str(e),
                }

            return InboundMessageResult(
                message_id=message_id,
                from_number=from_number,
                to_number=to_number,
                message_type=message_type,
                text=text,
                contact_name=contact_name,
                content_url=None,
                received_at=datetime.now(),
                location_latitude=float(location_obj.get('latitude')) if location_obj and location_obj.get('latitude') is not None else None,
                location_longitude=float(location_obj.get('longitude')) if location_obj and location_obj.get('longitude') is not None else None,
                location_details=location_details,
            )

        return InboundMessageResult(
            message_id=message_id,
            from_number=from_number,
            to_number=to_number,
            message_type=message_type,
            text=text,
            contact_name=contact_name,
            content_url=media_url,
            received_at=datetime.now(),
        )
    except Exception as e:
        logger.error(f"Error extracting message data: {e}")
        return None

async def process_webhook_payload(payload: Dict[str, Any]) -> List[InboundMessageResult]:
    try:
        results: List[InboundMessageResult] = []
        if "results" in payload:
            tasks = [asyncio.to_thread(_extract_message_data, result) for result in payload["results"]]
            extracted = await asyncio.gather(*tasks, return_exceptions=False)
            results = [m for m in extracted if m]
        # Fallback: Meta Cloud API envelope (entry -> changes -> value.messages)
        elif isinstance(payload, dict) and "entry" in payload and isinstance(payload["entry"], list):
            normalized_results: List[Dict[str, Any]] = []
            try:
                for entry in payload.get("entry", []) or []:
                    for change in (entry.get("changes") or []):
                        value = change.get("value") or {}
                        messages = value.get("messages") or []
                        contacts = value.get("contacts") or []
                        contact_name = None
                        if contacts and isinstance(contacts, list):
                            profile = (contacts[0] or {}).get("profile") or {}
                            contact_name = profile.get("name")
                        meta_to = (value.get("metadata") or {}).get("display_phone_number")
                        for msg in messages:
                            msg_type = (msg.get("type") or "").lower()
                            norm: Dict[str, Any] = {
                                "messageId": msg.get("id"),
                                "from": msg.get("from"),
                                "to": meta_to,
                                "contact": {"name": contact_name} if contact_name else {},
                                "message": {"type": msg_type}
                            }
                            if msg_type == "text":
                                norm["message"]["text"] = (msg.get("text") or {}).get("body")
                            elif msg_type in {"image", "video", "audio", "document"}:
                                media_obj = msg.get(msg_type) or {}
                                norm["message"]["url"] = media_obj.get("link") or media_obj.get("id")
                            elif msg_type == "location":
                                loc_obj = msg.get("location") or {}
                                norm["message"]["location"] = {
                                    "latitude": loc_obj.get("latitude"),
                                    "longitude": loc_obj.get("longitude"),
                                    "name": loc_obj.get("name"),
                                    "address": loc_obj.get("address"),
                                    "url": loc_obj.get("url"),
                                }
                            # Some aggregators place location fields flat in the message
                            if msg_type == "location" and not norm["message"].get("location"):
                                norm["message"]["location"] = {
                                    "latitude": msg.get("latitude"),
                                    "longitude": msg.get("longitude"),
                                    "name": msg.get("name"),
                                    "address": msg.get("address"),
                                    "url": msg.get("url"),
                                }
                            normalized_results.append(norm)
            except Exception as e:
                logger.warning(f"Failed to normalize Meta Cloud payload: {e}")

            if normalized_results:
                tasks = [asyncio.to_thread(_extract_message_data, result) for result in normalized_results]
                extracted = await asyncio.gather(*tasks, return_exceptions=False)
                results = [m for m in extracted if m]
        return results
    except Exception as e:
        logger.error(f"Error processing webhook payload: {e}")
        return []

# --- Manual Message Functions ---
async def send_manual_message_to_whatsapp(message_data: Dict, client: WhatsAppClient):
    """
    Sends a manual message from SwiftReplies to WhatsApp and updates the database.
    """
    try:
        message_id = message_data.get('message_id')
        contact_id = message_data.get('contact_id')
        content_text = message_data.get('content_text')
        chatbot_id = message_data.get('chatbot_id')
        
        logger.info(f"📤 Sending manual message {message_id} to WhatsApp")
        
        # Get contact phone number (offloaded to thread)
        def _fetch_phone_number(cid: int) -> Optional[str]:
            conn = db.connect_to_db()
            if not conn:
                return None
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT phone_number FROM contacts WHERE id = %s", (cid,))
                    row = cur.fetchone()
                    return row[0] if row else None
            finally:
                conn.close()

        phone_number = await asyncio.to_thread(_fetch_phone_number, contact_id)
        if not phone_number:
            logger.error(f"Contact {contact_id} not found or DB unavailable")
            return
        
        # Send via WhatsApp API
        sent_message = await asyncio.to_thread(client.send_text_message, phone_number, content_text)
        
        # Update message status in database
        if sent_message.success:
            # Update with WhatsApp message ID and sent status
            await asyncio.to_thread(
                db.update_message_status,
                message_id,
                'sent',
                sent_message.message_id,
            )
            logger.info(f"✅ Manual message {message_id} sent successfully to {phone_number}")
        else:
            # Update with failed status
            await asyncio.to_thread(
                db.update_message_status,
                message_id,
                'failed',
                None,
                f"WhatsApp API error: {sent_message.status}",
            )
            logger.error(f"❌ Failed to send manual message {message_id} to {phone_number}")
            
    except Exception as e:
        logger.error(f"💥 Error sending manual message: {e}", exc_info=True)
        # Try to update status to failed
        try:
            await asyncio.to_thread(
                db.update_message_status,
                message_data.get('message_id'),
                'failed',
                None,
                str(e),
            )
        except:
            pass

async def poll_for_manual_messages(client: WhatsAppClient):
    """
    Background task that polls for new manual messages that need to be sent to WhatsApp.
    Much more reliable than LISTEN/NOTIFY which doesn't work properly in Supabase.
    """
    logger.info("🔄 Starting manual message polling system...")
    
    last_processed_id = 0
    
    while True:
        try:
            # Get the latest processed message ID on startup
            if last_processed_id == 0:
                conn = db.connect_to_db()
                if conn:
                    try:
                        with conn.cursor() as cur:
                            cur.execute("""
                                SELECT COALESCE(MAX(id), 0) 
                                FROM messages 
                                WHERE direction = 'manual' AND user_sent = true
                            """)
                            result = cur.fetchone()
                            last_processed_id = result[0] if result else 0
                            logger.info(f"📍 Starting from message ID: {last_processed_id}")
                    finally:
                        conn.close()
            
            # Poll for new manual messages
            conn = db.connect_to_db()
            if not conn:
                logger.error("Could not connect to database for polling")
                await asyncio.sleep(5)
                continue
                
            try:
                with conn.cursor() as cur:
                    # Get new manual messages that haven't been processed yet
                    cur.execute("""
                        SELECT 
                            id, contact_id, content_text, chatbot_id, created_at, status
                        FROM messages 
                        WHERE direction = 'manual' 
                        AND user_sent = true 
                        AND id > %s
                        AND status != 'sent'
                        ORDER BY id ASC
                    """, (last_processed_id,))
                    
                    new_messages = cur.fetchall()
                    
                    for msg in new_messages:
                        message_id, contact_id, content_text, chatbot_id, created_at, status = msg
                        
                        logger.info(f"📨 Found new manual message ID: {message_id}")
                        
                        # Prepare message data for sending
                        message_data = {
                            'message_id': message_id,
                            'contact_id': contact_id,
                            'content_text': content_text,
                            'chatbot_id': chatbot_id,
                            'created_at': str(created_at)
                        }
                        
                        # Send message to WhatsApp
                        await send_manual_message_to_whatsapp(message_data, client)
                        
                        # Update last processed ID
                        last_processed_id = message_id
                        
            finally:
                conn.close()
            
            # Poll every 2 seconds for new messages
            await asyncio.sleep(2)
            
        except asyncio.CancelledError:
            logger.info("🛑 Manual message polling cancelled")
            break
            
        except Exception as e:
            logger.error(f"💥 Error in manual message polling: {e}", exc_info=True)
            await asyncio.sleep(5)

# --- Action Feedback Functions ---
def create_internal_agent_message(
    contact_id: int,
    chatbot_id: int,
    action_id: int,
    request_type: str,
    request_details: str,
    status: str,
    user_response: str = ""
) -> str:
    """
    Create an internal message to send to the agent for processing action feedback.
    This message will be processed by the agent to generate an appropriate response.
    """
    # Format the action type for display
    action_type_display = request_type.replace('_', ' ').title()
    
    # Create a comprehensive internal message with all context
    if status == 'approved':
        if user_response.strip():
            internal_message = f"This is an internal message: The {action_type_display} for '{request_details}' has been APPROVED. Admin response: {user_response}"
        else:
            internal_message = f"This is an internal message: The {action_type_display} for '{request_details}' has been APPROVED."
    elif status == 'denied':
        if user_response.strip():
            internal_message = f"This is an internal message: The {action_type_display} for '{request_details}' has been DENIED. Admin response: {user_response}"
        else:
            internal_message = f"This is an internal message: The {action_type_display} for '{request_details}' has been DENIED."
    else:
        internal_message = f"This is an internal message: The {action_type_display} for '{request_details}' has been {status.upper()}."
        if user_response.strip():
            internal_message += f" Admin response: {user_response}"
    
    logger.info(f"📝 Created internal agent message for action {action_id}: {internal_message[:100]}...")
    return internal_message

def generate_action_response(
    request_type: str, 
    status: str, 
    user_response: str = "", 
    request_details: str = ""
) -> str:
    """
    DEPRECATED: Generate contextual agent responses based on action type and outcome.
    This function is kept for potential fallback but is no longer used in the main flow.
    """
    # Base response templates
    templates = {
        'refund_request': {
            'approved': f"Great news! 🎉 Your refund request has been approved. {user_response}".strip(),
            'denied': f"I understand your refund concerns. {user_response} Please let me know if you have any questions.".strip()
        },
        'policy_clarification': {
            'approved': f"I've got the clarification you needed: {user_response}".strip(),
            'denied': f"Let me help clarify our policy. {user_response} Feel free to ask if you need more details.".strip()
        },
        'custom_quote': {
            'approved': f"Perfect! I've prepared a custom quote for you. {user_response}".strip(),
            'denied': f"I understand you're looking for a custom quote. {user_response} Let's explore other options.".strip()
        },
        'manual_followup': {
            'approved': f"Thanks for your patience! {user_response}".strip(),
            'denied': f"I appreciate your inquiry. {user_response} Is there anything else I can help with?".strip()
        },
        'approval_request': {
            'approved': f"Approved! ✅ {user_response}".strip(),
            'denied': f"I've reviewed your request. {user_response} Let me know if you'd like to discuss alternatives.".strip()
        },
        'help_needed': {
            'approved': f"I'm here to help! {user_response}".strip(),
            'denied': f"I understand you need assistance. {user_response} Let's find the best solution for you.".strip()
        }
    }
    
    # Get template for this action type
    action_templates = templates.get(request_type, {
        'approved': f"Your request has been processed. {user_response}".strip(),
        'denied': f"I've reviewed your request. {user_response}".strip()
    })
    
    # Get response for this status
    response = action_templates.get(status, f"Update on your {request_type.replace('_', ' ')}: {user_response}".strip())
    
    # If no user response provided, use default based on status
    if not user_response.strip():
        if status == 'approved':
            response = response.replace(f" {user_response}", "").strip()
        else:
            response = response.replace(f"{user_response} ", "").strip()
    
    return response

def update_action_indicator_status(action_id: int, contact_id: int, new_status: str) -> bool:
    """
    Update the status of an action indicator message in the conversation.
    This updates the content_text JSON to reflect the new status.
    """
    try:
        conn = db.connect_to_db()
        if not conn:
            return False
        
        with conn.cursor() as cur:
            # Find the action indicator message
            cur.execute("""
                UPDATE messages 
                SET content_text = jsonb_set(content_text::jsonb, '{status}', %s::jsonb)
                WHERE direction = 'internal' 
                AND message_type = 'action_indicator'
                AND contact_id = %s
                AND content_text::jsonb->>'action_id' = %s
            """, (f'"{new_status}"', contact_id, str(action_id)))
            
            updated_rows = cur.rowcount
            conn.commit()
            
            if updated_rows > 0:
                logger.info(f"✅ Updated action indicator status for action {action_id} to '{new_status}'")
                return True
            else:
                logger.warning(f"⚠️ No action indicator message found for action {action_id}")
                return False
                
    except Exception as e:
        logger.error(f"Error updating action indicator status: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# --- Scale Down Workers Function ---
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

# --- FastAPI Application ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management with multi-tenant support."""
    global MANUAL_MESSAGE_LISTENER_TASK
    
    # Startup
    logger.info("🚀 Starting SwiftReplies.ai Multi-Tenant WhatsApp Bot")
    
    # Initialize WhatsApp clients for multi-tenant support
    clients = {}
    
    # SwiftReplies (ECLA) client
    ecla_client = WhatsAppClient(
        api_key=settings.infobip_api_key,
        base_url=settings.infobip_base_url,
        sender=settings.whatsapp_sender,
    )
    clients['ecla'] = ecla_client
    clients[settings.whatsapp_sender] = ecla_client  # Also map by number
    
    # AstroSouks client (if configured)
    if settings.astrosouks_whatsapp_sender:
        astrosouks_client = WhatsAppClient(
            api_key=settings.infobip_api_key,
            base_url=settings.infobip_base_url,
            sender=settings.astrosouks_whatsapp_sender,
        )
        clients['astrosouks'] = astrosouks_client
        clients[settings.astrosouks_whatsapp_sender] = astrosouks_client  # Also map by number
        logger.info(f"🤖 AstroSouks client initialized for sender: {settings.astrosouks_whatsapp_sender}")
    
    # Store all clients and set default
    app.state.whatsapp_clients = clients
    app.state.whatsapp_client = ecla_client  # Keep backward compatibility
    
    logger.info(f"🤖 Multi-tenant WhatsApp clients initialized: {len(clients)} clients")
    
    # Start minimum number of workers
    for i in range(MIN_WORKERS):
        task = asyncio.create_task(agent_worker(i + 1, clients))
        WORKER_POOL.append(task)
    
    # Start the janitor task
    janitor_task = asyncio.create_task(scale_down_workers())
    
    # Start the debounce state cleanup task
    cleanup_task = asyncio.create_task(cleanup_stale_debounce_states())
    
    # Manual message handling via HTTP webhook endpoint (no polling needed)
    
    logger.info(f"✅ Multi-tenant system ready with {len(WORKER_POOL)} workers and HTTP webhook endpoints")
    
    yield
    
    # Clean up on shutdown
    logger.info("🛑 Shutting down multi-tenant system...")
    janitor_task.cancel()
    cleanup_task.cancel()
    for task in WORKER_POOL:
        task.cancel()
    
    # Manual message polling system cleanup handled by task cancellation
    
    tasks_to_wait = [janitor_task, cleanup_task, *WORKER_POOL]
    
    await asyncio.gather(*tasks_to_wait, return_exceptions=True)
    logger.info("All workers and services shut down.")

app = FastAPI(
    title="SwiftReplies.ai Multi-Tenant WhatsApp Bot", 
    version="2.0.0", 
    lifespan=lifespan,
    description="Multi-tenant WhatsApp automation platform"
)

# Add CORS middleware to handle frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Shopify OAuth endpoints removed per request

@app.post("/webhook")
async def receive_whatsapp_message(request: Request):
    """
    Enhanced webhook endpoint with multi-tenant support and usage tracking.
    """
    try:
        payload = await request.json()
        # Log full raw webhook payload for debugging (Infobip WhatsApp inbound)
        try:
            logger.info("📥 Raw webhook payload (Infobip WhatsApp): %s", json.dumps(payload))
        except Exception:
            logger.info("📥 Raw webhook payload (non-JSON-serializable): %s", str(payload))
        messages = await process_webhook_payload(payload)

        if not messages:
            logger.warning("Webhook payload parsed but contained no recognizable inbound messages.")
            # Signal transient parsing/format issues so the provider can retry delivery
            raise HTTPException(status_code=422, detail="No valid WhatsApp messages parsed from payload")

        # Log normalized messages snapshot for debugging location parsing edge cases
        try:
            for m in messages:
                logger.info(
                    "🧭 Normalized message - type=%s text_present=%s lat=%s lon=%s media_url=%s",
                    getattr(m, 'message_type', None),
                    bool(getattr(m, 'text', None)),
                    getattr(m, 'location_latitude', None),
                    getattr(m, 'location_longitude', None),
                    getattr(m, 'content_url', None),
                )
        except Exception:
            pass

        processed_count = 0
        for message in messages:
            # Push to handler; usage limits will be enforced in the worker
            await handle_incoming_message(message)
            processed_count += 1

        # Dynamic worker scaling based on queue size
        if GLOBAL_MESSAGE_QUEUE.qsize() > BUSY_THRESHOLD and len(WORKER_POOL) < MAX_WORKERS:
            logger.info(f"Queue is busy (size: {GLOBAL_MESSAGE_QUEUE.qsize()}). Scaling up workers.")
            new_worker_id = len(WORKER_POOL) + 1
            new_task = asyncio.create_task(agent_worker(new_worker_id, app.state.whatsapp_clients))
            WORKER_POOL.append(new_task)

        return {
            "status": "success", 
            "total_messages": len(messages),
            "processed_messages": processed_count,
            "queue_size": GLOBAL_MESSAGE_QUEUE.qsize(),
            "active_workers": len(WORKER_POOL)
        }

    except Exception as e:
        logger.error(f"Error in webhook endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred.")

@app.get("/health")
async def health_check():
    """Enhanced health check with multi-tenant metrics."""
    try:
        # Test database connectivity without blocking event loop
        def _test_db() -> bool:
            conn_local = db.connect_to_db()
            ok = conn_local is not None
            if conn_local:
                conn_local.close()
            return ok

        db_healthy = await asyncio.to_thread(_test_db)
        
        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "timestamp": datetime.now(),
            "active_workers": len(WORKER_POOL),
            "queued_messages": GLOBAL_MESSAGE_QUEUE.qsize(),
            "version": "2.0.0",
            "system": "multi-tenant",
            "database": "connected" if db_healthy else "disconnected",
            "debounce_states": len(user_debounce_states),
            "manual_message_system": "HTTP webhook",
            "webhook_endpoint": "/manual-message"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(),
            "error": str(e)
        }

@app.post("/manual-message")
async def handle_manual_message(request: Request):
    """HTTP endpoint to receive manual message notifications from database trigger."""
    try:
        payload = await request.json()
        logger.info(f"📨 Received manual message via HTTP: {payload}")

        # Determine tenant routing for manual message
        # Prefer explicit chatbot_id from payload; fallback to resolve by contact_id's owner
        def _fetch_contact_owner_and_phone(cid: int):
            conn = db.connect_to_db()
            if not conn:
                return None
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT phone_number, user_id FROM contacts WHERE id = %s", (cid,))
                    row = cur.fetchone()
                    if row:
                        return {"phone_number": row[0], "user_id": row[1]}
                    return None
            finally:
                conn.close()

        contact_id = payload.get("contact_id")
        chatbot_id = payload.get("chatbot_id")

        user_id_for_contact = None
        if contact_id and isinstance(contact_id, int):
            info = await asyncio.to_thread(_fetch_contact_owner_and_phone, contact_id)
            if info:
                user_id_for_contact = info.get("user_id")

        # Resolve sender based on contact's owner FIRST to avoid client-side mismatch
        sender_cfg = None
        if isinstance(user_id_for_contact, int):
            sender_cfg = MultiTenantConfig.resolve_sender_config_by_user(user_id_for_contact)
        if sender_cfg is None and isinstance(chatbot_id, int):
            sender_cfg = MultiTenantConfig.resolve_sender_config_by_chatbot(chatbot_id)

        # Default to ECLA if still unresolved
        client: WhatsAppClient
        if sender_cfg and isinstance(sender_cfg.get("client_key"), str):
            client_key = sender_cfg["client_key"]
            client = app.state.whatsapp_clients.get(client_key) or app.state.whatsapp_client
            logger.info(f"📨 Manual message routed to client '{client_key}' for user_id={user_id_for_contact} chatbot_id={chatbot_id}")
        else:
            client = app.state.whatsapp_client
            logger.info("📨 Manual message routed to default client (fallback)")

        # If the payload chatbot_id mismatches the resolved mapping, correct the DB message row
        try:
            resolved_chatbot_id = sender_cfg.get("chatbot_id") if sender_cfg else MultiTenantConfig.DEFAULT_CHATBOT_ID
            payload_mid = payload.get("message_id")
            if isinstance(resolved_chatbot_id, int) and isinstance(payload_mid, int):
                if not isinstance(chatbot_id, int) or chatbot_id != resolved_chatbot_id:
                    def _update_message_chatbot(mid: int, new_cid: int):
                        conn2 = db.connect_to_db()
                        if not conn2:
                            return False
                        try:
                            with conn2.cursor() as cur2:
                                cur2.execute("UPDATE messages SET chatbot_id = %s WHERE id = %s", (new_cid, mid))
                                conn2.commit()
                                return True
                        finally:
                            conn2.close()
                    ok_fix = await asyncio.to_thread(_update_message_chatbot, payload_mid, resolved_chatbot_id)
                    if ok_fix:
                        logger.info(f"🛠️ Corrected manual message chatbot_id to {resolved_chatbot_id} for message {payload_mid}")
        except Exception as _fix_err:
            logger.warning(f"Could not correct chatbot_id for manual message: {_fix_err}")

        # Send the message out via selected client
        await send_manual_message_to_whatsapp(payload, client)
        
        return {"status": "success", "message": "Manual message processed"}
        
    except Exception as e:
        logger.error(f"💥 Error processing manual message HTTP request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process manual message")


@app.post("/thread-instructions")
async def handle_thread_instructions(request: Request):
    """
    HTTP endpoint to inject per-thread instructions with minimal latency.
    Expected payload mirrors /manual-message:
    {
      "message_id": int,         # ignored
      "contact_id": int,         # required
      "content_text": str,       # required unless action=="clear"
      "chatbot_id": int,         # ignored
      "created_at": str,         # ignored
      "action": "set"|"clear"   # optional, default "set"
    }
    """
    try:
        payload = await request.json()
        logger.info(f"🧭 Received thread instruction request: {payload}")

        contact_id = payload.get("contact_id")
        instruction_text = payload.get("content_text")
        # Be tolerant: if action not provided, infer it from content_text
        raw_action = payload.get("action")
        if raw_action is None:
            action = "clear" if (not instruction_text or not isinstance(instruction_text, str) or not instruction_text.strip()) else "set"
        else:
            action = str(raw_action).strip().lower()

        if not contact_id or not isinstance(contact_id, int):
            raise HTTPException(status_code=400, detail="contact_id (int) is required")
        if action not in ("set", "clear"):
            raise HTTPException(status_code=400, detail="action must be 'set' or 'clear'")
        if action == "set" and (not instruction_text or not isinstance(instruction_text, str) or not instruction_text.strip()):
            raise HTTPException(status_code=400, detail="content_text is required when action is 'set'")

        # Resolve thread_id from contact
        def _fetch_thread_id(cid: int):
            conn = db.connect_to_db()
            if not conn:
                return None
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT thread_id FROM contacts WHERE id = %s", (cid,))
                    row = cur.fetchone()
                    return row[0] if row else None
            finally:
                conn.close()

        thread_id = await asyncio.to_thread(_fetch_thread_id, contact_id)
        if not thread_id:
            raise HTTPException(status_code=404, detail="contact_id not found")

        # Apply instruction via agent without using tool calls
        ok = await asyncio.to_thread(
            set_thread_instructions_for_thread,
            thread_id,
            None if action == "clear" else instruction_text.strip(),
        )
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to apply instructions")

        return {
            "status": "success",
            "thread_id": thread_id,
            "action": action,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Error processing thread instructions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process thread instructions")

# Shopify webhook endpoint removed per request to simplify server

@app.post("/action-feedback")
async def handle_action_feedback(request: Request):
    """
    HTTP endpoint to receive action status updates and trigger agent responses.
    When an action is approved/denied, this generates a contextual response to the customer.
    """
    try:
        payload = await request.json()
        logger.info(f"🎯 Received action feedback: {payload}")
        
        # Extract payload data
        action_id = payload.get('action_id')
        status = payload.get('status')  # 'approved' or 'denied'
        user_response = payload.get('user_response', '')
        contact_id = payload.get('contact_id')
        chatbot_id = payload.get('chatbot_id', 1)
        request_type = payload.get('request_type')
        request_details = payload.get('request_details', '')
        
        if not all([action_id, status, contact_id, request_type]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Create internal message for the agent to process
        internal_message = await asyncio.to_thread(
            create_internal_agent_message,
            contact_id,
            chatbot_id,
            action_id,
            request_type,
            request_details,
            status,
            user_response
        )
        
        if internal_message:
            # Get contact phone number and simulate incoming message to trigger agent
            def _fetch_contact_info(cid: int) -> Optional[tuple]:
                conn = db.connect_to_db()
                if not conn:
                    return None
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT phone_number, thread_id FROM contacts WHERE id = %s", (cid,))
                        row = cur.fetchone()
                        return (row[0], row[1]) if row else None
                finally:
                    conn.close()

            contact_info = await asyncio.to_thread(_fetch_contact_info, contact_id)
            if not contact_info:
                logger.error(f"Contact {contact_id} not found for action feedback")
                return {"status": "error", "message": "Contact not found"}
            
            phone_number, thread_id = contact_info
            
            # Create a message object for the agent to process
            internal_message_obj = InboundMessageResult(
                message_id=f"action_feedback_{action_id}_{int(time.time())}",
                from_number=phone_number,
                to_number="",  # Not needed for internal processing
                message_type="text",
                text=internal_message,
                contact_name=None,
                received_at=datetime.now()
            )
            
            # Add to the global message queue for agent processing
            await GLOBAL_MESSAGE_QUEUE.put(internal_message_obj)
            
            # Update action indicator message status
            await asyncio.to_thread(
                update_action_indicator_status,
                action_id,
                contact_id,
                status
            )
            
            logger.info(f"✅ Action feedback sent to agent for processing: action {action_id}")
            return {
                "status": "success", 
                "message": "Action feedback sent to agent for processing",
                "internal_message": internal_message
            }
        else:
            logger.warning(f"⚠️ Failed to create internal message for action {action_id}")
            return {"status": "error", "message": "Failed to create internal message"}
        
    except Exception as e:
        logger.error(f"💥 Error processing action feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process action feedback")

@app.get("/metrics")
async def system_metrics():
    """New endpoint for monitoring multi-tenant metrics."""
    try:
        return {
            "system": {
                "queue_size": GLOBAL_MESSAGE_QUEUE.qsize(),
                "worker_count": len(WORKER_POOL),
                "debounce_states": len(user_debounce_states),
                "max_workers": MAX_WORKERS,
                "busy_threshold": BUSY_THRESHOLD
            },
            "debounce": {
                "timeout_seconds": DEBOUNCE_SECONDS,
                "cleanup_interval": CLEANUP_INTERVAL_SECONDS,
                "active_timers": sum(1 for state in user_debounce_states.values() 
                                   if state.get('task') and not state['task'].done())
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Metrics endpoint failed: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve metrics")

if __name__ == "__main__":
    uvicorn.run(
        "whatsapp_message_fetcher:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        proxy_headers=True,
        forwarded_allow_ips='*'
    ) 