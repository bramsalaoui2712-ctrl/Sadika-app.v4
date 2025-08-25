from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, AsyncGenerator, Dict, Any
import uuid
from datetime import datetime
import json
import asyncio

# LLM integration (Emergent Integrations)
from emergentintegrations.llm.chat import LlmChat, UserMessage


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env', override=True)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# LLM Client
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')
if not EMERGENT_LLM_KEY:
    logging.warning("EMERGENT_LLM_KEY missing. /api/chat will run in mock mode.")
llm_client = True if EMERGENT_LLM_KEY else None  # flag only; we instantiate LlmChat per-request

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# ======== Existing Demo Models & Routes ========
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.dict()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.dict())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]


# ======== Chat Models & Helpers ========
class ChatStreamInput(BaseModel):
    message: str
    session_id: Optional[str] = None
    provider: Optional[str] = Field(default="openai", description="openai|anthropic|google")
    model: Optional[str] = Field(default="claude-3-sonnet", description="model name for provider")
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1024

class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: List[Dict[str, Any]]

SESSION_COL = "chat_sessions"

async def ensure_session(session_id: Optional[str]) -> str:
    """Return a valid session_id; create session doc if new."""
    sid = session_id or (str(uuid.uuid4()))
    existing = await db[SESSION_COL].find_one({"session_id": sid})
    if not existing:
        await db[SESSION_COL].insert_one({
            "session_id": sid,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "messages": []
        })
    return sid

async def append_message(session_id: str, role: str, content: str, meta: Optional[Dict[str, Any]] = None):
    await db[SESSION_COL].update_one(
        {"session_id": session_id},
        {
            "$push": {"messages": {"role": role, "content": content, "ts": datetime.utcnow(), "meta": meta or {}}},
            "$set": {"updated_at": datetime.utcnow()}
        },
        upsert=True
    )

async def get_history(session_id: str) -> List[Dict[str, Any]]:
    doc = await db[SESSION_COL].find_one({"session_id": session_id})
    return (doc or {}).get("messages", [])


# ======== Chat Endpoints ========
@api_router.get("/chat/history", response_model=ChatHistoryResponse)
async def chat_history(sessionId: str):
    if not sessionId:
        raise HTTPException(status_code=400, detail="sessionId required")
    msgs = await get_history(sessionId)
    return {"session_id": sessionId, "messages": msgs}


async def sse_chat_generator(payload: ChatStreamInput) -> AsyncGenerator[str, None]:
    """SSE generator that streams LLM tokens or a server-side mock if no key."""
    # 1) Ensure session
    sid = await ensure_session(payload.session_id)
    
    # 2) Persist user message
    await append_message(sid, "user", payload.message)

    # 3) Send session event first
    yield f"data: {json.dumps({'type': 'session', 'session_id': sid})}\n\n"

    # 4) Build messages from history for context
    history = await get_history(sid)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    # 5) Stream from real LLM if key present, else mock
    full = ""
    try:
        if llm_client:
            # Real LLM streaming via Emergent Integrations
            # Build a new LlmChat per-request to set model/provider
            chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=sid, system_message="Tu es une IA utile.", initial_messages=messages).with_model(payload.provider or "anthropic", payload.model or "claude-3-sonnet").with_params(temperature=payload.temperature or 0.7, max_tokens=payload.max_tokens or 1024)
            # Non-streaming method in this library; emulate streaming by chunking the final text
            final_text = await chat.send_message(UserMessage(text=payload.message))
            for part in final_text.split(" "):
                full += part + " "
                yield f"data: {json.dumps({'type': 'content', 'content': part + ' '})}\n\n"
                await asyncio.sleep(0.01)
        else:
            # Server-side mock stream (deterministic)
            demo = f"Bonjour ! Tu as dit: {payload.message}\n\nJe peux t'aider étape par étape."
            for token in demo.split(" "):
                full += (token + " ")
                yield f"data: {json.dumps({'type': 'content', 'content': token + ' '})}\n\n"
                await asyncio.sleep(0.02)

        # 6) Save assistant message
        await append_message(sid, "assistant", full, meta={"provider": payload.provider, "model": payload.model})

        yield f"data: {json.dumps({'type': 'complete', 'session_id': sid})}\n\n"
    except Exception as e:
        logging.exception("LLM streaming error")
        # Fallback to mock continuation for UX
        if not full:
            demo = "Désolé, le service IA est momentanément indisponible. Voici un aperçu: "
            for token in demo.split(" "):
                yield f"data: {json.dumps({'type': 'content', 'content': token + ' '})}\n\n"
                await asyncio.sleep(0.02)
            full = demo
            await append_message(sid, "assistant", full, meta={"error": str(e)})
            yield f"data: {json.dumps({'type': 'complete', 'session_id': sid})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"


@api_router.post("/chat/stream")
async def chat_stream(input: ChatStreamInput):
    return StreamingResponse(
        sse_chat_generator(input),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        },
    )

@api_router.get("/chat/stream")
async def chat_stream_get(q: str, sessionId: Optional[str] = None, provider: Optional[str] = None, model: Optional[str] = None, temperature: Optional[float] = 0.7, max_tokens: Optional[int] = 1024):
    input = ChatStreamInput(
        message=q,
        session_id=sessionId,
        provider=provider or "anthropic",
        model=model or "claude-3-sonnet",
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return StreamingResponse(
        sse_chat_generator(input),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        },
    )


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()