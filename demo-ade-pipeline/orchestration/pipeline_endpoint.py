"""
Loan Application Pipeline Orchestration

Layer 2 (Orchestration) - intelligent routing and decision-making.
Receives multiple document uploads, classifies each, extracts type-specific
fields, validates across documents, and returns comprehensive results.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone
import tempfile

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Add parent directory to path to import execution modules
sys.path.append(str(Path(__file__).parent.parent))
from execution.ade_client import init_client, parse_document, extract_fields
from execution.document_schemas import SCHEMA_PER_DOC_TYPE
from execution.validation_logic import run_all_validations, build_summary_table

# For converting Pydantic schemas to JSON
from landingai_ade.lib import pydantic_to_json_schema

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Demo ADE Pipeline - Loan Application Processor",
    description="Upload multiple financial documents for automatic classification, extraction, and validation",
    version="1.0.0"
)

# CORS configuration
# localhost origins are for demo/experimentation frontends only.
# Production frontends would use dedicated origins.
ALLOWED_ORIGINS = [
    "https://miagentuca.es",
    "https://www.miagentuca.es",
    "https://ade-pipeline.miagentuca.es",
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
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 5))
MAX_FILES = int(os.getenv("MAX_FILES", 10))
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

# DocType categorization schema (flat JSON, ADE doesn't support allOf/$ref)
DOC_TYPE_JSON_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": ["ID", "W2", "pay_stub", "bank_statement", "investment_statement"],
            "description": "The type of document being analyzed.",
            "title": "Document Type"
        }
    },
    "required": ["type"]
})

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
        "service": "demo-ade-pipeline",
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
class PipelineResponse(BaseModel):
    success: bool
    documents_processed: Optional[int] = None
    documents: Optional[list] = None
    validation: Optional[dict] = None
    summary_table: Optional[list] = None
    error: Optional[str] = None


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Demo ADE Pipeline - Loan Application Processor",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "process": "/process (POST)",
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
        "max_files": MAX_FILES,
    }


@app.post("/process", response_model=PipelineResponse)
async def process_loan_documents(
    request: Request,
    files: List[UploadFile] = File(...),
):
    """
    Process multiple loan application documents.

    Upload financial documents (PDF/images) with arbitrary filenames.
    The pipeline will classify each, extract relevant fields, and validate
    consistency across all documents.

    Supported document types: Government ID, W2, Pay Stub,
    Bank Statement, Investment Statement.
    """
    # Validate file count
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum {MAX_FILES} files allowed (received {len(files)})"
        )

    if len(files) == 0:
        raise HTTPException(
            status_code=400,
            detail="No files provided"
        )

    temp_file_paths = []
    processed_documents = []

    try:
        # Step 1: Validate and save all files
        file_info = []
        for upload_file in files:
            file_ext = Path(upload_file.filename or "").suffix.lower()
            if file_ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type '{file_ext}' for file '{upload_file.filename}'. "
                           f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
                )

            contents = await upload_file.read()
            file_size_mb = len(contents) / (1024 * 1024)
            if file_size_mb > MAX_FILE_SIZE_MB:
                raise HTTPException(
                    status_code=413,
                    detail=f"File '{upload_file.filename}' exceeds maximum size of "
                           f"{MAX_FILE_SIZE_MB}MB (actual: {file_size_mb:.2f}MB)"
                )

            # Save to temp file
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=file_ext
            ) as temp_file:
                temp_file.write(contents)
                temp_file_paths.append(temp_file.name)
                file_info.append({
                    "filename": upload_file.filename or f"file_{len(file_info)}",
                    "temp_path": temp_file.name,
                    "size_mb": round(file_size_mb, 2),
                })

        # Step 2: Parse and categorize each document
        for info in file_info:
            doc_result = {
                "filename": info["filename"],
                "document_type": None,
                "extracted_data": {},
                "metadata": {},
                "error": None,
            }

            # Parse the document
            parse_result = parse_document(
                info["temp_path"], split="page"
            )

            if not parse_result["success"]:
                doc_result["error"] = parse_result["error"]
                processed_documents.append(doc_result)
                continue

            # Categorize using first page markdown
            first_page_markdown = parse_result["splits_markdown"][0] \
                if parse_result["splits_markdown"] else parse_result["markdown"]

            cat_result = extract_fields(
                markdown=first_page_markdown,
                schema_json=DOC_TYPE_JSON_SCHEMA
            )

            if not cat_result["success"]:
                doc_result["error"] = f"Categorization failed: {cat_result['error']}"
                processed_documents.append(doc_result)
                continue

            doc_type = cat_result["fields"].get("type", "unknown")
            doc_result["document_type"] = doc_type

            # Step 3: Extract type-specific fields
            if doc_type in SCHEMA_PER_DOC_TYPE:
                schema_class = SCHEMA_PER_DOC_TYPE[doc_type]
                type_schema_json = pydantic_to_json_schema(schema_class)

                ext_result = extract_fields(
                    markdown=parse_result["markdown"],
                    schema_json=type_schema_json
                )

                if ext_result["success"]:
                    doc_result["extracted_data"] = ext_result["fields"]
                    doc_result["metadata"] = ext_result["metadata"]
                else:
                    doc_result["error"] = f"Extraction failed: {ext_result['error']}"
            else:
                doc_result["error"] = f"Unknown document type: {doc_type}"

            processed_documents.append(doc_result)

        # Step 4: Run validation checks
        validation_results = run_all_validations(processed_documents)
        summary_table = build_summary_table(processed_documents)

        # Build filenames list for logging
        filenames = [info["filename"] for info in file_info]

        log_request(request, endpoint="/process",
                    query=json.dumps(filenames), result={
            "success": True,
            "file_count": len(files),
            "documents_processed": len(processed_documents),
            "doc_types": [d["document_type"] for d in processed_documents],
            "name_match_passed": validation_results["name_match"]["passed"],
        })

        return PipelineResponse(
            success=True,
            documents_processed=len(processed_documents),
            documents=processed_documents,
            validation=validation_results,
            summary_table=summary_table,
        )

    except HTTPException:
        raise

    except Exception as e:
        log_request(request, endpoint="/process", query="", result={
            "success": False,
            "error": f"Unexpected error: {str(e)}",
        })
        return PipelineResponse(
            success=False,
            error=f"Unexpected error: {str(e)}"
        )

    finally:
        # Clean up all temporary files
        for path in temp_file_paths:
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8005))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "False").lower() == "true"

    print(f"\nStarting Demo ADE Pipeline - Loan Application Processor")
    print(f"   URL: http://{host}:{port}")
    print(f"   Docs: http://{host}:{port}/docs")
    print(f"   Max file size: {MAX_FILE_SIZE_MB}MB")
    print(f"   Max files: {MAX_FILES}\n")

    uvicorn.run(
        "pipeline_endpoint:app",
        host=host,
        port=port,
        reload=debug
    )
