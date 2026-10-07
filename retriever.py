"""
retriever.py — Query retrieval module for Gito.

Handles the user query cycle:
1. Receives raw user query.
2. Embeds query with BAAI/bge-small-en-v1.5 (with 'Represent this sentence: ' prefix).
3. Executes cosine similarity vector search in Qdrant.
4. Returns ranked chunks with metadata and similarity scores.
5. Formats retrieved chunks into structured context ready for LLM generation.
"""

import os
from typing import Optional, List, Dict, Any
from embedder import Embedder
from qdrant_store import QdrantVectorStore, DEFAULT_COLLECTION_NAME, DEFAULT_STORAGE_PATH


class Retriever:
    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        db_path: str = DEFAULT_STORAGE_PATH,
        embedder: Optional[Embedder] = None,
        vector_store: Optional[QdrantVectorStore] = None,
    ):
        """
        Initialize Retriever with Embedder and Qdrant store.
        """
        self.collection_name = collection_name
        self.db_path = db_path

        # Reuse or instantiate embedder
        if embedder is not None:
            self.embedder = embedder
        else:
            self.embedder = Embedder()

        # Reuse or instantiate vector store
        if vector_store is not None:
            self.vector_store = vector_store
        else:
            self.vector_store = QdrantVectorStore(
                collection_name=self.collection_name,
                path=self.db_path,
            )

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: Optional[float] = None,
        chunk_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the top-k most relevant chunks for a user query.

        Args:
            query: The user query string.
            top_k: Number of chunks to retrieve.
            score_threshold: Minimum cosine similarity score (e.g. 0.5) to keep.
            chunk_type: Optional filter ('code' or 'doc').

        Returns:
            List of matching chunk dicts sorted by similarity score descending.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        # 1. Embed query
        query_vector = self.embedder.embed_query(clean_query)

        # 2. Vector search in Qdrant
        results = self.vector_store.search(
            query_vector=query_vector,
            limit=top_k,
            chunk_type=chunk_type,
        )

        # 3. Apply score threshold if specified
        if score_threshold is not None:
            results = [r for r in results if r.get("score", 0.0) >= score_threshold]

        return results

    @staticmethod
    def format_context(results: List[Dict[str, Any]]) -> str:
        """
        Format retrieved chunks into a prompt-ready context block.
        """
        if not results:
            return "No relevant context found."

        context_blocks = []
        for i, item in enumerate(results, start=1):
            filepath = item.get("filepath", "unknown")
            name = item.get("name", "snippet")
            chunk_type = item.get("chunk_type", "text")
            score = item.get("score", 0.0)
            content = item.get("content", "").strip()

            header = f"[Source {i}] {filepath} ({name}) | Type: {chunk_type} | Score: {score:.4f}"
            block = f"{header}\n```\n{content}\n```"
            context_blocks.append(block)

        return "\n\n".join(context_blocks)

    def close(self):
        """Close connections."""
        if hasattr(self, "vector_store") and self.vector_store:
            self.vector_store.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ──────────────────────────────────────────────────────────────────────────────
# CLI: Test or interactive query retrieval
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Query Gito vector store via Qdrant")
    parser.add_argument("query", nargs="?", default=None, help="User query string")
    parser.add_argument("-k", "--top-k", type=int, default=5, help="Number of chunks to retrieve (default: 5)")
    parser.add_argument("--threshold", type=float, default=None, help="Minimum cosine similarity score threshold")
    parser.add_argument("--type", choices=["code", "doc"], default=None, help="Filter by chunk type")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION_NAME, help="Qdrant collection name")
    parser.add_argument("--db-path", default=DEFAULT_STORAGE_PATH, help="Qdrant storage path")
    parser.add_argument("-i", "--interactive", action="store_true", help="Launch interactive query prompt")

    args = parser.parse_args()

    retriever = Retriever(collection_name=args.collection, db_path=args.db_path)

    def run_query(q: str):
        print(f"\n==================================================")
        print(f"Query: \"{q}\"")
        print(f"==================================================")
        hits = retriever.retrieve(
            query=q,
            top_k=args.top_k,
            score_threshold=args.threshold,
            chunk_type=args.type,
        )

        if not hits:
            print("No matching chunks found.")
            return

        print(f"Found {len(hits)} matching chunk(s):\n")
        for idx, hit in enumerate(hits, start=1):
            print(f"--- [Match {idx}] Score: {hit['score']:.4f} ---")
            print(f"File: {hit['filepath']} | Name: {hit['name']} | Type: {hit['chunk_type']}")
            snippet = hit['content']
            lines = snippet.splitlines()
            preview = "\n".join(lines[:8])
            if len(lines) > 8:
                preview += f"\n... [{len(lines) - 8} more lines]"
            print(f"Preview:\n{preview}\n")

    if args.interactive:
        print("\n=== Gito Retriever Interactive Mode ===")
        print("Type your query and press Enter. Type 'exit' or 'quit' to stop.\n")
        try:
            while True:
                user_input = input("Gito Query > ").strip()
                if user_input.lower() in ("exit", "quit", "q"):
                    break
                if user_input:
                    run_query(user_input)
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            retriever.close()
            print("\nExited.")
    elif args.query:
        try:
            run_query(args.query)
        finally:
            retriever.close()
    else:
        retriever.close()
        parser.print_help()
