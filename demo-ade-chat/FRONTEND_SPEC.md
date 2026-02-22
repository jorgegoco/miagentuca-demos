# Frontend Specification: demo-ade-chat

> **For the Claude instance building the frontend.** This document is the complete contract between the live backend and the React app you are about to build. Read it fully before writing a single line of code.

---

## 1. What This App Does

A **multi-document research paper chatbot**. The backend ships with 8 medical research papers already indexed. Users can:

1. Browse the library of indexed papers
2. Upload additional PDFs (they get parsed, embedded, and indexed automatically)
3. Have a multi-turn conversation with an AI that searches the papers and answers questions
4. See exactly **which passage** in **which paper** the answer came from, with a cropped image of that exact section

---

## 2. Backend — Live URLs

| Item | URL |
|------|-----|
| API base | `https://miagentuca-demos-ade-chat.ud2cay.easypanel.host` |
| Interactive API docs (Swagger) | `https://miagentuca-demos-ade-chat.ud2cay.easypanel.host/docs` |
| Health check | `https://miagentuca-demos-ade-chat.ud2cay.easypanel.host/health` |

The API URL must be stored in an env variable: `VITE_API_URL`. Never hardcode it.

```javascript
// src/api/client.js — always use this
const API_URL = import.meta.env.VITE_API_URL
```

---

## 3. Tech Stack

| Layer | Choice |
|-------|--------|
| Framework | React 19 |
| Build tool | Vite |
| Styling | Tailwind CSS v4 |
| Icons | lucide-react |
| File uploads | react-dropzone v15 |
| HTTP | native `fetch` (no axios) |

**Do NOT use:**
- pdfjs-dist (the backend renders PDF crops server-side, frontend uses plain `<img>`)
- Any state management library (React `useState` only)
- Any UI component library (build everything with Tailwind)

**package.json dependencies:**
```json
{
  "dependencies": {
    "lucide-react": "latest",
    "react": "^19",
    "react-dom": "^19",
    "react-dropzone": "^15"
  }
}
```

**index.css:**
```css
@import "tailwindcss";
```

---

## 4. Complete API Reference

### 4.1 GET `/health`
Check service status and API key configuration.

**Response:**
```json
{
  "status": "healthy",
  "ade_configured": true,
  "openai_configured": true,
  "anthropic_configured": true,
  "total_chunks": 758,
  "total_documents": 8,
  "active_sessions": 0,
  "max_file_size_mb": 20
}
```

---

### 4.2 GET `/status`
Library overview — document count and per-document details.

**Response:**
```json
{
  "total_documents": 8,
  "total_chunks": 758,
  "documents": [
    {
      "doc_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "doc_name": "Vitamin_C_for_Preventing_and_Treating_the_Common_Cold.pdf",
      "chunk_count": 94,
      "chunk_summary": { "chunkText": 70, "chunkTable": 12, "chunkFigure": 12 },
      "indexed_at": "2026-02-22T10:30:00Z"
    }
  ]
}
```

---

### 4.3 GET `/documents`
List all indexed documents. Use this to populate the document library UI.

**Response:**
```json
{
  "success": true,
  "documents": [
    {
      "doc_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "doc_name": "Vitamin_C_for_Preventing_and_Treating_the_Common_Cold.pdf",
      "chunk_count": 94,
      "chunk_summary": { "chunkText": 70, "chunkTable": 12, "chunkFigure": 12 },
      "indexed_at": "2026-02-22T10:30:00Z"
    }
  ],
  "total_documents": 8,
  "total_chunks": 758
}
```

---

### 4.4 POST `/ingest`
Upload a PDF to index it. `multipart/form-data`, field name `file`.

**Request:**
```javascript
const formData = new FormData()
formData.append('file', file)
fetch(`${API_URL}/ingest`, { method: 'POST', body: formData })
```

**Response (new document):**
```json
{
  "success": true,
  "doc_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "doc_name": "my_paper.pdf",
  "already_indexed": false,
  "parsing": {
    "total_pages": 12,
    "total_chunks": 87,
    "chunk_summary": { "chunkText": 60, "chunkTable": 15, "chunkFigure": 12 },
    "parse_duration_ms": 8200
  },
  "indexing": {
    "chunks_embedded": 85,
    "chunks_skipped": 2,
    "embedding_duration_ms": 1400
  },
  "error": null
}
```

**Response (duplicate — already indexed):**
```json
{
  "success": true,
  "doc_name": "my_paper.pdf",
  "already_indexed": true,
  "error": null
}
```

