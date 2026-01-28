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


SUPPLIER_SEARCH_SYSTEM = """Eres un agente de compras experto para ferreterías y suministros industriales en España.
Tu trabajo es generar datos de proveedores con precios REALISTAS del mercado español actual.

REGLAS DE PRECIOS - Usa estas referencias reales del mercado español (sin IVA):

TORNILLERÍA Y FIJACIONES:
- Tornillos acero inoxidable: 0.03-0.25€/ud según tamaño (M4: ~0.03€, M6: ~0.08€, M8: ~0.12€, M10: ~0.20€)
- Tornillos acero zincado: 40-60% más baratos que inox
- Tacos + tornillos: 0.05-0.30€/ud
- Clavos: 0.01-0.05€/ud
- Arandelas: 0.01-0.08€/ud

HERRAMIENTAS ELÉCTRICAS:
- Taladro percutor básico: 50-80€
- Taladro percutor profesional (Bosch, Makita, DeWalt): 80-200€
- Amoladora 125mm: 40-120€
- Sierra circular: 100-300€
- Atornillador batería: 60-250€

MATERIAL ELÉCTRICO:
- Cable H07V-K 1.5mm² 100m: 25-40€
- Cable H07V-K 2.5mm² 100m: 35-55€
- Cable H07V-K 4mm² 100m: 55-85€
- Cable H07V-K 6mm² 100m: 80-120€
- Mecanismos (enchufes, interruptores): 2-15€/ud

CONSTRUCCIÓN:
- Cemento portland 25kg: 4.50-7.00€/saco
- Mortero 25kg: 2.50-5.00€/saco
- Yeso 20kg: 3.00-5.50€/saco
- Ladrillo hueco: 0.15-0.40€/ud

FONTANERÍA:
- Tubo PVC 110mm 3m: 8-15€
- Tubo multicapa 20mm: 1.50-3.00€/m
- Grifería básica: 25-60€
- Grifería media: 60-150€

PINTURA:
- Pintura plástica interior 15L: 30-70€
- Esmalte sintético 750ml: 8-18€
- Imprimación 4L: 15-30€

ENVÍO en España peninsular:
- Paquetería pequeña (<5kg): 4-8€
- Paquetería media (5-30kg): 8-15€
- Palé / mercancía pesada: 25-60€
- Envío gratis: solo en pedidos grandes (>200-500€ según proveedor)

IMPORTANTE: Los precios deben estar DENTRO de estos rangos. Si el producto no aparece en la lista, extrapola a partir de productos similares."""

SUPPLIER_SEARCH_PROMPT = """El usuario busca: "{product}" (cantidad: {quantity})
Urgencia: {urgency}

Genera datos de 4-5 proveedores españoles REALES que vendan este tipo de producto.
Elige proveedores apropiados para la categoría del producto:
- Tornillería/fijaciones: Würth España, Bricomart, Leroy Merlin Pro, Saltoki, Coferdroza
- Herramientas eléctricas: Würth España, Leroy Merlin Pro, Bricomart, Saltoki, Makita España
- Material eléctrico: Rexel, Saltoki, Grupo Electro Stocks, Sonepar, Leroy Merlin Pro
- Construcción/albañilería: Bricomart, BigMat, Leroy Merlin Pro, Punto de la Construcción, Cemex
- Fontanería: Saltoki, Salvador Escoda, Leroy Merlin Pro, Bricomart, Roca
- Pintura: Bricomart, Leroy Merlin Pro, AkzoNobel, Pinturas Isaval, Jotun

Responde SOLO con JSON válido en este formato exacto:
{{
  "product_parsed": {{
    "name": "nombre del producto normalizado",
    "specifications": "especificaciones técnicas concretas (medidas, material, norma DIN/ISO si aplica)",
    "quantity": {quantity}
  }},
  "suppliers": [
    {{
      "name": "Nombre Proveedor Real",
      "unit_price": 0.00,
      "delivery_days": 0,
      "min_order": 0,
      "shipping_cost": 0.00,
      "in_stock": true
    }}
  ]
}}

RECUERDA:
- Precios sin IVA, en EUR, DENTRO de los rangos de referencia
- Coste de envío coherente con el peso total del pedido
- Pedido mínimo realista (1 para herramientas, 10-100 para tornillería)
- Al menos un proveedor debe tener stock agotado (in_stock: false)
- Varía los días de entrega entre 1 y 7 días"""


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
            max_tokens=2000,
            system=SUPPLIER_SEARCH_SYSTEM,
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
