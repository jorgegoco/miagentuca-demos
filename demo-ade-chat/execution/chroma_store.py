"""
ChromaDB Store - Execution Layer

Multi-document vector store for the research chatbot.
Unlike the single-document RAG demo, this store is additive:
documents are never cleared on ingest — each chunk carries doc_id metadata
so documents can be listed, filtered, and deleted independently.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone

import chromadb


CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "/app/chroma_data")
COLLECTION_NAME = "chatbot_documents"
DOCS_INDEX_FILENAME = "docs_index.json"


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


# ---------------------------------------------------------------------------
# Document index (JSON sidecar file — tracks per-document metadata)
# ---------------------------------------------------------------------------

def _load_docs_index() -> Dict:
    """Load the document index from disk. Returns empty dict if not found."""
    index_path = Path(CHROMA_DB_PATH) / DOCS_INDEX_FILENAME
    if not index_path.exists():
        return {}
    try:
        return json.loads(index_path.read_text())
    except Exception:
        return {}


def _save_docs_index(index: Dict):
    """Persist the document index to disk."""
    index_path = Path(CHROMA_DB_PATH) / DOCS_INDEX_FILENAME
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=2))


def document_exists(doc_name: str) -> bool:
    """Check whether a document (by filename) is already indexed."""
    index = _load_docs_index()
    return any(v["doc_name"] == doc_name for v in index.values())


def get_doc_id_by_name(doc_name: str) -> Optional[str]:
    """Return the doc_id for a given filename, or None if not found."""
    index = _load_docs_index()
    for doc_id, meta in index.items():
        if meta["doc_name"] == doc_name:
            return doc_id
    return None


def list_documents() -> List[Dict]:
    """
    List all indexed documents with their metadata.

    Returns:
        List of dicts with: doc_id, doc_name, chunk_count, chunk_summary, indexed_at.
    """
    index = _load_docs_index()
    return list(index.values())


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def add_chunks(
    chunks: List[Dict],
    embeddings: List[List[float]],
    doc_id: str,
    doc_name: str,
) -> Dict:
    """
    Add chunks for one document into ChromaDB.

    Args:
        chunks: List of chunk dicts with keys: chunk_id, chunk_type, text, bbox, page.
        embeddings: Corresponding embedding vectors.
        doc_id: UUID for this document (used to filter/delete later).
        doc_name: Human-readable filename.

    Returns:
        Dict with: added (count), skipped (count).
    """
    collection = init_collection()
    added = 0
    skipped = 0
    chunk_summary: Dict[str, int] = {}

    for chunk, embedding in zip(chunks, embeddings):
        text = chunk.get("text", "")
        if not text or not text.strip():
            skipped += 1
            continue

        chunk_type = chunk.get("chunk_type", "unknown")
        chunk_summary[chunk_type] = chunk_summary.get(chunk_type, 0) + 1

        metadata: Dict = {
            "doc_id": doc_id,
            "doc_name": doc_name,
            "chunk_type": chunk_type,
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

    # Update the document index
    index = _load_docs_index()
    index[doc_id] = {
        "doc_id": doc_id,
        "doc_name": doc_name,
        "chunk_count": added,
        "chunk_summary": chunk_summary,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_docs_index(index)

    return {"added": added, "skipped": skipped}


def delete_document(doc_id: str) -> Dict:
    """
    Remove all chunks for a given document from ChromaDB and the index.

    Args:
        doc_id: The document UUID to remove.

    Returns:
        Dict with: deleted (count), error (str or None).
    """
    try:
        collection = init_collection()

        # Find all chunk IDs for this doc
        results = collection.get(
            where={"doc_id": doc_id},
            include=["metadatas"],
        )
        chunk_ids = results.get("ids", [])

        if chunk_ids:
            collection.delete(ids=chunk_ids)

        # Remove from index
        index = _load_docs_index()
        index.pop(doc_id, None)
        _save_docs_index(index)

        return {"deleted": len(chunk_ids), "error": None}

    except Exception as e:
        return {"deleted": 0, "error": str(e)}


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def query_similar(
    query_embedding: List[float],
    top_k: int = 5,
    threshold: float = 0.25,
    doc_id_filter: Optional[str] = None,
    chunk_type_filter: Optional[str] = None,
) -> List[Dict]:
    """
    Query ChromaDB for chunks similar to the query embedding.

    Args:
        query_embedding: The query vector (1536-dim).
        top_k: Maximum number of results to return.
        threshold: Minimum similarity score (0–1).
        doc_id_filter: If set, restrict search to chunks from this document.
        chunk_type_filter: If set, restrict to a specific chunk type (e.g. "chunkTable").

    Returns:
        List of result dicts: chunk_id, doc_id, doc_name, chunk_type, page,
        similarity, text, bbox (dict or None).
    """
    collection = init_collection()

    # Build where clause
    where: Optional[Dict] = None
    filters = []
    if doc_id_filter:
        filters.append({"doc_id": {"$eq": doc_id_filter}})
    if chunk_type_filter:
        filters.append({"chunk_type": {"$eq": chunk_type_filter}})

    if len(filters) == 1:
        where = filters[0]
    elif len(filters) > 1:
        where = {"$and": filters}

    query_params: Dict = {
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
            "doc_id": meta.get("doc_id", ""),
            "doc_name": meta.get("doc_name", ""),
            "chunk_type": meta.get("chunk_type", "unknown"),
            "page": meta.get("page", 0),
            "similarity": round(similarity, 4),
            "text": text,
            "bbox": bbox,
        })

    return parsed


def get_collection_count() -> int:
    """Return the total number of chunks across all documents."""
    try:
        collection = init_collection()
        return collection.count()
    except Exception:
        return 0
