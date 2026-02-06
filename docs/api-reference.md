# SAGE API Reference

Complete REST API documentation for all SAGE services.

## Table of Contents
- [Dashboard API](#dashboard-api-port-8080)
- [Refinery API](#refinery-api-internal)
- [MCP Server](#mcp-server-port-8000)
- [Common Response Formats](#common-response-formats)
- [Error Handling](#error-handling)

---

## Dashboard API (Port 8080)

The primary API for document upload, search, and management.

### Upload Endpoints

#### POST /api/upload

Upload a single document for immediate processing.

**Request:**
```http
POST /api/upload
Content-Type: multipart/form-data

file: <binary>
library: string (required)
version: string (default: "latest")
```

**Parameters:**
- `file` - Document file (max 50MB)
  - Supported formats: .md, .txt, .html, .pdf, .docx, .xlsx, .zip
- `library` - Library/collection name (e.g., "react", "python-docs")
- `version` - Version identifier (e.g., "18.2.0", "3.11")

**Response:** `200 OK`
```json
{
  "success": true,
  "library": "react",
  "version": "18.2.0",
  "files_processed": 1,
  "chunks_indexed": 47,
  "message": "Successfully indexed 47 chunks from 1 files",
  "was_duplicate": false,
  "linked_to": null,
  "truncation_warnings": [
    {
      "chunk_index": 12,
      "original_size": 5200,
      "truncated_size": 4000,
      "truncation_type": "character",
      "section_title": "Advanced Hooks API"
    }
  ]
}
```

**Error Response:** `400 Bad Request`
```json
{
  "detail": "File too large: 52.3MB exceeds 50MB limit"
}
```

**Error Response:** `422 Unprocessable Entity`
```json
{
  "detail": {
    "success": false,
    "error": "PDF processing failed: olmocr timed out after 600 seconds",
    "processing_step": "extraction",
    "file_name": "large_manual.pdf",
    "details": {
      "error_type": "PDFProcessingError"
    }
  }
}
```

**cURL Example:**
```bash
curl -X POST http://localhost:8080/api/upload \
  -F "file=@react-docs.md" \
  -F "library=react" \
  -F "version=18.2.0"
```

**Python Example:**
```python
import requests

with open("react-docs.md", "rb") as f:
    response = requests.post(
        "http://localhost:8080/api/upload",
        files={"file": f},
        data={"library": "react", "version": "18.2.0"}
    )
    
result = response.json()
print(f"Indexed {result['chunks_indexed']} chunks")

# Check for duplicates
if result['was_duplicate']:
    print(f"Duplicate detected, linked to {result['linked_to']}")

# Check for truncation warnings
if result['truncation_warnings']:
    print(f"Warning: {len(result['truncation_warnings'])} chunks truncated")
```

---

#### POST /api/upload/async

Upload a document for background processing. Recommended for large PDFs.

**Request:**
```http
POST /api/upload/async
Content-Type: multipart/form-data

file: <binary>
library: string (required)
version: string (default: "latest")
```

**Response:** `200 OK`
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Upload queued. PDF files may take a while to process. You can close this page."
}
```

**cURL Example:**
```bash
curl -X POST http://localhost:8080/api/upload/async \
  -F "file=@large_manual.pdf" \
  -F "library=product-docs" \
  -F "version=2.0"
```

**Usage Pattern:**
```python
import requests
import time

# 1. Start upload
response = requests.post(
    "http://localhost:8080/api/upload/async",
    files={"file": open("large_manual.pdf", "rb")},
    data={"library": "product-docs", "version": "2.0"}
)
task_id = response.json()["task_id"]

# 2. Poll for completion
while True:
    status_response = requests.get(
        f"http://localhost:8080/api/upload/status/{task_id}"
    )
    status = status_response.json()
    
    print(f"Status: {status['status']}")
    
    if status['status'] == 'completed':
        print(f"Success: {status['result']['chunks_indexed']} chunks indexed")
        break
    elif status['status'] == 'failed':
        print(f"Error: {status['error']}")
        break
    
    time.sleep(5)  # Poll every 5 seconds
```

---

#### GET /api/upload/status/{task_id}

Check the status of an async upload task.

**Parameters:**
- `task_id` - UUID returned from `/api/upload/async`

**Response (Pending):** `200 OK`
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "progress": "Queued for processing",
  "result": null,
  "error": null
}
```

**Response (Processing):** `200 OK`
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": "Converting document...",
  "result": null,
  "error": null
}
```

**Response (Completed):** `200 OK`
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": "Complete",
  "result": {
    "success": true,
    "library": "product-docs",
    "version": "2.0",
    "files_processed": 1,
    "chunks_indexed": 234,
    "message": "Successfully indexed 234 chunks",
    "was_duplicate": false,
    "linked_to": null,
    "truncation_warnings": []
  },
  "error": null
}
```

**Response (Failed):** `200 OK`
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "progress": null,
  "result": null,
  "error": "PDF processing failed: olmocr timed out"
}
```

**Error Response:** `404 Not Found`
```json
{
  "detail": "Task not found"
}
```

**cURL Example:**
```bash
curl http://localhost:8080/api/upload/status/550e8400-e29b-41d4-a716-446655440000
```

---

#### POST /api/upload-multiple

Upload multiple documents in one request.

**Request:**
```http
POST /api/upload-multiple
Content-Type: multipart/form-data

files: <binary>[] (multiple files)
library: string (required)
version: string (default: "latest")
```

**Response:** `200 OK`
```json
{
  "success": true,
  "library": "react",
  "version": "18.2.0",
  "files_processed": 15,
  "chunks_indexed": 523,
  "message": "Successfully indexed 523 chunks from 15 files",
  "was_duplicate": false,
  "linked_to": null,
  "truncation_warnings": [...]
}
```

**cURL Example:**
```bash
curl -X POST http://localhost:8080/api/upload-multiple \
  -F "files=@doc1.md" \
  -F "files=@doc2.md" \
  -F "files=@doc3.md" \
  -F "library=react" \
  -F "version=18.2.0"
```

---

### Search Endpoints

#### POST /api/search

Hybrid semantic + keyword search across documents.

**Request:**
```http
POST /api/search
Content-Type: application/json

{
  "query": "how to use useState hook",
  "library": "react",
  "version": "18.2.0",
  "limit": 5,
  "fusion": "dbsf"
}
```

**Parameters:**
- `query` (required) - Search query text
- `library` (optional) - Filter by library name
- `version` (optional) - Filter by version
- `limit` (optional) - Max results (default: 5)
- `fusion` (optional) - Fusion method: "dbsf" (default) or "rrf"

**Response:** `200 OK`
```json
[
  {
    "content": "# useState Hook\n\nThe useState hook is a fundamental React hook...",
    "library": "react",
    "version": "18.2.0",
    "title": "React Hooks Reference",
    "type": "document",
    "file_path": "/app/uploads/react/18.2.0/hooks.md",
    "score": 0.87
  },
  {
    "content": "## Using State in Functional Components\n\nTo use state...",
    "library": "react",
    "version": "18.2.0",
    "title": "Getting Started with Hooks",
    "type": "document",
    "file_path": "/app/uploads/react/18.2.0/tutorial.md",
    "score": 0.82
  }
]
```

**cURL Example:**
```bash
curl -X POST http://localhost:8080/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "how to use useState hook",
    "library": "react",
    "limit": 5
  }'
```

**Python Example:**
```python
import requests

response = requests.post(
    "http://localhost:8080/api/search",
    json={
        "query": "authentication middleware",
        "library": "express",
        "version": "4.18.0",
        "limit": 10
    }
)

results = response.json()
for result in results:
    print(f"[{result['score']:.2f}] {result['title']}")
    print(f"  {result['content'][:200]}...")
```

---

#### POST /api/resolve

Find libraries matching a search query (fuzzy matching).

**Request:**
```http
POST /api/resolve
Content-Type: application/json

{
  "query": "reac",
  "limit": 5
}
```

**Response:** `200 OK`
```json
[
  {
    "library": "react",
    "doc_count": 523,
    "relevance_score": 0.8,
    "versions": ["18.2.0", "18.1.0", "17.0.2"]
  },
  {
    "library": "react-native",
    "doc_count": 342,
    "relevance_score": 0.6,
    "versions": ["0.71.0", "0.70.0"]
  }
]
```

**cURL Example:**
```bash
curl -X POST http://localhost:8080/api/resolve \
  -H "Content-Type: application/json" \
  -d '{"query": "python", "limit": 5}'
```

---

### Library Management

#### GET /api/libraries

List all indexed libraries and their versions.

**Response:** `200 OK`
```json
[
  {
    "library": "express",
    "versions": ["4.18.2", "4.18.0", "4.17.1"]
  },
  {
    "library": "react",
    "versions": ["18.2.0", "18.1.0"]
  },
  {
    "library": "vue",
    "versions": ["3.3.0", "3.2.47"]
  }
]
```

**cURL Example:**
```bash
curl http://localhost:8080/api/libraries
```

**Python Example:**
```python
import requests

response = requests.get("http://localhost:8080/api/libraries")
libraries = response.json()

for lib in libraries:
    print(f"{lib['library']}: {', '.join(lib['versions'])}")
```

---

#### GET /api/document

Get the full content of a specific document.

**Parameters:**
- `file_path` (query param) - Document file path

**Request:**
```http
GET /api/document?file_path=/app/uploads/react/18.2.0/hooks.md
```

**Response:** `200 OK`
```json
{
  "title": "React Hooks Reference",
  "library": "react",
  "version": "18.2.0",
  "type": "document",
  "content": "# React Hooks Reference\n\n## useState\n\nThe useState hook...",
  "chunk_count": 47
}
```

**Error Response:** `404 Not Found`
```json
{
  "detail": "Document not found: /app/uploads/react/18.2.0/nonexistent.md"
}
```

**cURL Example:**
```bash
curl "http://localhost:8080/api/document?file_path=/app/uploads/react/18.2.0/hooks.md"
```

---

#### DELETE /api/library/{library}

Delete a library (or specific version) from the index.

**Parameters:**
- `library` (path param) - Library name
- `version` (query param, optional) - Specific version to delete

**Request:**
```http
DELETE /api/library/react?version=17.0.2
```

**Response:** `200 OK`
```json
{
  "success": true,
  "library": "react",
  "version": "17.0.2",
  "chunks_deleted": 456
}
```

**cURL Examples:**
```bash
# Delete specific version
curl -X DELETE "http://localhost:8080/api/library/react?version=17.0.2"

# Delete entire library (all versions)
curl -X DELETE http://localhost:8080/api/library/react
```

---

### Health & Status

#### GET /health

Kubernetes-style health check (liveness probe).

**Response:** `200 OK`
```json
{
  "status": "ok",
  "qdrant": "healthy",
  "uptime_seconds": 3456.78
}
```

**Response (Degraded):** `200 OK`
```json
{
  "status": "degraded",
  "qdrant": "unhealthy",
  "uptime_seconds": 123.45
}
```

---

#### GET /ready

Readiness probe for Kubernetes.

**Response (Ready):** `200 OK`
```json
{
  "ready": true
}
```

**Response (Not Ready):** `503 Service Unavailable`
```json
{
  "detail": "Not ready: Collection not found"
}
```

---

#### GET /api/status

Connection status to Qdrant.

**Response:** `200 OK`
```json
{
  "connected": true,
  "host": "localhost",
  "port": 6333,
  "collection": "sage_docs",
  "document_count": 12345
}
```

---

## Refinery API (Internal)

Legacy document processing service. Mostly superseded by Dashboard API.

### POST /ingest

**Request:**
```http
POST /ingest
Content-Type: multipart/form-data

file: <binary>
library: string
version: string
```

**Response:** Same as Dashboard `/api/upload`

---

### GET /health

**Response:**
```json
{
  "status": "ok",
  "uptime_seconds": 1234.56
}
```

---

## MCP Server (Port 8000)

Model Context Protocol server exposing tools to LLMs.

### MCP Tools

#### search_docs

Agent-optimized documentation search with context awareness.

**Input Schema:**
```json
{
  "query": "how to use useState",
  "library": "react",
  "version": "18.2.0",
  "limit": 5,
  "rerank": false,
  "fusion": "dbsf"
}
```

**Output:**
```json
{
  "results": [
    {
      "content": "...",
      "library": "react",
      "version": "18.2.0",
      "title": "Hooks API",
      "type": "document",
      "file_path": "...",
      "score": 0.87
    }
  ],
  "meta": {
    "query": "how to use useState",
    "original_library_arg": "react",
    "resolution_method": "explicit_arg",
    "ambiguity_detected": [],
    "active_context": ["react"],
    "latency_ms": 145
  }
}
```

**Special Features:**
- **Context Awareness:** Remembers previous library from conversation
- **Ambiguity Detection:** Detects multiple libraries (e.g., "React vs Vue")
- **Global Search:** Use `library="*"` or `library="GLOBAL"` to force global search
- **Fallback:** If targeted search fails, automatically tries global search

---

#### list_libraries

List all available libraries and versions.

**Output:**
```json
[
  {
    "library": "react",
    "versions": ["18.2.0", "18.1.0"]
  },
  {
    "library": "vue",
    "versions": ["3.3.0"]
  }
]
```

---

#### resolve_library

Find libraries matching a query (fuzzy matching).

**Input Schema:**
```json
{
  "query": "reac",
  "limit": 5
}
```

**Output:**
```json
[
  {
    "library": "react",
    "doc_count": 523,
    "relevance_score": 0.8,
    "versions": ["18.2.0", "18.1.0"]
  }
]
```

---

#### get_document

Retrieve full document content.

**Input Schema:**
```json
{
  "file_path": "/app/uploads/react/18.2.0/hooks.md"
}
```

**Output:**
```json
{
  "title": "React Hooks Reference",
  "library": "react",
  "version": "18.2.0",
  "type": "document",
  "content": "# React Hooks Reference\n\n...",
  "chunk_count": 47
}
```

---

## Common Response Formats

### UploadResult
```typescript
interface UploadResult {
  success: boolean;
  library: string;
  version: string;
  files_processed: number;
  chunks_indexed: number;
  message: string;
  was_duplicate: boolean;              // Phase 2: Deduplication
  linked_to: string | null;            // File path of original
  truncation_warnings: TruncationWarning[];  // Phase 3
}
```

### TruncationWarning
```typescript
interface TruncationWarning {
  chunk_index: number;
  original_size: number;               // In chars or tokens
  truncated_size: number;
  truncation_type: "character" | "token";
  section_title: string | null;        // Extracted from markdown header
}
```

### SearchResult
```typescript
interface SearchResult {
  content: string;
  library: string;
  version: string;
  title: string;
  type: string;
  file_path: string;
  score: number;                       // 0.0 - 1.0
}
```

### IngestionError (Phase 5)
```typescript
interface IngestionError {
  success: false;
  error: string;                        // Human-readable message
  processing_step: "extraction" | "chunking" | "embedding" | "indexing" | "unknown";
  file_name: string;
  details: {
    error_type: string;                 // Exception class name
    retries?: number;
    suggestion?: string;
    [key: string]: any;
  };
}
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | When |
|------|---------|------|
| 200 | Success | Request completed successfully |
| 400 | Bad Request | Validation failed (file size, type, etc.) |
| 404 | Not Found | Resource not found (document, task, etc.) |
| 422 | Unprocessable Entity | Processing failed (PDF timeout, embedding error) |
| 500 | Internal Server Error | Unexpected error |
| 503 | Service Unavailable | Service not ready (health check failed) |

### Error Response Format

**Validation Error:**
```json
{
  "detail": "File too large: 52.3MB exceeds 50MB limit"
}
```

**Processing Error:**
```json
{
  "detail": {
    "success": false,
    "error": "Embedding generation failed: Connection timeout",
    "processing_step": "embedding",
    "file_name": "large_doc.md",
    "details": {
      "error_type": "HTTPError",
      "retries": 3,
      "suggestion": "Check vLLM service status or reduce batch size"
    }
  }
}
```

### Error Codes by Processing Step

| Step | Common Errors | HTTP Code |
|------|---------------|-----------|
| **Validation** | File too large, Invalid extension, ZIP bomb | 400 |
| **Extraction** | PDF timeout, olmocr failure, Corrupt file | 422 |
| **Chunking** | Out of memory | 422 |
| **Embedding** | API timeout, Rate limit, Auth failure | 422 |
| **Indexing** | Qdrant connection error | 500 |

### Retry Recommendations

**Transient Errors (Retry):**
- Network timeouts
- Rate limits (429)
- Service unavailable (503)
- Connection errors

**Permanent Errors (Don't Retry):**
- Invalid API key (401)
- Bad request (400)
- File too large (400)
- Unsupported format (400)

---

## Rate Limiting

Currently **not implemented**. Recommended for production:
- Per-IP rate limiting (e.g., 100 req/minute)
- Per-API-key rate limiting
- Upload size quota per user/day

---

## Authentication

Currently **not implemented**. Recommended for production:
- API key header: `Authorization: Bearer <key>`
- JWT tokens for session-based auth
- OAuth2 for enterprise integration

---

## Pagination

Currently **not implemented** for search results. All results returned in single response.

Recommended enhancement:
```json
{
  "results": [...],
  "pagination": {
    "total": 234,
    "page": 1,
    "page_size": 10,
    "next_cursor": "..."
  }
}
```

---

## Versioning

API version: **1.1.0**

No API versioning scheme currently implemented. Consider adding:
- URL versioning: `/api/v1/search`
- Header versioning: `Accept: application/vnd.sage.v1+json`
