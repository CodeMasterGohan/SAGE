# Known Issues and Limitations

**Last Updated:** February 5, 2026  
**Version:** Post-Phase 7

---

## 🔴 High Priority

### 1. Test Environment Configuration

**Issue:** Integration tests fail when run on host system outside Docker.

**Symptoms:**
```bash
PermissionError: [Errno 13] Permission denied: '/app'
```

**Cause:**
- `UPLOAD_DIR` is set to `/app/uploads` (Docker container path)
- Tests run on host system don't have access to `/app` directory
- Test fixture `setup_upload_dir` tries to monkeypatch but UPLOAD_DIR is evaluated at module import time

**Impact:**
- 10 tests fail when running `pytest` on host
- All core functionality works perfectly in Docker
- Production deployment unaffected

**Affected Tests:**
- `tests/test_integration_full_pipeline.py` (7/8 tests)
- `tests/test_regression.py` (2/14 tests)
- `tests/test_vault_removal.py` (1/4 tests)

**Workarounds:**
```bash
# Option 1: Run tests in Docker (recommended)
docker-compose exec dashboard pytest tests/

# Option 2: Set UPLOAD_DIR before running tests
export UPLOAD_DIR=/tmp/sage-uploads && pytest tests/

# Option 3: Use temporary directory
mkdir -p /tmp/test-uploads && UPLOAD_DIR=/tmp/test-uploads pytest tests/
```

**Permanent Fix Required:**
- Make `UPLOAD_DIR` lazy-evaluated (load at function call time, not import time)
- OR configure pytest to set environment before module imports
- OR update test fixtures to properly monkeypatch before imports

**Priority:** High (blocks host-based testing)  
**Timeline:** Should fix before next development cycle  
**Production Impact:** None (only affects development/testing)

---

## 🟡 Medium Priority

### 2. Documentation Vault Reference

**Issue:** Developer documentation still contains one reference to removed vault service.

**Location:** `docs/03-Developer-Internals.md` (architecture section)

**Impact:**
- Confusing for new developers
- Test `test_vault_removal.py::test_developer_docs_no_vault_references` fails
- Documentation inconsistency

**Workaround:** None needed - doesn't affect functionality

**Fix Required:**
- Search for "vault" in `docs/03-Developer-Internals.md`
- Remove or update the reference
- Verify test passes

**Priority:** Medium (documentation quality)  
**Timeline:** Can fix anytime  
**Production Impact:** None

---

### 3. Pytest Coroutine Warnings

**Issue:** 2 warnings about unawaited coroutines in PDF processing tests.

**Symptoms:**
```
RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
```

**Cause:**
- Mock objects in async tests not properly awaited
- Affects `test_extract_pdf_text_async_timeout` and `test_async_maintains_timeout_behavior`

**Impact:**
- Tests still pass
- Warning noise in test output
- Not affecting actual functionality

**Fix Required:**
- Update mock setup to properly handle async mocks
- Use `AsyncMock` instead of `MagicMock` for async functions

**Priority:** Medium (test hygiene)  
**Timeline:** Should fix in next test cleanup  
**Production Impact:** None

---

## 🟢 Low Priority / Future Enhancements

### 4. Token Truncation Tracking

**Status:** API exists but not fully integrated

**Details:**
- Character truncation fully implemented and working
- Token truncation API exists in `yield_safe_batches()`
- Not yet generating warnings in production flow
- Would require adding tokenizer call to chunking pipeline

**Impact:** 
- Users see character truncation warnings (working)
- Users don't see token truncation warnings (rare edge case)

**Recommendation:**
- Consider implementing if users report token limit issues
- Current 4000 character limit covers most cases

**Priority:** Low (nice-to-have)  
**Timeline:** Future enhancement  
**Production Impact:** Minimal

---

### 5. Deduplication UI Feedback

**Status:** Working but could be enhanced

**Current Behavior:**
- Duplicate detected and linked silently
- Returns success with `was_duplicate: true` flag
- No special UI indication

**Enhancement Ideas:**
- Show "Already indexed as {original_filename}" notification
- Offer option to force re-process
- Display linked files in search results

**Impact:**
- Current behavior works correctly
- Enhanced UX would be helpful for power users

**Priority:** Low (UX enhancement)  
**Timeline:** Future improvement  
**Production Impact:** None

---

### 6. Large ZIP File Processing

**Status:** Working with limitations

**Details:**
- ZIP files processed sequentially (one file at a time)
- Very large ZIPs (100+ files) can take time
- Progress indication available but not granular

**Enhancement Ideas:**
- Parallel processing of ZIP contents
- Granular progress updates (file X of Y)
- Streaming ZIP extraction

**Impact:**
- Small-medium ZIPs process fine
- Large ZIPs work but slower than optimal

**Priority:** Low (performance optimization)  
**Timeline:** Future enhancement  
**Production Impact:** Minor (rarely hit)

---

### 7. Embedding Model Switching

**Status:** Models hardcoded in code

**Current:** 
- Dense: `sentence-transformers/all-MiniLM-L6-v2`
- Sparse: `prithivida/Splade_PP_en_v1`

**Limitation:**
- Cannot switch models without code change
- Model names not configurable via environment variables
- Changing models requires re-embedding all content

**Enhancement Ideas:**
- Make models configurable
- Support multiple embedding spaces simultaneously
- Provide migration tools for model changes

