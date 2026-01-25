#!/usr/bin/env python3
"""
Purchase Agent API Endpoint

Layer 2: Orchestration - Uses AI for supplier search simulation,
then deterministic execution for price analysis.
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
from execution.price_analyzer import analyze_suppliers, sort_suppliers_by_price

# Load environment variables
load_dotenv()

# Configuration
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
rate_limit = os.getenv("MAX_REQUESTS_PER_MINUTE", "5")

# Initialize FastAPI
app = FastAPI(
    title="Demo Compras - Purchase Agent",
    description="AI-powered procurement assistant for hardware stores",
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


class PurchaseRequest(BaseModel):
    """Request model for purchase query."""
    product: str = Field(..., min_length=3, max_length=500, description="Product description")
    quantity: int = Field(default=1, ge=1, le=10000, description="Quantity needed")
    urgency: str = Field(default="normal", description="Urgency level: normal, urgent, very_urgent")


class SupplierInfo(BaseModel):
    """Supplier information."""
    name: str
    unit_price: float
    total_price: float
    delivery_days: int
    min_order: int
    shipping_cost: float
    in_stock: bool


class Recommendations(BaseModel):
    """Purchase recommendations."""
    best_price: Optional[str]
    fastest_delivery: Optional[str]
    best_value: Optional[str]
    reasoning: str


class PurchaseResponse(BaseModel):
    """Response model for purchase query."""
    success: bool
    product_parsed: dict
    suppliers: list[SupplierInfo]
    recommendations: Recommendations
    error: Optional[str] = None


SUPPLIER_SEARCH_PROMPT = """Eres un agente de compras para una ferretería española.
El usuario busca: "{product}" (cantidad: {quantity})
Urgencia: {urgency}

Genera datos REALISTAS de 4-5 proveedores españoles. Usa proveedores reales como:
- Würth España
- Bricomart
- Leroy Merlin Pro
- Rexel
- Saltoki
- Suministros industriales locales

Para cada proveedor, proporciona datos realistas de:
- Precio unitario (en EUR, sin IVA)
- Días de entrega
- Pedido mínimo
- Coste de envío
- Disponibilidad en stock

Responde SOLO con JSON válido en este formato exacto:
{{
  "product_parsed": {{
    "name": "nombre del producto",
    "specifications": "especificaciones técnicas",
    "quantity": {quantity}
  }},
  "suppliers": [
    {{
      "name": "Nombre Proveedor",
      "unit_price": 0.00,
      "delivery_days": 0,
      "min_order": 0,
      "shipping_cost": 0.00,
      "in_stock": true
    }}
  ]
}}

Asegúrate de que los precios sean realistas para el mercado español.
Al menos un proveedor debe tener stock agotado (in_stock: false) para demostrar variedad."""


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "demo-compras",
        "anthropic_configured": anthropic_client is not None,
        "rate_limit": f"{rate_limit}/minute"
    }


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "Demo Compras - Purchase Agent",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "search": "POST /search",
            "docs": "/docs"
        }
    }


@app.post("/search", response_model=PurchaseResponse)
@limiter.limit(f"{rate_limit}/minute")
async def search_suppliers(body: PurchaseRequest, request: Request):
    """
    Search suppliers for a product and get purchase recommendations.
    """
    if not anthropic_client:
        raise HTTPException(
            status_code=503,
            detail="Anthropic API not configured"
        )

    try:
        # Build prompt
        prompt = SUPPLIER_SEARCH_PROMPT.format(
            product=body.product,
            quantity=body.quantity,
            urgency=body.urgency
        )

        # Call Claude API
        message = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
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

        supplier_data = json.loads(response_text)

        # Calculate total prices for each supplier
        suppliers = []
        for s in supplier_data.get("suppliers", []):
            total = round(s["unit_price"] * body.quantity + s["shipping_cost"], 2)
            suppliers.append({
                "name": s["name"],
                "unit_price": s["unit_price"],
                "total_price": total,
                "delivery_days": s["delivery_days"],
                "min_order": s["min_order"],
                "shipping_cost": s["shipping_cost"],
                "in_stock": s["in_stock"]
            })

        # Sort suppliers by price
        suppliers = sort_suppliers_by_price(suppliers)

        # Analyze and get recommendations (deterministic Layer 3)
        recommendations = analyze_suppliers(suppliers)

        return PurchaseResponse(
            success=True,
            product_parsed=supplier_data.get("product_parsed", {
                "name": body.product,
                "specifications": "",
                "quantity": body.quantity
            }),
            suppliers=suppliers,
            recommendations=Recommendations(**recommendations),
            error=None
        )

    except json.JSONDecodeError as e:
        return PurchaseResponse(
            success=False,
            product_parsed={"name": body.product, "specifications": "", "quantity": body.quantity},
            suppliers=[],
            recommendations=Recommendations(
                best_price=None,
                fastest_delivery=None,
                best_value=None,
                reasoning="Error parsing supplier data"
            ),
            error=f"JSON parse error: {str(e)}"
        )
    except anthropic.APIError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Anthropic API error: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8002"))
    print(f"Starting Purchase Agent on port {port}")
    print(f"API Key configured: {bool(anthropic_api_key)}")
    uvicorn.run(app, host="0.0.0.0", port=port)
