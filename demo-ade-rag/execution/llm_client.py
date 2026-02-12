"""
LLM Client - Execution Layer

Deterministic wrapper around Anthropic's Claude API for RAG answer generation.
Takes a question and retrieved context chunks, returns a grounded answer.
"""

import os
from typing import Dict, List, Optional

import anthropic


MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024

SYSTEM_PROMPT = (
    "Use the following pieces of retrieved context to answer the "
    "user's question. "
    "If you don't know the answer, say that you don't know."
    "\n\n"
    "{context}"
)


def init_anthropic_client() -> Optional[anthropic.Anthropic]:
    """Initialize Anthropic client. Returns None if API key not configured."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_key_here":
        return None
    return anthropic.Anthropic(api_key=api_key)


def generate_answer(question: str, context_chunks: List[Dict]) -> Dict:
    """
    Generate a grounded answer using Claude with retrieved context.

    Args:
        question: The user's question.
        context_chunks: List of chunk dicts with at least 'text', 'chunk_type', 'page'.

    Returns:
        Dict with: success, answer, error.
    """
    try:
        client = init_anthropic_client()
        if client is None:
            return {"success": False, "answer": "", "error": "Anthropic API key not configured"}

        # Build context string from retrieved chunks
        context_parts = []
        for i, chunk in enumerate(context_chunks, 1):
            chunk_type = chunk.get("chunk_type", "unknown")
            page = chunk.get("page", "?")
            text = chunk.get("text", "")
            context_parts.append(
                f"[Source {i} | Type: {chunk_type} | Page: {page}]\n{text}"
            )

        context = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant context found."

        system = SYSTEM_PROMPT.format(context=context)

        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[
                {"role": "user", "content": question}
            ],
        )

        answer = message.content[0].text if message.content else ""

        return {"success": True, "answer": answer, "error": None}

    except Exception as e:
        return {"success": False, "answer": "", "error": f"LLM generation failed: {str(e)}"}
