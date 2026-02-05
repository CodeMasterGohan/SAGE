## 2024-05-23 - FastAPI Sync vs Async with Blocking Clients
**Learning:** Using `async def` for FastAPI endpoints that utilize synchronous clients (like `QdrantClient`) or CPU-bound tasks (like `fastembed`) blocks the main event loop, causing severe performance degradation under concurrent load.
**Action:** Always define endpoints using synchronous libraries as `def` (sync) functions so FastAPI runs them in a thread pool, unblocking the event loop. Verify library async support before using `async def`.
