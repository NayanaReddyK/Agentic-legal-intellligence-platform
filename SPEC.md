# Agentic Legal Intelligence Platform — Working Specification

## Project goal

Build a demonstrable, lawyer-in-the-loop assistant for first-pass review of Indian corporate agreements. It should extract contract structure, identify a bounded set of risks, retrieve relevant statute provisions, check citation integrity, and let a lawyer accept, edit, or reject each finding.

The project claim to evaluate is: **for the selected contract types and statute corpus, a structured retrieval-and-review workflow produces more useful, supportable findings than a plain chat-model baseline.** This is a prototype, not legal advice or a production legal service.

## Scope

- Start with NDAs and vendor/service agreements; expand only if the core flow and evaluation are stable.
- Use text-based TXT, DOCX, and PDF contracts. Scanned-document OCR is out of scope.
- Ground legal citations in a small, curated corpus of Indian Contract Act, Arbitration and Conciliation Act, and selected Companies Act provisions.
- Show the source text and provenance for every cited provision. Use statute text checked against official sources; do not generate statute text from model memory.
- Require a human decision for every finding before it appears in an approved report.
- Keep the app single-user and local for this prototype. Authentication, multi-tenant storage, and production confidentiality controls are future work.

## Current implementation (baseline)

- Streamlit UI supports saved reviews and live upload/analysis.
- Parser reads TXT, DOCX, and text-based PDF, then segments sequentially numbered headings.
- LLM calls extract metadata and classify clauses; results are cached locally.
- Contract review currently targets termination, non-compete, liquidated damages, indemnity, and arbitration, plus simple missing-governing-law and confidentiality checks.
- ChromaDB and BGE-small provide dense statute retrieval. BM25 is listed as a dependency but is **not currently implemented**.
- A second model review checks clause-claim fit and citation applicability. A literal quote check exists, but it currently searches all retrieved evidence rather than confirming the quote against the exact cited provision.
- SQLite stores lawyer decisions and a decision-change log. The UI supports accept/reject, edits, notes, and Markdown export.
- There are five synthetic sample contracts and saved evaluation outputs. There is no full software test suite, no plain-model baseline, and no retrieval ablation yet.

These are baseline facts, not claims about the final deliverable. Do not describe the system as parallel, supervisor-routed, fully schema-validated, or citation-verified in code until those behaviors are implemented and demonstrated.

## Target workflow

1. Parse the contract and identify clauses, parties, dates, and amounts.
2. Build a visible review plan for the supported document type.
3. Run focused analysis and risk checks. Keep the orchestration simple; use parallel execution only for independent steps and measure its benefit before claiming a speedup.
4. Retrieve relevant statute provisions from the curated corpus.
5. Validate each citation identifier and quoted text against the exact source record; separately record whether the source is relevant to the claim.
6. Return structured findings with clause text, risk, severity, explanation, evidence, suggested wording, and confidence/status.
7. Let the lawyer accept, edit, or reject each finding and preserve the decision history.
8. Export a report containing accepted findings and clearly distinguishing AI output from lawyer approval.

An agent that finds no relevant source must say so rather than inventing one. Invalid or unverifiable citations must not be shown as supported.

## Agent boundaries

- **Supervisor/router:** classify the agreement, choose applicable checks, display the plan, and combine results. A deterministic router is acceptable for the MVP; do not add an LLM planner without a measurable need.
- **Document analysis:** extract structure and entities, classify clauses, and flag only simple, explainable internal inconsistencies.
- **Contract review:** apply a documented, bounded checklist to supported clause types and identify missing terms.
- **Legal research:** retrieve provisions and return exact source IDs, text, and provenance. No case-law claims unless a verified case corpus is added.
- **Compliance lite:** implement only a few checks that can be grounded and evaluated (for example, presence of signatory/approval details); otherwise label this as future work.
- **Drafting lite:** suggest replacement wording from reviewed patterns and label it as a draft. Cut this first if time is short.
- **Review/verifier:** enforce citation existence and quote matching in code; use model review only for semantic relevance and claim-to-clause fit.
- **Lawyer approval:** human decisions are final; preserve edits and notes.

Every model boundary should have a validated output shape. Record enough trace data to explain which stages ran, their sources, outcome, and timing, while avoiding storage of sensitive real contracts in this prototype.

## Evaluation requirements

- Maintain a development set and a held-out contract-level evaluation set. Do not tune rules or prompts on held-out contracts.
- Include synthetic planted issues for controlled checks and a smaller, independently reviewed set of realistic templates. Record provenance and licensing for public documents.
- Have a second reviewer label a subset and report disagreements; legal labels are not assumed to be objective ground truth.
- Compare the system with the same base model on the same contracts and task, without retrieval or the verifier. Report the prompt and model used.
- Measure clause extraction precision/recall, risk precision/recall, citation validity, citation relevance, reviewer edit/reject rate, and latency.
- Separate **citation validity** (the source ID exists and the quote matches that source) from **citation relevance** (the source supports the specific claim). Code can enforce validity; relevance needs human evaluation.
- Add retrieval metrics such as Recall@k and MRR only after creating a human-checked query-to-provision relevance set. Establish dense BGE as the baseline before adding BM25 or fine-tuning.
- Report measured results and failures, not targets as achievements. Treat a small test set as indicative only.

## Build order and cut line

1. Freeze this scope and inventory the legal corpus and its provenance.
2. Make citation validation exact and independently demonstrable with a deliberately fake citation and a mismatched quote.
3. Create an end-to-end trace and a visible plan for the existing pipeline; keep it sequential unless parallel execution is justified.
4. Add only the smallest useful compliance checks and decide whether drafting can fit after core reliability work.
5. Build a clean evaluation split, baseline, and verifier/retrieval ablations; freeze features before final reporting.
6. Prepare the demo, report, README, and reproducible setup instructions.

If time is short, cut drafting, then compliance depth, then extra contract types. Preserve citation verification, human approval, and evaluation. Do not claim a feature that was only designed but not implemented.

## Working agreements

- Keep statute text and legal rules tied to verified sources and human review.
- Use synthetic/public documents during development; do not put confidential contracts into hosted model calls or the repository.
- Keep model/provider configuration in environment variables; never commit credentials, uploads, local caches, or the generated Chroma database.
- For each implementation change, explain the behavior, validate it with a focused check, and update this specification if scope changes.
- Disclose AI assistance according to university rules and be able to explain the code, legal labels, and evaluation choices.
