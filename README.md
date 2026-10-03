# Gito - Github repo Agent

Gito is an agent designed to extract repositories from links, build a hybrid RAG (Retrieval-Augmented Generation) system, and answer user queries based on the codebase.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Pipeline Steps

### 1. Extract Repository
Extract code, docs, and README from GitHub API while filtering out git history, node_modules, build directories, binaries, and secrets:

```bash
python extractor.py https://github.com/owner/repo -o repo_output
```

### 2. Chunking
- **Code files**: Chunked by function/class (Python AST, multi-language regex).
- **Docs / README**: Chunked by token window (~1000–1500 tokens).

```bash
python chunker.py repo_output/ -o chunks.json
```

### 3. Embed & Store into Qdrant Vector DB
Embeds all chunks using `BAAI/bge-small-en-v1.5` (384 dimensions) and indexes them into **Qdrant**:

```bash
python embedder.py repo_output/ --collection gito_codebase --db-path ./qdrant_db
```

#### Vector DB Features:
- **Embedded / Local Storage**: Stored on disk in `./qdrant_db` (no Docker or external server setup required).
- **Remote / Cloud Support**: Supports Qdrant Cloud or Docker container by specifying `QDRANT_URL` and `QDRANT_API_KEY`.
- **Payload storage**: Stores code/doc content, file paths, chunk names, and types directly inside each vector point for instant retrieval.
