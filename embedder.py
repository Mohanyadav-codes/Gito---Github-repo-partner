"""
embedder.py — Generate embeddings using BAAI/bge-small-en-v1.5 and store in Qdrant.

• Documents/chunks  → encoded as-is (no prefix)
• Queries           → prefixed with "Represent this sentence: " (BGE convention)
• Output dimension  → 384
• Storage           → Qdrant vector database (local disk or remote server)
"""

import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer
from qdrant_store import QdrantVectorStore, DEFAULT_COLLECTION_NAME, DEFAULT_STORAGE_PATH

MODEL_NAME = "BAAI/bge-small-en-v1.5"
QUERY_PREFIX = "Represent this sentence: "


class Embedder:
    """Thin wrapper around SentenceTransformer for BGE embeddings."""

    def __init__(self, model_name: str = MODEL_NAME):
        print(f"Loading embedding model: {model_name} ...")
        self.model = SentenceTransformer(model_name)
        print(f"Model loaded.  Embedding dimension: {self.model.get_embedding_dimension()}")

    def embed_chunks(self, chunks: list[dict], batch_size: int = 64) -> np.ndarray:
        """
        Embed a list of chunk dicts (must contain a 'content' key).
        Returns an (N, 384) float32 numpy array, L2-normalised.
        """
        texts = [chunk['content'] for chunk in chunks]
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            normalize_embeddings=True,
        )
        return np.array(embeddings, dtype=np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """
        Embed a single search query (with the BGE query prefix).
        Returns a (384,) float32 numpy array, L2-normalised.
        """
        embedding = self.model.encode(
            QUERY_PREFIX + query,
            normalize_embeddings=True,
        )
        return np.array(embedding, dtype=np.float32)


# ──────────────────────────────────────────────────────────────────────────────
# CLI — Chunk a repository, generate embeddings, and index into Qdrant
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    from chunker import chunk_repository

    parser = argparse.ArgumentParser(
        description="Chunk a repo (or load chunks.json), generate BGE embeddings, and store them into Qdrant."
    )
    parser.add_argument('input_path', help="Path to an existing chunks.json file OR extracted repo directory")
    parser.add_argument(
        '--collection', '-c', default=DEFAULT_COLLECTION_NAME,
        help=f"Qdrant collection name (default: {DEFAULT_COLLECTION_NAME})"
    )
    parser.add_argument(
        '--db-path', '-p', default=DEFAULT_STORAGE_PATH,
        help=f"Local path for Qdrant database (default: {DEFAULT_STORAGE_PATH})"
    )
    parser.add_argument(
        '--recreate', action='store_true',
        help="Recreate the Qdrant collection if it already exists"
    )
    args = parser.parse_args()

    # 1. Load or Generate Chunks
    if os.path.isfile(args.input_path) and args.input_path.lower().endswith('.json'):
        print(f"\n── 1. Loading existing chunks from file: {args.input_path} ──")
        with open(args.input_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
    elif os.path.isdir(args.input_path):
        print(f"\n── 1. Chunking repo: {args.input_path} ──")
        chunks = chunk_repository(args.input_path)
    else:
        print(f"Error: '{args.input_path}' is neither an existing JSON file nor a valid directory.")
        exit(1)

    code_chunks = [c for c in chunks if c.get('chunk_type') == 'code']
    doc_chunks  = [c for c in chunks if c.get('chunk_type') == 'doc']
    print(f"  Total chunks : {len(chunks)}")
    print(f"  Code chunks  : {len(code_chunks)}")
    print(f"  Doc chunks   : {len(doc_chunks)}")

    if not chunks:
        print("No chunks found. Nothing to embed.")
        exit(0)

    # 2. Embedding
    print(f"\n── 2. Generating embeddings (BAAI/bge-small-en-v1.5) ──")
    embedder = Embedder()
    embeddings = embedder.embed_chunks(chunks)

    # 3. Store into Qdrant
    print(f"\n── 3. Indexing into Qdrant vector database ──")
    vector_store = QdrantVectorStore(
        collection_name=args.collection,
        path=args.db_path,
    )
    if args.recreate:
        vector_store.ensure_collection(recreate=True)

    indexed_count = vector_store.index_chunks(chunks, embeddings)
    total_count = vector_store.count()

    print(f"\nDone! Indexed {indexed_count} chunks into Qdrant collection '{args.collection}'.")
    print(f"Total vectors in collection: {total_count}")
    vector_store.close()
