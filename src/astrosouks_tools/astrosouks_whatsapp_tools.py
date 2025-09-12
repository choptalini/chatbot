from __future__ import annotations

"""
WhatsApp tools for AstroSouks (AstroTech).

Tool: astrosouks_send_product_image
- Sends either a single product image OR the approved 'astrosouks_tech_bestsellers' carousel template.
- Product names and image URLs are sourced from the generated text export
  (shopify_active_product_images_*.txt). This ensures we cover ALL active products.
"""

import re
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from langchain.tools import tool
from langchain_core.runnables import RunnableConfig

from infobip_whatsapp_methods.client import WhatsAppClient
from src.config.settings import settings
from src.multi_tenant_database import db as mt_db, get_user_by_phone_number as mt_get_user_by_phone_number
from src.astrosouks_tools.astrosouks_cag_tool import _load_astrosouks_knowledge_text


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
    """Parse the exported products+images file into {product_name: [img_url,...]} (first image only used).

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
            if len(mapping[current_name]) < 1:
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
    lines.append("INSTRUCTION FOR LLM — astrosouks_send_product_image")
    lines.append("")
    lines.append("Purpose:")
    lines.append("- Send rich content to a customer on WhatsApp using Infobip — either a single product image or an approved bestsellers carousel ('tech', 'home', or 'beauty').")
    lines.append("")
    lines.append("When to use:")
    lines.append("- Single image: the user asks to see a specific AstroSouks item.")
    lines.append("- Carousel: the user is browsing, comparing, or you want to showcase bestsellers.")
    lines.append("")
    lines.append("Arguments you must set:")
    lines.append("- product_name (Optional[str]): Exact product name (case‑insensitive match against the catalog list below). Use this to send ONE image. Do NOT set when sending a carousel.")
    lines.append("- carousel (Optional[str]): One of {'tech','home','beauty'}. Use this to send the pre‑approved carousel. Do NOT set any product_name when sending a carousel.")
    lines.append("- config.metadata.from_number (str, REQUIRED): Customer’s WhatsApp number to send to.")
    lines.append("- config.metadata.contact_id (int, optional): If absent, a contact is auto‑created for the AstroSouks tenant.")
    lines.append("")
    lines.append("Filling content:")
    lines.append("- Single image: caption must be the product name.")
    lines.append("- Carousel: for each card, {{1}} MUST be the price string from the knowledge base in the form '$<current> (was $<original>)' when available; else '$<current>'; else 'See price'. The QUICK_REPLY parameter MUST be the product name.")
    lines.append("")
    lines.append("Conflict rule:")
    lines.append("- If both product_name and carousel are provided, SEND THE CAROUSEL and ignore product_name.")
    lines.append("")
    lines.append("Options for product_name (exact names):")
    if PRODUCT_NAMES:
        for name in PRODUCT_NAMES:
            lines.append(f"  - {name}")
    else:
        lines.append("  - (No products loaded – ensure the shopify_active_product_images_*.txt export exists.)")
    lines.append("")
    lines.append("Operational notes for the LLM:")
    lines.append("- Do NOT construct raw Infobip payloads yourself — call this tool with the arguments above.")
    lines.append("- Always set either product_name OR carousel (or neither if not sending); never both unless intending to send the carousel.")
    lines.append("- Prices are sourced from the AstroSouks knowledge base; do not invent values.")
    return "\n".join(lines)


def _extract_prices_from_kb(product_name: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (current_price, original_price) strings like '19.99', '31.00' from knowledge base."""
    kb = _load_astrosouks_knowledge_text()
    if not kb:
        return None, None
    import re
    # Match section header like #### **Product**
    pattern = rf"^#### \*\*{re.escape(product_name)}\*\*\s*$"
    lines = kb.splitlines()
    idx = None
    for i, line in enumerate(lines):
        if re.match(pattern, line.strip()):
            idx = i
            break
    if idx is None:
        return None, None
    # Scan next ~20 lines for a Price line
    price_line = None
    for j in range(idx + 1, min(len(lines), idx + 25)):
        if lines[j].strip().startswith("#### ") or lines[j].strip() == "---":
            break
        if "**Price:**" in lines[j]:
            price_line = lines[j]
            break
    if not price_line:
        return None, None
    # Extract $current and optional 'On sale from $orig'
    cur = None
    orig = None
    m1 = re.search(r"\$([0-9]+(?:\.[0-9]{2})?)", price_line)
    if m1:
        cur = m1.group(1)
    m2 = re.search(r"On sale from \$([0-9]+(?:\.[0-9]{2})?)", price_line)
    if m2:
        orig = m2.group(1)
    return cur, orig


