"""
Agent Client - Execution Layer

Multi-turn chat agent using the Anthropic API with tool_use.
The model decides when to call search_documents() based on the conversation.

No external agent framework needed — the anthropic package handles the
tool-use loop natively, which is equivalent to Strands for this use case.
"""

import os
from typing import Dict, List, Optional, Tuple

import anthropic

from execution import embedding_client, chroma_store


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL_ID = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """You are a research assistant specializing in medical literature.
You have access to a library of research papers. When a user asks a question,
use the search_documents tool to find relevant passages, then provide a clear,
accurate answer grounded in the retrieved content.

Guidelines:
- Always search before answering factual questions about the research.
- Cite your sources: mention the document name and page number.
- If search returns no relevant results, say so honestly.
- For follow-up questions, consider whether a new search is needed or if
  the previous context already contains the answer.
- Be concise but thorough. Avoid speculation beyond what the papers say.
"""

TOOLS = [
    {
        "name": "search_documents",
        "description": (
            "Search the document library for passages relevant to the query. "
            "Returns formatted text passages with source metadata."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A natural language search query.",
                }
            },
            "required": ["query"],
        },
    }
]


def _run_search(
    query: str,
    doc_id_filter: Optional[str],
    top_k: int,
    threshold: float,
) -> Tuple[str, List[Dict]]:
    """Execute semantic search and return (formatted_text, raw_chunks)."""
    query_embedding = embedding_client.embed_text(query)
    chunks = chroma_store.query_similar(
        query_embedding=query_embedding,
        top_k=top_k,
        threshold=threshold,
        doc_id_filter=doc_id_filter,
    )

    if not chunks:
        return "No relevant passages found for this query.", []

    formatted = []
    for i, chunk in enumerate(chunks, 1):
        label = (
            f"[Source {i} | {chunk['doc_name']} | "
            f"Page {chunk['page']} | Type: {chunk['chunk_type']} | "
            f"Similarity: {chunk['similarity']:.2f}]"
        )
        formatted.append(f"{label}\n{chunk['text']}")

    return "\n\n---\n\n".join(formatted), chunks


def chat(
    messages: List[Dict],
    doc_id_filter: Optional[str] = None,
    top_k: int = 5,
    threshold: float = 0.25,
) -> Tuple[str, List[Dict]]:
    """
    Run one turn of the research chatbot.

    Args:
        messages: Full conversation history:
                  [{"role": "user"|"assistant", "content": "..."}]
                  The last item is the current user message.
        doc_id_filter: Restrict search to one document's chunks.
        top_k: Max chunks to retrieve per search.
        threshold: Min similarity score.

    Returns:
        (answer_text, retrieved_chunks) where retrieved_chunks are the
        sources from the last search call the model made.
    """
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your_key_here":
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Convert session history to Anthropic message format
    api_messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in messages
    ]

    all_retrieved_chunks: List[Dict] = []

    # Agentic loop: keep running until the model stops calling tools
    while True:
        response = client.messages.create(
            model=MODEL_ID,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=api_messages,
        )

        if response.stop_reason == "tool_use":
            # Execute each tool call the model requested
            tool_results = []
            for block in response.content:
                if block.type == "tool_use" and block.name == "search_documents":
                    query = block.input.get("query", "")
                    result_text, chunks = _run_search(
                        query, doc_id_filter, top_k, threshold
                    )
                    if chunks:
                        all_retrieved_chunks = chunks  # keep last search results
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                    })

            # Feed tool results back into the conversation
            api_messages.append({"role": "assistant", "content": response.content})
            api_messages.append({"role": "user", "content": tool_results})

        else:
            # Model is done — extract the final text answer
            answer = "".join(
                block.text for block in response.content if hasattr(block, "text")
            )
            return answer, all_retrieved_chunks
