## 2026-02-02 - Blocking Calls in Async Endpoints
**Learning:** Using `async def` for FastAPI endpoints that perform synchronous blocking I/O (like `QdrantClient` sync calls or CPU-bound `fastembed` generation) blocks the main asyncio event loop, causing severe concurrency issues.
**Action:** Define such endpoints as `def` (synchronous) so FastAPI runs them in a thread pool, keeping the main loop free for other requests.
