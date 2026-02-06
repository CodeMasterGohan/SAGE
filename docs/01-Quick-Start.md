# 🚀 Quick Start Guide

Get SAGE-Docs up and running in just 5 minutes!

---

## 📋 Prerequisites

Before you begin, make sure you have the following installed:

| Requirement | Version | Check Command |
|-------------|---------|---------------|
| Docker | 20.10+ | `docker --version` |
| Docker Compose | 2.0+ | `docker compose version` |
| Git | 2.0+ | `git --version` |

> ⚠️ **Warning:** SAGE-Docs requires at least **6GB of RAM** for the backend container. This is needed for loading the embedding models and PDF processing. Adjust your Docker resource limits if needed!

---

## ⚡ The 5-Minute Install

### Step 1: Clone the Repository

```bash
git clone https://github.com/CodeMasterGohan/SAGE.git
cd SAGE
```

### Step 2: Launch the Stack

```bash
docker-compose up -d --build
```

This command will:
- 🐋 Build the backend and MCP server containers
- 📦 Pull the Qdrant vector database image
- 🚀 Start all three services

> 💡 **Tip:** First launch may take 3-5 minutes as Docker builds the images and downloads embedding models. Subsequent starts are much faster!

### Step 3: Verify Everything is Running

```bash
docker-compose ps
```

You should see all containers in a `healthy` or `running` state:

```
NAME                     STATUS
sage-docs-dashboard      Up (healthy)
sage-docs-mcp            Up
sage-docs-qdrant         Up
sage-docs-refinery       Up (optional, legacy)
```

### Step 4: Open the Dashboard

🎉 Navigate to **http://localhost:8080** in your browser!

---

## 🔧 Configuration

### Environment Variables

SAGE-Docs uses environment variables for configuration. These are set in `docker-compose.yml`:

| Variable | Description | Default |
|----------|-------------|---------|
| `QDRANT_HOST` | Hostname of the Qdrant server | `qdrant` |
| `QDRANT_PORT` | Port for Qdrant connection | `6333` |
| `COLLECTION_NAME` | Main collection for documents | `sage_docs` |
| `JOBS_COLLECTION` | Collection for async job state (Phase 4) | `sage_jobs` |
| `EMBEDDING_MODE` | Embedding backend (`local` or `remote`) | `local` |
| `DENSE_MODEL_NAME` | Dense embedding model to use | `sentence-transformers/all-MiniLM-L6-v2` |
| `DENSE_VECTOR_SIZE` | Dimension of dense vectors | `384` |
| `USE_NOMIC_PREFIX` | Add Nomic prefixes (for Nomic models) | `false` |
| `UPLOAD_DIR` | Directory for uploaded files | `/app/uploads` |
| `PDF_TIMEOUT` | PDF processing timeout in seconds (Phase 4) | `600` |
| `WORKER_PROCESSES` | Background workers for async uploads | `2` |

**Remote Embeddings (GPU):**
| `VLLM_EMBEDDING_URL` | vLLM server URL | *(empty)* |
| `VLLM_MODEL_NAME` | Model name | `nomic-ai/nomic-embed-text-v1.5` |
| `VLLM_API_KEY` | API key | *(empty)* |

**PDF Processing (GPU):**
| `OLMOCR_SERVER` | olmocr server URL | *(empty)* |
| `OLMOCR_API_KEY` | API key | *(empty)* |

> ℹ️ **Note:** The embedding model runs locally inside the container. No API keys or external services required for the default configuration!

### Using a Different Embedding Model

To use a different embedding model, update the environment variables:

```yaml
environment:
  - DENSE_MODEL_NAME=nomic-ai/nomic-embed-text-v1.5
  - DENSE_VECTOR_SIZE=768
  - USE_NOMIC_PREFIX=true
```

> ⚠️ **Warning:** You must delete the existing Qdrant collection if you change embedding models, as vector dimensions won't match!

---

## 🔌 MCP Client Configuration

To connect your LLM (Claude, Gemini CLI, etc.) to SAGE-Docs, add this to your MCP client config:

```json
{
  "mcpServers": {
    "sage-docs": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

### Available MCP Tools

Once connected, your LLM will have access to:

| Tool | Description |
|------|-------------|
| `search_docs` | Semantic + keyword hybrid search |
| `list_libraries` | Get all indexed libraries |
| `resolve_library` | Find matching libraries by name |
| `get_document` | Retrieve full document content |

---

## ✅ Quick Verification Checklist

- [ ] All containers running: `docker-compose ps`
- [ ] Dashboard loads: http://localhost:8080
- [ ] Connection shows "Connected" in bottom-left corner
- [ ] Can upload a test document
- [ ] Search returns results

---

## 🆘 Troubleshooting

### Container Won't Start

```bash
# Check logs for errors
docker-compose logs dashboard
docker-compose logs mcp-server
docker-compose logs qdrant
```

### "Model loading failed" Error

The embedding models require significant memory. Try:

```bash
# Increase Docker memory limit
# Or reduce memory in docker-compose.yml:
mem_limit: 4g
memswap_limit: 6g
```

### PDF Upload Stuck

PDF processing uses olmocr for layout analysis, which can be slow. For PDFs:
- Small PDFs (<10MB): Synchronous processing
- Large PDFs (>10MB): Automatically uses async endpoint (Phase 4)

Check processing status:

```bash
# View dashboard logs
docker-compose logs -f dashboard

# Check for specific job
curl http://localhost:8080/api/upload/status/YOUR_TASK_ID
```

If stuck, check:
1. PDF timeout setting: `PDF_TIMEOUT=600` (increase if needed)
2. Worker processes: `WORKER_PROCESSES=2`
3. Available memory: PDFs need 2-4GB RAM

For persistent issues, see [troubleshooting.md](./troubleshooting.md#pdf-processing-issues)

---

## 🎯 What's Next?

Now that SAGE-Docs is running:

1. **[📖 User Guide](./02-User-Guide.md)** — Learn how to upload and search documentation
2. **[🧠 Developer Internals](./03-Developer-Internals.md)** — Understand the architecture for customization

> 💡 **Tip:** Try uploading a ZIP file of your project's documentation to quickly populate the search index!
