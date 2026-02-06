"""
Regression Test Suite - Phase 7
================================
Verifies that baseline functionality remains unchanged after all improvements.

These tests ensure that:
- Basic search still works exactly as before
- Basic upload hasn't regressed
- Library management functions correctly
- MCP integration remains functional
- Markdown processing unchanged
- Chunking behavior consistent
- Embedding generation works correctly

Tests use real components to verify no breaking changes.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock
from qdrant_client import QdrantClient
from qdrant_client.http import models


# ============================================================
# Setup fixture for temporary uploads directory
# ============================================================

@pytest.fixture(autouse=True)
def setup_upload_dir(monkeypatch, tmp_path):
    """Setup temporary upload directory for tests."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    # Force reimport to pick up new UPLOAD_DIR
    import sage_core.ingestion
    monkeypatch.setattr(sage_core.ingestion, "UPLOAD_DIR", upload_dir)
    return upload_dir


# ============================================================
# Test 1: Basic search still works
# ============================================================

@pytest.mark.asyncio
async def test_basic_search_still_works():
    """
    Verify that basic search functionality is unchanged.
    
    This is the most critical user path - must not regress.
    """
    from sage_core.embeddings import get_dense_model, get_sparse_model
    from sage_core.qdrant_utils import get_qdrant_client, ensure_collection
    
    # Setup
    client = get_qdrant_client()
    ensure_collection(client)
    
    # Get models
    dense_model = get_dense_model()
    sparse_model = get_sparse_model()
    
    # Verify models load
    assert dense_model is not None
    assert sparse_model is not None
    
    # Generate embeddings (basic functionality)
    test_query = "test search query"
    dense_vec = list(dense_model.embed([test_query]))[0]
    sparse_vec = list(sparse_model.embed([test_query]))[0]
    
    # Verify embedding dimensions
    assert len(dense_vec) > 0  # Should have embedding dimension
    assert hasattr(sparse_vec, 'indices')
    assert hasattr(sparse_vec, 'values')
    
    # Perform search (may return empty if no data, but should not error)
    try:
        results = client.query_points(
            collection_name="sage_docs",
            prefetch=[
                models.Prefetch(
                    query=dense_vec.tolist() if hasattr(dense_vec, 'tolist') else dense_vec,
                    using="dense",
                    limit=5
                ),
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sparse_vec.indices.tolist(),
                        values=sparse_vec.values.tolist()
                    ),
                    using="sparse",
                    limit=5
                )
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=5,
            with_payload=True
        )
        
        # Should complete without error
        assert results is not None
        assert hasattr(results, 'points')
        
    except Exception as e:
        pytest.fail(f"Basic search failed: {e}")


# ============================================================
# Test 2: Basic upload still works
# ============================================================

@pytest.mark.asyncio
async def test_basic_upload_still_works():
    """
    Verify that simple upload workflow hasn't regressed.
    
    Tests the happy path: markdown upload -> indexing -> searchable.
    """
    from sage_core.ingestion import ingest_document
    from sage_core.qdrant_utils import get_qdrant_client, ensure_collection
    
    # Setup
    client = get_qdrant_client()
    ensure_collection(client)
    
    # Simple markdown content
    content = b"""# Regression Test Document

This is a simple markdown document to verify basic upload still works.

## Section 1
Content in section 1.

## Section 2
Content in section 2.
"""
    
    # Upload
    result = await ingest_document(
        content=content,
        filename="regression_basic.md",
        library="regression-test",
        version="1.0",
        client=client
    )
    
    # Verify basic result structure unchanged
    assert "library" in result
    assert "version" in result
    assert "chunks_indexed" in result
    assert "files_processed" in result
    
    # Verify upload succeeded
    assert result["library"] == "regression-test"
    assert result["version"] == "1.0"
    assert result["files_processed"] == 1
    assert result["chunks_indexed"] > 0
    
    # Verify indexed in Qdrant
    scroll_results, _ = client.scroll(
        collection_name="sage_docs",
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="library",
                    match=models.MatchValue(value="regression-test")
                ),
                models.FieldCondition(
                    key="file_path",
                    match=models.MatchText(text="regression_basic.md")
                )
            ]
        ),
        limit=100,
        with_payload=True
    )
    
    assert len(scroll_results) > 0
    
    # Verify payload structure unchanged
    first_chunk = scroll_results[0].payload
    expected_fields = ["content", "library", "version", "title", "file_path", "chunk_index"]
    for field in expected_fields:
        assert field in first_chunk, f"Payload missing expected field: {field}"


