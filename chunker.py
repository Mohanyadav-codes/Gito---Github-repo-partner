"""
chunker.py — Two-strategy chunking for Gito.

Strategy 1 (Code files):  Split by functions/classes using AST (Python) or
                           regex heuristics (JS, TS, Java, Go, Rust, etc.).
Strategy 2 (Docs/README):  Split by token count, targeting ~1000-1500 tokens
                           per chunk, respecting section/paragraph boundaries.
"""

import os
import ast
import re
import json
import tiktoken


# ──────────────────────────────────────────────────────────────────────────────
# File classification
# ──────────────────────────────────────────────────────────────────────────────

CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs',
    '.cpp', '.c', '.h', '.hpp', '.rb', '.php', '.cs', '.swift', '.kt',
}

DOC_EXTENSIONS = {'.md', '.mdx', '.rst', '.txt'}

# Filenames that should be treated as docs regardless of extension
DOC_FILENAMES = {'readme', 'license', 'changelog', 'contributing'}


def classify_file(filepath: str) -> str:
    """Return 'code', 'doc', or 'skip'."""
    ext = os.path.splitext(filepath)[1].lower()
    basename = os.path.basename(filepath).lower()
    name_no_ext = os.path.splitext(basename)[0].lower()

    if ext in DOC_EXTENSIONS or name_no_ext in DOC_FILENAMES:
        return 'doc'
    if ext in CODE_EXTENSIONS:
        return 'code'
    return 'skip'


# ──────────────────────────────────────────────────────────────────────────────
# Token counting  (using tiktoken / cl100k_base — same tokenizer as GPT-4)
# ──────────────────────────────────────────────────────────────────────────────

_encoder = None


def _get_encoder():
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def count_tokens(text: str) -> int:
    return len(_get_encoder().encode(text))


# ──────────────────────────────────────────────────────────────────────────────
# Strategy 1 — Code chunking (by function / class)
# ──────────────────────────────────────────────────────────────────────────────

def _chunk_python(filepath: str, content: str) -> list[dict]:
    """Use Python's `ast` module for precise function/class extraction."""
    lines = content.splitlines(keepends=True)

    try:
        tree = ast.parse(content)
    except SyntaxError:
        # Fall back to the generic regex chunker
        return _chunk_code_generic(filepath, content)

    # Gather top-level function / class nodes
    nodes = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = 'class' if isinstance(node, ast.ClassDef) else 'function'
            nodes.append({
                'start': node.lineno - 1,       # 0-indexed
                'end':   node.end_lineno,        # exclusive
                'name':  node.name,
                'kind':  kind,
            })

    if not nodes:
        # No functions/classes — return the whole file as one chunk
        return [_make_code_chunk(filepath, 'python', os.path.basename(filepath), content)]

    nodes.sort(key=lambda n: n['start'])
    chunks = []

    # Module header (imports / globals before the first definition)
    if nodes[0]['start'] > 0:
        header = ''.join(lines[: nodes[0]['start']])
        if header.strip():
            chunks.append(
                _make_code_chunk(filepath, 'python', f"{os.path.basename(filepath)}:module_header", header)
            )

    # Each function / class
    for node in nodes:
        body = ''.join(lines[node['start'] : node['end']])
        chunks.append(
            _make_code_chunk(filepath, 'python', f"{os.path.basename(filepath)}:{node['name']}", body)
        )

    return chunks


