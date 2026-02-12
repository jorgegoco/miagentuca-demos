# Directive: RAG Pipeline - Document Q&A

## Purpose

Upload a document, parse it into chunks using LandingAI ADE, embed chunks into a ChromaDB vector database, and answer natural-language questions using semantic retrieval + Claude LLM generation. Supports PDFs, images, text documents, presentations, and spreadsheets.

## Input

- **Document file**: PDF, image (JPEG, JPG, PNG, etc.), text document (DOC, DOCX, ODT), presentation (ODP, PPT, PPTX), or spreadsheet (CSV, XLSX). Max 10MB.
- **Question**: Natural language question about the document.
- **Parameters** (optional): `top_k` (max results, default 3), `threshold` (min similarity, default 0.25), `chunk_type_filter` (e.g. "chunkTable").

## Process

### Step 1: Ingest - Validate and Parse
- Check file extension against supported ADE file types
- Check file size does not exceed MAX_FILE_SIZE_MB
- Save to temporary file for processing
- Tool: `execution/ade_client.py` -> `parse_document()`
- Returns: markdown, chunk list with chunk_id, chunk_type, text, bbox, page

### Step 2: Ingest - Embed and Index
- Filter out empty chunks (no text content)
- Batch-embed chunk texts using OpenAI text-embedding-3-small (1536-dim vectors)
- Tool: `execution/embedding_client.py` -> `embed_texts()`
- Clear previous ChromaDB collection (single-document-at-a-time design)
- Store chunks + embeddings + flat metadata (chunk_type, page, bbox_x0/y0/x1/y1)
- Tool: `execution/chroma_store.py` -> `clear_collection()`, `add_chunks()`
- Save document metadata (name, pages, chunks, summary) as JSON sidecar

### Step 3: Query - Retrieve
- Embed the question using same embedding model
- Tool: `execution/embedding_client.py` -> `embed_text()`
- Query ChromaDB for top_k nearest neighbors by L2 distance
- Filter by similarity threshold (similarity = 1 - L2 distance)
- Optionally filter by chunk_type metadata (hybrid search)
- Tool: `execution/chroma_store.py` -> `query_similar()`

### Step 4: Query - Generate
- Build context string from retrieved chunks with source labels
- Send question + context to Claude Haiku 4.5
- System prompt: "Use the following pieces of retrieved context to answer the user's question. If you don't know the answer, say that you don't know."
- Tool: `execution/llm_client.py` -> `generate_answer()`

### Step 5: Return Response
- Ingest: parsing stats + indexing stats
- Query: answer + source chunks with similarity scores and bbox for visual grounding

## Output

### Ingest Response
```json
{
  "success": true,
  "document_name": "report.pdf",
  "parsing": {
    "total_pages": 10,
    "total_chunks": 45,
    "chunk_summary": {"chunkText": 30, "chunkTable": 10, "chunkFigure": 5},
    "parse_duration_ms": 12345
  },
  "indexing": {
    "chunks_embedded": 43,
    "chunks_skipped": 2,
    "embedding_duration_ms": 3456
  }
}
```

### Query Response
```json
{
  "success": true,
  "question": "What was the total revenue?",
  "answer": "The total revenue was $383,285 million...",
  "sources": [
    {
      "chunk_id": "abc-123",
      "chunk_type": "chunkTable",
      "page": 42,
      "similarity": 0.847,
      "text_preview": "Net sales: ...",
      "bbox": {"x0": 0.05, "y0": 0.30, "x1": 0.95, "y1": 0.60}
    }
  ],
  "retrieval_info": {
    "chunks_searched": 45,
    "chunks_returned": 2,
    "top_k": 3,
    "threshold": 0.25
  }
}
```

## Edge Cases

- **Scanned/image-only PDFs**: ADE handles these natively (vision-first approach)
- **Large tables**: ADE processes visually, chunk_type "chunkTable" enables hybrid search filtering
- **Empty document**: Return success with warning, zero chunks indexed
- **Very short documents (<3 chunks)**: Return success with warning about limited RAG effectiveness
- **No relevant results**: Query returns empty sources; Claude responds "I don't know"
- **Concurrent ingest requests**: Serialized via asyncio.Lock to prevent ChromaDB corruption
- **Embedding API failure mid-batch**: Retry up to 3 times with exponential backoff
- **API rate limits**: ADE free tier has 1000 credits; OpenAI embeddings ~$0.02/1M tokens

## Rate Limiting

- Ingest: 3 requests per minute, 10 per day per IP
- Query: 5 requests per minute, 30 per day per IP
- Proxy-aware (extracts real IP from X-Forwarded-For behind Traefik)

## Security

- Uploaded files saved to temp directory, deleted immediately after processing
- No file contents logged (only filename, size, result status)
- API keys stored in environment, never exposed in responses
- ChromaDB persisted to Docker volume, not in repository
