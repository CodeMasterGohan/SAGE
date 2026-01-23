# 🧠 Developer Internals

A deep dive into SAGE-Docs architecture for contributors and advanced users.

---

## 📁 Project Structure

```
SAGE/
├── 📄 docker-compose.yml      # Service orchestration
├── 📄 README.md               # Project overview
├── 📄 .gitignore              # Git exclusions
│
├── 📂 backend/                # FastAPI Dashboard + REST API
│   ├── 📄 Dockerfile          # Container build instructions
│   ├── 📄 requirements.txt    # Python dependencies
│   ├── 📄 server.py           # REST API endpoints (~660 lines)
│   ├── 📄 ingest.py           # Document processing pipeline (~600 lines)
│   └── 📂 static/             # Frontend assets
│       ├── 📄 index.html      # Main dashboard HTML
│       ├── 📄 app.js          # Frontend JavaScript logic
│       └── 📄 styles.css      # Custom CSS styles
│
├── 📂 mcp-server/             # Model Context Protocol Server
│   ├── 📄 Dockerfile          # Container build instructions
│   ├── 📄 requirements.txt    # Python dependencies
│   └── 📄 main.py             # MCP tools implementation (~490 lines)
│
├── 📂 uploads/                # Uploaded document storage
│   └── 📂 {library}/          # Organized by library name
│       └── 📂 {version}/      # Then by version
│
└── 📂 docs/                   # This documentation!
```

---

## 🔄 Data Flow Architecture

### Upload Pipeline

```
┌─────────┐   POST /api/upload    ┌──────────┐
│  User   │ ─────────────────────▶│  server  │
│ Browser │                       │   .py    │
└─────────┘                       └────┬─────┘
                                       │
                    ┌──────────────────┘
                    ▼
            ┌───────────────┐     File Type Detection
            │   ingest.py   │ ────────────────────────▶ detect_file_type()
            └───────┬───────┘
                    │
        ┌───────────┼───────────┬──────────────┐
        ▼           ▼           ▼              ▼
    ┌───────┐  ┌────────┐  ┌────────┐    ┌──────────┐
    │  MD   │  │  HTML  │  │  PDF   │    │   ZIP    │
    │       │  │  ─▶MD  │  │ olmocr │    │ Extract  │
    └───┬───┘  └───┬────┘  └───┬────┘    └────┬─────┘
        │          │           │              │
        └──────────┴─────┬─────┴──────────────┘
                         ▼
              ┌─────────────────────┐
              │  split_text_semantic │  Chunking with overlap
              └──────────┬──────────┘
                         ▼
              ┌─────────────────────┐
              │   FastEmbed Dense   │  sentence-transformers/all-MiniLM-L6-v2
              │   FastEmbed BM25    │  Qdrant/bm25
              └──────────┬──────────┘
                         ▼
              ┌─────────────────────┐
              │   Qdrant Upsert     │  Store vectors + metadata
              └─────────────────────┘
```

### Search Pipeline

```
┌─────────┐   POST /api/search    ┌──────────┐
│  User   │ ─────────────────────▶│  server  │
│ Browser │                       │   .py    │
└─────────┘                       └────┬─────┘
                                       │
                    ┌──────────────────┘
                    ▼
        ┌───────────────────────┐
        │  Generate Embeddings  │
        │  • Dense (semantic)   │
        │  • Sparse (BM25)      │
        └───────────┬───────────┘
                    ▼
        ┌───────────────────────┐
        │  Qdrant query_points  │
        │  • Prefetch dense     │
        │  • Prefetch sparse    │
        │  • Fusion (DBSF/RRF)  │
        └───────────┬───────────┘
                    ▼
        ┌───────────────────────┐
        │  Format & Return      │
        │  search results       │
        └───────────────────────┘
```

---

## 🔧 Core Components

### Backend Server (`server.py`)

The FastAPI server handles:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Health check and Qdrant connection |
| `/api/upload` | POST | Single file upload |
| `/api/upload-multiple` | POST | Batch file upload |
| `/api/upload/async` | POST | Background upload for large files |
| `/api/upload/status/{id}` | GET | Check async upload progress |
| `/api/search` | POST | Hybrid search with fusion |
| `/api/resolve` | POST | Find libraries by name |
| `/api/libraries` | GET | List all libraries |
| `/api/document` | GET | Retrieve full document |
| `/api/library/{name}` | DELETE | Delete library |
| `/` | GET | Serve dashboard HTML |

**Key Classes:**

```python
class SearchRequest(BaseModel):
    query: str
    library: Optional[str] = None
    version: Optional[str] = None
    limit: int = 5
    fusion: str = "dbsf"

class SearchResult(BaseModel):
    content: str
    library: str
    version: str
    title: str
    type: str
    file_path: str
    score: float
```

### Ingestion Pipeline (`ingest.py`)

The document processor handles:

