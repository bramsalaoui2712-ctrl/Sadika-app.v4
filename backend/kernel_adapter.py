"""
Adapter pour intégrer le noyau Al Sâdika au backend FastAPI.
- Orchestrateurs par session
- Fonctions d'aide: run_kernel, memory_approve, memory_get, evaluator_feedback, mutate_summarizer
"""
from typing import Dict, Optional
from al_sadika_core_v2 import Verrou, Memory, LanguageEngine, LogicEngine, ActionEngine, Orchestrator, SkillRegistry, Evaluator

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
        # mettre à jour le mode si changé
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