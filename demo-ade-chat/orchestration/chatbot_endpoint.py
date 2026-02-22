"""
Chatbot Endpoint - Orchestration Layer

Layer 2 (Orchestration) — intelligent routing and decision-making.
Coordinates the full pipeline: ingest, multi-document ChromaDB,
Strands Agent chat with session memory, and visual grounding.
"""

import os
import sys
import json
import uuid
import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
import tempfile

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# Add parent directory to path so execution modules are importable
sys.path.append(str(Path(__file__).parent.parent))
from execution.ade_client import init_client as init_ade_client, parse_document
from execution.embedding_client import embed_texts, init_openai_client
from execution.chroma_store import (
    add_chunks,
    delete_document,
    document_exists,
    get_collection_count,
    list_documents,
)
from execution.agent_client import chat as agent_chat
from execution.image_client import get_chunk_image

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 20))
SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", 2))
UPLOADED_PDFS_DIR = os.getenv("UPLOADED_PDFS_DIR", "/app/uploaded_pdfs")
CHUNK_IMAGES_DIR = os.getenv("CHUNK_IMAGES_DIR", "/app/chunk_images")
PORT = int(os.getenv("PORT", 8007))

Path(UPLOADED_PDFS_DIR).mkdir(parents=True, exist_ok=True)
Path(CHUNK_IMAGES_DIR).mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Demo ADE Chat - Multi-Document Research Chatbot",
    description=(
        "Upload research papers, ask questions in multi-turn chat, "
        "get answers grounded in retrieved passages with visual source highlighting."
    ),
    version="1.0.0",
)

# Serve cropped chunk images as static files
app.mount(
    "/static/chunk-images",
    StaticFiles(directory=CHUNK_IMAGES_DIR),
    name="chunk_images",
)

# CORS configuration
# localhost origins are for demo/development frontends only.
ALLOWED_ORIGINS = [
    "https://miagentuca.es",
    "https://www.miagentuca.es",
    "https://ade-chat.miagentuca.es",
    "http://localhost:3000",
    "http://localhost:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

request_logger = logging.getLogger("request_log")
request_logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))
request_logger.addHandler(_handler)
request_logger.propagate = False


