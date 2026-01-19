"""
SAGE-Docs MCP Server
====================
Exposes SAGE-Docs documentation search capabilities to LLMs via Model Context Protocol.

Features:
- Hybrid semantic + keyword search with native Qdrant BM25
- DBSF fusion for better score normalization
- Optional ColBERT reranking for maximum accuracy

Tools:
- search_docs: Hybrid semantic + keyword search with optional reranking
- list_libraries: Discover available libraries/versions
- resolve_library: Find libraries matching a query (use before search_docs)
- get_document: Retrieve full document content

Usage:
  # Local (stdio transport for Gemini CLI, Claude Desktop, etc.)
  python main.py

  # HTTP transport (for containerized deployments)
  python main.py --transport http --port 8000
"""

import os
import sys
import logging
import argparse
from typing import Optional

from mcp.server.fastmcp import FastMCP
from qdrant_client import QdrantClient
from qdrant_client.http import models
from fastembed import TextEmbedding, SparseTextEmbedding

# Configure logging - reduce noise for MCP stdio
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("SAGE-MCP")
logger.setLevel(logging.INFO)

# Configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "sage_docs")

# ============================================================
# EMBEDDING MODEL CONFIGURATION (must match backend/ingest.py!)
# ============================================================
EMBEDDING_MODE = os.getenv("EMBEDDING_MODE", "local")
DENSE_MODEL_NAME = os.getenv("DENSE_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
USE_NOMIC_PREFIX = os.getenv("USE_NOMIC_PREFIX", "false").lower() == "true"

# Remote vLLM configuration (only used when EMBEDDING_MODE=remote)
VLLM_EMBEDDING_URL = os.getenv("VLLM_EMBEDDING_URL", "http://localhost:8000")
VLLM_MODEL_NAME = os.getenv("VLLM_MODEL_NAME", "nomic-ai/nomic-embed-text-v1.5")

# Initialize FastMCP server
mcp = FastMCP(
    "SAGE-Docs",
    stateless_http=True,
    json_response=True
)

# Model instances (lazy-loaded, then cached)
_qdrant_client: Optional[QdrantClient] = None
_dense_model: Optional[TextEmbedding] = None
_bm25_model: Optional[SparseTextEmbedding] = None
_rerank_model = None


def get_qdrant_client() -> QdrantClient:
    """Get or create Qdrant client."""
    global _qdrant_client
    if _qdrant_client is None:
        logger.info(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")
        _qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    return _qdrant_client


def get_dense_model() -> TextEmbedding:
    """Get or create dense embedding model."""
    global _dense_model
    if _dense_model is None:
        logger.info(f"Loading embedding model ({DENSE_MODEL_NAME})...")
        _dense_model = TextEmbedding(model_name=DENSE_MODEL_NAME)
    return _dense_model


def get_bm25_model() -> SparseTextEmbedding:
    """Get or create BM25 sparse embedding model."""
    global _bm25_model
    if _bm25_model is None:
        logger.info("Loading Qdrant BM25 model...")
        _bm25_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    return _bm25_model


def get_remote_embedding(text: str) -> list[float]:
    """Get embedding from remote vLLM server."""
    import httpx
    
    response = httpx.post(
        f"{VLLM_EMBEDDING_URL}/v1/embeddings",
        json={
            "input": [text],
            "model": VLLM_MODEL_NAME
        },
        timeout=30.0
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


def get_rerank_model():
    """Get or create ColBERT reranking model (loaded on demand)."""
    global _rerank_model
    if _rerank_model is None:
        try:
            from fastembed import LateInteractionTextEmbedding
            logger.info("Loading ColBERT reranking model...")
            _rerank_model = LateInteractionTextEmbedding("colbert-ir/colbertv2.0")
        except Exception as e:
            logger.warning(f"ColBERT model not available: {e}")
            _rerank_model = False
    return _rerank_model if _rerank_model else None


def rerank_results(query: str, results: list, top_k: int = 5) -> list:
    """Rerank results using ColBERT late interaction model."""
    rerank_model = get_rerank_model()
    if not rerank_model or not results:
        return results[:top_k]
    
    try:
        documents = [r["content"] for r in results]
        
        query_embedding = list(rerank_model.query_embed(query))[0]
        doc_embeddings = list(rerank_model.passage_embed(documents))
        
        scores = []
        for doc_emb in doc_embeddings:
            score = (query_embedding @ doc_emb.T).max(axis=1).sum()
            scores.append(float(score))
        
        reranked = sorted(
            zip(results, scores),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [
            {**r, "score": s, "reranked": True}
            for r, s in reranked[:top_k]
        ]
    except Exception as e:
        logger.warning(f"Reranking failed: {e}")
        return results[:top_k]


@mcp.tool()
def search_docs(
    query: str,
    library: str = None,
    version: str = None,
    limit: int = 5,
    rerank: bool = False,
    fusion: str = "dbsf"
) -> list[dict]:
    """
    Search documentation using hybrid semantic + keyword search.
    
    Args:
        query: Search query (e.g., "how to use useState hook")
        library: Optional library filter (e.g., "react", "python")
        version: Optional version filter (e.g., "18.2", "3.11")
        limit: Maximum number of results to return (default: 5)
        rerank: Enable ColBERT reranking for better accuracy (slower)
        fusion: Fusion method - "dbsf" (default, better) or "rrf" (faster)
    
    Returns:
        List of matching documentation chunks with content and metadata.
    """
    client = get_qdrant_client()
    bm25_model = get_bm25_model()
    
    query_for_embed = f"search_query: {query}" if USE_NOMIC_PREFIX else query
    
    if EMBEDDING_MODE == "remote":
        dense_vector = get_remote_embedding(query_for_embed)
    else:
        dense_model = get_dense_model()
        dense_vector = list(dense_model.embed([query_for_embed]))[0].tolist()
    
    sparse_embedding = list(bm25_model.embed([query]))[0]
    
    filter_conditions = []
    if library:
        filter_conditions.append(
            models.FieldCondition(
                key="library",
                match=models.MatchValue(value=library)
            )
        )
    if version:
        filter_conditions.append(
            models.FieldCondition(
                key="version",
                match=models.MatchValue(value=version)
            )
        )
    
    search_filter = None
    if filter_conditions:
        search_filter = models.Filter(must=filter_conditions)
    
    fusion_type = models.Fusion.DBSF if fusion.lower() == "dbsf" else models.Fusion.RRF
    fetch_limit = limit * 3 if rerank else limit
    
    try:
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                models.Prefetch(
                    query=dense_vector,
                    using="dense",
                    limit=fetch_limit * 2
                ),
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sparse_embedding.indices.tolist(),
                        values=sparse_embedding.values.tolist()
                    ),
                    using="sparse",
                    limit=fetch_limit * 2
                )
            ],
            query=models.FusionQuery(fusion=fusion_type),
            query_filter=search_filter,
            limit=fetch_limit,
            with_payload=True
        )
        
        formatted = []
        for point in results.points:
            payload = point.payload
            formatted.append({
                "content": payload.get("content", ""),
                "library": payload.get("library", "unknown"),
                "version": payload.get("version", "unknown"),
                "title": payload.get("title", ""),
                "type": payload.get("type", ""),
                "file_path": payload.get("file_path", ""),
                "score": point.score
            })
        
        if rerank and formatted:
            formatted = rerank_results(query, formatted, limit)
        else:
            formatted = formatted[:limit]
        
        return formatted
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return [{"error": str(e)}]


