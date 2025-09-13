#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# NOTE: Fichier noyau fourni par l'utilisateur (intégré tel quel). Ce fichier écrit des données locales dans .alsadika/ sous le cwd backend.
# La majeure partie de ce code vient du noyau "Al Sâdika — noyau unique (V2, patches fusionnés)".
# ATTENTION: Le code est autonome et ne requiert pas d'installation obligatoire.

# Début du contenu noyau (copié)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Al Sâdika — noyau unique (V2, patches fusionnés)
Mono-fichier local-first : orchestration, mémoire approuvée, filtre éthique Verrou, double mode (public/privé),
sceau durci (PBKDF2 + lockout), évaluateur adaptatif (feedback), mutation A/B validée d'une compétence (summarizer),
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
- Verrou appliqué: vérité > satisfaction, aucune proposition "pour proposer".
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
# Sceau durci (liaison à l'utilisatrice)
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
# Détection d'intention
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
             "Objectif: synthèse opérationnelle utile à l'équipe.", 320),
        ]
        s = 0.0
        for txt, mc in samples:
            out = fn(txt, mc)
            s += evaluator.score(out)
            if len(out) > mc + 50:
                s -= 0.5  # pénaliser dépassement
        return s / len(samples)

    def _gen_variant_source(self, head_ratio: float, tail_ratio: float, normalize: bool, keep_keywords: bool) -> str:
        # Source Python d'une fonction 'summarizer(text, max_chars)' sandbox-safe
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
        # Vérifications simples: non-contradiction triviale, pas de promesse d'omniscience
        if re.search(r"\binédit absolu\b", answer, re.I):
            answer = re.sub(r"\binédit absolu\b", "originalité probable (sans garantie d'inédit absolu)", answer, flags=re.I)
        return True, answer

class ActionEngine:
    # Stubs sûrs: pas d'accès hors dossier autorisé; pas d'exécution.
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
            # empreinte d'intégrité du fichier courant (tamper-evidence)
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

    c8 = sp.add_parser("feedback", help="Apprendre d'un retour utilisateur (approve/reject)")
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

# Fin du noyau copié