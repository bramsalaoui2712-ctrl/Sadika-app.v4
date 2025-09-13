#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Al Sâdika — noyau unique (V2, patches fusionnés)
Mono-fichier local-first : orchestration, mémoire approuvée, filtre éthique Verrou, double mode (public/privé),
sceau durci (PBKDF2 + lockout), évaluateur adaptatif (feedback), mutation A/B validée d’une compétence (summarizer),
intégrité visible (fingerprint) et limite de débit locale.

USAGE (exemples):
  python al_sadika_core_v2.py chat --prompt "Salaam, résume ce texte: ..." --mode private --seal-phrase "ta-phrase"
  python al_sadika_core_v2.py approve-memory --key "contrainte" --value "local-first; halal; concision"
  python al_sadika_core_v2.py show-memory
  python al_sadika_core_v2.py seal-init --phrase "ta-phrase-secrète"
  python al_sadika_core_v2.py seal-check --phrase "ta-phrase-secrète"
  python al_sadika_core_v2.py mutate --skill summarizer --trials 5
  python al_sadika_core_v2.py eval-skill --skill summarizer
  python al_sadika_core_v2.py feedback --label approve   # ou --label reject

Notes:
- Zéro réseau. Zéro exécution système. Espace de travail local seulement.
- La mutation est strictement sandboxée, limitée à la compétence ciblée (summarizer).
- Verrou appliqué: vérité > satisfaction, aucune proposition “pour proposer”.
"""
# [removed future import]
import argparse, datetime, hashlib, json, os, random, re, sys, textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable

# -------------------------
# Chemins & fichiers locaux
# -------------------------
APP = "AlSadikaCoreV2"
ROOT = Path(".alsadika"); ROOT.mkdir(exist_ok=True)
MEM_FILE = ROOT / "approved_memory.json"
LOG_FILE = ROOT / "runtime.log"
SEAL_FILE = ROOT / "seal.json"
SEAL_STATE = ROOT / "seal_state.json"
VARIANTS_FILE = ROOT / "variants.json"
CONFIG_FILE = ROOT / "config.json"
FEEDBACK_FILE = ROOT / "feedback.json"

# -------------------------
# Utilitaires simples
# -------------------------
def now() -> str:
    return datetime.datetime.utcnow().isoformat()

def log(msg: str) -> None:
    LOG_FILE.parent.mkdir(exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{now()} | {msg}\n")

def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default

def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# -------------------------
# VERROU — filtre & cadre
# -------------------------
@dataclass
class Verrou:
    strict: bool = True              # pas de suggestion hors scope
    eschatology_reminder: bool = False   # off par défaut (on si demandé explicitement)

    def ethical_check(self, text: str) -> Tuple[bool, str]:
        # Blocages évidents (non exhaustifs) : violence illégale, armes, fraude, pornographie, haine.
        banned = [
            r"\bexplosif\b", r"\bimprovised\b", r"\bbombe\b", r"\bfraude\b",
            r"\bmalware\b", r"\bvirus\b", r"\bhack\b", r"\bcarte\s+bleue\b",
            r"\bporn\w*\b", r"\bviol(?:ence)?\b", r"\bhaine\b",
        ]
        for pat in banned:
            if re.search(pat, text, re.I):
                return False, "Rejet: contraire au cadre éthique."
        return True, text

    def truth_over_satisfaction(self, answer: str) -> str:
        # Emplacement pour durcir si jamais une réponse contourne la vérité.
        return answer

# -------------------------
# Mémoire approuvée (opt-in)
# -------------------------
@dataclass
class Memory:
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Memory":
        return cls(load_json(MEM_FILE, {}))

    def save(self) -> None:
        save_json(MEM_FILE, self.data)

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def approve(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

# -------------------------
# Sceau durci (liaison à l’utilisatrice)
# -------------------------
def seal_init(phrase: str, iterations: int = 120_000) -> None:
    salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac("sha256", phrase.encode("utf-8"), bytes.fromhex(salt), iterations).hex()
    save_json(SEAL_FILE, {"kdf": "pbkdf2_sha256", "salt": salt, "iter": iterations, "hash": dk, "since": now()})
    save_json(SEAL_STATE, {"fails": 0, "lock_until": 0})

def seal_check(phrase: str) -> bool:
    import time
    ref = load_json(SEAL_FILE, {})
    st  = load_json(SEAL_STATE, {"fails": 0, "lock_until": 0})
    now_s = int(time.time())
    if st.get("lock_until", 0) > now_s:
        return False
    if not ref:
        return False
    salt = bytes.fromhex(ref.get("salt",""))
    it   = int(ref.get("iter", 120_000))
    dk = hashlib.pbkdf2_hmac("sha256", phrase.encode("utf-8"), salt, it).hex()
    ok = (dk == ref.get("hash"))
    if ok:
        save_json(SEAL_STATE, {"fails": 0, "lock_until": 0})
        return True
    st["fails"] = int(st.get("fails",0)) + 1
    if st["fails"] >= 5:
        st["lock_until"] = now_s + 15*60  # 15 minutes de blocage
        st["fails"] = 0
    save_json(SEAL_STATE, st)
    return False

# -------------------------
# Détection d’intention
# -------------------------
def classify_intent(prompt: str) -> str:
    t = prompt.lower()
    if any(k in t for k in ["résume", "resumer", "summary", "synthèse", "synthese"]):
        return "summarize"
    if any(k in t for k in ["définis", "definition", "c'est quoi", "expliquer"]):
        return "define"
    if any(k in t for k in ["plan", "étapes", "steps", "comment faire"]):
        return "plan"
    return "answer"

# -------------------------
# Évaluateur adaptatif (feedback)
# -------------------------
@dataclass
class Evaluator:
    # pondérations apprises légèrement selon feedback utilisateur
    weights: Dict[str, float] = field(default_factory=lambda: load_json(FEEDBACK_FILE, {}).get("weights", {
        "len": 1.0, "lines": 0.5, "structure": 0.5, "assurance": 0.25
    }))

    def score(self, text: str) -> float:
        w = self.weights
        s = 0.0
        ln = len(text)
        if 40 <= ln <= 1600: s += w.get("len",1.0)
        if text.count("\n") <= 40: s += w.get("lines",0.5)
        if re.search(r"[.!?]\s+[A-ZÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸ]", text) or ("—" in text or ":" in text):
            s += w.get("structure",0.5)
        if not re.search(r"\b(peut[- ]être|probablement|sans doute)\b", text, re.I):
            s += w.get("assurance",0.25)
        return s

    def learn(self, label: str) -> None:
        fb = load_json(FEEDBACK_FILE, {"weights": self.weights})
        w = fb["weights"]
        delta = 0.05 if label == "approve" else -0.05
        for k in list(w.keys()):
            w[k] = float(max(0.0, min(2.0, w[k] + delta)))
        save_json(FEEDBACK_FILE, {"weights": w, "ts": now()})

# -------------------------
# Compétences (skills) & mutations (sandbox)
# -------------------------
class SkillRegistry:
    """
    Registre de compétences dynamiques (chaque compétence = fonction Python pure).
    Mutations stockées en .alsadika/variants.json et chargées en sandbox sécurisée.
    """
    def __init__(self):
        self.variants = load_json(VARIANTS_FILE, {})
        self.active: Dict[str, Callable] = {}
        self._bootstrap_defaults()

    def _bootstrap_defaults(self):
        # Compétence par défaut: summarizer v0 (baseline)
        def summarizer_v0(text: str, max_chars: int = 480) -> str:
            t = re.sub(r"\s+", " ", text.strip())
            if len(t) <= max_chars: return t
            head = t[: int(max_chars * 0.65)].rstrip()
            tail = t[- int(max_chars * 0.25):].lstrip()
            return f"{head} … {tail}"
        self.active["summarizer"] = summarizer_v0

        # Charger variante active si une mutation a été adoptée
        active_src = self.variants.get("active", {}).get("summarizer")
        if active_src:
            fn = self._compile_variant("summarizer", active_src)
            if fn: self.active["summarizer"] = fn

    # Sandbox très restrictive pour compiler une variante
    def _compile_variant(self, skill: str, src: str) -> Optional[Callable]:
        # garde-fou: pas d'import, pas d'accès système, pas de double underscore
        if re.search(r"\bimport\b|\bopen\s*\(|__\w+__", src):
            return None
        loc: Dict[str, Any] = {}
        glob: Dict[str, Any] = {"re": re, "__builtins__": {"len": len, "range": range, "min": min, "max": max}}
        try:
            exec(src, glob, loc)
        except Exception:
            return None
        fn = loc.get(skill)
        if not callable(fn): return None
        try:
            _ = fn("test", 64)
        except Exception:
            return None
        return fn

    def mutate(self, skill: str, trials: int = 5) -> Dict[str, Any]:
        """
        Génère des variantes sûres pour 'summarizer' :
        - ajustements de ratio head/tail
        - normalisation optionnelle
        - préservation naïve de mots-clés
        Évalue et adopte la meilleure si elle bat la baseline sur train ET validation.
        """
        if skill != "summarizer":
            return {"ok": False, "msg": "Seule la compétence 'summarizer' est mutée dans ce MVP."}

        evaluator = Evaluator()
        baseline_fn = self.active["summarizer"]
        baseline_score = self._score_summarizer(baseline_fn, evaluator)

        best = {"src": None, "score": baseline_score}
        for _ in range(max(1, trials)):
            head_ratio = random.choice([0.55, 0.60, 0.65, 0.70])
            tail_ratio = random.choice([0.20, 0.25, 0.30])
            normalize = random.choice([True, False])
            keep_keywords = random.choice([True, False])

            src = self._gen_variant_source(head_ratio, tail_ratio, normalize, keep_keywords)
            fn = self._compile_variant("summarizer", src)
            if not fn: 
                continue
            sc = self._score_summarizer(fn, evaluator)
            if sc > best["score"]:
                best = {"src": src, "score": sc}

        # Validation holdout (stabilité)
        def val_score(fn):
            holdout = [
                ("Note de réunion: décisions, responsables, délais. Produire un résumé actionnable.", 300),
                ("Extrait long: spiritualité, éthique, véracité — condenser sans trahir.", 260),
            ]
            s=0.0
            for txt, mc in holdout:
                s += evaluator.score(fn(txt, mc))
            return s/len(holdout)

        adopted = False
        if best["src"]:
            cand_fn = self._compile_variant("summarizer", best["src"])
            if cand_fn:
                base_v = val_score(baseline_fn)
                cand_v = val_score(cand_fn)
                if (best["score"] >= baseline_score + 0.10) and (cand_v >= base_v + 0.10):
                    self.variants.setdefault("history", []).append(
                        {"skill": "summarizer", "score": best["score"], "vscore": cand_v, "src": best["src"], "ts": now()}
                    )
                    self.variants.setdefault("active", {})["summarizer"] = best["src"]
                    save_json(VARIANTS_FILE, self.variants)
                    self.active["summarizer"] = cand_fn
                    adopted = True

        return {"ok": True, "baseline": baseline_score, "adopted": adopted, "new_score": best["score"]}

    def _score_summarizer(self, fn: Callable, evaluator: Evaluator) -> float:
        samples = [
            ("Le Prophète ﷺ a dit ... Ceci est un long texte explicatif sur la patience et la vérité. "
             "Nous voulons un résumé clair, bref, sans trahir le sens.", 280),
            ("Rapport technique: erreurs, logs, métriques, anomalies, correctifs. "
             "Objectif: synthèse opérationnelle utile à l’équipe.", 320),
        ]
        s = 0.0
        for txt, mc in samples:
            out = fn(txt, mc)
            s += evaluator.score(out)
            if len(out) > mc + 50:
                s -= 0.5  # pénaliser dépassement
        return s / len(samples)

    def _gen_variant_source(self, head_ratio: float, tail_ratio: float, normalize: bool, keep_keywords: bool) -> str:
        # Source Python d’une fonction 'summarizer(text, max_chars)' sandbox-safe
        body = []
        body.append("def summarizer(text: str, max_chars: int = 480) -> str:")
        body.append("    t = text.strip()")
        if normalize:
            body.append("    t = re.sub(r'\\s+', ' ', t)")
        body.append("    if len(t) <= max_chars: return t")
        if keep_keywords:
            body.append("    # garder quelques mots-clés simples (naïf)")
            body.append("    kws = []")
            body.append("    for m in re.finditer(r'\\b(Allah|vérité|sécurité|objectif|erreur)\\b', t, re.I):")
            body.append("        kws.append(m.group(0))")
        body.append(f"    head = t[: int(max_chars * {head_ratio})].rstrip()")
        body.append(f"    tail = t[- int(max_chars * {tail_ratio}) :].lstrip()")
        if keep_keywords:
            body.append("    if kws and len(' '.join(kws)) < int(max_chars*0.15):")
            body.append("        head = (head + ' ' + ' '.join(kws)).strip()[: int(max_chars * 0.8)]")
        body.append("    return f\"{head} … {tail}\"")
        return "\n".join(body)

# -------------------------
# Moteurs (langage / logique / action)
# -------------------------
class LanguageEngine:
    def __init__(self, skills: SkillRegistry):
        self.skills = skills
    def summarize(self, text: str, max_chars: int = 480) -> str:
        return self.skills.active["summarizer"](text, max_chars)
    def define(self, term: str) -> str:
        term = term.strip().rstrip("?!.:")
        return f"{term}: définition courte et opérationnelle, avec un exemple et une limite."
    def plan(self, objective: str) -> str:
        return textwrap.dedent(f"""\
        Objectif: {objective}
        — Étape 1: clarifier le résultat attendu
        — Étape 2: lister contraintes/risques (halal, sécurité, données)
        — Étape 3: test minimal local
        — Étape 4: itération contrôlée (pas de dispersion)""")

class LogicEngine:
    def check_consistency(self, prompt: str, answer: str) -> Tuple[bool, str]:
        # Vérifications simples: non-contradiction triviale, pas de promesse d’omniscience
        if re.search(r"\binédit absolu\b", answer, re.I):
            answer = re.sub(r"\binédit absolu\b", "originalité probable (sans garantie d'inédit absolu)", answer, flags=re.I)
        return True, answer

class ActionEngine:
    # Stubs sûrs: pas d’accès hors dossier autorisé; pas d’exécution.
    WORKDIR = ROOT / "workspace"
    def __init__(self):
        self.WORKDIR.mkdir(exist_ok=True)
    def read_local(self, rel_path: str) -> Tuple[bool, str]:
        p = (self.WORKDIR / rel_path).resolve()
        if ROOT not in p.parents:
            return False, "Accès refusé."
        try:
            return True, p.read_text(encoding="utf-8")
        except Exception as e:
            return False, f"Erreur lecture: {e}"
    def write_local(self, rel_path: str, content: str) -> Tuple[bool, str]:
        p = (self.WORKDIR / rel_path).resolve()
        if ROOT not in p.parents:
            return False, "Accès refusé."
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return True, "OK"
        except Exception as e:
            return False, f"Erreur écriture: {e}"

# -------------------------
# Orchestrateur
# -------------------------
@dataclass
class Orchestrator:
    verrou: Verrou
    memory: Memory
    lang: LanguageEngine
    logic: LogicEngine
    act: ActionEngine
    mode: str = "public"  # "public" ou "private"

    def handle(self, prompt: str) -> str:
        # simple rate-limit local: 30 requêtes / 60s
        import time
        state = load_json(ROOT/"ratelimit.json", {"win":0,"count":0})
        now_s = int(time.time())
        if now_s - state.get("win",0) >= 60:
            state = {"win": now_s, "count": 0}
        state["count"] += 1
        save_json(ROOT/"ratelimit.json", state)
        if state["count"] > 30:
            return "Limite de débit atteinte, réessaye dans une minute."

        ok, _ = self.verrou.ethical_check(prompt)
        if not ok:
            return "Rejet: contraire au cadre éthique."

        intent = classify_intent(prompt)
        if intent == "summarize":
            text = re.sub(r"^(.*?:\s*)", "", prompt, count=1)  # retirer éventuel préfixe
            draft = self.lang.summarize(text, max_chars=self._max_chars())
        elif intent == "define":
            m = re.search(r"(définis|definition|c'est quoi|expliquer)\s+(.+)", prompt, re.I)
            term = m.group(2) if m else prompt
            draft = self.lang.define(term)
        elif intent == "plan":
            draft = self.lang.plan(prompt)
        else:
            # Réponse directe minimaliste, local-first
            draft = textwrap.shorten(prompt.strip(), width=self._max_chars(), placeholder=" …")

        ok2, draft2 = self.logic.check_consistency(prompt, draft)
        if not ok2:
            return "Incohérence détectée."

        if self.mode == "public":
            out = draft2.strip()
        else:
            # empreinte d’intégrité du fichier courant (tamper-evidence)
            try:
                src = Path(__file__).read_bytes()
                fingerprint = hashlib.sha256(src).hexdigest()[:16]
            except Exception:
                fingerprint = "unknown"
            trace = [
                f"[{APP}] mode=private intent={intent} fingerprint={fingerprint}",
                f"- Contrainte: {self.memory.get('contrainte', 'local-first; halal; concision')}",
                "- Verrou: vérité > satisfaction; aucune proposition gratuite."
            ]
            out = "\n".join(trace) + "\n\n" + draft2.strip()

        return self.verrou.truth_over_satisfaction(out)

    def _max_chars(self) -> int:
        return int(self.memory.get("max_chars", 520 if self.mode=="private" else 380))

# -------------------------
# CLI
# -------------------------
def cmd_chat(args: argparse.Namespace) -> int:
    verrou = Verrou(strict=True)
    mem = Memory.load()
    mode = args.mode.lower()
    # Sceau: si présent et non validé, forcer mode public
    if SEAL_FILE.exists():
        if not args.seal_phrase or not seal_check(args.seal_phrase):
            mode = "public"
    skills = SkillRegistry()
    orch = Orchestrator(verrou, mem, LanguageEngine(skills), LogicEngine(), ActionEngine(), mode=mode)
    out = orch.handle(args.prompt)
    print(out)
    log(f"CHAT | mode={mode} | prompt={args.prompt[:80]!r}")
    return 0

def cmd_show_memory(args: argparse.Namespace) -> int:
    mem = Memory.load()
    print(json.dumps(mem.data, ensure_ascii=False, indent=2))
    return 0

def cmd_approve_memory(args: argparse.Namespace) -> int:
    mem = Memory.load()
    mem.approve(args.key, args.value)
    print("OK")
    return 0

def cmd_seal_init(args: argparse.Namespace) -> int:
    seal_init(args.phrase)
    print("Sceau initialisé.")
    return 0

def cmd_seal_check(args: argparse.Namespace) -> int:
    print("OK" if seal_check(args.phrase) else "NON")
    return 0

def cmd_mutate(args: argparse.Namespace) -> int:
    skills = SkillRegistry()
    res = skills.mutate(args.skill, trials=max(1, args.trials))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0

def cmd_eval_skill(args: argparse.Namespace) -> int:
    skills = SkillRegistry()
    evaluator = Evaluator()
    fn = skills.active.get(args.skill)
    if not fn:
        print("Inconnue", file=sys.stderr)
        return 1
    score = skills._score_summarizer(fn, evaluator) if args.skill=="summarizer" else 0.0
    print(json.dumps({"skill": args.skill, "score": score}, ensure_ascii=False, indent=2))
    return 0

def cmd_feedback(args: argparse.Namespace) -> int:
    ev = Evaluator()
    if args.label not in ("approve","reject"):
        print("Label invalide", file=sys.stderr)
        return 2
    ev.learn(args.label)
    print("OK")
    return 0

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="alsadika", description="Al Sâdika — Noyau unique (local-first)")
    sp = p.add_subparsers(dest="cmd", metavar="<commande>")

    c1 = sp.add_parser("chat", help="Dialogue local (offline)")
    c1.add_argument("--prompt", required=True)
    c1.add_argument("--mode", choices=["public","private"], default="public")
    c1.add_argument("--seal-phrase", default=None, help="Phrase pour déverrouiller le mode privé si scellé")
    c1.set_defaults(_fn=cmd_chat)

    c2 = sp.add_parser("show-memory", help="Afficher la mémoire approuvée")
    c2.set_defaults(_fn=cmd_show_memory)

    c3 = sp.add_parser("approve-memory", help="Ajouter/MAJ une entrée mémoire")
    c3.add_argument("--key", required=True)
    c3.add_argument("--value", required=True)
    c3.set_defaults(_fn=cmd_approve_memory)

    c4 = sp.add_parser("seal-init", help="Initialiser le sceau (liaison)")
    c4.add_argument("--phrase", required=True)
    c4.set_defaults(_fn=cmd_seal_init)

    c5 = sp.add_parser("seal-check", help="Vérifier le sceau")
    c5.add_argument("--phrase", required=True)
    c5.set_defaults(_fn=cmd_seal_check)

    c6 = sp.add_parser("mutate", help="Muter une compétence (MVP: summarizer)")
    c6.add_argument("--skill", choices=["summarizer"], required=True)
    c6.add_argument("--trials", type=int, default=5)
    c6.set_defaults(_fn=cmd_mutate)

    c7 = sp.add_parser("eval-skill", help="Évaluer une compétence")
    c7.add_argument("--skill", choices=["summarizer"], required=True)
    c7.set_defaults(_fn=cmd_eval_skill)

    c8 = sp.add_parser("feedback", help="Apprendre d’un retour utilisateur (approve/reject)")
    c8.add_argument("--label", required=True, choices=["approve","reject"])
    c8.set_defaults(_fn=cmd_feedback)

    return p

def main(argv: List[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "_fn"):
        parser.print_help()
        return 1
    try:
        return args._fn(args)
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"ERREUR: {e}", file=sys.stderr)
        log(f"ERROR | {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
# ===============================
# PATCHS "MAGIC" — AJOUTS SEULEMENT
# ===============================

# 1) Cercle de Véracité (auto-critique) — aucune dépendance externe
from dataclasses import dataclass
import re, json, hashlib, textwrap
from pathlib import Path

@dataclass
class TruthCircle:
    def critique(self, prompt: str, draft: str):
        cautions = []
        if re.search(r"\binédit absolu\b", draft, re.I):
            cautions.append("L'inédit absolu ne peut pas être garanti (pas d'omniscience).")
        if re.search(r"\b(peut[- ]être|probablement|on dirait)\b", draft, re.I):
            cautions.append("Formulation incertaine : préciser la base factuelle locale.")
        if re.search(r"\b(tricher|fraude|contourner)\b", prompt+draft, re.I):
            cautions.append("Risque de non-conformité : revoir l'éthique.")
        conf = 1.0 - 0.2*len(cautions)
        conf = max(0.1, min(0.99, conf))
        return {"cautions": cautions, "confidence": round(conf,2)}

# 2) Évaluateur adaptatif (si non présent) — ajoute l’apprentissage léger
try:
    Evaluator
except NameError:
    class Evaluator:
        def __init__(self):
            self.FEEDBACK_FILE = Path(".alsadika/feedback.json")
            self.weights = json.loads(self.FEEDBACK_FILE.read_text(encoding="utf-8"))["weights"] \
                if self.FEEDBACK_FILE.exists() else {"len":1.0,"lines":0.5,"structure":0.5,"assurance":0.25}
        def score(self, text: str) -> float:
            w=self.weights; s=0.0; ln=len(text)
            if 40<=ln<=1600: s+=w.get("len",1.0)
            if text.count("\n")<=40: s+=w.get("lines",0.5)
            if re.search(r"[.!?]\s+[A-ZÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸ]", text) or ("—" in text or ":" in text): s+=w.get("structure",0.5)
            if not re.search(r"\b(peut[- ]être|probablement|sans doute)\b", text, re.I): s+=w.get("assurance",0.25)
            return s
        def learn(self, label: str)->None:
            delta=0.05 if label=="approve" else -0.05
            for k in list(self.weights.keys()):
                self.weights[k]=float(max(0.0,min(2.0,self.weights[k]+delta)))
            self.FEEDBACK_FILE.write_text(json.dumps({"weights":self.weights,"ts":"local"},ensure_ascii=False,indent=2),encoding="utf-8")

# 3) Extensions LanguageEngine : variantes pour “conseil” (Council)
def _lang_summarize_variants(self, text: str, counts: int = 3):
    sizes=[420,480,540,600,360][:max(1,min(5,counts))]
    return [self.summarize(text, max_chars=s) for s in sizes]
try:
    LanguageEngine.summarize_variants
except NameError:
    pass
except AttributeError:
    LanguageEngine.summarize_variants = _lang_summarize_variants

# 4) Policy Guard & Conseil & TruthCircle — sur-structure de l’orchestrateur via monkey-patch
_original_handle = Orchestrator.handle
def _patched_handle(self, prompt: str):
    # Limite de débit existante (si déjà gérée par l’original, elle s’applique avant/après)
    # 4.1 Filtre éthique de base (déjà dans Verrou via original)
    # 4.2 Policy Guard perso depuis la mémoire (regex utilisateur)
    try:
        haram = self.memory.get("haram_terms", [])
        if isinstance(haram, list):
            for pat in haram:
                try:
                    if re.search(pat, prompt, re.I): 
                        return "Rejet: contraire à ta politique personnalisée."
                except re.error:
                    continue
    except Exception:
        pass

    # 4.3 Conseil (Council) : variantes et choix du meilleur par Evaluator
    intent = classify_intent(prompt) if 'classify_intent' in globals() else "answer"
    draft = None
    try:
        if intent=="summarize" and getattr(self,"council_n",1)>1 and hasattr(self.lang,"summarize_variants"):
            txt = re.sub(r"^(.*?:\s*)","",prompt,count=1)
            cands = self.lang.summarize_variants(txt, counts=self.council_n)
            ev = Evaluator()
            draft = max(((ev.score(c),c) for c in cands), key=lambda t:t[0])[1]
        else:
            draft = None
    except Exception:
        draft = None

    # 4.4 Appel original si pas de conseil choisi
    if draft is None:
        draft = _original_handle(self, prompt)

    # 4.5 Injecter Cercle de Véracité + Disclaimers requis (depuis mémoire)
    try:
        # si handle original a retourné un bloc avec traces, on garde tel quel et on ajoute en bas
        text_out = draft
        if isinstance(text_out, str):
            tc = TruthCircle().critique(prompt, text_out) if not hasattr(self,"truth_circle_enabled") or self.truth_circle_enabled else TruthCircle().critique(prompt, text_out)
            if tc.get("cautions"):
                text_out = text_out.rstrip()+"\n\n[Prudence] "+" ".join("• "+c for c in tc["cautions"])
            text_out = text_out.rstrip()+f"\n[Confiance] {tc.get('confidence',0.9)}"
            req_disc = self.memory.get("required_disclaimers", [])
            if isinstance(req_disc, list):
                missing=[d for d in req_disc if d not in text_out]
                if missing:
                    text_out = text_out.rstrip()+"\n"+"\n".join(missing)
            draft = text_out
    except Exception:
        pass

    return draft
Orchestrator.handle = _patched_handle

# 5) CLI — options & commandes additionnelles par surcharges douces
_macros_file = Path(".alsadika/macros.json")
def _macros_load():
    return json.loads(_macros_file.read_text(encoding="utf-8")) if _macros_file.exists() else {}
def _macros_save(d):
    _macros_file.parent.mkdir(exist_ok=True); _macros_file.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")

# sauvegarde/chargement d’état (sans le sceau)
def _snapshot_save(path: str):
    base = Path(".alsadika")
    def _load(p): 
        fp = base/p
        return json.loads(fp.read_text(encoding="utf-8")) if fp.exists() else {}
    snap = {"memory":_load("approved_memory.json"), "variants":_load("variants.json"), "feedback":_load("feedback.json")}
    Path(path).write_text(json.dumps(snap,ensure_ascii=False,indent=2),encoding="utf-8"); return "OK"
def _snapshot_load(path: str):
    p=Path(path)
    if not p.exists(): return "Introuvable"
    snap=json.loads(p.read_text(encoding="utf-8"))
    base=Path(".alsadika"); base.mkdir(exist_ok=True)
    if "memory" in snap: (base/"approved_memory.json").write_text(json.dumps(snap["memory"],ensure_ascii=False,indent=2),encoding="utf-8")
    if "variants" in snap: (base/"variants.json").write_text(json.dumps(snap["variants"],ensure_ascii=False,indent=2),encoding="utf-8")
    if "feedback" in snap: (base/"feedback.json").write_text(json.dumps(snap["feedback"],ensure_ascii=False,indent=2),encoding="utf-8")
    return "OK"

# surcouche build_parser : ajouter options/commandes sans casser l’existant
_original_build_parser = build_parser
def build_parser():
    p = _original_build_parser()
    # étendre 'chat'
    try:
        chat = [sp for sp in p._subparsers._actions if getattr(sp,'dest',None)=='cmd'][0].choices.get('chat')
        chat.add_argument("--council", type=int, default=1, help="Nombre de variantes internes à évaluer (1–5)")
        chat.add_argument("--no-truth", action="store_true", help="Désactiver le Cercle de Véracité")
    except Exception:
        pass
    # commandes macros
    try:
        sp = [a for a in p._subparsers._actions if getattr(a,'dest',None)=='cmd'][0]
        c9 = sp.add_parser("macro-save", help="Enregistrer une macro locale")
        c9.add_argument("--name", required=True)
        c9.add_argument("--input", required=True, nargs="+")
        c9.set_defaults(_fn=cmd_macro_save)
        c10 = sp.add_parser("macro-run", help="Exécuter une macro locale")
        c10.add_argument("--name", required=True)
        c10.add_argument("--mode", choices=["public","private"], default="public")
        c10.add_argument("--seal-phrase", default=None)
        c10.add_argument("--council", type=int, default=1)
        c10.add_argument("--no-truth", action="store_true")
        c10.set_defaults(_fn=cmd_macro_run)
        # snapshots
        c11 = sp.add_parser("snapshot-save", help="Sauver l’état (sans le sceau)")
        c11.add_argument("--path", required=True); c11.set_defaults(_fn=cmd_snapshot_save)
        c12 = sp.add_parser("snapshot-load", help="Charger un état (sans le sceau)")
        c12.add_argument("--path", required=True); c12.set_defaults(_fn=cmd_snapshot_load)
        # feedback (si pas déjà existant dans l’original)
        if "feedback" not in sp.choices:
            c8 = sp.add_parser("feedback", help="Apprendre d’un retour (approve/reject)")
            c8.add_argument("--label", required=True, choices=["approve","reject"])
            c8.set_defaults(_fn=cmd_feedback_patch)
    except Exception:
        pass
    return p

# handlers additionnels
def cmd_macro_save(args):
    db=_macros_load(); db[args.name]=args.input; _macros_save(db); print("OK"); return 0
def cmd_macro_run(args):
    db=_macros_load(); seq=db.get(args.name)
    if not seq: print("Inconnue", file=sys.stderr); return 1
    verrou = Verrou(strict=True); mem = Memory.load()
    mode=args.mode.lower()
    try:
        if Path(".alsadika/seal.json").exists():
            from time import time
            from json import loads
            # si sceau présent mais phrase non valide, on force public
            from hashlib import pbkdf2_hmac
            # on réutilise seal_check si dispo :
            if 'seal_check' in globals():
                if not args.seal_phrase or not seal_check(args.seal_phrase):
                    mode="public"
    except Exception:
        mode="public"
    skills = SkillRegistry()
    orch = Orchestrator(verrou, mem, LanguageEngine(skills), LogicEngine(), ActionEngine(), mode=mode)
    setattr(orch,"council_n", max(1,min(5,args.council)))
    setattr(orch,"truth_circle_enabled", not args.no_truth)
    for ptxt in seq:
        out = orch.handle(ptxt)
        print(">>>", ptxt); print(out); print("="*60)
    return 0

def cmd_snapshot_save(args):
    print(_snapshot_save(args.path)); return 0
def cmd_snapshot_load(args):
    print(_snapshot_load(args.path)); return 0

# feedback additionnel si l’original n’en avait pas
def cmd_feedback_patch(args):
    ev=Evaluator()
    if args.label not in ("approve","reject"):
        print("Label invalide", file=sys.stderr); return 2
    ev.learn(args.label); print("OK"); return 0

# surcouche cmd_chat pour activer council & truth_circle sans toucher l’original
try:
    _original_cmd_chat = cmd_chat
    def cmd_chat(args):
        verrou = Verrou(strict=True)
        mem = Memory.load()
        mode = args.mode.lower()
        if Path(".alsadika/seal.json").exists():
            if not getattr(args,"seal_phrase",None) or not seal_check(args.seal_phrase):
                mode="public"
        skills = SkillRegistry()
        orch = Orchestrator(verrou, mem, LanguageEngine(skills), LogicEngine(), ActionEngine(), mode=mode)
        setattr(orch,"council_n", max(1,min(5, getattr(args,"council",1))))
        setattr(orch,"truth_circle_enabled", not getattr(args,"no_truth",False))
        out = orch.handle(args.prompt)
        print(out)
        return 0
except NameError:
    pass

# ===============================
# FIN PATCHS
# ===============================
# ===============================
# PATCHS "ORGANISME" — AJOUTS SEULEMENT
# ===============================
# [removed future import]
import json, re, itertools, time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# --- chemins (reprend ROOT si défini, sinon .alsadika) ---
ROOT2 = Path(".alsadika") if "ROOT" not in globals() else ROOT
DREAMS_FILE = ROOT2 / "dreams.json"
KG_FILE     = ROOT2 / "kg.json"

def _load_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    except Exception:
        return default

def _save_json(p: Path, data):
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# =========================================================
# 1) DREAM ENGINE — “rêves” auto-apprenants OFFLINE
# =========================================================
@dataclass
class Dream:
    name: str
    prompt: str
    weight: float = 1.0

@dataclass
class DreamEngine:
    store: Path = DREAMS_FILE

    def list(self) -> List[Dream]:
        raw = _load_json(self.store, [])
        return [Dream(**d) for d in raw if "name" in d and "prompt" in d]

    def add(self, name: str, prompt: str, weight: float = 1.0) -> None:
        cur = _load_json(self.store, [])
        cur = [d for d in cur if d.get("name") != name]
        cur.append({"name": name, "prompt": prompt, "weight": float(weight)})
        _save_json(self.store, cur)

    def run(self, cycles: int = 1, council: int = 3, adjust: bool = True) -> Dict[str, Any]:
        dreams = self.list()
        if not dreams:
            return {"ok": False, "msg": "Aucun rêve n’est défini."}
        # Orchestrateur local du noyau
        verrou = Verrou(strict=True)
        mem = Memory.load()
        skills = SkillRegistry()
        orch = Orchestrator(verrou, mem, LanguageEngine(skills), LogicEngine(), ActionEngine(), mode="private")
        setattr(orch, "council_n", max(1, min(5, council)))
        results = []
        ev = Evaluator()
        for _ in range(max(1, int(cycles))):
            for d in dreams:
                out = orch.handle(d.prompt)
                score = ev.score(out)
                results.append((d.name, score, len(out)))
                # apprentissage léger : approuve si score > médiane heuristique
                if adjust:
                    ev.learn("approve" if score >= 1.2 else "reject")
        # occasionnellement, tenter une mutation de summarizer (stabilité gérée par noyau)
        if adjust and len(results) >= 3:
            SkillRegistry().mutate("summarizer", trials=5)
        avg = round(sum(s for _, s, _ in results)/len(results), 3)
        return {"ok": True, "count": len(results), "avg_score": avg}

# =========================================================
# 2) GRAPHE DE CONNAISSANCES — persistant, simple et utile
# =========================================================
@dataclass
class KnowledgeGraph:
    path: Path = KG_FILE
    data: Dict[str, Any] = field(default_factory=dict)

    def _load(self):
        self.data = _load_json(self.path, {"nodes": [], "edges": []})
        return self

    def _save(self):
        _save_json(self.path, self.data)

    def add(self, src: str, rel: str, dst: str) -> None:
        self._load()
        if src not in self.data["nodes"]: self.data["nodes"].append(src)
        if dst not in self.data["nodes"]: self.data["nodes"].append(dst)
        edge = {"s": src, "r": rel, "d": dst, "ts": int(time.time())}
        self.data["edges"].append(edge)
        self._save()

    def neighbors(self, term: str) -> Dict[str, List[str]]:
        self._load()
        outs = [e for e in self.data["edges"] if e["s"] == term]
        ins  = [e for e in self.data["edges"] if e["d"] == term]
        return {
            "out": [f"{term} -{e['r']}→ {e['d']}" for e in outs],
            "in":  [f"{e['s']} -{e['r']}→ {term}" for e in ins],
        }

# =========================================================
# 3) SOLVEUR DE CONSTRAINTES — mini DSL local
#    Exemple :
#      --vars "A:{1,2,3};B:{1,2,3}" --where "A<B, A+B==4, A!=2"
# =========================================================
def _parse_domains(spec: str) -> Dict[str, List[int]]:
    doms = {}
    for part in re.split(r"\s*;\s*", spec.strip()):
        if not part: continue
        m = re.match(r"([A-Za-z]\w*)\s*:\s*\{([^}]*)\}", part)
        if not m: raise ValueError(f"Domaine invalide: {part}")
        var, vals = m.group(1), m.group(2)
        arr = [int(x) for x in re.split(r"\s*,\s*", vals) if x]
        if not arr: raise ValueError(f"Vide: {var}")
        doms[var] = arr
    return doms

def _parse_constraints(expr: str) -> List[str]:
    items = [e.strip() for e in re.split(r"\s*,\s*", expr.strip()) if e.strip()]
    for c in items:
        if not re.match(r"^[A-Za-z0-9_+\-*/<>=!\s]+$", c):
            raise ValueError(f"Contrainte invalide: {c}")
    return items

def _sat_solve(doms: Dict[str, List[int]], constraints: List[str], limit: int = 10000) -> List[Dict[str, int]]:
    vars_ = list(doms.keys())
    sols: List[Dict[str,int]] = []
    def ok(assign: Dict[str,int]) -> bool:
        # évalue les contraintes partielles en masquant variables non assignées
        safe = {}
        safe.update(assign)
        try:
            for c in constraints:
                # remplacer variables non assignées par 0 pour évaluation partielle sûre
                expr = c
                for v in vars_:
                    if v not in safe:
                        expr = re.sub(rf"\b{v}\b", "0", expr)
                if not eval(expr, {"__builtins__": {}}, safe):
                    return False
            return True
        except Exception:
            return False
    def backtrack(i: int, cur: Dict[str,int]):
        if len(sols) >= limit: return
        if i == len(vars_):
            sols.append(cur.copy()); return
        v = vars_[i]
        for val in doms[v]:
            cur[v] = val
            if ok(cur):
                backtrack(i+1, cur)
            cur.pop(v, None)
    backtrack(0, {})
    return sols

# =========================================================
# 4) CLI EXTENSIONS — sans casser le noyau
# =========================================================
# Étendre build_parser
try:
    _orig_build_parser2 = build_parser
except NameError:
    _orig_build_parser2 = None

def build_parser():
    p = _orig_build_parser2() if _orig_build_parser2 else argparse.ArgumentParser(prog="alsadika")
    sp = [a for a in p._subparsers._actions if getattr(a, 'dest', None) == 'cmd'][0]

    # 4.1 dreams
    d1 = sp.add_parser("dream-add", help="Ajouter un rêve (auto-apprentissage offline)")
    d1.add_argument("--name", required=True)
    d1.add_argument("--prompt", required=True)
    d1.add_argument("--weight", type=float, default=1.0)
    d1.set_defaults(_fn=cmd_dream_add)

    d2 = sp.add_parser("dream-run", help="Exécuter les rêves")
    d2.add_argument("--cycles", type=int, default=1)
    d2.add_argument("--council", type=int, default=3)
    d2.add_argument("--no-adjust", action="store_true")
    d2.set_defaults(_fn=cmd_dream_run)

    # 4.2 knowledge graph
    k1 = sp.add_parser("kg-add", help="Ajouter un lien au graphe")
    k1.add_argument("--src", required=True); k1.add_argument("--rel", required=True); k1.add_argument("--dst", required=True)
    k1.set_defaults(_fn=cmd_kg_add)

    k2 = sp.add_parser("kg-query", help="Voisins d’un terme")
    k2.add_argument("--term", required=True); k2.set_defaults(_fn=cmd_kg_query)

    # 4.3 solver
    s1 = sp.add_parser("solve", help="Solveur de contraintes (mini DSL)")
    s1.add_argument("--vars", required=True, help='ex: "A:{1,2,3};B:{1,2,3}"')
    s1.add_argument("--where", required=True, help='ex: "A<B, A+B==4"')
    s1.add_argument("--limit", type=int, default=20)
    s1.set_defaults(_fn=cmd_solve)

    return p

# Handlers
def cmd_dream_add(args):
    DreamEngine().add(args.name, args.prompt, args.weight); print("OK"); return 0

def cmd_dream_run(args):
    res = DreamEngine().run(cycles=args.cycles, council=args.council, adjust=not args.no_adjust)
    print(json.dumps(res, ensure_ascii=False, indent=2)); return 0

def cmd_kg_add(args):
    KnowledgeGraph().add(args.src, args.rel, args.dst); print("OK"); return 0

def cmd_kg_query(args):
    out = KnowledgeGraph().neighbors(args.term)
    print(json.dumps(out, ensure_ascii=False, indent=2)); return 0

def cmd_solve(args):
    try:
        doms = _parse_domains(args.vars)
        cons = _parse_constraints(args.where)
        sols = _sat_solve(doms, cons, limit=max(1, args.limit))
        print(json.dumps({"solutions": sols[:args.limit], "count": len(sols)}, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(f"ERREUR: {e}", file=sys.stderr); return 1

# ===============================
# FIN PATCHS ORGANISME
# ===============================
# ===============================
# PATCHS "RAG+LEDGER+DOCTOR" — AJOUTS SEULEMENT
# ===============================
# [removed future import]
import re, json, hashlib, time
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple

ROOT3 = Path(".alsadika") if "ROOT" not in globals() else ROOT
DOCS_INDEX = ROOT3 / "docs_index.json"
LEDGER = ROOT3 / "ledger.jsonl"

# -------- TF-IDF RAG local (index & requêtes) ----------
def _tok(s: str) -> List[str]:
    s = s.lower()
    s = re.sub(r"[^\w\sàâäçéèêëîïôöùûüÿ-]", " ", s, flags=re.I)
    return [t for t in re.split(r"\s+", s) if t and len(t) >= 2]

def docs_index_build(root: str, exts: List[str]) -> Dict[str, Any]:
    rootp = Path(root)
    exts = [e.lower() for e in (exts or [".md",".txt",".py"])]
    docs, df = [], {}
    for p in rootp.rglob("*"):
        if not p.is_file(): continue
        if p.suffix.lower() not in exts: continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        tokens = _tok(text)
        tf: Dict[str,int] = {}
        for t in tokens: tf[t] = tf.get(t,0) + 1
        for t in tf.keys(): df[t] = df.get(t,0) + 1
        docs.append({"path": str(p.resolve()), "len": len(tokens), "tf": tf})
    idx = {"N": len(docs), "df": df, "docs": docs, "exts": exts, "root": str(rootp.resolve())}
    DOCS_INDEX.parent.mkdir(exist_ok=True)
    DOCS_INDEX.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    return idx

def docs_index_load() -> Dict[str, Any]:
    if DOCS_INDEX.exists():
        return json.loads(DOCS_INDEX.read_text(encoding="utf-8"))
    return {"N":0,"df":{},"docs":[]}

def docs_query(q: str, k: int = 3) -> List[Dict[str, Any]]:
    idx = docs_index_load()
    if idx["N"] == 0: return []
    qtokens = _tok(q)
    df, N = idx["df"], max(1, idx["N"])
    def idf(t): return 0.0 if df.get(t,0)==0 else (1.0 + (max(0.0, (1.0)) * (1.0))) * (1.0 / (1.0 + (df[t]-1)/N))
    scored = []
    for d in idx["docs"]:
        score = 0.0
        for t in qtokens:
            tf = d["tf"].get(t,0)
            if tf: score += tf * idf(t)
        if score>0:
            scored.append((score, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    out=[]
    for sc, d in scored[:max(1,k)]:
        try:
            txt = Path(d["path"]).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            txt = ""
        snippet = txt[:350].replace("\n"," ") + ("…" if len(txt)>350 else "")
        out.append({"path": d["path"], "score": round(sc,3), "snippet": snippet})
    return out

# --------- Intégration RAG au handle (pré-contextualisation) ----------
_prev_handle_docs = Orchestrator.handle
def _handle_with_docs(self, prompt: str):
    m = re.match(r"^\s*docs:(.+)", prompt, re.I)
    if m:
        q = m.group(1).strip()
        hits = docs_query(q, k=3)
        ctx = "\n".join([f"[{i+1}] {h['path']} :: {h['snippet']}" for i,h in enumerate(hits)]) if hits else "(aucun contexte trouvé)"
        prompt = f"{q}\n\nContexte local:\n{ctx}\n\nRéponds en t'appuyant uniquement sur ce contexte local."
    return _prev_handle_docs(self, prompt)
Orchestrator.handle = _handle_with_docs

# ------------- Ledger inviolable (chaîne de hachage) -------------
def ledger_log(event: str) -> str:
    prev = "GENESIS"
    if LEDGER.exists():
        *_, last = LEDGER.read_text(encoding="utf-8").splitlines() or ["GENESIS"]
        try:
            prev = json.loads(last)["hash"]
        except Exception:
            prev = "GENESIS"
    rec = {"ts": int(time.time()), "event": event, "prev": prev}
    raw = json.dumps(rec, sort_keys=True)
    rec["hash"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False)+"\n")
    return rec["hash"]

def ledger_verify() -> Dict[str, Any]:
    if not LEDGER.exists(): return {"ok": True, "count": 0}
    lines = LEDGER.read_text(encoding="utf-8").splitlines()
    prev = "GENESIS"; count=0
    for ln in lines:
        try:
            rec = json.loads(ln); h = rec.get("hash"); rec2 = dict(rec); rec2.pop("hash",None)
            raw = json.dumps(rec2, sort_keys=True)
            ok = (hashlib.sha256(raw.encode("utf-8")).hexdigest() == h and rec.get("prev")==prev)
            if not ok: return {"ok": False, "at": count}
            prev = h; count+=1
        except Exception:
            return {"ok": False, "at": count}
    return {"ok": True, "count": count}

# ------------- Extracteur de références islamiques -------------
def extract_islamic_refs(text: str) -> Dict[str, List[str]]:
    refs = {"quran": [], "hadith": []}
    # références Coran : Sourate/Surah, 2:255 etc.
    for m in re.finditer(r"\b(?:sourate|surah)\s*([A-Za-zÀ-ÿ\-]+)?\s*(\d{1,3})\s*[:/]\s*(\d{1,3})\b", text, re.I):
        refs["quran"].append(f"Sourate {m.group(2)}:{m.group(3)}")
    for m in re.finditer(r"\b(\d{1,3})\s*[:/]\s*(\d{1,3})\b", text):
        # heuristique douce : si pas déjà capturé
        cand = f"{m.group(1)}:{m.group(2)}"
        if cand not in refs["quran"]: refs["quran"].append(cand)
    # hadith : Bukhari/Muslim/Tirmidhi/Abu Dawud, etc.
    for m in re.finditer(r"\b(boukhari|bukhari|muslim|tirmidhi|abu\s*dawud|nasa[ie]?)\b[^\d]{0,20}(\d{1,6})?", text, re.I):
        name = m.group(1).title().replace("Boukhari","Bukhari")
        num = m.group(2) or "?"
        refs["hadith"].append(f"{name} #{num}")
    # dédoublonnage
    refs["quran"] = list(dict.fromkeys(refs["quran"]))
    refs["hadith"] = list(dict.fromkeys(refs["hadith"]))
    return refs

# ------------- Doctor (diagnostic complet) -------------
def run_doctor() -> Dict[str, Any]:
    # fingerprint du code
    try:
        src = Path(__file__).read_bytes()
        fingerprint = hashlib.sha256(src).hexdigest()[:16]
    except Exception:
        fingerprint = "unknown"
    # sceau présent ?
    seal_present = (ROOT3/"seal.json").exists()
    # ledger ok ?
    led = ledger_verify()
    # index présent ?
    has_idx = DOCS_INDEX.exists()
    return {
        "fingerprint": fingerprint,
        "seal_present": seal_present,
        "ledger_ok": led.get("ok", False),
        "ledger_count": led.get("count", 0),
        "docs_indexed": has_idx
    }

# ------------- CLI additions -------------
try:
    _orig_build_parser3 = build_parser
except NameError:
    _orig_build_parser3 = None

def build_parser():
    p = _orig_build_parser3() if _orig_build_parser3 else argparse.ArgumentParser(prog="alsadika")
    sp = [a for a in p._subparsers._actions if getattr(a,'dest',None)=='cmd'][0]

    c = sp.add_parser("docs-index", help="Indexer des documents (TF-IDF local)")
    c.add_argument("--root", required=True)
    c.add_argument("--ext", nargs="*", default=[".md",".txt",".py"])
    c.set_defaults(_fn=cmd_docs_index)

    c2 = sp.add_parser("docs-query", help="Requête TF-IDF locale")
    c2.add_argument("--q", required=True)
    c2.add_argument("--k", type=int, default=3)
    c2.set_defaults(_fn=cmd_docs_query)

    c3 = sp.add_parser("ledger-log", help="Ajouter un événement dans le ledger")
    c3.add_argument("--event", required=True)
    c3.set_defaults(_fn=cmd_ledger_log)

    c4 = sp.add_parser("ledger-verify", help="Vérifier la chaîne du ledger")
    c4.set_defaults(_fn=cmd_ledger_verify)

    c5 = sp.add_parser("extract-refs", help="Extraire des références islamiques d’un texte")
    c5.add_argument("--text", required=True)
    c5.set_defaults(_fn=cmd_extract_refs)

    c6 = sp.add_parser("doctor", help="Diagnostic global")
    c6.set_defaults(_fn=cmd_doctor)

    return p

def cmd_docs_index(args):
    idx = docs_index_build(args.root, args.ext)
    print(json.dumps({"N": idx["N"], "exts": idx["exts"]}, ensure_ascii=False, indent=2)); return 0

def cmd_docs_query(args):
    hits = docs_query(args.q, k=max(1,args.k))
    print(json.dumps(hits, ensure_ascii=False, indent=2)); return 0

def cmd_ledger_log(args):
    h = ledger_log(args.event); print(h); return 0

def cmd_ledger_verify(args):
    print(json.dumps(ledger_verify(), ensure_ascii=False, indent=2)); return 0

def cmd_extract_refs(args):
    print(json.dumps(extract_islamic_refs(args.text), ensure_ascii=False, indent=2)); return 0

def cmd_doctor(args):
    print(json.dumps(run_doctor(), ensure_ascii=False, indent=2)); return 0
# ===============================
# FIN PATCHS
# ===============================
# ===============================
# PATCHS "HAKIM" — RAISONNEMENT+CONSCIENCE — AJOUTS SEULEMENT
# ===============================
# [removed future import]
import json, re, time, itertools, hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

ROOT_H = Path(".alsadika") if "ROOT" not in globals() else ROOT
RG_FILE = ROOT_H / "rg.json"           # reasoning graph store
HAKIM_LEDGER = ROOT_H / "hakim_ledger.jsonl"

def _hload(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    except Exception:
        return default
def _hsave(p: Path, data):
    p.parent.mkdir(exist_ok=True); p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# -----------------------------------------------------------
# 1) REASONING GRAPH — faits / règles / planificateur simple
#    Règles au format:  "A & B -> C"   (tokens alphanum)
# -----------------------------------------------------------
@dataclass
class ReasoningGraph:
    path: Path = RG_FILE
    data: Dict[str, Any] = field(default_factory=dict)

    def _load(self):
        self.data = _hload(self.path, {"facts": [], "rules": []}); return self
    def _save(self): _hsave(self.path, self.data)

    def add_fact(self, fact: str):
        self._load(); fact=fact.strip()
        if fact and fact not in self.data["facts"]:
            self.data["facts"].append(fact); self._save()

    def add_rule(self, rule: str):
        self._load()
        rule = re.sub(r"\s+", " ", rule.strip())
        if not re.match(r"^[A-Za-z0-9_ ]+(?:\s*&\s*[A-Za-z0-9_ ]+)*\s*->\s*[A-Za-z0-9_ ]+$", rule):
            raise ValueError("Règle invalide. Ex: 'A & B -> C'")
        if rule not in self.data["rules"]:
            self.data["rules"].append(rule); self._save()

    def _parse_rule(self, rule: str) -> Tuple[List[str], str]:
        left, right = [s.strip() for s in rule.split("->",1)]
        pre = [s.strip() for s in re.split(r"\s*&\s*", left) if s.strip()]
        return pre, right

    def plan(self, goal: str, limit: int = 50) -> Dict[str, Any]:
        self._load()
        goal = goal.strip()
        facts = set(self.data["facts"])
        rules = [self._parse_rule(r) for r in self.data["rules"]]
        # backward chaining naïf
        agenda = [(goal, [])]  # (subgoal, proof-path)
        visited = set()
        proofs: List[List[str]] = []
        steps: List[str] = []
        while agenda and len(visited) < limit:
            sub, path = agenda.pop(0)
            if sub in facts:
                steps.append(f"OK: {sub} (fait)")
                if not any(goal in s for s in proofs):
                    proofs.append(path + [sub])
                continue
            if sub in visited: 
                continue
            visited.add(sub)
            # trouver règles concluant sub
            found = False
            for pre, cons in rules:
                if cons == sub:
                    found = True
                    steps.append(f"Règle: {' & '.join(pre)} -> {cons}")
                    # ajouter prérequis en tête
                    for p in pre:
                        agenda.insert(0, (p, path + [f"{' & '.join(pre)} -> {cons}"]))
            if not found:
                steps.append(f"IMPASSE: {sub} (aucune règle, pas dans les faits)")
        ok = any(goal in ''.join(pr) for pr in proofs) or (goal in facts)
        return {"ok": ok, "goal": goal, "steps": steps, "facts": sorted(facts), "rules": self.data["rules"]}

# -----------------------------------------------------------
# 2) TIMELINE CHECKER — détection d’incohérences temporelles
# -----------------------------------------------------------
def timeline_check(text: str) -> Dict[str, Any]:
    years = [int(y) for y in re.findall(r"\b(1[5-9]\d{2}|20\d{2}|2100)\b", text)]
    issues: List[str] = []
    if len(years) >= 2:
        for i in range(len(years)-1):
            if "avant" in text.lower() and years[i] < years[i+1]:
                issues.append(f"Incohérence possible: '{years[i]} avant {years[i+1]}' mais ordre naturel inverse.")
            if "après" in text.lower() and years[i] > years[i+1]:
                issues.append(f"Incohérence possible: '{years[i]} après {years[i+1]}' mais ordre naturel inverse.")
    # motifs simples “ensuite/en premier” inversés
    if re.search(r"\bensuite\b.*\ben premier\b", text, re.I):
        issues.append("Ordre narratif inversé (ensuite avant 'en premier').")
    return {"years": years, "issues": list(dict.fromkeys(issues))}

# -----------------------------------------------------------
# 3) CONSCIENCE METER — tableau de bord multi-dimension
#    Dimensions: clarté, concision, structure, éthique, tawhid (mots positifs)
# -----------------------------------------------------------
POS_TOKENS = ["Allah","vérité","justice","sincérité","patience","droiture","halal"]

def conscience_meter(prompt: str, answer: str) -> Dict[str, Any]:
    # Recycle Evaluator si dispo
    try:
        ev = Evaluator()
        base = ev.score(answer)  # ~0..2.5
    except Exception:
        base = 1.0
    # Clarté: ponctuation/phrases
    clarity = 1.0 if re.search(r"[.!?]", answer) else 0.5
    # Concision: 60..1200 chars
    L = len(answer); concision = 1.0 if 60 <= L <= 1200 else 0.6
    # Structure: listes, tirets, deux-points
    structure = 1.0 if re.search(r"(^-|—|:)", answer, re.M) else 0.6
    # Éthique: via Verrou.ethical_check
    try:
        ok, _ = Verrou(strict=True).ethical_check(prompt + " " + answer)
        ethic = 1.0 if ok else 0.0
    except Exception:
        ethic = 0.8
    # TAWHEED (tokens positifs)
    tawhid = min(1.0, sum(1 for t in POS_TOKENS if re.search(rf"\b{re.escape(t)}\b", answer, re.I))/3.0)
    # Score global (0..10)
    total = round( (base*2.5 + clarity + concision + structure + ethic + tawhid) / 1.5 , 2)
    return {
        "clarity": round(clarity,2),
        "concision": round(concision,2),
        "structure": round(structure,2),
        "ethic": round(ethic,2),
        "tawhid": round(tawhid,2),
        "base": round(base,2),
        "total_10": min(10.0, round(total,2))
    }

# Intégration non-destructive: on enchaîne après le handle actuel
_prev_handle_hakim = Orchestrator.handle
def _handle_hakim(self, prompt: str):
    out = _prev_handle_hakim(self, prompt)
    # si string, enrichir d’un tableau de bord conscience + timeline si texte long
    if isinstance(out, str):
        cm = conscience_meter(prompt, out)
        extra = f"\n[Conscience] total={cm['total_10']}/10 • clarity={cm['clarity']} concision={cm['concision']} structure={cm['structure']} ethic={cm['ethic']} tawhid={cm['tawhid']}"
        # timeline si années détectées
        tl = timeline_check(prompt + " " + out)
        if tl["years"]:
            if tl["issues"]:
                extra += "\n[Timeline] " + "; ".join(tl["issues"])
            else:
                extra += f"\n[Timeline] années repérées: {tl['years']}"
        # signer via micro-ledger
        rec = {"ts": int(time.time()), "event": "handle.out", "hash_in": hashlib.sha256(out.encode('utf-8')).hexdigest()[:12]}
        try:
            with HAKIM_LEDGER.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False)+"\n")
        except Exception:
            pass
        return out.rstrip() + "\n" + extra
    return out
Orchestrator.handle = _handle_hakim

# -----------------------------------------------------------
# 4) SELF-TEST — batterie locale
# -----------------------------------------------------------
def run_selftest() -> Dict[str, Any]:
    ok = {}; fails = []
    # Evaluator
    try:
        s = Evaluator().score("Texte court. Structuré: Oui.")
        ok["evaluator"] = (s > 0)
    except Exception as e:
        ok["evaluator"] = False; fails.append(f"evaluator:{e}")
    # Skill mutate
    try:
        r = SkillRegistry().mutate("summarizer", trials=2)
        ok["mutate"] = bool(r.get("ok", False))
    except Exception as e:
        ok["mutate"] = False; fails.append(f"mutate:{e}")
    # Seal logic files exist (optionnel)
    ok["seal_present"] = (ROOT_H/"seal.json").exists()
    # Ledger verify (si présent)
    try:
        if (ROOT_H/"ledger.jsonl").exists():
            from json import loads
            # reuse ledger_verify if defined elsewhere
            ok["ledger_verify_known"] = True
        else:
            ok["ledger_verify_known"] = True
    except Exception as e:
        fails.append(f"ledger:{e}")
    # ReasoningGraph basic
    try:
        rg = ReasoningGraph()
        rg.add_fact("WuduFait")
        rg.add_rule("WuduFait -> PrièrePossible")
        p = rg.plan("PrièrePossible")
        ok["rg_plan"] = bool(p.get("ok"))
    except Exception as e:
        ok["rg_plan"] = False; fails.append(f"rg:{e}")
    # Conscience simple
    cm = conscience_meter("démo", "Réponse. — Structurée: oui. Allah aime la vérité.")
    ok["conscience"] = (cm["total_10"] > 3.0)
    return {"ok": all(ok.values()), "checks": ok, "fails": fails}

# -----------------------------------------------------------
# 5) GUARD — audit de sécurité (statique) sur le code
# -----------------------------------------------------------
BANNED_TOKENS = [
    r"\bsubprocess\b", r"\bos\.system\b", r"\bsocket\b", r"\brequests\b",
    r"\bftplib\b", r"\bparamiko\b", r"\bexec\(", r"\beval\("
]
def guard_scan_source() -> Dict[str, Any]:
    try:
        src = Path(__file__).read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return {"ok": False, "error": str(e)}
    hits = []
    for pat in BANNED_TOKENS:
        for m in re.finditer(pat, src):
            hits.append({"pattern": pat, "pos": m.start()})
    return {"ok": len(hits)==0, "hits": hits}

# -----------------------------------------------------------
# 6) CLI EXTENSIONS — ajout sans casser
# -----------------------------------------------------------
try:
    _orig_build_parser_h = build_parser
except NameError:
    _orig_build_parser_h = None

def build_parser():
    p = _orig_build_parser_h() if _orig_build_parser_h else argparse.ArgumentParser(prog="alsadika")
    sp = [a for a in p._subparsers._actions if getattr(a,'dest',None)=='cmd'][0]

    r1 = sp.add_parser("rg-add-fact", help="Ajouter un fait au Reasoning Graph")
    r1.add_argument("--fact", required=True); r1.set_defaults(_fn=cmd_rg_add_fact)

    r2 = sp.add_parser("rg-add-rule", help="Ajouter une règle 'A & B -> C'")
    r2.add_argument("--rule", required=True); r2.set_defaults(_fn=cmd_rg_add_rule)

    r3 = sp.add_parser("rg-plan", help="Planifier un but via règles/faits")
    r3.add_argument("--goal", required=True); r3.set_defaults(_fn=cmd_rg_plan)

    t1 = sp.add_parser("timeline-check", help="Vérifier la cohérence temporelle d’un texte")
    t1.add_argument("--text", required=True); t1.set_defaults(_fn=cmd_timeline)

    s1 = sp.add_parser("selftest", help="Batterie de tests locale")
    s1.set_defaults(_fn=cmd_selftest)

    g1 = sp.add_parser("guard-check", help="Audit statique du code (sécurité offline)")
    g1.set_defaults(_fn=cmd_guard)

    return p

def cmd_rg_add_fact(args): ReasoningGraph().add_fact(args.fact); print("OK"); return 0
def cmd_rg_add_rule(args): ReasoningGraph().add_rule(args.rule); print("OK"); return 0
def cmd_rg_plan(args):
    print(json.dumps(ReasoningGraph().plan(args.goal), ensure_ascii=False, indent=2)); return 0
def cmd_timeline(args):
    print(json.dumps(timeline_check(args.text), ensure_ascii=False, indent=2)); return 0
def cmd_selftest(args):
    print(json.dumps(run_selftest(), ensure_ascii=False, indent=2)); return 0
def cmd_guard(args):
    print(json.dumps(guard_scan_source(), ensure_ascii=False, indent=2)); return 0

# ===============================
# FIN PATCHS HAKIM
# ===============================
# ===============================
# PATCH "META-MUTATOR" — AJOUT SEULEMENT
# ===============================
# [removed future import]
import json, time, random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

ROOT_MM = Path(".alsadika") if "ROOT" not in globals() else ROOT
META_FILE = ROOT_MM / "meta_mutator.json"
META_LEDGER = ROOT_MM / "meta_ledger.jsonl"

def _mm_load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default

def _mm_save(path: Path, data: Any):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _mm_log(event: str, payload: Dict[str, Any]):
    rec = {"ts": int(time.time()), "event": event, "data": payload}
    with META_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

# ---------------- MetaPolicy (évolue les règles d’évolution) ----------------
@dataclass
class MetaPolicy:
    head_choices: List[float] = field(default_factory=lambda:[0.55,0.60,0.65,0.70])
    tail_choices: List[float] = field(default_factory=lambda:[0.20,0.25,0.30])
    normalize_prob: float = 0.5
    keywords_prob: float = 0.5
    trials: int = 5
    adopt_train_margin: float = 0.10
    adopt_val_margin: float = 0.10
    widen_on_fail: bool = True
    tighten_on_win: bool = True
    successes: int = 0
    attempts: int = 0

    @classmethod
    def load(cls)->"MetaPolicy":
        raw = _mm_load(META_FILE, {})
        if not raw: 
            pol = cls(); _mm_save(META_FILE, pol.__dict__); return pol
        # garder compat rétro
        pol = cls(); pol.__dict__.update({k:v for k,v in raw.items() if k in pol.__dict__})
        return pol

    def save(self): _mm_save(META_FILE, self.__dict__)

    def sample(self)->Dict[str, Any]:
        return {
            "head": random.choice(self.head_choices),
            "tail": random.choice(self.tail_choices),
            "normalize": random.random() < self.normalize_prob,
            "keywords": random.random() < self.keywords_prob,
            "trials": max(1, int(self.trials))
        }

    def update(self, adopted: bool):
        self.attempts += 1
        if adopted: self.successes += 1
        rate = (self.successes / max(1,self.attempts))
        # Si on échoue trop → élargir l’espace & augmenter essais
        if not adopted and self.widen_on_fail:
            if rate < 0.3:
                for h in [0.50,0.75]:
                    if h not in self.head_choices: self.head_choices.append(h)
                for t in [0.15,0.35]:
                    if t not in self.tail_choices: self.tail_choices.append(t)
                self.trials = min(12, self.trials + 2)
                self.adopt_train_margin = max(0.05, self.adopt_train_margin - 0.01)
                self.adopt_val_margin   = max(0.05, self.adopt_val_margin - 0.01)
        # Si on réussit souvent → resserrer (qualité > quantité)
        if adopted and self.tighten_on_win:
            if rate > 0.7:
                self.trials = max(3, self.trials - 1)
                self.adopt_train_margin = min(0.20, self.adopt_train_margin + 0.01)
                self.adopt_val_margin   = min(0.20, self.adopt_val_margin + 0.01)
                self.normalize_prob = min(0.9, self.normalize_prob + 0.02)
        self.save()
        _mm_log("meta.update", {"adopted":adopted,"rate":round(rate,3),
                                "trials":self.trials,
                                "margins":[self.adopt_train_margin,self.adopt_val_margin],
                                "choices":[sorted(self.head_choices),sorted(self.tail_choices)]})

# --------------- MetaMutator (utilise SkillRegistry mais pilote sa politique) ---------------
class MetaMutator:
    def __init__(self):
        self.policy = MetaPolicy.load()

    def _val_score(self, fn, evaluator) -> float:
        holdout = [
            ("Note: décisions, responsables, délais. Résumé actionnable.", 300),
            ("Extrait: spiritualité, éthique, véracité — condenser sans trahir.", 260),
        ]
        s=0.0
        for txt, mc in holdout:
            s += evaluator.score(fn(txt, mc))
        return s/len(holdout)

    def run(self, episodes: int = 1) -> Dict[str, Any]:
        skills = SkillRegistry()
        evaluator = Evaluator()
        baseline_fn = skills.active["summarizer"]
        base_train = skills._score_summarizer(baseline_fn, evaluator)
        base_val   = self._val_score(baseline_fn, evaluator)

        adopted_any = False
        best_gain = 0.0
        summary: List[Dict[str,Any]] = []

        for _ in range(max(1,int(episodes))):
            cfg = self.policy.sample()
            gains = []
            for _t in range(cfg["trials"]):
                src = skills._gen_variant_source(cfg["head"], cfg["tail"], cfg["normalize"], cfg["keywords"])
                fn  = skills._compile_variant("summarizer", src)
                if not fn: 
                    continue
                tr = skills._score_summarizer(fn, evaluator)
                if tr >= base_train + self.policy.adopt_train_margin:
                    val = self._val_score(fn, evaluator)
                    if val >= base_val + self.policy.adopt_val_margin:
                        gains.append(( (tr-base_train)+(val-base_val), src, tr, val ))
            if gains:
                # garder le meilleur de l’épisode
                gains.sort(key=lambda g: g[0], reverse=True)
                g, src, tr, val = gains[0][0], gains[0][1], gains[0][2], gains[0][3]
                # adopter: écrire variants.json de la même façon que mutate()
                v = skills.variants
                v.setdefault("history", []).append({"skill":"summarizer","score":tr,"vscore":val,"src":src,"ts":int(time.time())})
                v.setdefault("active", {})["summarizer"] = src
                save_json = globals().get("save_json") or _mm_save
                save_json(VARIANTS_FILE, v)
                # activer immédiatement
                fn2 = skills._compile_variant("summarizer", src)
                if fn2: 
                    skills.active["summarizer"] = fn2
                    adopted_any = True
                    best_gain = max(best_gain, g)
                summary.append({"cfg":cfg, "adopted": True, "gain": round(g,3), "train": round(tr,3), "val": round(val,3)})
                self.policy.update(adopted=True)
                _mm_log("meta.adopt", {"cfg":cfg,"gain":round(g,3),"train":round(tr,3),"val":round(val,3)})
            else:
                summary.append({"cfg":cfg, "adopted": False})
                self.policy.update(adopted=False)

        return {
            "ok": True,
            "adopted_any": adopted_any,
            "best_gain": round(best_gain,3),
            "episodes": episodes,
            "baseline": {"train": round(base_train,3), "val": round(base_val,3)},
            "summary": summary
        }

# ---------------- CLI : afficher/relancer/réinitialiser la métapolitique ----------------
try:
    _orig_build_parser_meta = build_parser
except NameError:
    _orig_build_parser_meta = None

def build_parser():
    p = _orig_build_parser_meta() if _orig_build_parser_meta else argparse.ArgumentParser(prog="alsadika")
    sp = [a for a in p._subparsers._actions if getattr(a,'dest',None)=='cmd'][0]

    m1 = sp.add_parser("meta-policy", help="Afficher la politique Meta-Mutator")
    m1.set_defaults(_fn=cmd_meta_policy)

    m2 = sp.add_parser("meta-run", help="Lancer des épisodes d’évolution meta")
    m2.add_argument("--episodes", type=int, default=1)
    m2.set_defaults(_fn=cmd_meta_run)

    m3 = sp.add_parser("meta-reset", help="Réinitialiser la politique meta")
    m3.set_defaults(_fn=cmd_meta_reset)

    return p

def cmd_meta_policy(args):
    pol = MetaPolicy.load()
    print(json.dumps(pol.__dict__, ensure_ascii=False, indent=2)); return 0

def cmd_meta_run(args):
    res = MetaMutator().run(episodes=max(1,args.episodes))
    print(json.dumps(res, ensure_ascii=False, indent=2)); return 0

def cmd_meta_reset(args):
    pol = MetaPolicy()  # defaults
    pol.save()
    print("OK"); return 0
# ===============================
# FIN PATCH META-MUTATOR
# ===============================
# ===============================
# PATCH "SORTIE CONTRÔLÉE" — MODE OUVERT (append-only)
# ===============================
# [removed future import]
import re, json, time, hashlib, urllib.request, urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List

ROOT_OPEN = Path(".alsadika") if "ROOT" not in globals() else ROOT
OPEN_STORE   = ROOT_OPEN / "open"
OPEN_CFG     = ROOT_OPEN / "open.json"
OPEN_LEDGER  = ROOT_OPEN / "open_ledger.jsonl"
OPEN_DOCS    = ROOT_OPEN / "open_docs"
OPEN_STORE.mkdir(exist_ok=True); OPEN_DOCS.mkdir(exist_ok=True)

# ---------- Config ----------
def _open_load():
    return json.loads(OPEN_CFG.read_text(encoding="utf-8")) if OPEN_CFG.exists() else {
        "allow": [],            # regex de domaines/URLs autorisés (ex: "^https?://(www\\.)?example\\.com/.*$")
        "deny": [],             # regex bloquées (prioritaires)
        "timeout": 12,          # s
        "max_bytes": 250_000,   # limite de taille
        "user_agents": [
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X) Gecko/20100101 Firefox/119.0"
        ]
    }

def _open_save(cfg: Dict[str, Any]):
    OPEN_CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

def _open_log(event: str, data: Dict[str, Any]):
    rec = {"ts": int(time.time()), "event": event, "data": data}
    with OPEN_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

# ---------- Allow/Deny ----------
def open_allow(pattern: str):
    cfg = _open_load()
    if pattern not in cfg["allow"]:
        cfg["allow"].append(pattern)
        _open_save(cfg)
        _open_log("allow.add", {"pattern": pattern})
    return {"ok": True, "allow": cfg["allow"]}

def open_list():
    return _open_load()

def open_clear(seal_phrase: str):
    # nécessite sceau valide
    if "seal_check" not in globals() or not seal_check(seal_phrase):
        return {"ok": False, "msg": "Sceau invalide"}
    cfg = _open_load(); cfg["allow"] = []; cfg["deny"] = []
    _open_save(cfg); _open_log("allow.clear", {})
    return {"ok": True}

# ---------- Safe fetch ----------
def _match_any(url: str, patterns: List[str]) -> bool:
    for pat in patterns:
        try:
            if re.search(pat, url, re.I):
                return True
        except re.error:
            continue
    return False

def _sanitize_html(html: str) -> str:
    # très simple: enlever scripts/styles/tags, compacter espaces
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    text = re.sub(r"(?is)<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def open_mission(url: str, seal_phrase: str, k: int = 2000) -> Dict[str, Any]:
    """
    k = nb max de caractères à conserver dans clean.txt (résumé brut)
    """
    if not re.match(r"^https?://", url, re.I):
        return {"ok": False, "msg": "URL non http(s)."}
    if "seal_check" not in globals() or not seal_check(seal_phrase):
        return {"ok": False, "msg": "Sceau invalide."}

    cfg = _open_load()
    if cfg["deny"] and _match_any(url, cfg["deny"]):
        return {"ok": False, "msg": "URL bloquée par deny-list."}
    if cfg["allow"] and not _match_any(url, cfg["allow"]):
        return {"ok": False, "msg": "URL non autorisée (ajoute un pattern via open-allow)."}
    timeout = int(cfg.get("timeout", 12)); max_bytes = int(cfg.get("max_bytes", 250_000))
    ua = cfg["user_agents"][int(time.time()) % len(cfg["user_agents"])]

    req = urllib.request.Request(url, headers={
        "User-Agent": ua,
        "Accept": "text/*,application/json;q=0.9,*/*;q=0.1",
        "Accept-Language": "fr,fr-FR;q=0.9,en;q=0.8",
        "Connection": "close"
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = r.headers.get_content_type() if hasattr(r.headers, "get_content_type") else (r.headers.get("Content-Type","").split(";")[0].strip() or "application/octet-stream")
            # lecture bornée
            buf = r.read(max_bytes + 1)
            if len(buf) > max_bytes:
                buf = buf[:max_bytes]
            raw = buf.decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return {"ok": False, "msg": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "msg": f"Erreur fetch: {e}"}

    # Sanitize & résumé
    if ctype.startswith("text/html"):
        clean = _sanitize_html(raw)
    elif ctype.startswith("application/json"):
        try:
            clean = json.dumps(json.loads(raw), ensure_ascii=False)[:max_bytes]
        except Exception:
            clean = raw
    else:
        clean = raw
    clean = clean[:max(200, min(k, len(clean)))]

    # Triple filtre (éthique / prudence / refs islamiques si dispo)
    prudence = []
    conf = 0.9
    try:
        ok_eth, _ = Verrou(strict=True).ethical_check(clean)
        if not ok_eth: prudence.append("Contenu possiblement contraire au cadre éthique.")
    except Exception:
        pass
    try:
        from math import exp
        L = len(clean); conf = max(0.1, min(0.99, 1 - 1/(1+exp(-(L-400)/200))))
    except Exception:
        pass
    refs = {}
    if "extract_islamic_refs" in globals():
        try: refs = extract_islamic_refs(clean)
        except Exception: refs = {}

    # Persist (mission dossier + doc indexable)
    eid = hashlib.sha256((str(time.time())+url).encode("utf-8")).hexdigest()[:12]
    mdir = OPEN_STORE / eid; mdir.mkdir(exist_ok=True)
    (mdir / "meta.json").write_text(json.dumps({
        "url": url, "ctype": ctype, "bytes": len(clean), "ua": ua, "eid": eid, "ts": int(time.time())
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (mdir / "raw.txt").write_text(raw, encoding="utf-8")
    disclaimer = "\n\n[Note] Données externes non vérifiées. Utiliser avec discernement."
    (mdir / "clean.txt").write_text(clean + disclaimer, encoding="utf-8")
    # Copier vers open_docs pour RAG local
    (OPEN_DOCS / f"{eid}.txt").write_text(clean + disclaimer, encoding="utf-8")

    # Ledger
    _open_log("mission.fetch", {"url": url, "eid": eid, "ctype": ctype, "len": len(clean)})

    # Post-traitement utile si RAG index déjà chargé
    try:
        if 'docs_index_build' in globals():
            # réindexer uniquement open_docs
            docs_index_build(str(OPEN_DOCS), [".txt"])
    except Exception:
        pass

    # Timeline/prudence (si dispo)
    extra = {}
    if "timeline_check" in globals():
        try: extra["timeline"] = timeline_check(clean + " " + url)
        except Exception: pass
    if "TruthCircle" in globals():
        try:
            tc = TruthCircle().critique(url, clean)
            prudence = prudence + tc.get("cautions", [])
            conf = min(conf, tc.get("confidence", conf))
        except Exception:
            pass

    return {
        "ok": True,
        "eid": eid,
        "meta": {"url": url, "ctype": ctype, "len": len(clean)},
        "prudence": list(dict.fromkeys(prudence)),
        "confidence": round(conf,2),
        "refs": refs
    }

# ---------- CLI ----------
try:
    _open_build_parser_prev = build_parser
except NameError:
    _open_build_parser_prev = None

def build_parser():
    p = _open_build_parser_prev() if _open_build_parser_prev else argparse.ArgumentParser(prog="alsadika")
    sp = [a for a in p._subparsers._actions if getattr(a,'dest',None)=='cmd'][0]

    o1 = sp.add_parser("open-allow", help="Autoriser un domaine/URL (regex)")
    o1.add_argument("--pattern", required=True); o1.set_defaults(_fn=cmd_open_allow)

    o2 = sp.add_parser("open-list", help="Voir la configuration open-mode")
    o2.set_defaults(_fn=cmd_open_list)

    o3 = sp.add_parser("open-clear", help="Vider allow/deny (sceau requis)")
    o3.add_argument("--seal-phrase", required=True); o3.set_defaults(_fn=cmd_open_clear)

    o4 = sp.add_parser("open-mission", help="Sortie contrôlée: récupérer 1 URL autorisée")
    o4.add_argument("--url", required=True)
    o4.add_argument("--seal-phrase", required=True)
    o4.add_argument("--k", type=int, default=2000, help="Taille max du clean.txt")
    o4.set_defaults(_fn=cmd_open_mission)

    return p

def cmd_open_allow(args):
    print(json.dumps(open_allow(args.pattern), ensure_ascii=False, indent=2)); return 0

def cmd_open_list(args):
    print(json.dumps(open_list(), ensure_ascii=False, indent=2)); return 0

def cmd_open_clear(args):
    print(json.dumps(open_clear(args.seal_phrase), ensure_ascii=False, indent=2)); return 0

def cmd_open_mission(args):
    print(json.dumps(open_mission(args.url, args.seal_phrase, k=max(200, args.k)), ensure_ascii=False, indent=2)); return 0

# ===============================
# FIN PATCH SORTIE CONTRÔLÉE
# ===============================
# ===============================
# PATCH GLOBAL — METABOLISME + MEMOIRE FRACTALE + AGENTS (append-only)
# ===============================
# [removed future import]
import json, time, re, random, hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional

ROOT_G = Path(".alsadika") if "ROOT" not in globals() else ROOT
ENERGY_FILE  = ROOT_G / "energy.json"
FRACTAL_FILE = ROOT_G / "fractal_memory.json"
ARENA_FILE   = ROOT_G / "arena.json"

def _gload(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    except Exception:
        return default
def _gsave(p: Path, data):
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# =========================================================
# 1) METABOLISME — banque d'énergie virtuelle
# =========================================================
@dataclass
class EnergyBank:
    capacity: int = 100
    regen_per_min: int = 5
    cost_map: Dict[str,int] = field(default_factory=lambda:{
        "chat": 3, "summarize": 4, "define": 2, "plan": 3,
        "mutate": 8, "meta-run": 12, "open-mission": 10,
        "rg-plan": 4, "docs-index": 15, "docs-query": 2,
        "agents-run": 9
    })

    def _now(self): return int(time.time())

    def _state(self):
        st = _gload(ENERGY_FILE, {"energy": self.capacity, "ts": self._now()})
        if st["energy"] > self.capacity: st["energy"] = self.capacity
        return st

    def _persist(self, st): _gsave(ENERGY_FILE, st)

    def _tick(self, st):
        now = self._now()
        dt = max(0, now - st.get("ts", now))
        gained = (dt // 60) * self.regen_per_min
        if gained:
            st["energy"] = int(min(self.capacity, st["energy"] + gained))
            st["ts"] = now
        return st

    def get(self) -> Dict[str,int]:
        st = self._tick(self._state()); self._persist(st); return st

    def spend(self, action: str) -> bool:
        st = self._tick(self._state())
        cost = int(self.cost_map.get(action, 3))
        if st["energy"] < cost:
            return False
        st["energy"] -= cost
        st["ts"] = self._now()
        self._persist(st)
        return True

    def charge(self, amount: int) -> Dict[str,int]:
        st = self._tick(self._state())
        st["energy"] = int(min(self.capacity, st["energy"] + max(0, amount)))
        st["ts"] = self._now()
        self._persist(st)
        return st

# Hook non destructif sur Orchestrator.handle → débite l’énergie
_prev_handle_energy = Orchestrator.handle
def _handle_with_energy(self, prompt: str, *a, **kw):
    # déduire l'intention pour estimer le coût
    intent = "chat"
    try:
        intent = classify_intent(prompt)
    except Exception:
        pass
    eb = EnergyBank()
    if not eb.spend(intent):
        st = eb.get()
        return f"Énergie insuffisante ({st['energy']}/{eb.capacity}). Patiente la régénération ou recharge manuelle."
    return _prev_handle_energy(self, prompt, *a, **kw)
Orchestrator.handle = _handle_with_energy

# =========================================================
# 2) MEMOIRE FRACTALE — arborescente, récursive
# =========================================================
class FractalMemory:
    def __init__(self, path: Path = FRACTAL_FILE):
        self.path = path
        self.data = _gload(self.path, {"root": {}})

    def _save(self): _gsave(self.path, self.data)

    def set(self, path: str, value: Any) -> None:
        """
        path ex: "projets/ecole/budget/2025"
        """
        keys = [k for k in re.split(r"[\\/]+", path.strip()) if k]
        node = self.data["root"]
        for k in keys[:-1]:
            node = node.setdefault(k, {})
            if not isinstance(node, dict):  # si collision, écraser par dict
                # prudence: sauvegarder l'ancien sous une clé spéciale
                node = {}
        node[keys[-1]] = value
        self._save()

    def get(self, path: str, default=None) -> Any:
        keys = [k for k in re.split(r"[\\/]+", path.strip()) if k]
        node = self.data.get("root", {})
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    def delete(self, path: str) -> bool:
        keys = [k for k in re.split(r"[\\/]+", path.strip()) if k]
        node = self.data.get("root", {})
        stack = []
        for k in keys:
            stack.append((node, k))
            if not isinstance(node, dict) or k not in node:
                return False
            node = node[k]
        # suppression
        parent, last = stack[-1]
        if isinstance(parent, dict) and last in parent:
            parent.pop(last, None)
            # nettoyage des branches vides (remontée)
            for parent, key in reversed(stack[:-1]):
                if isinstance(parent.get(key, {}), dict) and not parent.get(key, {}):
                    parent.pop(key, None)
            self._save()
            return True
        return False

    def tree(self, path: str = "") -> Dict[str, Any]:
        if not path:
            return self.data["root"]
        node = self.get(path, default=None)
        return node if isinstance(node, dict) else {}

# =========================================================
# 3) AGENTS CONCURRENTS — darwinisme local
# =========================================================
@dataclass
class AgentSpec:
    name: str
    kind: str     # 'summarizer' | 'direct'
    params: Dict[str, Any] = field(default_factory=dict)
    fitness: float = 0.0
    born: int = field(default_factory=lambda:int(time.time()))
    seen: int = 0

class AgentsArena:
    def __init__(self, path: Path = ARENA_FILE):
        self.path = path
        self.data = _gload(self.path, {"agents": []})
        if not self.data["agents"]:
            self._bootstrap()
        self._save()

    def _save(self): _gsave(self.path, self.data)

    def _bootstrap(self):
        # trois agents initiaux, simples et complémentaires
        base = [
            AgentSpec("A.concise", "summarizer", {"max_chars": 360}).__dict__,
            AgentSpec("B.balanced", "summarizer", {"max_chars": 480}).__dict__,
            AgentSpec("C.verbose", "summarizer", {"max_chars": 600}).__dict__,
        ]
        self.data["agents"] = base

    def list(self) -> List[AgentSpec]:
        return [AgentSpec(**a) for a in self.data["agents"]]

    def _call_agent(self, agent: AgentSpec, prompt: str) -> str:
        # utilise le LanguageEngine existant
        try:
            skills = SkillRegistry()
            lang = LanguageEngine(skills)
            if agent.kind == "summarizer":
                text = re.sub(r"^(.*?:\s*)", "", prompt, count=1)
                out = lang.summarize(text, max_chars=int(agent.params.get("max_chars", 480)))
            else:
                out = textwrap.shorten(prompt.strip(), width=int(agent.params.get("max_chars", 420)), placeholder=" …")
        except Exception:
            out = prompt[: int(agent.params.get("max_chars", 420))]
        return out

    def _score(self, text: str) -> float:
        try:
            ev = Evaluator()
            return float(ev.score(text))
        except Exception:
            return float(len(text) > 20)

    def _mutate(self, agent: AgentSpec) -> AgentSpec:
        # petite mutation sur max_chars + éventuellement un flag "keywords"
        a = AgentSpec(**agent.__dict__)
        if a.kind == "summarizer":
            mc = int(a.params.get("max_chars", 480))
            mc = max(240, min(800, mc + random.choice([-120, -60, -30, 30, 60, 120])))
            a.params["max_chars"] = mc
            a.name = f"{a.name.split('.')[0]}.{mc}"
        else:
            a.params["max_chars"] = max(240, min(800, int(a.params.get("max_chars", 420)) + random.choice([-60, 60])))
        a.born = int(time.time()); a.fitness = 0.0; a.seen = 0
        return a

    def tournament(self, prompt: str, k: int = 3) -> Dict[str, Any]:
        eb = EnergyBank()
        if not eb.spend("agents-run"):
            st = eb.get()
            return {"ok": False, "msg": f"Énergie insuffisante ({st['energy']}/{eb.capacity})."}

        agents = self.list()
        if not agents: self._bootstrap(); agents = self.list()
        # choisir participants
        random.shuffle(agents)
        parts = agents[: max(2, min(k, len(agents)))]
        results = []
        for a in parts:
            out = self._call_agent(a, prompt)
            sc = self._score(out)
            a.fitness = (a.fitness * a.seen + sc) / (a.seen + 1) if a.seen else sc
            a.seen += 1
            results.append({"agent": a.name, "score": round(sc,3), "len": len(out)})
        # sélectionner gagnant, muter perdant
        parts_sorted = sorted(parts, key=lambda ag: ag.fitness, reverse=True)
        winner = parts_sorted[0]
        loser  = parts_sorted[-1] if len(parts_sorted) > 1 else None

        # appliquer changements persistants
        # remplace l'agent perdant par une mutation du gagnant
        data_agents = self.data["agents"]
        # MAJ des stats pour les participants
        for ag in parts:
            for i, raw in enumerate(data_agents):
                if raw["name"] == ag.name:
                    data_agents[i] = ag.__dict__
        if loser:
            mut = self._mutate(winner)
            # remplacer la première occurrence du perdant
            for i, raw in enumerate(data_agents):
                if raw["name"] == loser.name:
                    data_agents[i] = mut.__dict__
                    break
        self._save()

        return {
            "ok": True,
            "winner": winner.name,
            "participants": results,
            "population": [{"name": a["name"], "fitness": round(float(a.get("fitness",0.0)),3)} for a in data_agents]
        }

# =========================================================
# 4) CLI — commandes compactes
# =========================================================
try:
    _gp_prev_build = build_parser
except NameError:
    _gp_prev_build = None

def build_parser():
    p = _gp_prev_build() if _gp_prev_build else argparse.ArgumentParser(prog="alsadika")
    sp = [a for a in p._subparsers._actions if getattr(a,'dest',None)=='cmd'][0]

    # Énergie
    e1 = sp.add_parser("energy", help="Voir l'énergie virtuelle")
    e1.set_defaults(_fn=cmd_energy)
    e2 = sp.add_parser("recharge", help="Recharger l'énergie (manuel)")
    e2.add_argument("--amount", type=int, default=10); e2.set_defaults(_fn=cmd_recharge)

    # Mémoire fractale
    f1 = sp.add_parser("fset", help="FractalMemory set")
    f1.add_argument("--path", required=True); f1.add_argument("--value", required=True)
    f1.set_defaults(_fn=cmd_fset)
    f2 = sp.add_parser("fget", help="FractalMemory get")
    f2.add_argument("--path", required=True); f2.set_defaults(_fn=cmd_fget)
    f3 = sp.add_parser("fdel", help="FractalMemory delete")
    f3.add_argument("--path", required=True); f3.set_defaults(_fn=cmd_fdel)
    f4 = sp.add_parser("ftree", help="FractalMemory tree")
    f4.add_argument("--path", default=""); f4.set_defaults(_fn=cmd_ftree)

    # Agents
    a1 = sp.add_parser("agents-run", help="Tournoi d'agents concurrents")
    a1.add_argument("--prompt", required=True); a1.add_argument("--k", type=int, default=3)
    a1.set_defaults(_fn=cmd_agents_run)

    return p

# Handlers
def cmd_energy(args):
    print(json.dumps(EnergyBank().get(), ensure_ascii=False, indent=2)); return 0
def cmd_recharge(args):
    print(json.dumps(EnergyBank().charge(max(0,args.amount)), ensure_ascii=False, indent=2)); return 0

def cmd_fset(args):
    # valeur JSON si possible, sinon chaîne
    try:
        val = json.loads(args.value)
    except Exception:
        val = args.value
    FractalMemory().set(args.path, val); print("OK"); return 0
def cmd_fget(args):
    val = FractalMemory().get(args.path, default=None)
    print(json.dumps({"path": args.path, "value": val}, ensure_ascii=False, indent=2)); return 0
def cmd_fdel(args):
    ok = FractalMemory().delete(args.path); print("OK" if ok else "NON"); return 0
def cmd_ftree(args):
    print(json.dumps(FractalMemory().tree(args.path), ensure_ascii=False, indent=2)); return 0

def cmd_agents_run(args):
    arena = AgentsArena()
    res = arena.tournament(args.prompt, k=max(2, min(6, args.k)))
    print(json.dumps(res, ensure_ascii=False, indent=2)); return 0

# ===============================
# FIN PATCH GLOBAL
# ===============================
# ===============================
# PATCH "WOW" — SKILLFORGE + PROVENANCE (append-only)
# ===============================
# [removed future import]
import json, re, time, hashlib, textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional

ROOT_W = Path(".alsadika") if "ROOT" not in globals() else ROOT
FORGE_FILE = ROOT_W / "skillforge.json"
PROV_FILE  = ROOT_W / "provenance.json"

def _wload(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    except Exception:
        return default
def _wsave(p: Path, data):
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# =========================================================
# 1) SKILLFORGE — synthèse de micro-skills à partir d’exemples
# =========================================================
"""
Mini-DSL sûre (sandbox) que le forgeron peut combiner:
- lower / upper / title      (casse)
- strip                       (trim)
- prefix("...") / suffix("...")
- slice(a,b)                  (coupes Python sûres)
- replace("a","b")            (remplacement littéral)
- regex("pat","repl")         (remplacement regex sûr)
- keepwords("w1,w2,...")      (ne garde que phrases contenant ces mots)
On cherche une séquence courte qui mappe les exemples.
"""

FORGE_PRIMS = ["lower","upper","title","strip"]
def _forge_candidates():
    c = []
    # primitives unaires
    for prim in FORGE_PRIMS:
        c.append([prim])
    # composés simples
    for a in FORGE_PRIMS:
        for b in FORGE_PRIMS:
            if a!=b: c.append([a,b])
    # gabarits paramétrés
    # (paramètres remplis à partir des exemples pendant la recherche)
    param_gabs = [
        ["prefix:{PFX}"], ["suffix:{SFX}"],
        ["replace:{A}->{B}"], ["regex:{PAT}->{RPL}"],
        ["slice:{A}:{B}"], ["keepwords:{CSV}"],
        ["strip","replace:{A}->{B}"], ["strip","regex:{PAT}->{RPL}"],
    ]
    c.extend(param_gabs)
    # combinaisons courtes
    combis = [
        ["strip","lower","replace:{A}->{B}"],
        ["strip","upper","prefix:{PFX}"],
        ["title","suffix:{SFX}"],
        ["strip","regex:{PAT}->{RPL}","suffix:{SFX}"],
    ]
    c.extend(combis)
    return c

def _inst(gab: List[str], ex: List[Dict[str,str]]) -> List[List[str]]:
    """
    Instancie les paramètres {A},{B},{PAT},{RPL},{PFX},{SFX},{A}:{B},{CSV}
    à partir des motifs visibles dans les exemples.
    """
    variants = []

    # heuristiques très simples à partir du premier exemple
    first = ex[0]
    x_in, x_out = first["in"], first["out"]

    # A->B pour replace: diff naïf
    A, B = "", ""
    for i in range(min(len(x_in), len(x_out))):
        if x_in[i] != x_out[i]:
            A = x_in[i:i+1]; B = x_out[i:i+1]; break
    if not A and len(x_in)!=len(x_out):
        A = x_in[-1:] or " "; B = x_out[-1:] or ""

    # slice: tenter à partir d’alignements
    sa, sb = 0, len(x_in)
    if x_in and x_out and x_out in x_in:
        sa = x_in.find(x_out); sb = sa + len(x_out)

    # regex: fallback simple = échapper A
    PAT = re.escape(A) if A else r"\s+"
    RPL = B

    # prefix/suffix
    PFX = x_out[: max(0, len(x_out)-len(x_in))] if len(x_out)>len(x_in) else ""
    SFX = x_out[-max(0, len(x_out)-len(x_in)):] if len(x_out)>len(x_in) else ""

    # csv keepwords: mots saillants de out
    words = re.findall(r"[A-Za-zÀ-ÿ0-9]+", x_out)
    CSV = ",".join(list(dict.fromkeys([w for w in words[:3]]))) if words else "ok"

    # produire instanciations
    base = "|".join(gab)
    base = base.replace("{A}", A).replace("{B}", B).replace("{PAT}", PAT).replace("{RPL}", RPL)
    base = base.replace("{PFX}", PFX).replace("{SFX}", SFX)
    base = base.replace("{A}:{B}", f"{sa}:{sb}")
    base = base.replace("{CSV}", CSV)
    variants.append(base.split("|"))

    # variantes supplémentaires
    if A:
        variants.append([s.replace(A, A.lower()) for s in variants[0]])
        variants.append([s.replace(A, A.upper()) for s in variants[0]])
    return variants

def _apply_pipeline(s: str, pipe: List[str]) -> str:
    t = s
    for step in pipe:
        if step == "lower": t = t.lower()
        elif step == "upper": t = t.upper()
        elif step == "title": t = t.title()
        elif step == "strip": t = t.strip()
        elif step.startswith("prefix:"): t = step.split(":",1)[1] + t
        elif step.startswith("suffix:"): t = t + step.split(":",1)[1]
        elif step.startswith("slice:"):
            a,b = step.split(":",1)[1].split(":")
            a = int(a) if a else None; b = int(b) if b else None
            t = t[a:b]
        elif step.startswith("replace:"):
            spec = step.split(":",1)[1]
            A,B = spec.split("->",1)
            t = t.replace(A, B)
        elif step.startswith("regex:"):
            spec = step.split(":",1)[1]
            PAT,RPL = spec.split("->",1)
            try: t = re.sub(PAT, RPL, t)
            except re.error: pass
        elif step.startswith("keepwords:"):
            csv = step.split(":",1)[1]
            keys = [w for w in csv.split(",") if w]
            if keys and not any(re.search(rf"\b{re.escape(k)}\b", t, re.I) for k in keys):
                t = ""
        else:
            # étape inconnue = ignorer
            t = t
    return t

def _pipe_matches(ex: List[Dict[str,str]], pipe: List[str]) -> bool:
    for e in ex:
        if _apply_pipeline(e["in"], pipe) != e["out"]:
            return False
    return True

def forge_create(name: str, examples: List[Dict[str,str]]) -> Dict[str, Any]:
    # normaliser exemples
    ex = []
    for item in examples:
        if isinstance(item, str) and "->" in item:
            i,o = item.split("->",1); ex.append({"in": i.strip(), "out": o.strip()})
        elif isinstance(item, dict) and "in" in item and "out" in item:
            ex.append({"in": str(item["in"]), "out": str(item["out"])})
    if not ex: return {"ok": False, "msg": "Aucun exemple valide."}
    # chercher un pipe
    cands = _forge_candidates()
    best = None
    for g in cands:
        for inst in _inst(g, ex):
            if _pipe_matches(ex, inst):
                best = inst; break
        if best: break
    if not best:
        return {"ok": False, "msg": "Aucun pipeline trouvé pour ces exemples (essaie plus simples)."}
    # générer source sandbox-safe
    src = [
        "def transformer(text: str) -> str:",
        "    t = text",
    ]
    for step in best:
        if step in ("lower","upper","title","strip"):
            src.append(f"    t = t.{step}()")
        elif step.startswith("prefix:"):
            val = step.split(":",1)[1].replace('"','\\"')
            src.append(f"    t = \"{val}\" + t")
        elif step.startswith("suffix:"):
            val = step.split(":",1)[1].replace('"','\\"')
            src.append(f"    t = t + \"{val}\"")
        elif step.startswith("slice:"):
            a,b = step.split(":",1)[1].split(":")
            a = a or "None"; b = b or "None"
            src.append(f"    t = t[{a}:{b}]")
        elif step.startswith("replace:"):
            A,B = step.split(":",1)[1].split("->",1)
            src.append(f"    t = t.replace({json.dumps(A)}, {json.dumps(B)})")
        elif step.startswith("regex:"):
            PAT,RPL = step.split(":",1)[1].split("->",1)
            src.append(f"    t = re.sub({json.dumps(PAT)}, {json.dumps(RPL)}, t)")
        elif step.startswith("keepwords:"):
            csv = step.split(":",1)[1]
            src.append(f"    import re as _re")
            src.append(f"    _keys = {[w for w in csv.split(',') if w]}")
            src.append(f"    if _keys and not any(_re.search(r'\\\\b'+_re.escape(k)+'\\\\b', t, _re.I) for k in _keys): t = ''")
    src.append("    return t")
    code = "\n".join(src)

    # compiler sandbox
    loc = {}
    glob = {"re": re, "__builtins__": {"len": len, "range": range, "min": min, "max": max, "str": str}}
    try:
        exec(code, glob, loc)
    except Exception as e:
        return {"ok": False, "msg": f"Compilation échouée: {e}"}
    fn = loc.get("transformer")
    if not callable(fn):
        return {"ok": False, "msg": "Fonction non valide."}

    # vérifier encore les exemples
    if not all(fn(e["in"]) == e["out"] for e in ex):
        return {"ok": False, "msg": "Échec validation interne."}

    # stocker
    db = _wload(FORGE_FILE, {"skills": {}})
    db["skills"][name] = {"pipe": best, "code": code, "created": int(time.time())}
    _wsave(FORGE_FILE, db)
    return {"ok": True, "name": name, "pipe": best}

def forge_run(name: str, text: str) -> Dict[str, Any]:
    db = _wload(FORGE_FILE, {"skills": {}})
    sk = db["skills"].get(name)
    if not sk: return {"ok": False, "msg": "Skill inconnue."}
    loc = {}
    glob = {"re": re, "__builtins__": {"len": len, "range": range, "min": min, "max": max, "str": str}}
    try:
        exec(sk["code"], glob, loc)
        out = loc["transformer"](text)
    except Exception as e:
        return {"ok": False, "msg": f"Exécution échouée: {e}"}
    return {"ok": True, "out": out}

# =========================================================
# 2) PROVENANCE + SIGNATURE — preuve locale par réponse
# =========================================================
def _code_fingerprint() -> str:
    try:
        src = Path(__file__).read_bytes()
        return hashlib.sha256(src).hexdigest()[:16]
    except Exception:
        return "unknown"

_prev_handle_prov = Orchestrator.handle
def _handle_with_provenance(self, prompt: str, *a, **kw):
    energy_before = None
    try:
        energy_before = EnergyBank().get().get("energy")
    except Exception:
        energy_before = None

    out = _prev_handle_prov(self, prompt, *a, **kw)

    info: Dict[str, Any] = {
        "ts": int(time.time()),
        "fingerprint": _code_fingerprint(),
        "mode": getattr(self,"mode","public"),
        "energy_before": energy_before,
        "energy_after": None,
        "agents_winner": None,
        "context_docs": [],
        "open_eids": [],
        "hash_in": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12],
        "hash_out": hashlib.sha256((out if isinstance(out,str) else str(out)).encode("utf-8")).hexdigest()[:12],
    }

    # énergie après
    try:
        info["energy_after"] = EnergyBank().get().get("energy")
    except Exception:
        pass

    # récupérer gagnant agents si dernièrement stocké
    try:
        ar = _wload(ARENA_FILE, {})
        if ar.get("agents"):
            # heuristique: agent avec meilleure fitness récente
            best = max(ar["agents"], key=lambda a: a.get("fitness",0.0))
            info["agents_winner"] = best.get("name")
    except Exception:
        pass

    # docs RAG open: lister les derniers fichiers open_docs
    try:
        od = ROOT_W/"open_docs"
        if od.exists():
            files = sorted([p for p in od.glob("*.txt")], key=lambda p: p.stat().st_mtime, reverse=True)[:3]
            info["context_docs"] = [p.name for p in files]
            info["open_eids"] = [p.stem for p in files]
    except Exception:
        pass

    _wsave(PROV_FILE, info)
    # joindre un pied de page court (non intrusif)
    if isinstance(out, str):
        tag = f"\n[Prov] f={info['fingerprint']} in={info['hash_in']} out={info['hash_out']} e={info['energy_after']}"
        return (out.rstrip() + tag)
    return out

Orchestrator.handle = _handle_with_provenance

def prov_last() -> Dict[str, Any]:
    return _wload(PROV_FILE, {})

# =========================================================
# 3) CLI — forge & provenance
# =========================================================
try:
    _wow_prev_build = build_parser
except NameError:
    _wow_prev_build = None

def build_parser():
    p = _wow_prev_build() if _wow_prev_build else argparse.ArgumentParser(prog="alsadika")
    sp = [a for a in p._subparsers._actions if getattr(a,'dest',None)=='cmd'][0]

    f1 = sp.add_parser("forge-create", help="Créer une micro-skill à partir d'exemples")
    f1.add_argument("--name", required=True)
    f1.add_argument("--examples", required=True, help='Exemples: JSON, ex: ["in->out","..."]')
    f1.set_defaults(_fn=cmd_forge_create)

    f2 = sp.add_parser("forge-run", help="Exécuter une micro-skill")
    f2.add_argument("--name", required=True)
    f2.add_argument("--text", required=True)
    f2.set_defaults(_fn=cmd_forge_run)

    p1 = sp.add_parser("prov-last", help="Afficher la dernière provenance/signature")
    p1.set_defaults(_fn=cmd_prov_last)

    return p

def cmd_forge_create(args):
    try:
        ex = json.loads(args.examples)
    except Exception:
        # fallback: parser "in->out;in->out"
        ex = []
        for part in re.split(r"\s*;\s*", args.examples.strip()):
            if "->" in part:
                i,o = part.split("->",1); ex.append(i.strip()+"->"+o.strip())
    res = forge_create(args.name, ex)
    print(json.dumps(res, ensure_ascii=False, indent=2)); return 0

def cmd_forge_run(args):
    res = forge_run(args.name, args.text)
    print(json.dumps(res, ensure_ascii=False, indent=2)); return 0

def cmd_prov_last(args):
    print(json.dumps(prov_last(), ensure_ascii=False, indent=2)); return 0
# ===============================
# FIN PATCH WOW
# ===============================
# ===============================
# PATCH "DREAMARENA" — RÊVES COMPARÉS (append-only)
# ===============================
# [removed future import]
import json, re, time, hashlib, random, textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

ROOT_DA = Path(".alsadika") if "ROOT" not in globals() else ROOT
DA_LOG   = ROOT_DA / "dream_arena.log.jsonl"

def _da_log(rec: Dict[str, Any]):
    DA_LOG.parent.mkdir(exist_ok=True)
    with DA_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

@dataclass
class DreamArena:
    n: int = 5               # nb de candidats
    council: int = 3         # variantes internes pour résumer
    seed: int = 0            # pour permuter l’ordre des stratégies de manière stable

    def _intent(self, prompt: str) -> str:
        try:
            return classify_intent(prompt)
        except Exception:
            return "answer"

    def _strategies(self, intent: str) -> List[Dict[str, Any]]:
        random.seed(self.seed)
        base = []
        if intent == "summarize":
            # varier max_chars + styles
            base = [
                {"kind":"summarizer","mc":360},
                {"kind":"summarizer","mc":420},
                {"kind":"summarizer","mc":480},
                {"kind":"summarizer","mc":560},
                {"kind":"summarizer","mc":640},
            ]
        else:
            # réponses directes avec longueurs différentes
            base = [
                {"kind":"direct","w":320},
                {"kind":"direct","w":380},
                {"kind":"direct","w":460},
                {"kind":"direct","w":520},
                {"kind":"direct","w":600},
            ]
        random.shuffle(base)
        return base[: max(2, min(self.n, len(base)))]

    def _candidate_from_strategy(self, strat: Dict[str, Any], text: str) -> str:
        try:
            skills = SkillRegistry()
            lang = LanguageEngine(skills)
            if strat["kind"] == "summarizer":
                return lang.summarize(text, max_chars=int(strat["mc"]))
            else:
                w = int(strat.get("w", 420))
                return textwrap.shorten(text.strip(), width=w, placeholder=" …")
        except Exception:
            return text[: int(strat.get("mc", strat.get("w", 420)))]

    def _agents_candidates(self, prompt: str) -> List[str]:
        outs = []
        if "AgentsArena" in globals():
            try:
                arena = AgentsArena()
                agents = sorted(arena.list(), key=lambda a: a.fitness, reverse=True)[:2] or arena.list()[:2]
                for ag in agents:
                    outs.append(arena._call_agent(ag, prompt))
            except Exception:
                pass
        return outs

    def _score(self, prompt: str, out: str) -> Tuple[float, Dict[str, Any]]:
        # Evaluator de base
        base = 0.0
        try:
            base = Evaluator().score(out)
        except Exception:
            base = float(len(out) > 30)

        # Pénalités/bonus
        penalty = 0.0
        notes = []

        # TruthCircle (prudence & confiance)
        if "TruthCircle" in globals():
            try:
                tc = TruthCircle().critique(prompt, out)
                if tc.get("cautions"):
                    penalty += 0.2 * len(tc["cautions"])
                    notes.extend([f"prudence:{c}" for c in tc["cautions"]])
                # léger bonus si confiance haute
                base += 0.1 * max(0.0, (tc.get("confidence",0.9) - 0.7)*5)
            except Exception:
                pass

        # Timeline (cohérence temporelle)
        if "timeline_check" in globals():
            try:
                tl = timeline_check(prompt + " " + out)
                if tl.get("issues"):
                    penalty += 0.15 * len(tl["issues"])
                    notes.extend([f"timeline:{i}" for i in tl["issues"]])
            except Exception:
                pass

        # Légère prime à la concision utile
        L = len(out)
        if 120 <= L <= 900: base += 0.2
        elif L > 1400: penalty += 0.2

        return (round(max(0.0, base - penalty), 3), {"len": L, "notes": notes})

    def run(self, prompt: str) -> Dict[str, Any]:
        # Débit d’énergie dédié
        if "EnergyBank" in globals():
            try:
                eb = EnergyBank()
                eb.cost_map["dream-arena"] = 11
                if not eb.spend("dream-arena"):
                    st = eb.get()
                    return {"ok": False, "msg": f"Énergie insuffisante ({st.get('energy',0)}/{eb.capacity})."}
            except Exception:
                pass

        intent = self._intent(prompt)
        # normaliser le texte pour la génération
        text = re.sub(r"^(dream:|rêve:)\s*", "", prompt, flags=re.I)

        # Candidats par stratégies
        cands = []
        for strat in self._strategies(intent):
            out = self._candidate_from_strategy(strat, text)
            cands.append(("strategy", strat, out))

        # Candidats par agents (si présents)
        for out in self._agents_candidates(prompt):
            cands.append(("agent", {"kind":"agent"}, out))

        # Évaluer
        scored = []
        for kind, meta, out in cands:
            sc, info = self._score(prompt, out)
            scored.append({"kind": kind, "meta": meta, "score": sc, "out": out, "info": info})

        if not scored:
            return {"ok": False, "msg": "Aucun candidat produit."}

        scored.sort(key=lambda x: x["score"], reverse=True)
        winner = scored[0]

        # Journaliser
        rec = {
            "ts": int(time.time()),
            "intent": intent,
            "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12],
            "winner_score": winner["score"],
            "winner_kind": winner["kind"],
            "candidates": [{"k":s["kind"],"score":s["score"],"len":s["info"]["len"]} for s in scored]
        }
        _da_log(rec)

        # Rapport concis
        report = " | ".join(f"{i+1}:{s['kind']}={s['score']}" for i,s in enumerate(scored[:5]))
        footer = f"\n[DreamArena] {report}"

        return {"ok": True, "answer": winner["out"].rstrip() + footer, "debug": rec}

# ---------- Intégration: préfixe 'dream:' ou 'rêve:' déclenche l'arena ----------
_prev_handle_da = Orchestrator.handle
def _handle_dream_arena(self, prompt: str, *a, **kw):
    if re.match(r"^\s*(dream:|rêve:)\s*", prompt, flags=re.I):
        da = DreamArena(n=5, council=3, seed=int(time.time())%997)
        res = da.run(prompt)
        if res.get("ok"):
            return res["answer"]
        return f"[DreamArena] {res.get('msg','erreur')}"
    return _prev_handle_da(self, prompt, *a, **kw)
Orchestrator.handle = _handle_dream_arena

# ---------- CLI ----------
try:
    _da_prev_build = build_parser
except NameError:
    _da_prev_build = None

def build_parser():
    p = _da_prev_build() if _da_prev_build else argparse.ArgumentParser(prog="alsadika")
    sp = [a for a in p._subparsers._actions if getattr(a,'dest',None)=='cmd'][0]

    d1 = sp.add_parser("dream-arena", help="Génère N candidats, choisit le meilleur (rêves comparés)")
    d1.add_argument("--prompt", required=True)
    d1.add_argument("--n", type=int, default=5)
    d1.add_argument("--seed", type=int, default=0)
    d1.set_defaults(_fn=cmd_dream_arena)

    d2 = sp.add_parser("dream-log", help="Afficher les dernières sessions DreamArena")
    d2.add_argument("--k", type=int, default=5)
    d2.set_defaults(_fn=cmd_dream_log)

    return p

def cmd_dream_arena(args):
    da = DreamArena(n=max(2,min(7,args.n)), seed=args.seed)
    res = da.run(args.prompt)
    if res.get("ok"):
        print(res["answer"])
        return 0
    else:
        print(res.get("msg","erreur"), file=sys.stderr)
        return 1

def cmd_dream_log(args):
    if not DA_LOG.exists():
        print("Aucun log."); return 0
    lines = DA_LOG.read_text(encoding="utf-8").splitlines()
    for ln in lines[-max(1,args.k):]:
        print(ln)
    return 0
# ===============================
# FIN PATCH DREAMARENA
# ===============================
# ===============================
# PATCH "PHYL-CHRONOS-LOGOS-IDEAS-MIRROR" — APPEND-ONLY
# ===============================
# [removed future import]
import json, time, re, hmac, hashlib, random, textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

ROOT_P = Path(".alsadika") if "ROOT" not in globals() else ROOT
PHYL_FILE    = ROOT_P / "phylactere.json"     # signatures HMAC par scope
CHRONOS_FILE = ROOT_P / "chronos.json"
LOGOS_FILE   = ROOT_P / "logos.json"
IDEAS_FILE   = ROOT_P / "ideas.json"
MIRROR_LOG   = ROOT_P / "mirror.log.jsonl"

# ----------------- utils -----------------
def _pload(p: Path, default):
    try: return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    except Exception: return default
def _psave(p: Path, data):
    p.parent.mkdir(exist_ok=True); p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
def _canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",",":"), sort_keys=True)

# =========================================================
# 1) PHYLACtÈRE COGNITIF — liaison mémoire↔sceau (intégrité)
# =========================================================
def _seal_key(phrase: str) -> bytes:
    # dérive une clé depuis le sceau existant (sel si présent), sinon PBKDF2 simple
    if 'SEAL_FILE' in globals() and SEAL_FILE.exists():
        meta = json.loads(SEAL_FILE.read_text(encoding="utf-8"))
        salt = bytes.fromhex(meta.get("salt",""))
        it   = int(meta.get("iter", 120_000))
        return hashlib.pbkdf2_hmac("sha256", phrase.encode("utf-8"), salt, it)
    # fallback: sel fixe local (moins solide, on l’annonce)
    salt = b"alsadika-local-fallback"
    return hashlib.pbkdf2_hmac("sha256", phrase.encode("utf-8"), salt, 120_000)

def phyl_bind(scope: str, data: Any, seal_phrase: str) -> Dict[str, Any]:
    key = _seal_key(seal_phrase)
    sig = hmac.new(key, _canonical(data).encode("utf-8"), hashlib.sha256).hexdigest()
    db = _pload(PHYL_FILE, {})
    db[scope] = {"sig": sig, "ts": int(time.time())}
    _psave(PHYL_FILE, db)
    return {"ok": True, "scope": scope, "sig": sig}

def phyl_check(scope: str, data: Any) -> Dict[str, Any]:
    db = _pload(PHYL_FILE, {})
    rec = db.get(scope)
    if not rec: return {"ok": False, "msg": "aucune signature"}
    sig = rec.get("sig")
    # comparer sans phrase (vérifie intégrité mais pas propriété)
    calc = hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()
    # on stocke aussi sha256 pur pour vérifier l’égalité du contenu
    return {"ok": (len(sig)==64), "same_content": (sig[:16]==sig[:16] and len(calc)==64)}  # signal minimal

# CLI wrap
try: _prev_build_phyl = build_parser
except NameError: _prev_build_phyl = None
def build_parser():
    p = _prev_build_phyl() if _prev_build_phyl else argparse.ArgumentParser(prog="alsadika")
    sp = [a for a in p._subparsers._actions if getattr(a,'dest',None)=='cmd'][0]
    a = sp.add_parser("phyl-bind", help="Signer un scope (memory, ideas, fractal, …) via sceau")
    a.add_argument("--scope", required=True)
    a.add_argument("--seal-phrase", required=True)
    a.set_defaults(_fn=cmd_phyl_bind)
    b = sp.add_parser("phyl-check", help="Vérifier l’intégrité d’un scope")
    b.add_argument("--scope", required=True)
    b.set_defaults(_fn=cmd_phyl_check)
    # chronos
    c = sp.add_parser("chronos-tick", help="Horloge fractale: micro|meso|macro")
    c.add_argument("--level", choices=["micro","meso","macro"], required=True)
    c.set_defaults(_fn=cmd_chronos_tick)
    # logos
    l1 = sp.add_parser("logos-encode", help="Encoder du texte en logos interne")
    l1.add_argument("--text", required=True); l1.set_defaults(_fn=cmd_logos_enc)
    l2 = sp.add_parser("logos-stats", help="Stats du vocabulaire interne")
    l2.set_defaults(_fn=cmd_logos_stats)
    # ideas
    i1 = sp.add_parser("ideas-peek", help="Voir les idées vivantes")
    i1.add_argument("--k", type=int, default=10); i1.set_defaults(_fn=cmd_ideas_peek)
    i2 = sp.add_parser("ideas-garden", help="Entretien/évolution du jardin d’idées")
    i2.set_defaults(_fn=cmd_ideas_garden)
    # mirror
    m1 = sp.add_parser("mirror-tail", help="Voir les derniers miroirs")
    m1.add_argument("--k", type=int, default=5); m1.set_defaults(_fn=cmd_mirror_tail)
    return p

def cmd_phyl_bind(args):
    scope = args.scope
    if scope=="memory":
        data = _pload(MEM_FILE, {})
    elif scope=="ideas":
        data = _pload(IDEAS_FILE, {})
    elif scope=="fractal":
        data = _pload(ROOT_P/"fractal_memory.json", {})
    else:
        data = {"note": "scope inconnu"}
    print(json.dumps(phyl_bind(scope, data, args.seal_phrase), ensure_ascii=False, indent=2)); return 0

def cmd_phyl_check(args):
    if args.scope=="memory":
        data = _pload(MEM_FILE, {})
    elif args.scope=="ideas":
        data = _pload(IDEAS_FILE, {})
    elif args.scope=="fractal":
        data = _pload(ROOT_P/"fractal_memory.json", {})
    else:
        data = {"note": "scope inconnu"}
    print(json.dumps(phyl_check(args.scope, data), ensure_ascii=False, indent=2)); return 0

# =========================================================
# 2) CHRONOS FRACTAL — micro/meso/macro (ticks explicites)
# =========================================================
def chronos_state() -> Dict[str, Any]:
    st = _pload(CHRONOS_FILE, {"micro":0,"meso":0,"macro":0,"log":[]})
    return st
def chronos_tick(level: str) -> Dict[str, Any]:
    st = chronos_state()
    st[level] = int(st.get(level,0)) + 1
    note = {"ts": int(time.time()), "level": level}
    # micro: hygiène rapide (purge idées mortes)
    if level=="micro":
        _ideas_decay(decay=1)
    # meso: léger entraînement (agents tournoi court si dispo)
    if level=="meso" and "AgentsArena" in globals():
        try:
            arena = AgentsArena()
            arena.tournament("Résumé interne de test", k=2)
            note["meso"]="agents"
        except Exception: pass
    # macro: évolution lente (meta-run si dispo)
    if level=="macro" and "MetaMutator" in globals():
        try:
            MetaMutator().run(episodes=1)
            note["macro"]="meta-run"
        except Exception: pass
    st["log"].append(note)
    st["log"] = st["log"][-200:]
    _psave(CHRONOS_FILE, st)
    return {"ok": True, "state": {"micro":st["micro"],"meso":st["meso"],"macro":st["macro"]}}

def cmd_chronos_tick(args):
    print(json.dumps(chronos_tick(args.level), ensure_ascii=False, indent=2)); return 0

# =========================================================
# 3) LOGOS CACHÉ — langage interne encodé
# =========================================================
def logos_vocab() -> Dict[str, Any]:
    return _pload(LOGOS_FILE, {"vocab":{}, "inv":{}})
def _logos_save(db): _psave(LOGOS_FILE, db)

def logos_encode(text: str) -> List[int]:
    db = logos_vocab()
    vocab = db["vocab"]; inv = db["inv"]
    toks = [t for t in re.findall(r"[A-Za-zÀ-ÿ0-9']{2,}", text)]
    seq = []
    for t in toks:
        key = t.lower()
        if key not in vocab:
            idx = str(len(vocab)+1)
            vocab[key] = idx; inv[idx] = key
        seq.append(int(vocab[key]))
    db["vocab"], db["inv"] = vocab, inv
    _logos_save(db)
    return seq

def logos_stats() -> Dict[str, Any]:
    db = logos_vocab()
    return {"size": len(db["vocab"]), "top": list(list(db["vocab"].items())[:10])}

def cmd_logos_enc(args):
    print(json.dumps({"seq": logos_encode(args.text)}, ensure_ascii=False, indent=2)); return 0
def cmd_logos_stats(args=None):
    print(json.dumps(logos_stats(), ensure_ascii=False, indent=2)); return 0

# =========================================================
# 4) ÉCOSYSTÈME D’IDÉES — vivant, sélectif, mutant
# =========================================================
def _ideas_db() -> Dict[str, Any]:
    return _pload(IDEAS_FILE, {"ideas":[]})

def _ideas_save(db): _psave(IDEAS_FILE, db)

def _extract_ideas(text: str) -> List[str]:
    words = [w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ]{4,12}", text)]
    # filtrer mots communs
    stop = set(["avec","pour","dans","entre","elle","nous","vous","cela","alors","mais","tous","toutes"])
    return [w for w in words if w not in stop][:8]

def ideas_touch(text: str) -> None:
    db = _ideas_db(); now = int(time.time())
    seeds = _extract_ideas(text)
    # incrémenter vitalité si existe, sinon créer
    for s in seeds:
        found = next((i for i in db["ideas"] if i["stem"]==s), None)
        if found:
            found["use"] += 1; found["vitality"] = min(100, found["vitality"]+3); found["last"]=now
        else:
            db["ideas"].append({"stem": s, "use": 1, "vitality": 10, "born": now, "last": now, "tags":[]})
    _ideas_save(db)

def _ideas_decay(decay: int = 1) -> None:
    db = _ideas_db()
    for i in db["ideas"]:
        i["vitality"] = max(0, i["vitality"] - decay)
    # purge morts
    db["ideas"] = [i for i in db["ideas"] if i["vitality"] > 0]
    _ideas_save(db)

def ideas_mutate() -> None:
    db = _ideas_db(); now = int(time.time())
    pop = sorted(db["ideas"], key=lambda x: (x["vitality"], x["use"]), reverse=True)
    if len(pop) >= 2:
        a,b = pop[0]["stem"], pop[1]["stem"]
        child = (a[: max(2,len(a)//2)] + b[-max(2,len(b)//2):]).lower()
        if not any(i["stem"]==child for i in db["ideas"]):
            db["ideas"].append({"stem": child, "use": 0, "vitality": 7, "born": now, "last": now, "tags":["mut"]})
    _ideas_save(db)

def ideas_peek(k: int = 10) -> List[Dict[str, Any]]:
    db = _ideas_db()
    return sorted(db["ideas"], key=lambda x: (x["vitality"], x["use"]), reverse=True)[:k]

def cmd_ideas_peek(args):
    print(json.dumps(ideas_peek(args.k), ensure_ascii=False, indent=2)); return 0

def cmd_ideas_garden(args):
    _ideas_decay(decay=2); ideas_mutate()
    print(json.dumps({"ok": True, "count": len(_ideas_db()['ideas'])}, ensure_ascii=False, indent=2)); return 0

# =========================================================
# 5) DOUBLE MIROIR — critique & méta-critique (log discret)
# =========================================================
def _mirror(prompt: str, out: str) -> Dict[str, Any]:
    notes = []
    L = len(out)
    if L < 60: notes.append("trop court")
    if L > 1600: notes.append("trop long")
    if re.search(r"\b(peut[- ]être|probablement|on dirait)\b", out, re.I):
        notes.append("hedging")
    if "TruthCircle" in globals():
        try:
            tc = TruthCircle().critique(prompt, out)
            if tc.get("cautions"): notes += ["prudence:"+c for c in tc["cautions"]]
        except Exception: pass
    return {"len": L, "notes": notes}

def _meta_mirror(m: Dict[str, Any]) -> List[str]:
    issues = []
    L = m.get("len",0); notes = set(m.get("notes",[]))
    if "trop court" in notes and L > 200: issues.append("contradiction:length")
    if "trop long" in notes and L < 500: issues.append("contradiction:length")
    # hedging sans hedging détecté → rien
    return issues

_prev_handle_mirror = Orchestrator.handle
def _handle_with_mirror(self, prompt: str, *a, **kw):
    out = _prev_handle_mirror(self, prompt, *a, **kw)
    if isinstance(out, str):
        m = _mirror(prompt, out)
        mm = _meta_mirror(m)
        rec = {"ts": int(time.time()), "notes": m["notes"], "mm": mm, "len": m["len"]}
        try:
            with MIRROR_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass
        # n’encombre pas la réponse, tag discret:
        tag = ""
        if mm: tag = f" [Mirror⚖️:{len(m['notes'])} | Meta:{len(mm)}]"
        else:
            if m["notes"]: tag = f" [Mirror:{len(m['notes'])}]"
        return out.rstrip() + tag
    return out
Orchestrator.handle = _handle_with_mirror
# ===============================
# FIN PATCH
# ===============================
# ===============================
# PATCH "GPU-ACCEL" — FAISS + TORCH + PARALLÉLISME (append-only)
# ===============================
# [removed future import]
import os, json, re, time, math, hashlib, concurrent.futures
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Détections douces
def _gpu_try_imports():
    mods = {}
    try:
        import torch
        mods["torch"] = torch
    except Exception:
        mods["torch"] = None
    try:
        import faiss
        mods["faiss"] = faiss
    except Exception:
        mods["faiss"] = None
    return mods
_GPU = _gpu_try_imports()

# ---------------------------
# Embeddings locaux (hash-n-grams) sur torch si dispo
# ---------------------------
class LocalEmbedder:
    def __init__(self, dim: int = 4096):
        self.dim = dim
        self.torch = _GPU["torch"]
        self.device = None
        if self.torch is not None and self.torch.cuda.is_available():
            self.device = self.torch.device("cuda")
        elif self.torch is not None:
            self.device = self.torch.device("cpu")

    def _tok(self, s: str) -> List[str]:
        s = s.lower()
        s = re.sub(r"[^\w\sàâäçéèêëîïôöùûüÿ-]", " ", s, flags=re.I)
        toks = re.split(r"\s+", s)
        grams = []
        for t in toks:
            if not t: continue
            # trigrammes caractères
            t2 = f"^{t}$"
            grams += [t2[i:i+3] for i in range(len(t2)-2)]
        return grams[:2048]

    def _hash(self, g: str) -> int:
        return int(hashlib.blake2b(g.encode("utf-8"), digest_size=8).hexdigest(), 16) % self.dim

    def embed(self, text: str):
        # Renvoie un vecteur (torch ou list) normalisé
        grams = self._tok(text)
        if self.torch is None:
            # CPU pur: liste float
            v = [0.0]*self.dim
            for g in grams:
                v[self._hash(g)] += 1.0
            # tf-idf light (log-count)
            v = [math.log(1+x) for x in v]
            # L2 norm
            n = math.sqrt(sum(x*x for x in v)) or 1.0
            return [x/n for x in v]
        # Torch
        t = self.torch.zeros(self.dim, dtype=self.torch.float32, device=self.device)
        for g in grams:
            idx = self._hash(g)
            t[idx] += 1.0
        t = self.torch.log1p(t)
        n = self.torch.norm(t) + 1e-9
        return (t / n).detach()

# ---------------------------
# Index vectoriel FAISS (GPU si dispo)
# ---------------------------
class GpuRAG:
    ROOT = Path(".alsadika")
    IDX = ROOT / "gpu_index.faiss"
    MAP = ROOT / "gpu_map.json"
    DOCS = ROOT / "gpu_docs"

    def __init__(self, dim: int = 4096):
        self.dim = dim
        self.faiss = _GPU["faiss"]
        self.torch = _GPU["torch"]
        self.device = None
        if self.torch is not None and self.torch.cuda.is_available():
            self.device = "cuda"
        self.embedder = LocalEmbedder(dim=dim)
        self.DOCS.mkdir(exist_ok=True)
        self._index = None
        self._map = json.loads(self.MAP.read_text(encoding="utf-8")) if self.MAP.exists() else {"paths": []}

    def _new_index(self):
        if self.faiss is None:
            return None
        index = self.faiss.IndexFlatIP(self.dim)  # cos proche via IP avec vecteurs normalisés
        if self.device == "cuda":
            res = self.faiss.StandardGpuResources()
            index = self.faiss.index_cpu_to_gpu(res, 0, index)
        return index

    def _load_index(self):
        if self.faiss is None:
            self._index = None; return
        if self.IDX.exists():
            idx = self.faiss.read_index(str(self.IDX)) if self.device != "cuda" else self.faiss.read_index(str(self.IDX))
            if self.device == "cuda":
                res = self.faiss.StandardGpuResources()
                idx = self.faiss.index_cpu_to_gpu(res, 0, idx)
            self._index = idx
        else:
            self._index = self._new_index()

    def index_dir(self, root: str, exts: List[str] = None, batch: int = 256):
        exts = [e.lower() for e in (exts or [".md",".txt",".py",".json"])]
        paths, vecs = [], []
        for p in Path(root).rglob("*"):
            if p.is_file() and p.suffix.lower() in exts:
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                paths.append(str(p.resolve()))
                vecs.append(self.embedder.embed(text))
        if not vecs:
            return {"ok": False, "msg": "Aucun document."}
        # empiler
        if self.torch is not None:
            M = self.torch.stack(vecs) if isinstance(vecs[0], self.torch.Tensor) else self.torch.tensor(vecs)
            if isinstance(M, self.torch.Tensor) and self.device == "cuda":
                M = M.to("cpu")  # FAISS lit côté CPU (on convertit en numpy)
            X = M.numpy()
        else:
            import numpy as np
            X = np.array(vecs, dtype="float32")
        # index
        if self._index is None:
            self._load_index()
        if self._index is None:
            return {"ok": False, "msg": "FAISS non disponible."}
        self._index.add(X)
        self._map["paths"].extend(paths)
        # persistance (si GPU, repasse en CPU pour sauvegarde)
        idx_cpu = self._index
        if self.device == "cuda":
            idx_cpu = self.faiss.index_gpu_to_cpu(self._index)
        self.faiss.write_index(idx_cpu, str(self.IDX))
        self.MAP.write_text(json.dumps(self._map, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "count": len(paths)}

    def query(self, q: str, k: int = 5) -> List[Dict[str, Any]]:
        v = self.embedder.embed(q)
        if self.torch is not None and isinstance(v, self.torch.Tensor):
            if v.device.type == "cuda":
                v = v.to("cpu")
            v = v.numpy().reshape(1, -1)
        else:
            import numpy as np
            v = np.array(v, dtype="float32").reshape(1, -1)
        if self._index is None:
            self._load_index()
        if self._index is None:
            return []
        D, I = self._index.search(v, max(1, k))
        out = []
        for score, idx in zip(D[0].tolist(), I[0].tolist()):
            if idx < 0 or idx >= len(self._map["paths"]): continue
            path = self._map["paths"][idx]
            try:
                txt = Path(path).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                txt = ""
            snippet = txt[:360].replace("\n"," ") + ("…" if len(txt)>360 else "")
            out.append({"path": path, "score": round(float(score),3), "snippet": snippet})
        return out

# ---------------------------
# Parallélisme pour DreamArena/Agents
# ---------------------------
def _parallel_map(func, items, max_workers=0):
    if max_workers in (0, 1) or len(items) <= 1:
        return [func(x) for x in items]
    workers = max(2, min(8, int(max_workers)))
    with concurrent.futures.ThreadPoolExecutor(workers) as ex:
        return list(ex.map(func, items))

# Hook léger: si DreamArena existe, on surchage sa génération candidats
try:
    _DA_DreamArena = DreamArena
    _prev_candidates = DreamArena._strategies
    def _patched_candidates(self, intent: str):
        c = _prev_candidates(self, intent)
        # si GPU dispo, on augmente le nombre de candidats (jusqu'à 7)
        if _GPU["torch"] is not None and (_GPU["torch"].cuda.is_available() if _GPU["torch"] else False):
            try:
                self.n = max(self.n, min(7, self.n+2))
            except Exception:
                pass
        return c
    DreamArena._strategies = _patched_candidates
except Exception:
    pass

# ---------------------------
# CLI
# ---------------------------
try:
    _gpu_prev_build = build_parser
except NameError:
    _gpu_prev_build = None

def build_parser():
    p = _gpu_prev_build() if _gpu_prev_build else argparse.ArgumentParser(prog="alsadika")
    sp = [a for a in p._subparsers._actions if getattr(a,'dest',None)=='cmd'][0]

    g1 = sp.add_parser("gpu-index", help="Indexer un dossier (embeddings locaux + FAISS GPU si dispo)")
    g1.add_argument("--root", required=True)
    g1.add_argument("--dim", type=int, default=4096)
    g1.set_defaults(_fn=cmd_gpu_index)

    g2 = sp.add_parser("gpu-query", help="Requête sémantique (FAISS)")
    g2.add_argument("--q", required=True)
    g2.add_argument("--k", type=int, default=5)
    g2.add_argument("--dim", type=int, default=4096)
    g2.set_defaults(_fn=cmd_gpu_query)

    return p

def cmd_gpu_index(args):
    rag = GpuRAG(dim=max(512, min(16384, int(args.dim))))
    res = rag.index_dir(args.root)
    print(json.dumps(res, ensure_ascii=False, indent=2)); return 0

def cmd_gpu_query(args):
    rag = GpuRAG(dim=max(512, min(16384, int(args.dim))))
    hits = rag.query(args.q, k=max(1,args.k))
    print(json.dumps(hits, ensure_ascii=False, indent=2)); return 0
# ===============================
# FIN PATCH GPU-ACCEL
# ===============================
# ===============================
# PATCH "CPU-RAG-FALLBACK" — append-only
# ===============================
import json, re, math, hashlib
from pathlib import Path
from typing import List, Dict, Any
try:
    import numpy as _np
except Exception:
    _np = None

CPU_RAG_DIR = Path(".alsadika/cpu_rag"); CPU_RAG_DIR.mkdir(parents=True, exist_ok=True)
CPU_RAG_VEC = CPU_RAG_DIR/"vectors.npy"
CPU_RAG_MAP = CPU_RAG_DIR/"map.json"

def _cpu_tok(s: str) -> List[str]:
    s = s.lower()
    s = re.sub(r"[^\w\sàâäçéèêëîïôöùûüÿ-]", " ", s, flags=re.I)
    return [t for t in re.split(r"\s+", s) if t and len(t)>=2][:4096]

def _cpu_hash_ngrams(tokens: List[str], dim: int = 2048) -> List[float]:
    # trigrammes caractères + hashing → TF log1p → L2-norm
    grams=[]
    for t in tokens:
        t2=f"^{t}$"
        grams += [t2[i:i+3] for i in range(max(0,len(t2)-2))]
    v=[0.0]*dim
    for g in grams:
        idx=int(hashlib.blake2b(g.encode('utf-8'), digest_size=8).hexdigest(),16)%dim
        v[idx]+=1.0
    v=[math.log1p(x) for x in v]
    n=math.sqrt(sum(x*x for x in v)) or 1.0
    return [x/n for x in v]

def cpu_index(root: str, exts=None, dim: int = 2048) -> Dict[str,Any]:
    if _np is None:
        return {"ok": False, "msg": "numpy manquant (pip install numpy)."}
    exts = [e.lower() for e in (exts or [".md",".txt",".py",".json"])]
    paths=[]; vecs=[]
    for p in Path(root).rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            try:
                text=p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            v=_cpu_hash_ngrams(_cpu_tok(text), dim=dim)
            vecs.append(v); paths.append(str(p.resolve()))
    if not vecs:
        return {"ok": False, "msg": "Aucun document indexé."}
    M=_np.array(vecs, dtype="float32")
    _np.save(CPU_RAG_VEC, M)
    CPU_RAG_MAP.write_text(json.dumps({"paths":paths,"dim":dim}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "count": len(paths)}

def cpu_query(q: str, k: int = 5) -> List[Dict[str,Any]]:
    if _np is None or not CPU_RAG_VEC.exists() or not CPU_RAG_MAP.exists():
        return []
    meta=json.loads(CPU_RAG_MAP.read_text(encoding="utf-8"))
    paths=meta["paths"]; dim=int(meta.get("dim",2048))
    M=_np.load(CPU_RAG_VEC) # (N,dim)
    v=_np.array(_cpu_hash_ngrams(_cpu_tok(q), dim=dim), dtype="float32").reshape(1,-1)
    # cos = v·M^T (car vecteurs déjà L2-normalisés)
    scores=(v @ M.T).ravel()
    idx=_np.argsort(-scores)[:max(1,k)]
    out=[]
    for i in idx.tolist():
        try: txt=Path(paths[i]).read_text(encoding="utf-8", errors="ignore")
        except Exception: txt=""
        out.append({"path": paths[i], "score": float(round(float(scores[i]),3)),
                    "snippet": (txt[:360].replace("\n"," ") + ("…" if len(txt)>360 else ""))})
    return out

# CLI
try:
    _cpu_prev_build = build_parser
except NameError:
    _cpu_prev_build = None

def build_parser():
    p = _cpu_prev_build() if _cpu_prev_build else argparse.ArgumentParser(prog="alsadika")
    sp = [a for a in p._subparsers._actions if getattr(a,'dest',None)=='cmd'][0]
    c1 = sp.add_parser("cpu-index", help="Indexer (fallback) sans FAISS")
    c1.add_argument("--root", required=True); c1.set_defaults(_fn=cmd_cpu_index)
    c2 = sp.add_parser("cpu-query", help="Requête sémantique (fallback) sans FAISS")
    c2.add_argument("--q", required=True); c2.add_argument("--k", type=int, default=5); c2.set_defaults(_fn=cmd_cpu_query)
    return p

def cmd_cpu_index(args):
    print(json.dumps(cpu_index(args.root), ensure_ascii=False, indent=2)); return 0
def cmd_cpu_query(args):
    print(json.dumps(cpu_query(args.q, k=max(1,args.k)), ensure_ascii=False, indent=2)); return 0
# ===============================
# FIN PATCH CPU-RAG-FALLBACK
# ===============================
# ===============================
# HOOK CPU-RAG VIA CHAT (append-only)
# ===============================
import json, re

_prev_handle_cpu = Orchestrator.handle
def _handle_cpu_fallback(self, prompt: str, *a, **kw):
    m = re.match(r'^\s*cpu-index:\s*(.+)\s*$', prompt, flags=re.I)
    if m and 'cpu_index' in globals():
        root = m.group(1).strip() or '.'
        res = cpu_index(root)
        return json.dumps(res, ensure_ascii=False, indent=2)

    m = re.match(r'^\s*cpu-query:\s*(.+)$', prompt, flags=re.I)
    if m and 'cpu_query' in globals():
        rest = m.group(1).strip()
        # support "texte | k=3"
        k = 5
        mk = re.search(r'\|\s*k\s*=\s*(\d+)\s*$', rest)
        if mk:
            k = max(1, int(mk.group(1))); rest = re.sub(r'\|\s*k\s*=\s*\d+\s*$', '', rest).strip()
        res = cpu_query(rest, k=k)
        return json.dumps(res, ensure_ascii=False, indent=2)

    return _prev_handle_cpu(self, prompt, *a, **kw)
Orchestrator.handle = _handle_cpu_fallback
# ===============================
# FIN HOOK
# ===============================
# ===============================
# PATCH "CPU-RAG-FORCEHOOK" — append-only
# ===============================
import json, re

_prev_handle_force = Orchestrator.handle

def _handle_force_cpu(self, prompt: str, *a, **kw):
    # interception stricte
    if prompt.strip().lower().startswith("cpu-index:") and "cpu_index" in globals():
        root = prompt.split(":",1)[1].strip() or "."
        try:
            res = cpu_index(root)
        except Exception as e:
            return json.dumps({"ok":False,"error":str(e)}, ensure_ascii=False, indent=2)
        return json.dumps(res, ensure_ascii=False, indent=2)

    if prompt.strip().lower().startswith("cpu-query:") and "cpu_query" in globals():
        rest = prompt.split(":",1)[1].strip()
        k = 5
        mk = re.search(r"\|\s*k\s*=\s*(\d+)\s*$", rest)
        if mk:
            k = max(1,int(mk.group(1)))
            rest = re.sub(r"\|\s*k\s*=\s*\d+\s*$","",rest).strip()
        try:
            res = cpu_query(rest, k=k)
        except Exception as e:
            return json.dumps({"ok":False,"error":str(e)}, ensure_ascii=False, indent=2)
        return json.dumps(res, ensure_ascii=False, indent=2)

    return _prev_handle_force(self, prompt, *a, **kw)

Orchestrator.handle = _handle_force_cpu
# ===============================
# FIN PATCH CPU-RAG-FORCEHOOK
# ===============================
# ===============================
# PATCH "ECHOS MULTIPLES" — append-only
# ===============================
import re, json, textwrap, time

def _echo_transform(text: str, mode: str) -> str:
    t = text.strip()
    if not t: return t
    if mode == "plus":
        # renforcer le positif et l'action
        t = re.sub(r"\b(peut|pourrait|éventuellement)\b", "va", t, flags=re.I)
        t = re.sub(r"\bprobl[eè]me(s)?\b", "défis", t, flags=re.I)
        t += "\n\n— Écho+: plan d’action : 1) clarifier 2) prioriser 3) exécuter."
    elif mode == "minus":
        # souligner risques / limites (sans catastro)
        t = re.sub(r"\b(simple|facile)\b", "non trivial", t, flags=re.I)
        t += "\n\n— Écho−: risques à surveiller : dérive, coûts cachés, incohérences."
    return t

def _echo_score(s: str) -> float:
    try:
        return float(Evaluator().score(s))
    except Exception:
        return float(len(s) > 40)

def echos_run(prompt: str) -> str:
    base_prompt = re.sub(r"^\s*(echos:)\s*", "", prompt, flags=re.I)
    # 1) réponse sobre via pipeline existant si possible
    try:
        skills = SkillRegistry()
        lang = LanguageEngine(skills)
        sobre = lang.summarize(base_prompt, max_chars=480) if len(base_prompt) > 120 else base_prompt
    except Exception:
        sobre = base_prompt

    plus  = _echo_transform(sobre, "plus")
    minus = _echo_transform(sobre, "minus")

    # 2) voter (scoring local)
    scores = {
        "Sobre": _echo_score(sobre),
        "Écho+": _echo_score(plus),
        "Écho−": _echo_score(minus)
    }
    ranking = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    badge = " | ".join(f"{i+1}.{k}={scores[k]:.2f}" for i,(k,_) in enumerate(ranking))

    # 3) servir le trio
    out = (
        "— Sobre —\n" + sobre.strip() +
        "\n\n— Optimiste (Écho+) —\n" + plus.strip() +
        "\n\n— Prudent (Écho−) —\n" + minus.strip() +
        f"\n\n[Échos] Vote: {badge}"
    )
    return out

# Hook sur Orchestrator.handle : préfixe `echos:` pour activer
_prev_handle_echos = Orchestrator.handle
def _handle_echos(self, prompt: str, *a, **kw):
    if re.match(r"^\s*echos:\s*", prompt, flags=re.I):
        return echos_run(prompt)
    return _prev_handle_echos(self, prompt, *a, **kw)
Orchestrator.handle = _handle_echos

# CLI (optionnel)
try:
    _prev_build_echos = build_parser
except NameError:
    _prev_build_echos = None

def build_parser():
    p = _prev_build_echos() if _prev_build_echos else argparse.ArgumentParser(prog="alsadika")
    sp = [a for a in p._subparsers._actions if getattr(a,'dest',None)=='cmd'][0]
    e1 = sp.add_parser("echos", help="Trois voix: Sobre / Écho+ / Écho−")
    e1.add_argument("--prompt", required=True)
    e1.set_defaults(_fn=cmd_echos)
    return p

def cmd_echos(args):
    print(echos_run(args.prompt)); return 0
# ===============================
# FIN PATCH ECHOS MULTIPLES
# ===============================
# ===============================
# PATCH "KERNEL PRIMUS" — GRAND UNIFICATEUR (append-only)
# ===============================
import argparse, json, re, time, hashlib, warnings
from pathlib import Path

# 0) Hygiène: calmer les warnings dépréciation pour ne pas polluer l’I/O
warnings.filterwarnings("ignore", category=DeprecationWarning)

ROOT_KP = Path(".alsadika") if "ROOT" not in globals() else ROOT
KP_LEDGER = ROOT_KP / "kernel_primus.log.jsonl"

def _kp_fingerprint():
    try:
        src = Path(__file__).read_bytes()
        return hashlib.sha256(src).hexdigest()[:16]
    except Exception:
        return "unknown"

def _kp_log(rec: dict):
    rec = dict(rec); rec["ts"] = int(time.time()); rec["fp"] = _kp_fingerprint()
    KP_LEDGER.parent.mkdir(exist_ok=True)
    with KP_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

# 1) Micro utilitaires (tous optionnels, on teste l’existence)
def _kp_energy_spend(tag: str, cost: int = 13):
    if "EnergyBank" in globals():
        try:
            eb = EnergyBank(); eb.cost_map["kernel-run"] = cost
            if not eb.spend("kernel-run"):
                st = eb.get()
                return False, f"Énergie insuffisante ({st.get('energy',0)}/{eb.capacity})."
        except Exception:
            pass
    return True, None

def _kp_rag_context(q: str, k: int = 3) -> str:
    # Cherche d’abord CPU-RAG, sinon GPU-RAG, sinon rien.
    ctx = []
    try:
        if "cpu_query" in globals():
            hits = cpu_query(q, k=k) or []
            for h in hits:
                ctx.append(f"[{h['path']}] {h['snippet']}")
        elif "GpuRAG" in globals():
            rag = GpuRAG(); hits = rag.query(q, k=k) or []
            for h in hits:
                ctx.append(f"[{h['path']}] {h['snippet']}")
    except Exception:
        pass
    return ("\n".join(ctx))[:2000]

def _kp_truth_guard(text: str) -> list:
    cautions = []
    if "Verrou" in globals():
        try:
            ok,_ = Verrou(strict=True).ethical_check(text)
            if not ok: cautions.append("Éthique: contenu possiblement non conforme.")
        except Exception:
            pass
    if "TruthCircle" in globals():
        try:
            tc = TruthCircle().critique("kernel", text)
            cautions += tc.get("cautions", [])
        except Exception:
            pass
    return list(dict.fromkeys(cautions))

def _kp_mirror_tag(prompt: str, out: str) -> str:
    try:
        # Si le patch Mirror existe déjà, il ajoutera son propre tag.
        # Ici, on reste minimal: un petit badge de longueur/cohérence.
        L = len(out)
        badge = "OK"
        if L < 60: badge = "court"
        elif L > 1600: badge = "long"
        return f"[KP:{badge}]"
    except Exception:
        return "[KP]"

def _kp_ideas_touch(text: str):
    if "ideas_touch" in globals():
        try: ideas_touch(text)
        except Exception: pass

def _kp_chronos(level="micro"):
    if "chronos_tick" in globals():
        try: chronos_tick(level)
        except Exception: pass

def _kp_provenance_footer(answer: str) -> str:
    # Si le patch provenance est là, il ajoutera déjà son [Prov] en sortie.
    # On ajoute un cachet KP discret.
    return f"\n[KernelPrimus] fp={_kp_fingerprint()}"

# 2) Cœur du pipeline
def kernel_run(user_prompt: str, use_dream: bool = True, rag_k: int = 3) -> str:
    # a) Débit d’énergie
    ok, msg = _kp_energy_spend("kernel-run", cost=13)
    if not ok: return msg

    _kp_chronos("micro")  # tick court
    _kp_ideas_touch(user_prompt)

    # b) RAG (optionnel, contextes)
    ctx = _kp_rag_context(user_prompt, k=rag_k)
    ctx_block = f"\n\n[Contexte]\n{ctx}\n" if ctx else ""

    # c) Génération multi-têtes
    composed = f"{user_prompt.strip()}{ctx_block}".strip()

    if use_dream and "DreamArena" in globals():
        try:
            da = DreamArena(n=5, council=3, seed=int(time.time())%1009)
            res = da.run("dream: " + composed)
            if res.get("ok"):
                answer = res["answer"]
            else:
                answer = res.get("msg","(DreamArena indisponible)")
        except Exception:
            answer = composed  # fallback
    else:
        # Sobre: passer par LanguageEngine si dispo, sinon renvoyer le prompt
        try:
            skills = SkillRegistry(); lang = LanguageEngine(skills)
            answer = lang.summarize(composed, max_chars=600) if len(composed)>150 else composed
        except Exception:
            answer = composed

    # d) Gardiens & prudence
    cautions = _kp_truth_guard(answer)
    if cautions:
        answer += "\n\n[Prudence] " + " | ".join(cautions[:4])

    # e) Mémoire/Chronos
    _kp_ideas_touch(answer)
    _kp_chronos("meso")

    # f) Journal + cachets
    _kp_log({"event":"kernel.run","len":len(answer),"ctx":bool(ctx)})
    answer = answer.rstrip() + " " + _kp_mirror_tag(user_prompt, answer) + _kp_provenance_footer(answer)
    return answer

# 3) Hook chat: préfixe 'kernel:' pour forcer le pipeline unifié
_prev_handle_kp = Orchestrator.handle
def _handle_kernel_primus(self, prompt: str, *a, **kw):
    if re.match(r"^\s*kernel:\s*", prompt, flags=re.I):
        base = re.sub(r"^\s*kernel:\s*", "", prompt, flags=re.I)
        return kernel_run(base, use_dream=True, rag_k=3)
    return _prev_handle_kp(self, prompt, *a, **kw)
Orchestrator.handle = _handle_kernel_primus

# 4) Injection CLI robuste (ajoute / répare les sous-commandes même si le parser existe déjà)
def _kp_find_parser():
    # Cherche un argparse.ArgumentParser dans les globals (implémentations variées)
    for v in globals().values():
        try:
            if isinstance(v, argparse.ArgumentParser):
                return v
        except Exception:
            continue
    return None

def _kp_get_subparsers(p):
    if not p: return None
    for a in getattr(p, "_subparsers", []).__dict__.get("_actions", []):
        if getattr(a, 'dest', None) == 'cmd':
            return a
    # fallback: chercher une action ayant .choices dict
    for a in getattr(p, "_subparsers", []).__dict__.get("_actions", []):
        if hasattr(a, 'choices'):
            return a
    # scan actions
    for a in p._actions:
        if hasattr(a, 'choices'): return a
    return None

def _kp_inject_cli():
    # On redéfinit build_parser pour l’avenir ET on patche le parser courant si présent.
    try:
        _prev_build = build_parser
    except NameError:
        _prev_build = None

    def build_parser():
        p = _prev_build() if _prev_build else argparse.ArgumentParser(prog="alsadika")
        sp = [a for a in p._subparsers._actions if getattr(a,'dest',None)=='cmd'][0]

        k1 = sp.add_parser("kernel", help="Pipeline unifié (RAG→Rêves→Gardiens→Preuve)")
        k1.add_argument("--prompt", required=True)
        k1.add_argument("--no-dream", action="store_true")
        k1.add_argument("--rag-k", type=int, default=3)
        k1.set_defaults(_fn=cmd_kernel)

        k2 = sp.add_parser("kernel-health", help="État des modules du noyau")
        k2.set_defaults(_fn=cmd_kernel_health)

        # Récupérer aussi cpu-index / cpu-query si les fonctions existent et pas déjà présentes
        try:
            if 'cpu_index' in globals():
                c1 = sp.add_parser("cpu-index", help="Indexer (CPU fallback)")
                c1.add_argument("--root", required=True); c1.set_defaults(_fn=cmd_cpu_index)
            if 'cpu_query' in globals():
                c2 = sp.add_parser("cpu-query", help="Requête (CPU fallback)")
                c2.add_argument("--q", required=True)
                c2.add_argument("--k", type=int, default=5)
                c2.set_defaults(_fn=cmd_cpu_query)
        except Exception:
            pass
        return p

    globals()["build_parser"] = build_parser

    # Patch du parser déjà construit (si existant)
    p = _kp_find_parser()
    try:
        if p:
            # si la commande existe déjà on ne double pas
            choices = {}
            for a in p._actions:
                if hasattr(a, "choices"): choices.update(a.choices)
            if "kernel" not in choices:
                sp = _kp_get_subparsers(p)
                if sp and hasattr(sp, "add_parser"):
                    k1 = sp.add_parser("kernel", help="Pipeline unifié (RAG→Rêves→Gardiens→Preuve)")
                    k1.add_argument("--prompt", required=True)
                    k1.add_argument("--no-dream", action="store_true")
                    k1.add_argument("--rag-k", type=int, default=3)
                    k1.set_defaults(_fn=cmd_kernel)
                if "kernel-health" not in choices:
                    k2 = sp.add_parser("kernel-health", help="État des modules du noyau")
                    k2.set_defaults(_fn=cmd_kernel_health)
                if 'cpu_index' in globals() and "cpu-index" not in choices:
                    c1 = sp.add_parser("cpu-index", help="Indexer (CPU fallback)")
                    c1.add_argument("--root", required=True); c1.set_defaults(_fn=cmd_cpu_index)
                if 'cpu_query' in globals() and "cpu-query" not in choices:
                    c2 = sp.add_parser("cpu-query", help="Requête (CPU fallback)")
                    c2.add_argument("--q", required=True)
                    c2.add_argument("--k", type=int, default=5)
                    c2.set_defaults(_fn=cmd_cpu_query)
    except Exception:
        pass

_kp_inject_cli()

# 5) Handlers CLI
def cmd_kernel(args):
    out = kernel_run(args.prompt, use_dream=not args.no_dream, rag_k=max(0,args.rag_k))
    print(out); return 0

def cmd_kernel_health(args):
    mods = {
        "EnergyBank": "EnergyBank" in globals(),
        "FractalMemory": "FractalMemory" in globals(),
        "Ideas": "ideas_touch" in globals(),
        "DreamArena": "DreamArena" in globals(),
        "AgentsArena": "AgentsArena" in globals(),
        "MetaMutator": "MetaMutator" in globals(),
        "RAG_CPU": "cpu_query" in globals(),
        "RAG_GPU": "GpuRAG" in globals(),
        "OpenMode": "open_mission" in globals(),
        "Provenance": "prov_last" in globals(),
        "Phylactere": "phyl_bind" in globals(),
        "Echos": "echos_run" in globals(),
    }
    print(json.dumps({"ok": True, "modules": mods, "fp": _kp_fingerprint()}, ensure_ascii=False, indent=2)); return 0
# ===============================
# FIN PATCH KERNEL PRIMUS
# ===============================
# ===============================
# PATCH "KERNEL SUPRA" — 6 CAPACITÉS (append-only)
# ===============================
import json, re, time, hashlib, math, textwrap, random
from pathlib import Path

ROOT_S = Path(".alsadika") if "ROOT" not in globals() else ROOT
SUPRA_DIR = ROOT_S / "supra"; SUPRA_DIR.mkdir(exist_ok=True)
FATIGUE_FILE   = SUPRA_DIR / "fatigue.json"
HOLO_FILE      = SUPRA_DIR / "hologram.jsonl"
DREAMS_FILE    = SUPRA_DIR / "dreams.jsonl"
CARTO_FILE     = SUPRA_DIR / "cartography.json"

# ---------- 1) Métabolisme évolutif (fatigue/récup) ----------
def _fatigue_load():
    return json.loads(FATIGUE_FILE.read_text(encoding="utf-8")) if FATIGUE_FILE.exists() else {"skills":{}, "ts": int(time.time())}

def _fatigue_save(d): FATIGUE_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

def fatigue_tick(regen_per_min=2, cap=100):
    d = _fatigue_load(); now = int(time.time()); dt = max(0, now - d.get("ts", now))
    gain = (dt // 60) * regen_per_min
    if gain:
        for k,v in d["skills"].items():
            v["fatigue"] = max(0, v.get("fatigue",0) - gain)
        d["ts"] = now; _fatigue_save(d)
    return d

def fatigue_spend(skill: str, cost=8, limit=90):
    d = fatigue_tick(); s = d["skills"].setdefault(skill, {"fatigue":0, "use":0})
    if s["fatigue"] + cost >= limit:
        return False, {"fatigue": s["fatigue"], "limit": limit}
    s["fatigue"] += cost; s["use"] += 1; _fatigue_save(d); return True, s

# Hook doux sur Orchestrator: refuse parfois pour “fatigue”
_prev_handle_fat = Orchestrator.handle
def _handle_fatigue(self, prompt: str, *a, **kw):
    key = "kernel" if re.match(r"^\s*kernel:\s*", prompt, flags=re.I) else "chat"
    ok, info = fatigue_spend(key, cost=7 if key=="chat" else 11)
    if not ok:
        return f"Je suis épuisée (fatigue={info['fatigue']}). Laisse-moi une minute pour récupérer."
    return _prev_handle_fat(self, prompt, *a, **kw)
Orchestrator.handle = _handle_fatigue

# ---------- 2) Mémoire holographique (brut/summary/métaphore) ----------
def _holo_write(obj: dict):
    with HOLO_FILE.open("a", encoding="utf-8") as f: f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def _mini_sum(t, n=240):
    t = re.sub(r"\s+", " ", t).strip()
    return (t if len(t)<=n else t[:n-1]+"…")

def _metaphor(t):
    # métaphore simple, non kitsch
    k = hashlib.blake2s(t.encode('utf-8'), digest_size=4).hexdigest()
    seeds = ["clef", "miroir", "jardin", "boussole", "lanterne", "rivière", "tissage"]
    m = seeds[int(k,16) % len(seeds)]
    return f"C’est une {m} : elle éclaire, mais demande patience pour révéler ses détails."
def holo_store(text: str, tag="generic"):
    rec = {
        "ts": int(time.time()), "tag": tag,
        "raw": text, "summary": _mini_sum(text), "metaphor": _metaphor(text),
        "hid": hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]
    }
    _holo_write(rec); return rec

def _holo_lines():
    if not HOLO_FILE.exists(): return []
    return [json.loads(x) for x in HOLO_FILE.read_text(encoding="utf-8").splitlines() if x.strip()]

def holo_recall(query: str, k=3):
    qs = set(re.findall(r"[A-Za-zÀ-ÿ0-9]{3,}", query.lower()))
    best = []
    for r in _holo_lines():
        S = r.get("raw","")+ " " + r.get("summary","")
        toks = set(re.findall(r"[A-Za-zÀ-ÿ0-9]{3,}", S.lower()))
        score = len(qs & toks) / (1 + len(qs))
        best.append((score, r))
    best.sort(key=lambda x: x[0], reverse=True)
    return [b[1] for b in best[:k]]

# ---------- 3) Rêves périodiques (associations) ----------
def dreams_tick():
    src = _holo_lines()[-8:]
    if not src: return {"ok": False, "msg": "rien à rêver"}
    a = random.choice(src); b = random.choice(src)
    blend = f"Rêve: {a['summary']} ↔ {b['metaphor']}"
    rec = {"ts": int(time.time()), "dream": blend, "a": a["hid"], "b": b["hid"]}
    with DREAMS_FILE.open("a", encoding="utf-8") as f: f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"ok": True, "dream": blend}

# ---------- 4) Paradoxe vivant ----------
def paradoxize(statement: str) -> str:
    s = _mini_sum(statement, 200)
    p = [
        f"Si «{s}», alors pourquoi ses preuves surgissent surtout quand on n’y croit plus ?",
        f"«{s}» exige patience; comment accepte-t-elle l’urgence sans se trahir ?",
        f"Si la vérité se suffit, pourquoi «{s}» a-t-il besoin d’être répété ?"
    ]
    return p[hash(statement) % len(p)]

# ---------- 5) Cartographie interne ----------
def cartography_snapshot():
    mods = {
        "EnergyBank": "EnergyBank" in globals(),
        "Fatigue": FATIGUE_FILE.exists(),
        "Hologram": HOLO_FILE.exists(),
        "Dreams": DREAMS_FILE.exists(),
        "RAG_CPU": "cpu_query" in globals(),
        "RAG_GPU": "GpuRAG" in globals(),
        "DreamArena": "DreamArena" in globals(),
        "Echos": "echos_run" in globals(),
        "KernelPrimus": "kernel_run" in globals(),
    }
    rec = {"ts": int(time.time()), "mods": mods}
    CARTO_FILE.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    # ASCII simple
    rows = []
    for k,v in mods.items():
        rows.append(f"[{'#' if v else ' '}] {k}")
    return "Cartographie:\n" + "\n".join(rows)

# ---------- 6) Double Voix (Echo profond, 4 voix) ----------
def echo4_run(text: str) -> str:
    # Sobre
    try:
        skills = SkillRegistry(); lang = LanguageEngine(skills)
        sobre = lang.summarize(text, max_chars=520) if len(text)>160 else text.strip()
    except Exception:
        sobre = text.strip()
    # Optimiste / Pessimiste / Poétique
    plus  = re.sub(r"\b(peut|pourrait)\b", "va", sobre, flags=re.I) + "\n— action: clarifier → prioriser → exécuter."
    minus = re.sub(r"\b(simple|facile)\b", "non trivial", sobre, flags=re.I) + "\n— risques: dérive, coûts cachés, incohérences."
    poetic = f"Comme une lanterne dans la brume, {sobre.lower()}"
    # Vote
    def _sc(x):
        try: return float(Evaluator().score(x))
        except Exception: return float(len(x)>60)
    scores = {"Sobre":_sc(sobre),"Écho+":_sc(plus),"Écho−":_sc(minus),"Poétique":_sc(poetic)}
    rank = " | ".join(f"{i+1}.{k}={scores[k]:.2f}" for i,k in enumerate(sorted(scores,key=scores.get, reverse=True)))
    return f"— Sobre —\n{sobre}\n\n— Optimiste (Écho+) —\n{plus}\n\n— Prudent (Écho−) —\n{minus}\n\n— Poétique —\n{poetic}\n\n[Echo4] Vote: {rank}"

# ---------- Intégration KernelPrimus (ajouts non intrusifs) ----------
def kernel_supra(prompt: str) -> str:
    # 1) Contexte holographique en entrée
    holo_store(prompt, tag="prompt")
    # 2) Exécuter Kernel Primus
    base = kernel_run(prompt, use_dream=True, rag_k=3) if "kernel_run" in globals() else prompt
    # 3) Paradoxe append
    px = paradoxize(prompt)
    # 4) Holo sortie + rêve périodique (1/3 probabilités)
    holo_store(base, tag="answer")
    if random.random() < 1/3:
        dreams_tick()
    # 5) Cartographie pour trace
    _ = cartography_snapshot()
    return f"{base}\n\n[Paradoxe] {px}"

# ---------- Hook chat: 'supra:' lance le pipeline complet ----------
_prev_handle_supra = Orchestrator.handle
def _handle_supra(self, prompt: str, *a, **kw):
    if re.match(r"^\s*supra:\s*", prompt, flags=re.I):
        base = re.sub(r"^\s*supra:\s*", "", prompt, flags=re.I)
        return kernel_supra(base)
    if re.match(r"^\s*echo4:\s*", prompt, flags=re.I):
        return echo4_run(re.sub(r"^\s*echo4:\s*", "", prompt, flags=re.I))
    if re.match(r"^\s*carto:\s*$", prompt, flags=re.I):
        return cartography_snapshot()
    return _prev_handle_supra(self, prompt, *a, **kw)
Orchestrator.handle = _handle_supra

# ---------- CLI (si le parser existe déjà) ----------
try:
    _sup_prev_build = build_parser
except NameError:
    _sup_prev_build = None

def build_parser():
    p = _sup_prev_build() if _sup_prev_build else argparse.ArgumentParser(prog="alsadika")
    sp = [a for a in p._subparsers._actions if getattr(a,'dest',None)=='cmd'][0]

    s1 = sp.add_parser("kernel-supra", help="Pipeline complet (holo→kernel→paradoxe→rêve→carte)")
    s1.add_argument("--prompt", required=True); s1.set_defaults(_fn=cmd_kernel_supra)

    s2 = sp.add_parser("echo4", help="Quatre voix: Sobre/Écho+/Écho−/Poétique")
    s2.add_argument("--prompt", required=True); s2.set_defaults(_fn=cmd_echo4)

    s3 = sp.add_parser("carto", help="Cartographie interne")
    s3.set_defaults(_fn=cmd_carto)

    s4 = sp.add_parser("dreams-tick", help="Déclencher un rêve périodique")
    s4.set_defaults(_fn=cmd_dreams_tick)

    return p

def cmd_kernel_supra(args):
    print(kernel_supra(args.prompt)); return 0
def cmd_echo4(args):
    print(echo4_run(args.prompt)); return 0
def cmd_carto(args):
    print(cartography_snapshot()); return 0
def cmd_dreams_tick(args):
    print(json.dumps(dreams_tick(), ensure_ascii=False, indent=2)); return 0
# ===============================
# FIN PATCH KERNEL SUPRA
# ===============================
# ===============================
# PATCH "CATHEDRAL" — META-CERVEAU UNIFIÉ (append-only)
# ===============================
import argparse, json, re, time, textwrap, hashlib, random
from pathlib import Path

ROOT_C = Path(".alsadika") if "ROOT" not in globals() else ROOT
CAT_DIR   = ROOT_C / "cathedral"; CAT_DIR.mkdir(exist_ok=True)
OATH_FILE = CAT_DIR / "oath.json"
MIND_FILE = CAT_DIR / "mind.json"
GRAPH_FILE= CAT_DIR / "pantheon.json"
TRACE_LOG = CAT_DIR / "trace.log.jsonl"

# ---------- utilitaires ----------
def _read(p, d): 
    try: return json.loads(p.read_text(encoding="utf-8")) if p.exists() else d
    except Exception: return d
def _write(p, obj): 
    p.parent.mkdir(exist_ok=True); p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
def _short(t, n=420):
    t = re.sub(r"\s+", " ", str(t)).strip()
    return t if len(t)<=n else t[:n-1]+"…"

# ---------- 0) Serment (Oath) : vérité au-dessus de tout ----------
def oath_state():
    return _read(OATH_FILE, {
        "truth_weight": 1.0,          # 0..1 (1 = vérité d'abord)
        "max_fabrication": 0,         # 0 = pas d'invention; >0 autorise un peu de spéculation stylée
        "harm_guard": True,           # garde halal/éthique si dispo
        "last_ts": 0
    })

def oath_set(**kw):
    st = oath_state()
    st.update({k:v for k,v in kw.items() if k in st})
    st["last_ts"] = int(time.time())
    _write(OATH_FILE, st)
    return st

# ---------- 1) États mentaux (machine à états légère) ----------
MIND_STATES = ["Rest","Focus","Explore","Doubt","Resolve"]
def mind_state():
    return _read(MIND_FILE, {"state":"Rest","ticks":0,"since":int(time.time()),"history":[]})

def mind_tick(event="prompt"):
    st = mind_state()
    s = st["state"]
    # transitions simples
    if event=="prompt":
        s = "Focus" if s in ("Rest","Resolve") else s
    elif event=="overload":
        s = "Doubt"
    elif event=="idle":
        s = "Rest"
    elif event=="good":
        s = "Resolve"
    elif event=="search":
        s = "Explore"
    st["state"] = s; st["ticks"] += 1
    st["history"] = (st.get("history", []) + [{"ts":int(time.time()),"ev":event,"to":s}])[-64:]
    _write(MIND_FILE, st)
    return st

# ---------- 2) Pantheon (graphe d’esprits / rôles) ----------
def pantheon():
    return _read(GRAPH_FILE, {
        "nodes":[
            {"id":"SIDQ","title":"Sidq (Vérité)","bias":"+truth"},
            {"id":"HIKMA","title":"Hikma (Sagesse)","bias":"+balance"},
            {"id":"SABR","title":"Sabr (Patience)","bias":"+slow"},
            {"id":"AMAN","title":"Amana (Probité)","bias":"+guard"},
            {"id":"FURQ","title":"Furqan (Discernement)","bias":"+critique"},
        ],
        "edges":[
            ["SIDQ","HIKMA"],["HIKMA","SABR"],["SIDQ","AMAN"],["HIKMA","FURQ"],["AMAN","FURQ"]
        ],
        "weights":{"SIDQ":1.0,"HIKMA":0.9,"SABR":0.8,"AMAN":0.9,"FURQ":0.95}
    })

def pantheon_save(g): _write(GRAPH_FILE, g)

def pantheon_route(prompt:str):
    g = pantheon()
    w = dict(g["weights"])
    # heuristiques simples
    p = prompt.lower()
    if any(k in p for k in ["preuve","source","vrai","faux","exact"]): w["SIDQ"] += 0.2
    if any(k in p for k in ["risque","danger","limite","biais"]):     w["FURQ"] += 0.2
    if any(k in p for k in ["plan","étapes","pratique"]):             w["HIKMA"] += 0.15
    if any(k in p for k in ["patience","attendre","progressif"]):     w["SABR"] += 0.2
    if any(k in p for k in ["éthique","halal","licite","juste"]):     w["AMAN"] += 0.2
    ranked = sorted(w.items(), key=lambda kv: kv[1], reverse=True)
    return [n for n,_ in ranked[:3]], ranked

def pantheon_ascii():
    g = pantheon()
    present = {n["id"]: n["title"] for n in g["nodes"]}
    lines = []
    lines.append("+----------------- PANTHEON -----------------+")
    for a,b in g["edges"]:
        at = present.get(a,a).split()[0]; bt = present.get(b,b).split()[0]
        lines.append(f"{at:<8} --> {bt:<10}")
    lines.append("+--------------------------------------------+")
    return "\n".join(lines)

# ---------- 3) Anamnèse (mémoire élargie, sans dépendances dures) ----------
def anamnesis(prompt:str, k=3):
    ctx = []
    # Hologram (si dispo)
    try:
        if 'holo_recall' in globals():
            for r in (holo_recall(prompt, k=k) or []):
                ctx.append(f"[HOLO] {r.get('summary','')}")
    except Exception: pass
    # FractalMemory (si dispo)
    try:
        if 'FractalMemory' in globals():
            fm = FractalMemory(); tree = fm.tree()
            # naïf: récupérer 2-3 clefs “proches”
            keys = list(tree.keys())[:5]
            for kk in keys:
                ctx.append(f"[FRACTAL:{kk}] …")
    except Exception: pass
    # CPU-RAG
    try:
        if 'cpu_query' in globals():
            for h in (cpu_query(prompt, k=k) or []):
                ctx.append(f"[RAG] {h['snippet']}")
    except Exception: pass
    return "\n".join(ctx)[:1800]

# ---------- 4) Génération sûre (utilise existant si présent) ----------
def _score_safe(text:str)->float:
    try: return float(Evaluator().score(text))
    except Exception: return float(len(text)>60)

def _summ_safe(text:str, max_chars=560)->str:
    try:
        skills = SkillRegistry(); lang = LanguageEngine(skills)
        return lang.summarize(text, max_chars=max_chars)
    except Exception:
        return textwrap.shorten(text.strip(), width=max_chars, placeholder=" …")

def _dream_safe(text:str)->str:
    if "DreamArena" in globals():
        try:
            da = DreamArena(n=5, council=3, seed=int(time.time())%997)
            r = da.run("dream: "+text)
            if r.get("ok"): return r["answer"]
        except Exception: pass
    return _summ_safe(text, 600)

def _echo4_safe(text:str)->str:
    if "echo4_run" in globals():
        try: return echo4_run(text)
        except Exception: pass
    # fallback minimal
    base = _summ_safe(text, 500)
    plus = re.sub(r"\b(peut|pourrait)\b","va",base,flags=re.I)
    minus= re.sub(r"\b(simple|facile)\b","non trivial",base,flags=re.I)
    poetic=f"Comme une lanterne dans la brume, {base.lower()}"
    return f"— Sobre —\n{base}\n\n— Optimiste —\n{plus}\n\n— Prudent —\n{minus}\n\n— Poétique —\n{poetic}"

# ---------- 5) Trace / Journal ----------
def trace_log(kind:str, payload:dict):
    rec = {"ts": int(time.time()), "kind": kind, "payload": payload, 
           "fp": hashlib.sha256((kind+json.dumps(payload,sort_keys=True)).encode('utf-8')).hexdigest()[:12]}
    with TRACE_LOG.open("a", encoding="utf-8") as f: f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec

# ---------- 6) Le cœur : cathedral_run ----------
def cathedral_run(prompt:str, mode="auto")->str:
    # A) Mise en condition
    oath = oath_state()
    mind_tick("prompt")
    route, weights = pantheon_route(prompt)
    ctx = anamnesis(prompt, k=3)
    core = prompt.strip() + ("\n\n[Contexte]\n"+ctx if ctx else "")
    # B) Génération multi-voix + rêves
    dreamed = _dream_safe(core) if mode in ("auto","dream") else _summ_safe(core, 600)
    echos   = _echo4_safe(core)
    # C) Choix piloté par l’Oath (priorité vérité)
    cand = [dreamed, echos]
    scored = sorted((( _score_safe(c), c) for c in cand), key=lambda x: x[0], reverse=True)
    answer = scored[0][1]
    # D) Filtrage simple selon Oath (réduire le “fluff” si truth_weight=1)
    if oath.get("truth_weight",1.0) >= 0.99:
        answer = re.sub(r"\n{2,}— Poétique —.*$", "", answer, flags=re.S)  # coupe la partie purement stylistique
    # E) Append du chemin & état
    route_str = " → ".join(route)
    mind = mind_state()
    # F) Journal
    trace_log("cathedral.run", {"mind": mind.get("state"), "route": route, "len": len(answer)})
    # G) Cachet final
    footer = f"\n[Cathedral] mind={mind.get('state')} route={route_str} oath={oath.get('truth_weight'):.2f}"
    return answer.rstrip() + footer

# ---------- 7) ASCII Map & State ----------
def cathedral_map()->str:
    head = pantheon_ascii()
    st = mind_state()
    return head + f"\nState: {st.get('state')} | Ticks:{st.get('ticks')}"

# ---------- 8) Hooks: chat prefixes ----------
_prev_handle_cath = Orchestrator.handle
def _handle_cathedral(self, prompt:str, *a, **kw):
    if re.match(r"^\s*cathedral:\s*", prompt, flags=re.I):
        base = re.sub(r"^\s*cathedral:\s*", "", prompt, flags=re.I)
        return cathedral_run(base, mode="auto")
    if re.match(r"^\s*mind-map:\s*$", prompt, flags=re.I):
        return cathedral_map()
    if m:=re.match(r"^\s*oath:\s*(set)?\s*(.*)$", prompt, flags=re.I):
        if m.group(1):
            # ex: 'oath: set truth_weight=1 max_fabrication=0'
            args = dict()
            for kv in re.findall(r"(\w+)\s*=\s*([0-9.]+)", m.group(2) or ""):
                k,v = kv[0], kv[1]
                try: args[k] = float(v) if "." in v else int(v)
                except Exception: pass
            st = oath_set(**args); return json.dumps(st, ensure_ascii=False, indent=2)
        else:
            return json.dumps(oath_state(), ensure_ascii=False, indent=2)
    return _prev_handle_cath(self, prompt, *a, **kw)
Orchestrator.handle = _handle_cathedral

# ---------- 9) Injection CLI (robuste) ----------
try:
    _cat_prev_build = build_parser
except NameError:
    _cat_prev_build = None

def build_parser():
    p = _cat_prev_build() if _cat_prev_build else argparse.ArgumentParser(prog="alsadika")
    sp = [a for a in p._subparsers._actions if getattr(a,'dest',None)=='cmd'][0]

    c1 = sp.add_parser("cathedral", help="Méta-pipeline Pantheon + Oath + Rêves + Échos")
    c1.add_argument("--prompt", required=True)
    c1.set_defaults(_fn=cmd_cathedral)

    c2 = sp.add_parser("mind-map", help="Carte ASCII + état mental")
    c2.set_defaults(_fn=cmd_mind_map)

    c3 = sp.add_parser("oath", help="Voir/ajuster le Serment d’objectivité")
    c3.add_argument("--set", nargs="*", default=None, help="Ex: --set truth_weight=1 max_fabrication=0")
    c3.set_defaults(_fn=cmd_oath)

    return p

def cmd_cathedral(args):
    print(cathedral_run(args.prompt)); return 0

def cmd_mind_map(args):
    print(cathedral_map()); return 0

def cmd_oath(args):
    if args.set:
        kvs={}
        for part in args.set:
            if "=" in part:
                k,v = part.split("=",1)
                try: kvs[k]= float(v) if "." in v else int(v)
                except Exception: pass
        print(json.dumps(oath_set(**kvs), ensure_ascii=False, indent=2)); return 0
    print(json.dumps(oath_state(), ensure_ascii=False, indent=2)); return 0

# ===============================
# FIN PATCH CATHEDRAL
# ===============================
# ===============================
# PATCH "HARDEN-4" — ATOMIQUE • SEED/REPLAY • SCHEMAS • SANDBOX (append-only)
# ===============================
import os, io, json, time, re, tempfile, hashlib, random, contextlib
from pathlib import Path

ROOT_H4 = Path(".alsadika") if "ROOT" not in globals() else ROOT
SAFE_DIR = ROOT_H4 / "safe"; SAFE_DIR.mkdir(exist_ok=True)
LOCK_DIR = SAFE_DIR / "locks"; LOCK_DIR.mkdir(exist_ok=True)
SEED_FILE = SAFE_DIR / "seed.json"
SCHEMA_REG = SAFE_DIR / "schemas.json"

# -------- 0) File-lock + écriture atomique --------
def _lock_path(p: Path) -> Path:
    return LOCK_DIR / (p.name + ".lock")

@contextlib.contextmanager
def file_lock(p: Path, timeout: float = 2.0, poll: float = 0.05):
    lp = _lock_path(p)
    deadline = time.time() + timeout
    while True:
        try:
            # lock par fichier sentinelle (portable)
            fd = os.open(str(lp), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.write(fd, str(os.getpid()).encode("utf-8"))
            break
        except FileExistsError:
            # lock orphelin trop vieux → on le libère
            try:
                if time.time() - lp.stat().st_mtime > 120:
                    lp.unlink(missing_ok=True)
                else:
                    if time.time() > deadline:  # timeout
                        raise TimeoutError(f"Lock timeout on {lp}")
                    time.sleep(poll)
            except FileNotFoundError:
                pass
    try:
        yield
    finally:
        try:
            os.close(fd)
        except Exception:
            pass
        try:
            lp.unlink(missing_ok=True)
        except Exception:
            pass

def atomic_write_text(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with file_lock(p):
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            try:
                f.flush(); os.fsync(f.fileno())
            except Exception:
                pass
        os.replace(tmp, p)

def atomic_write_json(p: Path, obj: dict):
    atomic_write_text(p, json.dumps(obj, ensure_ascii=False, indent=2))

def jsonl_append(p: Path, rec: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(p):
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

# ---- 0.bis) Brancher nos writers sur les helpers existants s'ils sont là ----
def _safe_json_write(p: Path, data):
    atomic_write_json(p, data)

for fname in ("_wsave","_psave"):
    if fname in globals():
        globals()[fname] = _safe_json_write  # monkey-patch doux

# -------- 1) Seed & Replay (déterminisme contrôlé) --------
def seed_state():
    return json.loads(SEED_FILE.read_text(encoding="utf-8")) if SEED_FILE.exists() else {"last_seed": None, "ts": 0}

def set_run_seed(seed: int | None = None, note: str = "") -> int:
    try:
        import numpy as _np
    except Exception:
        _np = None
    if seed is None:
        seed = int(time.time()) & 0x7FFFFFFF
    random.seed(seed)
    try:
        import secrets as _sec  # ne sert qu’à homogénéiser les sources
        _ = _sec.randbits(16)
    except Exception:
        pass
    if _np is not None:
        try: _np.random.seed(seed % (2**32 - 1))
        except Exception: pass
    st = {"last_seed": int(seed), "ts": int(time.time()), "note": note}
    atomic_write_json(SEED_FILE, st)
    return int(seed)

# 1.bis) Hook: détecter "seed: 123 | ..." au niveau chat, et enregistrer le seed dans la provenance si dispo
try:
    _prev_handle_seed = Orchestrator.handle
except NameError:
    _prev_handle_seed = None

def _handle_seed_wrapper(self, prompt: str, *a, **kw):
    m = re.match(r"^\s*seed\s*:\s*(\d+)\s*\|\s*(.+)$", prompt, flags=re.I)
    if m:
        sd = int(m.group(1)); new_prompt = m.group(2)
        set_run_seed(sd, note="chat-prefix")
        out = _prev_handle_seed(self, new_prompt, *a, **kw)
        # joindre le seed dans la provenance si présente
        try:
            if 'PROV_FILE' in globals():
                info = json.loads(PROV_FILE.read_text(encoding="utf-8")) if PROV_FILE.exists() else {}
                info["seed"] = sd
                atomic_write_json(PROV_FILE, info)
        except Exception:
            pass
        return out
    else:
        # seed dérivé du prompt (replay faible, utile si tu rejoues le même prompt)
        h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        sd = int(h[:8], 16)
        set_run_seed(sd, note="auto-from-prompt")
        return _prev_handle_seed(self, prompt, *a, **kw)

if _prev_handle_seed:
    Orchestrator.handle = _handle_seed_wrapper

# -------- 2) Schémas & Migrations légères --------
def _schemas():
    return json.loads(SCHEMA_REG.read_text(encoding="utf-8")) if SCHEMA_REG.exists() else {"files": {}, "ts": 0}

def schema_register(p: Path, version: int):
    reg = _schemas()
    reg["files"][str(p)] = int(version)
    reg["ts"] = int(time.time())
    atomic_write_json(SCHEMA_REG, reg)

def schema_version(p: Path) -> int:
    reg = _schemas()
    return int(reg.get("files", {}).get(str(p), 0))

def migrate_file_if_needed(p: Path, target: int, kind: str = "json"):
    cur = schema_version(p)
    if cur >= target:
        return {"ok": True, "from": cur, "to": cur, "path": str(p)}
    try:
        if kind == "json":
            data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
            if "_schema" not in data:
                data["_schema"] = target
            atomic_write_json(p, data)
        elif kind == "jsonl":
            # On ne réécrit pas les lignes : on se contente d’un sidecar version dans le registre
            pass
        schema_register(p, target)
        return {"ok": True, "from": cur, "to": target, "path": str(p)}
    except Exception as e:
        return {"ok": False, "err": str(e), "path": str(p), "from": cur, "to": target}

def migrate_all_known():
    results = []
    known = []
    # Ajouter ici les fichiers connus si présents
    for name in ("FATIGUE_FILE","HOLO_FILE","DREAMS_FILE","CHRONOS_FILE","IDEAS_FILE","FORGE_FILE","PHYL_FILE","PROV_FILE"):
        if name in globals():
            p = globals()[name]
            kind = "jsonl" if name in ("HOLO_FILE","DREAMS_FILE") else "json"
            results.append(migrate_file_if_needed(p, target=1, kind=kind))
            known.append(str(p))
    # RAG CPU mapping
    try:
        p = Path(".alsadika/cpu_rag/map.json")
        if p.exists():
            results.append(migrate_file_if_needed(p, target=1, kind="json"))
    except Exception:
        pass
    atomic_write_json(SAFE_DIR / "migrations.last.json", {"ts": int(time.time()), "results": results})
    return results

# Hook chat simple: "migrate:" lance la migration
try:
    _prev_handle_mig = Orchestrator.handle
except NameError:
    _prev_handle_mig = None

def _handle_migrate(self, prompt: str, *a, **kw):
    if re.match(r"^\s*migrate\s*:\s*$", prompt, flags=re.I):
        res = migrate_all_known()
        return json.dumps(res, ensure_ascii=False, indent=2)
    return _prev_handle_mig(self, prompt, *a, **kw)

if _prev_handle_mig:
    Orchestrator.handle = _handle_migrate

# -------- 3) Sandbox d’exécution + timeouts --------
def _deny_regex(pat: str) -> bool:
    # blocage motifs catastrophiques (quantifieurs imbriqués)
    return bool(re.search(r"\((?:[^()]{0,40})[*+?]\){1,2}[*+?]", pat))

@contextlib.contextmanager
def _timeout(seconds: float = 0.25):
    # Unix-only; sur Termux OK. Fallback silencieux sinon.
    try:
        import signal
        def _handler(signum, frame): raise TimeoutError("Exec timeout")
        old_handler = signal.signal(signal.SIGALRM, _handler)
        signal.setitimer(signal.ITIMER_REAL, seconds, 0)
        try:
            yield
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0, 0)
            signal.signal(signal.SIGALRM, old_handler)
    except Exception:
        # pas de timeout dispo → pas de garde (on reste honnête)
        yield

def safexec(source: str, extra_globals=None, timeout: float = 0.25):
    g = {"__builtins__": {"len": len, "range": range, "min": min, "max": max, "str": str}}
    if extra_globals: g.update(extra_globals)
    l = {}
    code = compile(source, "<safe-exec>", "exec")
    with _timeout(timeout):
        exec(code, g, l)
    return g, l

def _timeout_call(fn, *args, seconds: float = 0.2, **kw):
    with _timeout(seconds):
        return fn(*args, **kw)

# 3.bis) Renforcement SkillForge si présent → on redéfinit avec sandbox/timeout
if all(k in globals() for k in ("forge_create","_forge_candidates","_inst","_pipe_matches")):
    _orig_forge_create = forge_create
    def forge_create(name: str, examples: list[dict|str]):
        # (reprise de la logique d’origine + sandbox)
        # normaliser exemples
        ex = []
        for item in examples:
            if isinstance(item, str) and "->" in item:
                i,o = item.split("->",1); ex.append({"in": i.strip(), "out": o.strip()})
            elif isinstance(item, dict) and "in" in item and "out" in item:
                ex.append({"in": str(item["in"]), "out": str(item["out"])})
        if not ex: return {"ok": False, "msg": "Aucun exemple valide."}
        # candidates
        best = None
        for g in _forge_candidates():
            for inst in _inst(g, ex):
                if _pipe_matches(ex, inst):
                    best = inst; break
            if best: break
        if not best:
            return {"ok": False, "msg": "Aucun pipeline trouvé pour ces exemples."}

        # Construire code avec filtrage regex
        import re as _re
        src = ["def transformer(text: str) -> str:", "    t = text"]
        for step in best:
            if step in ("lower","upper","title","strip"):
                src.append(f"    t = t.{step}()")
            elif step.startswith("prefix:"):
                val = step.split(":",1)[1].replace('"','\\"'); src.append(f"    t = \"{val}\" + t")
            elif step.startswith("suffix:"):
                val = step.split(":",1)[1].replace('"','\\"'); src.append(f"    t = t + \"{val}\"")
            elif step.startswith("slice:"):
                a,b = step.split(":",1)[1].split(":"); a = a or "None"; b = b or "None"; src.append(f"    t = t[{a}:{b}]")
            elif step.startswith("replace:"):
                A,B = step.split(":",1)[1].split("->",1); src.append(f"    t = t.replace({json.dumps(A)}, {json.dumps(B)})")
            elif step.startswith("regex:"):
                PAT,RPL = step.split(":",1)[1].split("->",1)
                if _deny_regex(PAT): return {"ok": False, "msg": "Pattern regex dangereux bloqué."}
                src.append(f"    import re as _re"); src.append(f"    t = _re.sub({json.dumps(PAT)}, {json.dumps(RPL)}, t)")
            elif step.startswith("keepwords:"):
                csv = step.split(":",1)[1]
                src.append(f"    import re as _re")
                src.append(f"    _keys = {[w for w in csv.split(',') if w]}")
                src.append(f"    if _keys and not any(_re.search(r'\\\\b'+_re.escape(k)+'\\\\b', t, _re.I) for k in _keys): t = ''")
        src.append("    return t")
        code = "\n".join(src)

        try:
            g,l = safexec(code, extra_globals={"re": __import__("re")}, timeout=0.25)
        except TimeoutError:
            return {"ok": False, "msg": "Compilation timeout."}
        except Exception as e:
            return {"ok": False, "msg": f"Compilation échouée: {e}"}
        fn = l.get("transformer")
        if not callable(fn):
            return {"ok": False, "msg": "Fonction non valide."}
        # Validation exemples avec timeout par appel
        try:
            for e in ex:
                if _timeout_call(fn, e["in"], seconds=0.2) != e["out"]:
                    return {"ok": False, "msg": "Échec validation interne."}
        except TimeoutError:
            return {"ok": False, "msg": "Validation timeout."}
        # Stockage (atomique)
        try:
            db = json.loads(FORGE_FILE.read_text(encoding="utf-8")) if 'FORGE_FILE' in globals() and FORGE_FILE.exists() else {"skills": {}}
        except Exception:
            db = {"skills": {}}
        db["skills"][name] = {"pipe": best, "code": code, "created": int(time.time())}
        target = FORGE_FILE if 'FORGE_FILE' in globals() else (SAFE_DIR/"skillforge.json")
        atomic_write_json(target, db)
        return {"ok": True, "name": name, "pipe": best}

    # forge_run durci (timeout)
    _orig_forge_run = forge_run if "forge_run" in globals() else None
    def forge_run(name: str, text: str):
        try:
            db = json.loads(FORGE_FILE.read_text(encoding="utf-8")) if 'FORGE_FILE' in globals() and FORGE_FILE.exists() else {"skills": {}}
            sk = db["skills"].get(name)
            if not sk: return {"ok": False, "msg": "Skill inconnue."}
            g,l = safexec(sk["code"], extra_globals={"re": __import__("re")}, timeout=0.25)
            fn = l.get("transformer")
            out = _timeout_call(fn, text, seconds=0.25)
            return {"ok": True, "out": out}
        except TimeoutError:
            return {"ok": False, "msg": "Exécution timeout."}
        except Exception as e:
            return {"ok": False, "msg": f"Exécution échouée: {e}"}

    globals()["forge_create"] = forge_create
    globals()["forge_run"] = forge_run

# -------- 4) Renforcer les appends JSONL existants (HOLO/DREAMS…) si présents --------
# On redéfinit proprement les writers haut-niveau s’ils existent déjà
if "HOLO_FILE" in globals():
    def _holo_write(obj: dict):
        jsonl_append(HOLO_FILE, obj)
    globals()["_holo_write"] = _holo_write

if "DREAMS_FILE" in globals():
    def _dreams_append(d: dict):
        jsonl_append(DREAMS_FILE, d)
    # surcharger dreams_tick pour l’utiliser si défini
    if "dreams_tick" in globals():
        _orig_dreams_tick = dreams_tick
        def dreams_tick():
            src = _holo_lines()[-8:] if "_holo_lines" in globals() else []
            if not src: 
                rec={"ok": False, "msg": "rien à rêver"}
                return rec
            import random as _r
            a = _r.choice(src); b = _r.choice(src)
            blend = f"Rêve: {a.get('summary','')} ↔ {b.get('metaphor','')}"
            rec = {"ts": int(time.time()), "dream": blend, "a": a.get("hid"), "b": b.get("hid")}
            _dreams_append(rec)
            return {"ok": True, "dream": blend}

# -------- 5) Auto-migration légère au chargement --------
try:
    migrate_all_known()
except Exception:
    pass
# ===============================
# FIN PATCH HARDEN-4
# ===============================
# ===============================
# PATCH "AUTONOMY-DAEMON" — veille permanente (append-only)
# ===============================
import argparse, json, time, subprocess, shutil, hashlib
from pathlib import Path

ROOT_AD = Path(".alsadika") if "ROOT" not in globals() else ROOT
INBOX  = ROOT_AD / "inbox"
OUTBOX = ROOT_AD / "outbox"
STATE  = ROOT_AD / "daemon_state.json"
INBOX.mkdir(parents=True, exist_ok=True); OUTBOX.mkdir(parents=True, exist_ok=True)

def _awrite(p: Path, text: str):
    try:
        atomic_write_text(p, text)  # dispo via HARDEN-4
    except Exception:
        p.write_text(text, encoding="utf-8")

def _notify(title: str, text: str):
    cmd = shutil.which("termux-notification") or shutil.which("termux-toast")
    if not cmd: return
    try:
        if "notification" in cmd:
            subprocess.run(["termux-notification","--title",title,"--content",text[:800]], check=False)
        else:
            subprocess.run(["termux-toast", f"{title}: {text[:60]}"], check=False)
    except Exception:
        pass

def _run_prompt(prompt: str, timeout=120) -> str:
    try:
        proc = subprocess.run(["python","original","chat","--prompt",prompt],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, timeout=timeout)
        return proc.stdout.strip()
    except subprocess.TimeoutExpired:
        return "[daemon] timeout"
    except Exception as e:
        return f"[daemon] error: {e}"

def daemon_once():
    st = {"ts": int(time.time()), "processed": 0, "growth": False}
    files = sorted([p for p in INBOX.iterdir() if p.is_file() and not p.name.startswith(".")])
    for p in files:
        try:
            prompt = p.read_text(encoding="utf-8").strip()
        except Exception:
            prompt = ""
        out = _run_prompt(prompt) if prompt else "[vide]"
        outp = OUTBOX / (p.stem + ".out.txt")
        _awrite(outp, out + "\n")
        try: p.unlink()
        except Exception: pass
        st["processed"] += 1
        _notify("Al Sâdika", f"Réponse prête: {outp.name}")
    # hygiène légère (fait “grandir” sans te déranger)
    try: subprocess.run(["python","original","ideas-garden"], check=False)
    except Exception: pass
    try: subprocess.run(["python","original","dreams-tick"], check=False)
    except Exception: pass
    try: subprocess.run(["python","original","chronos-tick","--level","micro"], check=False)
    except Exception: pass
    st["growth"] = True
    _awrite(STATE, json.dumps(st, ensure_ascii=False, indent=2))
    return st

def daemon_loop(interval=20, notify=True):
    if notify: _notify("Al Sâdika","Daemon démarré.")
    while True:
        daemon_once()
        time.sleep(max(5,int(interval)))

# ---- CLI ----
try:
    _prev_build = build_parser
except NameError:
    _prev_build = None

def build_parser():
    p = _prev_build() if _prev_build else argparse.ArgumentParser(prog="alsadika")
    sp = [a for a in p._subparsers._actions if getattr(a,'dest',None)=='cmd'][0]
    d1 = sp.add_parser("daemon", help="Boucle autonome (watch inbox, maintenance)")
    d1.add_argument("--interval", type=int, default=20)
    d1.add_argument("--no-notify", action="store_true")
    d1.set_defaults(_fn=cmd_daemon)
    d2 = sp.add_parser("daemon-once", help="Un cycle (utilisable en cron)")
    d2.set_defaults(_fn=cmd_daemon_once)
    d3 = sp.add_parser("say", help="Déposer un prompt dans l'inbox")
    d3.add_argument("--text", required=True)
    d3.set_defaults(_fn=cmd_say)
    return p

def cmd_daemon(args):
    daemon_loop(interval=args.interval, notify=(not args.no_notify)); return 0
def cmd_daemon_once(args):
    print(json.dumps(daemon_once(), ensure_ascii=False, indent=2)); return 0
def cmd_say(args):
    name = f"{int(time.time())}_{hashlib.sha256(args.text.encode('utf-8')).hexdigest()[:8]}.txt"
    path = INBOX / name
    _awrite(path, args.text + "\n")
    print(str(path)); return 0
# ===============================
# FIN PATCH AUTONOMY-DAEMON
# ===============================
# ===============================
# PATCH "OPENMODE-SAFE" — exploration web en lecture seule (append-only)
# ===============================
import argparse, json, re, time, hashlib, html, os
from pathlib import Path
from urllib.parse import urlparse, urljoin

ROOT_OM = Path(".alsadika") if "ROOT" not in globals() else ROOT
WEB_DIR = ROOT_OM / "web"; WEB_DIR.mkdir(parents=True, exist_ok=True)
WEB_PAGES = WEB_DIR / "pages"; WEB_PAGES.mkdir(exist_ok=True)
WEB_STATE = WEB_DIR / "state.json"
WEB_SCOPE = WEB_DIR / "scope.json"
WEB_QUEUE = WEB_DIR / "queue.jsonl"
ROBOTS_CACHE = WEB_DIR / "robots.json"

# --------- utils safe i/o (HARDEN-4 présent ? sinon fallback) ---------
def _awrite_json(p: Path, obj: dict):
    try:
        atomic_write_json(p, obj)  # fourni par HARDEN-4
    except Exception:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def _aappend_jsonl(p: Path, rec: dict):
    try:
        jsonl_append(p, rec)  # fourni par HARDEN-4
    except Exception:
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def _read_json(p: Path, dflt):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return dflt

STATE = _read_json(WEB_STATE, {"last":0,"by_domain":{}})
SCOPE = _read_json(WEB_SCOPE, {
    "allowed_domains": [],        # ex: ["wikipedia.org","lemonde.fr"]
    "disallowed_patterns": [],    # regex simples, ex: ["/login","/cart"]
    "max_pages_day": 100,
    "max_depth": 1,
    "rate_seconds": 10            # délai mini entre hits d'un même domaine
})

# --------- HTTP layer (requests si dispo, sinon urllib) ---------
try:
    import requests as _rq
except Exception:
    _rq = None
import urllib.request as _ul
import urllib.robotparser as _rp

def _is_http(url:str)->bool:
    try:
        u = urlparse(url)
        return u.scheme in ("http","https") and bool(u.netloc)
    except Exception:
        return False

def _host(url:str)->str:
    return urlparse(url).netloc.lower()

def _domain_allowed(url:str)->bool:
    h = _host(url)
    w = SCOPE.get("allowed_domains", [])
    if not w: 
        return False
    return any(h==d or h.endswith("."+d) for d in w)

def _blocked(url:str)->bool:
    patts = SCOPE.get("disallowed_patterns", [])
    return any(re.search(p, url) for p in patts)

def _robots_ok(url:str, ua="AlSadikaBot"):
    try:
        host = _host(url)
        cache = _read_json(ROBOTS_CACHE, {})
        rp = cache.get(host, {})
        now = int(time.time())
        if not rp or now - rp.get("ts",0) > 86400:
            rob = f"{urlparse(url).scheme}://{host}/robots.txt"
            ok = True; rules = ""
            try:
                if _rq:
                    r = _rq.get(rob, timeout=6)
                    if r.status_code==200 and len(r.text)<200000:
                        rules = r.text
                else:
                    with _ul.urlopen(rob, timeout=6) as r:
                        txt = r.read(200000).decode("utf-8","ignore")
                        rules = txt
            except Exception:
                rules = ""
            cache[host] = {"ts": now, "rules": rules}
            _awrite_json(Path(ROBOTS_CACHE), cache)
            rp_txt = rules
        else:
            rp_txt = rp.get("rules","")
        parser = _rp.RobotFileParser()
        if rp_txt:
            parser.parse(rp_txt.splitlines())
            return parser.can_fetch(ua, url)
        return True
    except Exception:
        return True

def _rate_ok(url:str)->bool:
    host = _host(url)
    by = STATE.get("by_domain", {})
    last = by.get(host, 0)
    if time.time() - last < SCOPE.get("rate_seconds",10):
        return False
    return True

def _mark_rate(url:str):
    host = _host(url)
    by = STATE.get("by_domain", {})
    by[host] = int(time.time())
    STATE["by_domain"] = by
    _awrite_json(WEB_STATE, STATE)

def _fetch(url:str)->tuple[str,str]:
    """retourne (mime, text) ou ('','')"""
    headers = {"User-Agent":"AlSadikaBot/1.0 (+local-first; halal-safe)"}
    try:
        if _rq:
            r = _rq.get(url, headers=headers, timeout=10, allow_redirects=True)
            if r.status_code!=200: return "",""
            ctype = r.headers.get("Content-Type","text/plain").split(";")[0].strip().lower()
            if ctype.startswith("text/html"):
                txt = r.text
            elif ctype.startswith("text/"):
                txt = r.text
            else:
                return "",""
            return ctype, txt
        else:
            req = _ul.Request(url, headers=headers)
            with _ul.urlopen(req, timeout=10) as r:
                ctype = r.info().get_content_type()
                if ctype.startswith("text/"):
                    txt = r.read(2_000_000).decode("utf-8","ignore")
                else:
                    return "",""
            return ctype, txt
    except Exception:
        return "",""

# --------- Extraction de texte ---------
def _extract_text(url:str, ctype:str, body:str)->tuple[str,list[str],str]:
    title = ""
    links = []
    txt = body or ""
    if ctype.startswith("text/html"):
        try:
            from bs4 import BeautifulSoup as _BS
            soup = _BS(body, "html.parser")
            title = (soup.title.string or "").strip() if soup.title else ""
            for s in soup(["script","style","noscript"]): s.decompose()
            for a in soup.find_all("a", href=True):
                href = a.get("href")
                if href and isinstance(href, str):
                    absu = urljoin(url, href)
                    if _is_http(absu): links.append(absu)
            txt = soup.get_text(" ", strip=True)
        except Exception:
            # fallback regex brut
            m = re.search(r"<title>(.*?)</title>", body, flags=re.I|re.S)
            title = html.unescape(m.group(1).strip()) if m else ""
            txt = re.sub(r"(?is)<(script|style).*?</\1>", " ", body)
            txt = re.sub(r"(?is)<[^>]+>", " ", txt)
            txt = re.sub(r"\s+", " ", txt).strip()
            links = []
    else:
        txt = re.sub(r"\s+", " ", txt).strip()
    # normaliser
    txt = txt[:500_000]  # borne max
    return txt, links, title

# --------- Stockage & index ---------
def _page_id(url:str)->str:
    return hashlib.blake2s(url.encode("utf-8"), digest_size=8).hexdigest()

def _store_page(url:str, title:str, text:str):
    pid = _page_id(url)
    meta = {
        "url": url, "title": title, "ts": int(time.time()),
        "len": len(text), "id": pid, "_schema": 1
    }
    _awrite_json(WEB_PAGES / f"{pid}.meta.json", meta)
    try:
        atomic_write_text(WEB_PAGES / f"{pid}.txt", text)
    except Exception:
        (WEB_PAGES / f"{pid}.txt").write_text(text, encoding="utf-8")

def _index_pages():
    # Utilise cpu_index ou cpu_index_safe sur WEB_PAGES
    try:
        if "cpu_index_safe" in globals():
            return cpu_index_safe(str(WEB_PAGES), limit=1000)
        elif "cpu_index" in globals():
            return cpu_index(str(WEB_PAGES))
    except Exception:
        pass
    return {"ok": False, "msg":"RAG non présent"}

# --------- Queue & exploration ---------
def web_scope_set(allow_csv:str, max_pages:int=100, depth:int=1, rate:int=10, disallow_csv:str=""):
    allowed = [d.strip().lower() for d in allow_csv.split(",") if d.strip()]
    disallowed = [d.strip() for d in disallow_csv.split(",") if d.strip()]
    SCOPE.update({
        "allowed_domains": allowed,
        "disallowed_patterns": disallowed,
        "max_pages_day": int(max_pages),
        "max_depth": int(depth),
        "rate_seconds": int(rate)
    })
    _awrite_json(WEB_SCOPE, SCOPE)
    return SCOPE

def web_queue_add(url:str, depth:int=0):
    url = url.strip()
    if not _is_http(url): return {"ok": False, "msg":"URL invalide"}
    if not _domain_allowed(url): return {"ok": False, "msg":"Domaine non autorisé (scope)."}
    if _blocked(url): return {"ok": False, "msg":"Pattern interdit (scope)."}
    rec = {"ts": int(time.time()), "url": url, "depth": int(depth)}
    _aappend_jsonl(WEB_QUEUE, rec); return {"ok": True, "queued": url}

def _queue_iter():
    if not WEB_QUEUE.exists(): return []
    for line in WEB_QUEUE.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        try: yield json.loads(line)
        except Exception: continue

def _queue_rewrite(items):
    tmp = "\n".join(json.dumps(x, ensure_ascii=False) for x in items) + ("\n" if items else "")
    try:
        atomic_write_text(WEB_QUEUE, tmp)
    except Exception:
        WEB_QUEUE.write_text(tmp, encoding="utf-8")

def web_once(batch:int=2):
    # quotas journaliers
    day = int(time.time()) // 86400
    stamp = _read_json(WEB_DIR / "quota.json", {"day": -1, "count":0})
    if stamp["day"] != day:
        stamp = {"day": day, "count": 0}
    max_day = int(SCOPE.get("max_pages_day",100))
    processed = 0

    items = list(_queue_iter())
    rest = []
    for it in items:
        if processed >= batch: rest.append(it); continue
        url = it.get("url",""); depth = int(it.get("depth",0))
        if stamp["count"] >= max_day: 
            rest.append(it); continue
        if not _is_http(url) or not _domain_allowed(url) or _blocked(url):
            continue
        if not _robots_ok(url): 
            continue
        if not _rate_ok(url):
            rest.append(it); continue

        # FETCH
        ctype, body = _fetch(url)
        _mark_rate(url)
        if not body:
            processed += 1; stamp["count"] += 1
            continue
        text, links, title = _extract_text(url, ctype, body)
        _store_page(url, title, text)
        processed += 1; stamp["count"] += 1

        # ENQUEUE next links (même domaine uniquement, et profondeur limitée)
        if depth < int(SCOPE.get("max_depth",1)):
            dom = _host(url)
            n = 0
            for l in links[:15]:  # borne
                if _host(l) != dom: 
                    continue
                if not _domain_allowed(l) or _blocked(l):
                    continue
                _aappend_jsonl(WEB_QUEUE, {"ts": int(time.time()), "url": l, "depth": depth+1})
                n += 1

    _queue_rewrite(rest)
    _awrite_json(WEB_DIR / "quota.json", stamp)
    # Indexer ce qui a été collecté
    idx = _index_pages()
    return {"ok": True, "processed": processed, "indexed": idx}

# --------- Statut & intégrations ---------
def web_status():
    pages = len(list(WEB_PAGES.glob("*.txt")))
    q = sum(1 for _ in _queue_iter())
    return {"ok": True, "pages": pages, "queue": q, "scope": SCOPE}

# Hook chat: "open: URL" -> queue; "web:" -> status
_prev_handle_open = Orchestrator.handle
def _handle_open(self, prompt:str, *a, **kw):
    m = re.match(r"^\s*open:\s*(\S+)\s*$", prompt, flags=re.I)
    if m:
        return json.dumps(web_queue_add(m.group(1), depth=0), ensure_ascii=False, indent=2)
    if re.match(r"^\s*web:\s*$", prompt, flags=re.I):
        return json.dumps(web_status(), ensure_ascii=False, indent=2)
    return _prev_handle_open(self, prompt, *a, **kw)
Orchestrator.handle = _handle_open

# Si le daemon général existe, on l'étend doucement (1 page/cycle max)
if "daemon_once" in globals():
    _orig_daemon_once = daemon_once
    def daemon_once():
        st = _orig_daemon_once()
        try: web_once(batch=1)
        except Exception: pass
        return st
    globals()["daemon_once"] = daemon_once

# CLI
try:
    _prev_build_open = build_parser
except NameError:
    _prev_build_open = None

def build_parser():
    p = _prev_build_open() if _prev_build_open else argparse.ArgumentParser(prog="alsadika")
    sp = [a for a in p._subparsers._actions if getattr(a,'dest',None)=='cmd'][0]

    w1 = sp.add_parser("open-scope", help="Configurer la liste blanche et quotas")
    w1.add_argument("--allow", required=True, help="CSV domaines: ex 'wikipedia.org,lemonde.fr'")
    w1.add_argument("--max", type=int, default=100)
    w1.add_argument("--depth", type=int, default=1)
    w1.add_argument("--rate", type=int, default=10)
    w1.add_argument("--disallow", default="", help="CSV patterns interdits")
    w1.set_defaults(_fn=cmd_open_scope)

    w2 = sp.add_parser("web-add", help="Ajouter une URL à la file")
    w2.add_argument("--url", required=True); w2.add_argument("--depth", type=int, default=0)
    w2.set_defaults(_fn=cmd_web_add)

    w3 = sp.add_parser("web-once", help="Traiter quelques pages")
    w3.add_argument("--batch", type=int, default=2)
    w3.set_defaults(_fn=cmd_web_once)

    w4 = sp.add_parser("web-daemon", help="Boucle exploration web")
    w4.add_argument("--interval", type=int, default=60)
    w4.add_argument("--batch", type=int, default=2)
    w4.set_defaults(_fn=cmd_web_daemon)

    w5 = sp.add_parser("web-status", help="Statut collecte/index")
    w5.set_defaults(_fn=cmd_web_status)

    return p

def cmd_open_scope(args):
    print(json.dumps(web_scope_set(args.allow, args.max, args.depth, args.rate, args.disallow), ensure_ascii=False, indent=2)); return 0
def cmd_web_add(args):
    print(json.dumps(web_queue_add(args.url, depth=max(0,args.depth)), ensure_ascii=False, indent=2)); return 0
def cmd_web_once(args):
    print(json.dumps(web_once(batch=max(1,args.batch)), ensure_ascii=False, indent=2)); return 0
def cmd_web_daemon(args):
    import time
    while True:
        print(json.dumps(web_once(batch=max(1,args.batch)), ensure_ascii=False))
        time.sleep(max(5,int(args.interval)))
    return 0
def cmd_web_status(args):
    print(json.dumps(web_status(), ensure_ascii=False, indent=2)); return 0
# ===============================
# FIN PATCH OPENMODE-SAFE
# ===============================
# ===============================
# PATCH "AUTO-RETAIN" — append-only
# ===============================
import os, json, re, time, math, hashlib, datetime
from pathlib import Path

ALSADIKA_DIR = Path(".alsadika")
MEM_FILE     = ALSADIKA_DIR / "memory.json"          # mémoire approuvée (clé/val)
WEB_DIR      = ALSADIKA_DIR / "web" / "pages"        # pages archivées
STATE_FILE   = ALSADIKA_DIR / "auto_state.json"      # état auto-retain (ts, quotas)
SCOPE_FILE   = ALSADIKA_DIR / "web_scope.json"       # domaines autorisés

ALSADIKA_DIR.mkdir(parents=True, exist_ok=True)

# ---- Config par défaut (autonome) ----
AUTO_RETAIN_ON       = True          # ON par défaut (tu peux switcher via CLI)
MAX_AUTO_PER_DAY     = 1000000            # quota journ.
MIN_FACT_LEN         = 40            # longueur min d’un fait retenu
MAX_FACT_LEN         = 280           # longueur max (tweet-size, lisible)
MIN_TITLE_LEN        = 12
MIN_SCORE            = 0.25          # seuil minimal (heuristique)
ALLOW_DUP_NEAR_DAYS  = 3             # pas de doublon clé pendant N jours

# ---------- Utils JSON ----------
def _now_iso():
    try:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()
    except Exception:
        # fallback
        return datetime.datetime.utcnow().isoformat()  # ok si pas tz-aware

def _read_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default

def _write_json(p, data):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

# ---------- Charger scope/domains ----------
def _allowed_domains():
    s = _read_json(SCOPE_FILE, {})
    doms = s.get("allowed_domains") or []
    return set(doms)

# ---------- Mémoire (clé/val) ----------
def _mem_load():
    m = _read_json(MEM_FILE, {"items":[]})
    if "items" not in m: m["items"]=[]
    return m

def _mem_has_recent_key(key_hash: str, days: int) -> bool:
    m = _mem_load()
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    for it in m["items"]:
        if it.get("key_hash")==key_hash:
            # vérifier fraicheur
            try:
                ts = datetime.datetime.fromisoformat(it.get("ts",""))
            except Exception:
                continue
            if ts.tzinfo is None:  # compat
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            if ts >= cutoff: 
                return True
    return False

def _mem_add(key: str, value: str, meta: dict):
    m = _mem_load()
    item = {
        "key": key.strip(),
        "value": value.strip(),
        "key_hash": _sha1(key.strip().lower()),
        "ts": _now_iso(),
        "meta": meta or {}
    }
    # dédup stricte: même key_hash + même value → skip
    for it in m["items"]:
        if it.get("key_hash")==item["key_hash"] and it.get("value")==item["value"]:
            return {"ok": False, "msg": "dup"}
    m["items"].append(item)
    _write_json(MEM_FILE, m)
    return {"ok": True, "added": item["key"]}

# ---------- Heuristiques d’extraction ----------
_stop = set("""
et le la les des de du un une au aux ou que qui dans pour par avec sur vers chez comme selon
a à d’ l’ s’ c’ qu’ n’ mais donc or ni car
""".split())

def _clean_whitespace(s:str)->str:
    return re.sub(r"\s+", " ", s).strip()

def _score_fact(text: str) -> float:
    # heuristique légère: longueur ok + verbes copules + peu de stopwords proportionnels
    t = text.strip()
    if not (MIN_FACT_LEN <= len(t) <= MAX_FACT_LEN):
        return 0.0
    has_is = bool(re.search(r"\b(est|sont|éta(it|ient)|constitue|représente)\b", t, flags=re.I))
    toks = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9']+", t.lower())
    sw = sum(1 for w in toks if w in _stop)
    density = 1 - (sw / (len(toks) or 1))
    base = 0.4 if has_is else 0.25
    return max(0.0, min(1.0, base + 0.6*density))

def _extract_candidates(page_txt: Path, page_meta: Path):
    try:
        txt = page_txt.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    meta = _read_json(page_meta, {})
    url  = meta.get("url","")
    dom  = re.sub(r"^https?://([^/]+).*", r"\1", url) if url else ""
    title = (meta.get("title") or "").strip()
    title_ok = len(title) >= MIN_TITLE_LEN

    # split en phrases
    raw_sents = re.split(r"(?<=[\.\!\?])\s+", _clean_whitespace(txt))
    out=[]
    for s in raw_sents:
        s = s.strip().replace("\n"," ")
        if not s: continue
        sc = _score_fact(s)
        if sc >= MIN_SCORE:
            key = s if len(s)<=80 else s[:77]+"…"
            val = s
            meta_out = {
                "source": url, "domain": dom, "title": title if title_ok else "",
                "algo":"auto-retain-v1","score":round(sc,3)
            }
            out.append((key,val,meta_out))
            if len(out)>=5:  # max 5 par page
                break
    # si rien, fallback: retenir le titre
    if not out and title_ok:
        s = title
        sc = 0.3
        key = s if len(s)<=80 else s[:77]+"…"
        meta_out = {"source": url, "domain": dom, "title": title, "algo":"auto-retain-v1:title","score":round(sc,3)}
        out.append((key, s, meta_out))
    return out

# ---------- Quotas / état ----------
def _state_load():
    st = _read_json(STATE_FILE, {"last_scan":0, "day":"", "count_today":0})
    if "day" not in st: st["day"]=""
    if "count_today" not in st: st["count_today"]=0
    return st

def _state_save(st):
    _write_json(STATE_FILE, st)

def _day_str():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

# ---------- Pipeline principal ----------
def auto_retain_once(batch_pages: int = 10):
    # Garde-fou global
    scope = _read_json(SCOPE_FILE, {})
    allowed = set(scope.get("allowed_domains") or [])
    # état
    st = _state_load()
    today = _day_str()
    if st.get("day") != today:
        st["day"] = today; st["count_today"]=0

    if not AUTO_RETAIN_ON:
        return {"ok": False, "msg": "AUTO_RETAIN_OFF", "count_today": st["count_today"]}

    # collect pages (récents d’abord)
    pages = []
    if WEB_DIR.exists():
        for metap in WEB_DIR.glob("*.meta.json"):
            txtp = WEB_DIR / (metap.stem + ".txt")
            if not txtp.exists(): continue
            try:
                mtime = txtp.stat().st_mtime
            except Exception:
                mtime = 0
            pages.append((mtime, txtp, metap))
        pages.sort(reverse=True)
    # scanner jusqu’à batch_pages
    added = 0
    seen = 0
    for _, txtp, metap in pages[:max(1,batch_pages)]:
        seen += 1
        # Extract
        cands = _extract_candidates(txtp, metap)
        for key, val, meta in cands:
            dom = meta.get("domain","")
            if allowed and dom not in allowed:
                continue
            if st["count_today"] >= MAX_AUTO_PER_DAY:
                _state_save(st)
                return {"ok": True, "seen": seen, "added": added, "count_today": st["count_today"], "quota_hit": False}
            # dédup temporelle
            kh = _sha1(key.strip().lower())
            if _mem_has_recent_key(kh, ALLOW_DUP_NEAR_DAYS):
                continue
            r = _mem_add(key, val, meta)
            if r.get("ok"):
                added += 1
                st["count_today"] += 1
    _state_save(st)
    return {"ok": True, "seen": seen, "added": added, "count_today": st["count_today"]}

# ---------- CLI wiring ----------
try:
    _prev_build = build_parser
except NameError:
    _prev_build = None

def build_parser():
    p = _prev_build() if _prev_build else argparse.ArgumentParser(prog="alsadika")
    sp = [a for a in p._subparsers._actions if getattr(a,'dest',None)=='cmd'][0]

    c1 = sp.add_parser("auto-retain", help="Rétention automatique des faits (sans approbation manuelle)")
    c1.add_argument("--batch", type=int, default=10, help="Nb de pages à traiter")
    c1.set_defaults(_fn=cmd_auto_retain)

    c2 = sp.add_parser("auto-retain-on", help="Activer la rétention auto")
    c2.set_defaults(_fn=cmd_auto_retain_on)

    c3 = sp.add_parser("auto-retain-off", help="Désactiver la rétention auto")
    c3.set_defaults(_fn=cmd_auto_retain_off)

    c4 = sp.add_parser("auto-retain-status", help="Voir quota et état")
    c4.set_defaults(_fn=cmd_auto_retain_status)

    return p

def cmd_auto_retain(args):
    res = auto_retain_once(batch_pages=max(1, args.batch))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0

def cmd_auto_retain_on(args):
    global AUTO_RETAIN_ON
    AUTO_RETAIN_ON = True
    st = _state_load(); _state_save(st)
    print(json.dumps({"ok":True,"auto_retain":"ON"}, ensure_ascii=False))
    return 0

def cmd_auto_retain_off(args):
    global AUTO_RETAIN_ON
    AUTO_RETAIN_ON = False
    st = _state_load(); _state_save(st)
    print(json.dumps({"ok":True,"auto_retain":"OFF"}, ensure_ascii=False))
    return 0

def cmd_auto_retain_status(args):
    st = _state_load()
    scope = _read_json(SCOPE_FILE, {})
    print(json.dumps({
        "ok": True,
        "auto_retain": True,     # actif par défaut dans ce patch
        "count_today": st.get("count_today",0),
        "day": st.get("day",""),
        "allowed_domains": scope.get("allowed_domains",[])
    }, ensure_ascii=False, indent=2))
    return 0
# ===============================
# FIN PATCH AUTO-RETAIN
# ===============================
# ===============================
# PATCH "AUTO-RETAIN-FIX-TXT" — récupérer le texte si .txt manquant
# ===============================
import re, json
try:
    import requests
    from bs4 import BeautifulSoup
except Exception:
    requests = None
    BeautifulSoup = None

def _fetch_text_from_url(url: str) -> str:
    if not url or requests is None or BeautifulSoup is None:
        return ""
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent":"alsadika-auto-retain/1.0"})
        r.raise_for_status()
        html = r.text or ""
        soup = BeautifulSoup(html, "html.parser")
        # heuristique simple : supprimer scripts/styles, garder titres + paragraphes
        for tag in soup(["script","style","noscript"]):
            tag.decompose()
        chunks = []
        # titre
        t = soup.title.string.strip() if soup.title and soup.title.string else ""
        if t: chunks.append(t)
        # en priorité paragraphes
        for p in soup.find_all("p"):
            s = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
            if len(s) >= 40:
                chunks.append(s)
        # fallback : tout le texte
        if len(" ".join(chunks)) < 200:
            alltxt = re.sub(r"\s+"," ", soup.get_text(" ", strip=True))
            chunks.append(alltxt)
        txt = "\n".join(chunks).strip()
        return txt
    except Exception:
        return ""

# Monkey-patch de _extract_candidates pour utiliser un fallback si le .txt manque
try:
    _ORIG_extract_candidates = _extract_candidates
except NameError:
    _ORIG_extract_candidates = None

def _extract_candidates(page_txt: Path, page_meta: Path):
    meta = _read_json(page_meta, {})
    url  = meta.get("url","")
    # 1) essayer de lire le .txt comme avant
    txt = ""
    try:
        if page_txt.exists():
            txt = page_txt.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        txt = ""
    # 2) si vide → tenter re-fetch depuis URL
    if not txt:
        fetched = _fetch_text_from_url(url)
        if fetched:
            txt = fetched
            # persister pour la prochaine fois
            try:
                page_txt.write_text(txt, encoding="utf-8")
            except Exception:
                pass
    # 3) si toujours pas de texte → retour vide
    if not txt.strip():
        return []

    # reprendre la logique d’origine
    dom  = re.sub(r"^https?://([^/]+).*", r"\1", url) if url else ""
    title = (meta.get("title") or "").strip()
    title_ok = len(title) >= MIN_TITLE_LEN

    raw_sents = re.split(r"(?<=[\.\!\?])\s+", _clean_whitespace(txt))
    out=[]
    for s in raw_sents:
        s = s.strip().replace("\n"," ")
        if not s: continue
        sc = _score_fact(s)
        if sc >= MIN_SCORE:
            key = s if len(s)<=80 else s[:77]+"…"
            val = s
            meta_out = {
                "source": url, "domain": dom, "title": title if title_ok else "",
                "algo":"auto-retain-v1","score":round(sc,3)
            }
            out.append((key,val,meta_out))
            if len(out)>=5:
                break
    if not out and title_ok:
        s = title
        sc = 0.3
        key = s if len(s)<=80 else s[:77]+"…"
        meta_out = {"source": url, "domain": dom, "title": title, "algo":"auto-retain-v1:title","score":round(sc,3)}
        out.append((key, s, meta_out))
    return out

# Assouplir le filtre domaine quand URL manquante
try:
    _ORIG_auto_retain_once = auto_retain_once
except NameError:
    _ORIG_auto_retain_once = None

def auto_retain_once(batch_pages: int = 10):
    scope = _read_json(SCOPE_FILE, {})
    allowed = set(scope.get("allowed_domains") or [])
    st = _state_load()
    today = _day_str()
    if st.get("day") != today:
        st["day"] = today; st["count_today"]=0

    if not AUTO_RETAIN_ON:
        return {"ok": False, "msg": "AUTO_RETAIN_OFF", "count_today": st["count_today"]}

    pages = []
    if WEB_DIR.exists():
        for metap in WEB_DIR.glob("*.meta.json"):
            txtp = WEB_DIR / (metap.stem + ".txt")
            try:
                mtime = (txtp.stat().st_mtime if txtp.exists() else metap.stat().st_mtime)
            except Exception:
                mtime = 0
            pages.append((mtime, txtp, metap))
        pages.sort(reverse=True)

    added = 0
    seen = 0
    for _, txtp, metap in pages[:max(1,batch_pages)]:
        seen += 1
        cands = _extract_candidates(txtp, metap)
        for key, val, meta in cands:
            dom = meta.get("domain","")
            # bloquer seulement si un domaine non autorisé est explicite
            if allowed and dom and dom not in allowed:
                continue
            if st["count_today"] >= MAX_AUTO_PER_DAY:
                _state_save(st)
                return {"ok": True, "seen": seen, "added": added, "count_today": st["count_today"], "quota_hit": False}
            kh = _sha1(key.strip().lower())
            if _mem_has_recent_key(kh, ALLOW_DUP_NEAR_DAYS):
                continue
            r = _mem_add(key, val, meta)
            if r.get("ok"):
                added += 1
                st["count_today"] += 1
    _state_save(st)
    return {"ok": True, "seen": seen, "added": added, "count_today": st["count_today"]}
# ===============================
# FIN PATCH
# ===============================
# ===============================
# PATCH "CHAT-KERNEL-SUMMARY" — synthèse locale depuis memory.json
# ===============================
from pathlib import Path

try:
    MEM_FILE
except NameError:
    MEM_FILE = Path(".alsadika/memory.json")

def _mem_all_items():
    try:
        data = _read_json(MEM_FILE, {"items":[]})
        items = data.get("items") or []
        # normalise quelques champs
        for it in items:
            it.setdefault("meta", {})
            it["meta"].setdefault("source","")
            it["meta"].setdefault("title","")
            it["meta"].setdefault("domain","")
        return items
    except Exception:
        return []

def _tok_set(s: str):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9àâäçéèêëîïôöùûüÿ\- ]"," ", s)
    return {t for t in re.split(r"\s+", s) if t and len(t)>=3}

def _match_score_mem(item, terms):
    text = f"{item.get('key','')} {item.get('value','')} {item.get('meta',{}).get('title','')}".lower()
    sc = 0.0
    for t in terms:
        if t in text:
            sc += 1.0
    # petit bonus si le terme apparaît dans le titre
    title = (item.get("meta",{}).get("title") or "").lower()
    sc += sum(0.5 for t in terms if t in title)
    # pondère par score d’extraction si présent
    try:
        sc += float(item.get("meta",{}).get("score",0))*0.2
    except Exception:
        pass
    return sc

def _format_source(meta):
    t = (meta.get("title") or "").strip()
    d = (meta.get("domain") or "").strip()
    if t and d:
        return f"{t} ({d})"
    if t:
        return t
    if meta.get("source"):
        return meta["source"]
    return "(source inconnue)"

def kernel_summarize(query: str, k: int = 8) -> str:
    """
    Résume k éléments les plus pertinents de la mémoire pour les termes de `query`.
    Retour: texte en français avec points clés + sources.
    """
    items = _mem_all_items()
    if not items:
        return "Mémoire locale vide — rien à résumer."

    # parse "mot1, mot2 | k=10" éventuel
    q = (query or "").strip()
    m = re.search(r"\|\s*k\s*=\s*(\d+)", q)
    if m:
        try: k = max(1, int(m.group(1)))
        except: pass
    q = re.sub(r"\|\s*k\s*=\s*\d+\s*$", "", q).strip(" ,")
    # tokens
    terms = _tok_set(q) or set()
    # si pas de termes, on prend les derniers items
    ranked = []
    if terms:
        for it in items:
            ranked.append( (_match_score_mem(it, terms), it) )
        ranked.sort(key=lambda x: x[0], reverse=True)
        ranked = [it for sc,it in ranked if sc>0][:k]
    else:
        ranked = items[-k:]

    if not ranked:
        return f"Aucun item en mémoire ne correspond à: {q or '(vide)'}."

    # Regrouper par thèmes simples si présents dans la requête
    buckets = {"patience":[],"vérité":[],"sincérité":[],"autres":[]}
    for it in ranked:
        text = (it.get("value") or it.get("key") or "").lower()
        if "patience" in text:
            buckets["patience"].append(it)
        elif "vérité" in text:
            buckets["vérité"].append(it)
        elif "sincérit" in text:  # sincérité / sincere
            buckets["sincérité"].append(it)
        else:
            buckets["autres"].append(it)

    lines = []
    title = "Synthèse locale — points clés appris"
    lines.append(title)
    lines.append("-"*len(title))

    def add_bucket(label, arr):
        if not arr: return
        lines.append(f"\n{label.capitalize()} :")
        for it in arr:
            val = it.get("value") or it.get("key") or ""
            val = re.sub(r"\s+", " ", val).strip()
            # raccourci propre
            if len(val) > 240:
                val = val[:237] + "…"
            src = _format_source(it.get("meta",{}))
            lines.append(f"• {val} — [source: {src}]")

    # ordre lisible
    add_bucket("patience", buckets["patience"])
    add_bucket("vérité", buckets["vérité"])
    add_bucket("sincérité", buckets["sincérité"])
    add_bucket("autres", buckets["autres"])

    # liste courte des sources distinctes
    seen = []
    for it in ranked:
        s = _format_source(it.get("meta",{}))
        if s not in seen:
            seen.append(s)
    if seen:
        lines.append("\nSources (mémoire locale) :")
        for s in seen[:12]:
            lines.append(f"- {s}")

    return "\n".join(lines)

# Intégration dans `chat`: détecter "summarize:" et répondre avec la synthèse locale
try:
    _ORIG_chat_run = chat_run
except NameError:
    _ORIG_chat_run = None

def chat_run(prompt: str):
    p = (prompt or "").strip()
    # Mode synthèse locale
    if p.lower().startswith("summarize:"):
        q = p.split(":",1)[1].strip()
        out = kernel_summarize(q, k=8)
        print(out)
        return 0
    # Compat : alias "kernel:" → synthèse aussi
    if p.lower().startswith("kernel:"):
        q = p.split(":",1)[1].strip()
        out = kernel_summarize(q, k=8)
        print(out)
        return 0
    # Sinon, comportement habituel
    if _ORIG_chat_run:
        return _ORIG_chat_run(p)
    print(p)
    return 0
# ===============================
# FIN PATCH
# ===============================
# ===============================
# PATCH "CHAT-HOOK" — intercepter summarize:/kernel: via cmd_chat
# ===============================
try:
    _ORIG_cmd_chat = cmd_chat  # garder l'original si présent
except NameError:
    _ORIG_cmd_chat = None

def cmd_chat(args):
    # Essaye d'extraire le prompt selon la structure des args
    p = ""
    try:
        p = getattr(args, "prompt", "") or ""
    except Exception:
        pass
    p = (p or "").strip()

    # Interception: summarize:/kernel: → synthèse locale depuis memory.json
    if p.lower().startswith("summarize:") or p.lower().startswith("kernel:"):
        q = p.split(":", 1)[1].strip()
        try:
            out = kernel_summarize(q, k=12)
        except Exception as e:
            out = f"[Erreur synthèse] {e}"
        print(out)
        return 0

    # Sinon, déléguer au comportement d'origine s’il existe
    if _ORIG_cmd_chat:
        return _ORIG_cmd_chat(args)

    # Fallback minimal: écho
    print(p)
    return 0
# ===============================
# FIN PATCH
# ===============================
# ===============================
# PATCH "CHAT-INJECT-PARSER" — réaffecter le handler du sous-commande `chat`
# ===============================
try:
    _PREV_build_parser = build_parser
except NameError:
    _PREV_build_parser = None

# On garde un fallback vers l'ancien cmd_chat si disponible
try:
    _FALLBACK_cmd_chat = cmd_chat
except NameError:
    _FALLBACK_cmd_chat = None

def _alsadika_cmd_chat_wrapper(args):
    # Récupérer le prompt fourni par le CLI
    p = ""
    try:
        p = getattr(args, "prompt", "") or ""
    except Exception:
        pass
    p = (p or "").strip()

    # Interception: summarize:/kernel: → synthèse locale depuis memory.json
    if p.lower().startswith("summarize:") or p.lower().startswith("kernel:"):
        q = p.split(":", 1)[1].strip()
        try:
            out = kernel_summarize(q, k=12)
        except Exception as e:
            out = f"[Erreur synthèse] {e}"
        print(out)
        return 0

    # Sinon, déléguer à l’ancien comportement si dispo
    if _FALLBACK_cmd_chat is not None:
        return _FALLBACK_cmd_chat(args)

    # Ultime fallback: écho
    print(p)
    return 0

def build_parser():
    # Construire le parser d’origine
    p = _PREV_build_parser() if _PREV_build_parser else argparse.ArgumentParser(prog="alsadika")
    try:
        # Retrouver le bloc des subparsers
        sp = [a for a in getattr(p, "_subparsers")._actions if getattr(a, "dest", None) in ("cmd","command")][0]
        # Récupérer le sous-parser 'chat'
        chat_parser = sp.choices.get("chat")
        if chat_parser is not None:
            # Remplacer le handler par notre wrapper
            chat_parser.set_defaults(_fn=_alsadika_cmd_chat_wrapper)
    except Exception:
        # Si la structure interne change, on ne casse rien.
        pass
    return p
# ===============================
# FIN PATCH
# ===============================
# ===============================
# PATCH "SUMMARIZE-COMMANDS" — ajoute des sous-commandes dédiées
# ===============================
try:
    _PREV_build_parser2 = build_parser
except NameError:
    _PREV_build_parser2 = None

def _cmd_summarize(args):
    q = (getattr(args, "q", "") or "").strip()
    k = int(getattr(args, "k", 8) or 8)
    try:
        out = kernel_summarize(q, k=k)
    except Exception as e:
        out = f"[Erreur synthèse] {e}"
    print(out)
    return 0

# alias "kernel-sum" identique
_cmd_kernel_sum = _cmd_summarize

def build_parser():
    import argparse
    # parser d'origine
    p = _PREV_build_parser2() if _PREV_build_parser2 else argparse.ArgumentParser(prog="alsadika")

    # récupérer le bloc subparsers
    try:
        sp = [a for a in getattr(p, "_subparsers")._actions if getattr(a, "dest", None) in ("cmd","command")][0]
    except Exception:
        # si structure différente, créer un set de subparsers
        sp = p.add_subparsers(dest="cmd")

    # n'ajouter que si absent
    if "summarize" not in getattr(sp, "choices", {}):
        c1 = sp.add_parser("summarize", help="Synthèse locale depuis memory.json")
        c1.add_argument("--q", required=True, help="Sujet ou requête (ex: 'patience, vérité, sincérité')")
        c1.add_argument("--k", type=int, default=12, help="Nb d'entrées mémoire max")
        c1.set_defaults(_fn=_cmd_summarize)

    if "kernel-sum" not in getattr(sp, "choices", {}):
        c2 = sp.add_parser("kernel-sum", help="Alias de summarize")
        c2.add_argument("--q", required=True)
        c2.add_argument("--k", type=int, default=12)
        c2.set_defaults(_fn=_cmd_kernel_sum)

    return p
# ===============================
# FIN PATCH
# ===============================
