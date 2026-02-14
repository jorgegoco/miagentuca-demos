"""
ADE Client - Execution Layer

Deterministic wrapper around LandingAI's Agentic Document Extraction API.
Handles document parsing and field extraction with error handling.
"""

import os
import io
import json
import base64
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # pymupdf
from PIL import Image as PILImage
from landingai_ade import LandingAIADE
from landingai_ade.types import ParseResponse, ExtractResponse


def init_client() -> Optional[LandingAIADE]:
    """Initialize and return an ADE client. Returns None if API key not configured."""
    api_key = os.getenv("VISION_AGENT_API_KEY")
    if not api_key or api_key == "your_key_here":
        return None
    environment = os.getenv("ADE_ENVIRONMENT", "eu")
    return LandingAIADE(apikey=api_key, environment=environment)


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

        # Build chunk type summary and full chunk list
        chunk_summary = {}
        chunks = []

        for chunk in parse_result.chunks:
            t = chunk.type
            chunk_summary[t] = chunk_summary.get(t, 0) + 1

            chunk_data = {
                "id": chunk.id,
                "type": chunk.type,
                "markdown": chunk.markdown,
                "grounding": None,
            }
            if hasattr(chunk, "grounding") and chunk.grounding:
                grounding_data = {"page": chunk.grounding.page, "box": None}
                if hasattr(chunk.grounding, "box") and chunk.grounding.box:
                    grounding_data["box"] = {
                        "top": chunk.grounding.box.top,
                        "bottom": chunk.grounding.box.bottom,
                        "left": chunk.grounding.box.left,
                        "right": chunk.grounding.box.right,
                    }
                chunk_data["grounding"] = grounding_data
            chunks.append(chunk_data)

        # Build top-level grounding dict (includes table cells beyond chunk UUIDs)
        grounding = {}
        if hasattr(parse_result, "grounding") and parse_result.grounding:
            for gid, g in parse_result.grounding.items():
                entry = {"page": g.page, "type": g.type, "box": None}
                if hasattr(g, "box") and g.box:
                    entry["box"] = {
                        "top": g.box.top,
                        "bottom": g.box.bottom,
                        "left": g.box.left,
                        "right": g.box.right,
                    }
                grounding[gid] = entry

        return {
            "success": True,
            "markdown": parse_result.markdown,
            "total_pages": len(parse_result.splits),
            "total_chunks": len(parse_result.chunks),
            "chunk_summary": chunk_summary,
            "chunks": chunks,
            "grounding": grounding,
            "duration_ms": parse_result.metadata.duration_ms,
            "job_id": parse_result.metadata.job_id,
            "error": None,
        }

    except Exception as e:
        return {"success": False, "error": f"Parse failed: {str(e)}"}


def render_page_images(file_path: str, dpi: int = 150) -> List[Dict]:
    """
    Render each page of a document as a base64-encoded PNG image.

    For PDFs: renders each page at the given DPI using pymupdf.
    For images: reads the file and converts to PNG.

    Args:
        file_path: Path to the document (PDF or image).
        dpi: Resolution for PDF rendering (default 150).

    Returns:
        List of dicts with keys: page, image_base64, mime_type.
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        pages = []
        doc = fitz.open(str(path))
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=dpi)
            img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            pages.append({
                "page": page_num,
                "image_base64": base64.b64encode(buf.getvalue()).decode(),
                "mime_type": "image/png",
            })
        doc.close()
        return pages

    # Image file: single page
    img = PILImage.open(str(path))
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return [{
        "page": 0,
        "image_base64": base64.b64encode(buf.getvalue()).decode(),
        "mime_type": "image/png",
    }]


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
