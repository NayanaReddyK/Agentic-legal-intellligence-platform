from app.core.cache import cached_ask
from app.core.jsonutil import extract_json
import re

SYSTEM = (
    "You are a careful legal document analyst for Indian commercial contracts. "
    "Extract only what is stated in the text. If something is not stated, use null. "
    "Reply with JSON only, no commentary."
)

CLAUSE_TYPES = [
    "definitions", "shareholding", "termination", "non_compete", "penalty_liquidated_damages",
    "indemnity", "payment", "arbitration", "governing_law", "confidentiality",
    "intellectual_property", "general_boilerplate", "other",
]


def analyse_metadata(preamble: str, full_text: str) -> dict:
    prompt = f"""Extract the following from this contract as JSON:
{{"contract_type": str, "parties": [{{"name": str, "role": str}}], "agreement_date": str|null,
  "effective_date": str|null, "governing_law": str|null, "jurisdiction": str|null}}

CONTRACT OPENING:
{preamble}

CONTRACT TEXT:
{full_text[:6000]}"""
    return extract_json(cached_ask(prompt, system=SYSTEM))


def classify_clauses(clauses: list[dict]) -> list[dict]:
    """One LLM call for all clauses (saves free-tier quota)."""
    listing = "\n\n".join(f"[{c['id']}] {c['text'][:700]}" for c in clauses)
    prompt = f"""For each clause below, return a JSON list of objects:
{{"id": str, "type": one of {CLAUSE_TYPES}, "summary": str (max 20 words),
  "obligations": [str], "amounts": [str], "periods": [str]}}

CLAUSES:
{listing}"""
    out = extract_json(cached_ask(prompt, system=SYSTEM, max_tokens=4096))
    by_id = {o["id"]: o for o in out}
    for c in clauses:
        a = by_id.get(c["id"], {"type": "other", "summary": ""})
        for k in ("obligations", "amounts", "periods"):
            a[k] = a.get(k) or []
        if a.get("type") not in CLAUSE_TYPES:
            a["type"] = "other"
        c["analysis"] = a
    return clauses


GOV_RE = re.compile(r"governed by|governing law|laws? of india|exclusive jurisdiction|jurisdiction of (?:the )?courts?|subject to the jurisdiction", re.I)
CONF_RE = re.compile(r"confidential", re.I)


def find_missing(clauses: list[dict], metadata: dict) -> list[str]:
    """Pure code, no LLM: which expected clause types are absent? Checks the text itself, not model metadata."""
    body = " ".join(c["text"] for c in clauses)
    present = {c["analysis"]["type"] for c in clauses}
    missing = []
    if "governing_law" not in present and not GOV_RE.search(body):
        missing.append("governing_law")
    if "confidentiality" not in present and not CONF_RE.search(body):
        missing.append("confidentiality")
    return missing