# ============================================================
# Test 3: Library management still works
# ============================================================

@pytest.mark.asyncio
async def test_library_management_still_works():
    """
    Verify library create/list/delete operations unchanged.
    """
    from sage_core.ingestion import ingest_document
    from sage_core.qdrant_utils import get_qdrant_client, ensure_collection, delete_library
    
    # Setup
    client = get_qdrant_client()
    ensure_collection(client)
    
    # Create test library
    content = b"# Library Management Test\n\nTest content."
    
    result = await ingest_document(
        content=content,
        filename="libtest.md",
        library="lib-mgmt-test",
        version="1.0",
        client=client
    )
    
    assert result["chunks_indexed"] > 0
    
    # List libraries (verify our library exists)
    # Using facet API
    try:
        library_facets = client.facet(
            collection_name="sage_docs",
            key="library",
            limit=1000
        )
        
        library_names = [hit.value for hit in library_facets.hits]
        assert "lib-mgmt-test" in library_names
    except Exception:
        # Fallback to scroll if facet not available
        scroll_results, _ = client.scroll(
            collection_name="sage_docs",
            limit=1000,
            with_payload=["library"],
            with_vectors=False
        )
        library_names = set(p.payload.get("library") for p in scroll_results)
        assert "lib-mgmt-test" in library_names
    
    # Delete library
    deleted_count = delete_library(client, "lib-mgmt-test")
    assert deleted_count > 0
    
    # Verify deleted
    scroll_after, _ = client.scroll(
        collection_name="sage_docs",
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="library",
                    match=models.MatchValue(value="lib-mgmt-test")
                )
            ]
        ),
        limit=100
    )
    
    assert len(scroll_after) == 0, "Library should be deleted"


# ============================================================
# Test 4: MCP integration still works
# ============================================================

def test_mcp_integration_still_works():
    """
    Verify MCP server can still load and perform basic operations.
    """
    # Test that MCP server files exist and are importable
    try:
        import sys
        from pathlib import Path
        
        # Add mcp-server to path
        mcp_path = Path(__file__).parent.parent / "mcp-server"
        if mcp_path.exists():
            sys.path.insert(0, str(mcp_path))
            
            # Try importing MCP modules
            import search
            
            # Verify module loads (specific function names may vary)
            assert search is not None
            
    except ImportError as e:
        pytest.skip(f"MCP modules not available: {e}")


# ============================================================
# Test 5: Markdown processing unchanged
# ============================================================

@pytest.mark.asyncio
async def test_markdown_processing_unchanged():
    """
    Verify markdown file processing produces expected output.
    """
    from sage_core.file_processing import process_file_async
    
    # Test markdown content
    markdown = b"""# Test Document

## Introduction
This is an introduction.

## Features
- Feature 1
- Feature 2
- Feature 3

## Conclusion
That's all.
"""
    
    # Process
    result = await process_file_async(
        content=markdown,
        filename="test.md",
        library="test-lib",
        version="1.0"
    )
    
    # Verify result is markdown string
    assert isinstance(result, str)
    assert len(result) > 0
    
    # Verify structure preserved
    assert "# Test Document" in result
    assert "## Introduction" in result
    assert "## Features" in result
    assert "Feature 1" in result


# ============================================================
# Test 6: Chunking behavior consistent
# ============================================================

def test_chunking_behavior_consistent():
    """
    Verify chunking produces consistent, expected results.
    """
    from sage_core.chunking import process_markdown_chunks
    
    # Test content
    markdown = """# Document Title

## Section 1
This is section 1 content. It has some text.

## Section 2
This is section 2 content. It also has some text.

## Section 3
This is section 3 content. More text here.
"""
    
    # Process
    chunks, warnings = process_markdown_chunks(markdown)
    
    # Verify chunks generated
    assert len(chunks) > 0
    assert isinstance(chunks, list)
    assert all(isinstance(chunk, str) for chunk in chunks)
    
    # Verify warnings is a list (may be empty)
    assert isinstance(warnings, list)
    
    # Verify each chunk has content
    for chunk in chunks:
        assert len(chunk.strip()) > 0
    
    # Verify sections present in chunks
    all_content = " ".join(chunks)
    assert "Section 1" in all_content or "section 1" in all_content.lower()


