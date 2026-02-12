"""
Embedding Client - Execution Layer

Deterministic wrapper around OpenAI's text-embedding-3-small model.
Handles single and batch embedding with retry logic.
"""

import os
import time
from typing import List, Optional

import openai


EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
BATCH_SIZE = 100
MAX_RETRIES = 3


def init_openai_client() -> Optional[openai.OpenAI]:
    """Initialize OpenAI client. Returns None if API key not configured."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_key_here":
        return None
    return openai.OpenAI(api_key=api_key)


def embed_text(text: str) -> List[float]:
    """
    Embed a single text string into a 1536-dimensional vector.

    Args:
        text: The text to embed.

    Returns:
        List of 1536 floats.

    Raises:
        RuntimeError: If OpenAI API key is not configured or API call fails.
    """
    client = init_openai_client()
    if client is None:
        raise RuntimeError("OpenAI API key not configured")

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text
    )
    return response.data[0].embedding


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Embed multiple texts in batches with retry logic.

    Args:
        texts: List of text strings to embed.

    Returns:
        List of embedding vectors (each 1536 floats).

    Raises:
        RuntimeError: If OpenAI API key is not configured or all retries fail.
    """
    client = init_openai_client()
    if client is None:
        raise RuntimeError("OpenAI API key not configured")

    all_embeddings = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]

        for attempt in range(MAX_RETRIES):
            try:
                response = client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=batch
                )
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                break
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    raise RuntimeError(
                        f"Embedding failed after {MAX_RETRIES} retries: {str(e)}"
                    )
                time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s

    return all_embeddings
