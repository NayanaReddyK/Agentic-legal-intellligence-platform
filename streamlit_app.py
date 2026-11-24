import glob, json, os
import streamlit as st
from app.core import store
from app.core.parser import load_contract, segment_clauses
from app.report import (SEV_COLOR, STATUS_LABEL, STATUS_HELP, build_approved_markdown, fkey, visible_findings, where)

st.set_page_config(page_title="Contract review assistant", layout="wide")
store.init_db()
OPTIONS = ["Pending", "Accept", "Reject"]


def open_saved(path: str) -> dict:
    name = os.path.basename(path)[len("results_"):-len(".json")]
    findings = json.load(open(path, encoding="utf-8"))
    txt = f"tests/contracts/{name}.txt"
    clauses, title = [], name
    if os.path.exists(txt):
        raw = load_contract(txt)
        clauses = segment_clauses(raw)["clauses"]
        title = next((l.strip().title() for l in raw.splitlines() if l.strip()), name)
    return {"name": name, "title": title, "clauses": clauses, "findings": findings}


def on_change(name: str, key: str):
    store.save_decision(name, key, st.session_state[f"dec_{name}_{key}"],
                        st.session_state.get(f"fix_{name}_{key}", ""), st.session_state.get(f"note_{name}_{key}", ""))


st.title("Contract review assistant")
st.warning("AI-assisted first pass. Every finding needs a lawyer's decision. This is not legal advice.")

with st.sidebar:
    st.header("Open a contract")
    source = st.radio("Source", ["Saved results (demo)", "Upload and analyse"])
    if source == "Saved results (demo)":
        files = sorted(glob.glob("eval/results_*.json"))
        pick = st.selectbox("Saved review", files, format_func=lambda p: os.path.basename(p)[8:-5]) if files else None
        if not files:
            st.info("No saved results yet. Run run_review.py first.")
        if pick and st.button("Open"):
            st.session_state["case"] = open_saved(pick)
    else:
        up = st.file_uploader("Contract (.txt, .docx, .pdf)", type=["txt", "docx", "pdf"])
        st.caption("Runs the live pipeline. Uses model calls (cached afterwards).")
        if up and st.button("Analyse"):
            os.makedirs("uploads", exist_ok=True)
            path = os.path.join("uploads", up.name)
            open(path, "wb").write(up.getbuffer())
            with st.spinner("Analysing: parsing, reviewing, checking citations..."):
                from app.pipeline import analyse_file
                st.session_state["case"] = analyse_file(path)

case = st.session_state.get("case")
if not case:
    st.info("Open a saved review or upload a contract from the sidebar.")
    st.stop()

name = case["name"]
findings = visible_findings(case["findings"])
decisions = store.load_decisions(name)
clause_text = {c["id"]: c["text"] for c in case["clauses"]}
state = lambda f: decisions.get(fkey(f), {}).get("decision", "Pending")

st.subheader(case["title"])
c1, c2, c3, c4 = st.columns(4)
c1.metric("Findings", len(findings))
c2.metric("High severity", sum(f.get("severity") == "high" and f.get("status") != "disputed" for f in findings))
c3.metric("Disputed by reviewer", sum(f.get("status") == "disputed" for f in findings))
c4.metric("Still to decide", sum(state(f) == "Pending" for f in findings))

statuses = sorted({f.get("status", "unchecked") for f in findings})
shown = st.multiselect("Show statuses", statuses, default=statuses, format_func=lambda s: STATUS_LABEL.get(s, s))

for f in findings:
    if f.get("status", "unchecked") not in shown:
        continue
    key, sev, status = fkey(f), f.get("severity", "none"), f.get("status", "unchecked")
    with st.container(border=True):
        label = "DISPUTED" if status == "disputed" else sev.upper()
        st.markdown(f"**:{SEV_COLOR.get(sev, 'gray')}[{label}]**  {f.get('issue', '')}  \n"
                    f"{where(f)}  |  {STATUS_LABEL.get(status, status)}  |  confidence: {f.get('confidence', '')}")
        st.write(f.get("explanation", ""))
        if status == "disputed":
            st.caption("The reviewer believes this finding is inaccurate or overstated. Shown for transparency.")
        if f.get("citations"):
            st.markdown("**Sources:** " + "; ".join(c["ref"] for c in f["citations"]))
        st.markdown(f"**Suggested fix:** {f.get('suggested_fix', '')}")
        if f.get("reviewer_note"):
            st.caption(f"Reviewer note: {f['reviewer_note']}")
        with st.expander("Evidence and details"):
            st.caption(STATUS_HELP.get(status, ""))
            if f.get("clause_id") and clause_text.get(f["clause_id"]):
                st.markdown("**Clause text**"); st.text(clause_text[f["clause_id"]])
            for c in f.get("citations", []):
                st.markdown(f"**{c['ref']}** ({c.get('title', '')})"); st.text((f.get("evidence") or {}).get(c["ref"], "")[:900])
            if f.get("dropped_citations"):
                st.caption("Removed as irrelevant: " + "; ".join(c["ref"] for c in f["dropped_citations"]))
        d = decisions.get(key, {})
        st.radio("Decision", OPTIONS, index=OPTIONS.index(d.get("decision", "Pending")), horizontal=True,
                 key=f"dec_{name}_{key}", on_change=on_change, args=(name, key))
        st.text_area("Recommended action (edit if needed)", value=d.get("fix") or f.get("suggested_fix", ""),
                     key=f"fix_{name}_{key}", on_change=on_change, args=(name, key), height=80)
        st.text_input("Lawyer note", value=d.get("note", ""), key=f"note_{name}_{key}", on_change=on_change, args=(name, key))

st.divider()
pending = sum(state(f) == "Pending" for f in findings)
if pending:
    st.caption(f"{pending} finding(s) still pending. They will be excluded from the approved report.")
report_md = build_approved_markdown(name, case["title"], findings, store.load_decisions(name))
st.download_button("Download approved report (.md)", report_md, file_name=f"approved_review_{name}.md", mime="text/markdown")
with st.expander("Preview approved report"):
    st.markdown(report_md)