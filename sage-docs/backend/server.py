"""
SAGE-Docs Dashboard Backend
===========================
FastAPI server that provides REST API endpoints for the SAGE-Docs web dashboard.
Extends DRUID's dashboard pattern with document upload capabilities.
"""

import os
import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.http import models
from fastembed import TextEmbedding, SparseTextEmbedding

from ingest import ingest_document, delete_library, ensure_collection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SAGE-Dashboard")

# Configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "sage_docs")

# Embedding configuration (must match ingest settings)
EMBEDDING_MODE = os.getenv("EMBEDDING_MODE", "local")
DENSE_MODEL_NAME = os.getenv("DENSE_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
USE_NOMIC_PREFIX = os.getenv("USE_NOMIC_PREFIX", "false").lower() == "true"

# Global instances
_qdrant_client: Optional[QdrantClient] = None
_dense_model: Optional[TextEmbedding] = None
_bm25_model: Optional[SparseTextEmbedding] = None


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


# Pydantic models for request/response
class SearchRequest(BaseModel):
    query: str
    library: Optional[str] = None
    version: Optional[str] = None
    limit: int = 5
    fusion: str = "dbsf"


class ResolveRequest(BaseModel):
    query: str
    limit: int = 5


class SearchResult(BaseModel):
    content: str
    library: str
    version: str
    title: str
    type: str
    file_path: str
    score: float


class LibraryInfo(BaseModel):
    library: str
    versions: list[str]


class ResolveResult(BaseModel):
    library: str
    doc_count: int
    relevance_score: float
    versions: list[str]


class DocumentResult(BaseModel):
    title: str
    library: str
    version: str
    type: str
    content: str
    chunk_count: int


class ConnectionStatus(BaseModel):
    connected: bool
    host: str
    port: int
    collection: str
    document_count: Optional[int] = None


class UploadResult(BaseModel):
    success: bool
    library: str
    version: str
    files_processed: int
    chunks_indexed: int
    message: str


class DeleteResult(BaseModel):
    success: bool
    library: str
    version: Optional[str]
    chunks_deleted: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler for startup/shutdown."""
    # Startup: preload models and ensure collection
    logger.info("Preloading models...")
    get_dense_model()
    get_bm25_model()
    await ensure_collection(get_qdrant_client())
    logger.info("Models loaded.")
    yield
    # Shutdown
    logger.info("Shutting down...")


app = FastAPI(
    title="SAGE-Docs Dashboard API",
    description="REST API for SAGE-Docs documentation search and upload",
    version="1.0.0",
    lifespan=lifespan
)


# ============================================================
# STATUS & HEALTH ENDPOINTS
# ============================================================

@app.get("/api/status")
async def get_status() -> ConnectionStatus:
    """Check connection status to Qdrant."""
    try:
        client = get_qdrant_client()
        collection_info = client.get_collection(COLLECTION_NAME)
        return ConnectionStatus(
            connected=True,
            host=QDRANT_HOST,
            port=QDRANT_PORT,
            collection=COLLECTION_NAME,
            document_count=collection_info.points_count
        )
    except Exception as e:
        logger.error(f"Connection check failed: {e}")
        return ConnectionStatus(
            connected=False,
            host=QDRANT_HOST,
            port=QDRANT_PORT,
            collection=COLLECTION_NAME
        )


# ============================================================
# UPLOAD ENDPOINTS
# ============================================================

@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    library: str = Form(...),
    version: str = Form(default="latest")
) -> UploadResult:
    """
    Upload a document file to be indexed.
    
    Supports: Markdown (.md), HTML (.html/.htm), Text (.txt), PDF (.pdf), ZIP (archives)
    """
    try:
        client = get_qdrant_client()
        content = await file.read()
        
        result = await ingest_document(
            client=client,
            content=content,
            filename=file.filename,
            library=library,
            version=version
        )
        
        return UploadResult(
            success=True,
            library=result["library"],
            version=result["version"],
            files_processed=result["files_processed"],
            chunks_indexed=result["chunks_indexed"],
            message=f"Successfully indexed {result['chunks_indexed']} chunks from {result['files_processed']} files"
        )
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload-multiple")
async def upload_multiple_documents(
    files: list[UploadFile] = File(...),
    library: str = Form(...),
    version: str = Form(default="latest")
) -> UploadResult:
    """Upload multiple document files to be indexed."""
    try:
        client = get_qdrant_client()
        total_files = 0
        total_chunks = 0
        
        for file in files:
            content = await file.read()
            result = await ingest_document(
                client=client,
                content=content,
                filename=file.filename,
                library=library,
                version=version
            )
            total_files += result["files_processed"]
            total_chunks += result["chunks_indexed"]
        
        return UploadResult(
            success=True,
            library=library,
            version=version,
            files_processed=total_files,
            chunks_indexed=total_chunks,
            message=f"Successfully indexed {total_chunks} chunks from {total_files} files"
        )
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/library/{library}")
async def remove_library(library: str, version: Optional[str] = None) -> DeleteResult:
    """Delete a library (and optionally specific version) from the index."""
    try:
        client = get_qdrant_client()
        deleted_count = await delete_library(client, library, version)
        
        return DeleteResult(
            success=True,
            library=library,
            version=version,
            chunks_deleted=deleted_count
        )
        
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# SEARCH & LIBRARY ENDPOINTS (same as DRUID)
# ============================================================

@app.get("/api/libraries")
async def list_libraries() -> list[LibraryInfo]:
    """List all indexed libraries and their versions."""
    client = get_qdrant_client()
    
    try:
        # Get all unique libraries using facet API
        library_facets = client.facet(
            collection_name=COLLECTION_NAME,
            key="library",
            limit=1000
        )
        
        result = []
        for hit in library_facets.hits:
            lib_name = hit.value
            
            # Get versions for this library
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
            result.append(LibraryInfo(
                library=lib_name,
                versions=sorted(versions, reverse=True)
            ))
        
        return sorted(result, key=lambda x: x.library)
        
    except Exception as e:
        logger.error(f"Failed to list libraries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search")
async def search_docs(request: SearchRequest) -> list[SearchResult]:
    """Search documentation using hybrid semantic + keyword search."""
    client = get_qdrant_client()
    bm25_model = get_bm25_model()
    dense_model = get_dense_model()
    
    # Apply Nomic prefix if needed
    query_for_embed = f"search_query: {request.query}" if USE_NOMIC_PREFIX else request.query
    
    # Generate embeddings
    dense_vector = list(dense_model.embed([query_for_embed]))[0].tolist()
    sparse_embedding = list(bm25_model.embed([request.query]))[0]
    
    # Build filter conditions
    filter_conditions = []
    if request.library:
        filter_conditions.append(
            models.FieldCondition(
                key="library",
                match=models.MatchValue(value=request.library)
            )
        )
    if request.version:
        filter_conditions.append(
            models.FieldCondition(
                key="version",
                match=models.MatchValue(value=request.version)
            )
        )
    
    search_filter = None
    if filter_conditions:
        search_filter = models.Filter(must=filter_conditions)
    
    # Select fusion method
    fusion_type = models.Fusion.DBSF if request.fusion.lower() == "dbsf" else models.Fusion.RRF
    
    try:
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                models.Prefetch(
                    query=dense_vector,
                    using="dense",
                    limit=request.limit * 2
                ),
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sparse_embedding.indices.tolist(),
                        values=sparse_embedding.values.tolist()
                    ),
                    using="sparse",
                    limit=request.limit * 2
                )
            ],
            query=models.FusionQuery(fusion=fusion_type),
            query_filter=search_filter,
            limit=request.limit,
            with_payload=True
        )
        
        formatted = []
        for point in results.points:
            payload = point.payload
            formatted.append(SearchResult(
                content=payload.get("content", ""),
                library=payload.get("library", "unknown"),
                version=payload.get("version", "unknown"),
                title=payload.get("title", ""),
                type=payload.get("type", ""),
                file_path=payload.get("file_path", ""),
                score=point.score
            ))
        
        return formatted
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/resolve")
async def resolve_library(request: ResolveRequest) -> list[ResolveResult]:
    """Find libraries matching a search query."""
    client = get_qdrant_client()
    query_lower = request.query.lower()
    
    try:
        # Get all libraries using facet API
        library_facets = client.facet(
            collection_name=COLLECTION_NAME,
            key="library",
            limit=1000
        )
        
        # Score all libraries
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
        
        # Sort and take top N
        scored.sort(key=lambda x: (-x["relevance_score"], -x["doc_count"]))
        top_matches = scored[:request.limit]
        
        # Fetch versions for top matches
        results = []
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
            results.append(ResolveResult(
                library=match["library"],
                doc_count=match["doc_count"],
                relevance_score=match["relevance_score"],
                versions=sorted([v.value for v in version_facets.hits], reverse=True)
            ))
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to resolve library: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/document")
async def get_document(file_path: str) -> DocumentResult:
    """Get the full content of a specific document by its file path."""
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
            raise HTTPException(status_code=404, detail=f"Document not found: {file_path}")
        
        chunks = sorted(results, key=lambda p: p.payload.get("chunk_index", 0))
        full_content = "\n\n".join(p.payload.get("content", "") for p in chunks)
        first_payload = chunks[0].payload
        
        return DocumentResult(
            title=first_payload.get("title", ""),
            library=first_payload.get("library", "unknown"),
            version=first_payload.get("version", "unknown"),
            type=first_payload.get("type", ""),
            content=full_content,
            chunk_count=len(chunks)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """Serve the main dashboard page."""
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
