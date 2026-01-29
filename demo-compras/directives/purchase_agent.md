# Purchase Agent Directive

## Purpose
Assist any business with procurement by searching suppliers, comparing prices, and generating purchase recommendations. The agent auto-detects the product category and selects appropriate Spanish suppliers.

## Input
- **Product description**: What the user wants to buy (e.g., "1 paquete de folios A4", "100 tornillos de 6mm acero inoxidable", "caja de guantes de nitrilo")
- **Quantity**: How many units needed
- **Urgency**: normal, urgent, very_urgent

## Process

### Step 1: Parse Request
Extract from user input:
- Product type and specifications
- Auto-detect product category
- Quantity needed
- Delivery urgency
- Any brand preferences

### Step 2: Search Suppliers
Use AI to simulate supplier search. Suppliers must be:
- Real Spanish companies appropriate for the product category
- Category-specific (auto-detected from the product description)

Supplier pools by category:
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

### Step 3: Compare Options
For each supplier, evaluate:
- Unit price
- Bulk discounts
- Delivery time
- Minimum order quantity
- Shipping cost

### Step 4: Generate Recommendation
Provide:
- Best price option
- Best delivery time option
- Best overall value (balanced)
- Reasoning for each

## Output Format (JSON)
```json
{
  "success": true,
  "product_parsed": {
    "name": "string",
    "category": "detected category",
    "specifications": "string",
    "quantity": number
  },
  "suppliers": [
    {
      "name": "string",
      "unit_price": number,
      "unit": "commercial unit (e.g. caja 100 uds, paquete 500 hojas)",
      "total_price": number,
      "delivery_days": number,
      "min_order": number,
      "shipping_cost": number,
      "in_stock": boolean
    }
  ],
  "recommendations": {
    "best_price": "supplier_name",
    "fastest_delivery": "supplier_name",
    "best_value": "supplier_name",
    "reasoning": "string"
  }
}
```

## Edge Cases

### No suppliers found
Return empty suppliers array with helpful message.

### Product unclear
Ask for clarification or make reasonable assumptions, noting them in response.

### Very large quantities
Flag that bulk/wholesale pricing may apply and recommend direct contact.

## Price Accuracy
The system prompt includes reference price ranges for many product categories (office supplies, tech, hospitality, cleaning, screws, power tools, cables, construction, plumbing, paint). Claude must generate prices WITHIN these ranges. If a product doesn't appear in the references, Claude extrapolates from similar products. This was added to fix unrealistic pricing issues discovered during testing.

## Spanish Context
- All prices in EUR, sin IVA
- Suppliers are real Spanish/European companies matched to product category
- Product names may be in Spanish
- Shipping costs must be coherent with total order weight

## Unit Normalization
Vague inputs are normalized to standard commercial units. Examples:
- "unos guantes" → caja de 100 uds
- "folios" → paquete 500 hojas
- "tornillos M6" → caja de 100 uds
The `unit` field in each supplier response always clarifies what the price refers to.

## Rate Limiting
- 3 requests per minute per IP + 20 requests per day per IP
- Proxy-aware IP detection (X-Forwarded-For / X-Real-IP)
- CORS restricted to miagentuca.es and demo subdomains
- Max query length: 500 characters
- Configurable via `RATE_LIMIT` env var (default: `3/minute;20/day`)
