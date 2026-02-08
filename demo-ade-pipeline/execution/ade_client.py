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
    return LandingAIADE()


def parse_document(file_path: str, model: str = "dpt-2-latest",
                   split: str = "page") -> Dict:
    """
    Parse a document using ADE Parse API.

    Args:
        file_path: Path to the document (PDF, PNG, JPG, JPEG).
        model: ADE model to use.
        split: Split mode - "page" for per-page markdown.

    Returns:
        Dict with keys: success, markdown, splits, total_pages, total_chunks,
        chunk_summary, duration_ms, grounding, error.
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
            split=split,
            model=model
        )

        # Build chunk type summary
        chunk_summary = {}
        for chunk in parse_result.chunks:
            t = chunk.type
            chunk_summary[t] = chunk_summary.get(t, 0) + 1

        # Extract per-page markdown
        splits_markdown = []
        for s in parse_result.splits:
            splits_markdown.append(s.markdown)

        return {
            "success": True,
            "markdown": parse_result.markdown,
            "splits_markdown": splits_markdown,
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
