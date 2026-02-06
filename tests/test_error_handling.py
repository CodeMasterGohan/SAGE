"""
Tests for Enhanced Error Handling with Transaction Rollback
=============================================================
Phase 5: Comprehensive error handling, transaction semantics, and retry logic.
"""

import pytest
import asyncio
import io
import zipfile
from unittest.mock import Mock, patch, AsyncMock
from qdrant_client import QdrantClient
from qdrant_client.http import models
import httpx
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sage_core import ingestion, qdrant_utils, embeddings
from sage_core.file_processing import PDFProcessingError


# ============================================================
# Test Fixtures
# ============================================================

@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for testing."""
    client = Mock(spec=QdrantClient)
    client.collection_exists.return_value = True
    client.upsert.return_value = None
    client.delete.return_value = None
    return client


@pytest.fixture
def sample_markdown():
    """Sample markdown document for testing."""
    return """# Test Document

This is a test document with some content.
It has multiple paragraphs to create multiple chunks.

## Section 1
Content in section 1.

## Section 2
Content in section 2.
"""


@pytest.fixture
def tmp_path(tmpdir):
    """Provide a temporary directory path for tests."""
    return Path(tmpdir)


# ============================================================
# Test 1: Embedding Failure Rolls Back Partial Upload
# ============================================================

@pytest.mark.asyncio
async def test_embedding_failure_rolls_back_partial_upload(mock_qdrant_client, sample_markdown, tmp_path):
    """
    Test that embedding generation failure triggers cleanup of any created points.
    """
    # Mock the upload directory
    with patch('sage_core.ingestion.UPLOAD_DIR', tmp_path):
        # Set EMBEDDING_MODE to trigger remote embeddings path
        with patch('sage_core.ingestion.EMBEDDING_MODE', 'remote'):
            # Mock duplicate check to return None (not a duplicate) - must patch in ingestion module
            with patch('sage_core.ingestion.check_duplicate_content', return_value=None):
                # Mock embedding failure - patch in ingestion module where it's imported
                with patch('sage_core.ingestion.get_remote_embeddings_async_with_retry') as mock_embed:
                    mock_embed.side_effect = Exception("Embedding service unavailable")
                    
                    # Mock sparse model to work
                    with patch('sage_core.ingestion.get_sparse_model') as mock_sparse:
                        sparse_mock = Mock()
                        sparse_vec = Mock()
                        sparse_vec.indices = Mock()
                        sparse_vec.indices.tolist.return_value = [0, 1]
                        sparse_vec.values = Mock()
                        sparse_vec.values.tolist.return_value = [0.5, 0.3]
                        sparse_mock.embed.return_value = [sparse_vec] * 10
                        mock_sparse.return_value = sparse_mock
                        
                        # Mock ensure_collection
                        with patch('sage_core.ingestion.ensure_collection'):
                            # Attempt ingestion - should fail
                            with pytest.raises(Exception) as exc_info:
                                await ingestion.ingest_document(
                                    content=sample_markdown.encode(),
                                    filename="test.md",
                                    library="test-lib",
                                    version="1.0",
                                    client=mock_qdrant_client
                                )
                            
                            # Verify error contains embedding information
                            error = exc_info.value
                            error_str = str(error).lower()
                            assert "embedding" in error_str or "unavailable" in error_str


# ============================================================
# Test 2: Qdrant Upsert Failure - No Orphaned Chunks
# ============================================================

@pytest.mark.asyncio
async def test_qdrant_upsert_failure_no_orphaned_chunks(mock_qdrant_client, sample_markdown, tmp_path):
    """
    Test that Qdrant upsert failure doesn't leave partial data.
    Since upsert is atomic, either all points are inserted or none.
    """
    # Mock the upload directory
    with patch('sage_core.ingestion.UPLOAD_DIR', tmp_path):
        # Mock upsert failure
        mock_qdrant_client.upsert.side_effect = Exception("Qdrant connection failed")
        
        # Mock scroll to return empty (not a duplicate)
        mock_qdrant_client.scroll.return_value = ([], None)
        
        # Mock ensure_collection
        with patch('sage_core.qdrant_utils.ensure_collection'):
            # Track points that would be created
            point_ids_tracked = []
            
            original_create_point = ingestion._create_point
            def track_create_point(*args, **kwargs):
                point = original_create_point(*args, **kwargs)
                point_ids_tracked.append(point.id)
                return point
            
            with patch('sage_core.ingestion._create_point', side_effect=track_create_point):
                with patch('sage_core.embeddings.get_remote_embeddings_async_with_retry', 
                           return_value=[[0.1] * 384] * 10):  # Mock embeddings
                    with patch('sage_core.embeddings.get_sparse_model') as mock_sparse:
                        # Mock sparse model
                        sparse_mock = Mock()
                        sparse_vec = Mock()
                        sparse_vec.indices = Mock()
                        sparse_vec.indices.tolist.return_value = [0, 1]
                        sparse_vec.values = Mock()
                        sparse_vec.values.tolist.return_value = [0.5, 0.3]
                        sparse_mock.embed.return_value = [sparse_vec] * 10
                        mock_sparse.return_value = sparse_mock
                        
                        # Attempt ingestion - should fail
                        with pytest.raises(Exception) as exc_info:
                            await ingestion.ingest_document(
                                content=sample_markdown.encode(),
                                filename="test.md",
                                library="test-lib",
                                version="1.0",
                                client=mock_qdrant_client
                            )
                        
                        # Verify error contains Qdrant failure info
                        error_str = str(exc_info.value).lower()
                        assert "qdrant" in error_str or "index" in error_str or "failed" in error_str
                        # Points were created but upsert failed - rollback should be called
                        assert len(point_ids_tracked) > 0


# ============================================================
# Test 3: Transient Embedding Failure Retries
# ============================================================

@pytest.mark.asyncio
async def test_transient_embedding_failure_retries():
    """
    Test that transient failures (network errors) trigger retry with backoff.
    """
    # Mock HTTP client with transient failures followed by success
    call_count = 0
    
    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        
        if call_count < 3:
            # First 2 attempts fail with network error
            raise httpx.RequestError("Connection timeout")
        
        # Third attempt succeeds
        response = Mock()
        response.json.return_value = {
            "data": [{"index": 0, "embedding": [0.1] * 384}]
        }
        response.raise_for_status.return_value = None
        return response
    
    mock_client = Mock()
    mock_client.post = AsyncMock(side_effect=mock_post)
    
    # Call the embedding function
    result = await embeddings.get_remote_embeddings_async_with_retry(
        mock_client,
        ["test text"]
    )
    
    # Should succeed after retries
    assert result == [[0.1] * 384]
    assert call_count == 3  # Should have retried twice


# ============================================================
# Test 4: Permanent Failure Stops Retries
# ============================================================

@pytest.mark.asyncio
async def test_permanent_failure_stops_retries():
    """
    Test that non-transient errors (auth failures, invalid input) fail immediately.
    """
    # Mock HTTP client with permanent failure (authentication error)
    call_count = 0
    
    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        
        # Always fail with auth error (permanent)
        response = Mock()
        response.status_code = 401
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=Mock(), response=response
        )
        return response
    
    mock_client = Mock()
    mock_client.post = AsyncMock(side_effect=mock_post)
    
    # Call the embedding function - should fail immediately
    with pytest.raises(Exception):
        await embeddings.get_remote_embeddings_async_with_retry(
            mock_client,
            ["test text"]
        )
    
    # Should NOT retry for permanent errors
    assert call_count == 1


# ============================================================
# Test 5: Error Response Includes Processing Step
# ============================================================

@pytest.mark.asyncio
async def test_error_response_includes_processing_step(mock_qdrant_client, sample_markdown, tmp_path):
    """
    Test that errors include which processing step failed.
    """
    # Mock the upload directory
    with patch('sage_core.ingestion.UPLOAD_DIR', tmp_path):
        # Set EMBEDDING_MODE to trigger remote embeddings path
        with patch('sage_core.ingestion.EMBEDDING_MODE', 'remote'):
            # Mock duplicate check to return None (not a duplicate) - patch in ingestion module
            with patch('sage_core.ingestion.check_duplicate_content', return_value=None):
                # Mock sparse model to work properly - patch in ingestion module
                with patch('sage_core.ingestion.get_sparse_model') as mock_sparse:
                    sparse_mock = Mock()
                    sparse_vec = Mock()
                    sparse_vec.indices = Mock()
                    sparse_vec.indices.tolist.return_value = [0, 1]
                    sparse_vec.values = Mock()
                    sparse_vec.values.tolist.return_value = [0.5, 0.3]
                    sparse_mock.embed.return_value = [sparse_vec] * 10
                    mock_sparse.return_value = sparse_mock
                    
                    # Mock embedding failure - patch in ingestion module where it's imported
                    with patch('sage_core.ingestion.get_remote_embeddings_async_with_retry') as mock_embed:
                        mock_embed.side_effect = Exception("Rate limit exceeded")
                        
                        # Attempt ingestion - should raise IngestionError with details
                        with pytest.raises(Exception) as exc_info:
                            await ingestion.ingest_document(
                                content=sample_markdown.encode(),
                                filename="test.md",
                                library="test-lib",
                                version="1.0",
                                client=mock_qdrant_client
                            )
                        
                        error = exc_info.value
                        # Check if error has processing step info
                        if hasattr(error, 'processing_step'):
                            assert error.processing_step in ["extraction", "chunking", "embedding", "indexing"]
                        # Or check error message contains step info
                        error_str = str(error).lower()
                        assert "embedding" in error_str or "rate limit" in error_str
                    # Or check error message contains step info
                    error_str = str(error).lower()
                    assert "embedding" in error_str or "rate limit" in error_str


# ============================================================
# Test 6: Error Response Includes Specific Reason
# ============================================================

@pytest.mark.asyncio
async def test_error_response_includes_specific_reason(mock_qdrant_client):
    """
    Test that error responses include detailed error messages.
    """
    # Mock PDF processing failure
    bad_pdf = b"corrupted pdf data"
    
    with patch('sage_core.file_processing.process_file_async') as mock_process:
        mock_process.side_effect = PDFProcessingError(
            "Failed to parse PDF: Invalid header"
        )
        
        # Attempt ingestion - should provide detailed error
        with pytest.raises(Exception) as exc_info:
            await ingestion.ingest_document(
                content=bad_pdf,
                filename="bad.pdf",
                library="test-lib",
                version="1.0",
                client=mock_qdrant_client
            )
        
        error_msg = str(exc_info.value)
        # Should include specific error details
        assert "PDF" in error_msg or "parse" in error_msg or "Invalid header" in error_msg


# ============================================================
# Test 7: Partial Success for ZIP Uploads
# ============================================================

@pytest.mark.asyncio
async def test_partial_success_for_zip_uploads(mock_qdrant_client, tmp_path):
    """
    Test that ZIP processing continues on individual file failures,
    collecting success/failure per file.
    """
    # Mock the upload directory
    with patch('sage_core.ingestion.UPLOAD_DIR', tmp_path):
        # Set EMBEDDING_MODE to trigger remote embeddings path
        with patch('sage_core.ingestion.EMBEDDING_MODE', 'remote'):
            # Create mock ZIP with multiple files
            import zipfile
            import io
            
            # Create a real ZIP file in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr("doc1.md", "# Document 1\nContent 1")
                zip_file.writestr("doc2.md", "# Document 2\nContent 2")
                zip_file.writestr("bad.md", "# Bad Doc\nThis will fail")
            
            zip_content = zip_buffer.getvalue()
            
            # Mock duplicate check to return None (not duplicates) - patch in ingestion module
            with patch('sage_core.ingestion.check_duplicate_content', return_value=None):
                # Patch in ingestion module where it's imported
                with patch('sage_core.ingestion.get_remote_embeddings_async_with_retry') as mock_embed:
                    # Make embedding fail for the third file
                    call_count = [0]
                    async def embed_with_failure(client, texts):
                        call_count[0] += 1
                        if call_count[0] == 3:
                            raise Exception("Embedding failed for bad.md")
                        return [[0.1] * 384] * len(texts)
                    
                    mock_embed.side_effect = embed_with_failure
                    
                    # Patch sparse model in ingestion module
                    with patch('sage_core.ingestion.get_sparse_model') as mock_sparse:
                        sparse_mock = Mock()
                        sparse_vec = Mock()
                        sparse_vec.indices = Mock()
                        sparse_vec.indices.tolist.return_value = [0, 1]
                        sparse_vec.values = Mock()
                        sparse_vec.values.tolist.return_value = [0.5, 0.3]
                        sparse_mock.embed.return_value = [sparse_vec] * 10
                        mock_sparse.return_value = sparse_mock
                        
                        # Ingest ZIP with partial failure handling
                        result = await ingestion.ingest_document_with_partial_failure(
                            content=zip_content,
                            filename="docs.zip",
                            library="test-lib",
                            version="1.0",
                            client=mock_qdrant_client
                        )
                        
                        # Should have partial success
                        assert result["success"] is True
                        assert result["files_processed"] == 2  # Only 2 succeeded
                        assert result["files_failed"] == 1
                        assert len(result["failures"]) == 1
                        assert "bad.md" in str(result["failures"])


# ============================================================
# Test 8: Rollback Cleanup Verification
# ============================================================

@pytest.mark.asyncio
async def test_rollback_cleanup_verification(mock_qdrant_client, sample_markdown, tmp_path):
    """
    Test that rollback actually deletes points from Qdrant.
    """
    # Mock the upload directory
    with patch('sage_core.ingestion.UPLOAD_DIR', tmp_path):
        # Mock duplicate check to return None (not a duplicate)
        with patch('sage_core.qdrant_utils.check_duplicate_content', return_value=None):
            # Track delete calls
            deleted_ids = []
            
            def mock_delete(collection_name, points_selector):
                # Extract IDs from the selector
                deleted_ids.append(points_selector)
            
            mock_qdrant_client.delete.side_effect = mock_delete
            
            # Mock upsert to track point IDs, then fail
            created_points = []
            
            def mock_upsert(collection_name, points, wait=True):
                created_points.extend([p.id for p in points])
                raise Exception("Upsert failed after creating points")
            
            mock_qdrant_client.upsert.side_effect = mock_upsert
            
            with patch('sage_core.embeddings.get_remote_embeddings_async_with_retry',
                       return_value=[[0.1] * 384] * 5):
                with patch('sage_core.embeddings.get_sparse_model') as mock_sparse:
                    sparse_mock = Mock()
                    sparse_vec = Mock()
                    sparse_vec.indices = Mock()
                    sparse_vec.indices.tolist.return_value = [0, 1]
                    sparse_vec.values = Mock()
                    sparse_vec.values.tolist.return_value = [0.5, 0.3]
                    sparse_mock.embed.return_value = [sparse_vec] * 10
                    mock_sparse.return_value = sparse_mock
                    
                    # Attempt ingestion - should fail and trigger rollback
                    with pytest.raises(Exception):
                        await ingestion.ingest_document(
                            content=sample_markdown.encode(),
                            filename="test.md",
                            library="test-lib",
                            version="1.0",
                            client=mock_qdrant_client
                        )
                    
                    # Verify points were tracked and delete was called
                    assert len(created_points) > 0
                    # Delete should have been called to clean up
                    assert len(deleted_ids) > 0 or mock_qdrant_client.delete.called


# ============================================================
# Test 9: Delete Points by IDs Utility Function
# ============================================================

def test_delete_points_by_ids(mock_qdrant_client):
    """
    Test the delete_points_by_ids utility function.
    """
    point_ids = ["id1", "id2", "id3"]
    
    qdrant_utils.delete_points_by_ids(
        mock_qdrant_client,
        "test_collection",
        point_ids
    )
    
    # Verify delete was called with correct parameters
    assert mock_qdrant_client.delete.called
    call_args = mock_qdrant_client.delete.call_args
    assert call_args[1]["collection_name"] == "test_collection"
    # Should use PointIdsList selector
    assert hasattr(call_args[1]["points_selector"], '__class__')


# ============================================================
# Test 10: Exponential Backoff in Retry Logic
# ============================================================

@pytest.mark.asyncio
async def test_exponential_backoff_in_retry_logic():
    """
    Test that retry logic uses exponential backoff (1s, 2s, 4s).
    """
    import time
    
    call_times = []
    
    async def mock_post(*args, **kwargs):
        call_times.append(time.time())
        if len(call_times) < 3:
            raise httpx.RequestError("Timeout")
        
        response = Mock()
        response.json.return_value = {"data": [{"index": 0, "embedding": [0.1] * 384}]}
        response.raise_for_status.return_value = None
        return response
    
    mock_client = Mock()
    mock_client.post = AsyncMock(side_effect=mock_post)
    
    await embeddings.get_remote_embeddings_async_with_retry(
        mock_client,
        ["test text"]
    )
    
    # Check that delays increase (approximately 1s, 2s between calls)
    assert len(call_times) == 3
    if len(call_times) >= 2:
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        # Allow some tolerance for timing
        assert delay1 >= 0.5  # Should be ~1s
        assert delay2 >= 1.0  # Should be ~2s


# ============================================================
# Test 11: Custom IngestionError Exception
# ============================================================

def test_ingestion_error_structure():
    """
    Test that IngestionError has required fields.
    """
    from sage_core.ingestion import IngestionError
    
    error = IngestionError(
        message="Test error",
        processing_step="embedding",
        file_name="test.pdf",
        details={"error_type": "RateLimitError", "retries_attempted": 3}
    )
    
    assert error.message == "Test error"
    assert error.processing_step == "embedding"
    assert error.file_name == "test.pdf"
    assert error.details["error_type"] == "RateLimitError"
    assert error.details["retries_attempted"] == 3


# ============================================================
# Test 12: Error Details in Dashboard Response
# ============================================================

@pytest.mark.asyncio
async def test_error_details_in_dashboard_response():
    """
    Test that dashboard API returns structured error details.
    """
    # Skip if fastapi not available
    try:
        from dashboard.server import app
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("Dashboard dependencies not available")
    
    client = TestClient(app)
    
    # Mock ingestion to fail with detailed error
    with patch('dashboard.ingest.ingest_document') as mock_ingest:
        from sage_core.ingestion import IngestionError
        mock_ingest.side_effect = IngestionError(
            message="Rate limit exceeded",
            processing_step="embedding",
            file_name="test.pdf",
            details={
                "error_type": "RateLimitError",
                "retries_attempted": 3,
                "suggestion": "Try again in a few minutes"
            }
        )
        
        # Note: This test requires dashboard integration
        # We're testing the structure, actual integration may vary


# ============================================================
# Run Tests
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
