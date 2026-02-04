# Bolt's Performance Journal

This journal records critical performance learnings, bottlenecks, and optimization outcomes.

## 2024-05-23 - [Initial Setup]
**Learning:** Performance journal established.
**Action:** Consult this journal before starting performance tasks.

## 2024-05-23 - [FastAPI Blocking Event Loop]
**Learning:** `async def` endpoints calling synchronous blocking functions (like `QdrantClient` sync methods or `fastembed` model inference) block the main asyncio event loop, causing requests to be processed sequentially.
**Action:** Use `def` for endpoints performing blocking CPU or I/O operations to leverage FastAPI's thread pool, or use asynchronous clients/executors.
