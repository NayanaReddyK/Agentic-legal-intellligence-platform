import re
from collections import Counter
from app.core import llm
from app.core.cache import cached_ask
from app.core.jsonutil import extract_json

SEV_ORDER = {"high": 0, "medium": 1, "low": 2, "none": 3}

SYSTEM = (
    "You are an independent senior legal reviewer checking another assistant's findings about an Indian contract. "
    "Be strict. A source only 'supports' a claim if its own words establish that claim for the facts in the clause. "
    "Reply with JSON only."
)


def _norm(s: str) -> str:
    for a, b in {"“": '"', "”": '"', "‘": "'", "’": "'", "—": "-", "–": "-"}.items():
        s = s.replace(a, b)
    s = re.sub(r"\d{1,2}\[", "", s).replace("]", "")      # drop footnote markers like 1[ ... ]
    return re.sub(r"\s+", " ", s).strip().lower()


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _norm(s))


def quote_verified(f: dict) -> bool:
    """Code check: is the model's supporting quote really in the cited source text?"""
    q = _norm(f.get("supporting_quote") or "")
    parts = [p for p in re.split(r"\.\.\.|…", q) if len(re.sub(r"[^a-z0-9]", "", p)) >= 12]
    if not parts:
        return False
    texts = [_squash(t) for t in (f.get("evidence") or {}).values()]
    return all(any(_squash(p) in t for t in texts) for p in parts)


def _check_applicability(todo: list[dict], clause_text: dict) -> dict:
    blocks = []
    for i, f in enumerate(todo):
        cites = "\n".join(f"  - {c['ref']}: {f['evidence'].get(c['ref'], '')[:700]}" for c in f["citations"]) or "  (none)"
        blocks.append(f"FINDING {i}\nClause text: {clause_text.get(f['clause_id'], '')[:600]}\n"
                      f"Claim: {f['issue']}. {f['explanation']}\nCited sources:\n{cites}")
    prompt = f"""Check each finding.
For every cited source give a verdict:
 "supports"   = the source's own words establish the claim for the facts actually in the clause
 "related"    = same topic, but it does not establish the claim
 "irrelevant" = about something else, or depends on facts the clause does not contain
Also set "overstated": true if the claim says more than the sources support (for example calling a clause
void or unenforceable, or adding a legal test that is not in the sources).

Return a JSON list: [{{"i": int, "citations": [{{"ref": str, "verdict": str}}], "overstated": bool, "note": "max 30 words"}}]

{chr(10).join(blocks)}"""
    out = extract_json(cached_ask(prompt, system=SYSTEM, max_tokens=4000, model=llm.REVIEW_MODEL))
    return {o["i"]: o for o in out}


def review(findings: list[dict], clauses: list[dict]) -> list[dict]:
    clause_text = {c["id"]: c["text"] for c in clauses}
    todo = [f for f in findings if f.get("has_issue") and f.get("clause_id")]
    try:
        results = _check_applicability(todo, clause_text) if todo else {}
        failed = None
    except Exception as e:
        results, failed = {}, str(e)[:150]

    todo_ids = {id(f): i for i, f in enumerate(todo)}
    for f in findings:
        if f.get("has_issue") is None:
            f["status"] = "unchecked"; continue
        if not f["has_issue"]:
            f["status"] = "no_issue"; continue
        if not f.get("clause_id"):
            f["status"] = "rule_based"; continue          # missing-clause findings come from code, not the model
        if failed:
            f["status"] = "unchecked"; f["reviewer_note"] = f"Review step failed: {failed}"; continue
        res = results.get(todo_ids[id(f)], {})
        verdicts = {c.get("ref"): c.get("verdict") for c in res.get("citations", [])}
        kept, dropped = [], []
        for c in f["citations"]:
            c["verdict"] = verdicts.get(c["ref"], "related")
            (dropped if c["verdict"] == "irrelevant" else kept).append(c)
        f["citations"], f["dropped_citations"] = kept, dropped
        f["quote_verified"] = quote_verified(f)
        f["overstated"] = bool(res.get("overstated"))
        f["reviewer_note"] = res.get("note", "")
        if f["overstated"]:
            f["confidence"] = "low"
        supported = any(c["verdict"] == "supports" for c in kept)
        if supported and f["quote_verified"] and not f["overstated"]:
            f["status"] = "verified"
        elif supported:
            f["status"] = "needs_review"
        else:
            f["status"] = "commercial_risk"          # real concern, but no statute directly establishes it
    return findings


STATUS_TEXT = {
    "verified": "Verified: cited statute supports the finding and the quoted words were found in the source.",
    "needs_review": "Needs lawyer review: statute is relevant, but the reviewer flagged the wording or the quote.",
    "commercial_risk": "Risk observation: no cited statute directly establishes this. Lawyer to judge.",
    "rule_based": "Gap detected by rule: expected clause is absent.",
    "unchecked": "Not checked: the review step failed.",
}


def build_report(meta: dict, findings: list[dict]) -> dict:
    issues = [f for f in findings if f.get("has_issue") is not False]
    issues.sort(key=lambda f: (SEV_ORDER.get(f["severity"], 3), f["clause_id"] or "Z"))
    return {"contract_type": meta.get("contract_type"), "parties": meta.get("parties"),
            "counts": dict(Counter(f["status"] for f in issues)), "findings": issues}


def render_markdown(report: dict) -> str:
    L = [f"# Contract review: {report['contract_type']}", "",
         "_AI-assisted draft for lawyer review. Not legal advice._", "",
         f"Status counts: {report['counts']}", ""]
    for f in report["findings"]:
        where = f"Clause {f['clause_id'][1:]} ({f['clause_heading']})" if f["clause_id"] else "Whole contract"
        L += [f"## [{f['severity'].upper()}] {f['issue']}", f"**{where}**  |  confidence: {f['confidence']}", "",
              f["explanation"], "", f"**Suggested fix:** {f['suggested_fix']}", ""]
        if f["citations"]:
            L.append("**Sources:** " + "; ".join(c["ref"] for c in f["citations"]))
        L.append(f"**Review status:** {STATUS_TEXT.get(f['status'], f['status'])}")
        if f.get("overstated"):
            L.append("**warning:** the reviewer judged this explanation overstated. Treat the legal claim with caution.")
        if f.get("reviewer_note"):
            L.append(f"**Reviewer note:** {f['reviewer_note']}")
        if f.get("dropped_citations"):
            L.append("**Removed as irrelevant:** " + "; ".join(c["ref"] for c in f["dropped_citations"]))
        L.append("")
    return "\n".join(L)