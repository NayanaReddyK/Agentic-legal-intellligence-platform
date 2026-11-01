import re
import sys
from datetime import date
import fitz  # PyMuPDF
import chromadb
from sentence_transformers import SentenceTransformer

DB_PATH = "chroma_db"
COLLECTION = "statutes"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
MAX_CHARS = 1500

SECTION_RE = re.compile(
    r"(?m)(?:^[ \t]*|(?<=[ \t]{2}))(?:\d{1,2}\[)?(\d{1,3}[A-Z]{0,2})\.\s*([“\"‘'(]?[A-Z][^\n]{3,150})"
)
FOOTNOTE_RE = re.compile(
    r"^(Subs|Ins|Omitted|Rep|Added|Vide|See|The words|The figures|Came into|Clause|Sub-section)\b",
    re.I,
)
SCHEDULE_RE = re.compile(r"(?m)^\s*THE\s+FIRST\s+SCHEDULE")
NOISE_RE = re.compile(r"(?m)^\s*(IndiaCode|\d{1,3})\s*$\n?")
FOOTNOTE_LINE_RE = re.compile(r"(?m)^\s*\d{1,2}\.\s+(Subs|Ins|Omitted|Rep|Added)\b.*$\n?")
STATE_AMEND_RE = re.compile(r"(?m)^\s*STATE AMENDMENT")


def read_pdf(path: str) -> str:
    doc = fitz.open(path)
    text = "\n".join(page.get_text("text", sort=True) for page in doc)
    text = NOISE_RE.sub("", text)
    return FOOTNOTE_LINE_RE.sub("", text)


def cut_schedules(text: str) -> str:
    for m in SCHEDULE_RE.finditer(text):
        if m.start() > len(text) * 0.5:
            return text[: m.start()]
    return text


def split_sections(text: str, skip: set) -> list[dict]:
    matches = [m for m in SECTION_RE.finditer(text) if not FOOTNOTE_RE.match(m.group(2))]
    sections = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.start():end]
        body = STATE_AMEND_RE.split(body)[0].strip()   # drop state amendments
        num = m.group(1)
        if num in skip:
            continue
        title = re.split(r"[—–]", m.group(2))[0].strip(" .")
        if num not in sections or len(body) > len(sections[num]["text"]):
            sections[num] = {"section": num, "title": title, "text": body}
    return list(sections.values())


def split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHARS:
        return [text]
    parts, cur = [], ""
    for para in text.split("\n"):
        if len(cur) + len(para) > MAX_CHARS and cur:
            parts.append(cur)
            cur = ""
        cur += para + "\n"
    if cur.strip():
        parts.append(cur)
    return parts


def main(pdf_path: str, act_name: str, year: str, skip: set):
    text = cut_schedules(read_pdf(pdf_path))
    sections = split_sections(text, skip)
    print(f"Found {len(sections)} sections")
    for s in sections[:3]:
        print(f"  s.{s['section']}: {s['title']}")

    model = SentenceTransformer(EMBED_MODEL)
    client = chromadb.PersistentClient(path=DB_PATH)
    col = client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

    ids, docs, metas = [], [], []
    for s in sections:
        for n, chunk in enumerate(split_long(s["text"])):
            ids.append(f"{act_name}-{s['section']}-{n}")
            docs.append(f"{act_name} {year}, section {s['section']}: {s['title']}\n{chunk}")
            metas.append({
                "act": act_name,
                "year": year,
                "section": s["section"],
                "title": s["title"],
                "ingested": date.today().isoformat(),
            })

    embeddings = model.encode(docs, normalize_embeddings=True, show_progress_bar=True)
    col.delete(where={"act": act_name})
    col.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings.tolist())
    print(f"Stored {len(docs)} chunks. Collection size: {col.count()}")


if __name__ == "__main__":
    skip = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else set()
    main(sys.argv[1], sys.argv[2], sys.argv[3], skip)