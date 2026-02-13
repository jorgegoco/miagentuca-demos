"""
RAG Endpoint Orchestration

Layer 2 (Orchestration) - intelligent routing and decision-making.
Receives document uploads for indexing and questions for RAG-based Q&A.
"""

import os
import sys
import json
import asyncio
import logging
import time
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
import tempfile

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Add parent directory to path to import execution module
sys.path.append(str(Path(__file__).parent.parent))
from execution.ade_client import init_client, parse_document
from execution.embedding_client import embed_text, embed_texts, init_openai_client
from execution.chroma_store import (
    clear_collection, add_chunks, query_similar,
    get_collection_count, save_doc_metadata, load_doc_metadata,
    clear_doc_metadata,
)
from execution.llm_client import generate_answer, init_anthropic_client

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Demo ADE RAG - Document Q&A with Retrieval Augmented Generation",
    description="Upload documents, index with embeddings, and ask questions answered by AI using retrieved context",
    version="1.0.0",
)

# CORS configuration
# localhost origins are for demo/experimentation frontends only.
# Production frontends would use dedicated origins.
ALLOWED_ORIGINS = [
    "https://miagentuca.es",
    "https://www.miagentuca.es",
    "https://ade-rag.miagentuca.es",
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


def get_real_ip(request: Request) -> str:
    """Extract real client IP behind reverse proxy (Traefik/Nginx)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "127.0.0.1"


# Configuration
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 10))
ALLOWED_EXTENSIONS = {
    # PDFs
    ".pdf",
    # Images
    ".jpeg", ".jpg", ".png", ".apng", ".bmp", ".dcx", ".dds", ".dib",
    ".gd", ".gif", ".icns", ".jp2", ".pcx", ".ppm", ".psd", ".tga",
    ".tif", ".tiff", ".webp",
    # Text documents
    ".doc", ".docx", ".odt",
    # Presentations
    ".odp", ".ppt", ".pptx",
    # Spreadsheets
    ".csv", ".xlsx",
}

# Concurrency guard for ingest (ChromaDB PersistentClient is single-process)
_ingest_lock = asyncio.Lock()

# Structured request logger
request_logger = logging.getLogger("request_log")
request_logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))
request_logger.addHandler(_handler)
request_logger.propagate = False


def log_request(request: Request, *, endpoint: str, query: str, result: dict):
    """Log structured request data for analytics (stdout -> Docker/Easypanel)."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "demo-ade-rag",
        "endpoint": endpoint,
        "method": request.method,
        "ip": get_real_ip(request),
        "ip_chain": request.headers.get("X-Forwarded-For", ""),
        "user_agent": request.headers.get("User-Agent", ""),
        "referer": request.headers.get("Referer", ""),
        "origin": request.headers.get("Origin", ""),
        "accept_language": request.headers.get("Accept-Language", ""),
        "query": query,
        **result,
    }
    request_logger.info("[REQUEST_LOG] " + json.dumps(entry, ensure_ascii=False))


# --- Request/Response models ---

class QueryRequest(BaseModel):
    question: str
    top_k: int = 3
    threshold: float = 0.25
    chunk_type_filter: Optional[str] = None


class SourceInfo(BaseModel):
    chunk_id: str
    chunk_type: str
    page: int
    similarity: float
    text_preview: str
    bbox: Optional[dict] = None


class QueryResponse(BaseModel):
    success: bool
    question: Optional[str] = None
    answer: Optional[str] = None
    sources: Optional[list] = None
    retrieval_info: Optional[dict] = None
    error: Optional[str] = None


class IngestResponse(BaseModel):
    success: bool
    document_name: Optional[str] = None
    parsing: Optional[dict] = None
    indexing: Optional[dict] = None
    error: Optional[str] = None


# --- Endpoints ---

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Demo ADE RAG - Document Q&A with Retrieval Augmented Generation",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "ingest": "/ingest (POST)",
            "query": "/query (POST)",
            "status": "/status (GET)",
            "health": "/health (GET)",
        },
    }


