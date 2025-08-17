## Actions Center Tool PRD — Human-in-the-Loop Action Requests

### 1) Summary
Add a LangChain-compatible tool the agent can call to create “human-in-the-loop” action requests in the `actions` table. The tool lets the LLM specify only: `request_type`, `request_details`, optional `request_data` (JSON), and `priority` (low|medium|high). The system derives and fills multi-tenant context fields (`user_id`, `chatbot_id`, `contact_id`) and status (`pending`) and timestamps.

### 2) Problem & Goals
- Problem: The agent sometimes needs human approval/info to proceed (refunds, policy clarifications, custom quotes). We need a structured, auditable queue for these requests.
- Goals:
  - Provide a safe tool for the LLM to submit action requests with minimal, constrained inputs.
  - Ensure requests are multi-tenant aware and appear in realtime in the Actions Center UI.
  - Make requests observable (LangSmith) and easy to troubleshoot.

### 3) Scope
- In scope:
  - A new LangChain `@tool` function (Python) that creates an action row in DB.
  - Strict input schema and validation (type, details, priority, optional request_data JSON).
  - System-resolved context (user/chatbot/contact IDs) using existing infra.
  - Realtime broadcast of new actions (leveraging existing SQL).
  - Tracing via LangSmith.
- Out of scope (now):
  - Approve/deny endpoints and UI actions.
  - FE Actions page wiring to DB (stub exists; to follow in separate task).

### 4) Users & Actors
- Primary: Business owners/operators who review and resolve actions.
- Secondary: LLM agent which files action requests.

### 5) Data Model (Existing)
`actions` table (already defined): id, user_id, chatbot_id, contact_id, request_type, request_details, request_data JSONB, status (pending/approved/denied/cancelled, default pending), user_response, response_data JSONB, priority (low/medium/high/urgent, default medium), created_at, resolved_at, expires_at. Indexed for user/status/chatbot/contact/priority.

### 6) Tool Design
- Name: `submit_action_request`
- Location: `src/tools/actions_tool.py`
- Signature (LangChain tool):
  - Inputs (LLM-provided):
    - `request_type: str` — short classification (e.g., "refund_request", "policy_clarification").
    - `request_details: str` — concise human-readable context; no PII beyond what’s already in conversation.
    - `priority: Literal["low","medium","high"]` — enforced whitelist; defaults to `medium` if omitted.
    - `request_data: Optional[str]` — JSON string with structured fields when needed; validated and size-capped.
  - Context (system-provided via RunnableConfig.metadata):
    - `from_number` (phone) present like other tools; used to resolve `user_id`, `chatbot_id`, `contact_id`.
  - Behavior:
    1) Resolve multi-tenant context:
       - `get_user_by_phone_number(from_number)` → `{user_id, chatbot_id}`
       - `get_or_create_contact(from_number)` → `(contact_id, thread_id)`
    2) Validate and coerce `priority` to one of [low, medium, high].
    3) Parse `request_data` JSON (if provided) and enforce max size (e.g., 10 KB).
    4) Call `multi_tenant_database.create_action_request(user_id, chatbot_id, contact_id, request_type, request_details, request_data, priority)`.
    5) Return structured response `{success, action_id, status: "pending"}` and a short human-readable summary string.
  - Output (tool return): Simple JSON-like dict (serialized to str by LangChain): `{ "success": true, "action_id": 123, "status": "pending" }` and a concise message.

### 7) Safety & Guardrails
- The tool only accepts and stores: `request_type`, `request_details`, `priority`, optional `request_data`.
- System fills: `user_id`, `chatbot_id`, `contact_id`, `status=pending`, timestamps.
- Validate `priority` ∈ {low, medium, high}. Reject others.
- Validate `request_data` is valid JSON and size-capped; reject if invalid/too large.
- Sanitize strings (length caps: request_type ≤ 100 chars; request_details ≤ 2000 chars).

### 8) Observability
- Decorate with LangSmith `@traceable` and include tags: ["actions", "tool"].
- Attach minimal metadata (action_id on success, failure reason on error). Avoid sensitive data.

### 9) Realtime
- Leverage existing `DATABASE_REALTIME_SETUP.sql` which adds broadcast triggers for `actions`.
- After insert, FE subscribers on `actions:user:{user_id}` will receive notifications.

### 10) Integration Points
- Agent config: add tool name (`submit_action_request`) to `AGENT_CONFIGURATIONS["ecla_sales_agent"].tools` gated by `config.should_use_actions_center()`.
- Backend context: provide `from_number` in `RunnableConfig.metadata` (already done for other tools like `send_product_image`).

### 11) Error Handling
- Missing `from_number` → return `{success:false, error:"missing from_number in metadata"}`.
- No mapping for phone number → fail with clear message; do not attempt insert.
- DB errors → return `{success:false, error:"db_error"}` with log.

### 12) Rollout Plan
- Phase 1: Implement tool and unit tests; wire to agent config behind feature flag (actions center enabled).
- Phase 2: E2E test in staging (tool → DB insert → realtime broadcast). Verify LangSmith traces.
- Phase 3: Enable in production; monitor insert rates and FE notifications.

### 13) Acceptance Criteria
- Tool inserts an `actions` row with correct tenant context and status `pending` using only allowed inputs.
- Priority enforcement works; invalid priority rejected.
- Realtime broadcast observed in logs/Supabase console after insert.
- Trace appears in LangSmith with action_id on success.

### 14) Test Plan (QA)
- Unit: input validation (priority whitelist, JSON parse), size limits, missing metadata.
- Integration: simulate metadata with `from_number`; verify create_action_request invoked and row present with correct values.
- Negative: invalid JSON, oversized `request_data`, unmapped phone, DB failure.
- Realtime: confirm broadcast received on `actions:user:{user_id}`.

### 15) Open Questions
- Should `priority` allow `urgent` (table supports it) or keep LLM choices to low/medium/high? (Current: restrict to 3 values as requested.)
- Do we need a max rate per contact/day to prevent spammy requests by LLM?
- What fields should FE display by default for a generic `request_data` payload?

### 16) Implementation Notes (Dev)
- File: `src/tools/actions_tool.py`
- Pseudocode:
  - Read `from_number` from `config.metadata`.
  - Resolve `{user_id, chatbot_id}` via `get_user_by_phone_number(from_number)`.
  - Resolve `contact_id` via `get_or_create_contact(from_number)` (respecting multi-tenant helper if available).
  - Validate inputs; parse `request_data` JSON if provided.
  - `action_id = db.create_action_request(user_id, chatbot_id, contact_id, request_type, request_details, request_data, priority)`.
  - Return concise success string and dict payload.

### 17) Implementation Checklist (To‑Do)
- [x] Create tool file `src/tools/actions_tool.py` implementing `submit_action_request` with validation and multi-tenant context resolution.
- [x] Enforce priority whitelist (low|medium|high) and length/size caps.
- [x] Parse optional `request_data` JSON with ~10KB limit.
- [x] Integrate with `multi_tenant_database.create_action_request`.
- [x] Add tool to `TOOL_REGISTRY` and conditionally include in `AGENT_CONFIGURATIONS["ecla_sales_agent"].tools` when Actions Center is enabled.
- [ ] (Optional) Add LangSmith `@traceable` for additional observability.
- [ ] (Optional) FE: wire Actions page to query `actions` and subscribe to `actions:user:{user_id}` channel.

