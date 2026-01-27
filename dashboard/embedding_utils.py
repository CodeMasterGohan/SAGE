"""
Shared utility for remote embedding generation.
"""

import os
import logging
import asyncio
import httpx
from typing import Optional, List

logger = logging.getLogger("SAGE-Dashboard-Embedding")

# Configuration
VLLM_EMBEDDING_URL = os.getenv("VLLM_EMBEDDING_URL", "http://localhost:8000")
VLLM_MODEL_NAME = os.getenv("VLLM_MODEL_NAME", "nomic-ai/nomic-embed-text-v1.5")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "")

_http_client: Optional[httpx.AsyncClient] = None

async def get_http_client() -> httpx.AsyncClient:
    """Get or create global HTTP client with connection pooling."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            timeout=30.0
        )
    return _http_client

async def get_remote_embeddings_async(texts: List[str]) -> List[List[float]]:
    """Get embeddings from remote vLLM server using persistent connection."""
    if not texts:
        return []

    client = await get_http_client()
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
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            # Ensure order is preserved
            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in sorted_data]
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            if attempt == retries - 1:
                logger.error(f"Remote embedding failed after {retries} attempts: {e}")
                raise
            await asyncio.sleep(0.5 * (attempt + 1))
    return []

async def close_http_client():
    """Close the global HTTP client."""
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
