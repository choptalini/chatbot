"""
LangChain tool to submit human-in-the-loop action requests.

The LLM may only provide: request_type, request_details, optional request_data (JSON), and priority (low|medium|high).
System fills user_id, chatbot_id, contact_id, and status (pending).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import json

from langchain.tools import tool
from langchain_core.runnables import RunnableConfig

from src.multi_tenant_database import (
    get_user_by_phone_number,
    get_or_create_contact,
    create_action_request,
    log_message,
)
from src.multi_tenant_config import config as tenant_config
import psycopg2
import os
import time
from datetime import datetime
import logging

# WhatsApp client for notifications
from infobip_whatsapp_methods.client import WhatsAppClient
from src.config.settings import settings


def _coerce_priority(priority: Optional[str]) -> str:
    if not priority:
        return "medium"
    value = str(priority).strip().lower()
    if value not in {"low", "medium", "high"}:
        raise ValueError("priority must be one of: low, medium, high")
    return value


def _create_action_indicator_message(
    action_id: int, 
    contact_id: int, 
    chatbot_id: int,
    request_type: str,
    request_details: str,
    priority: str
) -> bool:
    """
    Create an internal action indicator message in the conversation timeline.
    This message is ONLY shown to internal users, never sent to WhatsApp.
    
    Uses:
    - direction='internal' → Won't trigger notify_manual_message() 
    - user_sent=False → Won't be processed by WhatsApp poller
    - status='indicator' → Clearly marked as internal indicator
    - message_type='action_indicator' → Frontend can filter and style appropriately
    """
    try:
        # Create unique message ID for the action indicator
        message_id = f"action_indicator_{action_id}_{int(time.time())}"
        
        # Content contains the essential action info for display
        content_data = {
            "action_id": action_id,
            "request_type": request_type,
            "status": "pending",
            "priority": priority
        }
        
        # Metadata contains additional context
        metadata = {
            "action_id": action_id,
            "internal_only": True,
            "action_type": "indicator",
            "original_request": request_details[:100] + "..." if len(request_details) > 100 else request_details
        }
        
        # Log the internal message (will be sent_at=NOW() automatically)
        success = log_message(
            contact_id=contact_id,
            message_id=message_id,
            direction='internal',         # ✅ Safe: Won't trigger manual message systems
            message_type='action_indicator',  # ✅ New type for frontend filtering
            content_text=json.dumps(content_data),
            status='indicator'            # ✅ Safe: Not 'sent', so WhatsApp ignores
        )
        
        return success
        
    except Exception as e:
        # Don't fail the entire action creation if indicator message fails
        print(f"Warning: Failed to create action indicator message: {e}")
        return False


def _validate_and_parse_request(
    request_type: Optional[str], request_details: Optional[str]
) -> Dict[str, str]:
    if not request_type or not request_type.strip():
        raise ValueError("request_type is required")
    if not request_details or not request_details.strip():
        raise ValueError("request_details is required")

    request_type = request_type.strip()
    request_details = request_details.strip()

    if len(request_type) > 100:
        raise ValueError("request_type too long (max 100 chars)")
    if len(request_details) > 2000:
        raise ValueError("request_details too long (max 2000 chars)")

    return {"request_type": request_type, "request_details": request_details}


def _parse_request_data(request_data: Optional[str]) -> Optional[Dict[str, Any]]:
    if request_data is None or str(request_data).strip() == "":
        return None
    # Enforce a soft size limit (~10KB) to prevent abuse
    if isinstance(request_data, str) and len(request_data.encode("utf-8")) > 10_240:
        raise ValueError("request_data exceeds 10KB limit")
    try:
        parsed = json.loads(request_data) if isinstance(request_data, str) else request_data
    except json.JSONDecodeError:
        raise ValueError("request_data must be valid JSON when provided")
    if not isinstance(parsed, dict):
        raise ValueError("request_data must be a JSON object")
    return parsed


def _scrub_request_data(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Remove fields that should be resolved by the system (PII like phone/email)."""
    if not data:
        return data
    scrubbed = {k: v for k, v in data.items() if k not in {"phone", "email", "user_id", "chatbot_id", "contact_id", "status"}}
    return scrubbed


