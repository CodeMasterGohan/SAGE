"""
SAGE-Docs MCP Server
====================
Exposes SAGE-Docs documentation search capabilities to LLMs via Model Context Protocol.

Features (Agent-Optimized):
- Smart Context: Sticky sessions and ambiguity handling (e.g. "React vs Vue").
- Hybrid Search: Semantic + Keyword + Reranking (ColBERT).
- Performance: Async caching and connection pooling.

Tools:
- search_docs: Agent-optimized search with context awareness.
- list_libraries: Discover available libraries/versions.
- resolve_library: Find libraries matching a query.
- get_document: Retrieve full document content.
"""

import os
import sys
import time
import logging
import argparse
import asyncio
from typing import Optional, List, Dict, Any

from mcp.server.fastmcp import FastMCP
from qdrant_client import QdrantClient
from qdrant_client.http import models
from fastembed import TextEmbedding, SparseTextEmbedding

# Local Modules
from middleware import SmartContextManager, AmbiguityHandler, context_manager
from search import perform_search_workflow

# Configure logging
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

# Embedding Configuration
EMBEDDING_MODE = os.getenv("EMBEDDING_MODE", "local")
DENSE_MODEL_NAME = os.getenv("DENSE_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
USE_NOMIC_PREFIX = os.getenv("USE_NOMIC_PREFIX", "false").lower() == "true"
VLLM_EMBEDDING_URL = os.getenv("VLLM_EMBEDDING_URL", "http://localhost:8000")
VLLM_MODEL_NAME = os.getenv("VLLM_MODEL_NAME", "nomic-ai/nomic-embed-text-v1.5")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "")

# Initialize FastMCP server
mcp = FastMCP(
    "SAGE-Docs",
    stateless_http=True,
    json_response=True
)

# Global State
_qdrant_client: Optional[QdrantClient] = None
_dense_model: Optional[TextEmbedding] = None
_bm25_model: Optional[SparseTextEmbedding] = None
_rerank_model = None
_http_client: Optional["httpx.AsyncClient"] = None  # For remote embeddings
_ambiguity_handler: Optional[AmbiguityHandler] = None


# ============================================================
# Core Model & Client Loaders
# ============================================================

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


def get_ambiguity_handler() -> AmbiguityHandler:
    """Get or create the ambiguity handler."""
    global _ambiguity_handler
    if _ambiguity_handler is None:
        _ambiguity_handler = AmbiguityHandler(get_qdrant_client, COLLECTION_NAME)
    return _ambiguity_handler


async def get_http_client() -> "httpx.AsyncClient":
    """Get or create global HTTP client with connection pooling."""
    global _http_client
    if _http_client is None:
        import httpx
        _http_client = httpx.AsyncClient(
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            timeout=30.0
        )
    return _http_client


async def get_remote_embedding(text: str) -> list[float]:
    """Get embedding from remote vLLM server using persistent connection."""
    client = await get_http_client()
    headers = {"Content-Type": "application/json"}
    if VLLM_API_KEY:
        headers["Authorization"] = f"Bearer {VLLM_API_KEY}"
    
    try:
        response = await client.post(
            f"{VLLM_EMBEDDING_URL}/v1/embeddings",
            json={"input": [text], "model": VLLM_MODEL_NAME},
            headers=headers
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]
    except Exception as e:
        logger.error(f"Remote embedding failed: {e}")
        raise


# ============================================================
# Search Helper
# ============================================================

async def _do_search(query: str, library: str, version: str, limit: int, rerank: bool, fusion: str) -> List[Dict]:
    """Wrapper that injects dependencies into the search module."""
    return await perform_search_workflow(
        query=query,
        library=library,
        version=version,
        limit=limit,
        rerank=rerank,
        fusion_str=fusion,
        # Inject dependencies
        get_client_fn=get_qdrant_client,
        get_dense_fn=get_dense_model,
        get_bm25_fn=get_bm25_model,
        get_rerank_fn=get_rerank_model,
        get_remote_embedding_fn=get_remote_embedding,
        collection_name=COLLECTION_NAME,
        embedding_mode=EMBEDDING_MODE,
        use_nomic_prefix=USE_NOMIC_PREFIX
    )

# ============================================================
# MCP Tools
# ============================================================

