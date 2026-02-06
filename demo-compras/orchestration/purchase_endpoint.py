#!/usr/bin/env python3
"""
Purchase Agent API Endpoint

Layer 2: Orchestration - Uses AI for supplier search simulation,
then deterministic execution for price analysis.
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
from execution.price_analyzer import analyze_suppliers, sort_suppliers_by_price

# Load environment variables
load_dotenv()

# Configuration
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")


def get_real_ip(request: Request) -> str:
    """Extract real client IP behind reverse proxy (Traefik/Nginx)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "127.0.0.1"

# Initialize FastAPI
app = FastAPI(
    title="Demo Compras - Purchase Agent",
    description="AI-powered procurement assistant for any business",
    version="1.0.0"
)

# CORS configuration - restrict to actual domains
ALLOWED_ORIGINS = [
    "https://miagentuca.es",
    "https://www.miagentuca.es",
    "https://compras.miagentuca.es",
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
        "service": "demo-compras",
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


class PurchaseRequest(BaseModel):
    """Request model for purchase query."""
    product: str = Field(..., min_length=3, max_length=500, description="Product description")
    quantity: int = Field(default=1, ge=1, le=10000, description="Quantity needed")
    urgency: str = Field(default="normal", description="Urgency level: normal, urgent, very_urgent")


class SupplierInfo(BaseModel):
    """Supplier information."""
    name: str
    unit_price: float
    unit: str
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
    procurement_tips: list[str] = []
    error: Optional[str] = None


SUPPLIER_SEARCH_SYSTEM = """Eres un agente de compras experto para empresas en España.
Tu trabajo es generar datos de proveedores con precios REALISTAS del mercado español actual.
Detecta automáticamente la categoría del producto y usa proveedores apropiados.

REGLAS DE PRECIOS - Usa estas referencias reales del mercado español (sin IVA):

MATERIAL DE OFICINA:
- Folios A4 500 hojas (80g): 4-6€/paquete
- Folios A4 500 hojas (90g premium): 6-9€/paquete
- Bolígrafos BIC/básicos: 0.15-0.40€/ud
- Bolígrafos marca (Pilot, Uni-ball): 1-4€/ud
- Archivadores A4: 1.50-4€/ud
- Sobres americanos caja 500: 8-15€
- Clips caja 100: 0.50-1.50€
- Grapadora: 5-25€
- Post-it pack 12: 8-15€
- Tóner HP/Canon básico: 25-50€
- Tóner HP/Canon original: 50-120€
- Cartuchos tinta: 10-30€
- Papel para impresora A3 500 hojas: 8-14€

INFORMÁTICA Y TECNOLOGÍA:
- Teclado USB básico: 8-20€
- Teclado inalámbrico: 20-60€
- Ratón óptico: 5-15€
- Ratón ergonómico: 20-60€
- Monitor 24" Full HD: 120-200€
- Monitor 27" QHD: 200-400€
- Disco duro externo 1TB: 45-70€
- SSD externo 1TB: 70-130€
- Cable HDMI 2m: 5-15€
- Memoria USB 64GB: 6-15€
- Webcam HD: 30-80€
- Router WiFi 6: 40-120€

HOSTELERÍA Y ALIMENTACIÓN:
- Servilletas 1 capa 1000 uds: 8-15€
- Servilletas 2 capas 100 uds: 2-5€
- Vasos desechables 50 uds: 3-7€
- Guantes desechables nitrilo caja 100: 5-12€
- Film transparente rollo 300m: 8-18€
- Papel aluminio rollo 100m: 12-22€
- Bolsas basura 100L (rollo 10): 2-5€
- Bayetas pack 10: 3-8€
- Lavavajillas industrial 5L: 8-18€
- Aceite de oliva virgen extra 5L: 25-45€
- Aceite de girasol 5L: 6-12€
- Harina 25kg: 12-20€
- Azúcar 25kg: 18-28€

LIMPIEZA E HIGIENE:
- Lejía 5L: 2-5€
- Fregasuelos 5L: 4-10€
- Gel hidroalcohólico 5L: 12-25€
- Jabón de manos 5L: 8-18€
- Papel higiénico industrial rollo 200m: 2-5€/rollo
- Papel secamanos rollo 150m: 3-6€/rollo
- Bolsas de basura 30L (rollo 25): 1.50-4€
- Escoba industrial: 5-15€
- Fregona + cubo: 10-25€
- Ambientador spray 750ml: 3-8€

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

NORMALIZACIÓN DE UNIDADES:
- Si el usuario da una descripción vaga (ej: "unos guantes", "folios", "tornillos"), normaliza a la unidad comercial estándar más habitual (caja, paquete, bolsa, unidad...).
- Ejemplos: "unos guantes de nitrilo" → caja de 100 uds. "folios" → paquete 500 hojas. "tornillos M6" → caja de 100 uds.
- El campo "unit" debe indicar SIEMPRE a qué se refiere el precio unitario (ej: "caja 100 uds", "paquete 500 hojas", "saco 25kg", "unidad", "bote 5L").

VARIACIÓN DE PRECIOS:
- NO generes precios agrupados dentro de un 10% entre todos los proveedores. En la realidad, hay diferencias significativas.
- Los proveedores generalistas (Amazon Business, Leroy Merlin) suelen ser un 15-30% más caros que los especialistas del sector.
- Los mayoristas (Makro, Würth) suelen ofrecer los mejores precios pero con pedido mínimo más alto.
- Genera un spread de precios realista: el proveedor más caro debería ser al menos un 25-40% más caro que el más barato.

STOCK:
- El stock debe variar de forma natural según el tipo de producto y la situación del mercado.
- Productos de alta rotación (folios, tornillos estándar, lejía): casi siempre en stock.
- Productos especializados o de marca concreta: posibilidad real de estar sin stock.
- NO fuerces que siempre haya exactamente un proveedor sin stock. Refleja la realidad del producto.

CONSEJOS DE COMPRA (procurement_tips):
- Genera 2-3 consejos prácticos y específicos para la categoría del producto.
- Deben ser útiles para alguien que compra este producto por primera vez o quiere optimizar.
- Ejemplos: "Los folios A4 de 80g son suficientes para impresoras láser estándar. Para impresión a doble cara, considere 90g." o "Compre guantes de nitrilo en cajas de 1000 unidades para ahorros del 15-20%."
- Los tips deben ser concretos y accionables, no genéricos.

IMPORTANTE: Los precios deben estar DENTRO de estos rangos. Si el producto no aparece en la lista, extrapola a partir de productos similares del mercado español."""

SUPPLIER_SEARCH_PROMPT_TEMPLATE = """El usuario busca: "{product}" (cantidad: {quantity})
Urgencia: {urgency}

{urgency_instructions}

PASO 1: Detecta la categoría del producto. Usa estas categorías y sus proveedores:
- Material de oficina: Lyreco, Staples, RAJA España, Office Depot, Amazon Business
- Informática/tecnología: PcComponentes, Amazon Business, Esprinet, LDLC, Coolmod
- Hostelería/alimentación: Makro, GM Food, Miró, Distriplus, Coviran
- Limpieza/higiene: Papelmatic, Proquimia, Distriplus, Amazon Business, Leroy Merlin Pro
- Tornillería/fijaciones: Würth España, Bricomart, Leroy Merlin Pro, Saltoki, Coferdroza
- Herramientas eléctricas: Würth España, Leroy Merlin Pro, Bricomart, Saltoki, Makita España
- Material eléctrico: Rexel, Saltoki, Grupo Electro Stocks, Sonepar, Leroy Merlin Pro
- Construcción/albañilería: Bricomart, BigMat, Leroy Merlin Pro, Punto de la Construcción, Cemex
- Fontanería: Saltoki, Salvador Escoda, Leroy Merlin Pro, Bricomart, Roca
- Pintura: Bricomart, Leroy Merlin Pro, AkzoNobel, Pinturas Isaval, Jotun
- Otro (productos generales): Amazon Business, ManoMano, Leroy Merlin Pro, Alibaba España, RAJA España

PASO 2: Genera datos de 4-5 proveedores españoles REALES de la categoría detectada.

{quantity_instructions}

Responde SOLO con JSON válido en este formato exacto:
{{{{
  "product_parsed": {{{{
    "name": "nombre del producto normalizado",
    "category": "categoría detectada",
    "specifications": "especificaciones concretas (gramaje, medidas, material, marca si procede)",
    "quantity": {quantity}
  }}}},
  "suppliers": [
    {{{{
      "name": "Nombre Proveedor Real",
      "unit_price": 0.00,
      "unit": "unidad comercial (ej: caja 100 uds, paquete 500 hojas, unidad, saco 25kg)",
      "delivery_days": 0,
      "min_order": 0,
      "shipping_cost": 0.00,
      "in_stock": true
    }}}}
  ],
  "procurement_tips": [
    "Consejo práctico 1 específico para esta categoría de producto",
    "Consejo práctico 2 sobre cómo optimizar la compra"
  ]
}}}}

RECUERDA:
- Precios sin IVA, en EUR, DENTRO de los rangos de referencia
- Coste de envío coherente con el peso total del pedido
- Pedido mínimo realista (1 para productos caros, 1-10 para consumibles)
- Varía los días de entrega entre 1 y 7 días
- Genera un spread de precios realista (el más caro al menos 25-40% más que el más barato)
- procurement_tips: 2-3 consejos prácticos y específicos para este producto"""


def build_supplier_search_prompt(product: str, quantity: int, urgency: str) -> str:
    """Build the user prompt with urgency- and quantity-aware instructions."""
    urgency_instructions = ""
    if urgency in ("urgent", "very_urgent"):
        urgency_instructions = (
            "⚠️ PEDIDO URGENTE: Prioriza proveedores con stock disponible y entrega rápida (1-2 días). "
            "Indica qué proveedores ofrecen envío express. "
            "Penaliza en la recomendación a proveedores con entrega superior a 2 días."
        )

    quantity_instructions = ""
    if quantity > 50:
        quantity_instructions = (
            "📦 PEDIDO EN VOLUMEN: Menciona la disponibilidad de descuentos por volumen. "
            "Destaca los requisitos de pedido mínimo de forma prominente. "
            "Si algún proveedor ofrece precios escalonados por cantidad, indícalo."
        )

    return SUPPLIER_SEARCH_PROMPT_TEMPLATE.format(
        product=product,
        quantity=quantity,
        urgency=urgency,
        urgency_instructions=urgency_instructions,
        quantity_instructions=quantity_instructions,
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "demo-compras",
        "anthropic_configured": anthropic_client is not None,
        "rate_limit": RATE_LIMIT
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
@limiter.limit(RATE_LIMIT)
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
        prompt = build_supplier_search_prompt(
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
                "unit": s.get("unit", "unidad"),
                "total_price": total,
                "delivery_days": s["delivery_days"],
                "min_order": s["min_order"],
                "shipping_cost": s["shipping_cost"],
                "in_stock": s["in_stock"]
            })

        # Sort suppliers by price
        suppliers = sort_suppliers_by_price(suppliers)

        # Analyze and get recommendations (deterministic Layer 3)
        recommendations = analyze_suppliers(
            suppliers, urgency=body.urgency, quantity=body.quantity
        )

        parsed = supplier_data.get("product_parsed", {
            "name": body.product,
            "specifications": "",
            "quantity": body.quantity
        })

        procurement_tips = supplier_data.get("procurement_tips", [])

        log_request(request, endpoint="/search", query=body.product, result={
            "success": True,
            "quantity": body.quantity,
            "urgency": body.urgency,
            "category": parsed.get("category", ""),
            "suppliers_count": len(suppliers),
        })

        return PurchaseResponse(
            success=True,
            product_parsed=parsed,
            suppliers=suppliers,
            recommendations=Recommendations(**recommendations),
            procurement_tips=procurement_tips,
            error=None
        )

    except json.JSONDecodeError as e:
        log_request(request, endpoint="/search", query=body.product, result={
            "success": False,
            "error": f"JSON parse error: {str(e)}",
        })
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
        log_request(request, endpoint="/search", query=body.product, result={
            "success": False,
            "error": f"Anthropic API error: {str(e)}",
        })
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
