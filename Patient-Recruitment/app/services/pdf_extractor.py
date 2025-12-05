from typing import Tuple
from pypdf import PdfReader

def extract_pdf_text_pages(pdf_path: str, start_page: int = 37, end_page: int = 41) -> str:
    """
    Extracts text from (1-based) start_page..end_page inclusive.
    If your PDF is zero-indexed by another tool, just adjust.
    """
    reader = PdfReader(pdf_path)
    n = len(reader.pages)
    s = max(1, start_page)
    e = min(end_page, n)
    chunks = []
    for i in range(s-1, e):  # convert to 0-based
        chunks.append(reader.pages[i].extract_text() or "")
    return "\n".join(chunks).strip()