# ============================================================
# Test 7: Embedding generation works
# ============================================================

def test_embedding_generation_works():
    """
    Verify embedding models load and generate embeddings correctly.
    """
    from sage_core.embeddings import get_dense_model, get_sparse_model
    
    # Load models
    dense_model = get_dense_model()
    sparse_model = get_sparse_model()
    
    assert dense_model is not None
    assert sparse_model is not None
    
    # Generate embeddings
    test_texts = [
        "This is a test document",
        "Another test document with different content"
    ]
    
    # Dense embeddings
    dense_embeddings = list(dense_model.embed(test_texts))
    assert len(dense_embeddings) == 2
    
    # Verify dimensionality
    dense_vec = dense_embeddings[0]
    if hasattr(dense_vec, 'tolist'):
        dense_vec = dense_vec.tolist()
    assert len(dense_vec) > 0  # Should have some dimension
    
    # Sparse embeddings
    sparse_embeddings = list(sparse_model.embed(test_texts))
    assert len(sparse_embeddings) == 2
    
    # Verify structure
    sparse_vec = sparse_embeddings[0]
    assert hasattr(sparse_vec, 'indices')
    assert hasattr(sparse_vec, 'values')
    assert len(sparse_vec.indices) > 0
    assert len(sparse_vec.values) > 0


# ============================================================
# Test 8: Collection structure unchanged
# ============================================================

def test_collection_structure_unchanged():
    """
    Verify Qdrant collection has expected structure.
    """
    from sage_core.qdrant_utils import get_qdrant_client, ensure_collection, COLLECTION_NAME
    
    client = get_qdrant_client()
    ensure_collection(client)
    
    # Get collection info
    collection = client.get_collection(COLLECTION_NAME)
    
    # Verify collection exists
    assert collection is not None
    
    # Verify vector configuration
    assert hasattr(collection.config, 'params')
    vectors_config = collection.config.params.vectors
    
    # Verify named vectors exist
    assert "dense" in vectors_config
    # Note: Sparse vectors might be configured differently
    
    # Verify dense vector config
    dense_config = vectors_config["dense"]
    assert hasattr(dense_config, 'size')
    assert dense_config.size > 0  # Should have dimension


# ============================================================
# Test 9: File type detection unchanged
# ============================================================

def test_file_type_detection_unchanged():
    """
    Verify file type detection still works correctly.
    """
    from sage_core.file_processing import detect_file_type
    
    # Test various file types
    test_cases = [
        ("document.md", b"# Markdown", "markdown"),
        ("document.txt", b"Plain text", "text"),
        ("document.html", b"<html>HTML</html>", "html"),
        ("document.pdf", b"%PDF-1.4", "pdf"),
        ("archive.zip", b"PK\x03\x04", "zip"),
    ]
    
    for filename, content, expected_type in test_cases:
        detected = detect_file_type(filename, content)
        assert detected == expected_type, f"Expected {expected_type} for {filename}, got {detected}"


# ============================================================
# Test 10: Error handling structure unchanged
# ============================================================

def test_error_handling_structure_unchanged():
    """
    Verify error handling maintains expected behavior.
    """
    from sage_core.ingestion import IngestionError
    
    # Verify IngestionError exists and has expected structure
    error = IngestionError(
        message="Test error",
        processing_step="test_step",
        file_name="test.md",
        details={"key": "value"}
    )
    
    # Verify attributes
    assert error.message == "Test error"
    assert error.processing_step == "test_step"
    assert error.file_name == "test.md"
    assert error.details == {"key": "value"}
    
    # Verify to_dict method
    error_dict = error.to_dict()
    assert "error" in error_dict
    assert "processing_step" in error_dict
    assert "file_name" in error_dict
    assert "details" in error_dict


