"""
main.py — End-to-End Pipeline & CLI for Gito.

Connects all components:
1. Interactive repository selection or adding a new GitHub repository.
2. Automated Extraction -> Chunking -> Embedding -> Qdrant indexing.
3. Direct conversational query loop with Gito's grounded LLM answering layer.
"""

import os
import sys
import argparse
from typing import Optional
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
from embedder import Embedder
from qdrant_store import QdrantVectorStore, DEFAULT_STORAGE_PATH, DEFAULT_COLLECTION_NAME
from retriever import Retriever
from agent import GitoAgent


REPOS_CACHE_DIR = "./repo_cache"


def banner():
    print(r"""
===================================================================
     ____ _ _              _ _ _           _   
    / ___(_) |_ ___       / / | |__   ___ | |_ 
   | |  _| | __/ _ \     / /| | '_ \ / _ \| __|
   | |_| | | || (_) |   / / | | |_) | (_) | |_ 
    \____|_|\__\___/   /_/  |_|_.__/ \___/ \__|
          GitHub Codebase AI Agent (Hybrid RAG)
===================================================================
""")


def select_or_add_repository(db_path: str = DEFAULT_STORAGE_PATH) -> str:
    """
    Prompt the user to select an existing indexed repo or add a new one.
    Returns the chosen collection name.
    """
    while True:
        collections = QdrantVectorStore.list_collections(path=db_path)
        print("\n📂 Available Repositories in Qdrant:")
        
        valid_indices = {}
        for idx, col in enumerate(collections, start=1):
            name = col["name"]
            count = col["count"]
            print(f"  [{idx}] {name} ({count} chunks indexed)")
            valid_indices[str(idx)] = name

        print("  [+] Add a new GitHub repository")
        print("  [q] Quit")

        choice = input("\nSelect an option [1..N, +, or q]: ").strip()

        if choice.lower() in ("q", "quit", "exit"):
            print("Exiting Gito.")
            sys.exit(0)

        if choice in ("+", "add", "new"):
            collection_name = index_new_repository(db_path=db_path)
            if collection_name:
                return collection_name
            continue

        if choice in valid_indices:
            selected = valid_indices[choice]
            print(f"\n✅ Selected repository: '{selected}'")
            return selected

        print("❌ Invalid option. Please choose a valid number, '+' to add, or 'q' to quit.")


def index_new_repository(
    url: Optional[str] = None,
    db_path: str = DEFAULT_STORAGE_PATH,
    embedder: Optional[Embedder] = None,
) -> Optional[str]:
    """
    Run the complete ingestion pipeline on a new GitHub repository:
    Extract -> Chunk -> Embed -> Qdrant Index.
    """
    if not url:
        print("\n" + "-" * 55)
        print("➕ Add a New GitHub Repository")
        print("-" * 55)
        url = input("Enter GitHub repository URL (e.g. https://github.com/owner/repo): ").strip()

    if not url:
        print("No URL provided. Cancelling.")
        return None

    try:
        owner, repo = parse_github_url(url)
    except Exception as e:
        print(f"❌ Invalid GitHub URL: {e}")
        return None

    collection_name = QdrantVectorStore.sanitize_collection_name(f"{owner}_{repo}")
    dest_dir = os.path.join(REPOS_CACHE_DIR, f"{owner}_{repo}")
    github_token = os.getenv("GITHUB_TOKEN")

    print(f"\nTarget Repository : {owner}/{repo}")
    print(f"Qdrant Collection : {collection_name}")
    print(f"Local Cache Path  : {dest_dir}")

    # Check if collection already exists
    existing_cols = [c["name"] for c in QdrantVectorStore.list_collections(path=db_path)]
    recreate = False
    if collection_name in existing_cols:
        re_choice = input(f"Collection '{collection_name}' already exists. Re-index? [y/N]: ").strip().lower()
        if re_choice not in ("y", "yes"):
            print(f"Using existing collection '{collection_name}'.")
            return collection_name
        recreate = True

    # 1. Extraction
    print("\n[Step 1/3] 📥 Extracting codebase via GitHub API (filtering junk/binaries)...")
    file_count = extract_repo(url, output_dir=dest_dir, token=github_token)
    if not file_count:
        print("❌ Extraction failed or repository was empty.")
        return None

    # 2. Chunking
    print(f"\n[Step 2/3] ✂️ Chunking files (AST functions for code, tokens for docs)...")
    chunks = chunk_repository(dest_dir)
    if not chunks:
        print("❌ No valid chunks found to index.")
        return None

    code_chunks = [c for c in chunks if c.get("chunk_type") == "code"]
    doc_chunks = [c for c in chunks if c.get("chunk_type") == "doc"]
    print(f"  Total chunks: {len(chunks)} ({len(code_chunks)} code, {len(doc_chunks)} docs)")

    # 3. Embedding & Indexing
    print("\n[Step 3/3] 🧠 Generating BGE embeddings & indexing into Qdrant...")
    if embedder is None:
        embedder = Embedder()

    embeddings = embedder.embed_chunks(chunks)

    vector_store = QdrantVectorStore(
        collection_name=collection_name,
        path=db_path,
    )
    if recreate:
        vector_store.ensure_collection(recreate=True)

    vector_store.index_chunks(chunks, embeddings)
    total_in_db = vector_store.count()
    vector_store.close()

    print(f"\n🎉 Successfully indexed '{owner}/{repo}' into Qdrant!")
    print(f"   Collection: '{collection_name}' ({total_in_db} points ready for search)\n")
    return collection_name


