# Demo Compras - Purchase Agent

AI-powered procurement assistant for hardware stores. Search suppliers, compare prices, and get purchase recommendations.

## Live Demo

**URL:** [compras.miagentuca.es](https://compras.miagentuca.es)

**API Docs:** [compras.miagentuca.es/docs](https://compras.miagentuca.es/docs)

## Overview

This demo showcases the 3-layer architecture for AI agents:

1. **Directive Layer** (`directives/purchase_agent.md`) - Procurement rules and supplier search specifications
2. **Execution Layer** (`execution/price_analyzer.py`) - Deterministic price comparison and recommendations
3. **Orchestration Layer** (`orchestration/purchase_endpoint.py`) - Intelligent supplier search using Claude API

## Features

- Searches Spanish suppliers (Würth, Bricomart, Leroy Merlin Pro, Saltoki, Rexel)
- Compares prices, delivery times, and minimum orders
- Calculates total costs including shipping
- Recommends best price, fastest delivery, and best value options
- Rate limiting (5 requests/minute per IP)

## API Usage

### Search Suppliers

**Endpoint:** `POST /search`

**Request:**
```bash
curl -X POST "https://compras.miagentuca.es/search" \
  -H "Content-Type: application/json" \
  -d '{
    "product": "100 tornillos de 6mm acero inoxidable",
    "quantity": 100,
    "urgency": "normal"
  }'
```

**Response:**
```json
{
  "success": true,
  "product_parsed": {
    "name": "Tornillos hexagonales 6mm acero inoxidable A2",
    "specifications": "M6, DIN 933, longitud 20mm",
    "quantity": 100
  },
  "suppliers": [
    {
      "name": "Würth España",
      "unit_price": 0.18,
      "total_price": 26.50,
      "delivery_days": 2,
      "min_order": 50,
      "shipping_cost": 8.50,
      "in_stock": true
    }
  ],
  "recommendations": {
    "best_price": "Würth España",
    "fastest_delivery": "Würth España",
    "best_value": "Würth España",
    "reasoning": "Würth España ofrece el mejor precio total de 26.50€"
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
