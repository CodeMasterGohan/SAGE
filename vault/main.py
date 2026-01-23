"""
SAGE Vault - High-Performance Document Processing Service
==========================================================
Provides async document processing with:
- Tokenizer-based batching for embedding models
- Dynamic batch sizing respecting token limits
- Code-aware semantic chunking
- Support for local and remote (vLLM) embeddings
"""

import os
import logging
import hashlib
import asyncio
import httpx
from pathlib import Path
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models
from fastembed import TextEmbedding, SparseTextEmbedding

# Tokenizer imports
try:
    from tokenizers import Tokenizer
    TOKENIZER_AVAILABLE = True
except ImportError:
    TOKENIZER_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SAGE-Vault")

# Configuration from environment
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "sage_docs")

# Chunking configuration
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "80"))
MAX_CHUNK_CHARS = int(os.getenv("MAX_CHUNK_CHARS", "4000"))

# Embedding configuration
EMBEDDING_MODE = os.getenv("EMBEDDING_MODE", "local")
DENSE_MODEL_NAME = os.getenv("DENSE_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
DENSE_VECTOR_SIZE = int(os.getenv("DENSE_VECTOR_SIZE", "384"))
USE_NOMIC_PREFIX = os.getenv("USE_NOMIC_PREFIX", "false").lower() == "true"

# Remote vLLM configuration
VLLM_EMBEDDING_URL = os.getenv("VLLM_EMBEDDING_URL", "http://localhost:8000")
VLLM_MODEL_NAME = os.getenv("VLLM_MODEL_NAME", "nomic-ai/nomic-embed-text-v1.5")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "")

# Batching configuration
MAX_BATCH_TOKENS = int(os.getenv("MAX_BATCH_TOKENS", "2000"))

# Adaptive concurrency: higher for GPU-backed remote vLLM, lower for local CPU
_DEFAULT_CONCURRENCY = "100" if EMBEDDING_MODE == "remote" else "10"
CONCURRENCY_LIMIT = int(os.getenv("VAULT_CONCURRENCY", _DEFAULT_CONCURRENCY))

# Global model instances (lazy loaded)
_tokenizer: Optional[Tokenizer] = None
_dense_model: Optional[TextEmbedding] = None
_sparse_model: Optional[SparseTextEmbedding] = None


# ============================================================
# TOKENIZER FUNCTIONS
# ============================================================
def get_tokenizer() -> Optional[Tokenizer]:
    """Load BERT tokenizer for token counting (conservative proxy for most models)."""
    global _tokenizer
    if _tokenizer is None and TOKENIZER_AVAILABLE:
        try:
            _tokenizer = Tokenizer.from_pretrained("bert-base-uncased")
            logger.info("Loaded bert-base-uncased tokenizer")
        except Exception as e:
            logger.warning(f"Could not load tokenizer: {e}. Using whitespace fallback.")
    return _tokenizer


