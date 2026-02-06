# SAGE Troubleshooting Guide

Comprehensive troubleshooting guide for common issues and their solutions.

## Table of Contents
- [Service Issues](#service-issues)
- [Upload Problems](#upload-problems)
- [PDF Processing Issues](#pdf-processing-issues)
- [Search Issues](#search-issues)
- [Embedding Issues](#embedding-issues)
- [Deduplication Issues](#deduplication-issues)
- [Performance Problems](#performance-problems)
- [Database Issues](#database-issues)
- [Network & Connectivity](#network--connectivity)
- [Debugging Commands](#debugging-commands)

---

## Service Issues

### Issue: Service Won't Start

**Symptoms:**
- Container exits immediately
- "Connection refused" errors
- Health checks fail

**Diagnosis:**
```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs dashboard
docker logs sage-dashboard-prod -f

# Check port conflicts
sudo netstat -tlnp | grep :8080
```

**Common Causes & Solutions:**

**1. Port Already in Use**
```bash
# Find process using port
sudo lsof -i :8080
sudo kill <PID>

# Or change port in docker-compose.yml
ports:
  - "8081:8080"  # Use different external port
```

**2. Docker Daemon Issues**
```bash
# Check Docker status
sudo systemctl status docker

# Restart Docker
sudo systemctl restart docker

# Check disk space
df -h
```

**3. Volume Permission Errors**
```bash
# Fix permissions
sudo chown -R 1000:1000 /mnt/data/qdrant /mnt/data/uploads

# Check volume mounts
docker inspect sage-dashboard-prod | grep -A 10 Mounts
```

---

### Issue: Dashboard Can't Access Web UI

**Symptoms:**
- 502 Bad Gateway
- Connection timeout
- Empty response

**Diagnosis:**
```bash
# Test health endpoint
curl http://localhost:8080/health

# Test from inside container
docker exec sage-dashboard-prod curl http://localhost:8080/health

# Check nginx/proxy logs (if using)
tail -f /var/log/nginx/error.log
```

**Solutions:**

**1. Service Not Running**
```bash
docker-compose ps dashboard
docker-compose up -d dashboard
```

**2. Firewall Blocking**
```bash
# Check firewall rules
sudo ufw status
sudo ufw allow 8080/tcp

# Or iptables
sudo iptables -L -n | grep 8080
```

**3. DNS Resolution (Kubernetes)**
```bash
# Test service DNS
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup dashboard-service

# Check service endpoints
kubectl get endpoints dashboard-service -n sage
```

---

### Issue: Async Uploads Stuck in "Processing"

**Symptoms:**
- Job status never changes from "processing"
- No progress updates
- Jobs timeout

**Diagnosis:**
```bash
# Check job status
curl http://localhost:8080/api/upload/status/YOUR_TASK_ID

# Check worker processes
docker exec sage-dashboard-prod ps aux | grep python

# Check for deadlocks or hanging processes
docker stats sage-dashboard-prod
```

**Solutions:**

**1. Worker Process Crashed**
```bash
# Check logs for exceptions
docker logs sage-dashboard-prod | grep -i "error\|traceback"

# Restart service
docker-compose restart dashboard
```

**2. Out of Memory**
```bash
# Check memory usage
docker stats --no-stream sage-dashboard-prod

# Increase memory limit in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 8g  # Increased from 6g
```

**3. Job State Corruption**
```bash
# Query Qdrant directly
curl "http://localhost:6333/collections/sage_jobs/points/scroll?with_payload=true&limit=10"

# Delete stuck job
curl -X POST "http://localhost:6333/collections/sage_jobs/points/delete" \
  -H "Content-Type: application/json" \
  -d '{"points": ["YOUR_TASK_ID"]}'
```

---

## Upload Problems

### Issue: Upload Fails Immediately

**Symptoms:**
- 400 Bad Request
- "File too large" error
- "File type not allowed"

**Diagnosis:**
```bash
# Check file size
ls -lh your-file.pdf

# Check file type
file your-file.pdf
```

**Solutions:**

**1. File Too Large**
```bash
# Current limit (default 50MB)
echo $MAX_FILE_SIZE

# Increase limit in .env
MAX_FILE_SIZE=104857600  # 100MB

# Restart services
docker-compose restart dashboard
```

**2. Unsupported File Type**
```bash
# Supported extensions:
# .md, .markdown, .txt, .html, .htm, .pdf, .docx, .xlsx, .zip, .rst, .adoc

# Convert to supported format or add to ALLOWED_EXTENSIONS
```

**3. ZIP Validation Failed**
```bash
# Test ZIP integrity
unzip -t your-archive.zip

# Check ZIP size constraints
zipinfo -v your-archive.zip | grep "uncompressed size"

# If too large, split into smaller ZIPs:
zip -s 100m output.zip large-archive.zip
```

---

### Issue: Partial Upload Success

**Symptoms:**
- Some files in ZIP processed, others failed
- Inconsistent chunk counts
- Some duplicates detected, others not

**Diagnosis:**
```bash
# Check response details
curl -X POST http://localhost:8080/api/upload \
  -F "file=@docs.zip" \
  -F "library=test" \
  -v  # Verbose mode

# Check logs for individual file errors
docker logs sage-dashboard-prod | grep "Error processing"
```

**Solutions:**

**1. Mixed File Types in ZIP**
```bash
# Identify problematic files
zipinfo -1 docs.zip | while read file; do
  ext="${file##*.}"
  if [[ ! "$ext" =~ ^(md|txt|html|pdf|docx)$ ]]; then
    echo "Unsupported: $file"
  fi
done

# Remove unsupported files
zip -d docs.zip "*.jpg" "*.png"
```

**2. Individual File Corruption**
```bash
# Extract and test individually
unzip docs.zip
for file in *.md; do
  curl -X POST http://localhost:8080/api/upload \
    -F "file=@$file" \
    -F "library=test" \
    || echo "Failed: $file"
done
```

---

## PDF Processing Issues

### Issue: PDF Timeout Errors

**Symptoms:**
- "PDF processing timed out after 600 seconds"
- olmocr process hangs
- Memory usage spikes during PDF processing

**Diagnosis:**
```bash
# Check PDF properties
pdfinfo large-file.pdf

# Check process status during upload
ps aux | grep olmocr
top -p $(pgrep -f olmocr)
```

**Solutions:**

**1. Increase Timeout**
```bash
# In .env
PDF_TIMEOUT=1200  # 20 minutes

# Restart services
docker-compose restart dashboard
```

**2. Use Async Upload**
```bash
# For large PDFs, always use async endpoint
curl -X POST http://localhost:8080/api/upload/async \
  -F "file=@large.pdf" \
  -F "library=manuals"

# Poll for completion
TASK_ID="..."
while true; do
  STATUS=$(curl -s http://localhost:8080/api/upload/status/$TASK_ID | jq -r '.status')
  echo "Status: $STATUS"
  [[ "$STATUS" == "completed" ]] && break
  sleep 10
done
```

**3. Use Remote GPU Server**
```bash
# Configure GPU server in .env
OLMOCR_SERVER=http://gpu-server:8000/v1
OLMOCR_API_KEY=your-api-key

# Verify connectivity
curl http://gpu-server:8000/health
```

**4. Split Large PDFs**
```bash
# Split PDF into smaller files
pdftk large.pdf burst output page_%04d.pdf

# Upload individually
for pdf in page_*.pdf; do
  curl -X POST http://localhost:8080/api/upload/async \
    -F "file=@$pdf" \
    -F "library=manual"
done
```

---

### Issue: olmocr Fails with Error

**Symptoms:**
- "olmocr failed with exit code 1"
- Empty markdown output
- GPU out of memory

**Diagnosis:**
```bash
# Test olmocr manually
python -m olmocr.pipeline /tmp/workspace \
  --markdown --pdfs test.pdf \
  --model allenai/olmOCR-2-7B-1025-FP8

# Check GPU availability (if local)
nvidia-smi

# Check olmocr server (if remote)
curl http://gpu-server:8000/health
```

**Solutions:**

**1. olmocr Not Installed**
```bash
# Install olmocr
pip install olmocr

# Verify installation
python -m olmocr --version
```

**2. GPU Out of Memory**
```bash
# Use FP8 model (smaller)
OLMOCR_MODEL=allenai/olmOCR-2-7B-1025-FP8

# Or reduce batch size (requires code change)
```

**3. Corrupted PDF**
```bash
# Validate PDF
pdf-parser -O test.pdf

# Try repair
pdftk broken.pdf output fixed.pdf

# Or convert via Ghostscript
gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 \
   -dNOPAUSE -dQUIET -dBATCH \
   -sOutputFile=fixed.pdf broken.pdf
```

---

### Issue: PDF Extraction Quality Poor

**Symptoms:**
- Garbled text
- Missing sections
- Tables not preserved

**Diagnosis:**
```bash
# Check PDF type
pdffonts test.pdf  # Text-based vs scanned

# Test extraction
pdftotext test.pdf - | head -50
```

**Solutions:**

**1. Scanned PDFs (Images)**
- olmocr is designed for this (should work well)
- Check image quality with `pdfimages`
- May need higher resolution scans

**2. Complex Layouts**
```bash
# olmocr handles complex layouts better than alternatives
# If still issues, try preprocessing:
# - Split multi-column PDFs
# - Remove headers/footers
# - Straighten skewed pages
```

**3. Alternative: Use Different Model**
```bash
# Try full precision model
OLMOCR_MODEL=allenai/olmOCR-2-7B
```

---

## Search Issues

### Issue: No Results Returned

**Symptoms:**
- Empty results array
- Search returns `[]`
- 0 matches for known content

**Diagnosis:**
```bash
# Check if collection has data
curl "http://localhost:6333/collections/sage_docs" | jq '.result.points_count'

# Test direct query
curl "http://localhost:6333/collections/sage_docs/points/scroll?limit=10" | jq '.result.points[].payload.content'

# Test search API
curl -X POST http://localhost:8080/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 10}' | jq '.'
```

**Solutions:**

**1. Collection Empty**
```bash
# Upload some documents first
curl -X POST http://localhost:8080/api/upload \
  -F "file=@test-doc.md" \
  -F "library=test"

# Verify indexing
curl "http://localhost:6333/collections/sage_docs" | jq '.result.points_count'
```

**2. Wrong Library/Version Filter**
```bash
# List available libraries
curl http://localhost:8080/api/libraries | jq '.'

# Search without filters
curl -X POST http://localhost:8080/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 10}'  # No library filter
```

**3. Embedding Model Mismatch**
```bash
# Check current vector size
curl "http://localhost:6333/collections/sage_docs" | \
  jq '.result.config.params.vectors.dense.size'

# Must match DENSE_VECTOR_SIZE
echo $DENSE_VECTOR_SIZE

# If mismatch, need to reindex all documents
```

---

### Issue: Slow Search Performance

**Symptoms:**
- Search takes >2 seconds
- High CPU usage during search
- Timeouts on large collections

**Diagnosis:**
```bash
# Measure search latency
time curl -X POST http://localhost:8080/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}' \
  -w "\nTotal time: %{time_total}s\n"

# Check collection size
curl "http://localhost:6333/collections/sage_docs" | \
  jq '.result.points_count'

# Check Qdrant metrics
curl "http://localhost:6333/metrics"
```

**Solutions:**

**1. Optimize HNSW Index**
```python
# In Python or direct API call
from qdrant_client import QdrantClient, models

client = QdrantClient("localhost", 6333)
client.update_collection(
    collection_name="sage_docs",
    hnsw_config=models.HnswConfigDiff(
        m=32,  # Increase for faster search (more memory)
        ef_construct=200
    )
)
```

**2. Reduce Search Vector Size**
```bash
# Use smaller embedding model (if acceptable)
DENSE_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
DENSE_VECTOR_SIZE=384  # vs 768 for larger models

# Requires reindexing
```

**3. Limit Result Count**
```bash
# Request fewer results
curl -X POST http://localhost:8080/api/search \
  -d '{"query": "test", "limit": 5}'  # vs 50
```

**4. Use Search Caching (Advanced)**
```python
# Add Redis cache for common queries
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_search(query: str, library: str, limit: int):
    return perform_search(query, library, limit)
```

---

### Issue: Irrelevant Search Results

**Symptoms:**
- Top results don't match query
- Wrong library documents returned
- Low relevance scores (<0.3)

**Diagnosis:**
```bash
# Check result scores
curl -X POST http://localhost:8080/api/search \
  -d '{"query": "authentication"}' | jq '.[].score'

# Try different fusion methods
curl -X POST http://localhost:8080/api/search \
  -d '{"query": "authentication", "fusion": "rrf"}'
```

**Solutions:**

**1. Use Reranking (MCP Server)**
```bash
# Enable ColBERT reranking for better relevance
curl http://localhost:8000/mcp/tools/search_docs \
  -d '{"query": "authentication", "rerank": true}'
```

**2. Adjust Chunk Size**
```bash
# Smaller chunks = more precise matching
CHUNK_SIZE=600
CHUNK_OVERLAP=60

# Requires reindexing
```

**3. Improve Query**
- Use more specific terms
- Include context words
- Try synonyms

**4. Check Data Quality**
```bash
# Sample document chunks
curl "http://localhost:6333/collections/sage_docs/points/scroll?limit=5" | \
  jq '.result.points[].payload.content' | head -20

# Look for:
# - Too short chunks
# - Garbled text
# - Missing context
```

---

## Embedding Issues

### Issue: Embedding Generation Failed

**Symptoms:**
- "Embedding generation failed: Connection timeout"
- 422 Unprocessable Entity
- "HTTPError" with retry count

**Diagnosis:**
```bash
# Check embedding mode
echo $EMBEDDING_MODE

# Test local model
python -c "from fastembed import TextEmbedding; m = TextEmbedding('sentence-transformers/all-MiniLM-L6-v2'); print(list(m.embed(['test'])))"

# Test remote API
curl -X POST http://gpu-server:8000/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $VLLM_API_KEY" \
  -d '{"input": ["test"], "model": "nomic-ai/nomic-embed-text-v1.5"}'
```

**Solutions:**

**1. Remote API Unreachable**
```bash
# Check connectivity
ping gpu-server
curl http://gpu-server:8000/health

# Check firewall
telnet gpu-server 8000

# Verify API endpoint
curl -v http://gpu-server:8000/v1/embeddings
```

**2. API Authentication Failed**
```bash
# Check API key
echo $VLLM_API_KEY

# Test with correct key
curl -X POST http://gpu-server:8000/v1/embeddings \
  -H "Authorization: Bearer correct-key-here" \
  -d '{"input": ["test"]}'
```

**3. Rate Limiting**
```bash
# Reduce concurrency
INGESTION_CONCURRENCY=20  # Down from 100

# Increase batch size to reduce calls
MAX_BATCH_TOKENS=5000  # Up from 2000
```

**4. Fallback to Local Mode**
```bash
# Temporarily switch to local
EMBEDDING_MODE=local
docker-compose restart dashboard
```

---

### Issue: Out of Memory During Embedding

**Symptoms:**
- Container killed (OOMKilled)
- System freeze during upload
- "MemoryError" in logs

**Diagnosis:**
```bash
# Check memory usage
docker stats sage-dashboard-prod

# Check system memory
free -h
vmstat 1 5

# Check container limits
docker inspect sage-dashboard-prod | grep -A 5 Memory
```

**Solutions:**

**1. Increase Container Memory**
```yaml
# docker-compose.yml
services:
  dashboard:
    deploy:
      resources:
        limits:
          memory: 8g  # Increased from 6g
```

**2. Reduce Batch Sizes**
```bash
MAX_BATCH_TOKENS=1000  # Smaller batches
INGESTION_CONCURRENCY=5  # Fewer concurrent embeddings
```

**3. Use Remote Embeddings**
```bash
# Offload to GPU server
EMBEDDING_MODE=remote
VLLM_EMBEDDING_URL=http://gpu-server:8000
```

**4. Process Files Individually**
```bash
# Instead of large ZIP, upload one-by-one
for file in *.md; do
  curl -X POST http://localhost:8080/api/upload \
    -F "file=@$file" -F "library=docs"
  sleep 2  # Throttle uploads
done
```

---

## Deduplication Issues

### Issue: Same File Uploaded Twice Creates Duplicates

**Symptoms:**
- `was_duplicate: false` for identical content
- Duplicate chunks in search results
- Increased storage usage

**Diagnosis:**
```bash
# Upload same file twice
curl -X POST http://localhost:8080/api/upload \
  -F "file=@test.md" -F "library=test" | jq '.was_duplicate'

# Check for content_hash in payload
curl "http://localhost:6333/collections/sage_docs/points/scroll?limit=10" | \
  jq '.result.points[].payload.content_hash'
```

**Solutions:**

**1. content_hash Missing**
```bash
# Check if deduplication feature is enabled
grep -r "content_hash" sage_core/ingestion.py

# Ensure using latest code (Phase 2+)
git pull origin main
docker-compose build --no-cache dashboard
```

**2. Different Formatting**
```bash
# Normalize whitespace before upload
sed 's/\r$//' windows-file.md > normalized.md
```

**3. Verify Hash Computation**
```python
# Test hash computation
from sage_core.qdrant_utils import compute_content_hash

content1 = open("file1.md").read()
content2 = open("file2.md").read()

print(compute_content_hash(content1))
print(compute_content_hash(content2))
# Should match if files identical
```

---

### Issue: content_hash Not Found in Metadata

**Symptoms:**
- Deduplication not working
- `linked_files` always empty
- Missing `content_hash` field

**Diagnosis:**
```bash
# Check payload schema
curl "http://localhost:6333/collections/sage_docs/points/scroll?limit=1" | \
  jq '.result.points[].payload | keys'

# Should include: content_hash, linked_files
```

**Solutions:**

**1. Old Data Without content_hash**
```bash
# Option A: Reindex all documents
# 1. Backup first
curl -X POST "http://localhost:6333/collections/sage_docs/snapshots"

# 2. Re-upload documents with new code
# This will add content_hash to new chunks

# Option B: Add content_hash to existing points
python scripts/backfill_content_hash.py
```

**2. Migration Script**
```python
# scripts/backfill_content_hash.py
from qdrant_client import QdrantClient
from sage_core.qdrant_utils import compute_content_hash

client = QdrantClient("localhost", 6333)

# Get all points
offset = None
while True:
    results, offset = client.scroll(
        collection_name="sage_docs",
        limit=100,
        offset=offset,
        with_payload=True,
        with_vectors=False
    )
    
    if not results:
        break
    
    for point in results:
        content = point.payload.get("content", "")
        content_hash = compute_content_hash(content)
        
        client.set_payload(
            collection_name="sage_docs",
            payload={"content_hash": content_hash, "linked_files": []},
            points=[point.id]
        )
    
    if not offset:
        break

print("Backfill complete")
```

---

## Performance Problems

### Issue: High CPU Usage

**Diagnosis:**
```bash
# Check container CPU
docker stats --no-stream sage-dashboard-prod

# Check processes
docker exec sage-dashboard-prod top -bn1

# Profile Python
docker exec sage-dashboard-prod py-spy top --pid 1
```

**Solutions:**

**1. Embedding Overload**
```bash
# Reduce concurrent embeddings
INGESTION_CONCURRENCY=10  # Down from 100

# Or switch to remote
EMBEDDING_MODE=remote
```

**2. Search Load**
```bash
# Add caching layer (Redis)
# Implement rate limiting
# Scale horizontally (more instances)
```

---

### Issue: High Memory Usage

**Solutions:**
```bash
# Increase container memory
# Reduce batch sizes
# Use remote embeddings
# Restart periodically (memory leaks)
docker-compose restart dashboard
```

---

## Database Issues

### Issue: Qdrant Connection Failed

**Symptoms:**
- "Connection refused"
- "Collection not found"
- Health check fails

**Diagnosis:**
```bash
# Check Qdrant status
docker-compose ps qdrant
docker logs sage-docs-qdrant

# Test connection
curl http://localhost:6333/collections

# From inside dashboard container
docker exec sage-dashboard-prod curl http://qdrant:6333/collections
```

**Solutions:**

**1. Qdrant Not Running**
```bash
docker-compose up -d qdrant
docker-compose logs qdrant
```

**2. Wrong Host/Port**
```bash
# Check environment
docker exec sage-dashboard-prod env | grep QDRANT

# Should be:
QDRANT_HOST=qdrant  # In Docker network
QDRANT_PORT=6333
```

**3. Collection Not Initialized**
```bash
# Create collection manually
curl -X PUT "http://localhost:6333/collections/sage_docs" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "dense": {"size": 384, "distance": "Cosine"}
    }
  }'
```

---

## Network & Connectivity

### Issue: Services Can't Communicate

**Docker Network:**
```bash
# Check network
docker network ls
docker network inspect sage_default

# All services should be on same network
```

**Kubernetes:**
```bash
# Check services
kubectl get svc -n sage

# Check endpoints
kubectl get endpoints -n sage

# Test connectivity
kubectl run -it --rm debug --image=busybox \
  --restart=Never -- wget -O- http://qdrant-service:6333/collections
```

---

## Debugging Commands

### Service Health Checks
```bash
# Dashboard
curl http://localhost:8080/health

# Qdrant
curl http://localhost:6333/health

# MCP
curl http://localhost:8000/health
```

### Log Collection
```bash
# All services
docker-compose logs > sage-logs.txt

# Specific service
docker logs sage-dashboard-prod --tail 1000 > dashboard.log

# Follow logs
docker-compose logs -f dashboard
```

### Database Inspection
```bash
# Collection info
curl http://localhost:6333/collections/sage_docs

# Count points
curl http://localhost:6333/collections/sage_docs/points/count

# Sample points
curl "http://localhost:6333/collections/sage_docs/points/scroll?limit=5&with_payload=true"

# Search by filter
curl -X POST http://localhost:6333/collections/sage_docs/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"filter": {"must": [{"key": "library", "match": {"value": "react"}}]}, "limit": 10}'
```

### Performance Profiling
```bash
# Install py-spy
pip install py-spy

# Profile dashboard
docker exec sage-dashboard-prod \
  py-spy record --pid 1 --duration 60 --output profile.svg

# View flamegraph
open profile.svg
```

### Force Cleanup
```bash
# Remove all data and restart
docker-compose down -v
rm -rf /mnt/data/qdrant/* /mnt/data/uploads/*
docker-compose up -d --build
```

---

## Getting Help

### Check Documentation
- [Architecture](./architecture.md)
- [API Reference](./api-reference.md)
- [Configuration](./configuration.md)
- [Deployment Guide](./deployment.md)

### Log Analysis Checklist
When reporting issues, include:
- Docker compose logs (`docker-compose logs`)
- Service versions (`docker-compose config`)
- Environment variables (sanitized)
- Steps to reproduce
- Expected vs actual behavior

### Community Support
- GitHub Issues: Report bugs
- Discussions: Ask questions
- Stack Overflow: Tag with `sage-docs`

---

**Still stuck?** Create a GitHub issue with:
1. Problem description
2. Steps to reproduce
3. Logs (sanitized)
4. Configuration (sanitized)
5. Environment (OS, Docker version, etc.)
