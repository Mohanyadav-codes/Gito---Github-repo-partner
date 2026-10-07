"""
agent.py — Gito: GitHub Repository AI Agent (LLM Answering Layer).

Completes the hybrid RAG pipeline:
1. Accepts user queries about a repository.
2. Retrieves top relevant code and documentation chunks using Qdrant vector search.
3. Injects the retrieved context into a grounded system prompt.
4. Generates comprehensive, cited answers using an LLM (Groq, OpenAI, Ollama, etc.).
"""

import os
import sys
from typing import Optional, List, Dict, Any, Generator
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv()

from retriever import Retriever
from qdrant_store import DEFAULT_COLLECTION_NAME, DEFAULT_STORAGE_PATH

# ──────────────────────────────────────────────────────────────────────────────
# System Prompt
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Gito, an expert GitHub Repository AI Agent.
Your mission is to help developers and users thoroughly understand codebases, locate functions and modules, trace logic, explain architecture, and answer questions with high precision.

You are given a user query along with retrieved context snippets (code functions, classes, and documentation) extracted directly from the repository.

Guidelines for answering:
1. GROUNDEDNESS: Base your answer strictly on the provided context snippets. Do not speculate or invent functions, files, or parameters not present in the context.
2. CITATIONS: Always explicitly cite the relevant files and function/class names (e.g., `[server.py:api_reports_export]` or `[docs/setup.md]`) when explaining code or architecture.
3. CODE SNIPPETS: Use concise, syntax-highlighted code blocks where helpful to illustrate your explanation.
4. HONESTY: If the retrieved snippets do not contain enough information to fully answer the query, clearly state what is known from the context and what information is missing.
5. STRUCTURE: Organize your answers clearly using headers, bullet points, and step-by-step breakdowns for readability.
"""

USER_PROMPT_TEMPLATE = """Retrieved Repository Context:
==================================================
{context}
==================================================

User Question:
{query}

