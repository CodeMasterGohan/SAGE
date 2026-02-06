## Plan: SAGE Application Improvements - Production Readiness Enhancement

This plan implements 5 critical improvements to SAGE (removing vault, adding deduplication, truncation warnings, async PDF processing, and comprehensive error handling) plus mandatory documentation overhaul. The improvements address UX issues, cost optimization, production reliability, and user awareness gaps identified in the architecture review.

**Phases: 7 phases**

---

## Phase 1: Remove Vault Service

**Objective:** Eliminate the unused vault service to reduce resource consumption and simplify architecture.

**Files/Functions to Modify/Create:**
- [docker-compose.yml](docker-compose.yml) - Remove vault service definition
- [vault/](vault/) - Delete entire directory
- [README.md](README.md) - Remove vault references
- [docs/03-Developer-Internals.md](docs/03-Developer-Internals.md) - Update architecture diagrams

**Tests to Write:**
- `test_docker_compose_services` - Verify vault is not in services list
- `test_dashboard_ingestion` - Verify dashboard still works without vault
- Integration test for full upload pipeline without vault

**Steps:**
1. Write tests to verify current services work without vault dependency
2. Run tests to confirm they pass with current architecture
3. Remove vault service from docker-compose.yml
4. Delete vault/ directory
5. Remove vault references from documentation
6. Run tests to confirm services still function correctly
7. Test full upload flow via dashboard UI
8. Run linting and validation

---

## Phase 2: Add Content Deduplication Foundation

**Objective:** Implement content-based deduplication to prevent duplicate embeddings and reduce API costs when users upload the same document multiple times.

**Files/Functions to Modify/Create:**
- [sage_core/qdrant_utils.py](sage_core/qdrant_utils.py) - Add `compute_content_hash()` function, update schema to include content_hash field
- [sage_core/ingestion.py](sage_core/ingestion.py) - Modify `ingest_document()` to check for existing content hashes before processing
- [dashboard/server.py](dashboard/server.py) - Add deduplication info to UploadResult model
- [tests/test_deduplication.py](tests/test_deduplication.py) - New test file

**Tests to Write:**
- `test_compute_content_hash_consistent` - Same content produces same hash
- `test_compute_content_hash_different` - Different content produces different hashes
- `test_check_duplicate_content_not_found` - Returns None for new content
- `test_check_duplicate_content_found` - Returns existing document info for duplicate
- `test_ingest_duplicate_document_skips_embedding` - Duplicate upload skips embedding generation
- `test_ingest_duplicate_document_links_metadata` - New filename linked to existing chunks