| Function | Purpose |
|----------|---------|
| `detect_file_type()` | Determine format from extension/content |
| `convert_html_to_markdown()` | Clean HTML → Markdown conversion |
| `extract_pdf_text()` | olmocr PDF processing |
| `extract_docx_text()` | Word document extraction |
| `extract_excel_text()` | Excel spreadsheet parsing |
| `split_text_semantic()` | Smart chunking with overlap |
| `ingest_document()` | Main entry point |
| `ensure_collection()` | Create Qdrant collection if missing |

**Chunking Configuration:**

```python
CHUNK_SIZE = 1500      # Characters per chunk
CHUNK_OVERLAP = 200    # Overlap between chunks
```

### MCP Server (`main.py`)

Exposes four tools to LLMs:

| Tool | Description |
|------|-------------|
| `search_docs` | Hybrid search with optional reranking |
| `list_libraries` | O(1) library enumeration via facets |
| `resolve_library` | Fuzzy library name matching |
| `get_document` | Retrieve and reconstruct full document |

**Transport Options:**

```bash
# stdio (for Claude Desktop, Gemini CLI)
python main.py

# HTTP/SSE (for containerized deployment)
python main.py --transport http --port 8000
```

---

## 💾 Qdrant Schema

### Collection Configuration

```python
vectors_config={
    "dense": VectorParams(
        size=384,  # MiniLM-L6-v2
        distance=Distance.COSINE
    )
},
sparse_vectors_config={
    "sparse": SparseVectorParams(
        index=SparseIndexParams(on_disk=False)
    )
},
quantization_config=ScalarQuantization(
    scalar=ScalarQuantizationConfig(
        type=ScalarType.INT8,
        always_ram=True
    )
)
```

### Point Payload Structure

Each indexed chunk contains:

```python
{
    "content": str,       # The actual chunk text
    "library": str,       # Library name
    "version": str,       # Version string
    "title": str,         # Document title
    "file_path": str,     # Path to stored file
    "chunk_index": int,   # Position in document
    "total_chunks": int,  # Total chunks in document
    "type": str           # Always "document"
}
```

### Indexes

```python
# Payload indexes for efficient filtering
client.create_payload_index("library", PayloadSchemaType.KEYWORD)
client.create_payload_index("version", PayloadSchemaType.KEYWORD)
client.create_payload_index("file_path", PayloadSchemaType.KEYWORD)
```

---

## 🧪 Custom Scripts

Scripts available in `docker-compose.yml`:

| Command | Description |
|---------|-------------|
| `docker-compose up -d --build` | Build and start all services |
| `docker-compose logs -f backend` | Stream backend logs |
| `docker-compose logs -f mcp-server` | Stream MCP server logs |
| `docker-compose down` | Stop all services |
| `docker-compose down -v` | Stop and remove volumes (⚠️ deletes data) |

---

## 🔌 API Examples

### Search Documents

```bash
curl -X POST http://localhost:8080/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication best practices",
    "library": "react",
    "limit": 5,
    "fusion": "dbsf"
  }'
```

### Upload a Document

```bash
curl -X POST http://localhost:8080/api/upload \
  -F "file=@./docs/guide.md" \
  -F "library=my-library" \
  -F "version=1.0"
```

### List All Libraries

```bash
curl http://localhost:8080/api/libraries
```

### Delete a Library

```bash
curl -X DELETE http://localhost:8080/api/library/my-library
```

---

## 🧩 Extending SAGE-Docs

### Adding a New File Format

1. Add detection in `ingest.py`:

```python
def detect_file_type(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == '.custom':
        return 'custom'
    # ...existing logic
```

2. Add extraction function:

```python
def extract_custom_text(content: bytes) -> str:
    # Your conversion logic here
    return markdown_text
```

3. Wire it into `process_file()`:

```python
def process_file(content, filename, library, version):
    file_type = detect_file_type(filename, content)
    if file_type == 'custom':
        return extract_custom_text(content)
    # ...existing logic
```

### Using a Different Embedding Model

Update `docker-compose.yml`:

```yaml
backend:
  environment:
    - DENSE_MODEL_NAME=nomic-ai/nomic-embed-text-v1.5
    - DENSE_VECTOR_SIZE=768
    - USE_NOMIC_PREFIX=true
```

> ⚠️ **Warning:** Delete the Qdrant collection first, as dimensions won't match!

---

## 📊 Performance Considerations

| Component | Bottleneck | Optimization |
|-----------|------------|--------------|
| PDF Processing | olmocr layout analysis | Async upload endpoint |
| Embedding | Model inference | Lazy load, cache models |
| Search | Vector similarity | INT8 quantization |
| BM25 | Index size | In-memory sparse vectors |

### Memory Usage

| Service | Recommended RAM |
|---------|-----------------|
| Backend | 4-6 GB |
| MCP Server | 2-4 GB |
| Qdrant | 1-2 GB (scales with data) |

---

## 🔗 Related Resources

- **[🏠 Welcome](./00-Welcome.md)** — Project overview
- **[🚀 Quick Start](./01-Quick-Start.md)** — Get running fast
- **[📖 User Guide](./02-User-Guide.md)** — Feature walkthrough

---

> 💡 **Tip:** Found something that could be improved? Contributions are welcome! The codebase is designed to be approachable.
