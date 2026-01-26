# SAGE-Docs

**Smart Accessible Gateway for Enterprise Documentation**

A documentation search system similar to DRUID, but with **web-based document upload** instead of DevDocs integration. Users can upload markdown, text, HTML, PDF, or ZIP files through a web interface, which get chunked, embedded, and indexed for semantic search.

## Features

- **📤 Web Upload**: Drag & drop or browse to upload documentation files
- **🛡️ Secure Processing**: Validation, sandboxing, and durable job queuing
- **🔍 Hybrid Search**: Semantic + keyword search with DBSF/RRF fusion
- **📚 Multi-Library**: Organize docs by library and version
- **🤖 MCP Server**: Expose search to LLMs via Model Context Protocol
- **🎨 Beautiful UI**: Modern dark theme dashboard

## Quick Start

```bash
# Start all services
docker-compose up -d --build

# Open dashboard
open http://localhost:8080
```

## Architecture

```
SAGE-Docs/
├── sage_core/           # Shared core library (chunking, processing, validation)
├── backend/             # FastAPI dashboard + REST API
│   └── server.py        # REST API endpoints
├── mcp-server/          # MCP server for LLM integration
│   └── main.py          # MCP tools (search, list, resolve, get)
├── tests/               # Integration tests
├── static/              # Web dashboard files
└── docker-compose.yml   # Service orchestration
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| Backend | 8080 | Dashboard + REST API |
| MCP Server | 8000 | MCP protocol for LLMs |
| Qdrant | 6334 | Vector database |

## Upload Supported Formats

- **Markdown**: `.md`, `.markdown`
- **HTML**: `.html`, `.htm`
- **Text**: `.txt`, `.rst`
- **PDF**: `.pdf`
- **Word**: `.docx`
- **Excel**: `.xlsx`, `.xls`
- **Archives**: `.zip` (extracts and processes all docs inside)

## API Endpoints

### Upload
- `POST /api/upload` - Upload single file
- `POST /api/upload-multiple` - Upload multiple files
- `DELETE /api/library/{name}` - Delete library

### Search
- `POST /api/search` - Hybrid search
- `POST /api/resolve` - Find matching libraries
- `GET /api/libraries` - List all libraries
- `GET /api/document?file_path=...` - Get full document

### Status
- `GET /api/status` - Connection status

## MCP Configuration

Add to your MCP client config:

```json
{
  "mcpServers": {
    "sage-docs": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

## Similarity to DRUID

This project maintains **the same code patterns and structure as DRUID** for easy maintenance:
- Same API response formats
- Same MCP tool signatures
- Same dashboard styling
- Same Qdrant collection schema

The main difference is replacing DevDocs integration with web upload.
