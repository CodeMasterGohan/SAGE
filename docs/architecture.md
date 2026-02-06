# SAGE Architecture

## System Overview

SAGE (Semantic Archive & Grouped Embeddings) is a modular documentation search system that provides hybrid search capabilities across multiple document libraries. The system consists of four main services working together to provide document ingestion, vector storage, and intelligent search capabilities.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         SAGE System                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │   Dashboard  │     │   Refinery   │     │  MCP Server  │    │
│  │   (Port 8080)│     │  (Internal)  │     │  (Port 8000) │    │
│  │              │     │              │     │              │    │
│  │  - Web UI    │     │  - Doc Proc. │     │  - LLM Tools │    │
│  │  - Upload API│     │  - Legacy    │     │  - Search    │    │
│  │  - Job Mgmt  │     │              │     │  - Context   │    │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘    │
│         │                    │                    │             │
│         │                    │                    │             │
│         │    ┌───────────────┴────────────────────┘             │
│         │    │                                                   │
│         ▼    ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐        │
│  │              Qdrant Vector Database                 │        │
│  │                  (Port 6333)                         │        │
│  │                                                      │        │
│  │  Collections:                                        │        │
│  │  ├─ sage_docs (documents & embeddings)              │        │
│  │  └─ sage_jobs (async job state)                     │        │
│  └─────────────────────────────────────────────────────┘        │
│                                                                  │
│  ┌─────────────────────────────────────────────────────┐        │
│  │              sage_core (Shared Library)             │        │
│  │                                                      │        │
│  │  ├─ ingestion.py    (unified pipeline)              │        │
│  │  ├─ file_processing.py (extraction)                 │        │
│  │  ├─ chunking.py     (text splitting)                │        │
│  │  ├─ embeddings.py   (vector generation)             │        │
│  │  ├─ validation.py   (security checks)               │        │
│  │  └─ qdrant_utils.py (database operations)           │        │
│  └─────────────────────────────────────────────────────┘        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### 1. Dashboard Service (Port 8080)

**Purpose:** Web UI and primary upload API endpoint.

**Key Features:**
- Static file serving for web interface
- Document upload with validation
- Async upload processing with job tracking
- Hybrid search API
- Library management
- Health checks

**Technology Stack:**
- FastAPI for REST API
- ProcessPoolExecutor for background jobs
- Qdrant client for vector operations
- FastEmbed for local embeddings

**API Endpoints:**
- `POST /api/upload` - Synchronous upload
- `POST /api/upload/async` - Background upload (returns job_id)
- `GET /api/upload/status/{job_id}` - Check async job status
- `POST /api/upload-multiple` - Batch upload
- `POST /api/search` - Hybrid search
- `GET /api/libraries` - List all libraries
- `POST /api/resolve` - Find libraries matching query
- `GET /api/document` - Get full document content
- `DELETE /api/library/{library}` - Delete library
- `GET /health` - Health check
- `GET /ready` - Readiness probe

### 2. Refinery Service

**Purpose:** Legacy document processing microservice (now thin wrapper around sage_core).

**Key Features:**
- Document ingestion API
- Direct sage_core integration

**Technology Stack:**
- FastAPI
- sage_core library

**API Endpoints:**
- `POST /ingest` - Process document
- `GET /health` - Health check

**Note:** Most functionality has been consolidated into sage_core. Refinery is maintained for backward compatibility.

### 3. MCP Server (Port 8000)

**Purpose:** Model Context Protocol integration for LLM tools.

**Key Features:**
- Agent-optimized search with context awareness
- Ambiguity detection (e.g., "React vs Vue")
- Session-based library context
- Smart fallback strategies
- ColBERT reranking (optional)

**Technology Stack:**
- FastMCP framework
- Qdrant for search
- FastEmbed for embeddings
- Custom middleware for context management

**MCP Tools:**
- `search_docs` - Context-aware documentation search
- `list_libraries` - List available libraries
- `resolve_library` - Library name resolution
- `get_document` - Retrieve full document

### 4. Qdrant Vector Database (Port 6333)

**Purpose:** Persistent vector storage and hybrid search.

**Collections:**

#### sage_docs (Main Collection)
```python
{
    "vectors": {
        "dense": {
            "size": 384,  # configurable via DENSE_VECTOR_SIZE
            "distance": "COSINE"
        },
        "sparse": {
            "index": "BM25"  # keyword search
        }
    },
    "payload_schema": {
        "content": "string",          # chunk text
        "library": "keyword",         # library name
        "version": "keyword",         # version identifier
        "title": "string",            # document title
        "file_path": "string",        # original file path
        "chunk_index": "integer",     # position in document
        "total_chunks": "integer",    # total chunks in document
        "type": "keyword",            # document type
        "content_hash": "string",     # SHA256 for deduplication
        "linked_files": "array",      # duplicate file references
        "truncation_info": "object"   # truncation warnings (if any)
    }
}
```

