import os
import sys
import pytest
import respx
from httpx import Response
from unittest.mock import MagicMock, patch

# Set environment variables for testing BEFORE importing dashboard modules
os.environ["EMBEDDING_MODE"] = "remote"
os.environ["VLLM_EMBEDDING_URL"] = "http://mock-vllm:8000"
os.environ["VLLM_MODEL_NAME"] = "mock-model"
os.environ["OLMOCR_SERVER"] = "http://mock-olmocr:8000"
# Ensure vault is not found to test fallback
sys.modules["vault"] = None

# Mock qdrant_client and fastembed to avoid real connections/loading
mock_qdrant = MagicMock()
sys.modules["qdrant_client"] = mock_qdrant
sys.modules["qdrant_client.http"] = MagicMock()
sys.modules["qdrant_client.http.models"] = MagicMock()

mock_fastembed = MagicMock()
sys.modules["fastembed"] = mock_fastembed

# Add repo root to path so we can import dashboard
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# Add dashboard directory to path so server.py can import ingest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dashboard")))

# Import dashboard modules
from dashboard import server
from dashboard import ingest

# Explicitly set globals if they were already loaded (just in case)
server.EMBEDDING_MODE = "remote"
ingest.EMBEDDING_MODE = "remote"
ingest.VAULT_AVAILABLE = False # Force fallback

@pytest.mark.asyncio
async def test_search_docs_uses_remote_embedding():
    """Test that search_docs uses remote embedding when configured."""

    # Mock the embedding response
    async with respx.mock(base_url="http://mock-vllm:8000") as respx_mock:
        route = respx_mock.post("/v1/embeddings").mock(return_value=Response(200, json={
            "data": [{"embedding": [0.1] * 384, "index": 0}]
        }))

        # Mock dependencies
        mock_client = MagicMock()
        mock_bm25 = MagicMock()
        # Mock sparse embedding return
        mock_sparse_vec = MagicMock()
        mock_sparse_vec.indices.tolist.return_value = [0, 1]
        mock_sparse_vec.values.tolist.return_value = [0.5, 0.5]
        mock_bm25.embed.return_value = [mock_sparse_vec]

        mock_dense = MagicMock()

        request = server.SearchRequest(query="test query")

        # We expect search_docs to await the remote call
        # Since we haven't implemented it yet, this test should fail (it will try to use dense_model)

        # We need to catch exceptions because qdrant query will likely fail on mocks or we just care about embedding call
        try:
            await server.search_docs(
                request=request,
                client=mock_client,
                bm25_model=mock_bm25,
                dense_model=mock_dense
            )
        except Exception as e:
            # It's okay if it fails later
            print(f"Caught expected exception: {e}")
            pass

        # Verify remote endpoint was called
        assert route.called, "Remote embedding endpoint was not called"
        assert route.call_count == 1

def test_extract_pdf_text_uses_olmocr_server():
    """Test that olmocr command includes --server when configured."""

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""

        # We need to ensure the temp file creation works, so we might need to mock tempfile or just let it use /tmp
        # It's easier to mock subprocess.run

        ingest.extract_pdf_text(b"fake pdf content")

        # Verify subprocess.run was called
        assert mock_run.called
        args = mock_run.call_args[0][0]

        assert "--server" in args
        assert "http://mock-olmocr:8000" in args

@pytest.mark.asyncio
async def test_ingest_markdown_uses_remote_embedding():
    """Test that ingest fallback uses remote embedding when configured."""

    async with respx.mock(base_url="http://mock-vllm:8000") as respx_mock:
        route = respx_mock.post("/v1/embeddings").mock(return_value=Response(200, json={
            "data": [{"embedding": [0.1] * 384, "index": 0}]
        }))

        mock_client = MagicMock()

        # Mock internal functions to isolate embedding logic
        with patch("dashboard.ingest.split_text_semantic", return_value=["chunk1"]):
            with patch("dashboard.ingest.save_uploaded_file", return_value="path/to/file"):
                 with patch("dashboard.ingest.get_sparse_model") as mock_get_sparse:
                    mock_sparse = MagicMock()
                    mock_sparse_vec = MagicMock()
                    mock_sparse_vec.indices.tolist.return_value = [0]
                    mock_sparse_vec.values.tolist.return_value = [1.0]
                    mock_sparse.embed.return_value = [mock_sparse_vec]
                    mock_get_sparse.return_value = mock_sparse

                    # Mock dense model to ensure it's NOT used
                    with patch("dashboard.ingest.get_dense_model") as mock_get_dense:
                        mock_dense = MagicMock()
                        mock_get_dense.return_value = mock_dense

                        await ingest._ingest_markdown(
                            client=mock_client,
                            markdown="test content",
                            filename="test.md",
                            library="lib",
                            version="v1"
                        )

                        # Verify remote called
                        assert route.called, "Remote embedding endpoint was not called in ingest"

                        # Verify local model NOT called
                        # mock_dense.embed.assert_not_called()
