#!/usr/bin/env python3
import os
import sys
import json

# Ensure project root is on sys.path so `src` imports work when running via absolute path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.astrosouks_tools.astrosouks_order_tool import create_astrosouks_order


def main():
    # Inputs provided by user
    customer_first_name = "Antonio"
    customer_last_name = "Wehbe"
    customer_phone = "70895652"
    shipping_address_line1 = "Sahel Alma 955, ROOFTOP"
    shipping_address_line2 = "near Sahel Alma 955"
    shipping_city = "Sahel Alma"
    shipping_province = "Mount Lebanon"
    shipping_country = "Lebanon"
    product_selections = '[{"product_name":"Bone Conduction Speaker","quantity":2,"variant_title":""}]'
    discount_percent = 10.0

    # RunnableConfig can be a simple dict for our usage (the tool only calls .get)
    config = {"metadata": {"from_number": "+96170895652", "user_id": 6, "chatbot_id": 3}}

    tool_input = {
        "customer_first_name": customer_first_name,
        "customer_last_name": customer_last_name,
        "customer_phone": customer_phone,
        "shipping_address_line1": shipping_address_line1,
        "shipping_address_line2": shipping_address_line2,
        "shipping_city": shipping_city,
        "shipping_province": shipping_province,
        "shipping_country": shipping_country,
        "product_selections": product_selections,
        "billing_same_as_shipping": True,
        "order_notes": "",
        "discount_percent": discount_percent,
    }

    result = create_astrosouks_order.invoke(tool_input, config=config)

    # Print tool summary string
    try:
        print(result)
    except Exception:
        print(json.dumps({"result": result}))


if __name__ == "__main__":
    main()


