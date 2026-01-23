"""
SAGE MCP Middleware (Agent Guardian)
=====================================
Manages session context and handles ambiguous queries for autonomous agents.

Optimizations:
- TTL-based caching of library list (5 min) to reduce Qdrant round-trips
- Hybrid alias resolution: hardcoded short aliases + dynamic prefix matching
"""

import asyncio
import logging
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor
from async_lru import alru_cache

logger = logging.getLogger("SAGE-MCP")

# Shared executor for async operations
_executor = ThreadPoolExecutor(max_workers=10)

# Cache TTL in seconds (5 minutes)
_LIBRARY_CACHE_TTL = 300


class SmartContextManager:
    """
    Manages session context to keep Agents grounded.
    
    Features:
    - Sticky sessions: Remembers last active library per session.
    - Explicit overrides: Allows agents to force a specific library.
    - Global escape hatch: Clears session on GLOBAL/wildcard requests.
    """
    
    def __init__(self):
        # Maps session_id (or default) to last_active_library
        # Using a simple dict for now; in prod, use Redis or similar.
        self._sessions: Dict[str, str] = {}

    def get_context(self, session_id: str = "default") -> Optional[str]:
        """Get the current active library for a session."""
        return self._sessions.get(session_id)

    def update_context(self, library: str, session_id: str = "default"):
        """Update the session's active library."""
        if library and library != "GLOBAL":
            self._sessions[session_id] = library
            logger.info(f"Session '{session_id}' context updated to: {library}")

    def clear_context(self, session_id: str = "default"):
        """Clear the session's active library (for global searches)."""
        if session_id in self._sessions:
            del self._sessions[session_id]


# ============================================================
# Module-Level Cached Library Fetcher
# ============================================================

@alru_cache(maxsize=16, ttl=_LIBRARY_CACHE_TTL)
async def _fetch_known_libraries(get_client_fn, collection_name: str) -> List[str]:
    """
    Fetch known libraries from Qdrant with TTL-based caching.
    
    This is a module-level function (not a method) so the cache is shared
    across all AmbiguityHandler instances and persists for the server lifetime.
    
    Args:
        get_client_fn: Callable that returns a QdrantClient
        collection_name: Name of the Qdrant collection
        
    Returns:
        List of library names found in the collection
    """
    client = get_client_fn()
    loop = asyncio.get_running_loop()
    
    try:
        # Use simple faceting to get available libraries
        library_facets = await loop.run_in_executor(
            _executor,
            lambda: client.facet(
                collection_name=collection_name,
                key="library",  # SAGE uses "library" at top level payload? CHECK THIS. 
                                # DRUID used "metadata.library". SAGE main.py uses "library".
                limit=1000
            )
        )
        libraries = [hit.value for hit in library_facets.hits]
        logger.info(f"Cached {len(libraries)} libraries (TTL: {_LIBRARY_CACHE_TTL}s)")
        return libraries
    except Exception as e:
        logger.error(f"Failed to fetch known libraries: {e}")
        return []

class AmbiguityHandler:
    """
    Detects and handles ambiguous queries (multiple libraries).
    
    Example: "React vs Vue" -> Detects both libraries for multi-search.
    
    Features:
    - TTL-cached library list (5 min) to reduce repeated Qdrant queries
    - Hybrid alias resolution: hardcoded short aliases + dynamic prefix matching
    - Substring matching: "using react" -> detects "react"
    """
    
    # Common library aliases (alias -> canonical name)
    # These handle short abbreviations that can't be inferred via prefix matching
    LIBRARY_ALIASES: Dict[str, str] = {
        "tailwind": "tailwindcss",
        "tw": "tailwindcss",
        "postgres": "postgresql",
        "pg": "postgresql",
        "js": "javascript",
        "ts": "typescript",
        "py": "python",
        "node": "nodejs",
        "mongo": "mongodb",
        "k8s": "kubernetes",
        "tf": "terraform",
        "vue": "vuejs",
        "next": "nextjs",
        "nuxt": "nuxtjs",
        "pd": "pandas",
        "np": "numpy",
        "plt": "matplotlib",
        "sk": "scikit-learn",
    }

    def __init__(self, get_qdrant_client_fn, collection_name: str):
        """
        Args:
            get_qdrant_client_fn: Callable that returns a QdrantClient.
            collection_name: Name of the Qdrant collection.
        """
        self._get_client = get_qdrant_client_fn
        self._collection_name = collection_name

    async def _get_known_libraries(self) -> List[str]:
        """
        Fetch known libraries with TTL caching.
        Uses module-level cache to share across instances.
        """
        return await _fetch_known_libraries(
            self._get_client, 
            self._collection_name
        )


    def resolve_alias(self, name: str, known_libraries: List[str]) -> Optional[str]:
        """
        Resolve a library name/alias to a canonical name.
        
        1. Check if name is a known library directly
        2. Check if name is an alias
        3. Check if name is a prefix of a known library (fuzzy match)
        """
        name_lower = name.lower()
        known_lower = {lib.lower(): lib for lib in known_libraries}
        
        # Direct match
        if name_lower in known_lower:
            return known_lower[name_lower]
        
        # Alias match
        if name_lower in self.LIBRARY_ALIASES:
            canonical = self.LIBRARY_ALIASES[name_lower]
            if canonical.lower() in known_lower:
                return known_lower[canonical.lower()]
        
        # Prefix/fuzzy match (e.g., "tailwind" matches "tailwindcss")
        for lib_lower, lib_original in known_lower.items():
            if lib_lower.startswith(name_lower) or name_lower.startswith(lib_lower):
                return lib_original
        
        return None

    async def detect_libraries(self, query: str) -> List[str]:
        """
        Scans query for known libraries.
        Returns a list of library names found in the query.
        """
        query_lower = query.lower()
        known_libraries = await self._get_known_libraries()
        known_lower = {lib.lower(): lib for lib in known_libraries}
        
        detected = set()  # Use set to avoid duplicates
        
        try:
            # 1. Check for known library names in query
            for lib_lower, lib_original in known_lower.items():
                if lib_lower in query_lower:
                    detected.add(lib_original)
            
            # 2. Check for aliases in query
            for alias, canonical in self.LIBRARY_ALIASES.items():
                if alias in query_lower:
                    # Resolve the canonical name to actual DB name
                    resolved = self.resolve_alias(canonical, known_libraries)
                    if resolved:
                        detected.add(resolved)
            
            return list(detected)
        except Exception as e:
            logger.error(f"Ambiguity detection failed: {e}")
            return []


# Global singleton instances (initialized lazily in main.py)
context_manager = SmartContextManager()
