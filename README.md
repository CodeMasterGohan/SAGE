# SAGE - Smart Accessible Gateway for Enterprise Documentation

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **Web-based document management with hybrid search and MCP integration**

SAGE is a powerful documentation search system that lets you upload documents through a web interface instead of scraping DevDocs. Upload PDFs, Markdown files, or ZIP archives, and search them using state-of-the-art hybrid search (semantic + keyword) powered by Qdrant vector database.

**Key Differentiator:** Upload your own documents via web interface instead of relying on pre-scraped DevDocs content.

---

## ✨ Features

- **📤 Web-Based Document Upload** - Drag & drop PDF, Markdown, HTML, or ZIP archives through an intuitive dashboard
- **🔍 Hybrid Search** - Dense semantic embeddings + sparse BM25 keyword search with fusion ranking
- **🧠 Intelligent Deduplication** - Automatically detects duplicate content to save embedding costs
- **⚠️ Truncation Warnings** - Real-time alerts when large documents are truncated (helps you maintain quality)
- **⏱️ Async PDF Processing** - Non-blocking PDF OCR with 10-minute timeout (handles large documents gracefully)
- **🤖 MCP Protocol Integration** - Expose documentation search to Claude Desktop and other LLM clients
- **🔄 Enhanced Error Handling** - Automatic retry logic with exponential backoff for transient failures
- **📚 Multi-Library Organization** - Organize documents by library name and version
- **🎨 Modern Dashboard** - Clean, intuitive dark theme web interface

---

## 🏗️ Architecture

SAGE consists of **4 containerized services**:

```
┌─────────────────────────────────────────────────────────────┐
│                        SAGE Stack                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Dashboard   │    │   Refinery   │    │  MCP Server  │  │
│  │  (Port 8080) │    │ (Internal)   │    │ (Port 8000)  │  │
│  │              │    │              │    │              │  │
│  │ • Web UI     │    │ • Document   │    │ • Search     │  │
│  │ • REST API   │    │   Processing │    │   API for    │  │
│  │ • Upload     │    │ • Validation │    │   LLMs       │  │
│  └───────┬──────┘    └──────────────┘    └───────┬──────┘  │
│          │                                        │         │
│          └────────────────┬───────────────────────┘         │
│                           ↓                                 │
│                  ┌──────────────┐                           │
│                  │    Qdrant    │                           │
│                  │ (Port 6334)  │                           │
│                  │              │                           │
│                  │ • Vector DB  │                           │
│                  │ • Dense +    │                           │
│                  │   Sparse     │                           │
│                  └──────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

### Service Details

| Service | Port | Description |
|---------|------|-------------|
| **Dashboard** | 8080 | Web UI and REST API for document upload and search |
| **Refinery** | Internal | Legacy document processing service (uses sage_core) |
| **MCP Server** | 8000 | Model Context Protocol server for LLM integration |
| **Qdrant** | 6334 | Vector database with hybrid search support |

### Data Flow

1. **Upload**: User uploads document via web dashboard (port 8080)
2. **Processing**: Dashboard uses `sage_core` to extract text and chunk content
3. **Embedding**: Generate dense (semantic) and sparse (BM25) vectors
4. **Indexing**: Store chunks with embeddings in Qdrant
5. **Search**: Query via dashboard or MCP server with hybrid search

---

## 📋 Prerequisites

- **Docker** and **Docker Compose** (v2.0+)
- **4GB RAM** minimum, **8GB recommended**
- **10GB disk space** for Qdrant vectors and uploaded documents
- **Internet connection** (for remote embeddings) or local CPU for local embeddings

---

## 🚀 Quick Start (5 Minutes)

Get SAGE running in 5 simple steps:

### 1. Clone Repository

```bash
git clone https://github.com/CodeMasterGohan/SAGE.git
cd SAGE
```

### 2. Configure Environment (Optional)

For local-only setup (CPU embeddings), no configuration needed!

For remote GPU embeddings or custom settings:

```bash
cp .env.example .env
# Edit .env with your settings (see Configuration section)
nano .env
```

### 3. Start Services

```bash
docker-compose up -d
```

This will:
- Download Docker images
- Start all 4 services
- Initialize Qdrant database
- Load embedding models (may take 2-3 minutes on first run)

### 4. Verify Services

Check that all services are healthy:

```bash
docker-compose ps
```

You should see 4 services running:
- `sage-docs-dashboard`
- `sage-docs-refinery`
- `sage-docs-mcp`
- `sage-docs-qdrant`

### 5. Access Dashboard

Open your browser to: **http://localhost:8080**

**First Upload:**
1. Click "Browse" or drag & drop a PDF/Markdown file
2. Enter a library name (e.g., "my-docs")
3. Optionally specify a version (defaults to "latest")
4. Click "Upload"
5. Search your content!

---

## 🔧 Configuration

SAGE is configured via environment variables. The default configuration works out of the box with local CPU embeddings.

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_MODE` | `local` | **CRITICAL**: `local` (CPU) or `remote` (GPU server) |
| `DENSE_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | Dense embedding model for semantic search |
| `DENSE_VECTOR_SIZE` | `384` | Vector dimensions for dense embeddings |
| `USE_NOMIC_PREFIX` | `false` | Add "search_document:" prefix for Nomic models |

### Remote Embeddings (GPU Server)

For production deployments with GPU servers:

| Variable | Default | Description |
|----------|---------|-------------|
| `VLLM_EMBEDDING_URL` | `http://localhost:8000` | vLLM/OpenAI-compatible embedding endpoint |
| `VLLM_MODEL_NAME` | `nomic-ai/nomic-embed-text-v1.5` | Model name for remote embeddings |
| `VLLM_API_KEY` | *(empty)* | Optional API key for authentication |

