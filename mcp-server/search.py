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


def execute_hybrid_query(
    client,
    collection_name: str,
    query: str,
    limit: int,
    dense_vector: list,
    sparse_embedding,
    library_filter: str = None,
    version_filter: str = None,
    fusion_type=models.Fusion.DBSF
):
    """
    Low-level helper to execute the hybrid query against Qdrant.
    
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
    """
    # Build Filter
    filter_conditions = []
    # SAGE field naming: "library" and "version" are top-level payload fields, not in "metadata"
    if library_filter and library_filter != "GLOBAL":
        filter_conditions.append(
            models.FieldCondition(key="library", match=models.MatchValue(value=library_filter))
        )
    if version_filter:
        filter_conditions.append(
            models.FieldCondition(key="version", match=models.MatchValue(value=version_filter))
        )
    
    search_filter = models.Filter(must=filter_conditions) if filter_conditions else None
        
    # Execute Hybrid Search
    return client.query_points(
        collection_name=collection_name,
        prefetch=[
            models.Prefetch(
                query=dense_vector, 
                using="dense", 
                limit=limit * 2, 
                filter=search_filter
            ),
            models.Prefetch(
                query=models.SparseVector(
                    indices=sparse_embedding.indices.tolist(),
                    values=sparse_embedding.values.tolist()
                ),
                using="sparse",
                limit=limit * 2,
                filter=search_filter
            )
        ],
        query=models.FusionQuery(fusion=fusion_type),
        limit=limit,
        with_payload=True
    )


async def perform_search_workflow(
    query: str, 
    library: Union[str, None], 
    version: Union[str, None], 
    limit: int, 
    rerank: bool, 
    fusion_str: str,
    # Dependencies (injected)
    get_client_fn,
    get_dense_fn,
    get_bm25_fn,
    get_rerank_fn,
    get_remote_embedding_fn,
    collection_name: str,
    embedding_mode: str,
    use_nomic_prefix: bool
) -> List[Dict]:
    """
    Executes a single search workflow (Async wrapper).
    
    This function is designed to be called with all dependencies injected,
    making it testable and decoupled from global state.
    """
    loop = asyncio.get_running_loop()
    fusion_type = models.Fusion.DBSF if fusion_str.lower() == "dbsf" else models.Fusion.RRF
    fetch_limit = limit * 3 if rerank else limit

    try:
        # 1. Generate Embeddings
        query_for_embed = f"search_query: {query}" if use_nomic_prefix else query
        
        if embedding_mode == "remote":
            dense_vector = await get_remote_embedding_fn(query_for_embed)
        else:
            dense_model = get_dense_fn()
            # Run blocking embedding in executor to avoid blocking event loop
            dense_vector = await loop.run_in_executor(
                _executor,
                lambda: list(dense_model.embed([query_for_embed]))[0].tolist()
            )
        
        bm25_model = get_bm25_fn()
        # Run blocking embedding in executor
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
