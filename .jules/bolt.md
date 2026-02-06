## 2024-05-23 - FastAPI Blocking Event Loop
**Learning:** Using synchronous clients (like `qdrant_client`) inside `async def` FastAPI endpoints blocks the main event loop, serializing requests.
**Action:** Always use `def` (sync) endpoints for synchronous I/O operations to let FastAPI offload them to a thread pool. Use `asyncio.run()` if you need to call isolated async functions from within these threads.
