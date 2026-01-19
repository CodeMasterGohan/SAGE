# 🔌 MCP Configuration Guide

Connect SAGE-Docs to your favorite AI-powered tools via Model Context Protocol.

---

## 🤔 What is MCP?

The **Model Context Protocol (MCP)** is an open standard that allows AI assistants to interact with external tools and data sources. SAGE-Docs implements MCP, enabling LLMs like Claude, Gemini, and others to search your documentation directly.

---

## 🖥️ VS Code Integration

### Gemini CLI / Claude for VS Code

If you're using an AI extension in VS Code that supports MCP, add SAGE-Docs to your configuration.

#### Step 1: Open MCP Settings

In VS Code, open your MCP configuration file. This is typically located at:

- **Windows:** `%APPDATA%\Code\User\globalStorage\<extension>\mcp.json`
- **macOS:** `~/Library/Application Support/Code/User/globalStorage/<extension>/mcp.json`
- **Linux:** `~/.config/Code/User/globalStorage/<extension>/mcp.json`

> 💡 **Tip:** Many extensions have a command palette option like "MCP: Open Configuration" or similar.

#### Step 2: Add SAGE-Docs Server

Add the following to your `mcpServers` configuration:

```json
{
  "mcpServers": {
    "sage-docs": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

#### Step 3: Reload the Extension

- Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on macOS)
- Type "Reload Window" and select it
- The SAGE-Docs tools should now be available

---

## 🤖 Claude Desktop

### Configuration

1. Open Claude Desktop settings
2. Navigate to the MCP section
3. Add a new server:

```json
{
  "mcpServers": {
    "sage-docs": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

> ℹ️ **Note:** The config file location varies by OS:
> - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
> - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

### Verify Connection

After restarting Claude Desktop, you should see a 🔧 tools icon. Click it to verify "sage-docs" is listed.

---

## 💻 Gemini CLI

### Configuration

Add SAGE-Docs to your Gemini CLI config:

```json
{
  "mcpServers": {
    "sage-docs": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

Config file locations:
- **macOS/Linux:** `~/.gemini/config.json` or `~/.config/gemini/settings.json`
- **Windows:** `%USERPROFILE%\.gemini\config.json`

---

## 🐳 Using with Docker Network

If your MCP client is also running in Docker, use the container name instead of `localhost`:

```json
{
  "mcpServers": {
    "sage-docs": {
      "url": "http://sage-docs-mcp:8000/sse"
    }
  }
}
```

> ⚠️ **Warning:** Both containers must be on the same Docker network for this to work.

---

## 🛠️ Available Tools

Once connected, your AI assistant gains access to these tools:

### `search_docs`

Search documentation using hybrid semantic + keyword search.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | ✅ | What to search for |
| `library` | string | ❌ | Filter to specific library |
| `version` | string | ❌ | Filter to specific version |
| `limit` | int | ❌ | Max results (default: 5) |
| `rerank` | bool | ❌ | Enable ColBERT reranking |
| `fusion` | string | ❌ | "dbsf" or "rrf" |

**Example prompt:**
> "Search SAGE-Docs for authentication patterns"

### `list_libraries`

Get all indexed libraries with their versions.

**Example prompt:**
> "What libraries are available in SAGE-Docs?"

### `resolve_library`

Find libraries matching a name query. Use this before `search_docs` to identify the correct library filter.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | ✅ | Library name to search |
| `limit` | int | ❌ | Max results (default: 5) |

**Example prompt:**
> "Find the React library in SAGE-Docs"

### `get_document`

Retrieve the full content of a specific document.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | ✅ | Path from search results |

**Example prompt:**
> "Get the full document at /app/uploads/react/latest/hooks.md"

---

## 🔧 Troubleshooting

### "Connection refused" Error

1. Verify SAGE-Docs is running:
   ```bash
   docker-compose ps
   ```

2. Check the MCP server logs:
   ```bash
   docker-compose logs mcp-server
   ```

3. Test the endpoint directly:
   ```bash
   curl http://localhost:8000/sse
   ```

### Tools Not Appearing

- Reload/restart your AI client after config changes
- Check for JSON syntax errors in your config
- Verify the URL matches exactly: `http://localhost:8000/sse`

### Slow Responses

The first query may be slow as embedding models load. Subsequent queries are faster.

> 💡 **Tip:** Use the `--preload` flag when starting the MCP server to load models at startup:
> ```bash
> python main.py --transport http --port 8000 --preload
> ```

---

## 📝 Example Conversations

### Basic Search

> **You:** Search SAGE-Docs for how to handle form validation
> 
> **Assistant:** *Uses `search_docs` tool*
> 
> I found 5 relevant results about form validation...

### Filtered Search

> **You:** First, find the React library in SAGE-Docs, then search for useState
> 
> **Assistant:** *Uses `resolve_library` first, then `search_docs` with library filter*
> 
> Found the "react" library with 127 documents. Here's what I found about useState...

### Get Full Document

> **You:** That hooks.md file looks useful. Can you show me the full content?
> 
> **Assistant:** *Uses `get_document` tool*
> 
> Here's the complete document content...

---

## 🔗 Related Docs

- **[🏠 Welcome](./00-Welcome.md)** — Project overview
- **[🚀 Quick Start](./01-Quick-Start.md)** — Get running fast
- **[📖 User Guide](./02-User-Guide.md)** — Feature walkthrough
- **[🧠 Developer Internals](./03-Developer-Internals.md)** — Architecture deep-dive

---

> 💡 **Tip:** Once configured, try asking your AI assistant "What can you do with SAGE-Docs?" to see all available tools!
