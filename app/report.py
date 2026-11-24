from datetime import date

SEV_ORDER = {"high": 0, "medium": 1, "low": 2, "none": 3}
SEV_COLOR = {"high": "red", "medium": "orange", "low": "blue", "none": "gray"}
STATUS_LABEL = {
    "verified": "Source-checked",
    "needs_review": "Needs review",
    "commercial_risk": "Risk observation",
    "rule_based": "Gap (rule-based)",
    "disputed": "Disputed by reviewer",
    "unchecked": "Not checked",
}
STATUS_HELP = {
    "verified": "The quoted words were found in the cited statute and a second model judged the finding supported. This is not a legal opinion.",
    "needs_review": "The statute is relevant, but the reviewer flagged the wording or the quote.",
    "commercial_risk": "A real concern, but no statute in the corpus directly establishes it. Lawyer to judge.",
    "rule_based": "An expected clause is absent (found by a text rule, not by the model).",
    "disputed": "The reviewer believes this finding is inaccurate or overstated. Shown for transparency.",
    "unchecked": "The review step failed for this finding.",
}


def fkey(f: dict) -> str:
    return f"{f.get('clause_id') or 'GLOBAL'}:{f.get('type')}"


def visible_findings(findings: list[dict]) -> list[dict]:
    items = [f for f in findings if f.get("has_issue") is not False]
    items.sort(key=lambda f: (f.get("status") == "disputed", SEV_ORDER.get(f.get("severity", "none"), 3), f.get("clause_id") or "Z"))
    return items


def where(f: dict) -> str:
    return f"Clause {f['clause_id'][1:]} ({f.get('clause_heading', '')})" if f.get("clause_id") else "Whole contract"


def build_approved_markdown(case_name: str, title: str, findings: list[dict], decisions: dict) -> str:
    acc = [f for f in findings if decisions.get(fkey(f), {}).get("decision") == "Accept"]
    rej = [f for f in findings if decisions.get(fkey(f), {}).get("decision") == "Reject"]
    pend = [f for f in findings if decisions.get(fkey(f), {}).get("decision", "Pending") == "Pending"]
    L = [f"# Contract review: {title}", "",
         f"File: {case_name}  |  Date: {date.today().isoformat()}", "",
         "_Prepared with AI assistance and reviewed finding by finding by a lawyer. Not legal advice until signed off below._", "",
         f"Accepted: {len(acc)}  |  Rejected: {len(rej)}  |  Not yet reviewed (excluded): {len(pend)}", "",
         "## Accepted findings", ""]
    if not acc:
        L += ["_None._", ""]
    for n, f in enumerate(acc, 1):
        d = decisions[fkey(f)]
        L += [f"### {n}. [{f.get('severity', '').upper()}] {f.get('issue', '')}", f"**{where(f)}**", "",
              f.get("explanation", ""), "", f"**Recommended action:** {d.get('fix') or f.get('suggested_fix', '')}"]
        if f.get("citations"):
            L.append("**Sources:** " + "; ".join(c["ref"] for c in f["citations"]))
        L.append(f"**AI review status:** {STATUS_LABEL.get(f.get('status'), f.get('status'))}")
        if d.get("note"):
            L.append(f"**Lawyer note:** {d['note']}")
        L.append("")
    L += ["## Rejected findings", ""]
    if not rej:
        L += ["_None._", ""]
    for f in rej:
        d = decisions[fkey(f)]
        L.append(f"- {where(f)}: {f.get('issue', '')}" + (f" (note: {d['note']})" if d.get("note") else ""))
    L += ["", "---", "Approved by: ______________________    Date: ____________", ""]
    return "\n".join(L)