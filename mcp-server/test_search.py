import sys
import os
from unittest.mock import MagicMock, patch

# Mocking qdrant_client and its models BEFORE importing search
# We use a dummy module for models to avoid import errors
from types import ModuleType
mock_models_mod = ModuleType("models")
mock_models_mod.Fusion = MagicMock()
mock_models_mod.Fusion.DBSF = "DBSF"
mock_models_mod.Fusion.RRF = "RRF"

sys.modules["qdrant_client"] = MagicMock()
sys.modules["qdrant_client.http"] = MagicMock()
sys.modules["qdrant_client.http.models"] = mock_models_mod

# Add the directory to sys.path to allow importing search
sys.path.append(os.path.dirname(__file__))

# Import the module
import search

import pytest

@pytest.fixture
def mock_client():
    return MagicMock()

@pytest.fixture
def sparse_embedding():
    emb = MagicMock()
    emb.indices.tolist.return_value = [1, 2, 3]
    emb.values.tolist.return_value = [0.1, 0.2, 0.3]
    return emb

def test_semantic_only(mock_client):
    dense_vector = [0.1] * 384
    search.execute_hybrid_query(
        client=mock_client,
        collection_name="test_col",
        query="test",
        limit=10,
        dense_vector=dense_vector,
        sparse_embedding=None,
        semantic_weight=1.0,
        keyword_weight=0.0
    )

    mock_client.query_points.assert_called_once()
    kwargs = mock_client.query_points.call_args.kwargs
    assert kwargs["using"] == "dense"
    assert kwargs["query"] == dense_vector

def test_keyword_only(mock_client, sparse_embedding):
    with patch.object(search.models, "SparseVector") as mock_sv:
        search.execute_hybrid_query(
            client=mock_client,
            collection_name="test_col",
            query="test",
            limit=10,
            dense_vector=None,
            sparse_embedding=sparse_embedding,
            semantic_weight=0.0,
            keyword_weight=1.0
        )

        mock_client.query_points.assert_called_once()
        kwargs = mock_client.query_points.call_args.kwargs
        assert kwargs["using"] == "sparse"
        mock_sv.assert_called_once()

def test_hybrid(mock_client, sparse_embedding):
    with patch.object(search.models, "FusionQuery") as mock_fq, \
         patch.object(search.models, "Prefetch") as mock_prefetch:
        dense_vector = [0.1] * 384
        search.execute_hybrid_query(
            client=mock_client,
            collection_name="test_col",
            query="test",
            limit=10,
            dense_vector=dense_vector,
            sparse_embedding=sparse_embedding,
            semantic_weight=0.5,
            keyword_weight=0.5
        )

        mock_client.query_points.assert_called_once()
        kwargs = mock_client.query_points.call_args.kwargs
        assert "prefetch" in kwargs
        assert len(kwargs["prefetch"]) == 2
        mock_fq.assert_called_once()

def test_filtering(mock_client):
    with patch.object(search.models, "FieldCondition") as mock_fc, \
         patch.object(search.models, "Filter") as mock_filter, \
         patch.object(search.models, "MatchValue") as mock_mv:
        dense_vector = [0.1] * 384
        search.execute_hybrid_query(
            client=mock_client,
            collection_name="test_col",
            query="test",
            limit=10,
            dense_vector=dense_vector,
            sparse_embedding=None,
            library_filter="my_lib",
            version_filter="1.0"
        )

        mock_client.query_points.assert_called_once()
        kwargs = mock_client.query_points.call_args.kwargs
        assert kwargs["query_filter"] is not None
        assert mock_fc.called
        assert mock_filter.called

def test_both_disabled(mock_client):
    with patch.object(search.models, "QueryResponse") as mock_qr:
        result = search.execute_hybrid_query(
            client=mock_client,
            collection_name="test_col",
            query="test",
            limit=10,
            dense_vector=None,
            sparse_embedding=None,
            semantic_weight=0.0,
            keyword_weight=0.0
        )

        mock_qr.assert_called_once_with(points=[])
        mock_client.query_points.assert_not_called()