def get_real_ip(request: Request) -> str:
    """Extract real client IP behind Traefik reverse proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "127.0.0.1"


def log_request(request: Request, *, endpoint: str, query: str, result: dict):
    """Log structured request data for analytics (stdout → Docker/Easypanel)."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "demo-ade-chat",
        "endpoint": endpoint,
        "method": request.method,
        "ip": get_real_ip(request),
        "ip_chain": request.headers.get("X-Forwarded-For", ""),
        "user_agent": request.headers.get("User-Agent", ""),
        "origin": request.headers.get("Origin", ""),
        "query": query,
        **result,
    }
    request_logger.info("[REQUEST_LOG] " + json.dumps(entry, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Session store (in-memory, TTL-based)
# ---------------------------------------------------------------------------

# sessions[session_id] = {
#   "messages": [{"role": "user"|"assistant", "content": "..."}],
#   "created_at": datetime,
#   "last_active": datetime,
# }
_sessions: Dict[str, Dict] = {}
_SESSION_TTL = timedelta(hours=SESSION_TTL_HOURS)


def _prune_sessions():
    """Remove sessions older than TTL. Called on each /chat request."""
    now = datetime.now(timezone.utc)
    expired = [
        sid for sid, data in _sessions.items()
        if now - data["last_active"] > _SESSION_TTL
    ]
    for sid in expired:
        del _sessions[sid]


def _get_or_create_session(session_id: str) -> Dict:
    """Return existing session or create a new one."""
    now = datetime.now(timezone.utc)
    if session_id not in _sessions:
        _sessions[session_id] = {
            "messages": [],
            "created_at": now,
            "last_active": now,
        }
    return _sessions[session_id]


# ---------------------------------------------------------------------------
# Concurrency guard for ChromaDB writes
# ---------------------------------------------------------------------------

_ingest_lock = asyncio.Lock()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    session_id: str
    message: str
    doc_id_filter: Optional[str] = None
    top_k: int = 5
    threshold: float = 0.25


class SourceInfo(BaseModel):
    chunk_id: str
    doc_id: str
    doc_name: str
    chunk_type: str
    page: int
    similarity: float
    text_preview: str
    bbox: Optional[dict] = None
    chunk_image_url: Optional[str] = None


class ChatResponse(BaseModel):
    success: bool
    session_id: Optional[str] = None
    answer: Optional[str] = None
    sources: Optional[List[dict]] = None
    retrieval_info: Optional[dict] = None
    error: Optional[str] = None


class IngestResponse(BaseModel):
    success: bool
    doc_id: Optional[str] = None
    doc_name: Optional[str] = None
    already_indexed: bool = False
    parsing: Optional[dict] = None
    indexing: Optional[dict] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/")
async def root():
    return {
        "service": "Demo ADE Chat - Multi-Document Research Chatbot",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health (GET)",
            "status": "/status (GET)",
            "ingest": "/ingest (POST)",
            "documents": "/documents (GET)",
            "delete_doc": "/documents/{doc_id} (DELETE)",
            "chat": "/chat (POST)",
            "session": "/sessions/{session_id} (GET | DELETE)",
            "images": "/static/chunk-images/{filename} (GET)",
        },
    }


@app.get("/health")
async def health_check():
    """Detailed health check: API key status + collection size."""
    ade_ok = init_ade_client() is not None
    openai_ok = init_openai_client() is not None
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_ok = bool(anthropic_key and anthropic_key != "your_key_here")

    return {
        "status": "healthy",
        "ade_configured": ade_ok,
        "openai_configured": openai_ok,
        "anthropic_configured": anthropic_ok,
        "total_chunks": get_collection_count(),
        "total_documents": len(list_documents()),
        "active_sessions": len(_sessions),
        "max_file_size_mb": MAX_FILE_SIZE_MB,
    }


@app.get("/status")
async def library_status():
    """Library stats: document count, total chunks, per-document details."""
    docs = list_documents()
    return {
        "total_documents": len(docs),
        "total_chunks": get_collection_count(),
        "documents": docs,
    }


@app.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    request: Request,
    file: UploadFile = File(...),
):
    """
    Upload a PDF → parse with ADE → embed → store in ChromaDB.

    Idempotent: if the same filename is already indexed, returns immediately.
    The original PDF is kept in UPLOADED_PDFS_DIR for visual grounding.
    """
    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    doc_name = file.filename or "unknown.pdf"

    # Duplicate check
    if document_exists(doc_name):
        log_request(request, endpoint="/ingest", query=doc_name, result={
            "success": True, "already_indexed": True,
        })
        return IngestResponse(
            success=True,
            doc_name=doc_name,
            already_indexed=True,
        )

    contents = await file.read()
    file_size_mb = len(contents) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_FILE_SIZE_MB}MB limit (actual: {file_size_mb:.2f}MB).",
        )

    doc_id = str(uuid.uuid4())
    # Save the original PDF permanently (needed for image_client later)
    pdf_save_path = Path(UPLOADED_PDFS_DIR) / f"{doc_id}.pdf"
    pdf_save_path.write_bytes(contents)

    temp_file_path = None
    try:
        # Also write to a temp path for ADE parsing (avoids path issues)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(contents)
            temp_file_path = tmp.name

        async with _ingest_lock:
            # Step 1: Parse with ADE
            parse_result = parse_document(temp_file_path)
            if not parse_result["success"]:
                pdf_save_path.unlink(missing_ok=True)
                log_request(request, endpoint="/ingest", query=doc_name, result={
                    "success": False, "error": parse_result["error"],
                })
                return IngestResponse(success=False, error=parse_result["error"])

            chunks = parse_result["chunks"]
            parsing_data = {
                "total_pages": parse_result["total_pages"],
                "total_chunks": parse_result["total_chunks"],
                "chunk_summary": parse_result["chunk_summary"],
                "parse_duration_ms": parse_result["duration_ms"],
            }

            # Step 2: Filter empty chunks
            non_empty = [c for c in chunks if c.get("text", "").strip()]
            skipped_empty = len(chunks) - len(non_empty)

            if not non_empty:
                pdf_save_path.unlink(missing_ok=True)
                return IngestResponse(
                    success=False,
                    parsing=parsing_data,
                    error="No text content found in document after parsing.",
                )

            # Step 3: Embed
            embed_start = time.time()
            texts = [c["text"] for c in non_empty]
            embeddings = embed_texts(texts)
            embed_ms = int((time.time() - embed_start) * 1000)

            # Step 4: Store in ChromaDB with doc_id metadata
            store_result = add_chunks(non_empty, embeddings, doc_id, doc_name)

        indexing_data = {
            "chunks_embedded": store_result["added"],
            "chunks_skipped": skipped_empty + store_result["skipped"],
            "embedding_duration_ms": embed_ms,
        }

        log_request(request, endpoint="/ingest", query=doc_name, result={
            "success": True,
            "doc_id": doc_id,
            "total_pages": parse_result["total_pages"],
            "chunks_embedded": store_result["added"],
        })

        return IngestResponse(
            success=True,
            doc_id=doc_id,
            doc_name=doc_name,
            already_indexed=False,
            parsing=parsing_data,
            indexing=indexing_data,
        )

    except Exception as e:
        pdf_save_path.unlink(missing_ok=True)
        log_request(request, endpoint="/ingest", query=doc_name, result={
            "success": False, "error": str(e),
        })
        return IngestResponse(success=False, error=f"Unexpected error: {str(e)}")

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass


@app.get("/documents")
async def list_all_documents():
    """List all indexed documents with chunk counts and index timestamps."""
    return {
        "success": True,
        "documents": list_documents(),
        "total_documents": len(list_documents()),
        "total_chunks": get_collection_count(),
    }


@app.delete("/documents/{doc_id}")
async def remove_document(doc_id: str):
    """Remove all chunks for a document from ChromaDB."""
    async with _ingest_lock:
        result = delete_document(doc_id)

    # Also remove the stored PDF (best-effort)
    pdf_path = Path(UPLOADED_PDFS_DIR) / f"{doc_id}.pdf"
    pdf_path.unlink(missing_ok=True)

    if result["error"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return {
        "success": True,
        "doc_id": doc_id,
        "chunks_deleted": result["deleted"],
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: Request,
    body: ChatRequest,
):
    """
    Multi-turn chat with the research paper library.

    The Strands Agent decides when to search and what to search for.
    Retrieved chunks are returned with visual grounding image URLs.
    """
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    if not body.session_id or not body.session_id.strip():
        raise HTTPException(status_code=400, detail="session_id cannot be empty.")

    _prune_sessions()
    session = _get_or_create_session(body.session_id)

    # Append user message to history
    session["messages"].append({"role": "user", "content": body.message})
    session["last_active"] = datetime.now(timezone.utc)

    try:
        # Run the Strands agent (passes full conversation history)
        answer, retrieved_chunks = agent_chat(
            messages=session["messages"],
            doc_id_filter=body.doc_id_filter,
            top_k=body.top_k,
            threshold=body.threshold,
        )

        # Append assistant answer to history
        session["messages"].append({"role": "assistant", "content": answer})
        session["last_active"] = datetime.now(timezone.utc)

        # Build sources with visual grounding
        sources = []
        for chunk in retrieved_chunks:
            text = chunk.get("text", "")
            doc_id = chunk.get("doc_id", "")

            # Attempt to render and crop chunk image
            chunk_image_url = None
            pdf_path = str(Path(UPLOADED_PDFS_DIR) / f"{doc_id}.pdf")
            img_filename = get_chunk_image(
                pdf_path=pdf_path,
                page=chunk.get("page", 0),
                bbox=chunk.get("bbox"),
                chunk_id=chunk["chunk_id"],
            )
            if img_filename:
                chunk_image_url = f"/static/chunk-images/{img_filename}"

            sources.append({
                "chunk_id": chunk["chunk_id"],
                "doc_id": doc_id,
                "doc_name": chunk.get("doc_name", ""),
                "chunk_type": chunk.get("chunk_type", "unknown"),
                "page": chunk.get("page", 0),
                "similarity": chunk.get("similarity", 0.0),
                "text_preview": text[:250] + "..." if len(text) > 250 else text,
                "bbox": chunk.get("bbox"),
                "chunk_image_url": chunk_image_url,
            })

        log_request(request, endpoint="/chat", query=body.message[:100], result={
            "success": True,
            "session_id": body.session_id,
            "sources_returned": len(sources),
            "doc_id_filter": body.doc_id_filter,
        })

        return ChatResponse(
            success=True,
            session_id=body.session_id,
            answer=answer,
            sources=sources,
            retrieval_info={
                "chunks_searched": get_collection_count(),
                "chunks_returned": len(sources),
                "doc_id_filter": body.doc_id_filter,
                "top_k": body.top_k,
                "threshold": body.threshold,
            },
        )

    except Exception as e:
        # Remove the failed user message from history to keep state consistent
        if session["messages"] and session["messages"][-1]["role"] == "user":
            session["messages"].pop()

        log_request(request, endpoint="/chat", query=body.message[:100], result={
            "success": False, "error": str(e),
        })
        return ChatResponse(success=False, error=f"Chat failed: {str(e)}")


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Return the message history for a session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
    session = _sessions[session_id]
    return {
        "success": True,
        "session_id": session_id,
        "messages": session["messages"],
        "created_at": session["created_at"].isoformat(),
        "last_active": session["last_active"].isoformat(),
        "message_count": len(session["messages"]),
    }


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Clear a session's message history."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
    del _sessions[session_id]
    return {"success": True, "session_id": session_id}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "False").lower() == "true"

    print(f"\nStarting Demo ADE Chat - Research Chatbot")
    print(f"   URL: http://{host}:{PORT}")
    print(f"   Docs: http://{host}:{PORT}/docs")
    print(f"   Max file size: {MAX_FILE_SIZE_MB}MB\n")

    uvicorn.run(
        "chatbot_endpoint:app",
        host=host,
        port=PORT,
        reload=debug,
    )