@mcp.tool()
async def search_docs(
    query: str,
    library: str = None,
    version: str = None,
    limit: int = 5,
    rerank: bool = False,
    fusion: str = "dbsf"
) -> Dict[str, Any]:
    """
    Agent-Optimized Documentation Search.
    
    Features:
    - Smart Context: Remembers previous library context.
    - Ambiguity Handling: Automatically detects multiple libraries (e.g. "React vs Vue").
    - Recursive Search: If targeted search fails, falls back to global search.
    
    Args:
        query: Search query (e.g. "how to use useState")
        library: Specific library filter. Use "*" or "GLOBAL" to force global search.
        version: Optional version filter.
        limit: Max results.
        rerank: Enable ColBERT reranking (slower, more accurate).
        fusion: "dbsf" (default) or "rrf".
    
    Returns:
        Dict containing "results" and "meta" (explaining how the search was resolved).
    """
    start_time = time.time()
    session_id = "default"  # Future: Extract from request context
    
    meta = {
        "query": query,
        "original_library_arg": library,
        "resolution_method": "unknown",
        "ambiguity_detected": [],
        "latency_ms": 0
    }
    
    target_libraries = []
    ambiguity_handler = get_ambiguity_handler()
    
    # 1. Resolve Context
    # Case A: Explicit Global
    if library in ["*", "GLOBAL"]:
        target_libraries = [None]
        meta["resolution_method"] = "explicit_global"
        context_manager.clear_context(session_id)
        
    # Case B: Explicit Library
    elif library:
        # Resolve aliases
        known_libs = await ambiguity_handler._get_known_libraries()
        resolved_lib = ambiguity_handler.resolve_alias(library, known_libs)
        
        if resolved_lib:
            target_libraries = [resolved_lib]
            if resolved_lib != library:
                meta["alias_resolved"] = f"{library} -> {resolved_lib}"
        else:
            target_libraries = [library]
        
        meta["resolution_method"] = "explicit_arg"
        context_manager.update_context(target_libraries[0], session_id)
        
    # Case C: Automatic Resolution
    else:
        detected_libs = await ambiguity_handler.detect_libraries(query)
        
        if len(detected_libs) > 1:
            target_libraries = detected_libs
            meta["resolution_method"] = "ambiguity_multi_search"
            meta["ambiguity_detected"] = detected_libs
        elif len(detected_libs) == 1:
            target_libraries = [detected_libs[0]]
            meta["resolution_method"] = "inferred_from_query"
            context_manager.update_context(detected_libs[0], session_id)
        else:
            # Check session
            active_context = context_manager.get_context(session_id)
            if active_context:
                target_libraries = [active_context]
                meta["resolution_method"] = "session_history"
            else:
                target_libraries = [None] # Global fallback
                meta["resolution_method"] = "default_global"
    
    meta["active_context"] = target_libraries
    
    # 2. Execute Search
    tasks = [
        _do_search(query=query, library=lib_target, version=version, limit=limit, rerank=rerank, fusion=fusion)
        for lib_target in target_libraries
    ]
    
    results_lists = await asyncio.gather(*tasks)
    
    final_results = []
    for r_list in results_lists:
        final_results.extend(r_list)
        
    if len(target_libraries) > 1:
        final_results.sort(key=lambda x: x["score"], reverse=True)
        final_results = final_results[:limit]
        
    # 3. Fallback
    if not final_results and all(l is not None for l in target_libraries):
        logger.info("Targeted search failed. Attempting global fallback.")
        fallback_results = await _do_search(
            query=query, library=None, version=None, limit=limit, rerank=rerank, fusion=fusion
        )
        if fallback_results:
            for res in fallback_results:
                res["search_note"] = "Global Fallback (Targeted search returned no results)"
            final_results = fallback_results
            meta["resolution_method"] += "_fallback_to_global"
            
    meta["latency_ms"] = int((time.time() - start_time) * 1000)
    
    return {
        "results": final_results,
        "meta": meta
    }


