"""
generate_docs_pdf.py — Generates Gito Technical Documentation & Architecture PDF.

Uses ReportLab to build a professional, visually structured reference guide with:
- System Architecture Diagram
- Dual-Strategy Chunking Flowchart
- Tech Stack Breakdown
- Code Map & Modification Cheat Sheet
- Step-by-Step Implementation Details
"""

import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import (
    Drawing,
    Rect,
    String,
    Line,
    Group,
    Polygon,
)
from reportlab.pdfgen import canvas


# ──────────────────────────────────────────────────────────────────────────────
# Palette & Colors
# ──────────────────────────────────────────────────────────────────────────────

PRIMARY = colors.HexColor("#1E293B")       # Slate 800 (Dark background/headers)
ACCENT_BLUE = colors.HexColor("#2563EB")   # Blue 600
ACCENT_CYAN = colors.HexColor("#0284C7")   # Sky 600
ACCENT_GREEN = colors.HexColor("#16A34A")  # Green 600
ACCENT_PURPLE = colors.HexColor("#7C3AED") # Purple 600
ACCENT_AMBER = colors.HexColor("#D97706")  # Amber 600
BG_LIGHT = colors.HexColor("#F8FAFC")      # Slate 50
BG_CARD = colors.HexColor("#F1F5F9")       # Slate 100
BORDER_COLOR = colors.HexColor("#CBD5E1")  # Slate 300
TEXT_DARK = colors.HexColor("#0F172A")     # Slate 900
TEXT_MUTED = colors.HexColor("#475569")    # Slate 600
TEXT_LIGHT = colors.HexColor("#FFFFFF")