@mcp.tool()
def list_libraries() -> list[dict]:
    """
    List all indexed libraries and their versions.
    
    Uses Qdrant's optimized facet API for O(1) performance.
    
    Returns:
        List of libraries with their available versions.
    """
    client = get_qdrant_client()

    try:
        library_facets = client.facet(
            collection_name=COLLECTION_NAME,
            key="library",
            limit=1000
        )

        result = []
        for hit in library_facets.hits:
            lib_name = hit.value

            version_facets = client.facet(
                collection_name=COLLECTION_NAME,
                key="version",
                facet_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="library",
                            match=models.MatchValue(value=lib_name)
                        )
                    ]
                ),
                limit=100
            )

            versions = [v.value for v in version_facets.hits]
            result.append({
                "library": lib_name,
                "versions": sorted(versions, reverse=True)
            })

        return sorted(result, key=lambda x: x["library"])

    except Exception as e:
        logger.error(f"Failed to list libraries: {e}")
        return [{"error": str(e)}]


@mcp.tool()
def resolve_library(
    query: str,
    limit: int = 5
) -> list[dict]:
    """
    Find libraries matching a search query.
    
    Use this BEFORE search_docs to identify the correct library filter.
    Returns libraries ranked by relevance with document counts.
    
    Args:
        query: Library name to search for (e.g., "react", "python requests")
        limit: Max results to return (default: 5)
    
    Returns:
        List of matching libraries with metadata for selection.
    """
    client = get_qdrant_client()
    query_lower = query.lower()
    
    try:
        library_facets = client.facet(
            collection_name=COLLECTION_NAME,
            key="library",
            limit=1000
        )
        
        scored = []
        for hit in library_facets.hits:
            lib_name = hit.value
            doc_count = hit.count
            
            name_lower = lib_name.lower()
            if name_lower == query_lower:
                score = 1.0
            elif query_lower in name_lower:
                score = 0.8
            elif name_lower in query_lower:
                score = 0.6
            else:
                query_words = set(query_lower.split())
                name_words = set(name_lower.replace('-', ' ').replace('_', ' ').split())
                overlap = query_words & name_words
                score = len(overlap) / max(len(query_words), 1) * 0.5
            
            if score > 0:
                scored.append({
                    "library": lib_name,
                    "doc_count": doc_count,
                    "relevance_score": round(score, 2)
                })
        
        scored.sort(key=lambda x: (-x["relevance_score"], -x["doc_count"]))
        top_matches = scored[:limit]
        
        for match in top_matches:
            version_facets = client.facet(
                collection_name=COLLECTION_NAME,
                key="version",
                facet_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="library",
                            match=models.MatchValue(value=match["library"])
                        )
                    ]
                ),
                limit=10
            )
            match["versions"] = sorted([v.value for v in version_facets.hits], reverse=True)
        
        return top_matches
        
    except Exception as e:
        logger.error(f"Failed to resolve library: {e}")
        return [{"error": str(e)}]


