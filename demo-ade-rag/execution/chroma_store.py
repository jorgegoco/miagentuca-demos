"""
ChromaDB Store - Execution Layer

Deterministic wrapper around ChromaDB for vector storage and retrieval.
Handles collection management, chunk storage, similarity queries,
and document metadata persistence.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone

import chromadb


CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "/app/chroma_data")
COLLECTION_NAME = "ade_documents"
DOC_META_FILENAME = "doc_meta.json"


def _get_client() -> chromadb.PersistentClient:
    """Get or create the ChromaDB persistent client."""
    return chromadb.PersistentClient(path=CHROMA_DB_PATH)


def init_collection() -> chromadb.Collection:
    """Initialize or get the ChromaDB collection."""
    client = _get_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def clear_collection():
    """Delete and recreate the collection (for new document uploads)."""
    client = _get_client()
    try:
        client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        pass
    client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def add_chunks(chunks: List[Dict], embeddings: List[List[float]]) -> Dict:
    """
    Add chunks with their embeddings to the ChromaDB collection.

    Args:
        chunks: List of chunk dicts with keys: chunk_id, chunk_type, text, bbox, page.
        embeddings: Corresponding embedding vectors.

    Returns:
        Dict with: added (count), skipped (count).
    """
    collection = init_collection()
    added = 0
    skipped = 0

    for chunk, embedding in zip(chunks, embeddings):
        text = chunk.get("text", "")
        if not text or not text.strip():
            skipped += 1
            continue

        metadata = {
            "chunk_type": chunk.get("chunk_type", "unknown"),
            "page": chunk.get("page", 0),
        }

        bbox = chunk.get("bbox")
        if bbox and len(bbox) == 4:
            metadata["bbox_x0"] = float(bbox[0])
            metadata["bbox_y0"] = float(bbox[1])
            metadata["bbox_x1"] = float(bbox[2])
            metadata["bbox_y1"] = float(bbox[3])

        collection.add(
            documents=[text],
            ids=[chunk["chunk_id"]],
            metadatas=[metadata],
            embeddings=[embedding],
        )
        added += 1

    return {"added": added, "skipped": skipped}


def query_similar(
    query_embedding: List[float],
    top_k: int = 3,
    threshold: float = 0.25,
    where: Optional[Dict] = None,
) -> List[Dict]:
    """
    Query ChromaDB for chunks similar to the query embedding.

    Args:
        query_embedding: The query vector (1536-dim).
        top_k: Maximum number of results.
        threshold: Minimum similarity score (1 - L2 distance).
        where: Optional metadata filter (e.g. {"chunk_type": "chunkTable"}).

    Returns:
        List of result dicts with: chunk_id, chunk_type, page, similarity,
        text, bbox (dict with x0/y0/x1/y1).
    """
    collection = init_collection()

    query_params = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        query_params["where"] = where

    results = collection.query(**query_params)

    parsed = []
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]
    ids = results["ids"][0]

    for text, meta, dist, chunk_id in zip(docs, metas, dists, ids):
        similarity = 1 - dist
        if similarity < threshold:
            continue

        bbox = None
        if all(k in meta for k in ("bbox_x0", "bbox_y0", "bbox_x1", "bbox_y1")):
            bbox = {
                "x0": meta["bbox_x0"],
                "y0": meta["bbox_y0"],
                "x1": meta["bbox_x1"],
                "y1": meta["bbox_y1"],
            }

        parsed.append({
            "chunk_id": chunk_id,
            "chunk_type": meta.get("chunk_type", "unknown"),
            "page": meta.get("page", 0),
            "similarity": round(similarity, 4),
            "text": text,
            "bbox": bbox,
        })

    return parsed


def get_collection_count() -> int:
    """Return the number of chunks in the collection."""
    try:
        collection = init_collection()
        return collection.count()
    except Exception:
        return 0


def save_doc_metadata(name: str, total_pages: int, total_chunks: int,
                      chunk_summary: Dict):
    """Save metadata about the currently indexed document."""
    meta_path = Path(CHROMA_DB_PATH) / DOC_META_FILENAME
    meta = {
        "document_name": name,
        "total_pages": total_pages,
        "total_chunks": total_chunks,
        "chunk_summary": chunk_summary,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }
    meta_path.write_text(json.dumps(meta, indent=2))


def load_doc_metadata() -> Optional[Dict]:
    """Load metadata about the currently indexed document. Returns None if none."""
    meta_path = Path(CHROMA_DB_PATH) / DOC_META_FILENAME
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text())
    except Exception:
        return None


def clear_doc_metadata():
    """Remove the document metadata file."""
    meta_path = Path(CHROMA_DB_PATH) / DOC_META_FILENAME
    if meta_path.exists():
        meta_path.unlink()
