# Bolt's Journal - SAGE Codebase

## 2026-01-19 - N+1 Facet Query Pattern Identified

**Learning:** The `list_libraries()` and `resolve_library()` endpoints both use an N+1 pattern where version facets are fetched in a loop for each library. Qdrant's facet API only supports filtering on payloads, not batching across multiple filter values. The optimization approach is to fetch ALL library+version combinations in a SINGLE facet call without filtering, then group client-side.

**Action:** Instead of querying versions per-library, fetch a combined facet or use a single scroll/count approach. The most efficient pattern is to get library facets first, then get ALL versions in ONE call and group by library client-side using a Map/dict.
