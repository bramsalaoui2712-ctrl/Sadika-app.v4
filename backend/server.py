import os, json
from typing import Optional, List, Dict
from datetime import datetime
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

try:
    from .llm_client import stream_chat
except ImportError:
    from llm_client import stream_chat

# Noyau (kernel/Hakim)
from al_sadika_core_v2 import kernel_run  # présent dans ton repo

app = FastAPI(title="Al Sadika Backend")

from jwt_guard import verify_request
@app.middleware("http")
async def _jwt_guard(request: Request, call_next):
    if await verify_request(request):
        return await call_next(request)
    from starlette.responses import JSONResponse
    return JSONResponse({"detail":"Unauthorized"}, status_code=401)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

IDENTITY = os.getenv("ALSADIKA_IDENTITY", "Tu es Al Sâdika, assistante véridique et souveraine. Réponds en français, brièvement, sans branding externe.")
DISCLAIMER = os.getenv("ALSADIKA_DISCLAIMER", "Al Sâdika est un outil d'assistance, elle ne remplace ni mufti ni décision personnelle.")

@app.get("/api/health")
def health():
    return {"status":"ok","ts":datetime.utcnow().isoformat()}

def _system_prompt() -> str:
    return f"""{IDENTITY}
Contraintes:
- Respect strict du cadre islamique.
- Aucune marque de LLM/tiers.
- Style: direct, concis, humain.
- Ajoute ce rappel discret si pertinent: {DISCLAIMER}"""

def _build_messages(q: str) -> List[Dict[str,str]]:
    return [{"role":"system","content":_system_prompt()},
            {"role":"user","content":q}]

@app.get("/api/chat/stream")
def chat_stream(
    q: str = Query(..., min_length=1),
    provider: str = Query("hybrid"),   # <-- défaut = LLM RÉEL
    model: Optional[str] = Query(None),
    sessionId: Optional[str] = None,
    truth: Optional[str] = None,
    council: Optional[str] = None,
    strict_identity: Optional[str] = None
):
    # ----- Mode noyau local (sans LLM) -----
    if provider == "kernel":
        def sse():
            sid = sessionId or "s-"+datetime.utcnow().isoformat()
            yield f"data: {json.dumps({'type':'session','session_id':sid}, ensure_ascii=False)}\n\n"
            try:
                out = kernel_run(q, use_dream=False, rag_k=0)
                yield f"data: {json.dumps({'type':'content','text':out}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type':'content','text':'[ERREUR noyau] '+str(e)}, ensure_ascii=False)}\n\n"
            yield "data: {\"type\":\"complete\"}\n\n"
        return EventSourceResponse(sse(), media_type="text/event-stream")

    # ----- Mode LLM réel (hybrid) -----
    messages = _build_messages(q)

    def sse_llm():
        sid = sessionId or "s-"+datetime.utcnow().isoformat()
        yield f"data: {json.dumps({'type':'session','session_id':sid}, ensure_ascii=False)}\n\n"
        try:
            for chunk in stream_chat(messages, model=model):
                yield f"data: {json.dumps({'type':'content','text':chunk}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'content','text':'[ERREUR LLM] '+str(e)}, ensure_ascii=False)}\n\n"
        yield "data: {\"type\":\"complete\"}\n\n"

    return EventSourceResponse(sse_llm(), media_type="text/event-stream")