def count_tokens(text: str) -> int:
    """Count tokens in text."""
    tokenizer = get_tokenizer()
    if tokenizer:
        return len(tokenizer.encode(text).ids)
    else:
        # Fallback: rough estimate (words * 1.3)
        return int(len(text.split()) * 1.3)


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to maximum token count."""
    tokenizer = get_tokenizer()
    if tokenizer:
        encoded = tokenizer.encode(text)
        if len(encoded.ids) <= max_tokens:
            return text
        truncated_ids = encoded.ids[:max_tokens]
        return tokenizer.decode(truncated_ids)
    else:
        # Fallback: approximate character truncation
        char_limit = int(max_tokens * 2.5)
        if len(text) <= char_limit:
            return text
        return text[:char_limit] + "..."


# ============================================================
# EMBEDDING MODEL FUNCTIONS
# ============================================================
def get_dense_model() -> TextEmbedding:
    """Get or create dense embedding model."""
    global _dense_model
    if _dense_model is None:
        logger.info(f"Loading dense model: {DENSE_MODEL_NAME}")
        _dense_model = TextEmbedding(model_name=DENSE_MODEL_NAME)
    return _dense_model


def get_sparse_model() -> SparseTextEmbedding:
    """Get or create sparse BM25 model."""
    global _sparse_model
    if _sparse_model is None:
        logger.info("Loading sparse BM25 model...")
        _sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    return _sparse_model


async def get_remote_embeddings_async(
    client: httpx.AsyncClient,
    texts: list[str]
) -> list[list[float]]:
    """Get embeddings from remote vLLM server."""
    if not texts:
        return []

    headers = {"Content-Type": "application/json"}
    if VLLM_API_KEY:
        headers["Authorization"] = f"Bearer {VLLM_API_KEY}"

    retries = 3
    for attempt in range(retries):
        try:
            response = await client.post(
                f"{VLLM_EMBEDDING_URL}/v1/embeddings",
                json={"input": texts, "model": VLLM_MODEL_NAME},
                headers=headers,
                timeout=120.0
            )
            response.raise_for_status()
            data = response.json()
            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in sorted_data]
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            if attempt == retries - 1:
                logger.error(f"Remote embedding failed after {retries} attempts: {e}")
                raise
            await asyncio.sleep(1 * (attempt + 1))


# ============================================================
# BATCHING FUNCTIONS
# ============================================================
def yield_safe_batches(chunks_data: list[dict], max_tokens: int = MAX_BATCH_TOKENS):
    """
    Yield batches of chunks respecting token limits.
    Truncates individual chunks if they exceed limits.
    """
    current_batch = []
    current_tokens = 0

    for item in chunks_data:
        text = item["text"]
        # Account for prefix tokens (~5 tokens for "search_document: ")
        item_tokens = count_tokens(text) + 5

        # Truncate if single chunk is too large
        if item_tokens > max_tokens:
            logger.warning(f"Chunk too large ({item_tokens} tokens). Truncating...")
            safe_limit = max_tokens - 10
            item["text"] = truncate_to_tokens(text, safe_limit)
            item_tokens = count_tokens(item["text"]) + 5

        # Start new batch if this would exceed limit
        if current_batch and (current_tokens + item_tokens > max_tokens):
            yield current_batch
            current_batch = []
            current_tokens = 0

        current_batch.append(item)
        current_tokens += item_tokens

    if current_batch:
        yield current_batch


# ============================================================
# CHUNKING FUNCTIONS
# ============================================================
def split_text_semantic(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """
    Split text into chunks with overlap, respecting code blocks and headers.
    """
    import re
    
    # Handle code blocks specially
    code_block_pattern = r'(```[\s\S]*?```)'
    parts = re.split(code_block_pattern, text)
    chunks = []
    current_chunk = ""

    for part in parts:
        is_code_block = part.startswith('```') and part.endswith('```')
        
        if is_code_block:
            if len(part) > MAX_CHUNK_CHARS:
                # Code block too large - split it
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                code_lines = part.split('\n')
                code_chunk = ""
                for line in code_lines:
                    if len(code_chunk) + len(line) > MAX_CHUNK_CHARS and code_chunk:
                        chunks.append(code_chunk.strip())
                        code_chunk = line + "\n"
                    else:
                        code_chunk += line + "\n"
                if code_chunk.strip():
                    chunks.append(code_chunk.strip())
                current_chunk = ""
            elif len(current_chunk) + len(part) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = part
            else:
                current_chunk += "\n" + part
        else:
            # Split by headers
            sections = re.split(r'(\n#{1,4}\s+[^\n]+)', part)
            for section in sections:
                if not section.strip():
                    continue
                    
                is_header = section.strip().startswith('#')
                
                if is_header and current_chunk.strip():
                    chunks.append(current_chunk.strip())
                    current_chunk = section
                elif len(current_chunk) + len(section) > chunk_size:
                    # Split by paragraphs
                    paragraphs = section.split('\n\n')
                    for para in paragraphs:
                        if len(current_chunk) + len(para) > chunk_size and current_chunk:
                            chunks.append(current_chunk.strip())
                            # Keep overlap
                            overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                            current_chunk = overlap_text + "\n\n" + para
                        else:
                            current_chunk += "\n\n" + para
                else:
                    current_chunk += section

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    # Final safety truncation
    safe_chunks = []
    for chunk in chunks:
        if chunk.strip():
            if len(chunk) > MAX_CHUNK_CHARS:
                safe_chunks.append(chunk[:MAX_CHUNK_CHARS - 20] + "\n[truncated]")
            else:
                safe_chunks.append(chunk)
    
    return safe_chunks


# ============================================================
# COLLECTION MANAGEMENT
# ============================================================
def check_collection_exists(client: QdrantClient, collection_name: str) -> bool:
    """Check if collection exists (with fallback for older Qdrant)."""
    try:
        return client.collection_exists(collection_name)
    except Exception:
        try:
            return any(c.name == collection_name for c in client.get_collections().collections)
        except Exception:
            return False


def ensure_collection(client: QdrantClient) -> None:
    """Create collection if it doesn't exist."""
    if check_collection_exists(client, COLLECTION_NAME):
        logger.info(f"Collection {COLLECTION_NAME} exists")
        return

    logger.info(f"Creating collection {COLLECTION_NAME}...")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": models.VectorParams(
                size=DENSE_VECTOR_SIZE,
                distance=models.Distance.COSINE
            )
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(
                index=models.SparseIndexParams(on_disk=False)
            )
        },
        quantization_config=models.ScalarQuantization(
            scalar=models.ScalarQuantizationConfig(
                type=models.ScalarType.INT8,
                always_ram=True
            )
        )
    )

    # Create payload indexes
    for field in ["library", "version", "file_path", "type"]:
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=field,
            field_schema=models.PayloadSchemaType.KEYWORD
        )
    
    logger.info(f"Collection {COLLECTION_NAME} created")


