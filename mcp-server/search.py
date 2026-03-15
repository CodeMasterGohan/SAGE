"""
SAGE Search Logic
==================
Hybrid semantic + keyword search with reranking support.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Union
from concurrent.futures import ThreadPoolExecutor

from qdrant_client.http import models

logger = logging.getLogger("SAGE-MCP")

# Shared executor for async operations
_executor = ThreadPoolExecutor(max_workers=10)


def rerank_results(query: str, results: list, rerank_model, top_k: int = 5) -> list:
    """
    Rerank results using ColBERT late interaction model.
    
    Args:
        query: The search query.
        results: List of result dicts with 'content' key.
        rerank_model: Loaded ColBERT model (or None to skip).
        top_k: Number of results to return.
    """
    if not rerank_model or not results:
        return results[:top_k]
    
    try:
        documents = [r["content"] for r in results]
        
        # ColBERT inference
        query_embedding = list(rerank_model.query_embed(query))[0]
        doc_embeddings = list(rerank_model.passage_embed(documents))
        
        scores = []
        for doc_emb in doc_embeddings:
            score = (query_embedding @ doc_emb.T).max(axis=1).sum()
            scores.append(float(score))
        
        # Sort and merge
        reranked = sorted(zip(results, scores), key=lambda x: x[1], reverse=True)
        return [{**r, "score": s, "reranked": True} for r, s in reranked[:top_k]]
    except Exception as e:
        logger.warning(f"Reranking failed: {e}")
        return results[:top_k]


# Mode presets for agentic hybrid search
MODE_PRESETS = {
    "auto":     {"semantic_weight": 1.0, "keyword_weight": 1.0},
    "hybrid":   {"semantic_weight": 1.0, "keyword_weight": 1.0},
    "semantic": {"semantic_weight": 1.0, "keyword_weight": 0.0},
    "keyword":  {"semantic_weight": 0.0, "keyword_weight": 1.0},
}


def _resolve_weights(
    mode: str = "auto",
    semantic_weight: Optional[float] = None,
    keyword_weight: Optional[float] = None,
) -> tuple[float, float]:
    """
    Resolve mode preset + explicit overrides into concrete weights.
    Explicit weights always take precedence over the mode preset.
    """
    preset = MODE_PRESETS.get(mode.lower(), MODE_PRESETS["auto"])
    sw = semantic_weight if semantic_weight is not None else preset["semantic_weight"]
    kw = keyword_weight if keyword_weight is not None else preset["keyword_weight"]
    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, sw)), max(0.0, min(1.0, kw))


def execute_hybrid_query(
    client,
    collection_name: str,
    query: str,
    limit: int,
    dense_vector: list,
    sparse_embedding,
    library_filter: str = None,
    version_filter: str = None,
    fusion_type=models.Fusion.DBSF,
    semantic_weight: float = 1.0,
    keyword_weight: float = 1.0,
):
    """
    Low-level helper to execute the hybrid query against Qdrant.
    
    Supports agentic weight control:
    - semantic_weight=0.0 skips the dense prefetch entirely.
    - keyword_weight=0.0 skips the sparse prefetch entirely.
    - When only one leg is active, fusion is bypassed for efficiency.
    
    Args:
        client: QdrantClient instance.
        collection_name: Name of the collection.
        query: The search query (for logging).
        limit: Max results.
        dense_vector: Pre-computed dense embedding.
        sparse_embedding: Pre-computed sparse (BM25) embedding.
        library_filter: Optional library to filter by.
        version_filter: Optional version to filter by.
        fusion_type: Fusion method (DBSF or RRF).
        semantic_weight: Weight for dense/semantic retrieval (0.0-1.0).
        keyword_weight: Weight for sparse/keyword retrieval (0.0-1.0).
    """
    # Build Filter
    filter_conditions = []
    if library_filter and library_filter != "GLOBAL":
        filter_conditions.append(
            models.FieldCondition(key="library", match=models.MatchValue(value=library_filter))
        )
    if version_filter:
        filter_conditions.append(
            models.FieldCondition(key="version", match=models.MatchValue(value=version_filter))
        )
    
    search_filter = models.Filter(must=filter_conditions) if filter_conditions else None

    use_semantic = semantic_weight > 0.0 and dense_vector is not None
    use_keyword = keyword_weight > 0.0 and sparse_embedding is not None

    if not use_semantic and not use_keyword:
        logger.warning(f"Agentic search: no active legs (semantic={semantic_weight}, keyword={keyword_weight})")
        # Return empty result set compatible with Qdrant QueryResponse
        return models.QueryResponse(points=[])

    # --- Single-vector fast paths (no fusion needed) ---
    if use_semantic and not use_keyword:
        logger.info(f"Agentic search: semantic-only (weight={semantic_weight})")
        return client.query_points(
            collection_name=collection_name,
            query=dense_vector,
            using="dense",
            query_filter=search_filter,
            limit=limit,
            with_payload=True,
        )

    if use_keyword and not use_semantic:
        logger.info(f"Agentic search: keyword-only (weight={keyword_weight})")
        return client.query_points(
            collection_name=collection_name,
            query=models.SparseVector(
                indices=sparse_embedding.indices.tolist(),
                values=sparse_embedding.values.tolist(),
            ),
            using="sparse",
            query_filter=search_filter,
            limit=limit,
            with_payload=True,
        )

    # --- Hybrid path (both vectors active) ---
    # Scale prefetch limits by weight so the higher-weighted leg gets more candidates
    total_weight = semantic_weight + keyword_weight
    sem_ratio = semantic_weight / total_weight if total_weight > 0 else 0.5
    kw_ratio = keyword_weight / total_weight if total_weight > 0 else 0.5
    base_prefetch = limit * 2

    prefetch_legs = []
    prefetch_legs.append(
        models.Prefetch(
            query=dense_vector,
            using="dense",
            limit=max(1, int(base_prefetch * sem_ratio * 2)),
            filter=search_filter,
        )
    )
    prefetch_legs.append(
        models.Prefetch(
            query=models.SparseVector(
                indices=sparse_embedding.indices.tolist(),
                values=sparse_embedding.values.tolist(),
            ),
            using="sparse",
            limit=max(1, int(base_prefetch * kw_ratio * 2)),
            filter=search_filter,
        )
    )

    logger.info(f"Agentic search: hybrid (semantic={semantic_weight}, keyword={keyword_weight})")
    return client.query_points(
        collection_name=collection_name,
        prefetch=prefetch_legs,
        query=models.FusionQuery(fusion=fusion_type),
        limit=limit,
        with_payload=True,
    )


async def perform_search_workflow(
    query: str, 
    library: Union[str, None], 
    version: Union[str, None], 
    limit: int, 
    rerank: bool, 
    fusion_str: str,
    # Agentic hybrid search controls
    mode: str = "auto",
    semantic_weight: Optional[float] = None,
    keyword_weight: Optional[float] = None,
    # Dependencies (injected)
    get_client_fn=None,
    get_dense_fn=None,
    get_bm25_fn=None,
    get_rerank_fn=None,
    get_remote_embedding_fn=None,
    collection_name: str = "",
    embedding_mode: str = "local",
    use_nomic_prefix: bool = False
) -> List[Dict]:
    """
    Executes a single search workflow (Async wrapper).
    
    This function is designed to be called with all dependencies injected,
    making it testable and decoupled from global state.
    
    Agentic hybrid search: use 'mode' for presets or explicit weights.
    """
    loop = asyncio.get_running_loop()
    fusion_type = models.Fusion.DBSF if fusion_str.lower() == "dbsf" else models.Fusion.RRF
    fetch_limit = limit * 3 if rerank else limit

    # Resolve agentic weights
    sw, kw = _resolve_weights(mode, semantic_weight, keyword_weight)

    try:
        # 1. Generate Embeddings
        query_for_embed = f"search_query: {query}" if use_nomic_prefix else query

        # Skip embedding generation if weight is zero
        dense_vector = None
        if sw > 0.0:
            if embedding_mode == "remote":
                dense_vector = await get_remote_embedding_fn(query_for_embed)
            else:
                dense_model = get_dense_fn()
                dense_vector = await loop.run_in_executor(
                    _executor,
                    lambda: list(dense_model.embed([query_for_embed]))[0].tolist()
                )
        
        sparse_embedding = None
        if kw > 0.0:
            bm25_model = get_bm25_fn()
            sparse_embedding = await loop.run_in_executor(
                _executor,
                lambda: list(bm25_model.embed([query]))[0]
            )
        
        # 2. Run blocking Qdrant call in executor
        client = get_client_fn()
        results = await loop.run_in_executor(
            _executor,
            lambda: execute_hybrid_query(
                client=client,
                collection_name=collection_name,
                query=query,
                limit=fetch_limit,
                semantic_weight=sw,
                keyword_weight=kw,
                dense_vector=dense_vector,
                sparse_embedding=sparse_embedding,
                library_filter=library,
                version_filter=version,
                fusion_type=fusion_type
            )
        )
        
        # 3. Format results
        formatted = []
        for point in results.points:
            payload = point.payload
            formatted.append({
                "content": payload.get("content", ""),
                "library": payload.get("library", "unknown"),
                "version": payload.get("version", "unknown"),
                "title": payload.get("title", ""),
                "file_path": payload.get("file_path", ""),
                "type": payload.get("type", ""),
                "chunk_index": payload.get("chunk_index"),
                "score": point.score,
                # Tag the source library for multi-search merging
                "source_context": library if library else "GLOBAL"
            })
        
        # 4. Rerank if requested
        if rerank and formatted:
            rerank_model = get_rerank_fn()
            formatted = await loop.run_in_executor(
                _executor, 
                lambda: rerank_results(query, formatted, rerank_model, limit)
            )
        else:
            formatted = formatted[:limit]
            
        return formatted
    except Exception as e:
        logger.error(f"Search workflow failed: {e}")
        return []
