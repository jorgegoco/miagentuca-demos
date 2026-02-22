# Directive: Multi-Document Research Chatbot Pipeline

## Goal

Run a self-hosted chatbot that lets users have multi-turn conversations over a library of PDF research papers. The system pre-loads 8 medical papers at startup, accepts additional uploads, stores everything in ChromaDB, and uses a Strands Agent (backed by the Anthropic API) to answer questions with cited sources and visual grounding (cropped PNG images of the exact chunk in the PDF).

---

## Inputs

| Input | Source | Notes |
|-------|--------|-------|
| PDF file | `/ingest` endpoint or `data/medical/` folder | Max 20MB, PDF only |
| User message | `/chat` endpoint body | Natural language question |
| `session_id` | `/chat` endpoint body | UUID v4; created by client on first message |
| `doc_id_filter` | `/chat` optional param | Restrict retrieval to one document |
| `top_k` | `/chat` optional param | How many chunks to retrieve (default: 5) |
| `threshold` | `/chat` optional param | Minimum similarity score (default: 0.25) |

---

## Tools / Scripts to Use (in order)

### Ingest flow: `ade_client` → `embedding_client` → `chroma_store`

1. **`execution/ade_client.py`** — `parse_document(file_path)` → chunks (chunk_id, chunk_type, text, bbox, page)
2. **`execution/embedding_client.py`** — `embed_texts(texts)` → list of 1536-dim vectors (OpenAI text-embedding-3-small)
3. **`execution/chroma_store.py`** — `add_chunks(chunks, embeddings, doc_id, doc_name)` → stores with metadata

### Chat flow: `chroma_store` → `agent_client` → `image_client`

4. **`execution/chroma_store.py`** — `query_similar(query_embedding, top_k, threshold, doc_id_filter)` — called internally by the agent's retrieval tool
5. **`execution/agent_client.py`** — `chat(messages, doc_id_filter, top_k, threshold)` → answer text + source chunks
6. **`execution/image_client.py`** — `get_chunk_image(pdf_path, page, bbox, chunk_id)` → PNG filename for StaticFiles URL

---

## Outputs

### `/ingest` response
```json
{
  "success": true,
  "doc_id": "uuid4",
  "doc_name": "my_paper.pdf",
  "already_indexed": false,
  "parsing": {
    "total_pages": 12,
    "total_chunks": 87,
    "chunk_summary": {"chunkText": 60, "chunkTable": 15, "chunkFigure": 12},
    "parse_duration_ms": 8200
  },
  "indexing": {
    "chunks_embedded": 85,
    "chunks_skipped": 2,
    "embedding_duration_ms": 1400
  }
}
```

### `/chat` response
```json
{
  "success": true,
  "session_id": "uuid4",
  "answer": "Based on the research, vitamin C reduces cold duration by...",
  "sources": [
    {
      "chunk_id": "abc-123",
      "doc_id": "uuid4",
      "doc_name": "Vitamin_C_for_Preventing_and_Treating_the_Common_Cold.pdf",
      "chunk_type": "chunkText",
      "page": 4,
      "similarity": 0.84,
      "text_preview": "In a meta-analysis of 29 trials...",
      "bbox": {"x0": 0.05, "y0": 0.30, "x1": 0.95, "y1": 0.55},
      "chunk_image_url": "/static/chunk-images/abc-123.png"
    }
  ],
  "retrieval_info": {
    "chunks_searched": 743,
    "chunks_returned": 3,
    "doc_id_filter": null
  }
}
```

---

## Endpoint Summary

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Service health + API key checks + total chunk count |
| GET | `/status` | Library stats: doc count, total chunks, per-doc details |
| POST | `/ingest` | Upload PDF → parse → embed → store |
| GET | `/documents` | List all indexed documents |
| DELETE | `/documents/{doc_id}` | Remove one document's chunks from ChromaDB |
| POST | `/chat` | Multi-turn chat: question → retrieval → agent answer + sources |
| GET | `/sessions/{session_id}` | Get message history for a session |
| DELETE | `/sessions/{session_id}` | Clear a session |
| GET | `/static/chunk-images/{filename}` | Serve PNG crop images |

---

## Edge Cases & Handling

