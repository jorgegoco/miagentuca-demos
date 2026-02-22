"""
Image Client - Execution Layer

Generates cropped PNG images from PDF pages for visual grounding.
Uses PyMuPDF (fitz) to render the page, crops to the chunk bbox,
adds a red border, and saves to CHUNK_IMAGES_DIR.

Results are cached: if the PNG already exists, rendering is skipped.
"""

import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CHUNK_IMAGES_DIR = os.getenv("CHUNK_IMAGES_DIR", "/app/chunk_images")

# Rendering settings (matching original lesson6 visual_grounding_helper.py)
RENDER_DPI = 150
PADDING_PX = 20
BORDER_PX = 3
BORDER_COLOR = (255, 0, 0)  # Red


def get_chunk_image(
    pdf_path: str,
    page: int,
    bbox: Optional[dict],
    chunk_id: str,
) -> Optional[str]:
    """
    Render and crop a chunk region from a PDF page, save as PNG.

    Args:
        pdf_path: Absolute path to the source PDF file.
        page: 0-indexed page number.
        bbox: Normalized bounding box dict with keys x0, y0, x1, y1 (0.0–1.0).
              If None, the whole page is returned.
        chunk_id: Used as the PNG filename (for caching).

    Returns:
        Filename of the saved PNG (relative, e.g. "abc-123.png"),
        or None if rendering failed.
    """
    try:
        import fitz  # PyMuPDF
        from PIL import Image, ImageDraw
    except ImportError as e:
        logger.error("Missing dependency for image rendering: %s", e)
        return None

    output_dir = Path(CHUNK_IMAGES_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    png_filename = f"{chunk_id}.png"
    png_path = output_dir / png_filename

    # Cache: skip if already rendered
    if png_path.exists():
        return png_filename

    if not Path(pdf_path).exists():
        logger.warning("PDF not found for image rendering: %s", pdf_path)
        return None

    try:
        doc = fitz.open(pdf_path)

        if page < 0 or page >= len(doc):
            logger.warning("Page %d out of range for %s (%d pages)", page, pdf_path, len(doc))
            doc.close()
            return None

        pdf_page = doc[page]
        page_width = pdf_page.rect.width
        page_height = pdf_page.rect.height

        # Render at DPI
        zoom = RENDER_DPI / 72  # fitz uses 72 DPI as base
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = pdf_page.get_pixmap(matrix=matrix)
        doc.close()

        # Convert to PIL Image
        img = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        img_w, img_h = img.size

        if bbox is not None:
            # Convert normalized bbox to pixel coordinates
            x0 = int(bbox["x0"] * img_w)
            y0 = int(bbox["y0"] * img_h)
            x1 = int(bbox["x1"] * img_w)
            y1 = int(bbox["y1"] * img_h)

            # Add padding, clip to image bounds
            x0 = max(0, x0 - PADDING_PX)
            y0 = max(0, y0 - PADDING_PX)
            x1 = min(img_w, x1 + PADDING_PX)
            y1 = min(img_h, y1 + PADDING_PX)

            # Crop
            img = img.crop((x0, y0, x1, y1))

            # Draw red border
            draw = ImageDraw.Draw(img)
            crop_w, crop_h = img.size
            for b in range(BORDER_PX):
                draw.rectangle(
                    [b, b, crop_w - 1 - b, crop_h - 1 - b],
                    outline=BORDER_COLOR,
                )

        img.save(png_path, format="PNG")
        return png_filename

    except Exception as e:
        logger.error("Image rendering failed for chunk %s: %s", chunk_id, e)
        return None
