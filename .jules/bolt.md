## 2025-01-26 - Async FastAPI and Synchronous Dependencies
**Learning:** Mixing `async def` endpoints with synchronous blocking operations (like CPU-bound embedding generation or synchronous database clients) blocks the main event loop, destroying concurrency. Using `def` for such endpoints allows FastAPI to run them in a thread pool, restoring concurrency.
**Action:** When using synchronous clients (like QdrantClient) or CPU-bound libraries (like fastembed) in FastAPI, define the path operation as `def` (sync) unless you are strictly using `await` for I/O.
