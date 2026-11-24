import os


def analyse_file(path: str) -> dict:
    """Run the full pipeline on one contract file (makes model calls; cached on disk)."""
    from app.core.parser import load_contract, segment_clauses
    from app.agents import doc_analysis as d
    from app.agents.contractreview import review_contract
    from app.agents.review_agent import review

    text = load_contract(path)
    seg = segment_clauses(text)
    meta = d.analyse_metadata(seg["preamble"], text)
    clauses = d.classify_clauses(seg["clauses"])
    findings = review_contract(clauses, d.find_missing(clauses, meta))
    findings = review(findings, clauses)
    return {"name": os.path.splitext(os.path.basename(path))[0],
            "title": meta.get("contract_type") or "Contract", "clauses": clauses, "findings": findings}