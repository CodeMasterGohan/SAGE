# SAGE Core - Shared Library
"""
SAGE Core Package
=================
Shared functionality for all SAGE services:
- Document ingestion (unified pipeline)
- Document chunking
- Embedding helpers
- Qdrant utilities
- File processing
"""

from sage_core.ingestion import ingest_document, save_uploaded_file
from sage_core.chunking import split_text_semantic, count_tokens, truncate_to_tokens, yield_safe_batches
from sage_core.embeddings import (
    get_dense_model,
    get_sparse_model,
    get_tokenizer,
    get_remote_embeddings_async,
)
from sage_core.qdrant_utils import (
    get_qdrant_client,
    ensure_collection,
    delete_library,
    check_collection_exists,
    COLLECTION_NAME,
)
from sage_core.file_processing import (
    detect_file_type,
    convert_html_to_markdown,
    extract_pdf_text,
    extract_docx_text,
    extract_excel_text,
    process_file,
    process_zip,
    extract_title_from_content,
)
from sage_core.validation import (
    validate_upload,
    MAX_FILE_SIZE,
    MAX_ZIP_ENTRIES,
    ALLOWED_EXTENSIONS,
)

__version__ = "1.0.0"
__all__ = [
    # Ingestion (NEW - unified pipeline)
    "ingest_document",
    "save_uploaded_file",
    # Chunking
    "split_text_semantic",
    "count_tokens",
    "truncate_to_tokens",
    "yield_safe_batches",
    # Embeddings
    "get_dense_model",
    "get_sparse_model",
    "get_tokenizer",
    "get_remote_embeddings_async",
    # Qdrant
    "get_qdrant_client",
    "ensure_collection",
    "delete_library",
    "check_collection_exists",
    "COLLECTION_NAME",
    # File processing
    "detect_file_type",
    "convert_html_to_markdown",
    "extract_pdf_text",
    "extract_docx_text",
    "extract_excel_text",
    "extract_title_from_content",
    "process_file",
    "process_zip",
    # Validation
    "validate_upload",
    "MAX_FILE_SIZE",
    "MAX_ZIP_ENTRIES",
    "ALLOWED_EXTENSIONS",
]
