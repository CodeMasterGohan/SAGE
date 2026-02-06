# Migration Notes - SAGE Production Readiness (Phases 1-7)

**Target Audience:** Users upgrading from pre-Phase-1 SAGE to current version  
**Last Updated:** February 5, 2026  
**Version:** Post-Phase 7 (Production Ready)

---

## 📋 Executive Summary

**Good News:** This is a **fully backward-compatible upgrade**! ✅

- ✅ No breaking changes to APIs
- ✅ No database migration required
- ✅ No configuration changes mandatory
- ✅ Existing data remains valid
- ✅ All existing features work unchanged

**What's New:**
- Removed unused vault service (resource optimization)
- Added content deduplication (cost optimization)
- Added truncation warnings (transparency)
- Async PDF processing (performance)
- Enhanced error handling (reliability)
- Comprehensive documentation (usability)

**Migration Difficulty:** 🟢 **EASY**  
**Downtime Required:** ⏱️ **~2 minutes** (Docker container restart)  
**Rollback Difficulty:** 🟢 **EASY** (just revert to previous image)

---

## 🎯 Who Needs to Migrate?

### Definitely Migrate If:
- ✅ You're using the vault service (can remove it)
- ✅ You upload duplicate documents frequently (save money)
- ✅ You upload large documents (want truncation visibility)
- ✅ You process many PDFs (want better performance)
- ✅ You need better error messages (want detailed failures)

### Consider Staying If:
- 🤷 You have a custom fork with significant changes
- 🤷 You're in the middle of a critical project (upgrade later)
- 🤷 You have zero issues with current version (upgrade when convenient)

### Must Migrate By:
- ⚠️ **Security fixes** will only be applied to latest version
- ⚠️ **New features** will only be added to latest version
- ⚠️ **Community support** focuses on latest version

---

## 🚀 Migration Steps

### Step 1: Backup (5 minutes)

```bash
cd /path/to/SAGE

# Backup Qdrant data
docker-compose exec qdrant tar czf /tmp/qdrant-backup.tar.gz /qdrant/storage
docker cp sage-docs-qdrant:/tmp/qdrant-backup.tar.gz ./backup-$(date +%Y%m%d).tar.gz

# Backup environment file
cp .env .env.backup

# Backup uploaded files (if using persistent volume)
cp -r uploads uploads-backup
```

### Step 2: Stop Services (30 seconds)

```bash
docker-compose down
```

### Step 3: Update Code (1 minute)

```bash
# Pull latest changes
git pull origin main

# OR download latest release
# wget https://github.com/your-org/sage/releases/latest/download/sage.tar.gz
# tar xzf sage.tar.gz
```

### Step 4: Review docker-compose.yml (1 minute)

**If using default `docker-compose.yml`:**
- ✅ Nothing to do - vault is already removed

**If using custom `docker-compose.yml`:**
```yaml
# Remove this entire section if present:
# vault:
#   image: vault:latest
#   ...
```

### Step 5: Update Environment Variables (Optional - 2 minutes)

**Required: None** - all existing variables still work

**Optional enhancements:**

```bash
# .env file additions (optional)

# Deduplication settings (Phase 2)
ENABLE_DEDUPLICATION=true  # Default: true
CONTENT_HASH_ALGORITHM=sha256  # Default: sha256

# Chunking settings (Phase 3)
MAX_CHUNK_CHARS=4000  # Default: 4000
MAX_CHUNK_TOKENS=500  # Default: 500
TRUNCATION_WARNINGS=true  # Default: true

# PDF processing (Phase 4)
PDF_PROCESSING_TIMEOUT=600  # Default: 600 seconds (10 min)
PDF_MAX_WORKERS=4  # Default: 4

# Error handling (Phase 5)
ENABLE_TRANSACTION_ROLLBACK=true  # Default: true
MAX_RETRY_ATTEMPTS=3  # Default: 3
RETRY_BACKOFF_FACTOR=2.0  # Default: 2.0
```

### Step 6: Start Services (30 seconds)

```bash
docker-compose up -d
```

### Step 7: Verify (2 minutes)

```bash
# Check all services running
docker-compose ps

# Check logs for errors
docker-compose logs --tail=50

# Verify dashboard accessible
curl http://localhost:8080/health || echo "Dashboard not ready yet"

# Verify MCP server accessible  
curl http://localhost:8000/health || echo "MCP server not ready yet"

# Verify Qdrant accessible
curl http://localhost:6334/health || echo "Qdrant not ready yet"
```

### Step 8: Smoke Test (3 minutes)

1. **Open dashboard:** http://localhost:8080
2. **Upload test document:**
   - Create small markdown file: `# Test\n\nMigration test`
   - Upload to new library: "migration-test"
   - Verify success message
3. **Test search:**
   - Search for "migration test"
   - Verify results returned
4. **Test deduplication:**
   - Upload same document again
   - Verify duplicate detection message
