# MiAgentUCA - Interactive Demos

Interactive demos showcasing AI agent capabilities for [miagentuca.es](https://miagentuca.es/).

## Architecture

All demos follow a **3-layer architecture** that separates concerns for maximum reliability:

1. **Directive Layer** - Natural language SOPs (what to do)
2. **Orchestration Layer** - AI-powered decision making (intelligent routing)
3. **Execution Layer** - Deterministic Python scripts (reliable execution)

See [CLAUDE.md](CLAUDE.md) for complete methodology.

## Demos

### 🗂️ demo-gestoria - Document Classifier
**Status:** In Development
**URL:** demo-gestoria.miagentuca.es
**Purpose:** Upload PDF documents (invoices, contracts, tax forms) → Classify type → Extract key information

### 🛒 demo-compras - Purchase Agent
**Status:** Planned
**URL:** demo-compras.miagentuca.es
**Purpose:** Search suppliers → Compare prices → Generate purchase recommendations

### 🤖 demo-explain-agent - Meta Demo
**Status:** Planned
**URL:** demo-explain.miagentuca.es
**Purpose:** Describe business process → Generate directive + code + flowchart (showcases methodology)

## Tech Stack

- **Backend:** FastAPI + Python 3.12
- **AI:** Anthropic Claude API
- **Deployment:** Docker + Easypanel on Contabo VPS
- **Rate Limiting:** Redis + SlowAPI
- **Reverse Proxy:** Nginx

## Development

Each demo is self-contained:

```bash
cd demo-gestoria
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn orchestration.main:app --reload
```

## Deployment

Each demo runs in its own Docker container:
- Port 8001: demo-gestoria
- Port 8002: demo-compras
- Port 8003: demo-explain-agent

Nginx routes subdomains to containers.

## Security

- Separate API keys with budget limits per demo
- Rate limiting (5 requests/minute per IP)
- CAPTCHA on public endpoints
- CloudFlare DDoS protection

## License

Private repository - All rights reserved