# ============================================================
# MAIN PROCESSING FUNCTION
# ============================================================
async def process_document_async(
    client: QdrantClient,
    content: str,
    filename: str,
    library: str,
    version: str = "latest",
    title: Optional[str] = None,
    file_path: Optional[str] = None
) -> dict:
    """
    Process a document asynchronously with batched embeddings.
    
    Args:
        client: Qdrant client
        content: Markdown/text content to process
        filename: Original filename
        library: Library name
        version: Version string
        title: Optional title (extracted from content if not provided)
        file_path: Optional file path for storage reference
    
    Returns:
        dict with processing statistics
    """
    import time
    start_time = time.time()
    
    # Ensure collection exists
    ensure_collection(client)
    
    # Extract title if not provided
    if not title:
        import re
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = match.group(1).strip() if match else Path(filename).stem
    
    # Split into chunks
    chunks = split_text_semantic(content)
    
    if not chunks:
        return {"chunks_indexed": 0, "duration_seconds": 0}
    
    # Prepare chunk data
    chunks_data = [
        {"text": chunk, "index": i}
        for i, chunk in enumerate(chunks)
    ]
    
    # Generate batches
    if EMBEDDING_MODE == "local":
        batch_size = 32
        chunk_batches = [chunks_data[i:i + batch_size] for i in range(0, len(chunks_data), batch_size)]
    else:
        chunk_batches = list(yield_safe_batches(chunks_data, max_tokens=MAX_BATCH_TOKENS))
    
    logger.info(f"Processing {len(chunks)} chunks in {len(chunk_batches)} batches for {filename}")
    
    # Get models
    sparse_model = get_sparse_model()
    dense_model_local = get_dense_model() if EMBEDDING_MODE == "local" else None
    
    all_points = []
    
    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=CONCURRENCY_LIMIT * 2)
    ) as http_client:
        
        for batch in chunk_batches:
            batch_texts = [item["text"] for item in batch]
            
            # Prepare texts with prefix if needed
            if USE_NOMIC_PREFIX:
                embed_texts = [f"search_document: {t}" for t in batch_texts]
            else:
                embed_texts = batch_texts
            
            # Generate dense embeddings
            if EMBEDDING_MODE == "remote":
                dense_vecs = await get_remote_embeddings_async(http_client, embed_texts)
            else:
                dense_vecs = list(dense_model_local.embed(embed_texts))
            
            # Generate sparse embeddings
            sparse_vecs = list(sparse_model.embed(batch_texts))
            
            # Create points
            for item, dense_vec, sparse_vec in zip(batch, dense_vecs, sparse_vecs):
                chunk_text = item["text"]
                chunk_index = item["index"]
                
                # Create unique ID
                point_id = hashlib.md5(
                    f"{library}:{version}:{filename}:{chunk_index}:{chunk_text[:100]}".encode()
                ).hexdigest()
                
                dense_list = dense_vec if isinstance(dense_vec, list) else dense_vec.tolist()
                
                point = models.PointStruct(
                    id=point_id,
                    vector={
                        "dense": dense_list,
                        "sparse": models.SparseVector(
                            indices=sparse_vec.indices.tolist(),
                            values=sparse_vec.values.tolist()
                        )
                    },
                    payload={
                        "content": chunk_text,
                        "library": library,
                        "version": version,
                        "title": title,
                        "file_path": file_path or filename,
                        "chunk_index": chunk_index,
                        "total_chunks": len(chunks),
                        "type": "document"
                    }
                )
                all_points.append(point)
    
    # Upsert to Qdrant
    if all_points:
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=all_points,
            wait=True
        )
    
    duration = time.time() - start_time
    logger.info(f"Indexed {len(all_points)} chunks for {filename} in {duration:.2f}s")
    
    return {
        "chunks_indexed": len(all_points),
        "duration_seconds": round(duration, 2),
        "library": library,
        "version": version
    }


async def delete_document_async(
    client: QdrantClient,
    library: str,
    version: Optional[str] = None,
    file_path: Optional[str] = None
) -> int:
    """Delete documents matching criteria."""
    filter_conditions = [
        models.FieldCondition(
            key="library",
            match=models.MatchValue(value=library)
        )
    ]
    
    if version:
        filter_conditions.append(
            models.FieldCondition(
                key="version",
                match=models.MatchValue(value=version)
            )
        )
    
    if file_path:
        filter_conditions.append(
            models.FieldCondition(
                key="file_path",
                match=models.MatchValue(value=file_path)
            )
        )
    
    # Count before delete
    count_result = client.count(
        collection_name=COLLECTION_NAME,
        count_filter=models.Filter(must=filter_conditions)
    )
    
    # Delete
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=models.FilterSelector(
            filter=models.Filter(must=filter_conditions)
        )
    )
    
    logger.info(f"Deleted {count_result.count} chunks")
    return count_result.count