| Case | Handling |
|------|---------|
| Duplicate PDF (same filename already indexed) | Return 200 with `already_indexed: true`, skip re-ingestion |
| Empty chunks from ADE | Filter out before embedding; log count of skipped chunks |
| ADE parse failure | Return 500 with `success: false` and error message |
| OpenAI embedding failure | Retry up to 3x with exponential backoff (built into embedding_client) |
| Session not found on `/sessions/{id}` | Return 404 |
| Session expired (>2h TTL) | Auto-pruned on next `/chat` call; client must start new session |
| Image crop fails (PDF missing or bbox invalid) | Log warning, set `chunk_image_url: null` in source — do not fail the whole chat response |
| Agent returns no sources | Return answer with empty `sources` array; do not error |
| File too large | Return 413 with clear message |
| Non-PDF file | Return 400 with clear message |
| ChromaDB write conflict (concurrent ingest) | asyncio.Lock on ingest — only one at a time |

---

## Session Management Rules

- Session ID: UUID v4, created by the **client** before first message
- Storage: In-memory Python dict (no database needed for demos)
- TTL: 2 hours from last activity (`last_active` updated on every `/chat` call)
- Pruning: Expired sessions removed lazily on each `/chat` call
- Message format: `[{"role": "user"|"assistant", "content": "..."}]` — full history passed to agent on each turn
- Max sessions: No hard limit for demo use; TTL prevents unbounded growth

---

## Pre-load Strategy (`scripts/preload.py`)

Runs **before** uvicorn starts (see Dockerfile CMD).

1. Check env var `PRELOAD_ENABLED` (default: `true`) — skip if false
2. For each PDF in `data/medical/`:
   - Call `chroma_store.document_exists(filename)` — skip if already indexed (idempotent)
   - Otherwise run the full ingest pipeline (parse → embed → store)
   - Log progress: `"[PRELOAD] Ingesting paper 3/8: Vitamin_C...pdf"`
3. Log total: `"[PRELOAD] Done. 8/8 papers indexed. Total chunks: 743"`

**Expected runtime:** ~10–12 minutes on first boot (8 PDFs through ADE + OpenAI embeddings).
**Subsequent boots:** ~2 seconds (all papers already indexed in ChromaDB volume).

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `VISION_AGENT_API_KEY` | required | LandingAI ADE for PDF parsing |
| `OPENAI_API_KEY` | required | OpenAI embeddings |
| `ANTHROPIC_API_KEY` | required | Anthropic API (tool_use agent loop) |
| `ADE_ENVIRONMENT` | `eu` | LandingAI region |
| `PORT` | `8007` | FastAPI port |
| `MAX_FILE_SIZE_MB` | `20` | Upload size limit |
| `PRELOAD_ENABLED` | `true` | Run preload.py on startup |
| `SESSION_TTL_HOURS` | `2` | Session expiry |
| `CHROMA_DB_PATH` | `/app/chroma_data` | ChromaDB persistence (mount as volume) |
| `UPLOADED_PDFS_DIR` | `/app/uploaded_pdfs` | Store original PDFs for image generation |
| `CHUNK_IMAGES_DIR` | `/app/chunk_images` | PNG crop cache |

---

## Volumes (Easypanel)

| Volume name | Mount point | Purpose |
|-------------|-------------|---------|
| `chatbot-chroma-data` | `/app/chroma_data` | ChromaDB persistence across restarts |
| `chatbot-uploaded-pdfs` | `/app/uploaded_pdfs` | Original PDFs (needed for image cropping) |
| `chatbot-chunk-images` | `/app/chunk_images` | PNG crop cache (avoids re-rendering) |

---

## Known Constraints / Learnings

- **ADE parsing is slow** (~60–90s per PDF). Pre-load makes the demo instant for users.
- **ChromaDB is single-process**: use `asyncio.Lock` around writes (ingest) to avoid corruption.
- **PyMuPDF on Docker**: requires `libmupdf-dev` system package in Dockerfile.
- **Strands AnthropicModel**: uses `anthropic` Python package under the hood. Ensure `ANTHROPIC_API_KEY` is set.
- **Session memory is not persisted**: if the container restarts, all active sessions are lost. This is acceptable for demos.
- **Image crop cache**: PNG files in `CHUNK_IMAGES_DIR` persist in the Docker volume. No need to re-render if `{chunk_id}.png` already exists.
