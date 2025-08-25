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
# Kernel adapter
try:
    from kernel_adapter import (
        run_kernel,
        memory_get,
        memory_approve,
        evaluator_feedback,
        mutate_summarizer,
        build_hybrid_system_message,
        post_filter_identity,
    )
except Exception:
    run_kernel = None

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env', override=True)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# LLM Key flag
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')
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
    provider: Optional[str] = Field(default="kernel", description="kernel|hybrid|openai|anthropic|google")
    model: Optional[str] = Field(default="local", description="model name for provider")
    temperature: Optional[float] = None
    max_tokens: Optional[int] = 1024
    mode: Optional[str] = Field(default="public", description="public|private (noyau)")
    council: Optional[int] = Field(default=1, ge=1, le=5)
    truth: Optional[bool] = Field(default=True)
    strict_identity: Optional[bool] = Field(default=True)
    refusal_handling: Optional[bool] = Field(default=True)

class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: List[Dict[str, Any]]

SESSION_COL = "chat_sessions"

async def ensure_session(session_id: Optional[str]) -> str:
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
    sid = await ensure_session(payload.session_id)
    await append_message(sid, "user", payload.message)
    yield f"data: {json.dumps({'type': 'session', 'session_id': sid})}\n\n"

    history = await get_history(sid)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    full = ""
    try:
        provider = (payload.provider or "kernel").lower()
        if provider == "kernel" and run_kernel is not None:
            final_text = run_kernel(sid, payload.message, mode=(payload.mode or "public"), council=payload.council, truth=payload.truth)
            for part in final_text.split(" "):
                full += part + " "
                yield f"data: {json.dumps({'type': 'content', 'content': part + ' '})}\n\n"
                await asyncio.sleep(0.005)
        elif provider == "hybrid" and llm_client and EMERGENT_LLM_KEY:
            # 1) Construire system prompt identitaire via noyau
            sysmsg = build_hybrid_system_message()
            # 2) Appel LLM (OpenAI path par défaut pour Universal Key)
            prov = "openai"
            modl = payload.model or "gpt-4o-mini"
            chat = (
                LlmChat(api_key=EMERGENT_LLM_KEY, session_id=sid, system_message=sysmsg, initial_messages=[])
                .with_model(prov, modl)
                .with_params(max_tokens=payload.max_tokens or 1024)
            )
            raw = await chat.send_message(UserMessage(text=payload.message))
            # 3) Post-filtre identité et vérité par noyau
            filtered = post_filter_identity(payload.message, raw, strict_identity=bool(payload.strict_identity))
            for part in filtered.split(" "):
                full += part + " "
                yield f"data: {json.dumps({'type': 'content', 'content': part + ' '})}\n\n"
                await asyncio.sleep(0.008)
        else:
            # Fallback LLM simple
            prov = provider
            modl = (payload.model or "o4-mini")
            if prov == "google":
                prov = "gemini"
            if prov != "gemini":
                prov = "openai"
                if not (modl.startswith("gpt-") or modl.startswith("o4") or modl.startswith("gpt4") or modl.startswith("o3")):
                    modl = "o4-mini"
            chat = (LlmChat(api_key=EMERGENT_LLM_KEY, session_id=sid, system_message="Tu es al sadika.", initial_messages=messages)
                    .with_model(prov, modl)
                    .with_params(max_tokens=payload.max_tokens or 1024))
            final_text = await chat.send_message(UserMessage(text=payload.message))
            filtered = post_filter_identity(payload.message, final_text, strict_identity=True)
            for part in filtered.split(" "):
                full += part + " "
                yield f"data: {json.dumps({'type': 'content', 'content': part + ' '})}\n\n"
                await asyncio.sleep(0.01)

        await append_message(sid, "assistant", full.strip(), meta={
            "provider": provider,
            "model": payload.model,
            "mode": payload.mode,
            "council": payload.council,
            "truth": payload.truth,
            "strict_identity": payload.strict_identity,
        })
        yield f"data: {json.dumps({'type': 'complete', 'session_id': sid})}\n\n"
    except Exception as e:
        logging.exception("Kernel/LLM streaming error")
        if not full:
            demo = "Désolé, le service a rencontré un souci."
            for token in demo.split(" "):
                yield f"data: {json.dumps({'type': 'content', 'content': token + ' '})}\n\n"
                await asyncio.sleep(0.02)
            await append_message(sid, "assistant", demo, meta={"error": str(e)})
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
async def chat_stream_get(q: str, sessionId: Optional[str] = None, provider: Optional[str] = None, model: Optional[str] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = 1024, mode: Optional[str] = "public", council: Optional[int] = 1, truth: Optional[bool] = True, strict_identity: Optional[bool] = True, refusal_handling: Optional[bool] = True):
    input = ChatStreamInput(
        message=q,
        session_id=sessionId,
        provider=provider or "kernel",
        model=model or ("gpt-4o-mini" if (provider or "").lower()=="hybrid" else "local"),
        temperature=temperature,
        max_tokens=max_tokens,
        mode=mode,
        council=council,
        truth=truth,
        strict_identity=strict_identity,
        refusal_handling=refusal_handling,
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

# ======== Kernel Admin Endpoints ========
class MemoryApproveBody(BaseModel):
    key: str
    value: Any

class FeedbackBody(BaseModel):
    label: str  # "approve" | "reject"

class MutateBody(BaseModel):
    trials: Optional[int] = 5

@api_router.get("/kernel/memory")
async def kernel_memory():
    try:
        return {"ok": True, "memory": memory_get()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/kernel/memory/approve")
async def kernel_memory_approve(body: MemoryApproveBody):
    try:
        memory_approve(body.key, body.value)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/kernel/feedback")
async def kernel_feedback(body: FeedbackBody):
    try:
        if body.label not in ("approve", "reject"):
            raise HTTPException(status_code=400, detail="label invalide")
        evaluator_feedback(body.label)
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/kernel/mutate")
async def kernel_mutate(body: MutateBody):
    try:
        res = mutate_summarizer(body.trials or 5)
        return {"ok": True, "result": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()