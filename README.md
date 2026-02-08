# MiAgentUCA - Interactive AI Demos

Interactive demos showcasing AI agent capabilities for [miagentuca.es](https://miagentuca.es/).

## Live Demos

| Demo | URL | Description |
|------|-----|-------------|
| **Gestoría** | [gestoria.miagentuca.es](https://gestoria.miagentuca.es) | Document classifier for Spanish accounting |
| **Compras** | [compras.miagentuca.es](https://compras.miagentuca.es) | Universal purchase agent (auto-detects product category) |
| **Explain** | [explain.miagentuca.es](https://explain.miagentuca.es) | Meta demo - shows how we build AI agents |
| **ADE Parse** | [ade-parse.miagentuca.es](https://ade-parse.miagentuca.es) | Document parser & field extractor (LandingAI ADE) |
| **ADE Pipeline** | [ade-pipeline.miagentuca.es](https://ade-pipeline.miagentuca.es) | Loan application document pipeline (LandingAI ADE) |

## Architecture

All demos follow a **3-layer architecture** that separates concerns for maximum reliability:

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: DIRECTIVE                                     │
│  Natural language SOPs in Markdown                      │
│  What to do, rules, edge cases                          │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 2: ORCHESTRATION                                 │
│  AI-powered decision making (Claude API)                │
│  Intelligent routing, error handling                    │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 3: EXECUTION                                     │
│  Deterministic Python scripts                           │
│  Reliable, testable, fast                               │
└─────────────────────────────────────────────────────────┘
```

**Why this works:** If you do everything with AI, errors compound. 90% accuracy per step = 59% success over 5 steps. Our solution pushes complexity into deterministic code, so AI focuses only on decision-making.

## Demos Overview

### Gestoría - Document Classifier
Upload a PDF document → AI classifies document type → Extracts key information

**Supported document types:**
- Facturas (invoices)
- Albaranes (delivery notes)
- Presupuestos (quotes)
- Contratos (contracts)
- Nóminas (payroll)
- Recibos (receipts)
- Certificados (certificates)

**API:** `POST https://gestoria.miagentuca.es/classify`

---

### Compras - Purchase Agent
Describe what you need → AI auto-detects category → Searches appropriate suppliers → Returns price comparison

**Examples:** "1 paquete de folios A4", "100 tornillos M6 inox", "caja guantes de nitrilo"

**Features:**
- Auto-detects product category (office, tech, hospitality, cleaning, construction...)
- Selects appropriate Spanish suppliers per category (Lyreco, PcComponentes, Makro, Würth...)
- Compares prices with realistic market ranges and confidence levels
- Urgency-aware recommendations (normal, urgent, very_urgent)
- Procurement strategy and actionable buying tips
- Recommends best price, fastest delivery, best value

**API:** `POST https://compras.miagentuca.es/search`

---

### Explain Agent - Meta Demo
Describe a business process → AI generates a structured DOE (Directive-Orchestration-Execution) specification

**Generates:**
- Process analysis (goal, inputs, outputs, complexity)
- Directive summary (SOP approach overview)
- Steps with DOE layer labels (directive / orchestration / execution)
- Execution capabilities (real APIs and tools needed)
- Edge cases and how the agent handles them
- Implementation estimate and notes

This demo shows potential clients exactly how we build AI solutions — every step is visible and labeled with its architectural layer.

**API:** `POST https://explain.miagentuca.es/explain`

---

### ADE Parse - Document Parser & Extractor
Upload any document (PDF or image) → Vision-first AI parses the content → Optionally extract structured fields using a JSON schema

**Capabilities:**
- Parses documents into structured markdown with chunk detection (text, tables, figures, logos, forms, signatures)
- Handles difficult documents: handwritten forms, charts, tables with missing gridlines, stamps, math notation
- Optional field extraction using custom JSON schemas with visual grounding (source references)
- Vision-first approach — understands layout and spatial relationships, not just text

**Powered by:** LandingAI Agentic Document Extraction (DPT-2 model)

**API:** `POST https://ade-parse.miagentuca.es/parse`

---

### ADE Pipeline - Loan Application Processor
Upload multiple financial documents → Auto-classify each document type → Extract type-specific fields → Cross-validate across all documents

**Supported document types:**
- Government ID (passport, driver's license)
- W-2 tax forms
- Pay stubs
- Bank statements
- Investment statements

**Validation checks:**
- Name matching across all documents
- Document year/recency verification
- Total asset calculation (bank + investment balances)

**Use case:** Banks, fintech, insurance — automate document intake for loan applications, KYC, claims processing

**Powered by:** LandingAI Agentic Document Extraction (DPT-2 model)

**API:** `POST https://ade-pipeline.miagentuca.es/process`

## Tech Stack

- **Backend:** FastAPI + Python 3.12
- **AI:** Anthropic Claude API + LandingAI ADE (document understanding)
- **Deployment:** Docker + Easypanel on Contabo VPS
- **Rate Limiting:** SlowAPI (3 requests/minute + 20/day per IP)
- **SSL:** Let's Encrypt (via Traefik)

## Repository Structure

```
miagentuca-demos/
├── CLAUDE.md                  # Master methodology (local only)
├── README.md                  # This file
├── demo-gestoria/             # Document classifier
│   ├── directives/            # Layer 1: SOPs
│   ├── execution/             # Layer 3: Python scripts
│   ├── orchestration/         # Layer 2: FastAPI + AI
│   └── Dockerfile
├── demo-compras/              # Purchase agent
│   ├── directives/
│   ├── execution/
│   ├── orchestration/
│   └── Dockerfile
├── demo-explain-agent/        # Meta demo
│   ├── directives/
│   ├── execution/
│   ├── orchestration/
│   └── Dockerfile
├── demo-ade-parse/            # Document parser (LandingAI ADE)
│   ├── directives/
│   ├── execution/
│   ├── orchestration/
│   └── Dockerfile
└── demo-ade-pipeline/         # Loan application pipeline (LandingAI ADE)
    ├── directives/
    ├── execution/
    ├── orchestration/
    └── Dockerfile
```

## API Documentation

Each demo has interactive API documentation:

- https://gestoria.miagentuca.es/docs
- https://compras.miagentuca.es/docs
- https://explain.miagentuca.es/docs
- https://ade-parse.miagentuca.es/docs
- https://ade-pipeline.miagentuca.es/docs

## Security

- Rate limiting: 3 requests/minute + 20/day per IP (proxy-aware)
- File size limits: 2MB for gestoria, 5MB for ADE services
- CORS restricted to miagentuca.es and demo subdomains
- HTTPS enforced via Traefik

## License

Private repository - All rights reserved

---

Built with the [3-Layer AI Architecture](https://miagentuca.es) by MiAgentUCA