#### sage_jobs (Job State Collection)
```python
{
    "payload_schema": {
        "task_id": "string",
        "status": "keyword",       # pending/processing/completed/failed
        "progress": "string",
        "filename": "string",
        "library": "keyword",
        "version": "keyword",
        "created_at": "string",
        "result": "object",
        "error": "string"
    }
}
```

### 5. sage_core (Shared Library)

**Purpose:** Unified document processing pipeline used by all services.

**Modules:**

#### ingestion.py
- **Main Functions:**
  - `ingest_document()` - Unified ingestion pipeline
  - `ingest_document_with_partial_failure()` - ZIP partial failure handling
  - `_ingest_markdown()` - Internal markdown processing

- **Features:**
  - Content deduplication via SHA256 hashing
  - Transaction semantics with rollback
  - Async/await support
  - Structured error handling via `IngestionError`
  - Truncation warning tracking

#### file_processing.py
- **Functions:**
  - `detect_file_type()` - MIME type detection
  - `process_file_async()` - Single file processing
  - `process_zip_async()` - ZIP archive extraction
  - `extract_pdf_text_async()` - PDF to markdown (olmocr)
  - `convert_html_to_markdown()` - HTML cleaning
  - `extract_docx_text()` - DOCX extraction
  - `extract_excel_text()` - Excel to text

- **Supported Formats:**
  - Markdown (.md, .markdown)
  - HTML (.html, .htm)
  - Plain text (.txt, .rst, .adoc)
  - PDF (.pdf) - via olmocr
  - Word (.docx) - via python-docx
  - Excel (.xlsx, .xls) - via openpyxl
  - ZIP archives (.zip)

#### chunking.py
- **Functions:**
  - `split_text_semantic()` - Semantic text chunking
  - `process_markdown_chunks()` - Chunking with truncation warnings
  - `yield_safe_batches()` - Token-aware batch generation
  - `count_tokens()` - Token counting
  - `truncate_to_tokens()` - Safe truncation

- **Configuration:**
  - `CHUNK_SIZE` - Target chunk size (default: 800 chars)
  - `CHUNK_OVERLAP` - Overlap between chunks (default: 80 chars)
  - `MAX_CHUNK_CHARS` - Hard limit (default: 4000 chars)
  - `MAX_CHUNK_TOKENS` - Token limit per chunk (default: 500)
  - `MAX_BATCH_TOKENS` - Token limit per batch (default: 2000)

#### embeddings.py
- **Functions:**
  - `get_dense_model()` - Load local embedding model
  - `get_sparse_model()` - Load BM25 model
  - `get_remote_embeddings_async()` - Remote API embeddings
  - `get_remote_embeddings_async_with_retry()` - Retry logic
  - `is_transient_error()` - Error classification

- **Modes:**
  - **Local:** FastEmbed models (no external dependencies)
  - **Remote:** vLLM/OpenAI API integration

#### validation.py
- **Functions:**
  - `validate_upload()` - Security validation
  - `validate_zip_archive()` - ZIP bomb detection
  - `sanitize_filename()` - Path traversal prevention

- **Checks:**
  - File size limits
  - Extension whitelist
  - ZIP entry counts
  - Compression ratio (zip bomb)
  - Path traversal attacks

#### qdrant_utils.py
- **Functions:**
  - `get_qdrant_client()` - Client singleton
  - `ensure_collection()` - Collection initialization
  - `compute_content_hash()` - SHA256 hashing
  - `check_duplicate_content()` - Deduplication check
  - `delete_library()` - Bulk deletion
  - `delete_points_by_ids()` - Rollback support

## Data Flow

### Upload → Processing → Indexing → Search

**1. Document Upload**
```
User uploads file
    ↓
Dashboard receives upload
    ↓
Validation (size, type, security)
    ↓
Save to /uploads/{library}/{version}/
    ↓
Queue for processing
```

