# 🕵️ Deep Dive: How It Works

This document provides a step-by-step explanation of the internal workflows within the SAGE-Docs application. It complements the high-level architecture view by detailing the "whens" and "whys" of each process.

---

## 1. 🚀 Application Startup

When you run `docker-compose up`, the following initialization sequence occurs:

### A. Infrastructure Layer (Qdrant)
1. **Container Start**: The `qdrant` service starts first (port 6334/6333).
2. **Volume Mount**: It mounts `qdrant_data` to persist vector data between restarts.
3. **Readiness**: Other services (`dashboard`, `mcp-server`) wait for Qdrant to be responsive.

### B. Dashboard & MCP Server Initialization
Both Python services follow a similar startup routine (defined in `lifespan` context managers):

1. **Model Pre-loading**:
   - The application downloads (if not cached) and loads the Embedding Models into memory.
   - **Dense Model**: `sentence-transformers/all-MiniLM-L6-v2` (~90MB). Used for semantic understanding.
   - **Sparse Model**: `Qdrant/bm25` (Specialized BERT). Used for keyword matching.
   *Why?* Pre-loading avoids latency on the first user request.

2. **Collection Verification (`ensure_collection`)**:
   - The app checks if the `sage_docs` collection exists in Qdrant.
   - **If Missing**: It creates the collection with specific configuration:
     - **Vectors**: Configured for 384-dim dense vectors (Cosine distance).
     - **Sparse Vectors**: Configured for BM25 keyword vectors.
     - **Quantization**: `INT8` scalar quantization is enabled to reduce RAM usage by ~4x with minimal accuracy loss.
     - **Indexes**: Payload indexes are created for `library`, `version`, and `file_path` fields to ensure filtering (e.g., "search only React docs") is O(1) fast.

---

## 2. 📥 Ingestion Workflow (Upload -> Index)

When a user uploads a file, it goes through a transformation pipeline to become searchable.

### Step 1: File Reception
- **Endpoint**: `POST /api/upload`
- **Input**: File (blob), Library Name (e.g., "react"), Version (e.g., "18.0").
- The file is read into memory (RAM).

### Step 2: Content Extraction (`process_file`)
The system detects the file type and extracts clean text:
- **Markdown/Text**: Decoded directly.
- **HTML**: Cleaned with BeautifulSoup (scripts removed) and converted to Markdown.
- **PDF**: Processed by **olmocr**, which uses vision-language models to understand layout, reading tables and headers correctly, then converting to Markdown.
- **ZIP**: Recursively unzips and processes each valid file inside.

### Step 3: Semantic Chunking (`split_text_semantic`)
The text is too long to be a single vector. It must be chopped into "chunks".
- **Logic**:
  1. Protects code blocks (so `function() { ... }` doesn't get split).
  2. Splits by paragraphs (`\n\n`).
  3. Merges paragraphs until `CHUNK_SIZE` (1500 chars) is reached.
  4. If a chunk gets too full, it breaks, keeping `CHUNK_OVERLAP` (200 chars) from the previous chunk.
  *Why Overlap?* To ensure context isn't lost at the cut point.

### Step 4: Dual Embedding
Each text chunk is turned into two types of numbers:
1. **Dense Vector**: The text is fed to the MiniLM model.
   - *Output*: `[0.1, -0.5, ...]` (384 floats). Represents *meaning*.
2. **Sparse Vector**: The text is fed to the BM25 model.
   - *Output*: `[(index: 42, value: 0.9), ...]` (Keywords). Represents *exact terms*.

### Step 5: Storage (Upsert)
The chunk is sent to Qdrant with:
- **ID**: Deterministic MD5 hash of the content (prevents duplicates).
- **Vectors**: Dense + Sparse.
- **Payload (Metadata)**: Original text, library name, file path, chunk index.

---

## 3. 🔍 Search Workflow

When a user (or Agent) searches for "how to fix timeout error", the system performs a **Hybrid Search**.

### Step 1: Query Embedding
The search query is embedded using the *exact same models* as ingestion:
- **Dense Query**: Captures "timeout", "latency", "slow request".
- **Sparse Query**: Captures exact tokens "timeout", "error".

### Step 2: Vector Search (Parallel)
Qdrant performs two searches simultaneously:
1. **Semantic Search**: Finds vectors close in the 384-dim space. (Finds concepts).
2. **Keyword Search**: Finds vectors with matching sparse indices. (Finds exact words).

### Step 3: Fusion and Ranking
The results are merged using **Reciprocal Rank Fusion (RRF)** or **Distribution-Based Score Fusion (DBSF)**.
- *Logic*: A document is ranked higher if it appears in *both* top lists.
- *Filters*: If the user selected a specific library, Qdrant applies a pre-filter so we only search relevant vectors.

---

## 4. 🤖 MCP Agent Interaction

The MCP Server adds an intelligent layer on top of the search for LLMs.

### Feature: Smart Context
Agents often ask follow-up questions like "how about in Vue?".
- **Sticky Session**: The server remembers the last searched library (e.g., "React").
- If the next query is generic ("best practices"), it automatically applies the "React" filter.

### Feature: Ambiguity Resolution
If an agent asks "Button component props", and you have docs for both "Mantine" and "Chakra UI":
1. The server scans available libraries.
2. It detects that "Button" exists in multiple places.
3. It performs a **Multi-Search**: It searches *both* libraries.
4. It returns fused results to the agent, explicitly noting "Found results in Mantine and Chakra".

### Feature: Full Document Reading
Search returns snippets. If the Agent needs more context:
1. Agent calls `get_document(file_path="...")`.
2. Server queries Qdrant for *all chunks* with that `file_path`.
3. It sorts them by `chunk_index`.
4. It stitches the text back together to reconstruct the original document.
