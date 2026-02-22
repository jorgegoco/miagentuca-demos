"""
Agent Client - Execution Layer

Strands Agent backed by the Anthropic API (AnthropicModel).
The agent has a single retrieval tool: search_documents().
It decides when to search and what to search for based on the conversation.

Session history is managed externally (in chatbot_endpoint.py) and passed
in as a messages list on each call, giving the agent full conversation context.
"""

import os
from typing import Dict, List, Optional, Tuple

from strands import Agent, tool
from strands.models.anthropic import AnthropicModel

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


def _build_retrieval_tool(
    doc_id_filter: Optional[str],
    top_k: int,
    threshold: float,
    retrieved_chunks_store: List[Dict],
):
    """
    Build a Strands tool function with the given retrieval parameters baked in.
    Also writes retrieved chunks into retrieved_chunks_store so the caller
    can access them after the agent finishes.
    """

    @tool
    def search_documents(query: str) -> str:
        """
        Search the document library for passages relevant to the query.
        Returns formatted text passages with source metadata.

        Args:
            query: A natural language search query.
        """
        try:
            query_embedding = embedding_client.embed_text(query)
            chunks = chroma_store.query_similar(
                query_embedding=query_embedding,
                top_k=top_k,
                threshold=threshold,
                doc_id_filter=doc_id_filter,
            )

            if not chunks:
                return "No relevant passages found for this query."

            # Store chunks so caller can attach them to the response
            retrieved_chunks_store.clear()
            retrieved_chunks_store.extend(chunks)

            # Format chunks as readable context for the agent
            formatted = []
            for i, chunk in enumerate(chunks, 1):
                source_label = (
                    f"[Source {i} | {chunk['doc_name']} | "
                    f"Page {chunk['page']} | Type: {chunk['chunk_type']} | "
                    f"Similarity: {chunk['similarity']:.2f}]"
                )
                formatted.append(f"{source_label}\n{chunk['text']}")

            return "\n\n---\n\n".join(formatted)

        except Exception as e:
            return f"Search failed: {str(e)}"

    return search_documents


def chat(
    messages: List[Dict],
    doc_id_filter: Optional[str] = None,
    top_k: int = 5,
    threshold: float = 0.25,
) -> Tuple[str, List[Dict]]:
    """
    Run one turn of the research chatbot agent.

    Args:
        messages: Full conversation history in format:
                  [{"role": "user"|"assistant", "content": "..."}]
                  The last message must be the user's current input.
        doc_id_filter: If set, search is restricted to this document.
        top_k: Number of chunks to retrieve.
        threshold: Minimum similarity score for retrieval.

    Returns:
        Tuple of (answer_text, retrieved_chunks).
        retrieved_chunks: List of source chunk dicts from the last search call.
    """
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your_key_here":
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    retrieved_chunks: List[Dict] = []
    retrieval_tool = _build_retrieval_tool(
        doc_id_filter=doc_id_filter,
        top_k=top_k,
        threshold=threshold,
        retrieved_chunks_store=retrieved_chunks,
    )

    model = AnthropicModel(
        model_id=MODEL_ID,
        api_key=ANTHROPIC_API_KEY,
    )

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[retrieval_tool],
    )

    # Replay conversation history then run the latest user message
    # Strands Agent supports passing messages directly for multi-turn context
    # The last item in messages is the current user turn
    current_message = messages[-1]["content"] if messages else ""
    history = messages[:-1] if len(messages) > 1 else []

    # Pass prior turns as context prefix in the system or via message history
    # Strands supports messages kwarg for prior context
    if history:
        # Build a compact history string to prepend as context
        history_lines = []
        for msg in history:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content']}")
        history_text = "\n".join(history_lines)
        full_message = (
            f"[Previous conversation]\n{history_text}\n\n"
            f"[Current question]\n{current_message}"
        )
    else:
        full_message = current_message

    response = agent(full_message)
    answer = str(response)

    return answer, retrieved_chunks
