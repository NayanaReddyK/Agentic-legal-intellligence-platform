import re
from app.core.cache import cached_ask
from app.core.jsonutil import extract_json
from app.rag.retrieve import gather_sources

# clause types worth a legal check, and the sections we always put in front of the model
PINNED = {
    "non_compete": [("Indian Contract Act", "27")],
    "penalty_liquidated_damages": [("Indian Contract Act", "74")],
    "indemnity": [("Indian Contract Act", "124"), ("Indian Contract Act", "125")],
    "arbitration": [("Arbitration and Conciliation Act", "7"),
                    ("Arbitration and Conciliation Act", "10"),
                    ("Arbitration and Conciliation Act", "11"),
                    ("Arbitration and Conciliation Act", "12"),
                    ("Arbitration and Conciliation Act", "20")],
    "termination": [],
}

MISSING_FINDINGS = {
    "governing_law": ("No governing law or jurisdiction clause. Add one naming Indian law and a court or arbitral seat.", "medium"),
    "confidentiality": ("No confidentiality clause. Add obligations covering business information, with exceptions and a survival period.", "medium"),
}

SYSTEM = (
    "You are a legal risk reviewer for Indian startup contracts, assisting a lawyer. "
    "Read the clause itself first: look for terms that are one-sided, uncapped, open-ended, missing a notice "
    "period, procedure, seat or limit, or unusually harsh. "
    "Then use the numbered statute sources to say whether the law addresses the problem. "
    "Rules: cite sources only by id (S1, S2...). Do not invent sections or case law. "
    "Do not describe facts the clause does not state. "
    "Do not say a clause is void or unenforceable unless a source says so. "
    "Do not add legal tests that are not in the sources. "
    "Cite a source only if its words apply to the clause; otherwise cite nothing. "
    "If a clause is risky or one-sided but no source addresses it, still report it: "
    "has_issue true, basis 'commercial', source_ids empty. "
    "Reply with JSON only."
)


def review_clause(clause: dict) -> dict | None:
    ctype = clause["analysis"]["type"]
    if ctype not in PINNED:
        return None
    k = 1 if PINNED[ctype] else 3          # pinned types already have the right sections; keep search noise low
    sources = gather_sources(f"{ctype.replace('_', ' ')} {clause['text'][:400]}", PINNED[ctype], k_semantic=k)
    src_text = "\n\n".join(
        f"[{s['id']}] {s['act']} {s['year']}, s.{s['section']} ({s['title']})\n{s['text']}" for s in sources)
    prompt = f"""Review this contract clause for legal risk under Indian law.

CLAUSE {clause['id']} ({clause['heading']}):
{clause['text'][:1500]}

STATUTE SOURCES:
{src_text}

Return JSON:
{{"has_issue": true|false,
  "basis": "statutory"|"commercial",
  "severity": "high"|"medium"|"low"|"none",
  "issue": "short title naming the actual problem in the clause",
  "explanation": "max 60 words, plain language, mention the exact problem in the clause",
  "source_ids": ["S1"],
  "supporting_quote": "words copied exactly from ONE source that support your claim, or empty",
  "suggested_fix": "max 40 words",
  "confidence": "high"|"medium"|"low"}}"""
    finding = {"clause_id": clause["id"], "clause_heading": clause["heading"], "type": ctype}
    try:
        out = extract_json(cached_ask(prompt, system=SYSTEM, max_tokens=3000))
    except Exception as e:
        return {**finding, "has_issue": None, "severity": "none", "issue": "Review failed",
                "explanation": str(e)[:200], "citations": [], "suggested_fix": "", "confidence": "low"}
    by_id = {s["id"]: s for s in sources}

    def deref(text: str) -> str:           # turn "(S3)" in the model's prose into "Indian Contract Act s.224"
        return re.sub(r"\bS\d+\b",
                      lambda m: f"{by_id[m.group(0)]['act']} s.{by_id[m.group(0)]['section']}" if m.group(0) in by_id else m.group(0),
                      text or "")

    ids = [i for i in (out.get("source_ids") or []) if i in by_id]       # drop made-up source ids
    finding.update({
        "has_issue": bool(out.get("has_issue")),
        "basis": out.get("basis", "commercial"),
        "severity": out.get("severity", "none"),
        "issue": deref(out.get("issue", "")),
        "explanation": deref(out.get("explanation", "")),
        "suggested_fix": deref(out.get("suggested_fix", "")),
        "confidence": out.get("confidence", "low"),
        "supporting_quote": out.get("supporting_quote", ""),
        "evidence": {f"{s['act']} s.{s['section']}": s["text"] for s in sources},
        "citations": [{"act": by_id[i]["act"], "section": by_id[i]["section"],
                       "title": by_id[i]["title"], "ref": f"{by_id[i]['act']} s.{by_id[i]['section']}"}
                      for i in ids],
        "retrieved": [f"{s['act']} s.{s['section']}" for s in sources],
    })
    return finding


def review_contract(clauses: list[dict], missing: list[str]) -> list[dict]:
    findings = [f for f in (review_clause(c) for c in clauses) if f]
    for m in missing:
        if m in MISSING_FINDINGS:
            text, sev = MISSING_FINDINGS[m]
            findings.append({"clause_id": None, "clause_heading": "(missing)", "type": f"missing_{m}",
                             "has_issue": True, "severity": sev, "issue": f"Missing {m.replace('_', ' ')} clause",
                             "explanation": text, "suggested_fix": text, "confidence": "high",
                             "citations": [], "retrieved": []})
    return findings