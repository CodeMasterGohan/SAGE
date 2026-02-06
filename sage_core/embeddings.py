"""
SAGE Core - Embedding Helpers
=============================
Unified embedding model management for local and remote embeddings.
"""

import os
import logging
import asyncio
from typing import List

import httpx

logger = logging.getLogger("SAGE-Core")

# Embedding configuration
EMBEDDING_MODE = os.getenv("EMBEDDING_MODE", "local")
DENSE_MODEL_NAME = os.getenv("DENSE_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
DENSE_VECTOR_SIZE = int(os.getenv("DENSE_VECTOR_SIZE", "384"))
USE_NOMIC_PREFIX = os.getenv("USE_NOMIC_PREFIX", "false").lower() == "true"

# Remote vLLM configuration
VLLM_EMBEDDING_URL = os.getenv("VLLM_EMBEDDING_URL", "http://localhost:8000")
VLLM_MODEL_NAME = os.getenv("VLLM_MODEL_NAME", "nomic-ai/nomic-embed-text-v1.5")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "")

# Global model instances (lazy loaded)
_dense_model = None
_sparse_model = None
_tokenizer = None
_http_client = None


def get_tokenizer():
    """Get or create tokenizer for token counting."""
    global _tokenizer
    if _tokenizer is None:
        try:
            from tokenizers import Tokenizer
            _tokenizer = Tokenizer.from_pretrained("bert-base-uncased")
            logger.info("Loaded bert-base-uncased tokenizer")
        except Exception as e:
            logger.warning(f"Could not load tokenizer: {e}")
    return _tokenizer


def get_dense_model():
    """Get or create dense embedding model."""
    global _dense_model
    if _dense_model is None:
        from fastembed import TextEmbedding
        logger.info(f"Loading dense model: {DENSE_MODEL_NAME}")
        _dense_model = TextEmbedding(model_name=DENSE_MODEL_NAME)
    return _dense_model


def get_sparse_model():
    """Get or create sparse BM25 model."""
    global _sparse_model
    if _sparse_model is None:
        from fastembed import SparseTextEmbedding
        logger.info("Loading sparse BM25 model...")
        _sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    return _sparse_model


def get_http_client() -> httpx.AsyncClient:
    """Get or create global HTTP client with connection pooling."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0),
            limits=httpx.Limits(max_connections=100)
        )
    return _http_client


async def get_remote_embedding(text: str) -> List[float]:
    """Get embedding from remote vLLM server using persistent connection."""
    client = get_http_client()

    headers = {"Content-Type": "application/json"}
    if VLLM_API_KEY:
        headers["Authorization"] = f"Bearer {VLLM_API_KEY}"

    response = await client.post(
        f"{VLLM_EMBEDDING_URL}/v1/embeddings",
        json={"input": [text], "model": VLLM_MODEL_NAME},
        headers=headers
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


def is_transient_error(error: Exception) -> bool:
    """
    Determine if an error is transient (should retry) or permanent (fail immediately).
    
    Transient errors:
    - Network timeouts/connection errors
    - Rate limits (429)
    - Temporary service unavailability (503)
    
    Permanent errors:
    - Authentication failures (401)
    - Invalid requests (400)
    - Not found (404)
    """
    if isinstance(error, httpx.RequestError):
        # Network errors are transient
        return True
    
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        # 429 (rate limit), 503 (service unavailable) are transient
        if status_code in [429, 503, 502, 504]:
            return True
        # 401 (auth), 400 (bad request), 404 (not found) are permanent
        if status_code in [401, 400, 404, 403]:
            return False
        # Other 5xx errors might be transient
        if 500 <= status_code < 600:
            return True
    
    return False


async def get_remote_embeddings_async(
    client: httpx.AsyncClient,
    texts: List[str]
) -> List[List[float]]:
    """Get embeddings from remote vLLM server for a batch of texts."""
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


async def get_remote_embeddings_async_with_retry(
    client: httpx.AsyncClient,
    texts: List[str],
    max_retries: int = 3
) -> List[List[float]]:
    """
    Get embeddings from remote vLLM server with intelligent retry logic.
    
    Distinguishes between transient and permanent errors:
    - Transient errors (network issues, rate limits) trigger exponential backoff
    - Permanent errors (auth failures, invalid input) fail immediately
    
    Args:
        client: HTTP client instance
        texts: List of texts to embed
        max_retries: Maximum number of retry attempts (default: 3)
    
    Returns:
        List of embedding vectors
    
    Raises:
        Exception: If all retries exhausted or permanent error encountered
    """
    if not texts:
        return []

    headers = {"Content-Type": "application/json"}
    if VLLM_API_KEY:
        headers["Authorization"] = f"Bearer {VLLM_API_KEY}"

    for attempt in range(max_retries):
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
            
        except Exception as e:
            # Check if error is transient
            if not is_transient_error(e):
                logger.error(f"Permanent error in embedding generation: {e}")
                raise  # Fail immediately for permanent errors
            
            # For transient errors, retry with exponential backoff
            if attempt == max_retries - 1:
                logger.error(f"Remote embedding failed after {max_retries} attempts: {e}")
                raise
            
            # Exponential backoff: 1s, 2s, 4s
            delay = 2 ** attempt
            logger.warning(f"Transient error in embedding (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay)


def close_http_client():
    """Close the HTTP client. Call during shutdown."""
    global _http_client
    if _http_client:
        asyncio.create_task(_http_client.aclose())
        _http_client = None
