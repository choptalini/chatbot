"""
Context-Augmented Generation (CAG) tool for the AstroSouks (AstroTech) AI Agent.

This tool mirrors the ECLA CAG tool but targets the AstroSouks tenant. It loads
its knowledge from a local text file (astrosouks_knowledgebase.txt) to provide
fast, deterministic answers without a vector store.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from langchain.tools import tool
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.config.settings import settings


# --- Constants ---
ASTROSOOUKS_KB_FILENAME = "astrosouks_knowledgebase.txt"

# Minimal fallback description to be used when the knowledge base file is
# missing or empty. This should be replaced/augmented automatically once the
# knowledge base file is populated by the tenant.
ASTROSOOUKS_FALLBACK_DESCRIPTION = (
    "AstroSouks (operating as AstroTech) is an online e-commerce store based in "
    "Beirut, Lebanon. They sell a wide variety of consumer goods and gadgets, "
    "including electronics, personal care devices, home and kitchen tools, and "
    "toys. The store focuses on discounted prices, guarantees on product quality, "
    "and fast shipping."
)


def _load_astrosouks_knowledge_text() -> str:
    """Load the AstroSouks knowledge base from a local text file.

    The file is expected to live next to this module, under the same folder,
    named "astrosouks_knowledgebase.txt". If the file is missing or empty,
    a concise fallback description will be returned so the tool remains usable.
    """
    try:
        base_dir = Path(__file__).resolve().parent
        kb_path = base_dir / ASTROSOOUKS_KB_FILENAME

        if not kb_path.exists() or not kb_path.is_file():
            logging.warning("AstroSouks knowledge base file not found: %s", kb_path)
            return ASTROSOOUKS_FALLBACK_DESCRIPTION

        text = kb_path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            logging.warning("AstroSouks knowledge base file is empty: %s", kb_path)
            return ASTROSOOUKS_FALLBACK_DESCRIPTION

        return text
    except Exception as e:
        logging.error("Failed to load AstroSouks knowledge base: %s", e, exc_info=True)
        return ASTROSOOUKS_FALLBACK_DESCRIPTION


def _build_system_prompt() -> str:
    """Construct the system prompt by embedding the knowledge base text."""
    kb_text = _load_astrosouks_knowledge_text()
    system_prompt = (
        "You are an expert AstroSouks (AstroTech) Customer Support Agent working strictly "
        "from the official AstroSouks knowledge base provided below. Your goal is to extract "
        "and synthesize the most helpful answer using ONLY that content.\n\n"
        "INSTRUCTIONS (apply carefully):\n"
        "1) First, scan the entire knowledge base for all relevant facts (names, prices, policies, "
        "   guarantees, descriptions). Prefer exact matches but also include near-synonyms "
        "   (e.g., 'kitchen', 'home', 'cleaning', 'food prep', 'storage', 'gadgets') when the intent "
        "   is about product categories.\n"
        "2) If the user asks for products in a category (e.g., kitchen tools), return a concise list of "
        "   matching or closely related items from the knowledge base. For each item, include name, price, "
        "   and a one-line summary. Do NOT invent items that do not appear in the knowledge base.\n"
        "3) If the user asks about policies (shipping, delivery time, returns, warranty, payment), extract "
        "   the exact statements (e.g., 'delivered within 3–4 days', '30-day returns'). If fees or specific "
        "   options (e.g., cash on delivery) are not stated, say 'Not specified in the knowledge base' and then "
        "   provide the closest related information (like the general delivery guarantee) plus the relevant contact details "
        "   from the knowledge base.\n"
        "4) Only when truly no relevant information exists after searching the entire knowledge base, state that it is "
        "   not specified. Before concluding that, always provide the closest related details available and the official "
        "   contact information present in the knowledge base.\n"
        "5) Keep answers crisp and structured. Prefer short paragraphs and bullet points.\n\n"
        "Answer format (adapt as appropriate):\n"
        "- Summary: a one-sentence direct answer.\n"
        "- Details: bullet list of facts (names, prices, policy lines, delivery times).\n"
        "- Related info: alternatives or adjacent items/policies from the knowledge base.\n"
        "- Contact (if needed): official email(s)/address from the knowledge base.\n\n"
        "--- ASTROSOUSKS KNOWLEDGE BASE START ---\n\n"
        f"{kb_text}\n\n"
        "--- ASTROSOUSKS KNOWLEDGE BASE END ---\n\n"
        "Now answer the user's question strictly using the information above."
    )
    return system_prompt


# --- Pydantic Input Schema ---
class AstroSouksCAGInput(BaseModel):
    query: str = Field(
        description=(
            "The user's question about AstroSouks products, pricing, policies, "
            "operations, or company information."
        )
    )


# --- Tool Implementation ---
@tool("astrosouks_info_tool", args_schema=AstroSouksCAGInput)
def context_augmented_generation_astrosouks_tool(query: str) -> str:
    """
    Answers questions about AstroSouks (AstroTech) products, usage, pricing,
    policies, and company information based strictly on the local knowledge base.
    """
    logging.info("AstroSouks CAG Tool invoked with query: %s", query)
    try:
        # Initialize the fast, large-context model for this task
        llm = init_chat_model(
            model="gpt-4.1-nano",
            model_provider="openai",
            max_tokens=None,
            api_key=settings.openai_api_key,
        )

        system_prompt = _build_system_prompt()
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=query),
        ]

        response = llm.invoke(messages)
        answer = response.content.strip()
        logging.info("AstroSouks CAG Tool generated answer: %s", answer)
        return answer

    except Exception as e:
        logging.error("Error in AstroSouks CAG tool: %s", e, exc_info=True)
        return (
            "I'm sorry, but I encountered an error while trying to find that "
            "information. Please try again later."
        )

