from typing import Dict, Any, Optional
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig
from infobip_whatsapp_methods.client import WhatsAppClient
from src.config.settings import settings

PRODUCT_IMAGES = {
    "ECLA® e20 Bionic⁺ Kit": "https://cdn.shopify.com/s/files/1/0715/1668/4484/files/bionic2_1600x_05ad8cb7-411e-4c1f-8b95-f18c38a331c3.webp?v=1752181116",
    "ECLA® Purple Corrector": "https://cdn.shopify.com/s/files/1/0715/1668/4484/files/pc1_1600x_0062e3af-3ab2-4728-a305-feecfde707b7.webp?v=1752180314",
    "ECLA® Teeth Whitening Pen": "https://cdn.shopify.com/s/files/1/0715/1668/4484/files/pen1_1600x_6a3393cf-190c-4d39-99ac-edda306eca99.webp?v=1752180586",
}

# Constants for template media
SHOWCASE_IMAGES = {
    "kit": "https://odvrvwoyqcfnwcvlbnip.supabase.co/storage/v1/object/public/swiftmessages.images//ecla_bionic_kit.jpeg",
    "pen": "https://odvrvwoyqcfnwcvlbnip.supabase.co/storage/v1/object/public/swiftmessages.images//ecla_whitening_pen.jpeg",
    "corrector": "https://odvrvwoyqcfnwcvlbnip.supabase.co/storage/v1/object/public/swiftmessages.images//ecla_whitening_paste.jpeg",
}
CHRISTMAS_OFFER_IMAGE = "https://odvrvwoyqcfnwcvlbnip.supabase.co/storage/v1/object/public/swiftmessages.images//ecla_christmas_offer.jpeg"


@tool
def send_product_image(
    product_name: Optional[str] = None,
    send_jounieh_location: bool = False,
    send_christmas_offer: bool = False,
    send_product_showcase: bool = False,
    *,
    config: RunnableConfig,
) -> Dict[str, Any]:
    """
    Sends rich content to the user on WhatsApp. Can send a product image, store location, the Christmas offer, or a product showcase carousel.
    The user's phone number is determined automatically from the session.

    Args:
        product_name (Optional[str]): The name of the product image to send. Must be one of "ECLA® e20 Bionic⁺ Kit", "ECLA® Purple Corrector", or "ECLA® Teeth Whitening Pen".
        send_jounieh_location (bool): Set to True to send the predefined 'Jounieh' store location.
        send_christmas_offer (bool): Set to True to send the special 'ecla_christmas_template'. Use this for the Christmas promotion.
        send_product_showcase (bool): Set to True to send the 'ecla_product_showcase' carousel featuring the main products. Use this when a user asks for an overview of all products.

    Note:
        Provide only one of 'product_name', 'send_jounieh_location', 'send_christmas_offer', or 'send_product_showcase'.
    """
    to_number = config["metadata"].get("from_number")
    if not to_number:
        return {"success": False, "error": "Could not determine the recipient's phone number."}

    # Validate that only one action is requested
    actions = [product_name, send_jounieh_location, send_christmas_offer, send_product_showcase]
    if sum(bool(a) for a in actions) != 1:
        return {"success": False, "error": "Provide exactly one action: product_name, location, christmas_offer, or product_showcase."}

    client = WhatsAppClient(
        api_key=settings.infobip_api_key,
        base_url=settings.infobip_base_url,
        sender=settings.whatsapp_sender,
    )

    # Christmas Offer Logic (Simple Image Template)
    if send_christmas_offer:
        payload = {
            "messages": [
                {
                    "from": settings.whatsapp_sender,
                    "to": to_number,
                    "content": {
                        "templateName": "ecla_christmas_template",
                        "templateData": {
                            "body": {"placeholders": []},
                            "header": {"type": "IMAGE", "mediaUrl": CHRISTMAS_OFFER_IMAGE},
                            "buttons": [{"type": "QUICK_REPLY", "parameter": "christmas_inquiry"}]
                        },
                        "language": "en",
                    },
                }
            ]
        }
        return client.send_raw_template(payload).to_dict()

    # Product Showcase Logic (Carousel Template)
    if send_product_showcase:
        payload = {
            "messages": [
                {
                    "from": settings.whatsapp_sender,
                    "to": to_number,
                    "content": {
                        "templateName": "ecla_product_showcase",
                        "templateData": {
                            "body": {"placeholders": []},
                            "carousel": {
                                "cards": [
                                    { # Card 1: Kit
                                        "header": {"type": "IMAGE", "mediaUrl": SHOWCASE_IMAGES["kit"]},
                                        "body": {"placeholders": []},
                                        "buttons": [{"type": "QUICK_REPLY", "parameter": "showcase_kit"}]
                                    },
                                    { # Card 2: Pen
                                        "header": {"type": "IMAGE", "mediaUrl": SHOWCASE_IMAGES["pen"]},
                                        "body": {"placeholders": []},
                                        "buttons": [{"type": "QUICK_REPLY", "parameter": "showcase_pen"}]
                                    },
                                    { # Card 3: Corrector
                                        "header": {"type": "IMAGE", "mediaUrl": SHOWCASE_IMAGES["corrector"]},
                                        "body": {"placeholders": []},
                                        "buttons": [{"type": "QUICK_REPLY", "parameter": "showcase_corrector"}]
                                    }
                                ]
                            }
                        },
                        "language": "en",
                    },
                }
            ]
        }
        return client.send_raw_template(payload).to_dict()

    if send_jounieh_location:
        return client.send_location_preset(to_number, "jounieh").to_dict()

    if product_name:
        image_url = PRODUCT_IMAGES.get(product_name)
        if not image_url:
            return {"success": False, "error": f"Product '{product_name}' not found."}
        return client.send_image(to_number, image_url, caption=product_name).to_dict()

    return {"success": False, "error": "No valid action specified."} 