
import sys
import os
from unittest.mock import MagicMock, patch
import pytest

# Add dashboard to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock qdrant_client and fastembed BEFORE importing server
sys.modules['qdrant_client'] = MagicMock()
sys.modules['qdrant_client.http'] = MagicMock()
sys.modules['fastembed'] = MagicMock()
sys.modules['ingest'] = MagicMock()

from server import list_libraries, LibraryInfo

@pytest.mark.asyncio
async def test_list_libraries_performance():
    # Setup Mock Client
    client = MagicMock()

    # Mock facet for libraries
    library_hit1 = MagicMock()
    library_hit1.value = "lib1"
    library_hit2 = MagicMock()
    library_hit2.value = "lib2"

    # Facet response structure
    facet_resp_libs = MagicMock()
    facet_resp_libs.hits = [library_hit1, library_hit2]

    facet_resp_versions = MagicMock()
    facet_resp_versions.hits = [] # Just to pass the check

    # Mock facet calls
    def facet_side_effect(collection_name, key, limit=None, filter=None):
        if key == "library":
            return facet_resp_libs
        if key == "version":
            return facet_resp_versions
        return MagicMock()

    client.facet.side_effect = facet_side_effect

    # Mock scroll for library-version mapping
    # We want to simulate a large DB where we have to scroll many times
    # Let's say we have 5000 points, limit is 2000. So 3 calls.

    points = []
    for i in range(5000):
        p = MagicMock()
        p.payload = {"library": "lib1", "version": "v1"}
        points.append(p)

    # Scroll side effect
    def scroll_side_effect(collection_name, limit=None, offset=None, with_payload=None, with_vectors=None, scroll_filter=None):
        start = 0 if offset is None else int(offset)
        end = start + limit
        batch = points[start:end]
        next_offset = end if end < len(points) else None
        return batch, next_offset

    client.scroll.side_effect = scroll_side_effect

    # Run the function
    result = await list_libraries(client)

    # Analyze calls
    print(f"\nScroll calls: {client.scroll.call_count}")
    print(f"Facet calls: {client.facet.call_count}")

    # Assertions for OPTIMIZED behavior
    # It calls facet for libs (1) + facet for versions per lib (2) = 3 calls
    # It calls scroll 0 times (replaced by facet queries)
    assert client.facet.call_count == 3
    assert client.scroll.call_count == 0

    # Check result correctness
    assert len(result) == 2

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_list_libraries_performance())
