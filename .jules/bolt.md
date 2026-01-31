## 2026-01-31 - Async/Sync Mismatch in FastAPI
**Learning:** The `dashboard` service uses synchronous `QdrantClient` and `fastembed` models. Defining FastAPI endpoints as `async def` causes these synchronous operations to block the main event loop, severely degrading concurrency.
**Action:** Ensure all endpoints using synchronous clients/models are defined as `def` (synchronous) so FastAPI runs them in a thread pool.

## 2026-01-31 - Qdrant Aggregation Strategy
**Learning:** Using `client.scroll()` to aggregate unique values (like libraries/versions) scales linearly with collection size (O(N)), causing timeouts on large datasets.
**Action:** Use `client.facet()` iteratively (O(L) where L is number of unique values) instead of scanning the full collection.
