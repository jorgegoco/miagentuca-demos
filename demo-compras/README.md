# Demo Compras - Purchase Agent

AI-powered procurement assistant for any business. Search suppliers, compare prices, and get purchase recommendations. Supports office supplies, tech, hospitality, cleaning, construction, and more — the agent auto-detects the product category.

## Live Demo

**URL:** [compras.miagentuca.es](https://compras.miagentuca.es)

**API Docs:** [compras.miagentuca.es/docs](https://compras.miagentuca.es/docs)

## Overview

This demo showcases the 3-layer architecture for AI agents:

1. **Directive Layer** (`directives/purchase_agent.md`) - Procurement rules and supplier search specifications
2. **Execution Layer** (`execution/price_analyzer.py`) - Deterministic price comparison and recommendations
3. **Orchestration Layer** (`orchestration/purchase_endpoint.py`) - Intelligent supplier search using Claude API

## Features

- Auto-detects product category (office, tech, hospitality, cleaning, construction, plumbing, paint...)
- Selects appropriate Spanish suppliers per category (Lyreco, PcComponentes, Makro, Würth, Bricomart...)
- Compares prices, delivery times, and minimum orders
- Calculates total costs including shipping
- Recommends best price, fastest delivery, and best value options
- Rate limiting (3 requests/minute + 20/day per IP)

## API Usage

### Search Suppliers

**Endpoint:** `POST /search`

**Request:**
```bash
curl -X POST "https://compras.miagentuca.es/search" \
  -H "Content-Type: application/json" \
  -d '{
    "product": "1 paquete de folios A4",
    "quantity": 1,
    "urgency": "normal"
  }'
```

**Response:**
```json
{
  "success": true,
  "product_parsed": {
    "name": "Papel A4 80g 500 hojas",
    "category": "Material de oficina",
    "specifications": "Folios A4, 80g/m², blanco, paquete 500 hojas",
    "quantity": 1
  },
  "suppliers": [
    {
      "name": "Lyreco",
      "unit_price": 4.50,
      "unit": "paquete 500 hojas",
      "total_price": 9.50,
      "delivery_days": 2,
      "min_order": 1,
      "shipping_cost": 5.00,
      "in_stock": true
    }
  ],
  "recommendations": {
    "best_price": "Lyreco",
    "fastest_delivery": "Lyreco",
    "best_value": "Lyreco",
    "reasoning": "Lyreco ofrece el mejor precio total de 9.50€"
  }
}
```

## Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product` | string | Yes | Product description (3-500 chars) |
| `quantity` | integer | No | Quantity needed (default: 1, max: 10000) |
| `urgency` | string | No | normal, urgent, very_urgent |

## Local Development

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Run server
python orchestration/purchase_endpoint.py
```

## License

Private demo - All rights reserved
