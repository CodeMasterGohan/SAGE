"""
SAGE Core - Text Chunking
=========================
Semantic text chunking with token-aware batching.
"""

import os
import re
import logging
from typing import List, Iterator, Tuple, Dict, Optional

logger = logging.getLogger("SAGE-Core")

# Chunking configuration
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "80"))
MAX_CHUNK_CHARS = int(os.getenv("MAX_CHUNK_CHARS", "4000"))
MAX_BATCH_TOKENS = int(os.getenv("MAX_BATCH_TOKENS", "2000"))
MAX_CHUNK_TOKENS = int(os.getenv("MAX_CHUNK_TOKENS", "500"))

# Tokenizer instance (lazy loaded)
_tokenizer = None


def get_tokenizer():
    """
    Get or create tokenizer for token counting.
    Uses BERT WordPiece tokenizer as a conservative proxy for most embedding models.
    """
    global _tokenizer
    if _tokenizer is None:
        try:
            from tokenizers import Tokenizer
            _tokenizer = Tokenizer.from_pretrained("bert-base-uncased")
            logger.info("Loaded bert-base-uncased tokenizer")
        except Exception as e:
            logger.warning(f"Could not load tokenizer: {e}. Using whitespace fallback.")
    return _tokenizer


def count_tokens(text: str) -> int:
    """Count tokens in text using the tokenizer, or fallback to word count estimate."""
    tokenizer = get_tokenizer()
    if tokenizer:
        return len(tokenizer.encode(text).ids)
    # Fallback: approximate (words * 1.3)
    return int(len(text.split()) * 1.3)


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to a maximum number of tokens."""
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


def yield_safe_batches(
    chunks_data: List[dict],
    max_tokens: int = MAX_BATCH_TOKENS,
    track_warnings: bool = False
) -> Iterator[List[dict]]:
    """
    Yields batches of chunk dicts such that the total token count per batch
    does not exceed max_tokens. Truncates individual chunks if they are too large.
    
    Args:
        chunks_data: List of chunk dicts with 'text' and 'index' keys
        max_tokens: Maximum tokens per batch
        track_warnings: If True, adds 'truncation_warning' to truncated chunks
    
    Returns:
        Iterator of chunk batches
    """
    current_batch = []
    current_tokens = 0

    for item in chunks_data:
        text = item["text"]
        # Account for prefix tokens (~5 tokens for "search_document: ")
        item_tokens = count_tokens(text) + 5
        original_tokens = item_tokens

        # Truncate if single chunk is too large
        if item_tokens > max_tokens:
            logger.warning(f"Chunk too large ({item_tokens} tokens). Truncating...")
            safe_limit = max_tokens - 10
            truncated_text = truncate_to_tokens(text, safe_limit)
            item["text"] = truncated_text
            item_tokens = count_tokens(item["text"]) + 5
            
            # Track warning if requested
            if track_warnings:
                # Extract section title
                header_match = re.search(r'^#+\s+(.+?)$', text, re.MULTILINE)
                section_title = header_match.group(1).strip() if header_match else None
                
                item["truncation_warning"] = {
                    "chunk_index": item.get("index", -1),
                    "original_size": original_tokens - 5,  # Remove prefix overhead
                    "truncated_size": item_tokens - 5,
                    "truncation_type": "token",
                    "section_title": section_title
                }

        # Start new batch if this would exceed limit
        if current_batch and (current_tokens + item_tokens > max_tokens):
            yield current_batch
            current_batch = []
            current_tokens = 0

        current_batch.append(item)
        current_tokens += item_tokens

    if current_batch:
        yield current_batch


def split_text_semantic(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP
) -> List[str]:
    """
    Split text into chunks with overlap, respecting code blocks and markdown headers.
    
    This is the unified chunking logic used across all SAGE services.
    """
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


def process_markdown_chunks(text: str) -> Tuple[List[str], List[Dict]]:
    """
    Process markdown text into chunks and track truncation warnings.
    
    This is the enhanced version of split_text_semantic that returns both
    chunks and a list of truncation warnings for user feedback.
    
    Args:
        text: Markdown text to chunk
    
    Returns:
        Tuple of (chunks, truncation_warnings)
        - chunks: List of text chunks
        - truncation_warnings: List of dicts with truncation details
    
    Each warning dict contains:
        - chunk_index: int - Index of the affected chunk
        - original_size: int - Original size (chars or tokens)
        - truncated_size: int - Size after truncation
        - truncation_type: str - "character" or "token"
        - section_title: Optional[str] - Section title if available
    """
    truncation_warnings = []
    
    # Handle code blocks specially
    code_block_pattern = r'(```[\s\S]*?```)'
    parts = re.split(code_block_pattern, text)
    chunks = []
    current_chunk = ""
    current_section_title = None

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
            elif len(current_chunk) + len(part) > CHUNK_SIZE and current_chunk:
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

                # Extract section title from header
                if is_header:
                    header_match = re.match(r'#+\s+(.+)', section.strip())
                    if header_match:
                        current_section_title = header_match.group(1).strip()

                if is_header and current_chunk.strip():
                    chunks.append(current_chunk.strip())
                    current_chunk = section
                elif len(current_chunk) + len(section) > CHUNK_SIZE:
                    # Split by paragraphs
                    paragraphs = section.split('\n\n')
                    for para in paragraphs:
                        if len(current_chunk) + len(para) > CHUNK_SIZE and current_chunk:
                            chunks.append(current_chunk.strip())
                            # Keep overlap
                            overlap_text = current_chunk[-CHUNK_OVERLAP:] if len(current_chunk) > CHUNK_OVERLAP else current_chunk
                            current_chunk = overlap_text + "\n\n" + para
                        else:
                            current_chunk += "\n\n" + para
                else:
                    current_chunk += section

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    # Final safety truncation with warning tracking
    safe_chunks = []
    for idx, chunk in enumerate(chunks):
        if chunk.strip():
            original_length = len(chunk)
            
            # Extract section title for this chunk
            header_match = re.search(r'^#+\s+(.+?)$', chunk, re.MULTILINE)
            section_title = header_match.group(1).strip() if header_match else None
            
            if len(chunk) > MAX_CHUNK_CHARS:
                # Character truncation
                truncated_chunk = chunk[:MAX_CHUNK_CHARS - 20] + "\n[truncated]"
                safe_chunks.append(truncated_chunk)
                
                # Record warning
                truncation_warnings.append({
                    "chunk_index": idx,
                    "original_size": original_length,
                    "truncated_size": MAX_CHUNK_CHARS - 20,
                    "truncation_type": "character",
                    "section_title": section_title
                })
                
                logger.warning(
                    f"Chunk {idx} truncated: {original_length} chars -> {MAX_CHUNK_CHARS - 20} chars"
                    f" (section: {section_title or 'unknown'})"
                )
            else:
                safe_chunks.append(chunk)

    return safe_chunks, truncation_warnings

