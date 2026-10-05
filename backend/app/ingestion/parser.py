"""Document parsing for text and PDF file uploads."""

import io
from pypdf import PdfReader


def parse_document(file_bytes: bytes, filename: str) -> tuple[str, str]:
    """Parse document bytes into clean text and identify file type.
    
    Returns:
        tuple[raw_text, file_type]
    """
    ext = filename.split(".")[-1].lower() if "." in filename else "txt"

    if ext == "pdf":
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            text_parts = []
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text_parts.append(extracted)
            raw_text = "\n\n".join(text_parts).strip()
            return raw_text, "pdf"
        except Exception as e:
            raise ValueError(f"Failed to parse PDF document: {str(e)}") from e
    else:
        # Default to plain text parsing
        try:
            raw_text = file_bytes.decode("utf-8").strip()
            return raw_text, "txt"
        except UnicodeDecodeError:
            raw_text = file_bytes.decode("latin-1", errors="replace").strip()
            return raw_text, "txt"