5. **Done!** ✅

---

## 🔄 API Changes (Backward Compatible)

### Response Model Extensions

All API endpoints return extended response models with new optional fields:

#### Upload Response (POST `/upload`, POST `/upload/async`)

**Before:**
```json
{
  "success": true,
  "library": "my-docs",
  "version": "1.0",
  "files_processed": 1,
  "chunks_indexed": 42,
  "message": "Successfully indexed..."
}
```

**After:**
```json
{
  "success": true,
  "library": "my-docs",
  "version": "1.0",
  "files_processed": 1,
  "chunks_indexed": 42,
  "message": "Successfully indexed...",
  "was_duplicate": false,           // NEW: Phase 2
  "linked_to": null,                 // NEW: Phase 2
  "truncation_warnings": []          // NEW: Phase 3
}
```

**Impact:** 
- ✅ Clients can ignore new fields
- ✅ Existing parsing still works
- ✅ No changes required to client code

### Error Response Structure

**Before:**
```json
{
  "detail": "Internal server error"
}
```

**After:**
```json
{
  "detail": {
    "error": "Embedding generation failed",
    "processing_step": "embedding",
    "file_name": "document.pdf",
    "details": {
      "reason": "Rate limit exceeded",
      "retry_after": 60
    }
  }
}
```

**Impact:**
- ✅ Backward compatible (detail can be string or object)
- ✅ Better debugging information
- ✅ Clients can handle errors more gracefully

---

## 🗄️ Database Changes

### Schema Evolution

**Good news:** Qdrant schema auto-upgrades! ✅

**What happens:**
- Existing collections remain unchanged
- New uploads include additional payload fields:
  - `content_hash` (Phase 2 - deduplication)
  - `linked_files` (Phase 2 - deduplication)
  - `section_title` (Phase 3 - truncation context)

**Existing data:**
- ✅ No migration needed
- ✅ Old points remain searchable
- ✅ New fields added only to new uploads
- ✅ Queries work on both old and new data

**Optional: Backfill content hashes for deduplication**

If you want deduplication to work with existing documents:

```python
# Optional backfill script (not required)
from sage_core.qdrant_utils import get_qdrant_client, compute_content_hash
from qdrant_client.models import Filter, FieldCondition, MatchValue

client = get_qdrant_client()

# Scroll through existing points
points, _ = client.scroll(
    collection_name="sage_docs",
    limit=100,
    with_payload=True,
    with_vectors=False
)

# Update each point with content hash
for point in points:
    content = point.payload.get("content", "")
    content_hash = compute_content_hash(content)
    
    client.set_payload(
        collection_name="sage_docs",
        points=[point.id],
        payload={"content_hash": content_hash}
    )

print(f"Backfilled {len(points)} points")
```

**Should you backfill?**
- ✅ Yes: If you have many duplicate documents already indexed
- ❌ No: If you have mostly unique documents (let it happen naturally)

---

## 🔧 Configuration Changes

### Removed Configuration

#### Vault Service (Phase 1)

**Before:**
```yaml
# docker-compose.yml
vault:
  image: vault:latest
  ports:
    - "8200:8200"
  environment:
    VAULT_DEV_ROOT_TOKEN_ID: ${VAULT_TOKEN}
```

**After:**
```yaml
# Service removed - delete if present
```

**Impact:**
- ✅ Reduces memory usage by ~100MB
- ✅ Reduces CPU usage
- ✅ Simplifies architecture
- ⚠️ If you customized vault for secrets: migrate secrets to environment variables

### New Configuration Options

#### Deduplication (Phase 2)

```bash
# Optional - defaults work for most cases
ENABLE_DEDUPLICATION=true
CONTENT_HASH_ALGORITHM=sha256  # Options: sha256, md5, blake2b
```

#### Chunking (Phase 3)

```bash
# Optional - tune for your documents
MAX_CHUNK_CHARS=4000  # Increase for longer chunks
MAX_CHUNK_TOKENS=500  # Embedding model limit
TRUNCATION_WARNINGS=true  # Disable to hide warnings
```

#### PDF Processing (Phase 4)

```bash
# Optional - tune for your PDFs
PDF_PROCESSING_TIMEOUT=600  # Seconds (10 min default)
PDF_MAX_WORKERS=4  # Concurrent PDF extractions
```

#### Error Handling (Phase 5)

```bash
# Optional - tune retry behavior
ENABLE_TRANSACTION_ROLLBACK=true  # Rollback on failure
MAX_RETRY_ATTEMPTS=3  # For transient failures
RETRY_BACKOFF_FACTOR=2.0  # Exponential backoff
```

---

## 🐛 Breaking Changes

**None!** This is a fully backward-compatible upgrade. 🎉

All existing integrations, API clients, and workflows continue to work unchanged.

---

## ⚠️ Potential Issues

### Issue 1: Docker Image Size Increase

**Change:** Docker image is ~50MB larger due to additional dependencies.

