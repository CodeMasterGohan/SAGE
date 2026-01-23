# 📖 User Guide

Master every feature of SAGE-Docs with this comprehensive walkthrough.

---

## 🗺️ The Dashboard Tour

When you first open SAGE-Docs at **http://localhost:8080**, you'll see a sleek, modern interface with three main areas:

![Screenshot placeholder - Full dashboard view](./screenshots/dashboard-overview.png)

### Sidebar Navigation

The left sidebar contains:

- **🔍 Search Tab** — The default view for searching documentation
- **📤 Upload Tab** — Switch here to add new documents
- **📚 Libraries List** — Quick access to browse by library
- **🔗 Quick Links** — Shortcuts like "All Libraries" and "Clear Search"
- **📊 Status Footer** — Shows Qdrant connection status and document count

### Main Content Area

The central area changes based on your selected tab:

- **Search View** — Hero search box with results grid
- **Upload View** — Drag & drop zone and library management

---

## 🔍 Searching Documentation

### Basic Search

1. Click on the **Search** tab (if not already selected)
2. Type your query in the search box (e.g., "how to handle authentication")
3. Press **Enter** or wait for auto-search

![Screenshot placeholder - Search results](./screenshots/search-results.png)

### Understanding Search Results

Each result card shows:

| Element | Description |
|---------|-------------|
| **Title** | Document or section title |
| **Library Badge** | Which library this doc belongs to |
| **Version Badge** | The version number |
| **Score** | Relevance score (higher = more relevant) |
| **Content Preview** | Snippet of matching content |

> 💡 **Tip:** Click on any result to expand and see the full content!

### Filtering by Library

To narrow your search to a specific library:

1. Click on a library name in the sidebar
2. The filter appears below the search box
3. Search results will only include that library
4. Click the **X** button to clear the filter

### Choosing Fusion Method

SAGE-Docs uses hybrid search, combining semantic and keyword results. You can choose how these are fused:

| Method | When to Use |
|--------|-------------|
| **DBSF** (Default) | Better normalization, recommended for most searches |
| **RRF** | Faster, but may favor keyword matches |

Use the dropdown next to the search box to switch methods.

---

## 📤 Uploading Documents

### Supported File Formats

SAGE-Docs can process:

| Format | Extensions | Notes |
|--------|------------|-------|
| **Markdown** | `.md`, `.markdown` | Preserves headers and code blocks |
| **HTML** | `.html`, `.htm` | Converted to clean Markdown |
| **Plain Text** | `.txt`, `.rst` | Chunked as-is |
| **PDF** | `.pdf` | Uses olmocr for layout analysis |
| **Word** | `.docx` | Extracts text with heading structure |
| **Excel** | `.xlsx`, `.xls` | Converts sheets to searchable text |
| **Archives** | `.zip` | Extracts and processes all docs inside |

### Step-by-Step Upload

1. Click the **Upload** tab in the sidebar
2. Enter a **Library Name** (required) — e.g., "react-docs"
3. Enter a **Version** (optional, defaults to "latest")
4. Drag files into the drop zone OR click to browse

![Screenshot placeholder - Upload in progress](./screenshots/upload-progress.png)

5. Watch the progress indicator
6. See the success message with chunk count

> ⚠️ **Warning:** PDF files may take significantly longer due to layout analysis. The page will show a progress message, and you can safely close the browser—processing continues in the background.

### Uploading Multiple Files

You can select multiple files at once! They'll all be processed and indexed under the same library name.

### Uploading a ZIP Archive

Have a folder of documentation? ZIP it up!

```bash
zip -r my-docs.zip ./docs-folder
```

Then upload the ZIP file. SAGE-Docs will:
- Extract all supported file types
- Ignore hidden files and unsupported formats
- Process each document individually
- Index everything under your chosen library name

---

## 📚 Managing Libraries

### Viewing All Libraries

Click **All Libraries** in the Quick Links section, or scroll through the sidebar list.

### Deleting a Library

> ⚠️ **Warning:** This action cannot be undone!

1. Go to the **Upload** tab
2. Scroll to the **Manage Libraries** section
3. Find the library you want to delete
4. Click the **Delete** button (trash icon)
5. Confirm the deletion

---

## 🤖 Using with AI Assistants

### Searching via MCP

Once your MCP client is configured (see [Quick Start](./01-Quick-Start.md#mcp-client-configuration)), you can ask your LLM to search for you:

**Example prompts:**

- "Search SAGE-Docs for how to handle errors"
- "Find documentation about authentication in the react library"
- "What libraries are available in SAGE-Docs?"

### Common MCP Commands

| Action | What to Ask |
|--------|-------------|
| Search all docs | "Search for [topic]" |
| Search specific library | "Search [library] for [topic]" |
| List libraries | "What libraries are in SAGE-Docs?" |
| Get full document | "Get the full document at [file path]" |

---

## 🎨 UI Features

### Dark Theme

SAGE-Docs uses a beautiful dark theme by default with:
- Cyan accent colors
- Subtle glow effects
- Smooth transitions
- JetBrains Mono for code

### Responsive Design

The interface adapts to:
- 🖥️ Desktop (full sidebar)
- 📱 Tablet (collapsible sidebar)
- 📞 Mobile (stacked layout)

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Execute search |
| `Escape` | Clear search input |
| `/` | Focus search box |

---

## 💡 Pro Tips

### Optimize Your Searches

1. **Be specific** — "React useState hook" beats "hooks"
2. **Use library filters** — Narrow down when you know the source
3. **Try both fusion methods** — DBSF usually wins, but RRF can surprise you

### Organize Your Libraries

- Use consistent naming: `react-18.2` not `React v18.2`
- Group related docs under one library
- Use versions for different releases

### Bulk Import Strategy

For large documentation sets:
1. Create a ZIP with proper folder structure
2. Upload once, let it process
3. Check the sidebar for confirmation

---

## 🔄 What's Next?

Ready to dive deeper?

- **[🧠 Developer Internals](./03-Developer-Internals.md)** — Understand how SAGE-Docs works under the hood
- **[🏠 Back to Welcome](./00-Welcome.md)** — Review the overview

> 💡 **Tip:** The best way to learn is to upload some docs and start searching! Try your own project's README as a quick test.