**To use remote embeddings:**
1. Set `EMBEDDING_MODE=remote` in [docker-compose.yml](docker-compose.yml)
2. Configure `VLLM_EMBEDDING_URL` in `.env`
3. Restart services: `docker-compose restart`

### PDF Processing (OCR)

| Variable | Default | Description |
|----------|---------|-------------|
| `PDF_TIMEOUT` | `600` | PDF processing timeout in seconds (10 minutes) |
| `OLMOCR_SERVER` | *(empty)* | Remote olmocr server URL (e.g., `http://gpu-server:8000/v1`) |
| `OLMOCR_API_KEY` | *(empty)* | Optional API key for olmocr server |
| `OLMOCR_MODEL` | `allenai/olmOCR-2-7B-1025-FP8` | OCR model for PDF text extraction |

### Chunking & Batching

| Variable | Default | Description |
|----------|---------|-------------|
| `CHUNK_SIZE` | `800` | Target chunk size in tokens |
| `CHUNK_OVERLAP` | `80` | Overlap between chunks in tokens |
| `MAX_CHUNK_CHARS` | `4000` | Hard limit on chunk size in characters |
| `MAX_CHUNK_TOKENS` | `500` | Hard limit on tokens per chunk (triggers warning) |
| `MAX_BATCH_TOKENS` | `2000` | Maximum tokens per embedding batch |
| `INGESTION_CONCURRENCY` | `100` (remote) / `10` (local) | Concurrent embedding requests |

### Upload Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_FILE_SIZE` | `52428800` | Maximum single file size (50MB) |
| `MAX_ZIP_ENTRIES` | `500` | Maximum files in a ZIP archive |
| `MAX_ZIP_TOTAL_SIZE` | `209715200` | Maximum ZIP uncompressed size (200MB) |
| `WORKER_PROCESSES` | `2` | Number of background worker processes |

### Qdrant Connection

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_HOST` | `qdrant` | Qdrant hostname (use `localhost` for external Qdrant) |
| `QDRANT_PORT` | `6333` | Qdrant API port |
| `COLLECTION_NAME` | `sage_docs` | Primary collection name for document chunks |
| `JOBS_COLLECTION` | `sage_jobs` | Collection for async job tracking |

### Example `.env` File

```bash
# Remote GPU embeddings
VLLM_EMBEDDING_URL=http://192.168.1.100:8000
VLLM_MODEL_NAME=nomic-ai/nomic-embed-text-v1.5
VLLM_API_KEY=my-secret-key

# Remote PDF processing
OLMOCR_SERVER=http://192.168.1.100:8000/v1
OLMOCR_MODEL=allenai/olmOCR-2-7B-1025-FP8

# Performance tuning
PDF_TIMEOUT=1200
CHUNK_SIZE=1000
INGESTION_CONCURRENCY=200
```

Then update `EMBEDDING_MODE=remote` in [docker-compose.yml](docker-compose.yml) and restart:

```bash
docker-compose down
docker-compose up -d
```

For complete configuration details, see [Configuration Reference](docs/CONFIGURATION.md).

---

## 📚 Usage & API Documentation

### Quick Links

- **[📖 User Guide](docs/02-User-Guide.md)** - Uploading, searching, managing documents
- **[🔌 API Reference](docs/API-REFERENCE.md)** - Complete REST API documentation
- **[🤖 MCP Integration](docs/04-MCP-Configuration.md)** - Claude Desktop & LLM setup
- **[🐛 Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

### Common Tasks

**Upload a document:**
```bash
curl -X POST http://localhost:8080/api/upload \
  -F "file=@document.pdf" \
  -F "library=my-docs" \
  -F "version=1.0"
```

**Search documents:**
```bash
curl -X POST http://localhost:8080/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication", "limit": 5}'
```

**List libraries:**
```bash
curl http://localhost:8080/api/libraries
```

For full API documentation, see [API Reference](docs/API-REFERENCE.md).

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

Built with:
- **[Qdrant](https://qdrant.tech/)** - Vector database with hybrid search
- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern Python web framework
- **[FastEmbed](https://github.com/qdrant/fastembed)** - Fast embedding generation
- **[olmOCR](https://github.com/allenai/olmOCR)** - Vision-language OCR for PDFs
- **[Docker](https://www.docker.com/)** - Containerization

Inspired by [DRUID](https://github.com/cfahlgren1/druid) - DevDocs search system.

---

**Questions?** Open an issue on [GitHub](https://github.com/CodeMasterGohan/SAGE/issues) or check the [documentation](docs/).

**Ready to search smarter?** Get started: `docker-compose up -d` 🚀
