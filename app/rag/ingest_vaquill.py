"""Import selected provisions from Vaquill Open India Law Parquet files.

This deliberately reads local Parquet files only. It does not call the Vaquill
API or download legal data, and it requires explicit Act-title filters so a
large corpus cannot be embedded accidentally.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from datetime import date
from pathlib import Path
from typing import Any

import chromadb
import pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer


DB_PATH = "chroma_db"
DEFAULT_COLLECTION = "statutes"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
MAX_CHARS = 1500
DEFAULT_BATCH_SIZE = 128


def _column(columns: list[str], *candidates: str, required: bool = False) -> str | None:
    by_lower = {name.lower(): name for name in columns}
    for candidate in candidates:
        if candidate.lower() in by_lower:
            return by_lower[candidate.lower()]
    if required:
        raise ValueError(
            f"Parquet is missing a required column (tried {', '.join(candidates)}). "
            f"Available columns: {', '.join(columns)}"
        )
    return None


def _value(row: dict[str, Any], column: str | None, default: str = "") -> str:
    if column is None:
        return default
    value = row.get(column)
    if value is None:
        return default
    return str(value).strip()


def _chunks(text: str, limit: int = MAX_CHARS) -> list[str]:
    """Keep short provisions whole; split unusually long ones on paragraph boundaries."""
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []

    chunks: list[str] = []
    current = ""
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        while len(paragraph) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(paragraph[:limit].strip())
            paragraph = paragraph[limit:].strip()
        if paragraph and len(current) + len(paragraph) + 2 > limit:
            if current:
                chunks.append(current)
            current = paragraph
        elif paragraph:
            current = f"{current}\n\n{paragraph}".strip()
    if current:
        chunks.append(current)
    return chunks


def _stable_id(act_id: str, act_title: str, section: str, chunk_no: int) -> str:
    identity = f"{act_id}|{act_title}|{section}|{chunk_no}"
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16]
    return f"vaquill-{digest}-{chunk_no}"


def ingest(
    parquet_path: Path,
    title_filters: list[str],
    *,
    collection_name: str = DEFAULT_COLLECTION,
    include_obsolete: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
) -> tuple[int, int]:
    if not parquet_path.is_file():
        raise FileNotFoundError(f"Parquet file not found: {parquet_path}")
    if not title_filters:
        raise ValueError("Supply at least one --title-contains filter to limit ingestion.")

    parquet = pq.ParquetFile(parquet_path)
    columns = parquet.schema_arrow.names
    act_col = _column(columns, "title", "act_title", "instrument_title", required=True)
    text_col = _column(columns, "text", "section_text", "body", "provision_text", required=True)
    section_col = _column(columns, "section_number", "section", "provision_number", required=True)
    act_id_col = _column(columns, "act_id", "instrument_id", "document_id")
    section_title_col = _column(columns, "section_title", "provision_title", "heading")
    year_col = _column(columns, "year", "enactment_year")
    state_col = _column(columns, "state", "jurisdiction")
    act_status_col = _column(columns, "act_status", "status")
    section_status_col = _column(columns, "section_status", "provision_status")
    source_col = _column(columns, "source_url", "source", "url")
    publisher_col = _column(columns, "source_publisher", "publisher")

    matchers = [filter_text.casefold() for filter_text in title_filters]
    excluded_statuses = {"repealed", "spent", "superseded", "repealed_in_part"}
    count = 0
    skipped_obsolete = 0
    model: SentenceTransformer | None = None
    collection = None
    pending_ids: list[str] = []
    pending_docs: list[str] = []
    pending_metas: list[dict[str, str]] = []

    def flush() -> None:
        nonlocal model, collection, pending_ids, pending_docs, pending_metas
        if not pending_docs or dry_run:
            pending_ids, pending_docs, pending_metas = [], [], []
            return
        if model is None:
            model = SentenceTransformer(EMBED_MODEL)
        if collection is None:
            client = chromadb.PersistentClient(path=DB_PATH)
            collection = client.get_or_create_collection(
                collection_name, metadata={"hnsw:space": "cosine"}
            )
        vectors = model.encode(
            pending_docs,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        collection.upsert(
            ids=pending_ids,
            documents=pending_docs,
            metadatas=pending_metas,
            embeddings=vectors.tolist(),
        )
        pending_ids, pending_docs, pending_metas = [], [], []

    for batch in parquet.iter_batches(batch_size=2048):
        for row in batch.to_pylist():
            act_title = _value(row, act_col)
            if not act_title or not any(term in act_title.casefold() for term in matchers):
                continue

            act_status = _value(row, act_status_col)
            section_status = _value(row, section_status_col)
            if not include_obsolete and (
                act_status.casefold() in excluded_statuses
                or section_status.casefold() in excluded_statuses
            ):
                skipped_obsolete += 1
                continue

            section = _value(row, section_col)
            body = _value(row, text_col)
            if not section or not body:
                continue
            section_title = _value(row, section_title_col, act_title)
            year = _value(row, year_col)
            act_id = _value(row, act_id_col, act_title)
            jurisdiction = _value(row, state_col, "central")
            header = f"{act_title} {year}, section {section}: {section_title}".strip()
            pieces = _chunks(f"{header}\n{body}")

            for chunk_no, piece in enumerate(pieces):
                pending_ids.append(_stable_id(act_id, act_title, section, chunk_no))
                pending_docs.append(piece)
                pending_metas.append({
                    "act": act_title,
                    "act_id": act_id,
                    "year": year,
                    "section": section,
                    "title": section_title,
                    "jurisdiction": jurisdiction,
                    "act_status": act_status,
                    "section_status": section_status,
                    "source_url": _value(row, source_col),
                    "source_publisher": _value(row, publisher_col),
                    "dataset": "vaquill-open-india-law",
                    "ingested": date.today().isoformat(),
                })
                count += 1
                if len(pending_docs) >= batch_size:
                    flush()

    flush()
    if dry_run:
        print(f"Dry run: selected {count} chunks; no embeddings or database writes made.")
    else:
        size = collection.count() if collection is not None else 0
        print(f"Upserted {count} chunks into {collection_name}. Collection size: {size}")
    if skipped_obsolete:
        print(f"Skipped {skipped_obsolete} provisions marked repealed, spent, or superseded.")
    return count, skipped_obsolete


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import selected provisions from a local Vaquill Open India Law Parquet file."
    )
    parser.add_argument("--parquet", required=True, type=Path, help="Local Parquet file path")
    parser.add_argument(
        "--title-contains",
        action="append",
        required=True,
        help="Act/instrument title substring to include; repeat to include more titles",
    )
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--include-obsolete",
        action="store_true",
        help="Include provisions explicitly marked repealed, spent, or superseded",
    )
    parser.add_argument("--dry-run", action="store_true", help="Count matches without indexing")
    args = parser.parse_args()
    ingest(
        args.parquet,
        args.title_contains,
        collection_name=args.collection,
        include_obsolete=args.include_obsolete,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
