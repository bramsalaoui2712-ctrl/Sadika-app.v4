import os, json, time
from typing import Iterable, List, Dict, Optional
import httpx

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")

def _headers():
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY manquant dans l'environnement.")
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "alsadika.local",
        "X-Title": "Al Sadika",
    }

def stream_chat(messages: List[Dict[str,str]], model: Optional[str]=None) -> Iterable[str]:
    """
    Renvoie un flux de tokens (strings) depuis OpenRouter.
    """
    mdl = model or MODEL
    url = f"{BASE}/chat/completions"
    body = {
        "model": mdl,
        "messages": messages,
        "stream": True,
    }
    with httpx.stream("POST", url, headers=_headers(), json=body, timeout=120) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line: 
                continue
            if line.startswith(b"data: "):
                payload = line[6:]
                if payload == b"[DONE]":
                    break
                try:
                    j = json.loads(payload.decode("utf-8"))
                    delta = j.get("choices",[{}])[0].get("delta",{}).get("content","")
                    if delta:
                        yield delta
                except Exception:
                    # on ignore les lignes non parseables
                    pass