**2. Document Processing Pipeline**
```
Extract content by type:
├─ PDF → olmocr → Markdown
├─ DOCX → python-docx → Markdown
├─ HTML → BeautifulSoup + markdownify → Markdown
├─ Excel → openpyxl → Markdown tables
├─ ZIP → Extract each file → Process individually
└─ Markdown/Text → Pass through

    ↓
Compute SHA256 content hash
    ↓
Check for duplicates in Qdrant
    ↓
If duplicate:
│   ├─ Skip embedding generation
│   ├─ Link to existing chunks
│   └─ Return early
Else:
│   ├─ Continue processing
    ↓
Split into semantic chunks (800 chars, 80 overlap)
    ↓
Track truncation warnings (>4000 chars or >500 tokens)
    ↓
Generate batches (max 2000 tokens per batch)
    ↓
Generate embeddings:
│   ├─ Dense vectors (384D, COSINE)
│   └─ Sparse vectors (BM25)
    ↓
Create Qdrant points with metadata
    ↓
Upsert to sage_docs collection (atomic)
    ↓
On error: Rollback all created points
```

**3. Deduplication Flow (Phase 2)**
```
New document arrives
    ↓
Extract and normalize content
    ↓
Compute SHA256 hash
    ↓
Query Qdrant for existing chunks with same hash
    ↓
Match found?
├─ YES:
│   ├─ Save file to disk (for reference)
│   ├─ Update linked_files in existing chunks
│   ├─ Return "was_duplicate: true"
│   └─ Skip embedding generation (cost savings!)
└─ NO:
    ├─ Proceed with full processing
    └─ Store content_hash in chunk metadata
```

**4. Async PDF Processing (Phase 4)**
```
Large PDF upload
    ↓
Create job entry in sage_jobs collection
    ↓
Submit to ProcessPoolExecutor
    ↓
Worker process:
│   ├─ Update job status: "processing"
│   ├─ Run olmocr (subprocess, timeout 600s)
│   ├─ Process markdown chunks
│   ├─ Generate embeddings
│   ├─ Index in Qdrant
│   └─ Update job status: "completed" or "failed"
    ↓
User polls /api/upload/status/{job_id}
    ↓
Job state persists across restarts (Qdrant storage)
```

**5. Search Flow**
```
User query → Dashboard/MCP
    ↓
Generate query embeddings:
│   ├─ Dense vector (semantic)
│   └─ Sparse vector (keyword)
    ↓
Hybrid search in Qdrant:
│   ├─ Prefetch: Dense top-N
│   ├─ Prefetch: Sparse top-N
│   └─ Fusion: DBSF or RRF
    ↓
Optional: ColBERT reranking
    ↓
Filter by library/version (if specified)
    ↓
Return ranked results with scores
```

**6. Error Handling & Rollback (Phase 5)**
```
Error occurs during processing
    ↓
IngestionError raised with context:
│   ├─ processing_step (extraction/chunking/embedding/indexing)
│   ├─ file_name
│   ├─ error_message
│   └─ details (error_type, suggestions)
    ↓
Transaction rollback:
│   └─ Delete any partial points via point IDs
    ↓
Return structured error to client:
│   {
│     "success": false,
│     "error": "...",
│     "processing_step": "embedding",
│     "file_name": "example.pdf",
│     "details": {"error_type": "HTTPError", "retries": 3}
│   }
```

## Embedding Strategy

### Local Mode (Default)
- **Model:** sentence-transformers/all-MiniLM-L6-v2
- **Dimensions:** 384
- **Pros:** Self-contained, no API costs, consistent performance
- **Cons:** Slower, less accurate than large models
- **Memory:** ~120MB model + ~1GB working memory

### Remote Mode (vLLM/OpenAI)
- **Model:** Configurable (e.g., nomic-ai/nomic-embed-text-v1.5)
- **Dimensions:** Model-dependent (768 for Nomic)
- **Pros:** Faster with GPU, more accurate, offloads compute
- **Cons:** API costs, network dependency, rate limits
- **Configuration:**
  - `EMBEDDING_MODE=remote`
  - `VLLM_EMBEDDING_URL=http://gpu-server:8000`
  - `VLLM_MODEL_NAME=nomic-ai/nomic-embed-text-v1.5`
  - `VLLM_API_KEY=your_key`

### Hybrid Search
- **Dense Vector:** Semantic similarity (COSINE)
- **Sparse Vector:** BM25 keyword matching
- **Fusion Methods:**
  - **DBSF** (Distribution-Based Score Fusion) - Default, better for diverse corpora
  - **RRF** (Reciprocal Rank Fusion) - Alternative, rank-based

## Scaling Considerations

### Horizontal Scaling

**Dashboard:**
- Stateless (except ProcessPoolExecutor)
- Can run multiple instances behind load balancer
- Job state persists in Qdrant (shared across instances)
- Consider sticky sessions for WebSocket connections (if added)

**Refinery:**
- Fully stateless
- Can scale independently
- Not currently used in production (legacy)

**MCP Server:**
- Stateless (context in middleware layer)
- Can scale with load balancer
- Session state would need Redis/sticky sessions

