"""PDF handler for local PDF processing."""

import uuid
import shutil
from pathlib import Path
from typing import Optional, Dict
import pypdf

ROOT = Path(__file__).parent.parent
SAMPLES_DIR = ROOT / "samples"


def generate_uuid_prefix() -> tuple[str, str]:
    """
    Generate full UUID and 8-character hex prefix.
    
    Returns:
        Tuple of (full_uuid_hex, 8_char_prefix)
    """
    full_uuid = uuid.uuid4()
    full_uuid_hex = full_uuid.hex
    prefix = full_uuid_hex[:8]
    return full_uuid_hex, prefix


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract text from PDF file.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Extracted text as string
    """
    try:
        reader = pypdf.PdfReader(str(pdf_path))
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text())
        return "\n\n".join(text_parts)
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {e}")


def process_pdf(pdf_path: Path) -> Dict[str, str]:
    """
    Process a PDF: copy with UUID prefix and extract text.
    
    Args:
        pdf_path: Path to original PDF file
        
    Returns:
        Dict with keys: full_uuid, prefix, copied_path, text, original_filename
    """
    # Ensure samples directory exists
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate UUID
    full_uuid_hex, prefix = generate_uuid_prefix()
    
    # Get original filename
    original_filename = pdf_path.name
    
    # Create new filename with prefix
    new_filename = f"{prefix}_{original_filename}"
    copied_path = SAMPLES_DIR / new_filename
    
    # Copy file
    shutil.copy2(pdf_path, copied_path)
    
    # Extract text
    text = extract_text_from_pdf(copied_path)
    
    return {
        "full_uuid": full_uuid_hex,
        "prefix": prefix,
        "copied_path": str(copied_path.relative_to(ROOT)),
        "text": text,
        "original_filename": original_filename
    }


def get_pdf_title(pdf_path: Path) -> Optional[str]:
    """
    Try to extract title from PDF metadata.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Title string or None
    """
    try:
        reader = pypdf.PdfReader(str(pdf_path))
        metadata = reader.metadata
        if metadata and metadata.get("/Title"):
            return metadata["/Title"]
    except Exception:
        pass
    return None

