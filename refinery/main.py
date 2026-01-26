"""
SAGE Refinery - Document Ingestion Service
==========================================
Legacy document processing service.

REFACTORED: Now uses unified sage_core ingestion pipeline.
All ingestion logic has been consolidated into sage_core for consistency.
"""

import sys
from pathlib import Path
import os

# Add project root (containing `sage_core` or `pyproject.toml`) to sys.path so imports work inside Docker
def _add_project_root_to_path():
    p = Path(__file__).resolve()
    for _ in range(6):
        if (p / "sage_core").exists() or (p / "pyproject.toml").exists():
            root = p
            sys.path.insert(0, str(root))
            return
        p = p.parent
    # Fallback to current working directory
    sys.path.insert(0, str(Path.cwd()))

_add_project_root_to_path()

import logging
import time
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
import uvicorn

from qdrant_client import QdrantClient

# Import unified functions from sage_core
from sage_core import ingest_document
from sage_core.qdrant_utils import (
    get_qdrant_client,
    ensure_collection,
    delete_library,
    COLLECTION_NAME
)
from sage_core.file_processing import detect_file_type, process_file, process_zip

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SAGE-Refinery")

# ============================================================
# FASTAPI SERVICE (Minimal)
# ============================================================

_server_start_time = time.time()

app = FastAPI(
    title="SAGE-Docs Refinery",
    description="Document ingestion service backed by sage_core",
    version="1.0.0"
)


@app.on_event("startup")
def _startup() -> None:
    """Ensure Qdrant collection exists on startup."""
    try:
        client = get_qdrant_client()
        ensure_collection(client)
        logger.info("Refinery startup complete")
    except Exception as exc:
        logger.error(f"Refinery startup failed: {exc}")


@app.get("/health")
def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - _server_start_time, 2)
    }


@app.post("/ingest")
async def ingest_endpoint(
    library: str = Form(...),
    version: str = Form("latest"),
    file: UploadFile = File(...)
) -> dict:
    """Ingest a document via multipart upload."""
    try:
        content = await file.read()
        client = get_qdrant_client()
        result = await ingest_document_refinery(
            content=content,
            filename=file.filename or "uploaded_file",
            library=library,
            version=version,
            client=client
        )
        return result
    except Exception as exc:
        logger.error(f"Refinery ingest failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================
# MAIN INGESTION FUNCTIONS
# ============================================================
async def ingest_document_refinery(
    content: bytes,
    filename: str,
    library: str,
    version: str = "latest",
    client: Optional[QdrantClient] = None
) -> dict:
    """
    Ingest a document using the unified sage_core pipeline.
    
    This is a thin wrapper around sage_core.ingestion.ingest_document
    for backwards compatibility with existing refinery code.
    
    Args:
        content: Raw file bytes
        filename: Original filename
        library: Library/collection name
        version: Version identifier
        client: Optional Qdrant client (creates one if not provided)
    
    Returns:
        dict: {
            "library": str,
            "version": str,
            "files_processed": int,
            "chunks_indexed": int,
            "duration_seconds": float
        }
    """
    logger.info(f"Refinery ingesting: {filename} for {library} v{version}")
    
    return await ingest_document(
        content=content,
        filename=filename,
        library=library,
        version=version,
        client=client
    )


async def delete_library_refinery(
    library: str,
    version: Optional[str] = None,
    client: Optional[QdrantClient] = None
) -> int:
    """
    Delete a library (and optionally specific version) from the index.
    
    Args:
        library: Library name
        version: Optional version filter
        client: Optional Qdrant client
    
    Returns:
        Number of chunks deleted
    """
    logger.info(f"Refinery deleting: library={library} version={version}")
    
    if client is None:
        client = get_qdrant_client()
    
    return delete_library(client, library, version)


# Expose functions for external use
__all__ = [
    'ingest_document_refinery',
    'delete_library_refinery',
    'get_qdrant_client',
    'ensure_collection'
]


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