# Regex patterns for detecting function/method starts per language
_FUNC_PATTERNS: dict[str, str] = {
    '.js':    r'^(?:export\s+)?(?:async\s+)?function\s+\w+|^(?:export\s+)?(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?(?:\([^)]*\)|[^=])\s*=>',
    '.ts':    r'^(?:export\s+)?(?:async\s+)?function\s+\w+|^(?:export\s+)?(?:const|let|var)\s+\w+\s*[=:]',
    '.jsx':   r'^(?:export\s+)?(?:async\s+)?function\s+\w+|^(?:export\s+)?(?:const|let|var)\s+\w+\s*=',
    '.tsx':   r'^(?:export\s+)?(?:async\s+)?function\s+\w+|^(?:export\s+)?(?:const|let|var)\s+\w+\s*=',
    '.java':  r'^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?(?:\w+\s+)+\w+\s*\(',
    '.go':    r'^func\s+',
    '.rs':    r'^(?:pub\s+)?(?:async\s+)?fn\s+',
    '.cpp':   r'^\w[\w\s\*&:<>]+\w+\s*\([^;]*$',
    '.c':     r'^\w[\w\s\*]+\w+\s*\([^;]*$',
    '.h':     r'^\w[\w\s\*]+\w+\s*\([^;]*$',
    '.hpp':   r'^\w[\w\s\*&:<>]+\w+\s*\([^;]*$',
    '.rb':    r'^\s*def\s+',
    '.php':   r'^\s*(?:public|private|protected)?\s*(?:static\s+)?function\s+',
    '.cs':    r'^\s*(?:public|private|protected|internal)?\s*(?:static\s+)?(?:async\s+)?(?:\w+\s+)+\w+\s*\(',
    '.swift': r'^\s*(?:public|private|internal|fileprivate|open)?\s*(?:static|class)?\s*func\s+',
    '.kt':    r'^\s*(?:public|private|protected|internal)?\s*(?:suspend\s+)?fun\s+',
}


def _chunk_code_generic(filepath: str, content: str) -> list[dict]:
    """Regex-based function splitting for non-Python languages."""
    ext = os.path.splitext(filepath)[1].lower()
    lang = ext.lstrip('.')
    pattern = _FUNC_PATTERNS.get(ext)

    if not pattern:
        return [_make_code_chunk(filepath, lang, os.path.basename(filepath), content)]

    lines = content.splitlines(keepends=True)
    func_starts: list[int] = [i for i, line in enumerate(lines) if re.search(pattern, line)]

    if not func_starts:
        return [_make_code_chunk(filepath, lang, os.path.basename(filepath), content)]

    chunks = []

    # Header (imports, etc.) before the first match
    if func_starts[0] > 0:
        header = ''.join(lines[: func_starts[0]])
        if header.strip():
            chunks.append(_make_code_chunk(filepath, lang, f"{os.path.basename(filepath)}:header", header))

    for idx, start in enumerate(func_starts):
        end = func_starts[idx + 1] if idx + 1 < len(func_starts) else len(lines)
        body = ''.join(lines[start:end])

        # Try to pull the function name from the first line
        first_line = lines[start].strip()
        m = re.search(r'(?:function|def|fn|func|fun)\s+(\w+)', first_line)
        if not m:
            m = re.search(r'(?:const|let|var)\s+(\w+)', first_line)
        name = m.group(1) if m else f'block_{idx}'

        chunks.append(_make_code_chunk(filepath, lang, f"{os.path.basename(filepath)}:{name}", body))

    return chunks


def _make_code_chunk(filepath: str, language: str, name: str, content: str) -> dict:
    return {
        'filepath':   filepath,
        'chunk_type': 'code',
        'language':   language,
        'name':       name,
        'content':    content,
    }


