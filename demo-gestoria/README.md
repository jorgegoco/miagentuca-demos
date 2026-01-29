# Demo Gestoría - Document Classifier

Automatic classification and data extraction for Spanish accounting documents (facturas, albaránes, presupuestos, contratos, nóminas, recibos, certificados).

## Overview

This demo showcases the 3-layer architecture for AI agents:

1. **Directive Layer** (`directives/classify_document.md`) - Document classification rules and extraction specifications
2. **Execution Layer** (`execution/pdf_parser.py`) - Deterministic PDF text extraction
3. **Orchestration Layer** (`orchestration/classify_endpoint.py`) - Intelligent classification using Claude API

## Features

- ✅ Supports 8 Spanish document types
- ✅ Extracts type-specific information (amounts, dates, companies, etc.)
- ✅ Returns confidence scores
- ✅ Rate limiting (3 requests/minute + 20/day per IP)
- ✅ 2MB file size limit
- ✅ Handles edge cases (corrupted files, scanned images, etc.)

## Quick Start

### 1. Configure Environment

```bash
# Edit .env file
nano .env

# Add your Anthropic API key
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### 2. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Run the Server

```bash
# Start development server
python orchestration/classify_endpoint.py
```

The API will be available at:
- **API**: https://gestoria.miagentuca.es
- **Docs**: https://gestoria.miagentuca.es/docs
- **Health**: https://gestoria.miagentuca.es/health

## API Usage

### Classify Document

**Endpoint:** `POST /classify`

**Request:**
```bash
curl -X POST "http://localhost:8001/classify" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/document.pdf"
```

**Response:**
```json
{
  "success": true,
  "document_type": "factura",
  "confidence": 92,
  "extracted_data": {
    "invoice_number": "FAC-2024-001",
    "date": "2024-01-15",
    "company": "Suministros García SL",
    "total_amount": "1,234.56"
  }
}
```

## Document Types Supported

| Type | Spanish | Extracts |
|------|---------|----------|
| Invoice | Factura | Number, date, company, amounts, tax |
| Delivery Note | Albarán | Number, date, supplier, items |
| Quote | Presupuesto | Number, date, validity, amount |
| Contract | Contrato | Type, parties, dates, terms |
| Payroll | Nómina | Employee, period, salaries |
| Receipt | Recibo | Date, amount, concept |
| Certificate | Certificado | Type, issued to, authority |
| Other | Otro | Best guess description |

## Configuration

Edit `.env` file:

```bash
# Anthropic API
ANTHROPIC_API_KEY=sk-ant-xxxxx

# Server config
HOST=0.0.0.0
PORT=8001

# Rate limiting
RATE_LIMIT=3/minute;20/day
MAX_FILE_SIZE_MB=2
```

## License

Private demo - All rights reserved
