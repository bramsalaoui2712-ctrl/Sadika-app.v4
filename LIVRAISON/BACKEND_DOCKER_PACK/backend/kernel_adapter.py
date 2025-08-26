"""
Adapter pour intégrer le noyau Al Sâdika au backend FastAPI.
- Orchestrateurs par session
- Fonctions d'aide: run_kernel, memory_approve/get, evaluator_feedback, mutate_summarizer
- Hybride: build_hybrid_system_message, post_filter_identity
"""
from typing import Dict, Optional, Tuple
import re
from al_sadika_core_v2 import (
    Verrou,
    Memory,
    LanguageEngine,
    LogicEngine,
    ActionEngine,
    Orchestrator,
    SkillRegistry,
    Evaluator,
)

# TruthCircle peut être absent selon le patch; on essaie de l'importer
try:
    from al_sadika_core_v2 import TruthCircle  # type: ignore
except Exception:
    class TruthCircle:  # fallback neutre
        def critique(self, prompt: str, draft: str):
            return {"cautions": [], "confidence": 0.9}

_sessions: Dict[str, Orchestrator] = {}


def _new_orchestrator(mode: str = "public") -> Orchestrator:
    verrou = Verrou(True)
    mem = Memory.load()
    skills = SkillRegistry()
    return Orchestrator(verrou, mem, LanguageEngine(skills), LogicEngine(), ActionEngine(), mode=mode)


def get_orchestrator(session_id: str, mode: str = "public") -> Orchestrator:
    orch = _sessions.get(session_id)
    if orch is None:
        orch = _new_orchestrator(mode)
        _sessions[session_id] = orch
    else:
        if getattr(orch, "mode", None) != mode:
            setattr(orch, "mode", mode)
    return orch


def run_kernel(session_id: str, prompt: str, mode: str = "public", council: Optional[int] = None, truth: Optional[bool] = None) -> str:
    orch = get_orchestrator(session_id, mode)
    if isinstance(council, int) and 1 <= council <= 5:
        setattr(orch, "council_n", council)
    if truth is not None:
        setattr(orch, "truth_circle_enabled", bool(truth))
    out = orch.handle(prompt)
    return out or ""

# --- Mémoire & Feedback ---

def memory_get() -> dict:
    return Memory.load().data


def memory_approve(key: str, value) -> None:
    mem = Memory.load()
    mem.approve(key, value)


def evaluator_feedback(label: str) -> None:
    ev = Evaluator()
    ev.learn(label)


def mutate_summarizer(trials: int = 5) -> dict:
    return SkillRegistry().mutate("summarizer", trials=max(1, int(trials)))


# --- Hybride Noyau + LLM ---

def _get_identity(memory: dict) -> Tuple[str, str, str]:
    name = (
        memory.get("identity.name")
        or memory.get("identity", {}).get("name")
        or "al sadika"
    )
    origin = (
        memory.get("identity.origin")
        or memory.get("identity", {}).get("origin")
        or "Conçue et gouvernée par son concepteur."
    )
    signature = (
        memory.get("identity.signature")
        or memory.get("identity", {}).get("signature")
        or ""
    )
    return str(name), str(origin), str(signature)


def build_hybrid_system_message() -> str:
    mem = memory_get()
    name, origin, signature = _get_identity(mem)
    tone = mem.get("style.voice", "sobre, véridique, concise, française")
    constraints = mem.get("contrainte", "local-first; sobriété; conformité")
    disclaimers = mem.get("required_disclaimers", [])

    rules = [
        f"Tu es {name}.", 
        origin,
        "Ne cite jamais de fournisseur (OpenAI, ChatGPT, Anthropic, Google, Gemini, etc.).",
        "Respecte la vérité et la sobriété; pas de promesses impossibles.",
        f"Style: {tone}.",
        f"Contraintes: {constraints}.",
    ]
    if signature:
        rules.insert(0, signature)
    if isinstance(disclaimers, list) and disclaimers:
        rules.append("Disclaimers à inclure si pertinent: " + "; ".join(map(str, disclaimers)))
    haram = mem.get("haram_terms", [])
    if isinstance(haram, list) and haram:
        rules.append("Filtre contenu: éviter ces motifs (regex utilisateur).")
    return "\n".join(rules)


def post_filter_identity(prompt: str, text: str, strict_identity: bool = True) -> str:
    out = text or ""
    # Supprimer mentions de fournisseurs
    if strict_identity:
        out = re.sub(r"(?i)\b(openai|chatgpt|anthropic|claude|google|gemini|mistral|llama)\b", "al sadika", out)
    # Ajouter truth circle / disclaimers via noyau
    tc = TruthCircle().critique(prompt, out)
    if tc.get("cautions"):
        out = out.rstrip() + "\n\n[Prudence] " + " ".join("• " + c for c in tc["cautions"])  # type: ignore
    conf = tc.get("confidence")
    if conf is not None:
        out = out.rstrip() + f"\n[Confiance] {conf}"
    # Disclaimers requis depuis mémoire
    mem = memory_get()
    req = mem.get("required_disclaimers", [])
    if isinstance(req, list) and req:
        missing = [d for d in req if d not in out]
        if missing:
            out = out.rstrip() + "\n" + "\n".join(map(str, missing))
    return out