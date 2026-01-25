#!/usr/bin/env python3
"""
Template Generator - Deterministic code template generation

This script handles the deterministic parts of template generation:
- Validating Mermaid syntax
- Formatting code blocks
- Generating consistent structure
"""


def validate_mermaid(diagram: str) -> bool:
    """Basic validation of Mermaid diagram syntax."""
    required_keywords = ["graph", "flowchart", "sequenceDiagram", "classDiagram"]
    has_type = any(kw in diagram for kw in required_keywords)
    has_arrows = "-->" in diagram or "---" in diagram or "==>" in diagram
    return has_type or has_arrows


def format_directive(
    purpose: str,
    inputs: list[str],
    process_steps: list[str],
    outputs: list[str],
    edge_cases: list[str]
) -> str:
    """Generate a formatted directive markdown document."""

    inputs_md = "\n".join(f"- {inp}" for inp in inputs)
    steps_md = "\n".join(f"### Paso {i+1}: {step}" for i, step in enumerate(process_steps))
    outputs_md = "\n".join(f"- {out}" for out in outputs)
    edge_cases_md = "\n".join(f"- {case}" for case in edge_cases)

    return f"""# Directiva del Agente

## Propósito
{purpose}

## Entradas
{inputs_md}

## Proceso
{steps_md}

## Salidas
{outputs_md}

## Casos Especiales
{edge_cases_md}
"""


def format_code_template(
    function_name: str,
    inputs: list[str],
    description: str
) -> str:
    """Generate a Python code template."""

    params = ", ".join(f"{inp}: str" for inp in inputs)

    return f'''#!/usr/bin/env python3
"""
{description}

Capa 3: Ejecución - Lógica determinística
"""

from typing import Optional


def {function_name}({params}) -> dict:
    """
    {description}

    Args:
        {chr(10).join(f"        {inp}: Descripción del parámetro" for inp in inputs)}

    Returns:
        dict: Resultado del procesamiento
    """
    # Validar entradas
    {chr(10).join(f"    if not {inp}: raise ValueError('{inp} es requerido')" for inp in inputs)}

    # Procesar datos
    result = {{
        "success": True,
        "data": {{}},
        "error": None
    }}

    # TODO: Implementar lógica de negocio

    return result


if __name__ == "__main__":
    # Test
    test_result = {function_name}({", ".join(f'"{inp}_test"' for inp in inputs)})
    print(test_result)
'''


def generate_three_layer_flowchart(process_name: str, steps: list[str]) -> str:
    """Generate a Mermaid flowchart showing the 3-layer architecture."""

    return f"""flowchart TB
    subgraph L1[Capa 1: Directiva]
        D1[📋 {process_name}]
        D2[Reglas y SOPs]
    end

    subgraph L2[Capa 2: Orquestación]
        O1[🤖 Agente IA]
        O2[Decisiones inteligentes]
    end

    subgraph L3[Capa 3: Ejecución]
        E1[⚙️ Scripts Python]
        E2[Lógica determinística]
    end

    User([👤 Usuario]) --> L1
    L1 --> L2
    L2 --> L3
    L3 --> Result([📊 Resultado])

    L2 -.->|Lee instrucciones| L1
    L2 -->|Ejecuta| L3
    L3 -.->|Retorna datos| L2
"""


if __name__ == "__main__":
    # Test template generation
    print("=== Directive Template ===")
    directive = format_directive(
        purpose="Automatizar proceso de ejemplo",
        inputs=["documento", "configuración"],
        process_steps=["Validar entrada", "Procesar datos", "Generar salida"],
        outputs=["resultado_json", "log_proceso"],
        edge_cases=["Documento vacío", "Formato inválido"]
    )
    print(directive)

    print("\n=== Code Template ===")
    code = format_code_template(
        function_name="procesar_documento",
        inputs=["documento", "config"],
        description="Procesa un documento según la configuración"
    )
    print(code)

    print("\n=== Flowchart ===")
    flowchart = generate_three_layer_flowchart(
        process_name="Clasificador de Documentos",
        steps=["Extraer texto", "Clasificar", "Extraer datos"]
    )
    print(flowchart)
