import json, sys
from app.core.parser import load_contract, segment_clauses
from app.agents import doc_analysis as d

path = sys.argv[1] if len(sys.argv) > 1 else "tests/contracts/contract_01.txt"
text = load_contract(path)
seg = segment_clauses(text)
print(f"Found {len(seg['clauses'])} clauses:", [c["heading"] for c in seg["clauses"]])

meta = d.analyse_metadata(seg["preamble"], text)
print("\nMETADATA:", json.dumps(meta, indent=2))

clauses = d.classify_clauses(seg["clauses"])
for c in clauses:
    a = c["analysis"]
    print(f"\n[{c['id']}] {c['heading']} -> {a['type']}\n   {a['summary']}\n   amounts={a['amounts']} periods={a['periods']}")

print("\nMISSING:", d.find_missing(clauses, meta))