**Impact:**
- Current models work well for most use cases
- Advanced users might want different models

**Priority:** Low (advanced feature)  
**Timeline:** Future enhancement  
**Production Impact:** None

---

## 🔵 Planned Future Enhancements

### 8. Performance Metrics

**Status:** Not implemented

**What's Missing:**
- No built-in performance monitoring
- No timing metrics logged
- No slow query detection

**Planned:**
- Add timing instrumentation
- Log performance metrics
- Dashboard for performance monitoring

**Priority:** Low (observability)  
**Timeline:** Phase 8 or later

---

### 9. Rate Limiting

**Status:** Not implemented

**Current:**
- No rate limiting on upload endpoints
- No concurrency limits
- Relies on client-side throttling

**Risk:**
- Spike in uploads could overwhelm system
- Embedding API could be rate-limited by provider

**Planned:**
- Add upload rate limits per user/IP
- Implement queue with max concurrency
- Graceful degradation under load

**Priority:** Low (unless scaling issues appear)  
**Timeline:** When needed for production scale

---

### 10. Search Analytics

**Status:** Not implemented

**What's Missing:**
- No search query logging
- No result relevance tracking
- No popular query identification

**Planned:**
- Log search queries and results
- Track click-through rates
- Identify knowledge gaps

**Priority:** Low (product analytics)  
**Timeline:** Post-MVP enhancement

---

## 🛡️ Limitations by Design

### 11. File Size Limits

**Hard Limits:**
- Max upload: 50 MB per file
- Max chunk: 4000 characters or 500 tokens
- Max batch: 100 chunks per API call

**Rationale:**
- Prevents memory exhaustion
- Ensures reasonable API costs
- Maintains search quality

**Workaround:**
- Split large documents into smaller files
- Use ZIP uploads for many small files

**Status:** Working as designed  
**No fix planned:** These are intentional limits

---

### 12. Supported File Types

**Currently Supported:**
- ✅ Markdown (.md)
- ✅ Plain text (.txt)
- ✅ HTML (.html)
- ✅ PDF (.pdf)
- ✅ ZIP archives (.zip)

**Not Supported:**
- ❌ Microsoft Word (.docx)
- ❌ Microsoft Excel (.xlsx)
- ❌ PowerPoint (.pptx)
- ❌ Images (OCR)
- ❌ Audio transcription
- ❌ Video content

**Rationale:**
- Focus on core documentation use case
- Avoid complex dependencies
- Keep processing pipeline simple

**Enhancement Path:**
- Could add .docx support via `python-docx`
- Could add OCR via `tesseract`
- Requires additional dependencies

**Priority:** Low (unless user demand)  
**Timeline:** Future enhancement based on feedback

---

### 13. Single Vector Database

**Current:**
- Uses Qdrant exclusively
- No support for other vector databases

**Limitation:**
- Cannot easily switch to Pinecone, Weaviate, etc.
- Qdrant-specific features used

**Rationale:**
- Qdrant works well for use case
- Abstraction would add complexity
- No user demand for alternatives

**Status:** Working as designed  
**No fix planned unless requirements change**

---

## 📝 Reporting New Issues

If you discover a new issue:

1. **Check this document** to see if it's already known
2. **Verify it's reproducible** in a clean environment
3. **Gather details:**
   - Error message (full traceback if possible)
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment (Docker vs host, versions, etc.)
4. **Report via GitHub issues** or contact development team

---

## ✅ Recently Fixed Issues

### ~~Vault Service Resource Consumption~~ - FIXED IN PHASE 1
- **Was:** Vault service running but unused, consuming resources
- **Fixed:** Vault service completely removed from architecture
- **Status:** ✅ Complete

### ~~No Deduplication~~ - FIXED IN PHASE 2
- **Was:** Duplicate uploads created duplicate embeddings
- **Fixed:** Content-based deduplication with linking
- **Status:** ✅ Complete

### ~~Silent Truncation~~ - FIXED IN PHASE 3
- **Was:** Content truncated without user awareness
- **Fixed:** Truncation warnings displayed prominently
- **Status:** ✅ Complete

### ~~Blocking PDF Processing~~ - FIXED IN PHASE 4
- **Was:** Long PDF processing blocked all uploads
- **Fixed:** Async subprocess-based PDF extraction
- **Status:** ✅ Complete

### ~~Poor Error Messages~~ - FIXED IN PHASE 5
- **Was:** Generic errors, orphaned chunks on failure
- **Fixed:** Structured errors with rollback
- **Status:** ✅ Complete

### ~~Outdated Documentation~~ - FIXED IN PHASE 6
- **Was:** Docs incomplete and inaccurate
- **Fixed:** Comprehensive documentation rewrite
- **Status:** ✅ Complete

---

## 📊 Issue Summary

| Priority | Count | % | Status |
|----------|-------|---|--------|
| 🔴 High | 1 | 7% | In Progress |
| 🟡 Medium | 2 | 14% | Tracked |
| 🟢 Low | 5 | 36% | Planning |
| 🔵 Future | 3 | 21% | Backlog |
| 🛡️ By Design | 3 | 21% | No Fix Needed |
| **Total** | **14** | **100%** | - |

**Critical/Blocker Issues:** 0  
**Production-Impacting Issues:** 0  
**Test/Development Issues:** 1 (high priority)

---

**Last Review:** February 5, 2026  
**Next Review:** TBD (after test environment fix)
