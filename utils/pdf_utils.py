"""
PDF utilities for extracting text from PDF files.
"""

from pypdf import PdfReader


def extract_text_from_pdf(path: str) -> str:
    """
    Extract text content from a PDF file.
    
    Args:
        path: Path to the PDF file
        
    Returns:
        Extracted text as a string
    """
    text = ""
    try:
        with open(path, "rb") as f:
            reader = PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
    except Exception as e:
        raise RuntimeError(f"Error reading PDF {path}: {e}")
    
    return text