Please provide a clear, accurate, and well-cited explanation based on the repository context above:"""


class GitoAgent:
    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        db_path: str = DEFAULT_STORAGE_PATH,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        retriever: Optional[Retriever] = None,
    ):
        """
        Initialize the Gito QA Agent.

        Args:
            collection_name: Qdrant collection to retrieve from.
            db_path: Path to Qdrant vector database.
            model: Model name (e.g. 'llama-3.3-70b-versatile', 'gpt-4o-mini').
            provider: 'groq', 'openai', or None (auto-detected from environment).
            api_key: Optional API key override.
            base_url: Optional custom base URL (e.g. Ollama http://localhost:11434/v1).
            retriever: Optional pre-configured Retriever instance.
        """
        self.retriever = retriever or Retriever(
            collection_name=collection_name,
            db_path=db_path,
        )

        self.api_key = api_key
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.client = None
        self.provider = provider
        self.model = model

        self._setup_llm_client()

    def _setup_llm_client(self):
        """Configure LLM client with auto-detection for Groq, OpenAI, or custom endpoints."""
        # 1. Determine provider and keys
        groq_key = self.api_key or os.getenv("GROQ_API_KEY")
        openai_key = self.api_key or os.getenv("OPENAI_API_KEY")

        if self.provider == "groq" or (self.provider is None and groq_key):
            try:
                from groq import Groq
                self.client = Groq(api_key=groq_key)
                self.provider = "groq"
                self.model = self.model or os.getenv("GITO_MODEL", "qwen/qwen3.8-27b")
                print(f"[Gito] Connected to Groq (model: {self.model})")
                return
            except Exception as e:
                print(f"[Gito] Warning: Failed to initialize Groq client: {e}")

        if self.provider == "openai" or (self.provider is None and (openai_key or self.base_url)):
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    api_key=openai_key or "not-needed",
                    base_url=self.base_url,
                )
                self.provider = "openai"
                self.model = self.model or os.getenv("GITO_MODEL", "gpt-4o-mini")
                print(f"[Gito] Connected to OpenAI-compatible provider (model: {self.model})")
                return
            except Exception as e:
                print(f"[Gito] Warning: Failed to initialize OpenAI client: {e}")

        # Fallback / Dry-run notice
        print("[Gito] Note: No GROQ_API_KEY or OPENAI_API_KEY detected.")
        print("[Gito] Set GROQ_API_KEY or OPENAI_API_KEY in your environment or .env file to generate live LLM responses.")

    def answer(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: Optional[float] = None,
        chunk_type: Optional[str] = None,
        stream: bool = True,
    ) -> str:
        """
        Run the complete query cycle:
        1. Retrieve top-k context snippets from Qdrant.
        2. Format prompt with context.
        3. Call LLM and return / stream the answer.
        """
        clean_query = query.strip()
        if not clean_query:
            return "Please provide a valid question."

        # 1. Retrieve relevant chunks
        hits = self.retriever.retrieve(
            query=clean_query,
            top_k=top_k,
            score_threshold=score_threshold,
            chunk_type=chunk_type,
        )

        if not hits:
            return "No relevant context found in the repository for this query."

        # 2. Build prompt context
        formatted_context = self.retriever.format_context(hits)
        user_prompt = USER_PROMPT_TEMPLATE.format(
            context=formatted_context,
            query=clean_query,
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # 3. Check if LLM client is available
        if self.client is None:
            # Fallback when API key is not yet set: show retrieved context preview
            output = (
                "\n[Gito Context Preview - No LLM API key provided]\n"
                f"Retrieved {len(hits)} relevant snippet(s):\n\n"
                f"{formatted_context}\n\n"
                "To get live AI answers, set GROQ_API_KEY or OPENAI_API_KEY in your environment:\n"
                "  $env:GROQ_API_KEY = \"your-key-here\"\n"
                "or create a .env file with GROQ_API_KEY=..."
            )
            print(output)
            return output

        # 4. Generate LLM response
        full_response = ""
        try:
            if stream:
                response_stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.2,
                    stream=True,
                )
                for chunk in response_stream:
                    delta = chunk.choices[0].delta.content or ""
                    sys.stdout.write(delta)
                    sys.stdout.flush()
                    full_response += delta
                sys.stdout.write("\n")
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.2,
                    stream=False,
                )
                full_response = response.choices[0].message.content
                print(full_response)
        except Exception as e:
            err_msg = f"\n[Gito Error] Failed to generate response from {self.provider}: {e}"
            print(err_msg)
            return err_msg

        return full_response

    def close(self):
        """Close vector store resources."""
        if hasattr(self, "retriever") and self.retriever:
            self.retriever.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ──────────────────────────────────────────────────────────────────────────────
# CLI: Interactive Chat & Single-Query Mode
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gito: AI Assistant for GitHub Repositories")
    parser.add_argument("query", nargs="?", default=None, help="Question to ask about the repository")
    parser.add_argument("-k", "--top-k", type=int, default=5, help="Number of context snippets to retrieve (default: 5)")
    parser.add_argument("--type", choices=["code", "doc"], default=None, help="Filter context by type (code or doc)")
    parser.add_argument("--threshold", type=float, default=None, help="Minimum similarity threshold")
    parser.add_argument("--model", default=None, help="Model name (e.g. llama-3.3-70b-versatile, gpt-4o-mini)")
    parser.add_argument("--provider", choices=["groq", "openai"], default=None, help="LLM provider")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION_NAME, help="Qdrant collection name")
    parser.add_argument("--db-path", default=DEFAULT_STORAGE_PATH, help="Qdrant database path")
    parser.add_argument("-i", "--interactive", action="store_true", help="Launch interactive Q&A session")

    args = parser.parse_args()

    agent = GitoAgent(
        collection_name=args.collection,
        db_path=args.db_path,
        model=args.model,
        provider=args.provider,
    )

    if args.interactive:
        print("\n" + "=" * 60)
        print("  Gito: GitHub Repository AI Assistant")
        print("  Type your question and press Enter. ('exit' to quit)")
        print("=" * 60 + "\n")
        try:
            while True:
                user_q = input("\nGito > ").strip()
                if user_q.lower() in ("exit", "quit", "q"):
                    break
                if user_q:
                    print()
                    agent.answer(
                        query=user_q,
                        top_k=args.top_k,
                        score_threshold=args.threshold,
                        chunk_type=args.type,
                        stream=True,
                    )
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            agent.close()
            print("\nGoodbye!")
    elif args.query:
        try:
            agent.answer(
                query=args.query,
                top_k=args.top_k,
                score_threshold=args.threshold,
                chunk_type=args.type,
                stream=True,
            )
        finally:
            agent.close()
    else:
        agent.close()
        parser.print_help()