**Steps:**
1. Write tests for content hash computation (failing - function doesn't exist)
2. Implement `compute_content_hash()` using SHA256 of full document body
3. Run tests to verify hash function works correctly
4. Write tests for duplicate detection in Qdrant (failing - no schema field)
5. Update Qdrant collection schema to add `content_hash` payload field
6. Implement `check_duplicate_content()` function to query by content hash
7. Run tests to verify duplicate detection works
8. Write tests for deduplication in ingestion pipeline (failing - not implemented)
9. Modify `ingest_document()` to check for duplicates before embedding
10. Add logic to link new filename to existing chunks if duplicate found
11. Run tests to verify duplicate documents skip embedding but are still searchable
12. Update API response model to include deduplication info (was_duplicate, linked_to)
13. Run all tests and linting

---

## Phase 3: Add Truncation Warnings to User Interface

**Objective:** Track and report content truncation to users so they're aware when chunks exceed size limits and content is lost.

**Files/Functions to Modify/Create:**
- [sage_core/chunking.py](sage_core/chunking.py) - Modify `process_markdown_chunks()` to track truncation events
- [sage_core/ingestion.py](sage_core/ingestion.py) - Return truncation warnings in result
- [dashboard/server.py](dashboard/server.py) - Add truncation_warnings field to UploadResult, display warnings in UI
- [dashboard/static/app.js](dashboard/static/app.js) - Display truncation warnings prominently
- [tests/test_truncation_warnings.py](tests/test_truncation_warnings.py) - New test file

**Tests to Write:**
- `test_no_truncation_warnings_for_small_chunks` - Normal sized chunks produce no warnings
- `test_character_truncation_warning` - Chunks >4000 chars generate warning with details
- `test_token_truncation_warning` - Chunks >500 tokens generate warning with token count
- `test_multiple_truncation_warnings_aggregated` - Multiple truncations reported correctly
- `test_api_response_includes_truncation_warnings` - Upload response contains warnings array
- `test_ui_displays_truncation_warnings` - Frontend shows warnings to user

**Steps:**
1. Write tests for truncation tracking (failing - no tracking exists)
2. Modify `process_markdown_chunks()` to return truncation events alongside chunks
3. Create TruncationWarning data structure with (chunk_index, chars_lost, tokens_lost, section_title)
4. Run tests to verify truncation tracking works
5. Write tests for truncation warnings in API response (failing - no field)
6. Modify `ingest_document()` to collect and return truncation warnings
7. Update UploadResult model to include truncation_warnings field
8. Run tests to verify API returns warnings
9. Write tests for UI display (failing - no UI element)
10. Add warning display component to frontend (prominent yellow alert)
11. Show details: "X chunks truncated, Y total chars lost"
12. Run integration tests to verify end-to-end warning flow
13. Run linting and validation

---

## Phase 4: Implement Async PDF Processing with Progress Updates

**Objective:** Convert blocking PDF OCR to non-blocking async subprocess execution to improve throughput and prevent worker starvation during long PDF processing.

**Files/Functions to Modify/Create:**
- [sage_core/file_processing.py](sage_core/file_processing.py) - Replace `extract_pdf_text()` with `extract_pdf_text_async()`
- [dashboard/server.py](dashboard/server.py) - Update background worker to use async PDF extraction
- [tests/test_async_pdf_processing.py](tests/test_async_pdf_processing.py) - New test file

**Tests to Write:**
- `test_extract_pdf_text_async_success` - Async extraction works for valid PDF
- `test_extract_pdf_text_async_timeout` - Timeout handled gracefully
- `test_extract_pdf_text_async_invalid_pdf` - Corrupt PDF raises proper exception
- `test_async_pdf_processing_non_blocking` - Multiple PDFs processed concurrently
- `test_pdf_processing_error_propagation` - Errors propagate to job status

**Steps:**
1. Write tests for async PDF extraction (failing - function doesn't exist)
2. Implement `extract_pdf_text_async()` using `asyncio.create_subprocess_exec()`
3. Replace synchronous subprocess.run() with async version
4. Run tests to verify async extraction works
5. Write tests for error propagation (failing - currently returns empty string)
6. Modify async function to raise exceptions instead of returning empty string on failure
7. Run tests to verify errors are properly raised
8. Write tests for concurrent PDF processing (failing - currently sequential)
9. Update background worker to properly await async PDF extraction
10. Test multiple concurrent PDF uploads don't block each other
11. Run integration tests with real PDFs
12. Verify timeout handling still works (10 min default)
13. Run linting and validation

---

## Phase 5: Enhanced Error Handling with Transaction Rollback

**Objective:** Implement robust error handling with transaction semantics to prevent orphaned chunks, add retry logic for transient failures, and provide detailed error messages to users.

**Files/Functions to Modify/Create:**
- [sage_core/ingestion.py](sage_core/ingestion.py) - Add transaction rollback, retry logic, detailed error capture
- [sage_core/qdrant_utils.py](sage_core/qdrant_utils.py) - Add `delete_points_by_ids()` cleanup function
- [dashboard/server.py](dashboard/server.py) - Improve error response details
- [tests/test_error_handling.py](tests/test_error_handling.py) - New test file

**Tests to Write:**
- `test_embedding_failure_rolls_back_partial_upload` - Failed embedding triggers cleanup
- `test_qdrant_upsert_failure_no_orphaned_chunks` - Failed upsert doesn't leave partial data
- `test_transient_embedding_failure_retries` - Network errors trigger retry with backoff
- `test_permanent_failure_stops_retries` - Non-transient errors fail immediately
- `test_error_response_includes_processing_step` - API returns which step failed
- `test_error_response_includes_specific_reason` - API returns detailed error message
- `test_partial_success_for_zip_uploads` - Some files succeed, some fail, all reported

**Steps:**
1. Write tests for transaction rollback (failing - no rollback exists)
2. Modify `ingest_document()` to track generated point IDs
3. Implement cleanup function to delete points by IDs on failure
4. Add try/except around embedding generation with rollback on failure
5. Run tests to verify partial uploads are cleaned up
6. Write tests for retry logic (failing - no retries exist)
7. Implement retry decorator with exponential backoff for embedding calls
8. Distinguish transient (network, rate limit) vs permanent (invalid input) errors
9. Run tests to verify retry behavior
10. Write tests for detailed error messages (failing - generic 500 errors)
11. Capture processing step context (extraction, chunking, embedding, indexing)
12. Return detailed error information in API response
13. Update dashboard to display specific error details to user
14. Write tests for partial success in ZIP uploads (failing - all-or-nothing currently)
15. Modify ZIP processing to continue on individual file failures
16. Collect success/failure per file and return detailed report
17. Run integration tests with failure scenarios
18. Run linting and validation

---

## Phase 6: Documentation Overhaul via Sub-Agents

**Objective:** Use specialized sub-agents to audit existing documentation, rewrite README.md from scratch, and create/update comprehensive technical documentation suite.

**Files/Functions to Modify/Create:**
- [README.md](README.md) - Complete rewrite
- [docs/architecture.md](docs/architecture.md) - New deep dive
- [docs/api-reference.md](docs/api-reference.md) - New complete API docs
- [docs/configuration.md](docs/configuration.md) - New config reference
- [docs/development.md](docs/development.md) - New developer guide
- [docs/deployment.md](docs/deployment.md) - New production guide
- [docs/troubleshooting.md](docs/troubleshooting.md) - New troubleshooting guide
- Update existing docs for accuracy

**Tests to Write:**
- `test_all_api_examples_work` - Code examples in docs are executable and correct
- `test_all_config_vars_documented` - Every env var in code has documentation
- `test_architecture_diagram_matches_code` - Diagram reflects actual structure
- `test_no_broken_internal_links` - All doc cross-references work

**Steps:**
1. Write tests for documentation quality checks (failing - outdated info exists)
2. Spawn documentation-audit sub-agent to analyze all code and docs
3. Collect audit report with discrepancies, undocumented features, outdated info
4. Run tests to baseline current quality metrics
5. Spawn README-writer sub-agent to completely rewrite README.md
6. Review new README for accuracy, completeness, beginner-friendliness
7. Replace old README with new version
8. Spawn technical-docs sub-agent to create/update docs/ folder content
9. Review generated docs for technical accuracy
10. Apply all documentation updates
11. Run tests to verify API examples work
12. Check all configuration variables are documented
13. Verify architecture diagrams match current code structure
14. Generate documentation quality report (coverage, accuracy, completeness scores)
15. Run linting on markdown files

---

## Phase 7: Integration Testing and Final Validation

**Objective:** Perform end-to-end integration testing of all improvements together, validate production readiness, and ensure no regressions.

**Files/Functions to Modify/Create:**
- [tests/test_integration_full_pipeline.py](tests/test_integration_full_pipeline.py) - New comprehensive integration tests
- [tests/test_regression.py](tests/test_regression.py) - New regression test suite

**Tests to Write:**
- `test_full_upload_pipeline_with_deduplication` - Upload, search, re-upload (dedupe check)
- `test_pdf_upload_async_with_truncation_warning` - Large PDF flow end-to-end
- `test_zip_upload_with_partial_failures` - ZIP with mixed valid/invalid files
- `test_concurrent_uploads_no_blocking` - Multiple users uploading simultaneously
- `test_search_results_after_improvements` - Search still returns correct results
- `test_mcp_server_still_functional` - MCP integration unchanged
- `test_docker_compose_all_services_healthy` - All containers start and pass health checks

**Steps:**
1. Write comprehensive integration tests covering all new features together
2. Run tests to verify all improvements work in combination (expect failures initially)
3. Debug and fix any integration issues between phases
4. Run full regression test suite against baseline scenarios
5. Verify no existing functionality broken by improvements
6. Test docker-compose startup with all services except vault
7. Verify all health checks pass
8. Perform manual QA testing via dashboard UI
9. Test upload flow: PDF, markdown, ZIP
10. Test search functionality unchanged
11. Test MCP server still works
12. Document any known issues or limitations
13. Run full lint and validation pass
14. Generate final test coverage report
15. Create migration notes for users

---

## Open Questions

1. **Content Hash Storage**: Should we store content hashes in a separate Qdrant collection for faster lookup, or in the payload of each chunk? (Option A: Separate collection - faster, Option B: In payload - simpler)

2. **Deduplication User Experience**: When duplicate detected, should users see: (Option A: Toast notification "Already indexed as X", Option B: Modal with option to force re-process, Option C: Silent deduplication with log entry only)

3. **Async PDF Processing Progress**: Should we implement real-time progress updates? (Option A: Server-Sent Events for live progress, Option B: Polling endpoint for status, Option C: No progress, just completion notification)

4. **Error Retry Strategy**: For transient failures during batch uploads, should we: (Option A: Retry failed files at end of batch, Option B: Retry immediately with backoff, Option C: Mark failed and let user manually retry)

5. **Documentation Sub-Agent Autonomy**: Should documentation sub-agents: (Option A: Present drafts and wait for approval before writing, Option B: Write autonomously and report what was changed, Option C: Interactive - ask questions when clarification needed)
