# Directive: Document Parser & Extractor

## Purpose

Parse any document using LandingAI's Agentic Document Extraction (ADE) and optionally extract structured key-value pairs using a user-defined JSON schema. Supports PDFs, images, text documents, presentations, and spreadsheets.

## Input

- **Document file**: PDF, image (JPEG, JPG, PNG, APNG, BMP, DCX, DDS, DIB, GD, GIF, ICNS, JP2, PCX, PPM, PSD, TGA, TIF, TIFF, WEBP), text document (DOC, DOCX, ODT), presentation (ODP, PPT, PPTX), or spreadsheet (CSV, XLSX). Max 5MB.
- **Schema** (optional): JSON schema defining fields to extract from the document

## Process

### Step 1: Validate Input
- Check file extension against supported ADE file types (see docs.landing.ai/ade/ade-file-types)
- Check file size does not exceed MAX_FILE_SIZE_MB
- Save to temporary file for processing

### Step 2: Parse Document
- Tool: `execution/ade_client.py` → `parse_document()`
- API: `LandingAIADE.parse(document, model="dpt-2-latest")`
- Returns: structured markdown, chunk list with types, bounding boxes, metadata
- Chunk types: `chunkText`, `chunkTable`, `chunkFigure`, `chunkLogo`, `chunkMarginalia`, `chunkCard`, `chunkAttestation`, `chunkScanCode`, `chunkForm`, `tableCell`

### Step 3: Extract Fields (if schema provided)
- Tool: `execution/ade_client.py` → `extract_fields()`
- API: `LandingAIADE.extract(schema, markdown, model="extract-latest")`
- Returns: extracted values + metadata with source chunk references (visual grounding)

### Step 4: Return Structured Response
- Parsing results: markdown, page count, chunk count, chunk summary
- Extraction results (if schema was provided): field values + grounding metadata

## Output

```json
{
  "success": true,
  "parsing": {
    "markdown": "full document markdown with chunk ID anchors",
    "total_pages": 1,
    "total_chunks": 23,
    "chunk_summary": {"chunkText": 14, "chunkTable": 2},
    "duration_ms": 50375,
    "chunks": [
      {
        "id": "uuid-string",
        "type": "chunkText",
        "markdown": "<a id='uuid'></a>\n\nChunk content...",
        "grounding": {
          "page": 0,
          "box": {"top": 0.01, "bottom": 0.09, "left": 0.29, "right": 0.52}
        }
      }
    ],
    "grounding": {
      "uuid-string": {"page": 0, "type": "chunkText", "box": {"top": 0.01, "bottom": 0.09, "left": 0.29, "right": 0.52}},
      "0-a": {"page": 0, "type": "tableCell", "box": {"top": 0.30, "bottom": 0.35, "left": 0.05, "right": 0.25}}
    },
    "page_images": [
      {"page": 0, "image_base64": "iVBOR...", "mime_type": "image/png"}
    ]
  },
  "extraction": {
    "fields": {"account_summary": {"current_charges": 155.15}},
    "metadata": {"account_summary.current_charges": {"references": ["0-d"]}}
  },
  "error": null
}
```

## Edge Cases

- **Scanned/image-only PDFs**: ADE handles these natively (vision-first approach)
- **Large tables (1000+ cells)**: ADE processes visually, avoiding LLM hallucination
- **Handwritten text**: Supported, including checkboxes and circled selections
- **Illustration-only documents**: Use model `dpt-1-latest` for better results
- **Invalid schema JSON**: Return error before calling extraction API
- **Empty document**: Return success with empty markdown and zero chunks
- **API rate limits**: ADE free tier has 1000 credits; monitor usage

## Rate Limiting

- 3 requests per minute, 20 per day per IP
- Proxy-aware (extracts real IP from X-Forwarded-For behind Traefik)

## Security

- Uploaded files saved to temp directory, deleted after processing
- No file contents logged (only filename, size, result status)
- API key stored in environment, never exposed in responses
