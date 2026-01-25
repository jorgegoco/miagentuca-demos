# Demo Explain Agent - Meta Demo

The "killer differentiator" demo that shows potential clients exactly how we build AI agents. Describe a business process and get a complete 3-layer architecture specification.

## Live Demo

**URL:** [explain.miagentuca.es](https://explain.miagentuca.es)

**API Docs:** [explain.miagentuca.es/docs](https://explain.miagentuca.es/docs)

## Overview

This demo showcases transparency in AI solution development:

1. **Directive Layer** (`directives/explain_agent.md`) - Rules for generating agent specifications
2. **Execution Layer** (`execution/template_generator.py`) - Deterministic template and flowchart generation
3. **Orchestration Layer** (`orchestration/explain_endpoint.py`) - Intelligent process analysis using Claude API

## What It Generates

For any business process description, it generates:

- **Process Analysis** - Goal, inputs, outputs, complexity level
- **Directive Document** - Complete markdown SOP with steps and edge cases
- **Execution Code** - Python code skeleton following best practices
- **Flowchart** - Mermaid diagram showing the 3-layer architecture
- **Implementation Notes** - Next steps and considerations

## Key Message

This demo communicates to potential clients:

1. **Transparency** - "This is exactly how we build your solution"
2. **Reliability** - "Deterministic code + AI = consistent results"
3. **Maintainability** - "Clear separation makes updates easy"
4. **No black boxes** - "You can read and audit everything"

## API Usage

### Explain Process

**Endpoint:** `POST /explain`

**Request:**
```bash
curl -X POST "https://explain.miagentuca.es/explain" \
  -H "Content-Type: application/json" \
  -d '{
    "process_description": "Automatizar el envío de emails de bienvenida cuando un cliente se registra en la web",
    "language": "es"
  }'
```

**Response:**
```json
{
  "success": true,
  "process_analysis": {
    "goal": "Enviar emails de bienvenida personalizados a nuevos clientes",
    "inputs": ["datos_registro_cliente", "plantilla_email", "config_smtp"],
    "outputs": ["email_enviado", "log_envio"],
    "complexity": "medium"
  },
  "directive": "# Directiva del Agente\n\n## Propósito\n...",
  "execution_code": "#!/usr/bin/env python3\n...",
  "flowchart": "flowchart TB\n    subgraph L1[Capa 1: Directiva]\n...",
  "implementation_notes": "Implementación estimada: 2-3 días..."
}
```

## Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `process_description` | string | Yes | Business process description (20-2000 chars) |
| `language` | string | No | Output language: es, en (default: es) |

## Example Processes

Try these descriptions:

- "Automatizar la gestión de facturas de proveedores"
- "Clasificar emails de soporte y asignar a equipos"
- "Generar informes semanales de ventas"
- "Validar pedidos antes de enviarlos al almacén"

## Local Development

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Run server
python orchestration/explain_endpoint.py
```

## License

Private demo - All rights reserved
