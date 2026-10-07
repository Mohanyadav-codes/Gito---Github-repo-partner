# Gito - Github repo Agent

Gito is an agent designed to extract repositories from links, build a hybrid RAG (Retrieval-Augmented Generation) system, and answer user queries based on the codebase.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Quickstart: Unified CLI

Launch Gito's interactive terminal. It prompts you to select an existing indexed project or paste a new GitHub repo link, indexes it automatically, and drops you into a direct conversational chat:

```bash
python main.py
```

You can also pass arguments directly:
```bash
# Add/index a new repo and start chatting immediately:
python main.py --repo https://github.com/owner/repo

# Query an existing collection in one shot:
python main.py --collection gito_codebase --query "How does the auth flow work?"
```

## Individual Pipeline Steps

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

### 4. Query Retrieval
Embeds the user's question using BGE query prefixing and performs cosine similarity search against Qdrant to retrieve relevant code and doc chunks:

```bash
# One-shot query
python retriever.py "how is attendance marked or recorded?" --top-k 3

# Filter by type (code or doc)
python retriever.py "installation steps" --top-k 3 --type doc

# Interactive query mode
python retriever.py -i
```

### 5. LLM Answering Layer (`agent.py`)
Passes the retrieved codebase snippets to the LLM agent (`Gito`) with strict grounding instructions to answer user questions with file/function citations:

```bash
# Set your API key (Groq or OpenAI)
# Powershell: $env:GROQ_API_KEY = "your-groq-key"
# Or create a .env file based on .env.example

# Ask a question (streams live answer)
python agent.py "How is attendance recorded in the database?"

# Interactive chat session
python agent.py -i

# Use specific model or provider
python agent.py "Explain the API endpoints" --provider groq --model llama-3.3-70b-versatile
```
