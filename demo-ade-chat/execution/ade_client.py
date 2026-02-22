"""
ADE Client - Execution Layer

Deterministic wrapper around LandingAI's Agentic Document Extraction API.
Extended for RAG: returns raw chunk list with text, bbox, and page metadata.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional

from landingai_ade import LandingAIADE
from landingai_ade.types import ParseResponse


def init_client() -> Optional[LandingAIADE]:
    """Initialize and return an ADE client. Returns None if API key not configured."""
    api_key = os.getenv("VISION_AGENT_API_KEY")
    if not api_key or api_key == "your_key_here":
        return None
    environment = os.getenv("ADE_ENVIRONMENT", "eu")
    return LandingAIADE(apikey=api_key, environment=environment)


def parse_document(file_path: str, model: str = "dpt-2-latest") -> Dict:
    """
    Parse a document using ADE Parse API and return chunks for RAG indexing.

    Args:
        file_path: Path to the document.
        model: ADE model to use. "dpt-2-latest" for general documents,
               "dpt-1-latest" for illustration-heavy documents.

    Returns:
        Dict with keys: success, markdown, total_pages, total_chunks,
        chunk_summary, chunks (raw list), duration_ms, error.
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

        # Build chunk type summary and extract raw chunks for RAG
        chunk_summary = {}
        chunks = []

        for chunk in parse_result.chunks:
            t = chunk.type
            chunk_summary[t] = chunk_summary.get(t, 0) + 1

            # Extract bbox from chunk grounding
            bbox = None
            page = 0
            if hasattr(chunk, "grounding") and chunk.grounding:
                page = chunk.grounding.page
                if hasattr(chunk.grounding, "box") and chunk.grounding.box:
                    bbox = [
                        chunk.grounding.box.left,
                        chunk.grounding.box.top,
                        chunk.grounding.box.right,
                        chunk.grounding.box.bottom,
                    ]

            chunks.append({
                "chunk_id": chunk.id,
                "chunk_type": chunk.type,
                "text": chunk.markdown,
                "bbox": bbox,
                "page": page,
            })

        return {
            "success": True,
            "markdown": parse_result.markdown,
            "total_pages": len(parse_result.splits),
            "total_chunks": len(parse_result.chunks),
            "chunk_summary": chunk_summary,
            "chunks": chunks,
            "duration_ms": parse_result.metadata.duration_ms,
            "job_id": parse_result.metadata.job_id,
            "error": None,
        }

    except Exception as e:
        return {"success": False, "error": f"Parse failed: {str(e)}"}


if __name__ == "__main__":
    # Quick test
    from dotenv import load_dotenv
    load_dotenv()

    result = parse_document("test.pdf")
    print(json.dumps(result, indent=2, default=str))
