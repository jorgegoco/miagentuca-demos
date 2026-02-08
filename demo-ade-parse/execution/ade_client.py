"""
ADE Client - Execution Layer

Deterministic wrapper around LandingAI's Agentic Document Extraction API.
Handles document parsing and field extraction with error handling.
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional

from landingai_ade import LandingAIADE
from landingai_ade.types import ParseResponse, ExtractResponse


def init_client() -> Optional[LandingAIADE]:
    """Initialize and return an ADE client. Returns None if API key not configured."""
    api_key = os.getenv("VISION_AGENT_API_KEY")
    if not api_key or api_key == "your_key_here":
        return None
    return LandingAIADE(apikey=api_key)


def parse_document(file_path: str, model: str = "dpt-2-latest") -> Dict:
    """
    Parse a document using ADE Parse API.

    Args:
        file_path: Path to the document (PDF, PNG, JPG, JPEG).
        model: ADE model to use. "dpt-2-latest" for general documents,
               "dpt-1-latest" for illustration-heavy documents.

    Returns:
        Dict with keys: success, markdown, total_pages, total_chunks,
        chunk_summary, duration_ms, error.
    """
    try:
        client = init_client()
        if client is None:
            return {"success": False, "error": "ADE API key not configured"}

        document_path = Path(file_path)
        if not document_path.exists():
            return {"success": False, "error": f"File not found: {file_path}"}

        parse_result: ParseResponse = client.parse(
            document=document_path,
            model=model
        )

        # Build chunk type summary
        chunk_summary = {}
        for chunk in parse_result.chunks:
            t = chunk.type
            chunk_summary[t] = chunk_summary.get(t, 0) + 1

        return {
            "success": True,
            "markdown": parse_result.markdown,
            "total_pages": len(parse_result.splits),
            "total_chunks": len(parse_result.chunks),
            "chunk_summary": chunk_summary,
            "duration_ms": parse_result.metadata.duration_ms,
            "job_id": parse_result.metadata.job_id,
            "error": None,
        }

    except Exception as e:
        return {"success": False, "error": f"Parse failed: {str(e)}"}


def extract_fields(markdown: str, schema_json: str,
                   model: str = "extract-latest") -> Dict:
    """
    Extract key-value pairs from parsed markdown using a JSON schema.

    Args:
        markdown: The markdown output from parse_document().
        schema_json: JSON string defining fields to extract.
        model: ADE extraction model to use.

    Returns:
        Dict with keys: success, fields, metadata, error.
    """
    try:
        client = init_client()
        if client is None:
            return {"success": False, "error": "ADE API key not configured"}

        # Validate schema is valid JSON
        try:
            json.loads(schema_json)
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid schema JSON: {str(e)}"}

        extraction_result: ExtractResponse = client.extract(
            schema=schema_json,
            markdown=markdown,
            model=model
        )

        return {
            "success": True,
            "fields": extraction_result.extraction,
            "metadata": extraction_result.extraction_metadata,
            "error": None,
        }

    except Exception as e:
        return {"success": False, "error": f"Extraction failed: {str(e)}"}


if __name__ == "__main__":
    # Quick test
    from dotenv import load_dotenv
    load_dotenv()

    result = parse_document("test.pdf")
    print(json.dumps(result, indent=2, default=str))
