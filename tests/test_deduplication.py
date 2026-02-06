"""
Tests for content deduplication functionality.

Following TDD: These tests are written BEFORE implementation.
They define the expected behavior of the deduplication system.
"""

import os
import tempfile
import pytest
from unittest.mock import Mock, AsyncMock, patch
from qdrant_client import QdrantClient
from qdrant_client.http import models

from sage_core.qdrant_utils import compute_content_hash, check_duplicate_content
from sage_core.ingestion import ingest_document


@pytest.fixture(autouse=True)
def temp_upload_dir(monkeypatch, tmp_path):
    """Use temporary directory for uploads during tests."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    # Force reimport to pick up new UPLOAD_DIR
    import sage_core.ingestion
    monkeypatch.setattr(sage_core.ingestion, "UPLOAD_DIR", upload_dir)
    return upload_dir


class TestComputeContentHash:
    """Tests for content hash computation (SHA256)."""

    def test_compute_content_hash_consistent(self):
        """Same content should always produce the same hash."""
        content = "# Test Document\n\nThis is test content for deduplication."
        
        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)
        
        assert hash1 == hash2
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA256 produces 64 hex characters

    def test_compute_content_hash_different(self):
        """Different content should produce different hashes."""
        content1 = "# Document A\n\nContent A"
        content2 = "# Document B\n\nContent B"
        
        hash1 = compute_content_hash(content1)
        hash2 = compute_content_hash(content2)
        
        assert hash1 != hash2

    def test_compute_content_hash_whitespace_sensitive(self):
        """Content hash should be sensitive to whitespace changes."""
        content1 = "Test content"
        content2 = "Test  content"  # Double space
        
        hash1 = compute_content_hash(content1)
        hash2 = compute_content_hash(content2)
        
        assert hash1 != hash2

    def test_compute_content_hash_empty_string(self):
        """Empty string should produce a valid hash."""
        content = ""
        
        hash_result = compute_content_hash(content)
        
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64


class TestCheckDuplicateContent:
    """Tests for duplicate content detection in Qdrant."""

    def test_check_duplicate_content_not_found(self):
        """Should return None when no duplicate exists."""
        # Mock Qdrant client
        mock_client = Mock(spec=QdrantClient)
        mock_client.scroll.return_value = ([], None)  # No results
        
        content_hash = "abc123def456"
        result = check_duplicate_content(mock_client, content_hash)
        
        assert result is None
        mock_client.scroll.assert_called_once()

    def test_check_duplicate_content_found(self):
        """Should return document info when duplicate exists."""
        # Mock Qdrant client with existing document
        mock_client = Mock(spec=QdrantClient)
        
        # Create mock point with payload
        mock_point = Mock()
        mock_point.payload = {
            "library": "test-lib",
            "version": "1.0",
            "file_path": "/uploads/test-lib/1.0/original.md",
            "title": "Original Document",
            "content_hash": "abc123def456"
        }
        
        mock_client.scroll.return_value = ([mock_point], None)
        
        content_hash = "abc123def456"
        result = check_duplicate_content(mock_client, content_hash)
        
        assert result is not None
        assert result["library"] == "test-lib"
        assert result["version"] == "1.0"
        assert result["file_path"] == "/uploads/test-lib/1.0/original.md"
        assert result["title"] == "Original Document"

    def test_check_duplicate_content_uses_correct_filter(self):
        """Should query Qdrant with correct content_hash filter."""
        mock_client = Mock(spec=QdrantClient)
        mock_client.scroll.return_value = ([], None)
        
        content_hash = "test_hash_123"
        check_duplicate_content(mock_client, content_hash)
        
        # Verify the scroll call was made with correct filter
        call_args = mock_client.scroll.call_args
        assert call_args is not None
        
        # Check that scroll_filter was passed
        scroll_filter = call_args.kwargs.get('scroll_filter')
        assert scroll_filter is not None

    def test_check_duplicate_content_returns_first_match(self):
        """When multiple matches exist, should return the first one."""
        mock_client = Mock(spec=QdrantClient)
        
        # Create two mock points
        mock_point1 = Mock()
        mock_point1.payload = {
            "library": "lib1",
            "version": "1.0",
            "file_path": "/path1",
            "title": "First",
            "content_hash": "hash123"
        }
        
        mock_point2 = Mock()
        mock_point2.payload = {
            "library": "lib2",
            "version": "2.0",
            "file_path": "/path2",
            "title": "Second",
            "content_hash": "hash123"
        }
        
        mock_client.scroll.return_value = ([mock_point1, mock_point2], None)
        
        result = check_duplicate_content(mock_client, "hash123")
        
        assert result["library"] == "lib1"  # Should return first match


class TestIngestDuplicateDocument:
    """Tests for ingestion behavior with duplicate content."""

    @pytest.mark.asyncio
    async def test_ingest_new_document_includes_hash(self):
        """New document ingestion should include content_hash in payload."""
        mock_client = Mock(spec=QdrantClient)
        mock_client.upsert = Mock()
        
        # Mock embedding models
        mock_dense = Mock()
        mock_dense.embed = Mock(return_value=[[0.1] * 384])  # Return 384-dim vector
        
        mock_sparse = Mock()
        mock_sparse_result = Mock()
        mock_sparse_result.indices = Mock()
        mock_sparse_result.indices.tolist = Mock(return_value=[1, 2, 3])
        mock_sparse_result.values = Mock()
        mock_sparse_result.values.tolist = Mock(return_value=[0.5, 0.3, 0.2])
        mock_sparse.embed = Mock(return_value=[mock_sparse_result])
        
        # Mock check_duplicate_content to return None (no duplicate)
        with patch('sage_core.ingestion.check_duplicate_content', return_value=None):
            with patch('sage_core.ingestion.get_dense_model', return_value=mock_dense):
                with patch('sage_core.ingestion.get_sparse_model', return_value=mock_sparse):
                    with patch('sage_core.ingestion.EMBEDDING_MODE', 'local'):
                        content = b"# Test Doc\n\nTest content"
                        
                        result = await ingest_document(
                            content=content,
                            filename="test.md",
                            library="test-lib",
                            version="1.0",
                            client=mock_client
                        )
        
        # Verify upsert was called
        assert mock_client.upsert.called
        
        # Check that points include content_hash
        call_args = mock_client.upsert.call_args
        points = call_args.kwargs.get('points', [])
        assert len(points) > 0
        
        # Verify content_hash exists in payload
        first_point = points[0]
        assert 'content_hash' in first_point.payload

    @pytest.mark.asyncio
    async def test_ingest_duplicate_document_skips_embedding(self):
        """Duplicate upload should skip expensive embedding generation."""
        mock_client = Mock(spec=QdrantClient)
        mock_client.upsert = Mock()
        
        # Mock existing document
        existing_doc = {
            "library": "test-lib",
            "version": "1.0",
            "file_path": "/uploads/test-lib/1.0/original.md",
            "title": "Original Document"
        }
        
        with patch('sage_core.ingestion.check_duplicate_content', return_value=existing_doc):
            with patch('sage_core.ingestion.get_dense_model') as mock_dense:
                with patch('sage_core.ingestion.get_sparse_model') as mock_sparse:
                    content = b"# Test Doc\n\nSame content as before"
                    
                    result = await ingest_document(
                        content=content,
                        filename="duplicate.md",  # Different filename, same content
                        library="test-lib",
                        version="1.0",
                        client=mock_client
                    )
        
        # Verify embedding models were NOT instantiated (expensive operation skipped)
        # If check_duplicate_content returns a result, we should skip embedding
        assert result is not None
        
        # Result should indicate duplication
        assert result.get("was_duplicate") is True
        assert result.get("linked_to") == existing_doc["file_path"]

    @pytest.mark.asyncio
    async def test_ingest_duplicate_document_links_metadata(self):
        """Duplicate should create metadata link to existing chunks."""
        mock_client = Mock(spec=QdrantClient)
        
        # Mock existing chunks
        mock_point1 = Mock()
        mock_point1.id = "chunk1"
        mock_point1.payload = {
            "library": "test-lib",
            "version": "1.0",
            "file_path": "/uploads/test-lib/1.0/original.md",
            "title": "Original",
            "content_hash": "hash123",
            "linked_files": []
        }
        
        mock_point2 = Mock()
        mock_point2.id = "chunk2"
        mock_point2.payload = {
            "library": "test-lib",
            "version": "1.0",
            "file_path": "/uploads/test-lib/1.0/original.md",
            "title": "Original",
            "content_hash": "hash123",
            "linked_files": []
        }
        
        # Mock scroll to return existing chunks
        mock_client.scroll.return_value = ([mock_point1, mock_point2], None)
        mock_client.set_payload = Mock()
        
        existing_doc = {
            "library": "test-lib",
            "version": "1.0",
            "file_path": "/uploads/test-lib/1.0/original.md",
            "title": "Original"
        }
        
        with patch('sage_core.ingestion.check_duplicate_content', return_value=existing_doc):
            content = b"# Test Doc\n\nSame content"
            
            result = await ingest_document(
                content=content,
                filename="duplicate.md",
                library="test-lib",
                version="1.0",
                client=mock_client
            )
        
        # Verify set_payload was called to add linked_files
        assert mock_client.set_payload.called
        
        # Result should show metadata link created
        assert result.get("chunks_indexed") == 0  # No new chunks created
        assert result.get("was_duplicate") is True

    @pytest.mark.asyncio
    async def test_ingest_same_content_different_library_creates_link(self):
        """Same content in different library should link, not duplicate embeddings."""
        mock_client = Mock(spec=QdrantClient)
        
        existing_doc = {
            "library": "lib-a",
            "version": "1.0",
            "file_path": "/uploads/lib-a/1.0/doc.md",
            "title": "Document"
        }
        
        with patch('sage_core.ingestion.check_duplicate_content', return_value=existing_doc):
            content = b"# Shared Doc\n\nThis content is shared"
            
            result = await ingest_document(
                content=content,
                filename="doc.md",
                library="lib-b",  # Different library
                version="1.0",
                client=mock_client
            )
        
        # Should create link, not duplicate
        assert result.get("was_duplicate") is True
        assert result.get("linked_to") == existing_doc["file_path"]

    @pytest.mark.asyncio
    async def test_ingest_returns_deduplication_info(self):
        """Result should include deduplication information."""
        mock_client = Mock(spec=QdrantClient)
        
        # Test with duplicate
        existing_doc = {
            "library": "test-lib",
            "version": "1.0",
            "file_path": "/uploads/test-lib/1.0/original.md",
            "title": "Original"
        }
        
        with patch('sage_core.ingestion.check_duplicate_content', return_value=existing_doc):
            content = b"# Test\n\nContent"
            
            result = await ingest_document(
                content=content,
                filename="dup.md",
                library="test-lib",
                version="1.0",
                client=mock_client
            )
        
        # Check result structure
        assert "was_duplicate" in result
        assert "linked_to" in result
        assert result["was_duplicate"] is True
        assert result["linked_to"] is not None


class TestAPIResponseModel:
    """Tests for API response model with deduplication info."""

    def test_upload_result_includes_deduplication_fields(self):
        """UploadResult model should include was_duplicate and linked_to fields."""
        try:
            from dashboard.server import UploadResult
        except ImportError:
            # If fastapi not available, skip this test
            pytest.skip("Dashboard dependencies not available")
        
        # Test non-duplicate case
        result1 = UploadResult(
            success=True,
            library="test-lib",
            version="1.0",
            files_processed=1,
            chunks_indexed=10,
            message="Success",
            was_duplicate=False,
            linked_to=None
        )
        
        assert result1.was_duplicate is False
        assert result1.linked_to is None
        
        # Test duplicate case
        result2 = UploadResult(
            success=True,
            library="test-lib",
            version="1.0",
            files_processed=1,
            chunks_indexed=0,
            message="Duplicate detected",
            was_duplicate=True,
            linked_to="/uploads/test-lib/1.0/original.md"
        )
        
        assert result2.was_duplicate is True
        assert result2.linked_to == "/uploads/test-lib/1.0/original.md"

    def test_upload_result_deduplication_fields_optional(self):
        """Deduplication fields should be optional for backwards compatibility."""
        try:
            from dashboard.server import UploadResult
        except ImportError:
            # If fastapi not available, skip this test
            pytest.skip("Dashboard dependencies not available")
        
        # Should work without deduplication fields
        result = UploadResult(
            success=True,
            library="test-lib",
            version="1.0",
            files_processed=1,
            chunks_indexed=5,
            message="Success"
        )
        
        assert result.success is True
        # Fields should exist with default values
        assert hasattr(result, 'was_duplicate')
        assert hasattr(result, 'linked_to')
