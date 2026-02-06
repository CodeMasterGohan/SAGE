# SAGE Configuration Reference

Complete guide to all configuration options and environment variables.

## Table of Contents
- [Core Settings](#core-settings)
- [Embedding Configuration](#embedding-configuration)
- [PDF Processing](#pdf-processing)
- [Chunking Configuration](#chunking-configuration)
- [Upload Limits](#upload-limits)
- [Qdrant Connection](#qdrant-connection)
- [Performance Tuning](#performance-tuning)
- [Configuration Examples](#configuration-examples)

---

## Core Settings

### COLLECTION_NAME
**Default:** `sage_docs`  
**Description:** Name of the main Qdrant collection for document storage.  
**Example:**
```bash
COLLECTION_NAME=my_docs
```

### JOBS_COLLECTION
**Default:** `sage_jobs`  
**Description:** Name of the Qdrant collection for async job state tracking.  
**Example:**
```bash
JOBS_COLLECTION=background_jobs
```

### UPLOAD_DIR
**Default:** `/app/uploads`  
**Description:** Directory where uploaded files are stored on disk.  
**Example:**
```bash
UPLOAD_DIR=/mnt/storage/sage-uploads
```

### WORKER_PROCESSES
**Default:** `2`  
**Description:** Number of worker processes for background upload jobs.  
**Recommendation:** Set to number of CPU cores for CPU-bound workloads.  
**Example:**
```bash
WORKER_PROCESSES=4
```

---

## Embedding Configuration

### EMBEDDING_MODE
**Default:** `local`  
**Options:** `local` | `remote`  
**Description:** Whether to generate embeddings locally or via external API.

**Local Mode:**
- Uses FastEmbed models
- No external dependencies
- Slower but consistent
- No API costs

**Remote Mode:**
- Requires external embedding service (vLLM, OpenAI)
- Faster with GPU
- Network dependency
- API costs apply

**Example:**
```bash
# Local embeddings (default)
EMBEDDING_MODE=local

# Remote embeddings (requires GPU server)
EMBEDDING_MODE=remote
VLLM_EMBEDDING_URL=http://gpu-server:8000
```

---

### DENSE_MODEL_NAME
**Default:** `sentence-transformers/all-MiniLM-L6-v2`  
**Description:** Model name for dense embeddings (local mode).  
**Vector Size:** 384 dimensions  
**Alternatives:**
- `sentence-transformers/all-MiniLM-L12-v2` (384D, slower but better)
- `BAAI/bge-small-en-v1.5` (384D, multilingual)
- `nomic-ai/nomic-embed-text-v1` (768D, requires remote mode)

**Example:**
```bash
DENSE_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
```

**⚠️ Important:** Changing this requires reindexing all documents and updating `DENSE_VECTOR_SIZE`.

---

### DENSE_VECTOR_SIZE
**Default:** `384`  
**Description:** Dimension size of dense embeddings.  
**Must match:** `DENSE_MODEL_NAME` output dimensions.

**Common Sizes:**
- 384: MiniLM models
- 512: Some BERT variants
- 768: Nomic, large BERT models
- 1536: OpenAI text-embedding-ada-002

**Example:**
```bash
DENSE_VECTOR_SIZE=768
```

---

### USE_NOMIC_PREFIX
**Default:** `false`  
**Description:** Whether to prepend "search_document:" and "search_query:" prefixes.  
**When to use:** Only for Nomic models (nomic-ai/nomic-embed-text-v1.5).  
**Example:**
```bash
USE_NOMIC_PREFIX=true
```

---

### Remote Embedding Settings

#### VLLM_EMBEDDING_URL
**Default:** *(empty)*  
**Description:** URL of vLLM embedding server.  
**Format:** `http://hostname:port`  
**Example:**
```bash
VLLM_EMBEDDING_URL=http://192.168.1.100:8000
```

#### VLLM_MODEL_NAME
**Default:** `nomic-ai/nomic-embed-text-v1.5`  
**Description:** Model identifier for vLLM server.  
**Must match:** Model loaded on vLLM server.  
**Example:**
```bash
VLLM_MODEL_NAME=nomic-ai/nomic-embed-text-v1.5
```

#### VLLM_API_KEY
**Default:** *(empty)*  
**Description:** API key for authenticated vLLM server (optional).  
**Example:**
```bash
VLLM_API_KEY=sk-1234567890abcdef
```

---

### OpenAI Configuration (Alternative to vLLM)

To use OpenAI embeddings, modify the code to use:
```bash
EMBEDDING_API_URL=https://api.openai.com/v1/embeddings
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
```

**Cost Comparison:**
- text-embedding-3-small: $0.02 per 1M tokens
- text-embedding-3-large: $0.13 per 1M tokens
- text-embedding-ada-002: $0.10 per 1M tokens

---

## PDF Processing

### OLMOCR_SERVER
**Default:** *(empty - runs locally)*  
**Description:** URL of remote olmocr server for GPU-accelerated PDF processing.  
**Format:** `http://hostname:port/v1`  
**Example:**
```bash
OLMOCR_SERVER=http://gpu-server:8000/v1
```

**Local vs Remote:**
- **Empty:** olmocr runs as subprocess (CPU, slow)
- **Set:** olmocr runs on remote GPU server (fast)

---

### OLMOCR_API_KEY
**Default:** *(empty)*  
**Description:** API key for authenticated olmocr server (optional).  
**Example:**
```bash
OLMOCR_API_KEY=your-secret-key
```

---

### OLMOCR_MODEL
**Default:** `allenai/olmOCR-2-7B-1025-FP8`  
**Description:** Model identifier for olmocr.  
**Alternatives:**
- `allenai/olmOCR-2-7B` (full precision, slower)
- `allenai/olmOCR-base` (smaller, faster, less accurate)

**Example:**
```bash
OLMOCR_MODEL=allenai/olmOCR-2-7B-1025-FP8
```

---

### PDF_TIMEOUT
**Default:** `600` (10 minutes)  
**Description:** Timeout in seconds for PDF processing.  
**Recommendation:** Increase for very large PDFs (500+ pages).  
**Example:**
```bash
PDF_TIMEOUT=1200  # 20 minutes
```

---

### PDF_MAX_SIZE
**Default:** *(not enforced)*  
**Description:** Maximum PDF file size in bytes.  
**Note:** Controlled by `MAX_FILE_SIZE` for all file types.  
**Example:**
```bash
PDF_MAX_SIZE=104857600  # 100MB
```

---

## Chunking Configuration

### CHUNK_SIZE
**Default:** `800`  
**Description:** Target chunk size in characters (approximate).  
**Impact:**
- **Smaller (400-600):** More precise search, more chunks, slower indexing
- **Larger (1000-1500):** More context, fewer chunks, faster indexing

**Example:**
```bash
CHUNK_SIZE=1000
```

---

### CHUNK_OVERLAP
**Default:** `80`  
**Description:** Overlap between adjacent chunks in characters.  
**Purpose:** Prevent splitting sentences/paragraphs across chunks.  
**Recommendation:** 10-15% of CHUNK_SIZE.  
**Example:**
```bash
CHUNK_OVERLAP=100
```

---

### MAX_CHUNK_CHARS
**Default:** `4000`  
**Description:** Hard limit on chunk size in characters.  
**Purpose:** Safety truncation to prevent oversized chunks.  
**Impact:** Chunks exceeding this are truncated with warning.  
**Example:**
```bash
MAX_CHUNK_CHARS=5000
```

---

### MAX_CHUNK_TOKENS
**Default:** `500`  
**Description:** Maximum tokens per chunk (for embedding models).  
**Purpose:** Prevent exceeding model's max input length.  
**Note:** Most embedding models support 512 tokens.  
**Example:**
```bash
MAX_CHUNK_TOKENS=512
```

---

### MAX_BATCH_TOKENS
**Default:** `2000`  
**Description:** Maximum total tokens per embedding batch.  
**Impact:**
- **Larger:** Fewer API calls, faster, but risk timeouts
- **Smaller:** More API calls, slower, but more reliable

**Recommendation by Mode:**
- Local: 1000-2000 (CPU memory limits)
- Remote: 2000-5000 (GPU memory, API limits)

**Example:**
```bash
MAX_BATCH_TOKENS=3000
```

---

## Upload Limits

### MAX_FILE_SIZE
**Default:** `52428800` (50MB)  
**Description:** Maximum size in bytes for individual file uploads.  
**Purpose:** Prevent DoS and memory exhaustion.  
**Example:**
```bash
MAX_FILE_SIZE=104857600  # 100MB
```

---

### MAX_ZIP_ENTRIES
**Default:** `500`  
**Description:** Maximum number of files in a ZIP archive.  
**Purpose:** Prevent zip bomb attacks.  
**Example:**
```bash
MAX_ZIP_ENTRIES=1000
```

---

### MAX_ZIP_TOTAL_SIZE
**Default:** `209715200` (200MB)  
**Description:** Maximum total uncompressed size of ZIP archive.  
**Purpose:** Prevent zip bomb attacks.  
**Example:**
```bash
MAX_ZIP_TOTAL_SIZE=524288000  # 500MB
```

---

## Qdrant Connection

### QDRANT_HOST
**Default:** `localhost`  
**Description:** Hostname or IP address of Qdrant server.  
**Docker:** Use service name (e.g., `qdrant`)  
**Example:**
```bash
QDRANT_HOST=qdrant
QDRANT_HOST=192.168.1.50
```

---

### QDRANT_PORT
**Default:** `6333`  
**Description:** Port number for Qdrant HTTP API.  
**Example:**
```bash
QDRANT_PORT=6333
```

---

### QDRANT_API_KEY
**Default:** *(not implemented)*  
**Description:** API key for Qdrant Cloud or secured instances.  
**Note:** Currently not used in code. Add if using Qdrant Cloud.  
**Example:**
```bash
QDRANT_API_KEY=your-api-key
```

---

## Performance Tuning

### INGESTION_CONCURRENCY
**Default:** 
- Local mode: `10`
- Remote mode: `100`

**Description:** Maximum concurrent embedding requests.  
**Impact:**
- **Higher:** Faster bulk ingestion, but risk OOM or rate limits
- **Lower:** Slower, but more stable

**Recommendation:**
- Local CPU: 5-10
- Local GPU: 20-50
- Remote API: 50-200

**Example:**
```bash
INGESTION_CONCURRENCY=50
```

---

## Configuration Examples

### Development Environment (Local)

```bash
# .env file for local development
QDRANT_HOST=localhost
QDRANT_PORT=6333
COLLECTION_NAME=sage_docs
EMBEDDING_MODE=local
DENSE_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
DENSE_VECTOR_SIZE=384
CHUNK_SIZE=800
CHUNK_OVERLAP=80
MAX_FILE_SIZE=52428800
WORKER_PROCESSES=2
PDF_TIMEOUT=600
```

**Use case:** Running on laptop, no GPU, testing features.

---

### Production (Self-Hosted GPU)

```bash
# .env file for production with dedicated GPU server
QDRANT_HOST=qdrant.internal
QDRANT_PORT=6333
COLLECTION_NAME=production_docs
EMBEDDING_MODE=remote
VLLM_EMBEDDING_URL=http://gpu-01.internal:8000
VLLM_MODEL_NAME=nomic-ai/nomic-embed-text-v1.5
VLLM_API_KEY=sk-prod-secret-key-12345
DENSE_VECTOR_SIZE=768
USE_NOMIC_PREFIX=true
OLMOCR_SERVER=http://gpu-01.internal:8000/v1
OLMOCR_API_KEY=sk-prod-secret-key-12345
CHUNK_SIZE=1000
CHUNK_OVERLAP=100
MAX_FILE_SIZE=104857600
MAX_ZIP_ENTRIES=1000
INGESTION_CONCURRENCY=100
WORKER_PROCESSES=8
PDF_TIMEOUT=900
```

**Use case:** High-volume production deployment with GPU acceleration.

---

### Production (OpenAI API)

```bash
# .env file for production using OpenAI embeddings
QDRANT_HOST=qdrant-cluster.internal
QDRANT_PORT=6333
COLLECTION_NAME=production_docs
EMBEDDING_MODE=remote
# Note: Requires code modification to use OpenAI SDK
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
DENSE_VECTOR_SIZE=1536
CHUNK_SIZE=1000
MAX_FILE_SIZE=52428800
INGESTION_CONCURRENCY=50
WORKER_PROCESSES=4
# PDF still processed locally
PDF_TIMEOUT=600
```

**Use case:** Cloud deployment with managed embedding service.

---

### High-Volume Ingestion

```bash
# Optimized for bulk document ingestion
EMBEDDING_MODE=remote
VLLM_EMBEDDING_URL=http://gpu-cluster:8000
INGESTION_CONCURRENCY=200
MAX_BATCH_TOKENS=5000
WORKER_PROCESSES=16
CHUNK_SIZE=1200
CHUNK_OVERLAP=120
MAX_FILE_SIZE=104857600
MAX_ZIP_ENTRIES=2000
PDF_TIMEOUT=1200
```

**Use case:** Initial data migration, ingesting thousands of documents.

---

### Cost-Optimized Setup

```bash
# Minimize API costs by maximizing local processing
EMBEDDING_MODE=local
DENSE_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
CHUNK_SIZE=1000  # Fewer chunks = fewer API calls
MAX_BATCH_TOKENS=2000  # Larger batches
INGESTION_CONCURRENCY=5  # Lower concurrency to avoid rate limits
WORKER_PROCESSES=2
# Process PDFs locally to avoid GPU server costs
PDF_TIMEOUT=900
```

**Use case:** Budget-constrained deployment, low upload frequency.

---

### Memory-Constrained Environment

```bash
# Optimized for low-memory servers (e.g., 2GB RAM)
EMBEDDING_MODE=local
DENSE_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
CHUNK_SIZE=600  # Smaller chunks
MAX_CHUNK_CHARS=3000
MAX_BATCH_TOKENS=1000  # Smaller batches
INGESTION_CONCURRENCY=3  # Low concurrency
WORKER_PROCESSES=1  # Single worker
MAX_FILE_SIZE=20971520  # 20MB limit
```

**Use case:** Docker on low-memory VPS or edge device.

---

## Configuration Best Practices

### 1. Always Set in `.env` File

```bash
# Create .env file in project root
cp .env.example .env
nano .env
```

### 2. Never Commit Secrets

```bash
# .gitignore
.env
.env.local
*.key
```

### 3. Use Environment-Specific Configs

```bash
# .env.development
EMBEDDING_MODE=local

# .env.production
EMBEDDING_MODE=remote
VLLM_EMBEDDING_URL=http://gpu-01:8000
```

### 4. Document Your Configuration

```bash
# .env.example (committed to repo)
# Qdrant connection
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# Embedding configuration
EMBEDDING_MODE=local  # Change to 'remote' for GPU

# Required for remote mode:
# VLLM_EMBEDDING_URL=http://your-gpu-server:8000
# VLLM_API_KEY=your-api-key
```

---

## Docker Compose Configuration

### docker-compose.yml

```yaml
services:
  dashboard:
    environment:
      # Override defaults here
      - EMBEDDING_MODE=local
      - DENSE_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
      # Or reference .env file variables:
      - VLLM_EMBEDDING_URL=${VLLM_EMBEDDING_URL:-}
      - VLLM_API_KEY=${VLLM_API_KEY:-}
```

### docker-compose.override.yml

```yaml
# Local developer overrides (not committed)
services:
  dashboard:
    environment:
      - EMBEDDING_MODE=local
      - LOG_LEVEL=DEBUG
```

---

## Kubernetes ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: sage-config
data:
  QDRANT_HOST: "qdrant-service"
  QDRANT_PORT: "6333"
  COLLECTION_NAME: "production_docs"
  EMBEDDING_MODE: "remote"
  DENSE_MODEL_NAME: "sentence-transformers/all-MiniLM-L6-v2"
  CHUNK_SIZE: "1000"
  WORKER_PROCESSES: "4"

---
apiVersion: v1
kind: Secret
metadata:
  name: sage-secrets
type: Opaque
stringData:
  VLLM_API_KEY: "sk-prod-secret"
  OLMOCR_API_KEY: "sk-prod-secret"
```

---

## Health Check Configuration

```yaml
# docker-compose.yml
services:
  dashboard:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

---

## Troubleshooting Configuration Issues

### Issue: "Collection not found"
**Solution:** Ensure `COLLECTION_NAME` matches across all services:
```bash
# Check all service configs
docker-compose config | grep COLLECTION_NAME
```

### Issue: "Embedding dimension mismatch"
**Solution:** `DENSE_VECTOR_SIZE` must match model output:
```bash
# MiniLM-L6-v2
DENSE_VECTOR_SIZE=384

# Nomic models
DENSE_VECTOR_SIZE=768
```

### Issue: "Out of memory during embedding"
**Solution:** Reduce batch sizes and concurrency:
```bash
MAX_BATCH_TOKENS=1000
INGESTION_CONCURRENCY=5
WORKER_PROCESSES=2
```

### Issue: "PDF processing timeout"
**Solution:** Increase timeout or use remote GPU:
```bash
PDF_TIMEOUT=1200  # 20 minutes
# Or use GPU
OLMOCR_SERVER=http://gpu-server:8000/v1
```

---

## Environment Variable Priority

Configuration is loaded in this order (highest priority first):

1. **Runtime environment variables** (docker run -e)
2. **docker-compose.yml environment section**
3. **.env file** (docker-compose)
4. **Code defaults** (in Python files)

Example:
```bash
# These override docker-compose.yml
docker-compose run -e EMBEDDING_MODE=remote dashboard

# These override .env
export QDRANT_HOST=production-qdrant
docker-compose up
```

---

## Validation Checklist

Before deploying, validate your configuration:

- [ ] All services have matching `QDRANT_HOST` and `QDRANT_PORT`
- [ ] All services have matching `COLLECTION_NAME`
- [ ] `DENSE_VECTOR_SIZE` matches your embedding model
- [ ] Remote mode: `VLLM_EMBEDDING_URL` is accessible
- [ ] Secrets (API keys) are in `.env`, not committed
- [ ] Memory limits appropriate for `WORKER_PROCESSES`
- [ ] `PDF_TIMEOUT` sufficient for largest PDFs
- [ ] Upload limits (`MAX_FILE_SIZE`) match your use case
- [ ] Health check endpoints return 200 OK

```bash
# Quick validation
curl http://localhost:8080/health
curl http://localhost:6333/collections/sage_docs
```
