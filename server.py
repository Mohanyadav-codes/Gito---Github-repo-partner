"""
server.py — FastAPI Backend for Gito React Frontend.

Provides REST endpoints for:
1. GET  /api/projects       - List indexed repositories and chunk counts from Qdrant.
2. POST /api/projects       - Ingest and index a new GitHub repository URL.
3. POST /api/chat           - Ask queries against a repository with citation extraction.
4. GET  /api/health         - Health check & API key detection status.
"""

import os
import sys
from typing import Optional, List, Dict, Any
import json
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv()

from extractor import extract_repo, parse_github_url
from chunker import chunk_repository
from qdrant_store import QdrantVectorStore, DEFAULT_STORAGE_PATH, DEFAULT_COLLECTION_NAME
from retriever import Retriever
from agent import GitoAgent

app = FastAPI(title="Gito API", description="GitHub Repository Agent Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REPOS_CACHE_DIR = "./repo_cache"

# Lazy-loaded shared embedder instance to ensure instant server startup
_embedder_instance = None


def get_embedder():
    global _embedder_instance
    if _embedder_instance is None:
        from embedder import Embedder
        _embedder_instance = Embedder()
    return _embedder_instance


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas
# ──────────────────────────────────────────────────────────────────────────────

class AddRepoRequest(BaseModel):
    url: str
    recreate: bool = False


class ChatRequest(BaseModel):
    collection: str
    message: str
    top_k: int = 5
    type: Optional[str] = None  # 'code', 'doc', or None


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    has_groq = bool(os.getenv("GROQ_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    return {
        "status": "healthy",
        "has_llm_key": has_groq or has_openai,
        "active_provider": "groq" if has_groq else ("openai" if has_openai else "none"),
    }


@app.get("/api/projects")
def list_projects():
    """List all indexed repositories from Qdrant."""
    try:
        collections = QdrantVectorStore.list_collections(path=DEFAULT_STORAGE_PATH)
        return {"projects": collections}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects")
def add_project(req: AddRepoRequest):
    """
    Ingest, chunk, embed, and index a new GitHub repo.
    """
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Repository URL is required.")

    try:
        owner, repo = parse_github_url(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid GitHub URL: {e}")

    collection_name = QdrantVectorStore.sanitize_collection_name(f"{owner}_{repo}")
    dest_dir = os.path.join(REPOS_CACHE_DIR, f"{owner}_{repo}")
    github_token = os.getenv("GITHUB_TOKEN")

    # 1. Extract
    file_count = extract_repo(url, output_dir=dest_dir, token=github_token)
    if not file_count:
        raise HTTPException(status_code=400, detail="Failed to fetch repository files or repository is empty.")

    # 2. Chunk
    chunks = chunk_repository(dest_dir)
    if not chunks:
        raise HTTPException(status_code=400, detail="No extractable code or documentation chunks found in repository.")

    # 3. Embed & Index
    embedder = get_embedder()
    embeddings = embedder.embed_chunks(chunks)

    vector_store = QdrantVectorStore(collection_name=collection_name, path=DEFAULT_STORAGE_PATH)
    if req.recreate:
        vector_store.ensure_collection(recreate=True)

    indexed_count = vector_store.index_chunks(chunks, embeddings)
    total_count = vector_store.count()
    vector_store.close()

    return {
        "status": "success",
        "collection": collection_name,
        "repo_name": f"{owner}/{repo}",
        "indexed_chunks": indexed_count,
        "total_chunks": total_count,
    }


@app.post("/api/chat")
def chat_with_repo(req: ChatRequest):
    """
    Query a repository with vector search and generate an answer with citations.
    """
    collection = req.collection.strip()
    message = req.message.strip()

    if not collection:
        raise HTTPException(status_code=400, detail="Collection/project name is required.")
    if not message:
        raise HTTPException(status_code=400, detail="Message query is required.")

    embedder = get_embedder()
    vector_store = QdrantVectorStore(collection_name=collection, path=DEFAULT_STORAGE_PATH)
    retriever = Retriever(
        collection_name=collection,
        db_path=DEFAULT_STORAGE_PATH,
        embedder=embedder,
        vector_store=vector_store,
    )

    # 1. Retrieve top-k matches
    hits = retriever.retrieve(
        query=message,
        top_k=req.top_k,
        chunk_type=req.type,
    )

    # 2. Generate answer with GitoAgent
    agent = GitoAgent(
        collection_name=collection,
        db_path=DEFAULT_STORAGE_PATH,
        retriever=retriever,
    )

    answer_text = agent.answer(query=message, top_k=req.top_k, chunk_type=req.type, stream=False)

    agent.close()

    citations = [
        {
            "filepath": hit.get("filepath", ""),
            "name": hit.get("name", ""),
            "chunk_type": hit.get("chunk_type", ""),
            "score": round(hit.get("score", 0.0), 4),
            "content": hit.get("content", ""),
            "language": hit.get("language"),
        }
        for hit in hits
    ]

    return {
        "answer": answer_text,
        "citations": citations,
        "collection": collection,
    }


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest):
    """
    Stream query answer tokens in real-time via Server-Sent Events (SSE).
    """
    collection = req.collection.strip()
    message = req.message.strip()

    if not collection:
        raise HTTPException(status_code=400, detail="Collection name required.")
    if not message:
        raise HTTPException(status_code=400, detail="Query message required.")

    def event_generator():
        embedder = get_embedder()
        vector_store = QdrantVectorStore(collection_name=collection, path=DEFAULT_STORAGE_PATH)
        retriever = Retriever(
            collection_name=collection,
            db_path=DEFAULT_STORAGE_PATH,
            embedder=embedder,
            vector_store=vector_store,
        )
        agent = GitoAgent(
            collection_name=collection,
            db_path=DEFAULT_STORAGE_PATH,
            retriever=retriever,
        )

        try:
            for event in agent.answer_stream(
                query=message,
                top_k=req.top_k,
                chunk_type=req.type,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            agent.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )



# Mount React static files if built
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dist):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Starting Gito Web Server on http://localhost:8000")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