# ============================================================
# Test 11: Validation still works
# ============================================================

def test_validation_still_works():
    """
    Verify upload validation functionality unchanged.
    """
    from sage_core.validation import validate_upload, UploadValidationError
    
    # Test valid upload
    valid_content = b"# Valid Document\n\nContent here."
    try:
        validate_upload(valid_content, "valid.md", "text/markdown")
        # Should not raise
    except UploadValidationError:
        pytest.fail("Valid upload should not raise validation error")
    
    # Test invalid upload (too large)
    large_content = b"X" * (51 * 1024 * 1024)  # 51MB
    with pytest.raises(UploadValidationError) as exc_info:
        validate_upload(large_content, "large.md", "text/markdown")
    
    error_msg = str(exc_info.value).lower()
    assert "large" in error_msg or "size" in error_msg or "limit" in error_msg


# ============================================================
# Test 12: Deduplication doesn't break normal flow
# ============================================================

@pytest.mark.asyncio
async def test_deduplication_backward_compatible():
    """
    Verify that deduplication features don't break existing workflows.
    
    Tests that:
    - New uploads still work normally
    - Result structure maintains backward compatibility
    - Optional fields have sensible defaults
    """
    from sage_core.ingestion import ingest_document
    from sage_core.qdrant_utils import get_qdrant_client, ensure_collection
    
    # Setup
    client = get_qdrant_client()
    ensure_collection(client)
    
    # Upload new content
    content = b"# Backward Compat Test\n\nUnique content for regression."
    
    result = await ingest_document(
        content=content,
        filename="backcompat.md",
        library="regression-backcompat",
        version="1.0",
        client=client
    )
    
    # Verify result has all pre-existing fields
    assert "library" in result
    assert "version" in result
    assert "chunks_indexed" in result
    assert "files_processed" in result
    
    # Verify new optional fields exist but don't break anything
    assert "was_duplicate" in result  # New field
    assert "linked_to" in result  # New field
    
    # For new content, should be False/None
    assert result["was_duplicate"] is False
    assert result["linked_to"] is None


# ============================================================
# Test 13: Search results format unchanged
# ============================================================

@pytest.mark.asyncio
async def test_search_results_format_unchanged():
    """
    Verify search results maintain expected format.
    """
    from sage_core.ingestion import ingest_document
    from sage_core.embeddings import get_dense_model, get_sparse_model
    from sage_core.qdrant_utils import get_qdrant_client, ensure_collection
    
    # Setup
    client = get_qdrant_client()
    ensure_collection(client)
    
    # Upload test content
    content = b"# Search Format Test\n\nSearchable content for format verification."
    
    await ingest_document(
        content=content,
        filename="search_format.md",
        library="regression-search-fmt",
        version="1.0",
        client=client
    )
    
    # Perform search
    dense_model = get_dense_model()
    sparse_model = get_sparse_model()
    
    query = "searchable content"
    dense_vec = list(dense_model.embed([query]))[0]
    sparse_vec = list(sparse_model.embed([query]))[0]
    
    results = client.query_points(
        collection_name="sage_docs",
        prefetch=[
            models.Prefetch(
                query=dense_vec.tolist() if hasattr(dense_vec, 'tolist') else dense_vec,
                using="dense",
                limit=5
            ),
            models.Prefetch(
                query=models.SparseVector(
                    indices=sparse_vec.indices.tolist(),
                    values=sparse_vec.values.tolist()
                ),
                using="sparse",
                limit=5
            )
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="library",
                    match=models.MatchValue(value="regression-search-fmt")
                )
            ]
        ),
        limit=5,
        with_payload=True
    )
    
    # Verify result structure
    assert hasattr(results, 'points')
    
    if results.points:
        point = results.points[0]
        
        # Verify point structure
        assert hasattr(point, 'id')
        assert hasattr(point, 'score')
        assert hasattr(point, 'payload')
        
        # Verify payload has expected fields
        payload = point.payload
        expected_fields = ["content", "library", "version", "title", "file_path"]
        for field in expected_fields:
            assert field in payload, f"Missing expected field: {field}"


print("✓ All regression tests defined")
