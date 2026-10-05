"""Text chunking logic with stable S1, S2 chunk labeling and SHA-256 hashing."""

import hashlib
from typing import TypedDict


class ChunkDict(TypedDict):
    chunk_label: str
    position: int
    text: str


def compute_content_hash(text: str) -> str:
    """Compute SHA-256 hash of normalized text."""
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def chunk_text(text: str, target_words_per_chunk: int = 200) -> list[ChunkDict]:
    """Split text into chunks of roughly target_words_per_chunk words.
    
    Assigns stable labels S1, S2, ... in sequence.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()] if text.strip() else []

    chunks: list[ChunkDict] = []
    current_words: list[str] = []
    chunk_counter = 1

    for para in paragraphs:
        para_words = para.split()
        current_words.extend(para_words)

        if len(current_words) >= target_words_per_chunk:
            chunk_str = " ".join(current_words)
            chunks.append({
                "chunk_label": f"S{chunk_counter}",
                "position": chunk_counter,
                "text": chunk_str,
            })
            chunk_counter += 1
            current_words = []

    # Final leftover chunk
    if current_words:
        chunk_str = " ".join(current_words)
        chunks.append({
            "chunk_label": f"S{chunk_counter}",
            "position": chunk_counter,
            "text": chunk_str,
        })

    return chunks
