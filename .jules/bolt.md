## 2026-01-25 - FastAPI Sync Blocking Anti-Pattern
**Learning:** The codebase extensively used `async def` for FastAPI endpoints that relied entirely on blocking synchronous operations (`QdrantClient`, `fastembed`). This caused the main event loop to freeze during requests, destroying concurrency.
**Action:** Always verify if database clients and heavy computation libraries are async-compatible. If they are synchronous, use `def` (sync) endpoints in FastAPI to leverage the threadpool, or wrap calls in `run_in_threadpool`.
