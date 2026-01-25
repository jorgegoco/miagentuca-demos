# API Integration Guide for miagentuca.es Landing Page

This document explains how to integrate the AI demos into the miagentuca.es landing page hosted on GitHub Pages.

## Available APIs

All APIs are live and ready to use. CORS is enabled for all origins.

| Demo | Base URL | Purpose |
|------|----------|---------|
| Gestoría | `https://gestoria.miagentuca.es` | Document classification |
| Compras | `https://compras.miagentuca.es` | Supplier search |
| Explain | `https://explain.miagentuca.es` | Agent architecture generator |

---

## 1. Gestoría - Document Classifier

**Upload a PDF → Get document type and extracted data**

### Endpoint
```
POST https://gestoria.miagentuca.es/classify
Content-Type: multipart/form-data
```

### JavaScript Example
```javascript
async function classifyDocument(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('https://gestoria.miagentuca.es/classify', {
    method: 'POST',
    body: formData
  });

  return await response.json();
}

// Usage with file input
document.getElementById('pdf-input').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (file && file.type === 'application/pdf') {
    const result = await classifyDocument(file);
    console.log(result);
    // result.document_type = "factura", "nomina", "contrato", etc.
    // result.extracted_data = { invoice_number, date, amount, etc. }
  }
});
```

### Response Format
```json
{
  "success": true,
  "document_type": "factura",
  "confidence": 95,
  "extracted_data": {
    "invoice_number": "FAC-2026-001",
    "date": "15/01/2026",
    "company_name": "Empresa SL",
    "total_amount": "1.234,56 EUR"
  },
  "notes": "Additional context about the document",
  "error": null
}
```

### Supported Document Types
- `factura` - Invoice
- `albarán` - Delivery note
- `presupuesto` - Quote
- `contrato` - Contract
- `nómina` - Payroll
- `recibo` - Receipt
- `certificado` - Certificate
- `otro` - Other

---

## 2. Compras - Purchase Agent

**Describe a product → Get supplier comparison and recommendations**

### Endpoint
```
POST https://compras.miagentuca.es/search
Content-Type: application/json
```

### JavaScript Example
```javascript
async function searchSuppliers(product, quantity = 1, urgency = 'normal') {
  const response = await fetch('https://compras.miagentuca.es/search', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      product: product,
      quantity: quantity,
      urgency: urgency  // 'normal', 'urgent', 'very_urgent'
    })
  });

  return await response.json();
}

// Usage
const result = await searchSuppliers('100 tornillos de 6mm acero inoxidable', 100, 'normal');
console.log(result.recommendations.best_price);  // "Würth España"
console.log(result.suppliers);  // Array of supplier options
```

### Response Format
```json
{
  "success": true,
  "product_parsed": {
    "name": "Tornillos hexagonales 6mm acero inoxidable",
    "specifications": "M6, DIN 933",
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
  },
  "error": null
}
```

---

## 3. Explain - Agent Architecture Generator

**Describe a business process → Get complete agent specification**

### Endpoint
```
POST https://explain.miagentuca.es/explain
Content-Type: application/json
```

### JavaScript Example
```javascript
async function explainProcess(description, language = 'es') {
  const response = await fetch('https://explain.miagentuca.es/explain', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      process_description: description,
      language: language  // 'es' or 'en'
    })
  });

  return await response.json();
}

// Usage
const result = await explainProcess(
  'Automatizar el envío de emails de bienvenida cuando un cliente se registra'
);

console.log(result.process_analysis);  // { goal, inputs, outputs, complexity }
console.log(result.directive);         // Markdown SOP document
console.log(result.execution_code);    // Python code skeleton
console.log(result.flowchart);         // Mermaid diagram
```

### Response Format
```json
{
  "success": true,
  "process_analysis": {
    "goal": "Enviar emails de bienvenida personalizados",
    "inputs": ["datos_cliente", "plantilla_email", "config_smtp"],
    "outputs": ["email_enviado", "log_auditoria"],
    "complexity": "medium"
  },
  "directive": "# Directiva del Agente\n\n## Propósito\n...",
  "execution_code": "#!/usr/bin/env python3\n...",
  "flowchart": "flowchart TB\n    subgraph L1[Capa 1: Directiva]\n...",
  "implementation_notes": "Implementación estimada: 2-3 días...",
  "error": null
}
```

### Rendering the Flowchart
The `flowchart` field contains Mermaid syntax. To render it:

```html
<!-- Include Mermaid.js -->
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>

<div class="mermaid" id="flowchart-container"></div>

<script>
  mermaid.initialize({ startOnLoad: false });

  // After getting the API response
  document.getElementById('flowchart-container').innerHTML = result.flowchart;
  mermaid.init(undefined, '#flowchart-container');
</script>
```

---

## Health Check Endpoints

All services have health check endpoints:

```javascript
// Check if services are available
async function checkHealth() {
  const services = [
    'https://gestoria.miagentuca.es/health',
    'https://compras.miagentuca.es/health',
    'https://explain.miagentuca.es/health'
  ];

  for (const url of services) {
    try {
      const response = await fetch(url);
      const data = await response.json();
      console.log(url, data.status);  // "healthy"
    } catch (error) {
      console.error(url, 'unavailable');
    }
  }
}
```

---

## Rate Limiting

All endpoints are rate-limited to **5 requests per minute per IP address**.

If exceeded, you'll receive:
```json
{
  "detail": "Rate limit exceeded: 5 per 1 minute"
}
```

**Recommendation:** Add UI feedback when rate limit is hit:
```javascript
if (response.status === 429) {
  showMessage('Has alcanzado el límite de solicitudes. Espera un minuto.');
}
```

---

## Error Handling

All APIs return consistent error formats:

```javascript
async function callAPI(url, options) {
  try {
    const response = await fetch(url, options);

    if (!response.ok) {
      if (response.status === 429) {
        throw new Error('Rate limit exceeded. Please wait a minute.');
      }
      if (response.status === 503) {
        throw new Error('Service temporarily unavailable.');
      }
      throw new Error(`HTTP error: ${response.status}`);
    }

    const data = await response.json();

    if (!data.success) {
      throw new Error(data.error || 'Unknown error');
    }

    return data;
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
}
```

---

## File Size Limits

For the Gestoría (document classifier):
- **Maximum file size:** 2MB
- **Accepted format:** PDF only

```javascript
function validateFile(file) {
  const maxSize = 2 * 1024 * 1024; // 2MB

  if (file.size > maxSize) {
    throw new Error('El archivo es demasiado grande. Máximo 2MB.');
  }

  if (file.type !== 'application/pdf') {
    throw new Error('Solo se aceptan archivos PDF.');
  }

  return true;
}
```

---

## CORS

CORS is enabled for all origins (`*`), so you can call these APIs directly from your GitHub Pages site without any proxy.

---

## Interactive API Documentation

For testing and exploring the APIs:
- https://gestoria.miagentuca.es/docs
- https://compras.miagentuca.es/docs
- https://explain.miagentuca.es/docs

---

## Summary

| API | Method | Endpoint | Input |
|-----|--------|----------|-------|
| Gestoría | POST | `/classify` | `multipart/form-data` with PDF file |
| Compras | POST | `/search` | JSON: `{ product, quantity, urgency }` |
| Explain | POST | `/explain` | JSON: `{ process_description, language }` |

All responses are JSON with a `success` boolean and relevant data fields.
