"""
SAGE Refinery - Document Ingestion Service
==========================================
Legacy document processing service.

REFACTORED: Now uses unified sage_core ingestion pipeline.
All ingestion logic has been consolidated into sage_core for consistency.
"""

import sys
from pathlib import Path

# Add sage_core to path
SAGE_CORE_PATH = Path(__file__).parent.parent / "sage_core"
if str(SAGE_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(SAGE_CORE_PATH))

import logging
from typing import Optional

from qdrant_client import QdrantClient

# Import unified functions from sage_core
from ingestion import ingest_document
from qdrant_utils import (
    get_qdrant_client,
    ensure_collection,
    delete_library,
    COLLECTION_NAME,
    UPLOAD_DIR
)
from file_processing import detect_file_type, process_file, process_zip

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SAGE-Refinery")


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
