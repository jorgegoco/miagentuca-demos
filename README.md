# MiAgentUCA - Interactive AI Demos

Interactive demos showcasing AI agent capabilities for [miagentuca.es](https://miagentuca.es/).

## Live Demos

| Demo | URL | Description |
|------|-----|-------------|
| **Gestoría** | [gestoria.miagentuca.es](https://gestoria.miagentuca.es) | Document classifier for Spanish accounting |
| **Compras** | [compras.miagentuca.es](https://compras.miagentuca.es) | Universal purchase agent (auto-detects product category) |
| **Explain** | [explain.miagentuca.es](https://explain.miagentuca.es) | Meta demo - shows how we build AI agents |

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

## Tech Stack

- **Backend:** FastAPI + Python 3.12
- **AI:** Anthropic Claude API
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
└── demo-explain-agent/        # Meta demo
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

## Security

- Rate limiting: 3 requests/minute + 20/day per IP (proxy-aware)
- File size limits: 2MB max for uploads
- CORS restricted to miagentuca.es and demo subdomains
- HTTPS enforced via Traefik

## License

Private repository - All rights reserved

---

Built with the [3-Layer AI Architecture](https://miagentuca.es) by MiAgentUCA
