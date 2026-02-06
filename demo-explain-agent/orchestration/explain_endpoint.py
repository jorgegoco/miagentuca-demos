#!/usr/bin/env python3
"""
Explain Agent API Endpoint

Layer 2: Orchestration - Uses AI to analyze business processes
and generate 3-layer architecture specifications.
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv
import anthropic

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

# Configuration
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

# Initialize FastAPI
app = FastAPI(
    title="Demo Explain Agent - Meta Demo",
    description="Shows how we build AI agents using the 3-layer architecture",
    version="1.0.0"
)

# CORS configuration - restrict to actual domains
ALLOWED_ORIGINS = [
    "https://miagentuca.es",
    "https://www.miagentuca.es",
    "https://explain.miagentuca.es",
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
anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key) if anthropic_api_key else None

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
        "service": "demo-explain-agent",
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


class ExplainRequest(BaseModel):
    """Request model for explain endpoint."""
    process_description: str = Field(
        ...,
        min_length=20,
        max_length=2000,
        description="Description of the business process to automate"
    )
    language: str = Field(default="es", description="Output language: es, en")


class ProcessAnalysis(BaseModel):
    """Analysis of the business process."""
    goal: str
    inputs: list[str]
    outputs: list[str]
    complexity: str


class DirectiveStep(BaseModel):
    """A single step in the automated process."""
    name: str
    description: str
    layer: str  # "directive" | "orchestration" | "execution"


class ExecutionCapability(BaseModel):
    """A tool or API the agent would use."""
    description: str
    tool: str


class ExplainResponse(BaseModel):
    """Response model for explain endpoint."""
    success: bool
    process_analysis: Optional[ProcessAnalysis] = None
    directive_summary: Optional[str] = None
    steps: Optional[list[DirectiveStep]] = None
    execution_capabilities: Optional[list[ExecutionCapability]] = None
    edge_cases: Optional[list[str]] = None
    implementation_estimate: Optional[str] = None
    implementation_notes: Optional[str] = None
    error: Optional[str] = None


EXPLAIN_PROMPT = """Eres un arquitecto de soluciones IA especializado en automatización de procesos para PYMEs españolas.

El cliente describe este proceso de negocio:
"{process_description}"

Analiza el proceso y genera una especificación usando la arquitectura DOE (Directiva-Orquestación-Ejecución).

Responde SOLO con JSON válido en este formato exacto:
{{
  "process_analysis": {{
    "goal": "Objetivo principal en una frase",
    "inputs": ["entrada1", "entrada2"],
    "outputs": ["salida1", "salida2"],
    "complexity": "low|medium|high"
  }},
  "directive_summary": "Resumen de 2-3 frases de lo que haría la directiva (la SOP del agente). Describe el objetivo y el enfoque general, no los pasos.",
  "steps": [
    {{
      "name": "Nombre corto del paso",
      "description": "1-2 frases explicando qué ocurre en este paso",
      "layer": "directive|orchestration|execution"
    }}
  ],
  "execution_capabilities": [
    {{
      "description": "Qué hace esta capacidad concreta",
      "tool": "Herramienta o API (ej: Gmail API, Google Drive API, Google Calendar API, Webhook, Base de datos)"
    }}
  ],
  "edge_cases": [
    "Caso especial 1 y cómo se manejaría",
    "Caso especial 2 y cómo se manejaría"
  ],
  "implementation_estimate": "Estimación realista (ej: '1-2 semanas de desarrollo')",
  "implementation_notes": "1-2 frases con contexto adicional o recomendaciones"
}}

REGLAS:
- Genera entre 3 y 6 pasos (steps). Cada paso debe indicar a qué capa pertenece:
  * "directive" = reglas/SOP que definen qué hacer (ej: "Cuando se reciba un registro nuevo, verificar que el email es válido")
  * "orchestration" = decisiones inteligentes del agente IA (ej: "Determinar el tipo de cliente y seleccionar la plantilla de bienvenida adecuada")
  * "execution" = scripts deterministas que hacen el trabajo (ej: "Enviar email via API de Gmail con la plantilla seleccionada")
