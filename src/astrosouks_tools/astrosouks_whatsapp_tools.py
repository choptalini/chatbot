from __future__ import annotations

"""
WhatsApp tools for AstroSouks (AstroTech).

Tool: astrosouks_send_product_image
- Sends up to 3 images for a given AstroSouks product name to the current WhatsApp recipient.
- Product names and image URLs are sourced from the generated text export
  (shopify_active_product_images_*.txt). This ensures we cover ALL active products.
"""

import re
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from langchain.tools import tool
from langchain_core.runnables import RunnableConfig

from infobip_whatsapp_methods.client import WhatsAppClient
from src.config.settings import settings
from src.multi_tenant_database import db as mt_db, get_user_by_phone_number as mt_get_user_by_phone_number


def _find_latest_products_file() -> Optional[Path]:
    """Locate the most recent shopify_active_product_images_*.txt file.

    Search order:
      1) ASTROSOUSKS_PRODUCTS_FILE env var (absolute or relative path)
      2) Project root glob: shopify_active_product_images_*.txt
    """
    env_path = os.getenv("ASTROSOUSKS_PRODUCTS_FILE")
    if env_path:
        p = Path(env_path)
        if not p.is_absolute():
            p = Path(__file__).resolve().parents[2] / p
        return p if p.exists() else None

    root = Path(__file__).resolve().parents[2]  # project root (whatsapp_folder)
    candidates = sorted(root.glob("shopify_active_product_images_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _parse_products_file(path: Path) -> Dict[str, List[str]]:
    """Parse the exported products+images file into {product_name: [img_url,...]} (max 3 urls).

    The file format is lines with headers like:
      # Product Name
      ID: gid://... | Handle: ... | Status: ACTIVE | Vendor: ...
      Images: N
        - https://...
        - https://...
    """
    mapping: Dict[str, List[str]] = {}
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return mapping

    current_name: Optional[str] = None
    for raw in content.splitlines():
        line = raw.strip()
        if line.startswith("# "):
            name = line[2:].strip()
            if name.endswith(":"):
                name = name[:-1].strip()
            current_name = name
            mapping.setdefault(current_name, [])
            continue
        if not current_name:
            continue
        m = re.search(r"-\s+(https?://\S+)", line)
        if m:
            url = m.group(1).strip()
            if len(mapping[current_name]) < 3:
                mapping[current_name].append(url)

    # Drop any entries without images
    return {k: v for k, v in mapping.items() if v}


def _load_astrosouks_product_images() -> Dict[str, List[str]]:
    products_file = _find_latest_products_file()
    if not products_file:
        return {}
    return _parse_products_file(products_file)


ASTROSOUSKS_PRODUCT_IMAGES: Dict[str, List[str]] = _load_astrosouks_product_images()
PRODUCT_NAMES: List[str] = sorted(ASTROSOUSKS_PRODUCT_IMAGES.keys())


def _build_tool_description() -> str:
    lines: List[str] = []
    lines.append("Sends rich content to the user on WhatsApp. This AstroSouks tool sends up to 3 product images.")
    lines.append("")
    lines.append("Args:")
    lines.append("  - product_name (Optional[str]): The AstroSouks product name to send images for. Must be one of the options listed below (case-insensitive).")
    lines.append("")
    lines.append("Options for product_name (exact names):")
    if PRODUCT_NAMES:
        for name in PRODUCT_NAMES:
            lines.append(f"  - {name}")
    else:
        lines.append("  - (No products loaded – ensure the shopify_active_product_images_*.txt export exists.)")
    lines.append("")
    lines.append("Notes:")
    lines.append("  - Provide only one argument: product_name.")
    lines.append("  - This tool is exclusive to AstroSouks products and sends images only (no locations, no carousels, no templates).")
    lines.append("")
    lines.append("Example:")
    lines.append("  astrosouks_send_product_image(product_name=\"Food Vacuum Sealer\")")
    return "\n".join(lines)


@tool
def astrosouks_send_product_image(
    product_name: Optional[str] = None,
    *,
    config: RunnableConfig,
) -> Dict[str, Any]:
    """
    Sends rich content to the user on WhatsApp. This AstroSouks tool sends up to 3 product images.
    """
    # Ensure description is fully populated (LangChain/LangGraph will read this as instruction)
    try:
        astrosouks_send_product_image.description = _build_tool_description()
        astrosouks_send_product_image.__doc__ = astrosouks_send_product_image.description
    except Exception:
        pass

    to_number = config["metadata"].get("from_number")
    if not to_number:
        return {"success": False, "error": "Could not determine the recipient's phone number."}

    if not product_name or not isinstance(product_name, str) or not product_name.strip():
        return {"success": False, "error": "Provide a valid product_name (string)."}

    if not ASTROSOUSKS_PRODUCT_IMAGES:
        return {"success": False, "error": "No product images mapping loaded. Ensure the export file exists."}

    # Case-insensitive exact match across known names
    lookup = {k.lower(): k for k in ASTROSOUSKS_PRODUCT_IMAGES.keys()}
    key_lower = product_name.strip().lower()
    matched_key = lookup.get(key_lower)
    if not matched_key:
        return {"success": False, "error": f"Product '{product_name}' not found. Check available names in the tool description."}

    image_urls = ASTROSOUSKS_PRODUCT_IMAGES.get(matched_key, [])[:3]
    if not image_urls:
        return {"success": False, "error": f"No images available for '{matched_key}'."}

    client = WhatsAppClient(
        api_key=settings.infobip_api_key,
        base_url=settings.infobip_base_url,
        sender=settings.astrosouks_whatsapp_sender,
    )

    sent: List[Dict[str, Any]] = []
    errors: List[str] = []

    for url in image_urls:
        try:
            result = client.send_image(to_number, url, caption=matched_key).to_dict()
            sent.append(result)
            try:
                if result.get("success"):
                    # AstroSouks tool always uses AstroSouks tenant context (sender: 9613451652)
                    # This ensures all messages sent FROM 9613451652 are logged to user_id=6
                    user_id = 6  # AstroSouks
                    chatbot_id = 3  # AstroSouks chatbot
                    
                    # Get contact_id from metadata if available, otherwise create/find for this customer
                    metadata = config.get("metadata", {}) if config else {}
                    contact_id = metadata.get("contact_id")
                    
                    if not contact_id:
                        # Create/find contact for this customer under AstroSouks tenant
                        contact_id, _thread_id = mt_db.get_or_create_contact(to_number, user_id=user_id)
                    if contact_id:
                        mt_db.log_message(
                            contact_id=contact_id,
                            message_id=result.get("message_id"),
                            direction='outgoing',
                            message_type='image',
                            chatbot_id=chatbot_id,
                            content_text=matched_key,
                            content_url=url,
                            status=result.get("status") or 'sent',
                            metadata={"tool": "astrosouks_send_product_image", "product_name": matched_key},
                            ai_processed=False,
                        )
            except Exception:
                pass
        except Exception as e:
            errors.append(str(e))

    success = any(r.get("success") for r in sent)
    return {
        "success": success,
        "product": matched_key,
        "images_attempted": len(image_urls),
        "results": sent,
        "errors": errors,
    }

# Set description at import time as well (for IDEs/registries that snapshot at import)
try:
    astrosouks_send_product_image.description = _build_tool_description()
    astrosouks_send_product_image.__doc__ = astrosouks_send_product_image.description
except Exception:
    pass

