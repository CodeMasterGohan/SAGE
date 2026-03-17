## 2024-05-15 - Offloading synchronous I/O and CPU-bound tasks
**Learning:** We need to use `asyncio.to_thread` or `loop.run_in_executor` for synchronous I/O (like writing to files) and CPU-bound operations (like running fastembed models) in async functions to avoid blocking the event loop.
**Action:** Identify and offload synchronous file I/O operations inside `dashboard/ingest.py`, `dashboard/server.py` and `refinery/main.py`
