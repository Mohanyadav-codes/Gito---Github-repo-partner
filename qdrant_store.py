"""
qdrant_store.py — Vector database storage and retrieval using Qdrant.

Supports:
- Local persistent storage (embedded on disk, no Docker needed)
- Remote Qdrant server / Qdrant Cloud (via URL & API Key)
- Automatic collection creation with cosine similarity
- Batch upserts with chunk metadata (payload)
- Fast vector similarity search with optional metadata filtering
"""

import os
import uuid
from typing import Optional, List, Dict, Any
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

DEFAULT_COLLECTION_NAME = "gito_codebase"
DEFAULT_STORAGE_PATH = "./qdrant_db"
VECTOR_DIMENSION = 384  # For BAAI/bge-small-en-v1.5


class QdrantVectorStore:
    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        path: Optional[str] = None,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        vector_dim: int = VECTOR_DIMENSION,
    ):
        """
        Initialize Qdrant client and prepare collection.

        Args:
            collection_name: Name of the collection in Qdrant.
            path: Local directory path for embedded storage (e.g., './qdrant_db').
            url: Remote Qdrant URL (e.g., 'http://localhost:6333' or cloud endpoint).
            api_key: API key for Qdrant Cloud if applicable.
            vector_dim: Dimensionality of vectors (default 384).
        """
        self.collection_name = collection_name
        self.vector_dim = vector_dim

        # Priority: URL if provided or set in env, else local disk path
        qdrant_url = url or os.getenv("QDRANT_URL")
        qdrant_api_key = api_key or os.getenv("QDRANT_API_KEY")

        if qdrant_url:
            print(f"Connecting to remote Qdrant at: {qdrant_url}")
            self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        else:
            storage_path = path or os.getenv("QDRANT_PATH", DEFAULT_STORAGE_PATH)
            os.makedirs(storage_path, exist_ok=True)
            print(f"Using local embedded Qdrant storage at: {os.path.abspath(storage_path)}")
            self.client = QdrantClient(path=storage_path)

        self.ensure_collection()

    def ensure_collection(self, recreate: bool = False):
        """Create the collection if it doesn't exist, or recreate if requested."""
        exists = self.client.collection_exists(self.collection_name)
        if exists and recreate:
            print(f"Recreating collection '{self.collection_name}'...")
            self.client.delete_collection(self.collection_name)
            exists = False

        if not exists:
            print(f"Creating Qdrant collection '{self.collection_name}' (dim={self.vector_dim}, distance=COSINE)...")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_dim, distance=Distance.COSINE),
            )
        else:
            print(f"Qdrant collection '{self.collection_name}' is ready.")

    def index_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: np.ndarray,
        batch_size: int = 100,
    ) -> int:
        """
        Upsert chunks and their embeddings into the Qdrant collection.

        Args:
            chunks: List of chunk metadata dictionaries.
            embeddings: (N, vector_dim) numpy array of embedding vectors.
            batch_size: Batch size for upserts.

        Returns:
            Number of points indexed.
        """
        if len(chunks) == 0:
            print("No chunks to index.")
            return 0

        total = len(chunks)
        print(f"Indexing {total} chunks into Qdrant collection '{self.collection_name}'...")

        points = []
        for i, (chunk, vec) in enumerate(zip(chunks, embeddings)):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{chunk.get('filepath', '')}:{chunk.get('name', '')}:{i}"))
            
            # Store metadata as payload
            payload = {
                "filepath": chunk.get("filepath", ""),
                "chunk_type": chunk.get("chunk_type", ""),
                "name": chunk.get("name", ""),
                "content": chunk.get("content", ""),
            }
            if "language" in chunk:
                payload["language"] = chunk["language"]
            if "token_count" in chunk:
                payload["token_count"] = chunk["token_count"]

            vector_data = vec.tolist() if isinstance(vec, np.ndarray) else vec

            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector_data,
                    payload=payload,
                )
            )

            if len(points) >= batch_size:
                self.client.upsert(collection_name=self.collection_name, points=points)
                points = []

        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)

        print(f"Successfully indexed {total} points into Qdrant!")
        return total

    def search(
        self,
        query_vector: np.ndarray,
        limit: int = 5,
        chunk_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for top-k similar chunks using cosine similarity.

        Args:
            query_vector: (384,) query embedding vector.
            limit: Number of top results to return.
            chunk_type: Optional filter ('code' or 'doc').

        Returns:
            List of result dicts containing id, score, and payload.
        """
        query_list = query_vector.tolist() if isinstance(query_vector, np.ndarray) else query_vector

        query_filter = None
        if chunk_type:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="chunk_type",
                        match=MatchValue(value=chunk_type),
                    )
                ]
            )

        res = self.client.query_points(
            collection_name=self.collection_name,
            query=query_list,
            query_filter=query_filter,
            limit=limit,
        )

        results = []
        for point in res.points:
            results.append({
                "id": point.id,
                "score": point.score,
                "filepath": point.payload.get("filepath", ""),
                "name": point.payload.get("name", ""),
                "chunk_type": point.payload.get("chunk_type", ""),
                "content": point.payload.get("content", ""),
                "language": point.payload.get("language", None),
                "payload": point.payload,
            })

        return results

    def count(self) -> int:
        """Return total number of points in collection."""
        res = self.client.count(collection_name=self.collection_name)
        return res.count

    @classmethod
    def sanitize_collection_name(cls, name: str) -> str:
        """Sanitize a string to be a valid Qdrant collection name."""
        import re
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name).strip('_')
        return sanitized.lower() or "repo_default"

    @classmethod
    def list_collections(
        cls,
        path: Optional[str] = None,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all collections with their point counts.
        """
        qdrant_url = url or os.getenv("QDRANT_URL")
        qdrant_api_key = api_key or os.getenv("QDRANT_API_KEY")

        if qdrant_url:
            temp_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        else:
            storage_path = path or os.getenv("QDRANT_PATH", DEFAULT_STORAGE_PATH)
            os.makedirs(storage_path, exist_ok=True)
            temp_client = QdrantClient(path=storage_path)

        try:
            cols = temp_client.get_collections().collections
            info_list = []
            for c in cols:
                try:
                    count = temp_client.count(c.name).count
                except Exception:
                    count = 0
                info_list.append({"name": c.name, "count": count})
            return info_list
        finally:
            try:
                temp_client.close()
            except Exception:
                pass

    def close(self):
        """Close the Qdrant client connection cleanly."""
        if hasattr(self, "client") and self.client is not None:
            try:
                self.client.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

