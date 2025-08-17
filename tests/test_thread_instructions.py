import os
import sys
import uuid


def _set_required_env():
    os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
    os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
    os.environ.setdefault("INFOBIP_API_KEY", "test-infobip-key")
    os.environ.setdefault("INFOBIP_BASE_URL", "api.infobip.test")
    os.environ.setdefault("WHATSAPP_SENDER", "0000000000")


def test_agent_set_and_get_thread_instructions():
    _set_required_env()

    # Import after setting env
    from src.agent import core as agent_core

    # Force MemorySaver by nulling the external checkpointer symbol
    agent_core.postgres_checkpointer = None

    # Build a minimal config for the agent
    cfg = {
        "description": "test agent",
        "model_settings": {
            "provider": "openai",
            "name": "gpt-4.1-nano",
        },
        "system_prompt": "You are a test agent.",
        "tools": [],
    }

    agent = agent_core.ECLAAgent(agent_config=cfg)

    thread_id = str(uuid.uuid4())

    # Set instructions
    ok = agent.set_thread_instructions(thread_id, "Be concise.")
    assert ok is True

    # Read back
    got = agent.get_thread_instructions(thread_id)
    assert got == "Be concise."

    # Clear
    ok2 = agent.set_thread_instructions(thread_id, None)
    assert ok2 is True
    got2 = agent.get_thread_instructions(thread_id)
    assert got2 is None


def test_thread_instructions_endpoint_set_and_clear(monkeypatch):
    _set_required_env()

    # Import after env
    from fastapi.testclient import TestClient
    import whatsapp_folder.whatsapp_message_fetcher_multitenant as appmod

    # Fake DB connection for thread_id lookup
    class _Cur:
        def __init__(self, thread_id):
            self._thread_id = thread_id

        def execute(self, *_args, **_kwargs):
            pass

        def fetchone(self):
            return (self._thread_id,)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Conn:
        def cursor(self):
            return _Cur("test-thread-123")

        def close(self):
            pass

    monkeypatch.setattr(appmod.db, "connect_to_db", lambda: _Conn())

    # Stub instruction setter to avoid depending on agent registry here
    called = {"args": None}

    def _fake_setter(thread_id, instructions, agent_id="ecla_sales_agent"):
        called["args"] = (thread_id, instructions, agent_id)
        return True

    monkeypatch.setattr(appmod, "set_thread_instructions_for_thread", _fake_setter)

    client = TestClient(appmod.app)

    # Set
    payload = {
        "message_id": 1,
        "contact_id": 999,
        "content_text": "Act in concise mode.",
        "chatbot_id": 2,
        "created_at": "2025-01-01T00:00:00Z",
    }
    r = client.post("/thread-instructions", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "success"
    assert body["action"] == "set"
    assert body["thread_id"] == "test-thread-123"
    assert called["args"] == ("test-thread-123", "Act in concise mode.", "ecla_sales_agent")

    # Clear
    payload2 = {
        "message_id": 2,
        "contact_id": 999,
        "content_text": "",
        "action": "clear",
    }
    r2 = client.post("/thread-instructions", json=payload2)
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["status"] == "success"
    assert body2["action"] == "clear"
    assert body2["thread_id"] == "test-thread-123"

    # Missing contact_id
    r3 = client.post("/thread-instructions", json={"content_text": "x"})
    assert r3.status_code == 400

    # Missing content_text for set
    r4 = client.post("/thread-instructions", json={"contact_id": 1})
    assert r4.status_code == 400

