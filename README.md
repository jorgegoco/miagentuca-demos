# MiAgentUCA - Interactive AI Demos

Interactive demos showcasing AI agent capabilities for [miagentuca.es](https://miagentuca.es/).

## Live Demos

| Demo | URL | Description |
|------|-----|-------------|
| **Gestoría** | [gestoria.miagentuca.es](https://gestoria.miagentuca.es) | Document classifier for Spanish accounting |
| **Compras** | [compras.miagentuca.es](https://compras.miagentuca.es) | Purchase agent for hardware procurement |
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
Describe what you need → AI searches suppliers → Returns price comparison and recommendations

**Example:** "100 tornillos de 6mm acero inoxidable"

**Features:**
- Searches Spanish suppliers (Würth, Bricomart, Leroy Merlin Pro, etc.)
- Compares prices, delivery times, minimum orders
- Recommends best price, fastest delivery, best value

**API:** `POST https://compras.miagentuca.es/search`

---

### Explain Agent - Meta Demo
Describe a business process → AI generates complete agent specification

**Generates:**
- Process analysis (goal, inputs, outputs, complexity)
- Directive document (markdown SOP)
- Python execution code
- Mermaid flowchart
- Implementation notes

This demo shows potential clients exactly how we build AI solutions.

**API:** `POST https://explain.miagentuca.es/explain`

## Tech Stack

- **Backend:** FastAPI + Python 3.12
- **AI:** Anthropic Claude API
- **Deployment:** Docker + Easypanel on Contabo VPS
- **Rate Limiting:** SlowAPI (5 requests/minute per IP)
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

- Rate limiting: 5 requests/minute per IP
- File size limits: 2MB max for uploads
- CORS enabled for miagentuca.es
- HTTPS enforced

## License

Private repository - All rights reserved

---

Built with the [3-Layer AI Architecture](https://miagentuca.es) by MiAgentUCA