**Response (error):**
```json
{
  "success": false,
  "error": "Parse failed: ..."
}
```

**HTTP error codes:**
- `400` — not a PDF
- `413` — file too large (> 20MB)

---

### 4.5 DELETE `/documents/{doc_id}`
Remove a document and all its chunks from the library.

**Request:**
```javascript
fetch(`${API_URL}/documents/${docId}`, { method: 'DELETE' })
```

**Response:**
```json
{
  "success": true,
  "doc_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "chunks_deleted": 94
}
```

---

### 4.6 POST `/chat`
Send a message in a conversation. The agent decides when to search the library.

**Request body:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "What are the main treatments for the common cold?",
  "doc_id_filter": null,
  "top_k": 5,
  "threshold": 0.25
}
```

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `session_id` | string (UUID v4) | yes | — | Create once per conversation with `crypto.randomUUID()` |
| `message` | string | yes | — | The user's question |
| `doc_id_filter` | string \| null | no | `null` | Restrict search to one document |
| `top_k` | int | no | `5` | Max chunks to retrieve |
| `threshold` | float | no | `0.25` | Min similarity score (0–1) |

**Response:**
```json
{
  "success": true,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "answer": "Based on the research, the main treatments for the common cold include...",
  "sources": [
    {
      "chunk_id": "abc-123",
      "doc_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "doc_name": "Prevention_and_treatment_of_the_common_cold.pdf",
      "chunk_type": "chunkText",
      "page": 4,
      "similarity": 0.847,
      "text_preview": "In a randomized controlled trial, vitamin C...",
      "bbox": { "x0": 0.05, "y0": 0.30, "x1": 0.95, "y1": 0.55 },
      "chunk_image_url": "/static/chunk-images/abc-123.png"
    }
  ],
  "retrieval_info": {
    "chunks_searched": 758,
    "chunks_returned": 3,
    "doc_id_filter": null,
    "top_k": 5,
    "threshold": 0.25
  },
  "error": null
}
```

**Important:** `sources` can be an empty array if the agent answered without searching (e.g., conversational follow-up). `chunk_image_url` can be `null` if image rendering failed — always guard against this.

---

### 4.7 GET `/sessions/{session_id}`
Retrieve full message history for a session (useful for debugging, not required for core UX).

**Response:**
```json
{
  "success": true,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "messages": [
    { "role": "user", "content": "What causes the common cold?" },
    { "role": "assistant", "content": "The common cold is primarily caused by..." }
  ],
  "created_at": "2026-02-22T10:30:00Z",
  "last_active": "2026-02-22T10:31:45Z",
  "message_count": 2
}
```

---

### 4.8 DELETE `/sessions/{session_id}`
Clear a session so the user can start a fresh conversation.

**Response:**
```json
{ "success": true, "session_id": "550e8400-e29b-41d4-a716-446655440000" }
```

---

### 4.9 GET `/static/chunk-images/{filename}`
Serve a cropped PNG image of a document chunk. Used via plain `<img>` tag.

**Usage:**
```jsx
<img src={`${API_URL}${source.chunk_image_url}`} alt="source chunk" />
```

`chunk_image_url` from the `/chat` response already includes the `/static/chunk-images/` prefix, so just prepend `API_URL`.

---

## 5. API Client (`src/api/client.js`)

Write all fetch calls here. Components never call `fetch` directly.

```javascript
const API_URL = import.meta.env.VITE_API_URL

export async function getHealth() {
  const res = await fetch(`${API_URL}/health`)
  return res.json()
}

export async function getDocuments() {
  const res = await fetch(`${API_URL}/documents`)
  return res.json()  // { success, documents, total_documents, total_chunks }
}

export async function ingestDocument(file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_URL}/ingest`, { method: 'POST', body: formData })
  return res.json()  // IngestResponse
}

export async function deleteDocument(docId) {
  const res = await fetch(`${API_URL}/documents/${docId}`, { method: 'DELETE' })
  return res.json()
}

export async function sendMessage({ sessionId, message, docIdFilter = null, topK = 5, threshold = 0.25 }) {
  const res = await fetch(`${API_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      doc_id_filter: docIdFilter,
      top_k: topK,
      threshold,
    }),
  })
  return res.json()  // ChatResponse
}

