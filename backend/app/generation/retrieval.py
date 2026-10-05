"""Lexical BM25 chunk retrieval for prompt context assembly."""

import math
from collections import Counter
from backend.app.db.models.source import SourceChunk


def retrieve_relevant_chunks(
    chunks: list[SourceChunk],
    query: str,
    top_k: int = 5,
) -> list[SourceChunk]:
    """Retrieve top_k most relevant chunks using BM25 scoring over query terms.
    
    Returns all chunks if total chunks <= top_k.
    """
    if len(chunks) <= top_k:
        return chunks

    query_tokens = [w.lower() for w in query.split() if len(w) > 2]
    if not query_tokens:
        return chunks[:top_k]

    # Simple BM25 scoring
    doc_count = len(chunks)
    avg_doc_len = sum(len(c.text.split()) for c in chunks) / doc_count if doc_count > 0 else 1.0
    k1 = 1.5
    b = 0.75

    # Count document frequency for query terms
    df = Counter()
    for chunk in chunks:
        words = set(w.lower() for w in chunk.text.split())
        for q in query_tokens:
            if q in words:
                df[q] += 1

    scores: list[tuple[float, SourceChunk]] = []
    for chunk in chunks:
        doc_words = [w.lower() for w in chunk.text.split()]
        doc_len = len(doc_words)
        tf_counts = Counter(doc_words)

        score = 0.0
        for q in query_tokens:
            if q in tf_counts:
                tf = tf_counts[q]
                doc_freq = df.get(q, 0)
                idf = math.log((doc_count - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)
                num = tf * (k1 + 1)
                den = tf + k1 * (1 - b + b * (doc_len / avg_doc_len))
                score += idf * (num / den)

        scores.append((score, chunk))

    # Sort descending by BM25 score, retaining stable chunk order for ties
    scores.sort(key=lambda x: (x[0], -x[1].position), reverse=True)
    return [item[1] for item in scores[:top_k]]
