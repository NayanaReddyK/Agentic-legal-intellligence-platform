from app.rag.search import search, _col


def _clean(text: str) -> str:
    return text.replace("IndiaCode", " ")


def get_section(act: str, section: str, max_chars: int = 1200):
    """Fetch one named section (first chunk) straight from the database."""
    r = _col.get(where={"$and": [{"act": act}, {"section": section}]})
    if not r["ids"]:
        return None
    rows = sorted(zip(r["ids"], r["documents"], r["metadatas"]),
                  key=lambda x: int(x[0].rsplit("-", 1)[1]))
    _, doc, meta = rows[0]
    return {"text": _clean(doc)[:max_chars], "meta": meta}


def gather_sources(query: str, pinned: list, k_semantic: int = 3) -> list[dict]:
    """Pinned sections first (rule-based), then semantic hits. Each gets an id S1, S2, ..."""
    out, seen = [], set()

    def add(text, meta):
        key = (meta["act"], meta["section"])
        if key in seen:
            return
        seen.add(key)
        out.append({"id": f"S{len(out) + 1}", "act": meta["act"], "year": meta["year"],
                    "section": meta["section"], "title": meta["title"], "text": text})

    for act, sec in pinned:
        hit = get_section(act, sec)
        if hit:
            add(hit["text"], hit["meta"])
    for r in search(query, k=k_semantic + len(pinned)):
        if len(out) >= len(pinned) + k_semantic:
            break
        add(_clean(r["text"])[:1200], r["meta"])
    return out