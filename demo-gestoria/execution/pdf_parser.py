"""
PDF Parser - Deterministic text extraction from PDF files

This script provides reliable PDF text extraction for the document classifier.
No AI decision-making happens here - just deterministic extraction.
"""

import sys
from pathlib import Path
from typing import Dict, Optional
import PyPDF2


class PDFParseError(Exception):
    """Custom exception for PDF parsing errors"""
    pass


def extract_text_from_pdf(pdf_path: str) -> Dict[str, any]:
    """
    Extract text from a PDF file.

    Args:
        pdf_path: Absolute path to the PDF file

    Returns:
        Dictionary containing:
        - success: bool
        - text: str (extracted text)
        - pages: int (number of pages)
        - error: str (error message if failed)

    Raises:
        PDFParseError: If file cannot be read or parsed
    """

    # Validate input
    pdf_file = Path(pdf_path)

    if not pdf_file.exists():
        return {
            "success": False,
            "text": "",
            "pages": 0,
            "error": f"File not found: {pdf_path}"
        }

    if not pdf_file.is_file():
        return {
            "success": False,
            "text": "",
            "pages": 0,
            "error": f"Path is not a file: {pdf_path}"
        }

    # Check file size (2MB limit)
    max_size = 2 * 1024 * 1024  # 2MB in bytes
    file_size = pdf_file.stat().st_size

    if file_size > max_size:
        return {
            "success": False,
            "text": "",
            "pages": 0,
            "error": f"File exceeds maximum size of 2MB (actual: {file_size / 1024 / 1024:.2f}MB)"
        }

    # Check if file is actually a PDF (magic bytes)
    try:
        with open(pdf_path, 'rb') as f:
            header = f.read(4)
            if header != b'%PDF':
                return {
                    "success": False,
                    "text": "",
                    "pages": 0,
                    "error": "File is not a valid PDF (invalid magic bytes)"
                }
    except Exception as e:
        return {
            "success": False,
            "text": "",
            "pages": 0,
            "error": f"Error reading file: {str(e)}"
        }

    # Extract text from PDF
    try:
        with open(pdf_path, 'rb') as file:
            # Create PDF reader
            pdf_reader = PyPDF2.PdfReader(file)

            # Get number of pages
            num_pages = len(pdf_reader.pages)

            if num_pages == 0:
                return {
                    "success": False,
                    "text": "",
                    "pages": 0,
                    "error": "PDF has no pages"
                }

            # Extract text from all pages
            extracted_text = []

            for page_num in range(num_pages):
                try:
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()

                    if page_text:
                        extracted_text.append(page_text.strip())

                except Exception as page_error:
                    # Log page error but continue
                    extracted_text.append(f"[Error extracting page {page_num + 1}]")

            # Combine all page text
            full_text = "\n\n".join(extracted_text)

            # Check if we extracted any meaningful text
            if not full_text or len(full_text.strip()) < 10:
                return {
                    "success": True,
                    "text": full_text,
                    "pages": num_pages,
                    "warning": "Minimal text extracted. Document may be scanned image or empty."
                }

            return {
                "success": True,
                "text": full_text,
                "pages": num_pages,
                "error": None
            }

    except PyPDF2.errors.PdfReadError as e:
        return {
            "success": False,
            "text": "",
            "pages": 0,
            "error": f"PDF read error: {str(e)}. File may be corrupted or password-protected."
        }

    except Exception as e:
        return {
            "success": False,
            "text": "",
            "pages": 0,
            "error": f"Unexpected error parsing PDF: {str(e)}"
        }


def main():
    """
    CLI interface for testing the PDF parser.

    Usage:
        python pdf_parser.py /path/to/document.pdf
    """
    if len(sys.argv) < 2:
        print("Usage: python pdf_parser.py <pdf_file_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]

    print(f"Parsing PDF: {pdf_path}")
    print("-" * 50)

    result = extract_text_from_pdf(pdf_path)

    if result["success"]:
        print(f"✓ Success!")
        print(f"  Pages: {result['pages']}")
        print(f"  Text length: {len(result['text'])} characters")

        if "warning" in result:
            print(f"  ⚠ Warning: {result['warning']}")

        print("\nExtracted text preview (first 500 chars):")
        print("-" * 50)
        print(result["text"][:500])

        if len(result["text"]) > 500:
            print("\n... (truncated)")

    else:
        print(f"✗ Failed!")
        print(f"  Error: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
