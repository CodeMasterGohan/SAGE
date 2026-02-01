## 2024-05-23 - Sync Client in Async Endpoints
**Learning:** Using synchronous clients (like `QdrantClient`) inside `async def` FastAPI endpoints blocks the main event loop, causing severe concurrency issues.
**Action:** Define such endpoints with `def` (sync) so FastAPI runs them in a thread pool, or migrate to async clients.
