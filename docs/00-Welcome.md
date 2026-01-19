# 🏠 Welcome to SAGE-Docs

> **The Smart Accessible Gateway for Enterprise Documentation**

*Upload, search, and discover your documentation like never before.*

---

## 🎯 The Hook

**SAGE-Docs transforms your scattered documentation into a searchable, AI-powered knowledge base in minutes.**

Imagine uploading a ZIP file of markdown docs, PDFs, or even Excel spreadsheets—and instantly being able to semantically search across everything. That's SAGE.

---

## 🛠️ Tech Stack

Built with modern, production-ready technologies:

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-DC244C?style=for-the-badge&logo=qdrant&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![MCP](https://img.shields.io/badge/MCP_Protocol-4A154B?style=for-the-badge&logo=anthropic&logoColor=white)

### Core Dependencies

| Package | Purpose |
|---------|---------|
| `FastAPI 0.109` | High-performance REST API framework |
| `Qdrant Client` | Vector database for semantic search |
| `FastEmbed` | Local embedding model inference |
| `Docling` | PDF-to-markdown conversion with layout analysis |
| `MCP SDK` | Model Context Protocol for LLM integration |
| `BeautifulSoup4` | HTML parsing and cleanup |
| `python-docx` | Microsoft Word document processing |
| `openpyxl` | Excel spreadsheet processing |

---

## ✅ Features at a Glance

Why teams love SAGE-Docs:

✅ **Web-Based Upload** — Drag & drop documents through a sleek modern dashboard  
✅ **Hybrid Search** — Combines semantic understanding with BM25 keyword matching  
✅ **DBSF Fusion** — Advanced score normalization for better results than traditional RRF  
✅ **Multi-Format Support** — Markdown, HTML, PDF, DOCX, Excel, and ZIP archives  
✅ **Library Organization** — Group documents by library and version  
✅ **MCP Integration** — Expose search to LLMs like Claude and Gemini  
✅ **ColBERT Reranking** — Optional late-interaction reranking for maximum accuracy  
✅ **Beautiful Dark UI** — Modern, responsive interface with Tailwind CSS  
✅ **Docker-Ready** — One-command deployment with docker-compose  

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        SAGE-Docs System                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│   │   Frontend   │    │   Backend    │    │  MCP Server  │      │
│   │   (HTML/JS)  │───▶│   FastAPI    │───▶│   (MCP)      │      │
│   │   Port 8080  │    │   Port 8080  │    │   Port 8000  │      │
│   └──────────────┘    └──────┬───────┘    └──────┬───────┘      │
│                              │                    │              │
│                              ▼                    ▼              │
│                     ┌────────────────────────────────┐          │
│                     │       Qdrant Vector DB         │          │
│                     │   (Semantic + Sparse Search)   │          │
│                     │         Port 6334              │          │
│                     └────────────────────────────────┘          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📚 Documentation Structure

Navigate through the docs:

| Document | Description |
|----------|-------------|
| [🚀 Quick Start](./01-Quick-Start.md) | Get up and running in 5 minutes |
| [📖 User Guide](./02-User-Guide.md) | Complete walkthrough of features |
| [🧠 Developer Internals](./03-Developer-Internals.md) | Architecture deep-dive for contributors |
| [🔌 MCP Configuration](./04-MCP-Configuration.md) | Connect to VS Code, Claude, Gemini CLI |
| [🌐 Integrations Guide](./05-Integrations-Guide.md) | Remote access, Open WebUI, MCPO, security |

---

## 🌟 Ready to Get Started?

Head over to the **[Quick Start Guide](./01-Quick-Start.md)** and have SAGE-Docs running in under 5 minutes!

> 💡 **Tip:** SAGE-Docs works great with MCP-compatible AI assistants. Once running, your LLM can search your documentation directly!