def chunk_code_file(filepath: str, content: str) -> list[dict]:
    """Route to the right code chunker based on extension."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.py':
        return _chunk_python(filepath, content)
    return _chunk_code_generic(filepath, content)


# ──────────────────────────────────────────────────────────────────────────────
# Strategy 2 — Doc chunking (by token window, ~1000-1500 tokens)
# ──────────────────────────────────────────────────────────────────────────────

def chunk_doc_file(
    filepath: str,
    content: str,
    min_tokens: int = 1000,
    max_tokens: int = 1500,
) -> list[dict]:
    """
    Chunk markdown / text docs into ~1000-1500 token windows.
    Splitting priority: heading boundaries → paragraph boundaries → sentences.
    Small trailing fragments are merged into the previous or next chunk.
    """
    # Split on markdown headings, keeping the heading with the section that follows
    sections = re.split(r'(?=^#{1,6}\s+)', content, flags=re.MULTILINE)

    # Flatten sections into paragraph-level pieces, then into sentence-level pieces
    # so we always have small enough units to pack into windows.
    pieces: list[str] = []
    for section in sections:
        if not section:
            continue
        sec_tokens = count_tokens(section)
        if sec_tokens <= max_tokens:
            pieces.append(section)
        else:
            # Split by paragraphs
            paragraphs = re.split(r'\n\n+', section)
            for para in paragraphs:
                if not para.strip():
                    continue
                para_tokens = count_tokens(para)
                if para_tokens <= max_tokens:
                    pieces.append(para + '\n\n')
                else:
                    # Split by sentences as last resort
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    for sent in sentences:
                        if sent.strip():
                            pieces.append(sent + ' ')

    # Now greedily pack pieces into chunks of ~min_tokens..max_tokens
    chunks: list[dict] = []
    current_text = ''
    current_tokens = 0

    for piece in pieces:
        piece_tokens = count_tokens(piece)

        if current_tokens + piece_tokens > max_tokens and current_tokens >= min_tokens:
            # Current buffer is full enough — flush it
            chunks.append(_make_doc_chunk(filepath, len(chunks), current_text, current_tokens))
            current_text = piece
            current_tokens = piece_tokens
        else:
            current_text += piece
            current_tokens += piece_tokens

    # Flush remainder — merge into the last chunk if it's too small
    if current_text.strip():
        if current_tokens < min_tokens and chunks:
            prev = chunks[-1]
            prev['content'] = prev['content'] + '\n\n' + current_text.strip()
            prev['token_count'] += current_tokens
        else:
            chunks.append(_make_doc_chunk(filepath, len(chunks), current_text, current_tokens))

    return chunks


def _make_doc_chunk(filepath: str, index: int, content: str, token_count: int) -> dict:
    return {
        'filepath':    filepath,
        'chunk_type':  'doc',
        'name':        f'{os.path.basename(filepath)}:chunk_{index}',
        'content':     content.strip(),
        'token_count': token_count,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Public API — walk a repo directory and chunk everything
# ──────────────────────────────────────────────────────────────────────────────

def chunk_repository(repo_dir: str) -> list[dict]:
    """
    Walk an extracted repo directory and return a flat list of chunks.
    Each chunk is a dict with keys: filepath, chunk_type, name, content, …
    """
    all_chunks: list[dict] = []

    for root, _dirs, files in os.walk(repo_dir):
        for filename in files:
            abs_path = os.path.join(root, filename)
            rel_path = os.path.relpath(abs_path, repo_dir).replace('\\', '/')

            ftype = classify_file(rel_path)
            if ftype == 'skip':
                continue

            try:
                with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                continue

            if not content.strip():
                continue

            if ftype == 'code':
                all_chunks.extend(chunk_code_file(rel_path, content))
            else:
                all_chunks.extend(chunk_doc_file(rel_path, content))

    return all_chunks


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Chunk extracted repository files for RAG.")
    parser.add_argument('repo_dir', help="Path to the extracted repo directory")
    parser.add_argument('--output', '-o', default='chunks.json', help="Output JSON file (default: chunks.json)")
    args = parser.parse_args()

    chunks = chunk_repository(args.repo_dir)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    code_chunks = [c for c in chunks if c['chunk_type'] == 'code']
    doc_chunks  = [c for c in chunks if c['chunk_type'] == 'doc']

    print(f"\nChunking complete!")
    print(f"  Total chunks : {len(chunks)}")
    print(f"  Code chunks  : {len(code_chunks)}")
    print(f"  Doc chunks   : {len(doc_chunks)}")
    print(f"  Saved to     : {args.output}")