export async function clearSession(sessionId) {
  const res = await fetch(`${API_URL}/sessions/${sessionId}`, { method: 'DELETE' })
  return res.json()
}
```

---

## 6. Component Architecture

```
src/
├── App.jsx                    ← all state, top-level layout, tab switching
├── index.css                  ← @import "tailwindcss";
├── api/
│   └── client.js              ← all fetch calls (see section 5)
└── components/
    ├── StatusBanner.jsx        ← "8 papers / 758 chunks" header stat
    ├── PipelineVisual.jsx      ← 3-phase flow: Ingest → Embed → Agent
    ├── DocumentLibrary.jsx     ← list of indexed docs with delete buttons
    ├── UploadZone.jsx          ← drag-and-drop PDF upload
    ├── IngestResult.jsx        ← result card after successful upload
    ├── DocFilterPanel.jsx      ← dropdown to restrict chat to one document
    ├── ChatPanel.jsx           ← scrollable message thread
    ├── ChatMessage.jsx         ← user/assistant bubble + sources accordion
    ├── ChatSourceCard.jsx      ← chunk card: badge + page + similarity + image
    ├── ChatInput.jsx           ← textarea + send button + advanced options toggle
    ├── SessionControls.jsx     ← "New Chat" button
    ├── ChunkTypeBadge.jsx      ← colored label for chunkText/chunkTable/chunkFigure
    ├── SimilarityBar.jsx       ← small progress bar showing similarity score
    ├── LoadingSpinner.jsx      ← generic spinner
    └── ErrorBanner.jsx         ← dismissable error message
```

---

## 7. App State (`App.jsx`)

```javascript
// Session
const [sessionId, setSessionId] = useState(() => crypto.randomUUID())

// Document library
const [documents, setDocuments] = useState([])
// Shape: [{ doc_id, doc_name, chunk_count, chunk_summary, indexed_at }]

// Chat messages
const [messages, setMessages] = useState([])
// Shape: [{ role: 'user'|'assistant', content: string, sources: [], timestamp: Date }]

// Ingest state
const [ingestFile, setIngestFile] = useState(null)
const [ingestLoading, setIngestLoading] = useState(false)
const [ingestResult, setIngestResult] = useState(null)
const [ingestError, setIngestError] = useState(null)

// Chat state
const [chatLoading, setChatLoading] = useState(false)
const [chatError, setChatError] = useState(null)

// Filters (passed to /chat)
const [docIdFilter, setDocIdFilter] = useState(null)  // null = search all docs
const [topK, setTopK] = useState(5)
const [threshold, setThreshold] = useState(0.25)