@mcp.tool()
async def resolve_library(query: str, limit: int = 5) -> list[dict]:
    """
    Find libraries matching a search query.
    
    Optimized: Fetches versions for top matches in a single scroll query.
    """
    # Re-using SAGE's superior resolution logic, but injecting client getter
    # Note: We could use AmbiguityHandler here, but SAGE's scoring is nicer for UI/Human use.
    client = get_qdrant_client()
    query_lower = query.lower()
    
    try:
        # We need to run this in executor because QdrantClient is sync (mostly) 
        # but here we use the sync methods directly. 
        # Wait, FastMCP tools can be async.
        
        # Facet query
        loop = asyncio.get_running_loop()
        library_facets = await loop.run_in_executor(
            None, # Default executor
            lambda: client.facet(
                collection_name=COLLECTION_NAME,
                key="library",
                limit=1000
            )
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
        
        if not top_matches:
            return []
            
        # Get versions for top matches
        top_lib_names = {m["library"] for m in top_matches}
        library_versions = {lib: set() for lib in top_lib_names}
        
        scroll_filter = models.Filter(
            should=[
                models.FieldCondition(key="library", match=models.MatchValue(value=lib_name))
                for lib_name in top_lib_names
            ]
        )
        
        # Scroll in executor
        results, _ = await loop.run_in_executor(
            None,
            lambda: client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=scroll_filter,
                limit=1000,
                with_payload=["library", "version"],
                with_vectors=False
            )
        )
        
        for point in results:
            lib = point.payload.get("library")
            ver = point.payload.get("version")
            if lib in library_versions and ver:
                library_versions[lib].add(ver)
                
        for match in top_matches:
            lib_name = match["library"]
            match["versions"] = sorted(library_versions.get(lib_name, set()), reverse=True)[:10]
            
        return top_matches
        
    except Exception as e:
        logger.error(f"Failed to resolve library: {e}")
        return [{"error": str(e)}]


@mcp.tool()
async def list_libraries() -> list[dict]:
    """List all indexed libraries and their versions."""
    client = get_qdrant_client()
    loop = asyncio.get_running_loop()
    
    try:
        # 1. Get unique libraries
        library_facets = await loop.run_in_executor(
            None,
            lambda: client.facet(
                collection_name=COLLECTION_NAME,
                key="library",
                limit=1000
            )
        )
        
        if not library_facets.hits:
            return []
            
        # 2. Get versions via scroll (optimized)
        library_versions = {hit.value: set() for hit in library_facets.hits}
        
        # Helper for scrolling
        def _get_all_versions():
            all_results = []
            next_offset = None
            while True:
                results, next_offset = client.scroll(
                    collection_name=COLLECTION_NAME,
                    offset=next_offset,
                    limit=2000,
                    with_payload=["library", "version"],
                    with_vectors=False
                )
                all_results.extend(results)
                if not next_offset:
                    break
            return all_results

        results = await loop.run_in_executor(None, _get_all_versions)
        
        for point in results:
            lib = point.payload.get("library")
            ver = point.payload.get("version")
            if lib in library_versions and ver:
                library_versions[lib].add(ver)
                
        # 3. Format
        final_list = []
        for hit in library_facets.hits:
            lib_name = hit.value
            versions = sorted(library_versions.get(lib_name, set()), reverse=True)
            final_list.append({
                "library": lib_name,
                "versions": versions
            })
            
        return sorted(final_list, key=lambda x: x["library"])

    except Exception as e:
        logger.error(f"Failed to list libraries: {e}")
        return [{"error": str(e)}]


@mcp.tool()
def get_document(file_path: str) -> dict:
    """Get the full content of a specific document by its file path."""
    client = get_qdrant_client()
    
    try:
        results, _ = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="file_path", match=models.MatchValue(value=file_path))]
            ),
            limit=100,
            with_payload=True
        )
        
        if not results:
            return {"error": f"Document not found: {file_path}"}
        
        chunks = sorted(results, key=lambda p: p.payload.get("chunk_index", 0))
        full_content = "\n\n".join(p.payload.get("content", "") for p in chunks)
        
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
    parser = argparse.ArgumentParser(description="SAGE-Docs MCP Server")
    parser.add_argument("--transport", "-t", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--port", "-p", type=int, default=8000)
    parser.add_argument("--preload", action="store_true")
    args = parser.parse_args()
    
    if args.preload:
        logger.info("Preloading models...")
        get_dense_model()
        get_bm25_model()
    
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