@app.get("/health")
async def health_check():
    """Detailed health check."""
    ade_client = init_client()
    openai_client = init_openai_client()
    anthropic_client = init_anthropic_client()
    doc_meta = load_doc_metadata()

    return {
        "status": "healthy",
        "ade_configured": ade_client is not None,
        "openai_configured": openai_client is not None,
        "anthropic_configured": anthropic_client is not None,
        "chroma_collection_count": get_collection_count(),
        "document_loaded": doc_meta is not None,
        "document_name": doc_meta["document_name"] if doc_meta else None,
        "max_file_size_mb": MAX_FILE_SIZE_MB,
    }


@app.get("/status")
async def document_status():
    """Return information about the currently indexed document."""
    doc_meta = load_doc_metadata()
    if doc_meta is None:
        return {
            "document_loaded": False,
            "document_name": None,
            "total_chunks": 0,
        }

    return {
        "document_loaded": True,
        "document_name": doc_meta.get("document_name"),
        "total_chunks": doc_meta.get("total_chunks", 0),
        "chunk_summary": doc_meta.get("chunk_summary", {}),
        "total_pages": doc_meta.get("total_pages", 0),
        "indexed_at": doc_meta.get("indexed_at"),
    }


@app.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    request: Request,
    file: UploadFile = File(...),
):
    """
    Upload and index a document for RAG queries.

    Parses the document with ADE, embeds all chunks with OpenAI,
    and stores them in ChromaDB. Replaces any previously indexed document.

    - **file**: Document to index (PDF, images, Word, PowerPoint, Excel, CSV)
    """
    # Validate file extension
    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file_ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    temp_file_path = None

    try:
        # Read and validate file size
        contents = await file.read()
        file_size_mb = len(contents) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum size of {MAX_FILE_SIZE_MB}MB (actual: {file_size_mb:.2f}MB)",
            )

        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            temp_file.write(contents)
            temp_file_path = temp_file.name

        # Acquire ingest lock to prevent concurrent indexing
        async with _ingest_lock:
            # Step 1: Parse document with ADE
            parse_result = parse_document(temp_file_path)

            if not parse_result["success"]:
                log_request(request, endpoint="/ingest", query=file.filename or "", result={
                    "success": False,
                    "error": parse_result["error"],
                })
                return IngestResponse(
                    success=False,
                    error=parse_result["error"],
                )

            chunks = parse_result["chunks"]
            parsing_data = {
                "total_pages": parse_result["total_pages"],
                "total_chunks": parse_result["total_chunks"],
                "chunk_summary": parse_result["chunk_summary"],
                "parse_duration_ms": parse_result["duration_ms"],
            }

            # Step 2: Filter out empty chunks before embedding
            non_empty_chunks = [
                c for c in chunks
                if c.get("text") and c["text"].strip()
            ]
            skipped = len(chunks) - len(non_empty_chunks)

            if not non_empty_chunks:
                log_request(request, endpoint="/ingest", query=file.filename or "", result={
                    "success": False,
                    "error": "No text content found in document",
                })
                return IngestResponse(
                    success=False,
                    parsing=parsing_data,
                    error="No text content found in document after parsing.",
                )

            # Step 3: Embed all chunk texts
            embed_start = time.time()
            texts = [c["text"] for c in non_empty_chunks]
            embeddings = embed_texts(texts)
            embed_duration_ms = int((time.time() - embed_start) * 1000)

            # Step 4: Clear old data and store new chunks
            clear_collection()
            clear_doc_metadata()
            store_result = add_chunks(non_empty_chunks, embeddings)

            # Step 5: Save document metadata
            save_doc_metadata(
                name=file.filename or "unknown",
                total_pages=parse_result["total_pages"],
                total_chunks=store_result["added"],
                chunk_summary=parse_result["chunk_summary"],
            )

            indexing_data = {
                "chunks_embedded": store_result["added"],
                "chunks_skipped": skipped + store_result["skipped"],
                "embedding_duration_ms": embed_duration_ms,
            }

        log_request(request, endpoint="/ingest", query=file.filename or "", result={
            "success": True,
            "file_size_mb": round(file_size_mb, 2),
            "total_pages": parse_result["total_pages"],
            "total_chunks": parse_result["total_chunks"],
            "chunks_embedded": store_result["added"],
        })

        return IngestResponse(
            success=True,
            document_name=file.filename,
            parsing=parsing_data,
            indexing=indexing_data,
        )

    except HTTPException:
        raise

    except Exception as e:
        log_request(request, endpoint="/ingest", query=file.filename or "", result={
            "success": False,
            "error": f"Unexpected error: {str(e)}",
        })
        return IngestResponse(
            success=False,
            error=f"Unexpected error: {str(e)}",
        )

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass


@app.post("/query", response_model=QueryResponse)
async def query_document(
    request: Request,
    body: QueryRequest,
):
    """
    Ask a question about the indexed document.

    Retrieves relevant chunks via semantic search and generates
    a grounded answer using Claude.

    - **question**: Natural language question
    - **top_k**: Maximum chunks to retrieve (default 3)
    - **threshold**: Minimum similarity score 0-1 (default 0.25)
    - **chunk_type_filter**: Optional filter by chunk type (e.g. "chunkTable")
    """
    try:
        # Check that a document is loaded
        doc_meta = load_doc_metadata()
        if doc_meta is None or get_collection_count() == 0:
            raise HTTPException(
                status_code=400,
                detail="No document indexed. Please upload a document first via /ingest.",
            )

        if not body.question or not body.question.strip():
            raise HTTPException(
                status_code=400,
                detail="Question cannot be empty.",
            )

        # Step 1: Embed the question
        question_embedding = embed_text(body.question)

        # Step 2: Query ChromaDB
        where_filter = None
        if body.chunk_type_filter:
            where_filter = {"chunk_type": body.chunk_type_filter}

        similar_chunks = query_similar(
            query_embedding=question_embedding,
            top_k=body.top_k,
            threshold=body.threshold,
            where=where_filter,
        )

        # Step 3: Generate answer with Claude
        llm_result = generate_answer(body.question, similar_chunks)

        if not llm_result["success"]:
            log_request(request, endpoint="/query", query=body.question, result={
                "success": False,
                "error": llm_result["error"],
            })
            return QueryResponse(
                success=False,
                question=body.question,
                error=llm_result["error"],
            )

        # Step 4: Build response with sources
        sources = []
        for chunk in similar_chunks:
            text = chunk.get("text", "")
            sources.append({
                "chunk_id": chunk["chunk_id"],
                "chunk_type": chunk["chunk_type"],
                "page": chunk["page"],
                "similarity": chunk["similarity"],
                "text_preview": text[:200] + "..." if len(text) > 200 else text,
                "bbox": chunk.get("bbox"),
            })

        log_request(request, endpoint="/query", query=body.question, result={
            "success": True,
            "chunks_returned": len(sources),
            "chunk_type_filter": body.chunk_type_filter,
        })

        return QueryResponse(
            success=True,
            question=body.question,
            answer=llm_result["answer"],
            sources=sources,
            retrieval_info={
                "chunks_searched": get_collection_count(),
                "chunks_returned": len(sources),
                "top_k": body.top_k,
                "threshold": body.threshold,
                "chunk_type_filter": body.chunk_type_filter,
            },
        )

    except HTTPException:
        raise

    except Exception as e:
        log_request(request, endpoint="/query", query=body.question, result={
            "success": False,
            "error": f"Unexpected error: {str(e)}",
        })
        return QueryResponse(
            success=False,
            question=body.question,
            error=f"Unexpected error: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8006))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "False").lower() == "true"

    print(f"\nStarting Demo ADE RAG - Document Q&A")
    print(f"   URL: http://{host}:{port}")
    print(f"   Docs: http://{host}:{port}/docs")
    print(f"   Max file size: {MAX_FILE_SIZE_MB}MB\n")

    uvicorn.run(
        "rag_endpoint:app",
        host=host,
        port=port,
        reload=debug,
    )