// UI
const [activeTab, setActiveTab] = useState('library')  // 'library' | 'chat'
```

**On mount:** call `getDocuments()` and set `documents`.

**After ingest success:** call `getDocuments()` again to refresh the list.

**After delete:** call `getDocuments()` again to refresh the list.

**New chat:** generate a new `sessionId` with `crypto.randomUUID()`, clear `messages`.

---

## 8. Component Specifications

### `StatusBanner.jsx`
**Props:** `{ totalDocuments, totalChunks }`
**Renders:** A banner showing "N papers · M chunks indexed" at the top of the page. Shows a neutral state if `totalDocuments === 0` ("Library indexing in progress…").

---

### `PipelineVisual.jsx`
**Props:** none (static diagram)
**Renders:** A horizontal 3-step flow showing how the pipeline works:
1. **Ingest** — PDF → ADE parse → ChromaDB
2. **Embed** — OpenAI embeddings
3. **Agent** — Claude AI with retrieval tool → answer

Visual only, no interactivity. Helps users understand what's happening under the hood.

---

### `DocumentLibrary.jsx`
**Props:** `{ documents, onDelete, onFilterSelect, activeFilter }`
**Renders:**
- A list/grid of document cards, one per indexed paper
- Each card shows: filename, chunk count, indexed date, chunk type breakdown
- A delete button (trash icon) per card — calls `onDelete(doc_id)`
- A "Filter chat to this doc" button — calls `onFilterSelect(doc_id)`
- Highlight the active filter if `activeFilter === doc.doc_id`
- Empty state if `documents.length === 0`

---

### `UploadZone.jsx`
**Props:** `{ onFileSelect, disabled }`
**Renders:** Drag-and-drop area using `react-dropzone`. Accept `.pdf` only. Shows filename when a file is selected. Calls `onFileSelect(file)` when a file is dropped or chosen.

---

### `IngestResult.jsx`
**Props:** `{ result }` where `result` is the `/ingest` response
**Renders:**
- If `result.already_indexed`: a yellow info banner — "Already indexed"
- If `result.success`: green card showing pages parsed, chunks embedded, parse time, embedding time
- If `!result.success`: red error card with `result.error`

---

### `DocFilterPanel.jsx`
**Props:** `{ documents, activeFilter, onFilterChange }`
**Renders:** A dropdown (or button row) letting the user restrict chat searches to one document. Options: "All documents" (sets filter to `null`) + one entry per doc. Show the active doc name when a filter is selected.

---

### `ChatPanel.jsx`
**Props:** `{ messages, loading }`
**Renders:** Scrollable list of `ChatMessage` components. Auto-scrolls to bottom on new messages. Shows a loading indicator at the bottom when `loading === true`.

---

### `ChatMessage.jsx`
**Props:** `{ message }` where `message = { role, content, sources, timestamp }`
**Renders:**
- **User messages:** right-aligned bubble, slate/gray background
- **Assistant messages:** left-aligned bubble, white background with subtle border
- If `message.sources?.length > 0`: a collapsible "Sources" section below the answer
  - Collapsed by default, click to expand
  - Shows `ChatSourceCard` for each source

---

### `ChatSourceCard.jsx`
**Props:** `{ source }` where source is one item from `response.sources`
**Renders:**
- `ChunkTypeBadge` for `source.chunk_type`
- Document name (truncated if long)
- Page number: `Page {source.page + 1}` (0-indexed from API, show 1-indexed to user)
- `SimilarityBar` for `source.similarity`
- Text preview (2–3 lines, truncated)
- Chunk image — **only if `source.chunk_image_url` is not null:**

```jsx
{source.chunk_image_url && (
  <img
    src={`${API_URL}${source.chunk_image_url}`}
    alt={`${source.doc_name} page ${source.page + 1}`}
    className="rounded-lg border border-slate-200 max-w-full mt-2"
    onError={(e) => { e.currentTarget.style.display = 'none' }}
  />
)}
```

The `onError` handler hides the image silently if it fails to load (don't show broken image icons).

---

### `ChatInput.jsx`
**Props:** `{ onSend, disabled, placeholder }`
**Renders:**
- A multi-line textarea (auto-grows, `Shift+Enter` for newline, `Enter` to send)
- A send button (arrow icon, disabled when `disabled` or input is empty)
- An "Advanced" toggle that reveals `topK` and `threshold` sliders/inputs
- The component calls `onSend(messageText)` — the parent handles all state

---

### `SessionControls.jsx`
**Props:** `{ onNewChat, messageCount }`
**Renders:** A "New Chat" button (with a refresh/plus icon). Shows message count when `messageCount > 0`. Clicking triggers `onNewChat()` which generates a new UUID and clears messages in the parent.

---

### `ChunkTypeBadge.jsx`
**Props:** `{ type }` — one of `"chunkText"`, `"chunkTable"`, `"chunkFigure"`, `"chunkMarginalia"`
**Renders:** A small colored pill badge:
- `chunkText` → green
- `chunkTable` → blue
- `chunkFigure` → purple
- `chunkMarginalia` → orange
- unknown → gray

---

### `SimilarityBar.jsx`
**Props:** `{ score }` — float 0–1
**Renders:** A small horizontal progress bar showing the similarity score as a percentage. Label: `{(score * 100).toFixed(0)}%`. Color: green if > 0.7, yellow if > 0.4, gray otherwise.

---

### `LoadingSpinner.jsx`
**Props:** `{ size? }` — default medium
**Renders:** An animated spinning circle (CSS animation or Tailwind `animate-spin`).

---

### `ErrorBanner.jsx`
**Props:** `{ message, onDismiss }`
**Renders:** Red banner with an X button to dismiss. Shows `message`.

---

## 9. Page Layout

Two-tab layout. The tab bar is always visible at the top.

```
┌─────────────────────────────────────────────────────────────┐
│  StatusBanner  "8 papers · 758 chunks"                      │
├─────────────────────────────────────────────────────────────┤
│  [ Library ]  [ Chat ]   ← tab bar                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  LIBRARY TAB:                                               │
│  ┌──────────────────┐  ┌────────────────────────────────┐  │
│  │  PipelineVisual  │  │  UploadZone                    │  │
│  │  (static diagram)│  │  + IngestResult (if result)    │  │
│  └──────────────────┘  └────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  DocumentLibrary (list of all indexed papers)       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  CHAT TAB:                                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  SessionControls (New Chat button)                   │  │
│  │  DocFilterPanel (restrict to one doc)                │  │
│  │  ChatPanel (scrollable messages)                     │  │
│  │  ChatInput (textarea + send)                         │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 10. Key UX Behaviours

