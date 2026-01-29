## 2024-05-23 - Qdrant Aggregation Optimization
**Learning:** Avoid using `client.scroll()` or full table scans for aggregation tasks (like listing unique values). Qdrant's `facet()` API is designed for this and is significantly faster, even if it requires N+1 queries (one per group) when the number of groups is small.
**Action:** When needing to list hierarchical metadata (e.g., Library -> Versions), prefer iterative `facet()` queries over scrolling the entire collection, especially if the top-level cardinality (Libraries) is low.
