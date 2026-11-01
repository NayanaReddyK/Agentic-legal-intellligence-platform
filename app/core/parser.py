import re
from pathlib import Path


def load_contract(path: str) -> str:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".txt":
        return p.read_text(encoding="utf-8", errors="ignore")
    if ext == ".docx":
        from docx import Document
        return "\n".join(par.text for par in Document(str(p)).paragraphs)
    if ext == ".pdf":
        import fitz
        return "\n".join(page.get_text("text", sort=True) for page in fitz.open(str(p)))
    raise ValueError(f"Unsupported file type: {ext}")


# top-level clause heading: "4. NON-COMPETE" or "4. Non-Compete" or "Clause 4 - Non-Compete"
HEAD_RE = re.compile(
    r"(?m)^[ \t]*(?:Clause\s+)?(\d{1,2})[.)]?[ \t]+([A-Z][A-Za-z0-9 ,&/'\-]{2,70})[ \t]*$"
)


def normalise(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"[ \t]+\n", "\n", text)


def segment_clauses(text: str) -> dict:
    """Return {'preamble': str, 'clauses': [{'id','number','heading','text'}]}"""
    text = normalise(text)
    heads = []
    expected = 1
    for m in HEAD_RE.finditer(text):
        if int(m.group(1)) == expected:        # numbers must run 1,2,3... (rejects stray numbers)
            heads.append(m)
            expected += 1
    if not heads:
        return {"preamble": text.strip(),
                "clauses": [{"id": "C1", "number": "1", "heading": "Full text", "text": text.strip()}]}
    preamble = text[: heads[0].start()].strip()
    clauses = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        clauses.append({
            "id": f"C{m.group(1)}",
            "number": m.group(1),
            "heading": m.group(2).strip().title(),
            "text": text[m.start():end].strip(),
        })
    return {"preamble": preamble, "clauses": clauses}