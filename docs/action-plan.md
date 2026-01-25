# Priority-Ordered Action Plan

## P0 – Critical (must fix before production)
- **Patch Stored XSS Vulnerability:** Wrap `${result.library}` and `${result.version}` in `escapeHtml()` in `app.js`. This is a critical security flaw allowing arbitrary code execution in the dashboard. (Benefit: Immediate protection against injections; Effort: S)
- **Unify Codebase ("Split Brain" Fix):** Create a shared `sage_core` package containing `ingest.py`, Qdrant connection logic, and embedding models. Import this in both `backend` and `mcp-server`. (Benefit: Eliminates duplicate logic and silent search consistency failures; Effort: L)
- **Enforce upload constraints:** max file size, allowed MIME types, ZIP entry limits; reject oversized/empty ingests. (Benefit: prevents resource exhaustion and archive bombs; Effort: M)

## P1 – High Impact
- **Implement Process-Based Workers:** Replace `threading.Thread` with `ProcessPoolExecutor` or a dedicated queue (RQ/Celery) for ingest tasks. (Benefit: Fixes GIL blocking where uploads starve API requests; Effort: M)
- **Durable Job State:** Move upload task tracking from in-memory `_upload_tasks` dict to Qdrant or Redis. (Benefit: Long-running uploads survive container restarts; Effort: S)
- **Sandbox heavy parsers:** Run Docling, python-docx, and openpyxl via worker containers or seccomp/AppArmor; add timeouts. (Benefit: reduces exploit/DoS surface; Effort: M)

## P2 – Medium Impact
- **Upgrade Embedding Model:** Switch from 2021-era `all-MiniLM-L6-v2` to `nomic-embed-text-v1.5` or `bge-m3`. (Benefit: Significant jump in retrieval relevance for technical docs; Effort: S)
- **Add Integration Tests:** Add tests for ingest pipeline, search filters, and MCP tools; add CI. (Benefit: cuts regression risk; Effort: M)
- **Improve Observability:** structured logs, metrics, readiness probes, and dependency lockfiles. (Benefit: better operability; Effort: S)

## P3 – Nice to Have
- **Add document pagination/streaming:** Support partial content retrieval for large files in get_document. (Benefit: avoids truncation and large responses; Effort: S)
- **Optional ColBERT rerank:** Provide as a service with feature flagging and timeouts. (Benefit: better relevance when needed; Effort: M)
- **Harden UI/UX:** better error surfacing, progress for background tasks, and cleanup of stale tasks. (Benefit: clearer user experience and fewer dangling tasks; Effort: S)

# Optional Strategic Improvements
- **Introduce a dedicated ingestion service:** (worker pool + message queue) to decouple user latency from document processing. Tradeoff: added infrastructure, but gains reliability and scale-out.
- **Consolidate backend and MCP into a single service:** Expose both HTTP and MCP transports from one FastAPI app sharing the core library. drastically reduces maintanence.
- **Add an API gateway:** (Traefik/Envoy) for TLS termination, rate limiting, and request size enforcement; slightly more ops overhead but significantly better security posture.
