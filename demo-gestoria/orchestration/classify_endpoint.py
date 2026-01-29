"""
Document Classification Orchestration

This is Layer 2 (Orchestration) - intelligent routing and decision-making.
Reads directives, calls execution tools, interacts with Claude API.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
import tempfile
import time

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel
from dotenv import load_dotenv
import anthropic

# Add parent directory to path to import execution module
sys.path.append(str(Path(__file__).parent.parent))
from execution.pdf_parser import extract_text_from_pdf

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Demo Gestoría - Document Classifier",
    description="Upload PDF documents for automatic classification and data extraction",
    version="1.0.0"
)

# CORS configuration - restrict to actual domains
ALLOWED_ORIGINS = [
    "https://miagentuca.es",
    "https://www.miagentuca.es",
    "https://gestoria.miagentuca.es",
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


# Rate limiting - proxy-aware with daily cap
RATE_LIMIT = os.getenv("RATE_LIMIT", "3/minute;20/day")
limiter = Limiter(key_func=get_real_ip)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Initialize Anthropic client
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
if not anthropic_api_key or anthropic_api_key == "your_demo_key_here":
    print("⚠️  WARNING: ANTHROPIC_API_KEY not configured in .env file")
    anthropic_api_key = None

anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key) if anthropic_api_key else None

# Configuration
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 2))

# Structured request logger
request_logger = logging.getLogger("request_log")
request_logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))
request_logger.addHandler(_handler)
request_logger.propagate = False


def log_request(request: Request, *, endpoint: str, query: str, result: dict):
    """Log structured request data for analytics (stdout → Docker/Easypanel)."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "demo-gestoria",
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


class ClassificationResponse(BaseModel):
    """Response model for document classification"""
    success: bool
    document_type: Optional[str] = None
    confidence: Optional[int] = None
    extracted_data: Optional[dict] = None
    notes: Optional[str] = None
    error: Optional[str] = None


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Demo Gestoría - Document Classifier",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "classify": "/classify (POST)",
            "health": "/health (GET)"
        }
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "anthropic_configured": anthropic_client is not None,
        "max_file_size_mb": MAX_FILE_SIZE_MB,
        "rate_limit": RATE_LIMIT
    }


@app.post("/classify", response_model=ClassificationResponse)
@limiter.limit(RATE_LIMIT)
async def classify_document(request: Request, file: UploadFile = File(...)):
    """
    Classify an uploaded PDF document and extract relevant information.

    Follows the 3-layer architecture:
    1. Reads directive (directives/classify_document.md)
    2. Calls execution tool (execution/pdf_parser.py)
    3. Makes intelligent decision using Claude API
    4. Returns structured response
    """

    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )

    # Create temporary file
    temp_file = None

    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            contents = await file.read()

            # Check file size
            file_size_mb = len(contents) / (1024 * 1024)
            if file_size_mb > MAX_FILE_SIZE_MB:
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds maximum size of {MAX_FILE_SIZE_MB}MB (actual: {file_size_mb:.2f}MB)"
                )

            temp_file.write(contents)
            temp_file_path = temp_file.name

        # Step 1: Extract text from PDF (deterministic execution)
        parse_result = extract_text_from_pdf(temp_file_path)

        if not parse_result["success"]:
            return ClassificationResponse(
                success=False,
                error=parse_result["error"]
            )

        extracted_text = parse_result["text"]
        warning = parse_result.get("warning")

        # Check if API key is configured
        if not anthropic_client:
            return ClassificationResponse(
                success=False,
                error="Classification service not configured. Please contact administrator."
            )

        # Step 2: Classify and extract using Claude API (intelligent orchestration)
        classification_prompt = f"""You are analyzing a document from a Spanish accounting firm (gestoría).

Document text:
{extracted_text[:4000]}  # Limit to ~4000 chars to stay within token limits

Task:
1. Classify the document type from these options:
   - factura (invoice)
   - albarán (delivery note)
   - presupuesto (quote/estimate)
   - contrato (contract)
   - nómina (payroll/pay slip)
   - recibo (receipt)
   - certificado (certificate)
   - otro (other/unknown)

2. Extract relevant information based on the document type:
   - For facturas: invoice number, date, company name, total amount, tax amount, recipient
   - For albaránes: delivery note number, date, supplier name, items, recipient
   - For presupuestos: quote number, date, validity period, company, total amount
   - For contratos: contract type, parties involved, start date, duration
   - For nóminas: employee name, period, gross salary, net salary, company
   - For recibos: date, amount, concept, payee
   - For certificados: certificate type, issued to, issuing authority, date
   - For otro: brief description

3. Provide a confidence score (0-100) for your classification

Return ONLY valid JSON in this exact format:
{{
  "document_type": "factura",
  "confidence": 85,
  "extracted_data": {{
    "field_name": "value"
  }},
  "notes": "Any relevant observations"
}}"""

        # Call Claude API
        try:
            message = anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": classification_prompt
                }]
            )

            # Parse Claude's response
            response_text = message.content[0].text.strip()

            # Extract JSON from response (Claude sometimes adds markdown)
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            result = json.loads(response_text)

            # Add warning if text extraction was minimal
            notes = result.get("notes", "")
            if warning:
                notes = f"{warning} {notes}".strip()

            log_request(request, endpoint="/classify", query=file.filename or "", result={
                "success": True,
                "file_size_mb": round(file_size_mb, 2),
                "document_type": result.get("document_type", ""),
                "confidence": result.get("confidence", 0),
            })

            return ClassificationResponse(
                success=True,
                document_type=result.get("document_type"),
                confidence=result.get("confidence"),
                extracted_data=result.get("extracted_data"),
                notes=notes if notes else None
            )

        except anthropic.APIError as e:
            log_request(request, endpoint="/classify", query=file.filename or "", result={
                "success": False,
                "error": f"API error: {str(e)}",
            })
            return ClassificationResponse(
                success=False,
                error=f"API error: {str(e)}"
            )

        except json.JSONDecodeError:
            log_request(request, endpoint="/classify", query=file.filename or "", result={
                "success": False,
                "error": "Failed to parse classification results",
            })
            return ClassificationResponse(
                success=False,
                error="Failed to parse classification results"
            )

    except HTTPException:
        raise

    except Exception as e:
        log_request(request, endpoint="/classify", query=file.filename or "", result={
            "success": False,
            "error": f"Unexpected error: {str(e)}",
        })
        return ClassificationResponse(
            success=False,
            error=f"Unexpected error: {str(e)}"
        )

    finally:
        # Clean up temporary file
        if temp_file and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8001))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "False").lower() == "true"

    print(f"\n🚀 Starting Demo Gestoría - Document Classifier")
    print(f"   URL: http://{host}:{port}")
    print(f"   Docs: http://{host}:{port}/docs")
    print(f"   Rate limit: {RATE_LIMIT}")
    print(f"   Max file size: {MAX_FILE_SIZE_MB}MB\n")

    uvicorn.run(
        "classify_endpoint:app",
        host=host,
        port=port,
        reload=debug
    )
