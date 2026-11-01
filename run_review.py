import json, sys
from app.core.parser import load_contract, segment_clauses
from app.agents import doc_analysis as d
from app.agents.contractreview import review_contract
from app.agents.review_agent import review, build_report, render_markdown

path = sys.argv[1] if len(sys.argv) > 1 else "tests/contracts/contract_01.txt"
name = path.replace("\\", "/").split("/")[-1].replace(".txt", "")
text = load_contract(path)
seg = segment_clauses(text)
meta = d.analyse_metadata(seg["preamble"], text)
clauses = d.classify_clauses(seg["clauses"])
findings = review_contract(clauses, d.find_missing(clauses, meta))
findings = review(findings, clauses)          # Review Agent: verify, downgrade, drop weak citations
report = build_report(meta, findings)

for f in report["findings"]:
    print(f"\n[{f['status'].upper()}] {f['clause_id']} {f['clause_heading']}  severity={f['severity']} confidence={f['confidence']}")
    print(f"   {f['issue']}")
    print(f"   cites: {[c['ref'] for c in f['citations']]}   dropped: {[c['ref'] for c in f.get('dropped_citations', [])]}")
    if f.get("reviewer_note"):
        print(f"   reviewer: {f['reviewer_note']}")
print("\nCounts:", report["counts"])

json.dump(findings, open(f"eval/results_{name}.json", "w", encoding="utf-8"), indent=2)
open(f"eval/report_{name}.md", "w", encoding="utf-8").write(render_markdown(report))
print(f"Saved eval/results_{name}.json and eval/report_{name}.md")