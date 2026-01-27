"""
SAGE-Docs Dashboard Backend
===========================
FastAPI server that provides REST API endpoints for the SAGE-Docs web dashboard.
Extends DRUID's dashboard pattern with document upload capabilities.
"""

import os
import logging
import uuid
import threading
from typing import Optional, Annotated
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
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

# Global checks for startup/shutdown only - not for direct use
_qdrant_client: Optional[QdrantClient] = None
_dense_model: Optional[TextEmbedding] = None
_bm25_model: Optional[SparseTextEmbedding] = None


def get_qdrant_client() -> QdrantClient:
    """Dependency for getting Qdrant client."""
    global _qdrant_client
    if _qdrant_client is None:
        logger.info(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")
        _qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    return _qdrant_client


def get_dense_model() -> TextEmbedding:
    """Dependency for getting dense embedding model."""
    global _dense_model
    if _dense_model is None:
        logger.info(f"Loading embedding model ({DENSE_MODEL_NAME})...")
        _dense_model = TextEmbedding(model_name=DENSE_MODEL_NAME)
    return _dense_model


def get_bm25_model() -> SparseTextEmbedding:
    """Dependency for getting BM25 sparse embedding model."""
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


class AsyncUploadStarted(BaseModel):
    task_id: str
    message: str


class UploadStatus(BaseModel):
    task_id: str
    status: str  # "pending", "processing", "completed", "failed"
    progress: Optional[str] = None
    result: Optional[UploadResult] = None
    error: Optional[str] = None


class DeleteResult(BaseModel):
    success: bool
    library: str
    version: Optional[str]
    chunks_deleted: int


# In-memory task storage for background uploads
_upload_tasks: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler for startup/shutdown."""
    # Startup: preload models and ensure collection
    logger.info("Preloading models...")
    get_dense_model()
    get_bm25_model()
    client = get_qdrant_client()
    ensure_collection(client)
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
def get_status(
    client: Annotated[QdrantClient, Depends(get_qdrant_client)]
) -> ConnectionStatus:
    """Check connection status to Qdrant."""
    try:
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
    version: str = Form(default="latest"),
    client: QdrantClient = Depends(get_qdrant_client)
) -> UploadResult:
    """
    Upload a document file to be indexed.
    
    Supports: Markdown (.md), HTML (.html/.htm), Text (.txt), PDF (.pdf), ZIP (archives)
    """
    try:
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
    version: str = Form(default="latest"),
    client: QdrantClient = Depends(get_qdrant_client)
) -> UploadResult:
    """Upload multiple document files to be indexed."""
    try:
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


def _process_upload_background(task_id: str, content: bytes, filename: str, library: str, version: str):
    """Background worker for processing uploads (runs in separate thread)."""
    import asyncio
    
    def run_async():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            _upload_tasks[task_id]["status"] = "processing"
            _upload_tasks[task_id]["progress"] = "Converting document..."
            
            # Note: Background tasks need their own client instance or thread-safe handling
            # Ideally we pass a factory or handle this better, but for now we re-instantiate or use global if safe
            # Since get_qdrant_client is now async and uses global, we might need a sync wrapper or use sync client for thread
            # For simplicity in this refactor, we'll create a new client for the thread
            client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
            result = loop.run_until_complete(ingest_document(
                client=client,
                content=content,
                filename=filename,
                library=library,
                version=version
            ))
            
            _upload_tasks[task_id]["status"] = "completed"
            _upload_tasks[task_id]["progress"] = "Complete"
            _upload_tasks[task_id]["result"] = UploadResult(
                success=True,
                library=result["library"],
                version=result["version"],
                files_processed=result["files_processed"],
                chunks_indexed=result["chunks_indexed"],
                message=f"Successfully indexed {result['chunks_indexed']} chunks"
            )
        except Exception as e:
            logger.error(f"Background upload failed: {e}")
            _upload_tasks[task_id]["status"] = "failed"
            _upload_tasks[task_id]["error"] = str(e)
        finally:
            loop.close()
    
    run_async()


@app.post("/api/upload/async")
async def upload_document_async(
    file: UploadFile = File(...),
    library: str = Form(...),
    version: str = Form(default="latest")
) -> AsyncUploadStarted:
    """
    Upload a document for async processing.
    
    Use this for large PDFs which may take a while to process.
    Returns a task_id to poll for status.
    """
    content = await file.read()
    task_id = str(uuid.uuid4())
    
    # Initialize task
    _upload_tasks[task_id] = {
        "status": "pending",
        "progress": "Queued for processing",
        "filename": file.filename,
        "library": library,
        "version": version,
        "result": None,
        "error": None
    }
    
    # Start background thread
    thread = threading.Thread(
        target=_process_upload_background,
        args=(task_id, content, file.filename, library, version)
    )
    thread.start()
    
    return AsyncUploadStarted(
        task_id=task_id,
        message=f"Upload queued. PDF files may take a while to process. You can close this page."
    )


@app.get("/api/upload/status/{task_id}")
async def get_upload_status(task_id: str) -> UploadStatus:
    """Get the status of an async upload task."""
    if task_id not in _upload_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = _upload_tasks[task_id]
    return UploadStatus(
        task_id=task_id,
        status=task["status"],
        progress=task.get("progress"),
        result=task.get("result"),
        error=task.get("error")
    )


@app.delete("/api/library/{library}")
def remove_library(
    library: str, 
    version: Optional[str] = None,
    client: QdrantClient = Depends(get_qdrant_client)
) -> DeleteResult:
    """Delete a library (and optionally specific version) from the index."""
    try:
        deleted_count = delete_library(client, library, version)
        
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
def list_libraries(
    client: QdrantClient = Depends(get_qdrant_client)
) -> list[LibraryInfo]:
    """List all indexed libraries and their versions.
    
    Optimized: Uses 2 facet queries instead of N+1 (one per library).
    """
    
    try:
        # Query 1: Get all unique libraries
        library_facets = client.facet(
            collection_name=COLLECTION_NAME,
            key="library",
            limit=1000
        )
        
        if not library_facets.hits:
            return []
        
        # Query 2: Get ALL versions in a single call (no filter)
        # This avoids N separate queries for each library
        version_facets = client.facet(
            collection_name=COLLECTION_NAME,
            key="version",
            limit=1000
        )
        
        # Build library-version mapping using scroll with minimal payload
        # We need to know which versions belong to which libraries
        # Scroll a sample of points to build the mapping efficiently
        library_versions: dict[str, set[str]] = {hit.value: set() for hit in library_facets.hits}
        
        # Use scroll to get library-version pairs with minimal data
        results, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=2000,  # Reasonable batch
            with_payload=["library", "version"],
            with_vectors=False
        )
        
        for point in results:
            lib = point.payload.get("library")
            ver = point.payload.get("version")
            if lib in library_versions and ver:
                library_versions[lib].add(ver)
        
        # While there are more results, continue scrolling
        while next_offset and len(results) == 2000:
            results, next_offset = client.scroll(
                collection_name=COLLECTION_NAME,
                offset=next_offset,
                limit=2000,
                with_payload=["library", "version"],
                with_vectors=False
            )
            for point in results:
                lib = point.payload.get("library")
                ver = point.payload.get("version")
                if lib in library_versions and ver:
                    library_versions[lib].add(ver)
        
        # Build result
        result = []
        for hit in library_facets.hits:
            lib_name = hit.value
            versions = sorted(library_versions.get(lib_name, set()), reverse=True)
            result.append(LibraryInfo(
                library=lib_name,
                versions=versions
            ))
        
        return sorted(result, key=lambda x: x.library)
        
    except Exception as e:
        logger.error(f"Failed to list libraries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search")
def search_docs(
    request: SearchRequest,
    client: QdrantClient = Depends(get_qdrant_client),
    bm25_model: SparseTextEmbedding = Depends(get_bm25_model),
    dense_model: TextEmbedding = Depends(get_dense_model)
) -> list[SearchResult]:
    """Search documentation using hybrid semantic + keyword search."""
    
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
def resolve_library(
    request: ResolveRequest,
    client: QdrantClient = Depends(get_qdrant_client)
) -> list[ResolveResult]:
    """Find libraries matching a search query.
    
    Optimized: Fetches versions for top matches in a single scroll query.
    """
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
        
        if not top_matches:
            return []
        
        # Build version map for top matches only (batch approach)
        # Use filter to limit scroll to matched libraries
        top_lib_names = {m["library"] for m in top_matches}
        library_versions: dict[str, set[str]] = {lib: set() for lib in top_lib_names}
        
        # Single scroll query with filter for matched libraries
        scroll_filter = models.Filter(
            should=[
                models.FieldCondition(
                    key="library",
                    match=models.MatchValue(value=lib_name)
                )
                for lib_name in top_lib_names
            ]
        )
        
        results, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=scroll_filter,
            limit=1000,
            with_payload=["library", "version"],
            with_vectors=False
        )
        
        for point in results:
            lib = point.payload.get("library")
            ver = point.payload.get("version")
            if lib in library_versions and ver:
                library_versions[lib].add(ver)
        
        # Build final results
        results = []
        for match in top_matches:
            lib_name = match["library"]
            versions = sorted(library_versions.get(lib_name, set()), reverse=True)[:10]
            results.append(ResolveResult(
                library=lib_name,
                doc_count=match["doc_count"],
                relevance_score=match["relevance_score"],
                versions=versions
            ))
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to resolve library: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/document")
def get_document(
    file_path: str,
    client: QdrantClient = Depends(get_qdrant_client)
) -> DocumentResult:
    """Get the full content of a specific document by its file path."""
    
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
