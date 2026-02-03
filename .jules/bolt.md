## 2024-05-22 - [Qdrant Facet vs Scroll]
**Learning:** Using `client.scroll` to find unique values (like libraries/versions) scales linearly with collection size (O(N)). Replacing it with iterative `client.facet` queries (O(NumGroups)) is orders of magnitude faster for large datasets, even with the N+1 query overhead.
**Action:** Always prefer `client.facet()` for aggregation tasks in Qdrant. Avoid `scroll` for metadata discovery.

## 2024-05-22 - [FastAPI Async Anti-Pattern]
**Learning:** The `dashboard` service uses `async def` endpoints with synchronous `QdrantClient`. This blocks the main event loop during database operations.
**Action:** Future optimizations should convert these to `def` (sync) endpoints to leverage FastAPI's thread pool, or switch to `AsyncQdrantClient`.
