"""
Test script: invoke AstroSouks inventory tool and save output to a txt file.

Env (loaded from .env):
  - ASTROSOUKS_SHOPIFY_SHOP_DOMAIN (required)
  - ASTROSOUKS_SHOPIFY_TOKEN       (required)

Usage:
  python scripts/test_astrosouks_inventory.py

Output:
  astrosouks_active_inventory_<domain>.txt (project root)
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure project root is on sys.path so 'src.*' imports work when running this script directly
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.astrosouks_tools.astrosouks_inventory_tool import check_astrosouks_inventory


def _sanitize_filename_component(text: str) -> str:
    sanitized = (text or "").strip().lower()
    for ch in [" ", ".", "/", "\\", ":", "*", "?", "\"", "<", ">", "|"]:
        sanitized = sanitized.replace(ch, "_")
    sanitized = sanitized.replace("-", "_")
    return sanitized[:80] or "store"


def main() -> None:
    load_dotenv()

    shop_domain = os.getenv("ASTROSOUKS_SHOPIFY_SHOP_DOMAIN")
    if not shop_domain:
        raise SystemExit("ERROR: ASTROSOUKS_SHOPIFY_SHOP_DOMAIN not set in environment.")

    # Invoke tool for all ACTIVE products (plain text output: one line per product)
    result_txt = check_astrosouks_inventory.invoke({"product_name": "all"})

    # Save to project root
    root = Path(__file__).resolve().parents[1]
    domain_component = _sanitize_filename_component(shop_domain)
    out_path = root / f"astrosouks_active_inventory_{domain_component}.txt"
    out_path.write_text((result_txt or "") + "\n", encoding="utf-8")
    print(f"Saved inventory output to: {out_path}")


if __name__ == "__main__":
    main()