def _build_tech_carousel_payload(sender: str, to_number: str) -> Dict[str, Any]:
    """Construct the TECH bestsellers carousel payload with prices filled in."""
    # Mapping of product display name -> image URL
    cards_spec: List[Tuple[str, str]] = [
        ("4in1 Fast Car Charger", "https://cdn.shopify.com/s/files/1/0609/5306/7597/files/4prtc-5-main.webp?v=1749984953"),
        ("Jet Drone", "https://cdn.shopify.com/s/files/1/0609/5306/7597/files/Rc-Fighter-Jet-Plane-9.jpg?v=1753622834"),
        ("Bone Conduction Speaker", "https://cdn.shopify.com/s/files/1/0609/5306/7597/files/Diseno_sin_titulo_16.webp?v=1752164423"),
        ("Power Bank Speaker - 3 in 1", "https://cdn.shopify.com/s/files/1/0609/5306/7597/files/dfkjdfldf2-550x550h.png?v=1740953617"),
        ("Wireless Glasses Headset", "https://cdn.shopify.com/s/files/1/0609/5306/7597/files/no_brand_f-06_kacamata_headset_bloetooth_musik_mp3_nirkabel_smart_glasses_wireless_headset_earphone_headphone_waterproof_anti-blu-ray_smart_sunglasses_kaca_mat_full06_toedkmct_41310141-12a5-441e-a51f-90a03ed7e05c.webp?v=1754750155"),
        ("Galaxy Man - Projector", "https://cdn.shopify.com/s/files/1/0609/5306/7597/files/10948_2_1024x1024_44da9e4b-b626-46db-8f70-fe5b8480e7c0.webp?v=1741469527"),
        ("Dorry Smart Body Scale", "https://cdn.shopify.com/s/files/1/0609/5306/7597/files/rn-image_picker_lib_temp_a8e6fa4f-a67f-47c9-9abd-53bb5e87e387.jpg?v=1755800525"),
        ("Neck Heater - Rechargeable", "https://cdn.shopify.com/s/files/1/0609/5306/7597/files/3364a5c7-0c5e-430d-9bcc-216892af870f.jpg?v=1732214801"),
    ]

    cards: List[Dict[str, Any]] = []
    for name, url in cards_spec:
        cur, orig = _extract_prices_from_kb(name)
        if cur and orig:
            placeholder = f"${cur} (was ${orig})"
        elif cur:
            placeholder = f"${cur}"
        else:
            placeholder = "See price"
        cards.append({
            "header": {"type": "IMAGE", "mediaUrl": url},
            "body": {"placeholders": [placeholder]},
            "buttons": [{"type": "QUICK_REPLY", "parameter": name}]
        })

    payload = {
        "messages": [
            {
                "from": sender,
                "to": to_number,
                "content": {
                    "templateName": "astrosouks_tech_bestsellers",
                    "templateData": {
                        "body": {"placeholders": []},
                        "carousel": {"cards": cards}
                    },
                    "language": "en"
                }
            }
        ]
    }
    return payload


def _build_home_carousel_payload(sender: str, to_number: str) -> Dict[str, Any]:
    """Construct the HOME bestsellers carousel payload with prices filled in."""
    # Products extracted from screenshots (home best sellers):
    # Bag Sealer, Food Vacuum Sealer, Spray Mop - 2 in 1, 3 in 1 Vacuum Cleaner,
    # Ultrasonic Cleaner, Electric Juicer - Portable, 3-in-1 Air Cooler Fan, Action Self-Squeezing Mop
    cards_spec: List[Tuple[str, str]] = [
        ("Bag Sealer", ""),
        ("Food Vacuum Sealer", ""),
        ("Spray Mop - 2 in 1", ""),
        ("3 in 1 Vacuum Cleaner", ""),
        ("Ultrasonic Cleaner", ""),
        ("Electric Juicer - Portable", ""),
        ("3-in-1 Air Cooler Fan", ""),
        ("Action Self-Squeezing Mop", ""),
    ]

    # Try to find image URLs for these names from our exported products file mapping
    # Fallback: leave mediaUrl blank if not found; the template must still pass validation
    images_map = ASTROSOUSKS_PRODUCT_IMAGES or {}

    cards: List[Dict[str, Any]] = []
    for name, url in cards_spec:
        # Attempt to map to known image file by closest key (case-insensitive exact)
        key = None
        lookup = {k.lower(): k for k in images_map.keys()}
        if name.lower() in lookup:
            key = lookup[name.lower()]
            urls = images_map.get(key, [])
            if urls:
                url = urls[0]
        cur, orig = _extract_prices_from_kb(name)
        if cur and orig:
            placeholder = f"${cur} (was ${orig})"
        elif cur:
            placeholder = f"${cur}"
        else:
            placeholder = "See price"
        cards.append({
            "header": {"type": "IMAGE", "mediaUrl": url},
            "body": {"placeholders": [placeholder]},
            "buttons": [{"type": "QUICK_REPLY", "parameter": name}]
        })

    payload = {
        "messages": [
            {
                "from": sender,
                "to": to_number,
                "content": {
                    "templateName": "astrosouks_home_bestsellers",
                    "templateData": {
                        "body": {"placeholders": []},
                        "carousel": {"cards": cards}
                    },
                    "language": "en"
                }
            }
        ]
    }
    return payload


