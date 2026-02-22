"""
Preload Script

Runs at container startup (before uvicorn) to index the bundled medical papers.
Idempotent: papers already in ChromaDB are skipped (uses document_exists check).

Expected runtime on first boot: ~10-12 minutes (8 PDFs through ADE + embeddings).
Subsequent boots: ~2 seconds (all papers already indexed in the mounted volume).
"""

import os
import sys
import uuid
import time
import shutil
from pathlib import Path

# Make execution modules importable from this script's location
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from execution.ade_client import parse_document, init_client as init_ade_client
from execution.embedding_client import embed_texts, init_openai_client
from execution.chroma_store import add_chunks, document_exists

PRELOAD_ENABLED = os.getenv("PRELOAD_ENABLED", "true").lower() == "true"
DATA_DIR = Path(__file__).parent.parent / "data" / "medical"
UPLOADED_PDFS_DIR = Path(os.getenv("UPLOADED_PDFS_DIR", "/app/uploaded_pdfs"))

UPLOADED_PDFS_DIR.mkdir(parents=True, exist_ok=True)


def log(msg: str):
    print(f"[PRELOAD] {msg}", flush=True)


def ingest_pdf(pdf_path: Path, index: int, total: int) -> bool:
    """
    Ingest a single PDF into ChromaDB.
    Returns True on success, False on failure.
    """
    doc_name = pdf_path.name
    log(f"Ingesting paper {index}/{total}: {doc_name}")

    start = time.time()

    # Step 1: Parse with ADE
    parse_result = parse_document(str(pdf_path))
    if not parse_result["success"]:
        log(f"  ERROR parsing {doc_name}: {parse_result['error']}")
        return False

    chunks = parse_result["chunks"]
    non_empty = [c for c in chunks if c.get("text", "").strip()]
    log(
        f"  Parsed: {parse_result['total_pages']} pages, "
        f"{len(non_empty)} non-empty chunks "
        f"(took {parse_result['duration_ms']}ms)"
    )

    if not non_empty:
        log(f"  WARNING: No text content found in {doc_name}, skipping.")
        return False

    # Step 2: Embed
    texts = [c["text"] for c in non_empty]
    embeddings = embed_texts(texts)

    # Step 3: Generate doc_id and store
    doc_id = str(uuid.uuid4())
    store_result = add_chunks(non_empty, embeddings, doc_id, doc_name)

    # Step 4: Copy PDF to UPLOADED_PDFS_DIR so image_client can find it later
    dest_pdf = UPLOADED_PDFS_DIR / f"{doc_id}.pdf"
    shutil.copy2(str(pdf_path), str(dest_pdf))

    elapsed = int((time.time() - start) * 1000)
    log(
        f"  Done: {store_result['added']} chunks indexed "
        f"(skipped {store_result['skipped']}), took {elapsed}ms total"
    )
    return True


def main():
    if not PRELOAD_ENABLED:
        log("PRELOAD_ENABLED=false — skipping.")
        return

    log("Starting pre-load of medical research papers...")

    # Validate API keys before starting
    if init_ade_client() is None:
        log("ERROR: VISION_AGENT_API_KEY not configured. Cannot parse PDFs.")
        return
    if init_openai_client() is None:
        log("ERROR: OPENAI_API_KEY not configured. Cannot embed chunks.")
        return

    pdf_files = sorted(DATA_DIR.glob("*.pdf"))
    if not pdf_files:
        log(f"No PDFs found in {DATA_DIR}. Nothing to pre-load.")
        return

    total = len(pdf_files)
    log(f"Found {total} papers to check.")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        if document_exists(pdf_path.name):
            log(f"Skipping {i}/{total}: {pdf_path.name} (already indexed)")
            skip_count += 1
            continue

        ok = ingest_pdf(pdf_path, i, total)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    log(
        f"Pre-load complete: {success_count} ingested, "
        f"{skip_count} skipped (already done), {fail_count} failed."
    )


if __name__ == "__main__":
    main()
