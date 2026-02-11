"""
Document Parser Orchestration

Layer 2 (Orchestration) - intelligent routing and decision-making.
Receives document uploads, calls ADE execution layer, returns structured results.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
import tempfile

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel
from dotenv import load_dotenv

# Add parent directory to path to import execution module
sys.path.append(str(Path(__file__).parent.parent))
from execution.ade_client import init_client, parse_document, extract_fields

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Demo ADE Parse - Document Parser & Extractor",
    description="Upload documents for parsing and structured field extraction using LandingAI ADE",
    version="1.0.0"
)

# CORS configuration
ALLOWED_ORIGINS = [
    "https://miagentuca.es",
    "https://www.miagentuca.es",
    "https://ade-parse.miagentuca.es",
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


# Rate limiting
RATE_LIMIT = os.getenv("RATE_LIMIT", "3/minute;20/day")
limiter = Limiter(key_func=get_real_ip)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configuration
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 5))
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
        "service": "demo-ade-parse",
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


# Response models
class ParseResponse(BaseModel):
    success: bool
    parsing: Optional[dict] = None
    extraction: Optional[dict] = None
    error: Optional[str] = None


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Demo ADE Parse - Document Parser & Extractor",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "parse": "/parse (POST)",
            "health": "/health (GET)"
        }
    }


@app.get("/health")
async def health_check():
    """Detailed health check."""
    ade_client = init_client()
    return {
        "status": "healthy",
        "ade_configured": ade_client is not None,
        "max_file_size_mb": MAX_FILE_SIZE_MB,
        "rate_limit": RATE_LIMIT
    }


@app.post("/parse", response_model=ParseResponse)
@limiter.limit(RATE_LIMIT)
async def parse_and_extract(
    request: Request,
    file: UploadFile = File(...),
    schema: Optional[str] = Form(None),
):
    """
    Parse an uploaded document and optionally extract fields.

    - **file**: Document to parse (PDF, images, Word, PowerPoint, Excel, CSV)
    - **schema**: Optional JSON schema for field extraction
    """
    # Validate file extension
    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file_ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    temp_file_path = None

    try:
        # Read and validate file size
        contents = await file.read()
        file_size_mb = len(contents) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum size of {MAX_FILE_SIZE_MB}MB (actual: {file_size_mb:.2f}MB)"
            )

        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            temp_file.write(contents)
            temp_file_path = temp_file.name

        # Step 1: Parse document
        parse_result = parse_document(temp_file_path)

        if not parse_result["success"]:
            log_request(request, endpoint="/parse", query=file.filename or "", result={
                "success": False,
                "error": parse_result["error"],
            })
            return ParseResponse(
                success=False,
                error=parse_result["error"]
            )

        parsing_data = {
            "markdown": parse_result["markdown"],
            "total_pages": parse_result["total_pages"],
            "total_chunks": parse_result["total_chunks"],
            "chunk_summary": parse_result["chunk_summary"],
            "duration_ms": parse_result["duration_ms"],
        }

        # Step 2: Extract fields if schema provided
        extraction_data = None
        if schema:
            extract_result = extract_fields(
                markdown=parse_result["markdown"],
                schema_json=schema
            )

            if not extract_result["success"]:
                log_request(request, endpoint="/parse", query=file.filename or "", result={
                    "success": False,
                    "error": extract_result["error"],
                })
                return ParseResponse(
                    success=False,
                    parsing=parsing_data,
                    error=extract_result["error"]
                )

            extraction_data = {
                "fields": extract_result["fields"],
                "metadata": extract_result["metadata"],
            }

        log_request(request, endpoint="/parse", query=file.filename or "", result={
            "success": True,
            "file_size_mb": round(file_size_mb, 2),
            "total_pages": parse_result["total_pages"],
            "total_chunks": parse_result["total_chunks"],
            "extraction_requested": schema is not None,
        })

        return ParseResponse(
            success=True,
            parsing=parsing_data,
            extraction=extraction_data,
        )

    except HTTPException:
        raise

    except Exception as e:
        log_request(request, endpoint="/parse", query=file.filename or "", result={
            "success": False,
            "error": f"Unexpected error: {str(e)}",
        })
        return ParseResponse(
            success=False,
            error=f"Unexpected error: {str(e)}"
        )

    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8004))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "False").lower() == "true"

    print(f"\nStarting Demo ADE Parse - Document Parser & Extractor")
    print(f"   URL: http://{host}:{port}")
    print(f"   Docs: http://{host}:{port}/docs")
    print(f"   Rate limit: {RATE_LIMIT}")
    print(f"   Max file size: {MAX_FILE_SIZE_MB}MB\n")

    uvicorn.run(
        "parse_endpoint:app",
        host=host,
        port=port,
        reload=debug
    )
