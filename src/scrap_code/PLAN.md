# WhatsApp Agent Integration Plan

This document outlines the steps to integrate the AI agent with the WhatsApp messaging service, manage conversation history in a PostgreSQL database, and add new capabilities to the agent.

## 1. Project Setup & Analysis

- [ ] Analyze `terminal_chat.py` to understand how the `ECLAAgent` is invoked and how its responses are handled.
- [ ] Check `requirements.txt` for the `psycopg2-binary` dependency. If it's not present, add it.
- [ ] Analyze `whatsapp_message_fetcher.py` to identify where to add the new logic for database interaction and agent invocation.

## 2. Database Integration

- [ ] In a new `database.py` file or within `whatsapp_message_fetcher.py`, create functions to interact with the PostgreSQL database:
    - `connect_to_db()`: Establishes a connection to the database.
    - `get_or_create_contact(phone_number)`: Checks if a contact with the given phone number exists. If not, it creates a new contact with a unique `thread_id`. It returns the contact information, including the `thread_id`.
    - `log_message(contact_id, message_id, direction, message_type, content_text, content_url, status)`: Logs a message to the `messages` table.

## 3. Agent and Tool Enhancements

- [ ] Create a new tool file `src/tools/ecla_whatsapp_tools.py` for WhatsApp-specific tools.
- [ ] Implement a `send_product_image_tool(product_name: str)` in the new tool file. This tool will look up a predefined image URL based on the product name and use the `WhatsAppClient` to send the image. The tool function will **not** take the `to_number` as an argument.
- [ ] Update `src/agent/core.py` to include the new `send_product_image_tool` in the agent's toolset.
- [ ] Update the agent's system prompt in `src/agent/core.py` to instruct it on how and when to use the new image-sending tool.

## 4. End-to-End Integration in `whatsapp_message_fetcher.py`

- [ ] In the `/webhook` endpoint of `whatsapp_message_fetcher.py`:
    - For each incoming message, extract the `from_number` and the message content.
    - Call `get_or_create_contact` to get the contact and `thread_id`.
    - Log the incoming message to the database using `log_message`.
    - Invoke the `ECLAAgent` with the message content and `thread_id`.
    - The agent's response stream will be processed.
- [ ] Implement logic to handle the agent's output:
    - If the output is a text message, send it to the user via the `WhatsAppClient`.
    - If the output is a tool call for sending an image:
        - Execute the tool call. The `from_number` from the original incoming message will be used as the `to_number`.
    - Log all outgoing messages (both text and images) to the database.

## 5. Code Cleanup and Finalizing

- [ ] Review all changes for code quality, clarity, and correctness.
- [ ] Ensure all new functions and modules are well-documented.
- [ ] Remove any unnecessary files or code.
- [ ] Verify that the application runs without errors. 