- execution_capabilities: lista de 2-4 herramientas/APIs REALES que se necesitarían para implementar esto
- edge_cases: 2-3 situaciones problemáticas y cómo las manejaría el agente
- Sé ESPECÍFICO para el proceso descrito, no genérico
- Todo en español
- implementation_estimate debe ser realista para una PYME (no exagerar ni minimizar)
- La directive_summary NO debe repetir los pasos, sino explicar el enfoque general"""


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "demo-explain-agent",
        "anthropic_configured": anthropic_client is not None,
        "rate_limit": RATE_LIMIT
    }


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "Demo Explain Agent - Meta Demo",
        "version": "1.0.0",
        "description": "Muestra cómo construimos agentes IA con arquitectura de 3 capas",
        "endpoints": {
            "health": "/health",
            "explain": "POST /explain",
            "docs": "/docs"
        }
    }


@app.post("/explain", response_model=ExplainResponse)
@limiter.limit(RATE_LIMIT)
async def explain_process(body: ExplainRequest, request: Request):
    """
    Analyze a business process and generate a 3-layer architecture specification.
    """
    if not anthropic_client:
        raise HTTPException(
            status_code=503,
            detail="Anthropic API not configured"
        )

    try:
        # Build prompt
        prompt = EXPLAIN_PROMPT.format(
            process_description=body.process_description
        )

        # Call Claude API
        message = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Parse response
        response_text = message.content[0].text.strip()

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        result = json.loads(response_text)

        # Parse steps
        steps_raw = result.get("steps", [])
        steps = []
        for s in steps_raw:
            if isinstance(s, dict) and "name" in s and "description" in s:
                steps.append(DirectiveStep(
                    name=s["name"],
                    description=s["description"],
                    layer=s.get("layer", "execution")
                ))

        # Parse execution capabilities
        caps_raw = result.get("execution_capabilities", [])
        capabilities = []
        for c in caps_raw:
            if isinstance(c, dict) and "description" in c and "tool" in c:
                capabilities.append(ExecutionCapability(
                    description=c["description"],
                    tool=c["tool"]
                ))

        analysis = result.get("process_analysis", {
            "goal": "Objetivo no especificado",
            "inputs": [],
            "outputs": [],
            "complexity": "medium"
        })

        log_request(request, endpoint="/explain", query=body.process_description[:200], result={
            "success": True,
            "language": body.language,
            "complexity": analysis.get("complexity", ""),
        })

        return ExplainResponse(
            success=True,
            process_analysis=ProcessAnalysis(**analysis),
            directive_summary=result.get("directive_summary", ""),
            steps=steps if steps else None,
            execution_capabilities=capabilities if capabilities else None,
            edge_cases=result.get("edge_cases"),
            implementation_estimate=result.get("implementation_estimate", ""),
            implementation_notes=result.get("implementation_notes", ""),
            error=None
        )

    except json.JSONDecodeError as e:
        log_request(request, endpoint="/explain", query=body.process_description[:200], result={
            "success": False,
            "error": f"Error parsing response: {str(e)}",
        })
        return ExplainResponse(
            success=False,
            process_analysis=None,
            directive_summary=None,
            steps=None,
            execution_capabilities=None,
            edge_cases=None,
            implementation_estimate=None,
            implementation_notes=None,
            error=f"Error parsing response: {str(e)}"
        )
    except anthropic.APIError as e:
        log_request(request, endpoint="/explain", query=body.process_description[:200], result={
            "success": False,
            "error": f"Anthropic API error: {str(e)}",
        })
        raise HTTPException(
            status_code=502,
            detail=f"Anthropic API error: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8003"))
    print(f"Starting Explain Agent on port {port}")
    print(f"API Key configured: {bool(anthropic_api_key)}")
    uvicorn.run(app, host="0.0.0.0", port=port)
