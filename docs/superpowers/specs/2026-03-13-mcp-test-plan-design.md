# 📝 MCP Test Plan: Scenario-Based Coverage

**Date:** 2026-03-13  
**Topic:** Verifying MCP Server "Usefulness" for Architectural Research  
**Status:** Design Phase

---

## 🎯 Goal

The primary goal of this test plan is to verify that the SAGE-Docs MCP server provides **useful, complete, and architecturally relevant** information to the customer. We define "usefulness" for the **Architectural Research** persona as the ability to retrieve a comprehensive set of documents (the "full puzzle") rather than just isolated snippets.

---

## 🏛️ Architecture

The test plan follows a **Scenario-Based Coverage** approach, simulating actual customer journeys and comparing the MCP server's output against a "Gold Standard" reference.

### Components

1.  **📚 Scenarios (`tests/mcp/scenarios.json`)**:
    *   Defines 5-10 complex, architectural research tasks.
    *   Specifies queries, target libraries/versions, and "must-have" results.
    *   Includes negative test cases for ambiguity and fallback logic.

2.  **🏎️ Runner (`tests/mcp/runner.py`)**:
    *   A Python-based orchestrator that connects to the MCP server.
    *   Executes tool calls in sequence (e.g., `resolve_library` -> `search_docs` -> `get_document`).
    *   Captures full responses, including metadata, search notes, and context chunks.

3.  **📊 Scoring Engine (`tests/mcp/scoring.py`)**:
    *   Evaluates the captured output against the "Gold Standard".
    *   Calculates key metrics: Completeness, Context, Metadata, and Latency.
    *   Generates a structured JSON report of the results.

---

## ⚙️ Data Flow

1.  **Read Scenarios**: `runner.py` loads test cases from `scenarios.json`.
2.  **Execute & Capture**:
    *   `runner.py` initializes a fresh MCP session for each scenario.
    *   Tool calls are executed with `context_chunks=3` to ensure deep context.
    *   The complete tool response (JSON) is captured for analysis.
3.  **Evaluate**:
    *   `scoring.py` compares the retrieved `file_paths` and `content` against the "must-have" list in the scenario.
    *   Metadata (library/version resolution) and search notes (e.g., "Global Fallback") are verified.
4.  **Reporting**: A final report is generated in `tests/mcp/results/`, highlighting successes, failures, and performance metrics.

---

## 📊 Key Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **Completeness Score** | % of "must-have" architectural documents/concepts found in top 5 results. | > 80% |
| **Context Score** | % of results that correctly included surrounding `context_chunks`. | 100% |
| **Metadata Score** | Accuracy of library/version resolution and "Smart Context" persistence. | > 95% |
| **Latency** | Responsiveness of `search_docs` and `get_document` (ms). | < 2000ms |

---

## 🛡️ Error Handling & Testing

*   **Session Isolation**: Each scenario starts with a clean context to prevent cross-contamination.
*   **Retry Logic**: Basic retries for connection timeouts during model pre-loading.
*   **Negative Testing**: Verification of "Ambiguity Handler" for multi-library queries and "Global Fallback" for zero-result targeted searches.
*   **Mock Mode**: A toggle to run against a mock Qdrant client for logic verification without a database.

---

## 🔗 Related Docs

- **[🔌 MCP Configuration Guide](../../docs/04-MCP-Configuration.md)**
- **[🧠 Developer Internals](../../docs/03-Developer-Internals.md)**