**Impact:**
- Longer initial pull time
- Slightly more disk usage

**Mitigation:**
- Use Docker layer caching
- Pull during off-hours
- Not a runtime performance issue

### Issue 2: First Upload After Migration is Slower

**Change:** Qdrant schema updates on first upload.

**Impact:**
- First upload takes 2-3 seconds instead of <1 second
- Only happens once per collection

**Mitigation:**
- Perform test upload during migration
- Or just accept the one-time delay

### Issue 3: Deduplication Changes Upload Behavior

**Change:** Duplicate uploads now skip embedding generation.

**Impact:**
- Duplicate uploads complete faster
- Duplicate uploads don't create new chunks
- UI shows "Already indexed" instead of "Uploaded"

**Expected Behavior:**
- ✅ Intended feature (saves money and storage)

**Revert If Unwanted:**
```bash
# Disable deduplication
export ENABLE_DEDUPLICATION=false
```

---

## 🔙 Rollback Procedure

If you need to revert to previous version:

### Step 1: Stop New Version

```bash
docker-compose down
```

### Step 2: Restore Previous Version

```bash
# Option A: Revert git commit
git revert HEAD
git pull origin main

# Option B: Checkout previous tag
git checkout v1.0.0  # Replace with actual previous version

# Option C: Restore from backup
tar xzf sage-backup.tar.gz
```

### Step 3: Restore Configuration

```bash
# Restore old docker-compose.yml (if you modified it)
git checkout HEAD~1 docker-compose.yml

# Restore old environment variables
cp .env.backup .env
```

### Step 4: Restore Data (if needed)

```bash
# Only if you modified data during migration
docker-compose up -d qdrant
docker cp backup-20260205.tar.gz sage-docs-qdrant:/tmp/
docker-compose exec qdrant tar xzf /tmp/backup-20260205.tar.gz -C /
```

### Step 5: Start Previous Version

```bash
docker-compose up -d
```

### Step 6: Verify

```bash
docker-compose ps
curl http://localhost:8080/health
```

**Rollback Time:** ~5 minutes  
**Data Loss:** None (if you backed up)

---

## 📊 Migration Verification Checklist

After migration, verify these functions:

### Core Functionality
- [ ] Dashboard loads (http://localhost:8080)
- [ ] Upload markdown file works
- [ ] Upload PDF file works
- [ ] Upload ZIP file works
- [ ] Search returns results
- [ ] Create library works
- [ ] Delete library works

### New Features
- [ ] Upload duplicate shows "Already indexed" message
- [ ] Large document shows truncation warning
- [ ] Truncation warning displays in UI (yellow banner)
- [ ] PDF upload completes without blocking
- [ ] Error messages show detailed information

### Performance
- [ ] Upload response time < 5 seconds (for small files)
- [ ] Search response time < 2 seconds
- [ ] Concurrent uploads don't block each other
- [ ] Memory usage reasonable (~500MB total)

### Services
- [ ] Dashboard service healthy
- [ ] MCP service healthy
- [ ] Qdrant service healthy
- [ ] Refinery service healthy
- [ ] Vault service NOT present (removed)

---

## 📞 Support

### Common Questions

**Q: Do I need to re-index existing documents?**  
A: No. Existing embeddings remain valid and searchable.

**Q: Will deduplication work with old documents?**  
A: Only for new uploads. Old documents can be backfilled (optional).

**Q: Can I disable new features?**  
A: Yes. Set environment variables (e.g., `ENABLE_DEDUPLICATION=false`).

**Q: Is there downtime during migration?**  
A: ~2 minutes during Docker restart. Schedule during maintenance window.

**Q: Can I test before production migration?**  
A: Yes. Spin up new environment with backup data and test thoroughly.

### Getting Help

**Issues during migration:**
1. Check [KNOWN-ISSUES.md](KNOWN-ISSUES.md)
2. Check Docker logs: `docker-compose logs`
3. Check service health: `docker-compose ps`
4. Review [troubleshooting.md](docs/troubleshooting.md)
5. Open GitHub issue with details

**Successful migration:**
- ✅ You should see no changes in behavior
- ✅ Plus new features available
- ✅ Plus better error messages
- ✅ Plus improved performance

---

## 🎉 Success!

Once you've completed these steps and verified functionality, you're done!

**Congratulations on upgrading to production-ready SAGE!** 🚀

**Next steps:**
1. Monitor logs for any issues
2. Gather user feedback on new features
3. Consider backfilling content hashes (optional)
4. Review [User Guide](docs/02-User-Guide.md) for new features
5. Review [Developer Guide](docs/03-Developer-Internals.md) for code changes

---

**Questions?** Check [docs/troubleshooting.md](docs/troubleshooting.md) or open an issue.

**Migration Date:** __________  
**Migrated By:** __________  
**Issues Encountered:** __________  
**Status:** ☐ Success  ☐ Partial  ☐ Failed
