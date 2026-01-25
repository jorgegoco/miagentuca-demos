# Purchase Agent Directive

## Purpose
Assist hardware store procurement by searching suppliers, comparing prices, and generating purchase recommendations.

## Input
- **Product description**: What the user wants to buy (e.g., "100 tornillos de 6mm acero inoxidable")
- **Quantity**: How many units needed
- **Urgency**: normal, urgent, very_urgent

## Process

### Step 1: Parse Request
Extract from user input:
- Product type and specifications
- Quantity needed
- Delivery urgency
- Any brand preferences

### Step 2: Search Suppliers
Use AI to simulate supplier search with realistic Spanish suppliers:
- Würth España
- Bricomart
- Leroy Merlin Pro
- Rexel
- Saltoki
- Local distributors

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
    "specifications": "string",
    "quantity": number
  },
  "suppliers": [
    {
      "name": "string",
      "unit_price": number,
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

## Spanish Context
- All prices in EUR
- Suppliers are Spanish/European
- Product names may be in Spanish
- IVA (21%) should be noted if included/excluded

## Rate Limiting
- 5 requests per minute per IP
- Max query length: 500 characters
