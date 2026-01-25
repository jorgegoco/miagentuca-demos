#!/usr/bin/env python3
"""
Explain Agent API Endpoint

Layer 2: Orchestration - Uses AI to analyze business processes
and generate 3-layer architecture specifications.
"""

import os
import sys
import json
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv
import anthropic

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from execution.template_generator import validate_mermaid, generate_three_layer_flowchart

# Load environment variables
load_dotenv()

# Configuration
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
rate_limit = os.getenv("MAX_REQUESTS_PER_MINUTE", "5")

# Initialize FastAPI
app = FastAPI(
    title="Demo Explain Agent - Meta Demo",
    description="Shows how we build AI agents using the 3-layer architecture",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Initialize Anthropic client
anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key) if anthropic_api_key else None


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


class ExplainResponse(BaseModel):
    """Response model for explain endpoint."""
    success: bool
    process_analysis: Optional[ProcessAnalysis]
    directive: Optional[str]
    execution_code: Optional[str]
    flowchart: Optional[str]
    implementation_notes: Optional[str]
    error: Optional[str] = None


EXPLAIN_PROMPT = """Eres un arquitecto de soluciones IA especializado en automatización de procesos.

El cliente describe este proceso de negocio:
"{process_description}"

Analiza el proceso y genera una especificación completa usando la arquitectura de 3 capas.

Responde SOLO con JSON válido en este formato exacto:
{{
  "process_analysis": {{
    "goal": "Objetivo principal del proceso",
    "inputs": ["entrada1", "entrada2"],
    "outputs": ["salida1", "salida2"],
    "complexity": "low|medium|high"
  }},
  "directive": "# Directiva del Agente\\n\\n## Propósito\\n[Descripción clara del objetivo]\\n\\n## Entradas\\n- [Lista de entradas necesarias]\\n\\n## Proceso\\n### Paso 1: [Nombre]\\n[Descripción]\\n\\n### Paso 2: [Nombre]\\n[Descripción]\\n\\n## Salidas\\n- [Lista de salidas/entregables]\\n\\n## Casos Especiales\\n- [Manejo de errores y edge cases]",
  "execution_code": "#!/usr/bin/env python3\\n# Capa 3: Ejecución\\n\\ndef procesar(entrada: str) -> dict:\\n    # Validación\\n    if not entrada:\\n        raise ValueError('Entrada requerida')\\n    \\n    # Procesamiento\\n    resultado = {{}}\\n    \\n    # TODO: Implementar lógica\\n    \\n    return resultado",
  "flowchart": "flowchart TB\\n    subgraph L1[Capa 1: Directiva]\\n        D1[Reglas del proceso]\\n    end\\n    subgraph L2[Capa 2: Orquestación]\\n        O1[Agente IA]\\n    end\\n    subgraph L3[Capa 3: Ejecución]\\n        E1[Scripts Python]\\n    end\\n    User([Usuario]) --> L1\\n    L1 --> L2\\n    L2 --> L3\\n    L3 --> Result([Resultado])",
  "implementation_notes": "Notas sobre la implementación, estimación de tiempo, y próximos pasos"
}}

IMPORTANTE:
- La directiva debe ser en español y usar formato Markdown
- El código debe ser Python válido y seguir buenas prácticas
- El flowchart debe ser Mermaid válido
- Sé específico para el proceso descrito, no genérico
- Incluye manejo de errores realista"""


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "demo-explain-agent",
        "anthropic_configured": anthropic_client is not None,
        "rate_limit": f"{rate_limit}/minute"
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
@limiter.limit(f"{rate_limit}/minute")
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
            max_tokens=3000,
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

        # Validate flowchart
        flowchart = result.get("flowchart", "")
        if not validate_mermaid(flowchart):
            # Generate a fallback flowchart
            flowchart = generate_three_layer_flowchart(
                process_name=result.get("process_analysis", {}).get("goal", "Proceso"),
                steps=["Paso 1", "Paso 2", "Paso 3"]
            )

        return ExplainResponse(
            success=True,
            process_analysis=ProcessAnalysis(**result.get("process_analysis", {
                "goal": "Objetivo no especificado",
                "inputs": [],
                "outputs": [],
                "complexity": "medium"
            })),
            directive=result.get("directive", ""),
            execution_code=result.get("execution_code", ""),
            flowchart=flowchart,
            implementation_notes=result.get("implementation_notes", ""),
            error=None
        )

    except json.JSONDecodeError as e:
        return ExplainResponse(
            success=False,
            process_analysis=None,
            directive=None,
            execution_code=None,
            flowchart=None,
            implementation_notes=None,
            error=f"Error parsing response: {str(e)}"
        )
    except anthropic.APIError as e:
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
