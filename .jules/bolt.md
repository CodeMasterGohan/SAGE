## 2024-05-23 - [Qdrant Large Collection Aggregation]
**Learning:** Using `client.scroll()` to aggregate unique values (like listing libraries) causes a full collection scan, transferring massive amounts of payload data. `client.facet()` is significantly more efficient for this purpose, even if it requires iterative queries (N+1) to drill down into sub-categories (like versions per library).
**Action:** Always prefer `client.facet()` over `scroll()` for unique value aggregation. For hierarchical data, use iterative facet queries with filters.