def _build_beauty_carousel_payload(sender: str, to_number: str) -> Dict[str, Any]:
    """Construct the BEAUTY bestsellers carousel payload (9 cards) with prices filled in."""
    # Products extracted from screenshots (beauty best sellers):
    # Carrera - Waver, SilverCrest - Perfect Curl, Hair Dryer Brush - 4 in 1,
    # Thread Hair Removal Machine, Nevadent Electric Tooth Brush,
    # Black Head Remover, Dead Skin Remover, Flawless Facial Hair Removal,
    # Hair Curler - Rechargeable
    names = [
        "Carrera - Waver",
        "SilverCrest - Perfect Curl",
        "Hair Dryer Brush - 4 in 1",
        "Thread Hair Removal Machine",
        "Nevadent Electric Tooth Brush",
        "Black Head Remover",
        "Dead Skin Remover",
        "Flawless Facial Hair Removal",
        "Hair Curler - Rechargeable",
    ]

    images_map = ASTROSOUSKS_PRODUCT_IMAGES or {}
    lookup = {k.lower(): k for k in images_map.keys()}

    cards: List[Dict[str, Any]] = []
    for name in names:
        url = ""
        key = lookup.get(name.lower())
        if key:
            urls = images_map.get(key, [])
            if urls:
                url = urls[0]
        cur, orig = _extract_prices_from_kb(name)
        if cur and orig:
            placeholder = f"${cur} (was ${orig})"
        elif cur:
            placeholder = f"${cur}"
        else:
            placeholder = "See price"
        cards.append({
            "header": {"type": "IMAGE", "mediaUrl": url},
            "body": {"placeholders": [placeholder]},
            "buttons": [{"type": "QUICK_REPLY", "parameter": name}]
        })

    payload = {
        "messages": [
            {
                "from": sender,
                "to": to_number,
                "content": {
                    "templateName": "astrosouks_beauty_bestsellers",
                    "templateData": {
                        "body": {"placeholders": []},
                        "carousel": {"cards": cards}
                    },
                    "language": "en"
                }
            }
        ]
    }
    return payload


@tool
def astrosouks_send_product_image(
    product_name: Optional[str] = None,
    carousel: Optional[str] = None,
    *,
    config: RunnableConfig,
) -> Dict[str, Any]:
    """
    INSTRUCTION FOR LLM — How to use this tool:
    - Use to send either a single product image (set product_name) or a bestsellers carousel (set carousel to 'tech' or 'home').
    - Required: config.metadata.from_number must be the customer's phone number.
    - Single image rules: send the first image; set caption to the product name.
    - Carousel rules: auto-fill each card's {{1}} with the price from the KB (format "$<current> (was $<original>)" when available). Set button QUICK_REPLY parameter to the product name.
    - If both product_name and carousel are set, the carousel is sent and product_name is ignored.
    - The tool logs the message under the AstroSouks tenant automatically.
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

    client = WhatsAppClient(
        api_key=settings.infobip_api_key,
        base_url=settings.infobip_base_url,
        sender=settings.astrosouks_whatsapp_sender,
    )

    # Branch 1: send the approved carousel
    if carousel:
        c = (carousel or "").strip().lower()
        if c not in ("tech", "home", "beauty"):
            return {"success": False, "error": "carousel must be one of: 'tech', 'home', 'beauty'"}
        if c == "tech":
            payload = _build_tech_carousel_payload(client.sender, to_number)
        elif c == "home":
            payload = _build_home_carousel_payload(client.sender, to_number)
        else:
            payload = _build_beauty_carousel_payload(client.sender, to_number)
        result = client.send_raw_template(payload).to_dict()
        try:
            if result.get("success"):
                metadata = config.get("metadata", {}) if config else {}
                contact_id = metadata.get("contact_id")
                if not contact_id:
                    contact_id, _ = mt_db.get_or_create_contact(to_number, user_id=6)
                if contact_id:
                    mt_db.log_message(
                        contact_id=contact_id,
                        message_id=result.get("message_id"),
                        direction='outgoing',
                        message_type='template',
                        chatbot_id=3,
                        content_text='astrosouks_tech_bestsellers',
                        content_url=None,
                        status=result.get("status") or 'sent',
                        metadata={"tool": "astrosouks_send_product_image", "template": ("astrosouks_tech_bestsellers" if c=="tech" else ("astrosouks_home_bestsellers" if c=="home" else "astrosouks_beauty_bestsellers"))},
                        ai_processed=False,
                    )
        except Exception:
            pass
        return {"success": result.get("success", False), "template": ("astrosouks_tech_bestsellers" if c=="tech" else ("astrosouks_home_bestsellers" if c=="home" else "astrosouks_beauty_bestsellers")), "result": result}

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

    image_urls = ASTROSOUSKS_PRODUCT_IMAGES.get(matched_key, [])[:1]
    if not image_urls:
        return {"success": False, "error": f"No images available for '{matched_key}'."}

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