### Ingest flow
1. User drops/selects a PDF in `UploadZone`
2. Parent sets `ingestFile`, shows filename and a "Upload" button
3. On submit: set `ingestLoading = true`, call `ingestDocument(file)`
4. On response: set `ingestResult`, call `getDocuments()` to refresh library
5. If `already_indexed`: show info message, do NOT show error

### Chat flow
1. User types message in `ChatInput` and presses Enter
2. Immediately append `{ role: 'user', content: message }` to `messages` — optimistic update
3. Set `chatLoading = true`
4. Call `sendMessage({ sessionId, message, docIdFilter, topK, threshold })`
5. On response: append `{ role: 'assistant', content: answer, sources }` to `messages`
6. Set `chatLoading = false`
7. Auto-scroll `ChatPanel` to bottom

### New chat
1. Generate new `sessionId` with `crypto.randomUUID()`
2. Clear `messages = []`
3. Clear `chatError = null`
4. Keep `docIdFilter` as-is (user may want to continue with same filter)

### Delete document
1. Show confirmation (simple `window.confirm` is fine)
2. Call `deleteDocument(docId)`
3. If the deleted doc was the active filter, clear `docIdFilter = null`
4. Refresh `documents` with `getDocuments()`

---

## 11. Styling Guidelines

- **Font:** System font stack (no custom fonts needed)
- **Background:** `bg-slate-50` for the page, `bg-white` for cards
- **Primary color:** Indigo (`indigo-600` for buttons, `indigo-50` for active states)
- **User chat bubble:** `bg-indigo-600 text-white` (right-aligned)
- **Assistant chat bubble:** `bg-white border border-slate-200` (left-aligned)
- **Cards:** `rounded-xl shadow-sm border border-slate-200`
- **Tone:** Clean, minimal, professional — this is a demo for potential clients

---

## 12. Environment Variables

Create a `.env.local` for local dev:

```
VITE_API_URL=https://miagentuca-demos-ade-chat.ud2cay.easypanel.host
```

**Never hardcode the API URL.** Always use `import.meta.env.VITE_API_URL`.

---

## 13. Deployment (Vercel)

1. Push the frontend repo to GitHub
2. Import into Vercel
3. Set environment variable: `VITE_API_URL=https://miagentuca-demos-ade-chat.ud2cay.easypanel.host`
4. Deploy — Vercel detects Vite automatically

**Alternative (self-hosted on Easypanel):** Add a Dockerfile to the frontend repo:

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json .
RUN npm install
COPY . .
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

Then in Easypanel: build arg `VITE_API_URL=https://miagentuca-demos-ade-chat.ud2cay.easypanel.host`.

---

## 14. Verification Checklist

Before considering the frontend done, verify every item:

- [ ] `StatusBanner` shows correct paper + chunk counts (fetched from `/documents`)
- [ ] `DocumentLibrary` shows all 8 pre-loaded medical papers
- [ ] Upload a new PDF → appears in library, chunk count updates
- [ ] Upload same PDF again → "already indexed" message (no error)
- [ ] Delete a paper → disappears from library
- [ ] Chat: ask "What causes the common cold?" → get an answer with sources
- [ ] Sources accordion expands showing paper name, page, similarity
- [ ] Chunk image renders inline in source card (not broken)
- [ ] Filter chat to one doc → sources all from that paper only
- [ ] "New Chat" resets conversation (new session, messages cleared)
- [ ] Multi-turn: follow-up question uses prior context ("What did you just say about vitamin C?")
- [ ] `chatLoading` spinner shows while waiting for response
- [ ] Error banner appears if API call fails
- [ ] Works on mobile (responsive layout)

---

## 15. Pre-loaded Research Papers (for reference)

The backend starts with these 8 papers already indexed — users will see them immediately in the library tab without uploading anything:

1. Common_cold_clinincal_evidence.pdf
2. CT_Study_of_the_Common_Cold.pdf
3. Evaluation_of_echinacea_for_the_prevention_and_treatment_of_the_common_cold.pdf
4. Prevention_and_treatment_of_the_common_cold.pdf
5. The_common_cold_a_review_of_the_literature.pdf
6. Understanding_the_symptoms_of_the_common_cold_and_influenza.pdf
7. Viruses_and_Bacteria_in_the_Etiology_of_the_Common_Cold.pdf
8. Vitamin_C_for_Preventing_and_Treating_the_Common_Cold.pdf
