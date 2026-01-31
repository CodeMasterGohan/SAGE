
import sys
import asyncio
from unittest.mock import MagicMock, patch

# Mock fastembed before importing server
sys.modules["fastembed"] = MagicMock()
sys.modules["fastembed.TextEmbedding"] = MagicMock()
sys.modules["fastembed.SparseTextEmbedding"] = MagicMock()
sys.modules["fastapi.staticfiles"] = MagicMock()

from qdrant_client.http import models
from dashboard.server import list_libraries, LibraryInfo

# Mock Qdrant types
Hit = MagicMock()
Hit.value = "lib1"
Hit.count = 10

def test_list_libraries_optimized():
    print("Testing optimized logic...")
    # Setup Mock Client
    client = MagicMock()

    # Hits for libraries
    lib_hit1 = MagicMock()
    lib_hit1.value = "lib1"
    lib_hit2 = MagicMock()
    lib_hit2.value = "lib2"

    # Hits for versions
    v1_hit = MagicMock()
    v1_hit.value = "v1.0"
    v2_hit = MagicMock()
    v2_hit.value = "v1.1"

    v3_hit = MagicMock()
    v3_hit.value = "v2.0"

    def facet_side_effect(collection_name, key, filter=None, limit=None, **kwargs):
        hits_mock = MagicMock()
        if key == "library":
            hits_mock.hits = [lib_hit1, lib_hit2]
            return hits_mock
        elif key == "version":
            # Inspect filter to decide what to return
            # filter is models.Filter
            # We can inspect the match value in the filter
            # filter.must[0].match.value

            # Since we are mocking, we assume the code constructs it correctly.
            # But let's verify we can extract it to ensure correct filtering.

            try:
                # Basic inspection if possible, or just fallback
                lib_val = filter.must[0].match.value
                if lib_val == "lib1":
                    hits_mock.hits = [v1_hit, v2_hit]
                elif lib_val == "lib2":
                    hits_mock.hits = [v3_hit]
                else:
                    hits_mock.hits = []
            except:
                # If structure is not what we expect (e.g. test setup issues), return empty
                hits_mock.hits = []

            return hits_mock
        return hits_mock

    client.facet.side_effect = facet_side_effect

    # Ensure scroll raises error if called
    client.scroll.side_effect = Exception("Scroll should NOT be called!")

    # Run the function
    # Note: It is now synchronous def, so we don't need asyncio.run
    # However, for backward compatibility if it were async, we could check.
    # But we explicitly changed it to sync.
    if asyncio.iscoroutinefunction(list_libraries):
        result = asyncio.run(list_libraries(client))
    else:
        result = list_libraries(client)

    # Verify results
    assert len(result) == 2
    lib1 = next(l for l in result if l.library == "lib1")
    lib2 = next(l for l in result if l.library == "lib2")

    assert "v1.0" in lib1.versions
    assert "v1.1" in lib1.versions
    assert "v2.0" in lib2.versions
    assert len(lib1.versions) == 2
    assert len(lib2.versions) == 1

    # Verify implementation details
    # client.scroll should NOT be called
    client.scroll.assert_not_called()

    # client.facet should be called 3 times (1 for libs + 2 for versions)
    assert client.facet.call_count == 3

    print("Optimization verification success!")

if __name__ == "__main__":
    try:
        test_list_libraries_optimized()
    except AssertionError as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