def _fetch_contact_user_id(contact_id: int) -> Optional[int]:
    """Best-effort lookup of user_id from contacts table when not provided in metadata."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return None
    try:
        conn = psycopg2.connect(db_url)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM contacts WHERE id=%s", (contact_id,))
                row = cur.fetchone()
                return int(row[0]) if row and row[0] is not None else None
        finally:
            conn.close()
    except Exception:
        return None


def _send_action_notification_to_owner(
    owner_phone: str,
    owner_name: str,
    for_contact: str,
    request_type: str,
    priority: str,
    request_details: str,
    request_data: Optional[Dict[str, Any]],
) -> None:
    """Best-effort WhatsApp utility template notification (no DB logging).

    Uses Infobip template `agent_action_required_full_details` with 6 placeholders:
      1. Owner name (e.g., "Antonio")
      2. Action type (e.g., refund_request)
      3. For contact (phone or label)
      4. Priority (low|medium|high)
      5. Details (short excerpt)
      6. Structured Data (pretty-printed JSON or "N/A")
    """

    try:
        # Prepare placeholder values
        details_excerpt = (request_details or "").strip()
        if len(details_excerpt) > 200:
            details_excerpt = details_excerpt[:200] + "..."

        def _format_request_data_one_line(data: Optional[Dict[str, Any]]) -> str:
            if not isinstance(data, dict) or not data:
                return "N/A"
            parts = []
            for k, v in data.items():
                try:
                    # Human-friendly key (Product Name, Order Id, etc.)
                    label = " ".join(str(k).replace("_", " ").split()).title()
                except Exception:
                    label = str(k)
                v_str = str(v)
                parts.append(f"{label}: {v_str}")
            s = "- ".join(parts)
            # remove newlines/extra spaces to fit WhatsApp template nicely
            s = " ".join(s.splitlines())
            if len(s) > 1200:
                s = s[:1200] + "..."
            return s

        structured_str = _format_request_data_one_line(request_data)

        placeholders = [
            owner_name,
            request_type,
            for_contact,
            priority,
            details_excerpt,
            structured_str,
        ]

        client = WhatsAppClient(
            api_key=settings.infobip_api_key,
            base_url=settings.infobip_base_url,
            sender=settings.whatsapp_sender,
        )

        # Prefer high-level client method for template sends
        resp = client.send_template(
            to_number=owner_phone,
            template_name="agent_action_required_full_details",
            language="en",
            body_variables=placeholders,
        )
        if not getattr(resp, "success", False):
            logging.warning(
                "Action notification template send returned non-success: %s",
                getattr(resp, "status", "unknown"),
            )
    except Exception as notify_err:
        # Never fail the action creation if notification sending fails
        logging.error("Failed to send action owner notification: %s", notify_err)


def _normalized_msisdn(num: str) -> str:
    if not isinstance(num, str):
        return str(num)
    return num.replace(" ", "").lstrip("+")


ASTRO_ACTION_OWNER_MSISDN = _normalized_msisdn("+961 71 000 086")  # Strict, no env override


def _owner_roster_lookup(user_id: int, chatbot_id: int) -> Dict[str, str]:
    """Return owner {phone,name} for a given (user_id, chatbot_id).

    Robust rule: ANY AstroSouks action (chatbot_id==3 or user_id==6) routes to
    +96171000086 strictly. No environment overrides, no fallbacks.
    Other tenants fallback to ECLA defaults (optionally overridable via envs).
    """
    # ECLA defaults (can be overridden)
    ecla_phone = _normalized_msisdn(os.getenv("ECLA_OWNER_PHONE") or "96170895652")
    ecla_name = (os.getenv("ECLA_OWNER_NAME") or "Antonio").strip()

    # AstroSouks hard binding
    if int(chatbot_id) == 3 or int(user_id) == 6:
        return {"phone": ASTRO_ACTION_OWNER_MSISDN, "name": "AstroSouks-Owner"}

    # Default/ECLA
    return {"phone": ecla_phone, "name": ecla_name}


@tool
def submit_action_request(
    request_type: Optional[str] = None,
    request_details: Optional[str] = None,
    priority: Optional[str] = None,
    request_data: Optional[str] = None,
    *,
    config: RunnableConfig,
) -> Dict[str, Any]:
    """
    Create a pending human-in-the-loop Action when the agent needs approval/clarification/help.

    You may provide (LLM-only):
    - request_type (str, required): short slug (e.g., "refund_request", "policy_clarification").
    - request_details (str, required): concise, actionable explanation (≤ 2000 chars).
    - priority (optional): "low" | "medium" | "high" (default "medium").
    - request_data (optional): JSON object string (≤ ~10KB) with structured context.

    System fills (do not set): user_id, chatbot_id, contact_id, status="pending", timestamps.

    Rules:
    - Provide only the fields above; keep details specific and safe.
    - priority must be low/medium/high.
    - request_data must be a JSON object string (not array/primitive).

    When to use: refunds beyond policy, policy clarifications, custom quotes, or edge cases requiring human input.

    Output:
    - Success: { success: true, action_id, status: "pending", summary }
    - Failure: { success: false, error }

    Realtime: DB triggers broadcast new actions to the Actions Center UI for operator review.
    """
    try:
        # Resolve metadata (phone number) from the tool invocation context
        # Handle both RunnableConfig objects and dicts
        if hasattr(config, "metadata"):
            metadata = getattr(config, "metadata", None) or {}
        elif isinstance(config, dict):
            metadata = config.get("metadata", {})
        else:
            metadata = {}
        from_number = metadata.get("from_number")
        user_id_meta = metadata.get("user_id")
        chatbot_id_meta = metadata.get("chatbot_id")
        contact_id_meta = metadata.get("contact_id")

        user_id: Optional[int] = int(user_id_meta) if user_id_meta is not None else None
        chatbot_id: Optional[int] = int(chatbot_id_meta) if chatbot_id_meta is not None else None
        contact_id: Optional[int] = int(contact_id_meta) if contact_id_meta is not None else None

        # Try to resolve missing pieces without requiring the LLM to pass them
        if contact_id is None and from_number:
            contact_id, _ = get_or_create_contact(from_number)
        if user_id is None:
            # Prefer metadata; otherwise derive from contact or phone
            if contact_id is not None:
                user_id = _fetch_contact_user_id(contact_id)
            if user_id is None and from_number:
                ui = get_user_by_phone_number(from_number) or {}
                user_id = int(ui["user_id"]) if ui.get("user_id") is not None else None
        if chatbot_id is None:
            # Prefer metadata; otherwise derive from phone; fallback to default
            if from_number:
                ui = get_user_by_phone_number(from_number) or {}
                chatbot_id = int(ui["chatbot_id"]) if ui.get("chatbot_id") is not None else None
            if chatbot_id is None:
                chatbot_id = int(getattr(tenant_config, "DEFAULT_CHATBOT_ID", 1))

        # Final validation
        if not all([user_id, chatbot_id, contact_id]):
            return {"success": False, "error": "Insufficient context to create action (user/chatbot/contact)."}

        # Validate base inputs
        validated = _validate_and_parse_request(request_type, request_details)
        coerced_priority = _coerce_priority(priority)

        # Parse request_data early so we can leverage any provided phone/email hints to resolve context
        parsed_request_data_raw = _parse_request_data(request_data)

        # If we still lack context, try using phone from request_data
        if (contact_id is None or user_id is None or chatbot_id is None):
            if not from_number and isinstance(parsed_request_data_raw, dict):
                req_phone = parsed_request_data_raw.get("phone") or parsed_request_data_raw.get("phone_number")
                if isinstance(req_phone, str) and req_phone.strip():
                    from_number = req_phone.strip()
            # Resolve from phone if possible
            if contact_id is None and from_number:
                contact_id, _ = get_or_create_contact(from_number)
            if user_id is None and from_number:
                ui2 = get_user_by_phone_number(from_number) or {}
                user_id = int(ui2["user_id"]) if ui2.get("user_id") is not None else user_id
            if chatbot_id is None and from_number:
                ui3 = get_user_by_phone_number(from_number) or {}
                chatbot_id = int(ui3["chatbot_id"]) if ui3.get("chatbot_id") is not None else chatbot_id
            if chatbot_id is None:
                chatbot_id = int(getattr(tenant_config, "DEFAULT_CHATBOT_ID", 1))

        # Final check post phone-based resolution
        if user_id is None and contact_id is not None:
            user_id = _fetch_contact_user_id(contact_id)

        # Scrub PII/system-managed fields before persisting request_data
        parsed_request_data = _scrub_request_data(parsed_request_data_raw)

        # Persist
        action_id = create_action_request(
            user_id=user_id,
            chatbot_id=chatbot_id,
            contact_id=contact_id,
            request_type=validated["request_type"],
            request_details=validated["request_details"],
            request_data=parsed_request_data,
            priority=coerced_priority,
        )

        if not action_id:
            return {
                "success": False,
                "error": "Database insert failed for action request",
            }

        # Create action indicator message in conversation timeline
        # This is optional - if it fails, the action itself still succeeds
        indicator_created = _create_action_indicator_message(
            action_id=action_id,
            contact_id=contact_id,
            chatbot_id=chatbot_id,
            request_type=validated['request_type'],
            request_details=validated['request_details'],
            priority=coerced_priority
        )

        # --- Owner WhatsApp notification (do not log to DB) ---
        try:
            # Select owner per (user_id, chatbot_id) with AstroSouks hard binding
            owner = _owner_roster_lookup(user_id=user_id, chatbot_id=chatbot_id)
            owner_phone = owner.get("phone")
            owner_name = owner.get("name")
            # Extra guard: if AstroSouks, enforce target strictly
            if int(chatbot_id) == 3 or int(user_id) == 6:
                owner_phone = ASTRO_ACTION_OWNER_MSISDN
                owner_name = owner_name or "AstroSouks-Owner"
            for_contact_value = from_number if from_number else f"Contact ID {contact_id}"
            _send_action_notification_to_owner(
                owner_phone=owner_phone,
                owner_name=owner_name,
                for_contact=for_contact_value,
                request_type=validated["request_type"],
                priority=coerced_priority,
                request_details=validated["request_details"],
                request_data=parsed_request_data,
            )
        except Exception as _e:
            logging.error("Owner notification send failed: %s", _e)

        summary = (
            f"Action #{action_id} created (type={validated['request_type']}, "
            f"priority={coerced_priority}) — pending review"
        )
        if indicator_created:
            summary += " | Conversation indicator added"
        
        return {
            "success": True,
            "action_id": int(action_id),
            "status": "pending",
            "summary": summary,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

