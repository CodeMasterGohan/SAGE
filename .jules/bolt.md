## 2026-01-27 - FastAPI Synchronous Blocking
**Learning:** The `dashboard` service was using `async def` for endpoints that perform synchronous blocking operations (Qdrant client calls, CPU-bound embedding generation). This blocks the asyncio event loop, serializing requests and killing concurrency.
**Action:** When using synchronous clients (like `QdrantClient`) or heavy CPU tasks in FastAPI, use `def` endpoints instead of `async def` to leverage the thread pool, or use `run_in_executor` explicitly.
