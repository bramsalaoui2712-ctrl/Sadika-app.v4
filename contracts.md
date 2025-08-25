# API Contracts and Integration Plan (Chat IA)

Status: Draft v1 (frontend is mock-only today). This file defines the exact contracts, backend scope, and how we will replace mocks with real endpoints. All backend routes are prefixed with /api.

1) Current Mocking (frontend-only)
- File: /app/frontend/src/mock/mock.js
- Used by: /app/frontend/src/pages/Chat.jsx
- Behavior: simulateAIResponse(text, onToken) emits token-like chunks with delays to emulate streaming.
- Seed messages + quick prompts are local constants.
- No network calls are made yet.

2) Data Models (MongoDB)
- Collection: sessions
  - id: ObjectId
  - sessionId: string (client-generated; persisted)
  - createdAt: ISODate
  - lastActiveAt: ISODate
- Collection: messages
  - id: ObjectId
  - sessionId: string
  - role: "user" | "assistant"
  - content: string
  - ts: ISODate
  - meta?: object (optional provider/raw usage)

3) API Endpoints (FastAPI, Motor, prefix /api)
- POST /api/chat/session
  - Purpose: Ensure a session document exists; upsert by client sessionId.
  - Body: { sessionId: string }
  - 200: { ok: true, sessionId }

- GET /api/chat/history?sessionId=...
  - 200: { sessionId, messages: Message[] }

- POST /api/chat/send
  - Purpose: One-shot non-streaming completion
  - Body: { sessionId: string, message: string, system?: string, model?: string }
  - 200: { message: Message }  // assistant message

- GET /api/chat/stream?sessionId=...&q=...&model=...
  - Purpose: Server-Sent Events (SSE) streaming tokens
  - Response: text/event-stream
    - data: { type: "chunk", content: string } ... multiple times
    - data: { type: "done", message: Message }

- Notes
  - All endpoints are CORS-enabled.
  - Business logic: store both user and assistant messages; keep lastActiveAt fresh.
  - If no LLM key configured (or user opted to mock), /api/chat/stream will stream a deterministic mock to keep UX consistent.

4) LLM Integration (Emergent Integrations)
- Provider: Emergent Integrations library (uses Universal Key to route to OpenAI / Anthropic / Google)
- We will request the Universal Key from the user and place it in backend/.env as EMERGENT_LLM_KEY (do not change MONGO_URL or ports).
- Default model (can change later): Anthropic Claude Sonnet (balanced). Frontend may pass model to switch dynamically.
- Streaming: Implemented server-side; SSE to client.

5) Frontend ↔ Backend Integration Changes
- Replace simulateAIResponse in Chat.jsx with:
  - On first load: GET /api/chat/history?sessionId=...
  - On send:
    - POST user message to /api/chat/send (optional) or initiate GET /api/chat/stream with EventSource to stream assistant reply
  - Persist messages in local state; also rely on server history for reloads.
- Strict URL usage
  - Frontend uses process.env.REACT_APP_BACKEND_URL + "/api"
  - No hardcoded URLs/ports in code.

6) Error Handling
- 400: validation errors (missing sessionId/message)
- 401: missing/invalid LLM key (when real provider required)
- 429: provider rate limit bubbled to client
- 500: unexpected errors; message: human-readable, requestId in logs

7) Testing Plan
- Backend first: deep_testing_backend_v2 against endpoints (history, session, stream mock)
- After backend passes, ask user before automated frontend testing. Replace mock on FE and verify SSE stream.

8) Rollout Plan
- Phase A: Implement endpoints with mock fallback (requires user approval to mock).
- Phase B: Wire Emergent Integrations with Universal Key; enable real LLM streaming.
- Phase C: Switch FE to backend endpoints, remove /mock usage.
