"""
Adapter pour intégrer le noyau Al Sâdika au backend FastAPI.
- Gère des orchestrateurs par session (mémoire locale du noyau reste sur disque .alsadika/)
- Expose une API simple: run_kernel(session_id, prompt, mode)
"""
from typing import Dict
from al_sadika_core_v2 import Verrou, Memory, LanguageEngine, LogicEngine, ActionEngine, Orchestrator

_sessions: Dict[str, Orchestrator] = {}

def get_orchestrator(session_id: str, mode: str = "public") -> Orchestrator:
    if session_id in _sessions:
        return _sessions[session_id]
    orch = Orchestrator(Verrou(True), Memory.load(), LanguageEngine(skills=__get_skills()), LogicEngine(), ActionEngine(), mode=mode)
    _sessions[session_id] = orch
    return orch

# recrée un registre de compétences en important depuis le noyau
from al_sadika_core_v2 import SkillRegistry as _SkillRegistry

def __get_skills():
    return _SkillRegistry()

def run_kernel(session_id: str, prompt: str, mode: str = "public") -> str:
    orch = get_orchestrator(session_id, mode)
    out = orch.handle(prompt)
    return out or ""