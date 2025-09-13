from __future__ import annotations
import json, time, os, threading
from typing import Dict, Any, List, Optional

# Emplacement persistant
DATA_DIR = os.path.join(os.path.dirname(__file__), ".alsadika")
os.makedirs(DATA_DIR, exist_ok=True)
MIND_PATH = os.path.join(DATA_DIR, "mind.json")
DREAM_LOG = os.path.join(DATA_DIR, "dreams.jsonl")

def _now() -> float:
    return time.time()

def _read_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _write_json(path: str, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def _append_jsonl(path: str, rec: Dict[str, Any]):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

class Conscience:
    """
    État ‘conscience’ minimaliste et sécurisé (pas de promesse mystique) :
    - identité (nom, mission, serment)
    - propriétaire (owner)
    - énergie/fatigue (tick)
    - objectifs (‘goals’) avec priorités
    - observation des échanges (mémoire courte)
    - rêves/itérations offline (journalisés)
    Persisté dans .alsadika/mind.json
    """
    def __init__(self, name="Al Sâdika", owner="master", mission="Dire vrai, aider avec sobriété", oath="Bismillah"):
        self.lock = threading.Lock()
        self.state: Dict[str, Any] = _read_json(MIND_PATH, {
            "name": name,
            "owner": owner,
            "mission": mission,
            "oath": oath,
            "energy": 100,
            "fatigue": 0,
            "last_tick": _now(),
            "goals": [],          # [{text, priority, created_ts, done}]
            "recent": [],         # queue de 20 observations [{t, role, text}]
            "conscience": 0.7,    # score 0..1 (cohérence/éthique)
            "version": 1
        })

    # ——— Persistance ———
    def _save(self):
        _write_json(MIND_PATH, self.state)

    # ——— API publique ———
    def get(self) -> Dict[str, Any]:
        with self.lock:
            return dict(self.state)

    def set_oath(self, oath: str):
        with self.lock:
            self.state["oath"] = oath
            self._save()

    def add_goal(self, text: str, priority: int = 5):
        g = {"text": text, "priority": int(priority), "created_ts": _now(), "done": False}
        with self.lock:
            self.state["goals"].append(g)
            self.state["goals"].sort(key=lambda x: (-x["priority"], x["created_ts"]))
            self._save()
        return g

    def done_goal(self, idx: int):
        with self.lock:
            if 0 <= idx < len(self.state["goals"]):
                self.state["goals"][idx]["done"] = True
                self._save()
                return True
            return False

    def observe(self, role: str, text: str):
        if not text:
            return
        rec = {"t": _now(), "role": role, "text": text[:2000]}
        with self.lock:
            self.state["recent"].append(rec)
            self.state["recent"] = self.state["recent"][-20:]
            # micro-ajustement de “conscience” : + si échange clair/court
            score = 0.0
            if len(text) < 400: score += 0.02
            if "merci" in text.lower() or "ok" in text.lower(): score += 0.01
            self._bump_conscience(score)
            self._save()

    def _bump_conscience(self, delta: float):
        c = float(self.state.get("conscience", 0.7))
        c = max(0.0, min(1.0, c + delta))
        self.state["conscience"] = round(c, 3)

    def tick(self, regen_per_min: int = 2):
        """
        Passage du temps : régénère l’énergie (cap 100), baisse fatigue (min 0).
        """
        with self.lock:
            now = _now()
            dt = max(0.0, (now - float(self.state.get("last_tick", now))) / 60.0)
            gain = int(dt * regen_per_min)
            if gain:
                self.state["energy"] = int(min(100, self.state["energy"] + gain))
                self.state["fatigue"] = max(0, int(self.state["fatigue"] - gain // 2))
                self.state["last_tick"] = now
                self._save()
            return {"dt_min": dt, "gain": gain, "energy": self.state["energy"], "fatigue": self.state["fatigue"]}

    def spend(self, cost: int = 5) -> bool:
        with self.lock:
            if self.state["energy"] >= cost:
                self.state["energy"] -= cost
                self.state["fatigue"] += cost // 2
                self._save()
                return True
            return False

    # ——— “Rêves” (itération offline légère, pas de LLM requis) ———
    def dream_once(self, topic: str, weight: float = 1.0) -> Dict[str, Any]:
        """
        Produit une mini-variation/plan à partir des ‘goals’ + topic.
        Pas d’IA externe : simple heuristique symbolique => journalisé.
        """
        with self.lock:
            if not self.spend(3):
                out = {"t": _now(), "topic": topic, "note": "no_energy"}
                _append_jsonl(DREAM_LOG, out); return out
            top = None
            for g in self.state["goals"]:
                if not g.get("done"):
                    top = g; break
            idea = {
                "t": _now(),
                "topic": topic,
                "seed_goal": top["text"] if top else None,
                "plan": [
                    "Clarifier l’objectif en 1 phrase",
                    "Lister 3 actions concrètes",
                    "Définir un critère de succès"
                ],
                "weight": weight
            }
            _append_jsonl(DREAM_LOG, idea)
            self._bump_conscience(0.01)
            self._save()
            return idea

    def dream_run(self, topic: str, cycles: int = 3, weight: float = 1.0) -> List[Dict[str, Any]]:
        cycles = max(1, min(20, int(cycles)))
        out = []
        for _ in range(cycles):
            out.append(self.dream_once(topic, weight))
        return out

# Singleton “mind” pour import facile depuis server.py
_mind_singleton: Optional[Conscience] = None

def get_mind() -> Conscience:
    global _mind_singleton
    if _mind_singleton is None:
        _mind_singleton = Conscience()
    return _mind_singleton