**Qdrant:**
- Supports clustering (Qdrant Cloud or self-hosted)
- Sharding by collection
- Replication for HA

### Performance Tuning

**Embedding Concurrency:**
- Local: `INGESTION_CONCURRENCY=10` (CPU-bound)
- Remote: `INGESTION_CONCURRENCY=100` (network-bound)

**Batch Sizes:**
- `MAX_BATCH_TOKENS=2000` - Embedding batch size
- Larger batches = fewer API calls, but risk timeouts

**Worker Processes:**
- `WORKER_PROCESSES=2` - Background upload workers
- Set to CPU count for CPU-bound workloads

**Qdrant Optimization:**
- INT8 quantization enabled by default (memory savings)
- `always_ram=True` for quantized vectors (speed)
- Sparse index on-disk=False (speed over space)

## Security

### Upload Validation
- File size limits (50MB default)
- Extension whitelist
- MIME type checking
- ZIP bomb detection (compression ratio > 100x)
- Path traversal prevention

### API Security
- No authentication currently implemented
- Recommended: Add API key middleware for production
- Network isolation via Docker network
- Qdrant access limited to internal network

### Data Privacy
- All data stored in Qdrant (vector DB)
- No external API calls in local mode
- Remote mode: Data sent to embedding API
- Consider self-hosted vLLM for sensitive data

## Monitoring & Observability

### Health Checks
- `/health` - Liveness probe (service up, Qdrant connected)
- `/ready` - Readiness probe (can serve requests)

### Metrics to Track
- Upload rate (files/minute)
- Processing time (seconds/file)
- Search latency (milliseconds)
- Embedding costs (API calls, tokens)
- Error rates by processing step
- Queue depth (pending jobs)
- Qdrant collection size (points, memory)

### Logging
- Structured logging with log levels
- Processing step annotations
- Error context preservation
- Performance timing

## Deployment Patterns

### Development
```bash
docker-compose up -d
# All services local, no GPU required
```

### Production (Single Host)
```yaml
services:
  dashboard:
    deploy:
      resources:
        limits:
          memory: 6g
        reservations:
          memory: 2g
  qdrant:
    volumes:
      - /mnt/data/qdrant:/qdrant/storage
```

### Production (Distributed)
```
┌────────────────┐
│  Load Balancer │
└────────┬───────┘
         │
    ┌────┴────┬──────────┐
    │         │          │
┌───▼───┐ ┌───▼───┐ ┌───▼───┐
│Dashboard│Dashboard│Dashboard│
│  Pod 1 │  Pod 2 │  Pod 3 │
└───┬───┘ └───┬───┘ └───┬───┘
    │         │          │
    └────┬────┴────┬─────┘
         │         │
    ┌────▼─────────▼────┐
    │ Qdrant Cluster    │
    │ (3 nodes, HA)     │
    └───────────────────┘
```

## Technology Stack Summary

| Component | Technology | Version |
|-----------|-----------|---------|
| API Framework | FastAPI | Latest |
| Vector DB | Qdrant | Latest |
| Embeddings (Local) | FastEmbed | Latest |
| Embeddings (Remote) | vLLM/OpenAI API | - |
| PDF Processing | olmocr | Latest |
| DOCX Processing | python-docx | Latest |
| Excel Processing | openpyxl | Latest |
| HTML Conversion | BeautifulSoup + markdownify | Latest |
| Async Runtime | ProcessPoolExecutor | Python stdlib |
| MCP Framework | FastMCP | Latest |
| HTTP Client | httpx | Latest |
| Container Runtime | Docker Compose | Latest |

## Recent Architectural Changes

### Phase 1: Vault Removal
- Removed `vault-docs/` local file storage
- Single source of truth: Qdrant
- Simplified deployment

### Phase 2: Deduplication
- SHA256 content hashing
- Duplicate detection before embedding
- Metadata linking (`linked_files` array)
- Cost optimization

### Phase 3: Truncation Warnings
- Character truncation tracking (>4000 chars)
- Token truncation tracking (>500 tokens)
- User feedback in upload response
- Section title extraction

### Phase 4: Async PDF Processing
- ProcessPoolExecutor for background jobs
- Job state in Qdrant (`sage_jobs` collection)
- 10-minute timeout per PDF
- Durable job tracking (survives restarts)

### Phase 5: Enhanced Error Handling
- Structured `IngestionError` exception
- Transaction rollback on failure
- Retry logic for transient errors
- Detailed error context in API responses

### Ongoing: Service Consolidation
- Unified `sage_core` library
- Refinery → thin wrapper
- Dashboard → primary service
- Consistent behavior across all entry points