# ──────────────────────────────────────────────────────────────────────────────
# Canvas with Header/Footer and Page Numbers
# ──────────────────────────────────────────────────────────────────────────────

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(TEXT_MUTED)

        # Header (pages 2+)
        if self._pageNumber > 1:
            self.drawString(54, 755, "GITO — GITHUB REPOSITORY AI AGENT | TECHNICAL ARCHITECTURE")
            self.setStrokeColor(BORDER_COLOR)
            self.setLineWidth(0.6)
            self.line(54, 748, 558, 748)

        # Footer
        self.setStrokeColor(BORDER_COLOR)
        self.setLineWidth(0.6)
        self.line(54, 42, 558, 42)
        self.setFont("Helvetica", 8)
        self.drawString(54, 30, "Gito Hybrid RAG Architecture Specification — Confidential & Technical Reference")
        self.drawRightString(558, 30, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


# ──────────────────────────────────────────────────────────────────────────────
# Flowchart & Diagram Generators
# ──────────────────────────────────────────────────────────────────────────────

def create_pipeline_diagram() -> Drawing:
    """Generates the End-to-End Architecture Flowchart."""
    d = Drawing(504, 175)

    # Ingestion Pipeline Header
    d.add(Rect(0, 155, 504, 18, fillColor=BG_CARD, strokeColor=BORDER_COLOR, rx=3, ry=3))
    d.add(String(10, 160, "INGESTION PIPELINE (Offline / On-Demand Indexing)", fontName="Helvetica-Bold", fontSize=8, fillColor=PRIMARY))

    # Boxes: Ingestion Phase
    boxes_ingestion = [
        (10, 105, 80, 40, "1. GitHub URL", "REST API Tree", ACCENT_BLUE),
        (110, 105, 85, 40, "2. extractor.py", "Exclude Junk", ACCENT_CYAN),
        (215, 105, 85, 40, "3. chunker.py", "AST & Tokens", ACCENT_PURPLE),
        (320, 105, 85, 40, "4. embedder.py", "BGE-Small (384d)", ACCENT_AMBER),
        (425, 105, 75, 40, "5. Qdrant DB", "Collection Store", ACCENT_GREEN),
    ]

    for x, y, w, h, title, sub, color in boxes_ingestion:
        d.add(Rect(x, y, w, h, fillColor=BG_LIGHT, strokeColor=color, strokeWidth=1.5, rx=4, ry=4))
        d.add(Rect(x, y + 26, w, 14, fillColor=color, strokeColor=color, rx=2, ry=2))
        d.add(String(x + 5, y + 29, title, fontName="Helvetica-Bold", fontSize=7, fillColor=TEXT_LIGHT))
        d.add(String(x + 5, y + 10, sub, fontName="Helvetica", fontSize=6.5, fillColor=TEXT_DARK))

    # Ingestion Arrows
    for x_arr in [90, 195, 300, 405]:
        d.add(Line(x_arr, 125, x_arr + 20, 125, strokeColor=TEXT_MUTED, strokeWidth=1.2))
        d.add(Polygon([x_arr + 20, 125, x_arr + 15, 128, x_arr + 15, 122], fillColor=TEXT_MUTED, strokeColor=TEXT_MUTED))

    # Query Pipeline Header
    d.add(Rect(0, 75, 504, 18, fillColor=BG_CARD, strokeColor=BORDER_COLOR, rx=3, ry=3))
    d.add(String(10, 80, "QUERY & RETRIEVAL PIPELINE (Real-Time User Serving)", fontName="Helvetica-Bold", fontSize=8, fillColor=PRIMARY))

    # Boxes: Query Phase
    boxes_query = [
        (10, 20, 95, 45, "User Question", "Prompt Ingestion", ACCENT_BLUE),
        (125, 20, 105, 45, "retriever.py", "BGE Query Prefix", ACCENT_AMBER),
        (250, 20, 110, 45, "Qdrant Cosine Match", "Top-K Chunks + Payload", ACCENT_GREEN),
        (380, 20, 115, 45, "agent.py (LLM)", "Grounded Citations", ACCENT_PURPLE),
    ]

    for x, y, w, h, title, sub, color in boxes_query:
        d.add(Rect(x, y, w, h, fillColor=BG_LIGHT, strokeColor=color, strokeWidth=1.5, rx=4, ry=4))
        d.add(Rect(x, y + 31, w, 14, fillColor=color, strokeColor=color, rx=2, ry=2))
        d.add(String(x + 5, y + 34, title, fontName="Helvetica-Bold", fontSize=7, fillColor=TEXT_LIGHT))
        d.add(String(x + 5, y + 14, sub, fontName="Helvetica", fontSize=6.5, fillColor=TEXT_DARK))

    # Query Arrows
    for x_arr in [105, 230, 360]:
        d.add(Line(x_arr, 42, x_arr + 20, 42, strokeColor=TEXT_MUTED, strokeWidth=1.2))
        d.add(Polygon([x_arr + 20, 42, x_arr + 15, 45, x_arr + 15, 39], fillColor=TEXT_MUTED, strokeColor=TEXT_MUTED))

    # Link from Qdrant storage down to Qdrant matching
    d.add(Line(462, 105, 462, 85, strokeColor=ACCENT_GREEN, strokeWidth=1.2))
    d.add(Line(462, 85, 305, 85, strokeColor=ACCENT_GREEN, strokeWidth=1.2))
    d.add(Line(305, 85, 305, 65, strokeColor=ACCENT_GREEN, strokeWidth=1.2))
    d.add(Polygon([305, 65, 302, 70, 308, 70], fillColor=ACCENT_GREEN, strokeColor=ACCENT_GREEN))

    return d


def create_chunking_diagram() -> Drawing:
    """Generates the Dual-Strategy Chunking Mechanism Diagram."""
    d = Drawing(504, 110)

    # Left: Code Strategy
    d.add(Rect(0, 0, 245, 110, fillColor=BG_LIGHT, strokeColor=ACCENT_PURPLE, strokeWidth=1.5, rx=4, ry=4))
    d.add(Rect(0, 88, 245, 22, fillColor=ACCENT_PURPLE, strokeColor=ACCENT_PURPLE, rx=3, ry=3))
    d.add(String(8, 94, "STRATEGY A: CODE CHUNKING", fontName="Helvetica-Bold", fontSize=8.5, fillColor=TEXT_LIGHT))
    d.add(String(8, 73, "• Target: .py, .js, .ts, .jsx, .tsx, .java, .go, .rs, .c, .cpp", fontName="Helvetica", fontSize=7.5, fillColor=TEXT_DARK))
    d.add(String(8, 58, "• Python: AST (Abstract Syntax Tree) splits by Class/Function", fontName="Helvetica", fontSize=7.5, fillColor=TEXT_DARK))
    d.add(String(8, 43, "• Polyglot: Regex pattern heuristics for definitions/exports", fontName="Helvetica", fontSize=7.5, fillColor=TEXT_DARK))
    d.add(String(8, 28, "• Header Extraction: Imports & constants -> 'module_header'", fontName="Helvetica", fontSize=7.5, fillColor=TEXT_DARK))
    d.add(String(8, 13, "• Output: 1 chunk per logical function with exact name metadata", fontName="Helvetica-Bold", fontSize=7.5, fillColor=ACCENT_PURPLE))

    # Right: Doc Strategy
    d.add(Rect(255, 0, 245, 110, fillColor=BG_LIGHT, strokeColor=ACCENT_CYAN, strokeWidth=1.5, rx=4, ry=4))
    d.add(Rect(255, 88, 245, 22, fillColor=ACCENT_CYAN, strokeColor=ACCENT_CYAN, rx=3, ry=3))
    d.add(String(263, 94, "STRATEGY B: DOC & README CHUNKING", fontName="Helvetica-Bold", fontSize=8.5, fillColor=TEXT_LIGHT))
    d.add(String(263, 73, "• Target: .md, .mdx, .rst, .txt, README, LICENSE, GUIDES", fontName="Helvetica", fontSize=7.5, fillColor=TEXT_DARK))
    d.add(String(263, 58, "• Token Window: 1,000 to 1,500 tokens (tiktoken cl100k_base)", fontName="Helvetica", fontSize=7.5, fillColor=TEXT_DARK))
    d.add(String(263, 43, "• 3-Tier Split: Markdown Headings -> Paragraphs -> Sentences", fontName="Helvetica", fontSize=7.5, fillColor=TEXT_DARK))
    d.add(String(263, 28, "• Anti-Orphan: Tiny heading fragments merged into adjacent chunk", fontName="Helvetica", fontSize=7.5, fillColor=TEXT_DARK))
    d.add(String(263, 13, "• Output: Dense contextual passages with token count payload", fontName="Helvetica-Bold", fontSize=7.5, fillColor=ACCENT_CYAN))

    return d


# ──────────────────────────────────────────────────────────────────────────────
# Main Document Builder
# ──────────────────────────────────────────────────────────────────────────────

def build_pdf(output_filename="GITO_TECHNICAL_DOCUMENTATION.pdf"):
    doc = SimpleDocTemplate(
        output_filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom Typography Styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=PRIMARY,
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=TEXT_MUTED,
        spaceAfter=12,
    )

    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=PRIMARY,
        spaceBefore=10,
        spaceAfter=6,
    )

    h2_style = ParagraphStyle(
        "SectionH2",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=ACCENT_BLUE,
        spaceBefore=6,
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=TEXT_DARK,
        spaceAfter=5,
    )

    bullet_style = ParagraphStyle(
        "BulletCustom",
        parent=body_style,
        leftIndent=12,
        bulletIndent=4,
        spaceAfter=3,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=TEXT_LIGHT,
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=TEXT_DARK,
    )

    code_style = ParagraphStyle(
        "CodeText",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=7.5,
        leading=9.5,
        textColor=PRIMARY,
    )

    story = []

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 1: TITLE, EXECUTIVE SUMMARY & END-TO-END FLOWCHART
    # ──────────────────────────────────────────────────────────────────────────

    story.append(Paragraph("Gito — GitHub Repository AI Partner", title_style))
    story.append(Paragraph("Comprehensive Technical Architecture, Pipeline Flow & Developer Reference Guide", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=ACCENT_BLUE, spaceAfter=8))

    # Executive Overview Box
    overview_text = (
        "<b>Executive Overview:</b> Gito is an autonomous codebase agent built on a <b>Hybrid RAG (Retrieval-Augmented Generation)</b> architecture. "
        "It ingests any public or private GitHub repository via API, filters junk and binary files, splits code semantically by function "
        "(via AST) and documentation by token windows, embeds chunks using the state-of-the-art <b>BAAI/bge-small-en-v1.5</b> model, "
        "and indexes them into a localized <b>Qdrant</b> vector database. When a user queries the repo, Gito performs asymmetric vector similarity search "
        "and injects grounded context snippets into an LLM answering layer to deliver cited, accurate answers."
    )
    story.append(Paragraph(overview_text, body_style))
    story.append(Spacer(1, 6))

    # End-to-End Pipeline Diagram
    story.append(Paragraph("1. High-Level System Architecture & Flowchart", h1_style))
    story.append(create_pipeline_diagram())
    story.append(Spacer(1, 8))

    # Tech Stack Table
    story.append(Paragraph("2. Core Technology Stack Cheat Sheet", h1_style))

    tech_data = [
        [
            Paragraph("Component", table_header_style),
            Paragraph("Technology / Library", table_header_style),
            Paragraph("Key Role & Implementation Detail", table_header_style),
        ],
        [
            Paragraph("<b>Repo Extraction</b>", table_cell_style),
            Paragraph("GitHub REST API v3<br/><code>requests</code>", code_style),
            Paragraph("Recursive tree fetching (<code>git/trees?recursive=1</code>). Downloads raw files while bypassing binaries, lock files, and node_modules.", table_cell_style),
        ],
        [
            Paragraph("<b>Code Chunking</b>", table_cell_style),
            Paragraph("Python <code>ast</code><br/>Regex Heuristics", code_style),
            Paragraph("Extracts discrete functions, methods, and classes. Preserves module-level headers (imports & global variables).", table_cell_style),
        ],
        [
            Paragraph("<b>Doc Chunking</b>", table_cell_style),
            Paragraph("<code>tiktoken</code><br/>(cl100k_base)", code_style),
            Paragraph("Hierarchical 3-tier splitting: Headings -> Paragraphs -> Sentences. Targets 1,000–1,500 token windows without orphan headings.", table_cell_style),
        ],
        [
            Paragraph("<b>Vector Embeddings</b>", table_cell_style),
            Paragraph("<code>BAAI/bge-small-en-v1.5</code><br/><code>sentence-transformers</code>", code_style),
            Paragraph("384-dimensional dense vectors. L2-normalized so cosine similarity is computed via dot product. Queries use asymmetric instruction prefix.", table_cell_style),
        ],
        [
            Paragraph("<b>Vector Database</b>", table_cell_style),
            Paragraph("<code>qdrant-client</code> (v1.19+)<br/>Local Persistent Storage", code_style),
            Paragraph("On-disk storage in <code>./qdrant_db/</code> (no Docker required). Stores full chunk payload (filepath, name, type, code content) for fast lookup.", table_cell_style),
        ],
        [
            Paragraph("<b>LLM Layer</b>", table_cell_style),
            Paragraph("<code>groq</code> / <code>openai</code><br/>Pluggable Architecture", code_style),
            Paragraph("Grounded system prompt enforcing <code>[file:function]</code> citations. Supports real-time token streaming and dry-run fallback.", table_cell_style),
        ],
    ]

    tech_table = Table(tech_data, colWidths=[1.3 * inch, 1.7 * inch, 4.0 * inch])
    tech_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BG_LIGHT, BG_CARD]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    story.append(tech_table)
    story.append(PageBreak())

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 2: FEATURE DEEP-DIVES & CHUNKING STRATEGY
    # ──────────────────────────────────────────────────────────────────────────

    story.append(Paragraph("3. Deep-Dive: How Backend Features Were Built", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceAfter=8))

    # Feature 1
    story.append(Paragraph("A. Smart Ingestion & Exclusion Engine (<code>extractor.py</code>)", h2_style))
    story.append(Paragraph(
        "Standard repo clones bloat embeddings with multi-megabyte lock files, minified bundles, and compiled binaries. "
        "Gito avoids this completely by querying the recursive Git tree endpoint and evaluating every path against strict exclusion predicates:",
        body_style
    ))
    story.append(Paragraph("• <b>Excluded Directories:</b> <code>.git/</code>, <code>node_modules/</code>, <code>venv/</code>, <code>dist/</code>, <code>build/</code>, <code>__pycache__/</code>, <code>target/</code>, <code>vendor/</code>", bullet_style))
    story.append(Paragraph("• <b>Excluded Binaries/Media:</b> Images (<code>.png</code>, <code>.jpg</code>), video (<code>.mp4</code>), archives (<code>.zip</code>, <code>.tar.gz</code>), binaries (<code>.exe</code>, <code>.dll</code>), datasets (<code>.csv</code>, <code>.sqlite</code>)", bullet_style))
    story.append(Paragraph("• <b>Excluded Locks & Configs:</b> <code>package-lock.json</code>, <code>yarn.lock</code>, <code>.env</code>, <code>.gitignore</code>, and linter dotfiles (<code>.*rc</code>, <code>.*rc.json</code>)", bullet_style))
    story.append(Paragraph("• <b>Direct Raw Streaming:</b> Downloads valid source files directly from <code>raw.githubusercontent.com</code>, preserving repository folder structure.", bullet_style))
    story.append(Spacer(1, 6))

    # Feature 2 & Chunking Diagram
    story.append(Paragraph("B. Dual-Strategy Chunking Engine (<code>chunker.py</code>)", h2_style))
    story.append(Paragraph(
        "RAG systems fail when code is split arbitrarily across line numbers. Gito implements two distinct, tailored chunking strategies:",
        body_style
    ))
    story.append(create_chunking_diagram())
    story.append(Spacer(1, 6))

    # Feature 3
    story.append(Paragraph("C. BGE Embedding & Vector Normalization (<code>embedder.py</code>)", h2_style))
    story.append(Paragraph(
        "Gito utilizes <b>BAAI/bge-small-en-v1.5</b> (384 dimensions). This model achieves MTEB benchmark performance while running fast on standard CPUs. Key mechanics:",
        body_style
    ))
    story.append(Paragraph("• <b>Asymmetric Query Prefixing:</b> BGE requires queries to be prepended with <code>\"Represent this sentence: \"</code> to bridge the semantic asymmetry between short questions and dense code blocks. Documents/chunks are embedded as-is.", bullet_style))
    story.append(Paragraph("• <b>L2-Normalization:</b> Vectors are normalized to unit length (<code>||v|| = 1.0</code>). This mathematically reduces cosine similarity to a simple vector dot product, enabling lightning-fast distance computations in Qdrant.", bullet_style))
    story.append(Spacer(1, 6))

    # Feature 4
    story.append(Paragraph("D. Qdrant Local Multi-Tenant Storage (<code>qdrant_store.py</code>)", h2_style))
    story.append(Paragraph(
        "Instead of storing loose binary arrays on disk, Gito integrates <b>Qdrant</b> in embedded file mode (<code>./qdrant_db/</code>):",
        body_style
    ))
    story.append(Paragraph("• <b>Sanitized Multi-Repo Collections:</b> Each repository receives its own isolated Qdrant collection named after <code>owner_repo</code> (e.g., <code>octocat_hello-world</code>).", bullet_style))
    story.append(Paragraph("• <b>Rich Payload Metadata:</b> Along with the 384-d vector, each point stores: <code>filepath</code>, <code>chunk_type</code>, <code>name</code>, <code>content</code>, and <code>language</code>. No secondary database lookups are needed.", bullet_style))
    story.append(Paragraph("• <b>Qdrant 1.19+ API:</b> Uses modern <code>query_points()</code> with optional payload filtering by <code>chunk_type</code>.", bullet_style))

    story.append(PageBreak())

    # ──────────────────────────────────────────────────────────────────────────
    # PAGE 3: CODE MAP, DEVELOPER CHEAT SHEET & QUERY CYCLE
    # ──────────────────────────────────────────────────────────────────────────

    story.append(Paragraph("4. Code Map & Developer Reference (What Each File Does)", h1_style))
    story.append(Paragraph("Use this cheat sheet whenever you need to modify, optimize, or extend any part of the Gito backend:", body_style))
    story.append(Spacer(1, 4))

    code_map_data = [
        [
            Paragraph("File", table_header_style),
            Paragraph("Core Classes & Functions", table_header_style),
            Paragraph("What It Does & When to Modify", table_header_style),
        ],
        [
            Paragraph("<code>extractor.py</code>", code_style),
            Paragraph("<code>extract_repo()</code><br/><code>is_excluded()</code><br/><code>parse_github_url()</code>", code_style),
            Paragraph("Handles GitHub API repository download and filtering.<br/><b>Modify when:</b> Adding new ignored file extensions, changing GitHub branch rules, or supporting enterprise GitHub URLs.", table_cell_style),
        ],
        [
            Paragraph("<code>chunker.py</code>", code_style),
            Paragraph("<code>chunk_repository()</code><br/><code>chunk_code_file()</code><br/><code>chunk_doc_file()</code><br/><code>_chunk_python()</code>", code_style),
            Paragraph("Splits files into semantic chunks.<br/><b>Modify when:</b> Adding AST support for new programming languages, adjusting the 1,000–1,500 token window, or tuning markdown heading split rules.", table_cell_style),
        ],
        [
            Paragraph("<code>embedder.py</code>", code_style),
            Paragraph("<code>Embedder</code><br/><code>.embed_chunks()</code><br/><code>.embed_query()</code>", code_style),
            Paragraph("Generates 384-d BGE vector embeddings.<br/><b>Modify when:</b> Changing the embedding model (e.g., to BGE-base or voyage-code), altering batch sizes, or modifying query prefixes.", table_cell_style),
        ],
        [
            Paragraph("<code>qdrant_store.py</code>", code_style),
            Paragraph("<code>QdrantVectorStore</code><br/><code>.index_chunks()</code><br/><code>.search()</code><br/><code>.list_collections()</code>", code_style),
            Paragraph("Manages Qdrant vector database storage & search.<br/><b>Modify when:</b> Changing database location (<code>./qdrant_db</code>), adding remote cloud credentials, or adding payload filter fields.", table_cell_style),
        ],
        [
            Paragraph("<code>retriever.py</code>", code_style),
            Paragraph("<code>Retriever</code><br/><code>.retrieve()</code><br/><code>.format_context()</code>", code_style),
            Paragraph("Orchestrates query embedding and vector search matching.<br/><b>Modify when:</b> Tuning <code>top_k</code> defaults, setting minimum similarity thresholds, or modifying the context block prompt template.", table_cell_style),
        ],
        [
            Paragraph("<code>agent.py</code>", code_style),
            Paragraph("<code>GitoAgent</code><br/><code>.answer()</code><br/><code>SYSTEM_PROMPT</code>", code_style),
            Paragraph("The LLM answering layer.<br/><b>Modify when:</b> Editing Gito's system prompt instructions, adding new LLM providers (Anthropic, DeepSeek), or adjusting temperature and streaming parameters.", table_cell_style),
        ],
        [
            Paragraph("<code>main.py</code>", code_style),
            Paragraph("<code>main()</code><br/><code>chat_loop()</code><br/><code>index_new_repository()</code><br/><code>select_or_add_repository()</code>", code_style),
            Paragraph("Unified CLI entrypoint connecting the complete pipeline.<br/><b>Modify when:</b> Adding new CLI flags, enhancing menu options, or hooking up backend events to a frontend UI.", table_cell_style),
        ],
    ]

    code_map_table = Table(code_map_data, colWidths=[1.1 * inch, 1.9 * inch, 4.0 * inch])
    code_map_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BG_LIGHT, BG_CARD]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    story.append(code_map_table)
    story.append(Spacer(1, 10))

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 5: THE USER QUERY & ANSWERING CYCLE
    # ──────────────────────────────────────────────────────────────────────────

    story.append(Paragraph("5. Step-by-Step Query & Answering Lifecycle", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceAfter=8))

    cycle_steps = [
        "<b>1. User Question Ingestion:</b> User types a query (e.g. <i>\"How does authentication work?\"</i>).",
        "<b>2. Query Normalization & Embedding:</b> Query is prefixed with <code>\"Represent this sentence: \"</code>, passed to BGE-Small, and normalized to unit length.",
        "<b>3. Qdrant Cosine Retrieval:</b> Qdrant executes cosine distance comparison against all vectors in the collection, returning top-$k$ hits with payloads.",
        "<b>4. Prompt Construction & Grounding:</b> Retrieved code/doc chunks are formatted into numbered source blocks with metadata: <code>[Source 1] auth.py (auth.py:verify_token) | Score: 0.8120</code>.",
        "<b>5. LLM Synthesis & Streaming:</b> The LLM receives the system prompt + context and streams a cited, grounded response directly to the user.",
    ]

    for step in cycle_steps:
        story.append(Paragraph(f"• {step}", bullet_style))

    story.append(Spacer(1, 8))

    # Quickstart Box
    quickstart_data = [
        [
            Paragraph("<b>CLI Quickstart Command:</b>", table_header_style),
            Paragraph("<code>python main.py</code> (Launches interactive menu to select existing repo or index a new one)", table_header_style),
        ]
    ]
    qs_table = Table(quickstart_data, colWidths=[2.2 * inch, 4.8 * inch])
    qs_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT_BLUE),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(qs_table)

    # Build the document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"\n[SUCCESS] Generated documentation PDF: {output_filename}")


if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "GITO_TECHNICAL_DOCUMENTATION.pdf"
    build_pdf(out_file)