@mcp.tool()
def get_document(file_path: str) -> dict:
    """
    Get the full content of a specific document by its file path.
    
    Args:
        file_path: Path to the document (from search results)
    
    Returns:
        Document content and metadata.
    """
    client = get_qdrant_client()
    
    try:
        results, _ = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="file_path",
                        match=models.MatchValue(value=file_path)
                    )
                ]
            ),
            limit=100,
            with_payload=True
        )
        
        if not results:
            return {"error": f"Document not found: {file_path}"}
        
        chunks = sorted(results, key=lambda p: p.payload.get("chunk_index", 0))
        
        full_content = "\n\n".join(
            p.payload.get("content", "") for p in chunks
        )
        
        first_payload = chunks[0].payload
        
        return {
            "title": first_payload.get("title", ""),
            "library": first_payload.get("library", "unknown"),
            "version": first_payload.get("version", "unknown"),
            "type": first_payload.get("type", ""),
            "content": full_content,
            "chunk_count": len(chunks)
        }
        
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        return {"error": str(e)}


def main():
    """Entry point with transport selection."""
    parser = argparse.ArgumentParser(description="SAGE-Docs MCP Server")
    parser.add_argument(
        "--transport", "-t",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport type (default: stdio)"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="HTTP port (default: 8000)"
    )
    parser.add_argument(
        "--preload",
        action="store_true",
        help="Preload embedding models at startup"
    )
    args = parser.parse_args()
    
    if args.preload:
        logger.info("Preloading models...")
        get_dense_model()
        get_bm25_model()
        logger.info("Models preloaded.")
    
    if args.transport == "http":
        import uvicorn
        logger.info(f"Starting SAGE-Docs MCP server on HTTP port {args.port}")
        app = mcp.sse_app()
        uvicorn.run(app, host="0.0.0.0", port=args.port)
    else:
        logger.info("Starting SAGE-Docs MCP server on stdio")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
