# Demo ADE Parse - Document Parser & Extractor

Upload any document and get structured markdown back. Optionally pass a JSON schema to extract specific fields with source references. Powered by [LandingAI Agentic Document Extraction (ADE)](https://docs.landing.ai/ade/ade-overview).

## Live Demo

**URL:** [ade-parse.miagentuca.es](https://ade-parse.miagentuca.es)

**Interactive API docs:** [ade-parse.miagentuca.es/docs](https://ade-parse.miagentuca.es/docs)

## How to Use It

The service has one main endpoint. Send a document and get parsed markdown. Add a `schema` field to also extract structured data.

### Parse only

```bash
curl -X POST "https://ade-parse.miagentuca.es/parse" \
  -F "file=@invoice.pdf"
```

### Parse + extract fields

```bash
curl -X POST "https://ade-parse.miagentuca.es/parse" \
  -F "file=@invoice.pdf" \
  -F 'schema={
    "type": "object",
    "properties": {
      "invoice_number": {"type": "string", "description": "Invoice or document number"},
      "total_amount": {"type": "number", "description": "Total amount including tax"},
      "vendor_name": {"type": "string", "description": "Name of the vendor or issuer"}
    },
    "required": ["invoice_number", "total_amount"]
  }'
```

## Inputs

**Endpoint:** `POST /parse` (`multipart/form-data`)

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | file | Yes | Document to parse. Max 5 MB. |
| `schema` | string | No | JSON schema defining fields to extract. |

### Supported file types

| Category | Extensions |
|----------|------------|
| PDF | `.pdf` |
| Images | `.jpeg` `.jpg` `.png` `.apng` `.bmp` `.dcx` `.dds` `.dib` `.gd` `.gif` `.icns` `.jp2` `.pcx` `.ppm` `.psd` `.tga` `.tif` `.tiff` `.webp` |
| Text documents | `.doc` `.docx` `.odt` |
| Presentations | `.odp` `.ppt` `.pptx` |
| Spreadsheets | `.csv` `.xlsx` |

> Text documents and presentations are converted to PDF internally by ADE before parsing, which may slightly alter layout.

## Output

### Parse-only response

```json
{
  "success": true,
  "parsing": {
    "markdown": "# Invoice\n\n| Item | Amount |\n|------|--------|\n| Widget | $50 |\n...",
    "total_pages": 1,
    "total_chunks": 8,
    "chunk_summary": {"chunkText": 5, "chunkTable": 2, "chunkLogo": 1},
    "duration_ms": 2340
  },
  "extraction": null,
  "error": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `parsing.markdown` | string | Full document content converted to markdown |
| `parsing.total_pages` | integer | Number of pages detected |
| `parsing.total_chunks` | integer | Number of semantic regions detected |
| `parsing.chunk_summary` | object | Count of each chunk type (see [Chunk types](#chunk-types)) |
| `parsing.duration_ms` | integer | ADE API processing time in milliseconds |

### Parse + extract response

When a `schema` is provided, the response includes an `extraction` object:

```json
{
  "success": true,
  "parsing": {
    "markdown": "...",
    "total_pages": 1,
    "total_chunks": 8,
    "chunk_summary": {"chunkText": 5, "chunkTable": 2, "chunkLogo": 1},
    "duration_ms": 2340
  },
  "extraction": {
    "fields": {
      "invoice_number": "INV-2024-0042",
      "total_amount": 1250.00,
      "vendor_name": "Acme Corp"
    },
    "metadata": {
      "invoice_number": {"references": ["chunk-abc123"]},
      "total_amount": {"references": ["chunk-def456"]},
      "vendor_name": {"references": ["chunk-abc123"]}
    }
  },
  "error": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `extraction.fields` | object | Extracted key-value pairs matching the provided schema |
| `extraction.metadata` | object | Visual grounding — links each field to its source chunk(s) in the document |

### Error responses

```json
{
  "success": false,
  "parsing": null,
  "extraction": null,
  "error": "Unsupported file type '.txt'. Allowed: .pdf, .jpg, .png, ..."
}
```

| HTTP Status | Cause |
|-------------|-------|
| 400 | Unsupported file type |
| 413 | File exceeds 5 MB limit |
| 429 | Rate limit exceeded |

## Extraction Schema Guide

The `schema` parameter accepts a JSON Schema string. ADE uses it to extract specific fields from the parsed markdown.

**Supported features:** `type`, `properties`, `description`, `required`, `enum`, `nullable`, `anyOf`, arrays with `items`, nested objects (up to 5 levels deep).

### Example: extract from a pay stub

```json
{
  "type": "object",
  "properties": {
    "employee_name": {
      "type": "string",
      "description": "Full name of the employee"
    },
    "pay_period": {
      "type": "string",
      "description": "Pay period dates (e.g. Jan 1 - Jan 15, 2024)"
    },
    "gross_pay": {
      "type": "number",
      "description": "Gross pay amount before deductions"
    },
    "deductions": {
      "type": "array",
      "description": "List of deductions applied to gross pay",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string", "description": "Name of the deduction"},
          "amount": {"type": "number", "description": "Deduction amount"}
        }
      }
    },
    "net_pay": {
      "type": "number",
      "description": "Net pay after all deductions"
    }
  },
  "required": ["employee_name", "net_pay"]
}
```

> **Tip:** Write detailed `description` values — they directly influence extraction accuracy. Tell the model what the field looks like in the document, not just what it's called.

## What ADE Can Handle

ADE uses a **vision-first approach**: it treats documents as visual objects rather than running traditional OCR. This means it understands layout, spatial relationships, and visual elements that text extraction misses.

**Difficult documents it handles well:**

- Tables without gridlines or with merged cells
- Mega tables with 1,000+ cells (processed visually, avoids LLM hallucination)
- Handwritten forms, including checkboxes and circled selections
- Charts, flowcharts, and diagrams
- Mathematical notation and equations
- Stamps, signatures, and attestations (curved text included)
- Logos and visual branding
- Scanned/image-only PDFs (no separate OCR step needed)
- Mixed-format pages (text + tables + figures together)

### Models

| Model | Purpose |
|-------|---------|
| `dpt-2-latest` | General document parsing (default) |
| `dpt-1-latest` | Better for illustration-heavy documents (e.g. IKEA instructions) |
| `extract-latest` | Schema-based field extraction from parsed markdown |

### Chunk types

ADE segments documents into typed chunks. The `chunk_summary` field in the response shows what was detected:

| Chunk type | What it represents |
|------------|--------------------|
| `chunkText` | Paragraphs, headings, body text |
| `chunkTable` | Tables (detected visually, not by gridlines) |
| `chunkFigure` | Charts, diagrams, images |
| `chunkLogo` | Logos and visual branding |
| `chunkMarginalia` | Margin notes, headers, footers |
| `chunkCard` | Business cards, ID cards |
| `chunkAttestation` | Stamps, signatures, certifications |
| `chunkScanCode` | QR codes, barcodes |
| `chunkForm` | Form fields, checkboxes |
| `tableCell` | Individual cells within a table |

## Setup

### Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VISION_AGENT_API_KEY` | Yes | -- | LandingAI API key |
| `ADE_ENVIRONMENT` | No | `eu` | ADE region (`eu` or `us`) |
| `HOST` | No | `0.0.0.0` | Server bind address |
| `PORT` | No | `8004` | Server port |
| `DEBUG` | No | `False` | Enable hot reload |
| `RATE_LIMIT` | No | `3/minute;20/day` | Request rate limit per IP |
| `MAX_FILE_SIZE_MB` | No | `5` | Maximum upload file size in MB |

### Local development

```bash
cd demo-ade-parse/
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Set your API key in .env
# VISION_AGENT_API_KEY=land_sk_...

python orchestration/parse_endpoint.py
```

Server starts at `http://localhost:8004`. Interactive docs at `http://localhost:8004/docs`.

### Docker

```bash
docker build -t demo-ade-parse .
docker run -p 8004:8004 -e VISION_AGENT_API_KEY=land_sk_... demo-ade-parse
```

### Production

Deployed on Easypanel (Contabo VPS). Traefik handles HTTPS and routes `ade-parse.miagentuca.es` to the container on port 8004. Real API keys are configured in Easypanel environment variables, not in the repo.

## Rate Limits

| Limit | Value |
|-------|-------|
| Per minute | 3 requests per IP |
| Per day | 20 requests per IP |

Rate limiting is proxy-aware: behind Traefik, the real client IP is extracted from the `X-Forwarded-For` header. When the limit is exceeded, the API returns HTTP 429.