def chat_loop(
    collection_name: str,
    db_path: str = DEFAULT_STORAGE_PATH,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    embedder: Optional[Embedder] = None,
):
    """
    Interactive Q&A session with Gito for the selected repository.
    """
    print(f"\n🤖 Initializing Gito for collection: '{collection_name}'...")
    
    # Pre-warm shared embedder to avoid reloading weights
    if embedder is None:
        embedder = Embedder()

    vector_store = QdrantVectorStore(collection_name=collection_name, path=db_path)
    retriever = Retriever(
        collection_name=collection_name,
        db_path=db_path,
        embedder=embedder,
        vector_store=vector_store,
    )

    agent = GitoAgent(
        collection_name=collection_name,
        db_path=db_path,
        model=model,
        provider=provider,
        retriever=retriever,
    )

    print("\n" + "=" * 60)
    print(f"  Gito is ready! Ask anything about: '{collection_name}'")
    print("  Commands:")
    print("    :switch  - Switch or add another repository")
    print("    :top <k> - Change number of retrieved snippets (default: 5)")
    print("    :exit    - Exit Gito")
    print("=" * 60 + "\n")

    top_k = 5

    try:
        while True:
            prompt = input(f"\nGito [{collection_name}] > ").strip()
            if not prompt:
                continue

            if prompt.lower() in (":exit", "exit", "quit", ":q"):
                print("Goodbye!")
                break

            if prompt.lower() == ":switch":
                agent.close()
                new_col = select_or_add_repository(db_path=db_path)
                chat_loop(new_col, db_path=db_path, model=model, provider=provider, embedder=embedder)
                return

            if prompt.lower().startswith(":top"):
                parts = prompt.split()
                if len(parts) > 1 and parts[1].isdigit():
                    top_k = int(parts[1])
                    print(f"Retriever top_k set to {top_k}.")
                else:
                    print("Usage: :top <number>")
                continue

            print()
            agent.answer(query=prompt, top_k=top_k, stream=True)

    except (KeyboardInterrupt, EOFError):
        print("\nSession ended.")
    finally:
        agent.close()


def main():
    parser = argparse.ArgumentParser(description="Gito — GitHub Repository AI Agent")
    parser.add_argument("--repo", "-r", default=None, help="GitHub repository URL to index and query directly")
    parser.add_argument("--collection", "-c", default=None, help="Existing Qdrant collection name to use")
    parser.add_argument("--query", "-q", default=None, help="Single query to ask (non-interactive mode)")
    parser.add_argument("--db-path", default=DEFAULT_STORAGE_PATH, help="Path to local Qdrant database")
    parser.add_argument("--model", default=None, help="LLM model name")
    parser.add_argument("--provider", choices=["groq", "openai"], default=None, help="LLM provider")
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve")

    args = parser.parse_args()

    banner()

    # Shared embedder so model weights are loaded only once
    shared_embedder = None

    # Case 1: Repo URL passed via CLI
    if args.repo:
        shared_embedder = Embedder()
        collection_name = index_new_repository(
            url=args.repo,
            db_path=args.db_path,
            embedder=shared_embedder,
        )
        if not collection_name:
            print("Failed to initialize repository.")
            return
    # Case 2: Collection name explicitly passed
    elif args.collection:
        collection_name = args.collection
    # Case 3: Interactive selection menu
    else:
        collection_name = select_or_add_repository(db_path=args.db_path)

    # If single query mode
    if args.query:
        if shared_embedder is None:
            shared_embedder = Embedder()
        vector_store = QdrantVectorStore(collection_name=collection_name, path=args.db_path)
        retriever = Retriever(
            collection_name=collection_name,
            db_path=args.db_path,
            embedder=shared_embedder,
            vector_store=vector_store,
        )
        with GitoAgent(
            collection_name=collection_name,
            db_path=args.db_path,
            model=args.model,
            provider=args.provider,
            retriever=retriever,
        ) as agent:
            print(f"\nQuery: {args.query}\n")
            agent.answer(query=args.query, top_k=args.top_k, stream=True)
        return

    # Enter interactive chat loop
    chat_loop(
        collection_name=collection_name,
        db_path=args.db_path,
        model=args.model,
        provider=args.provider,
        embedder=shared_embedder,
    )


if __name__ == "__main__":
    main()
