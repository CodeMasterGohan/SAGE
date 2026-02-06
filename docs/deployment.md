# SAGE Deployment Guide

Production deployment guide for SAGE documentation search system.

## Table of Contents
- [Deployment Checklist](#deployment-checklist)
- [Docker Compose Production](#docker-compose-production)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Environment Variables & Secrets](#environment-variables--secrets)
- [Scaling Strategies](#scaling-strategies)
- [Monitoring & Observability](#monitoring--observability)
- [Backup & Recovery](#backup--recovery)
- [Security Hardening](#security-hardening)
- [Performance Optimization](#performance-optimization)
- [Disaster Recovery](#disaster-recovery)

---

## Deployment Checklist

Before deploying to production:

### Pre-Deployment
- [ ] Review and set all environment variables in `.env`
- [ ] Configure secrets management (API keys, credentials)
- [ ] Set appropriate upload limits for your use case
- [ ] Configure remote GPU servers (if using remote embeddings)
- [ ] Plan data migration strategy (if migrating existing data)
- [ ] Document your configuration in internal wiki

### Infrastructure
- [ ] Provision adequate resources (CPU, memory, storage)
- [ ] Set up persistent volumes for Qdrant data
- [ ] Configure networking (ports, firewall rules)
- [ ] Set up load balancer (if running multiple instances)
- [ ] Configure DNS records

### Security
- [ ] Enable HTTPS/TLS for all endpoints
- [ ] Set up API authentication (if required)
- [ ] Review and tighten upload validation rules
- [ ] Configure network policies (Docker network, K8s NetworkPolicy)
- [ ] Set up secrets management (Vault, K8s Secrets)
- [ ] Review file permissions on persistent volumes

### Monitoring
- [ ] Set up health check monitoring
- [ ] Configure log aggregation (ELK, Splunk, etc.)
- [ ] Set up alerting for errors and performance issues
- [ ] Configure metrics collection (Prometheus, Datadog)
- [ ] Create dashboards for key metrics

### Testing
- [ ] Test document upload (small, medium, large files)
- [ ] Test PDF processing end-to-end
- [ ] Test search functionality across libraries
- [ ] Perform load testing with realistic traffic
- [ ] Test failover and recovery procedures
- [ ] Verify backup and restore procedures

---

## Docker Compose Production

### Basic Production Setup

**docker-compose.prod.yml:**
```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:v1.7.4  # Pin specific version
    container_name: sage-qdrant-prod
    restart: always
    ports:
      - "6333:6333"
    volumes:
      - /mnt/data/qdrant:/qdrant/storage  # Production mount point
    environment:
      - QDRANT__SERVICE__HTTP_PORT=6333
    deploy:
      resources:
        limits:
          memory: 4g
        reservations:
          memory: 2g
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/collections"]
      interval: 30s
      timeout: 10s
      retries: 3

  dashboard:
    build:
      context: .
      dockerfile: dashboard/Dockerfile
    container_name: sage-dashboard-prod
    restart: always
    depends_on:
      qdrant:
        condition: service_healthy
    ports:
      - "8080:8080"
    volumes:
      - /mnt/data/uploads:/app/uploads
      - ./dashboard/static:/app/static:ro
      - ./sage_core:/app/sage_core:ro
    env_file:
      - .env.production
    environment:
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
    deploy:
      resources:
        limits:
          memory: 6g
          cpus: '4'
        reservations:
          memory: 2g
          cpus: '2'
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "10"

  mcp-server:
    build:
      context: .
      dockerfile: mcp-server/Dockerfile
    container_name: sage-mcp-prod
    restart: always
    depends_on:
      qdrant:
        condition: service_healthy
    ports:
      - "8000:8000"
    env_file:
      - .env.production
    environment:
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
    deploy:
      resources:
        limits:
          memory: 4g
          cpus: '2'
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "10"

volumes:
  qdrant_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/data/qdrant

networks:
  default:
    name: sage_prod

```

### Deploy Commands

```bash
# Create production .env file
cp .env.example .env.production
nano .env.production

# Create required directories
sudo mkdir -p /mnt/data/qdrant
sudo mkdir -p /mnt/data/uploads
sudo chown -R 1000:1000 /mnt/data/qdrant /mnt/data/uploads

# Build and start services
docker-compose -f docker-compose.prod.yml up -d --build

# Check status
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs -f

# View logs
docker logs sage-dashboard-prod -f --tail 100
```

---

## Kubernetes Deployment

### Namespace & ConfigMap

**namespace.yaml:**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: sage
```

**configmap.yaml:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: sage-config
  namespace: sage
data:
  QDRANT_HOST: "qdrant-service"
  QDRANT_PORT: "6333"
  COLLECTION_NAME: "sage_docs"
  JOBS_COLLECTION: "sage_jobs"
  EMBEDDING_MODE: "remote"
  DENSE_MODEL_NAME: "sentence-transformers/all-MiniLM-L6-v2"
  DENSE_VECTOR_SIZE: "384"
  CHUNK_SIZE: "1000"
  CHUNK_OVERLAP: "100"
  MAX_FILE_SIZE: "104857600"
  MAX_BATCH_TOKENS: "3000"
  WORKER_PROCESSES: "4"
  PDF_TIMEOUT: "900"
```

**secrets.yaml:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: sage-secrets
  namespace: sage
type: Opaque
stringData:
  VLLM_API_KEY: "your-vllm-api-key"
  OLMOCR_API_KEY: "your-olmocr-api-key"
  QDRANT_API_KEY: ""  # If using Qdrant Cloud
```

### Qdrant StatefulSet

**qdrant-statefulset.yaml:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: qdrant-service
  namespace: sage
spec:
  clusterIP: None
  selector:
    app: qdrant
  ports:
    - port: 6333
      targetPort: 6333

---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: qdrant
  namespace: sage
spec:
  serviceName: qdrant-service
  replicas: 1  # Single instance for now
  selector:
    matchLabels:
      app: qdrant
  template:
    metadata:
      labels:
        app: qdrant
    spec:
      containers:
      - name: qdrant
        image: qdrant/qdrant:v1.7.4
        ports:
        - containerPort: 6333
          name: http
        volumeMounts:
        - name: qdrant-data
          mountPath: /qdrant/storage
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /
            port: 6333
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /collections
            port: 6333
          initialDelaySeconds: 10
          periodSeconds: 5
  volumeClaimTemplates:
  - metadata:
      name: qdrant-data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: "fast-ssd"  # Your storage class
      resources:
        requests:
          storage: 100Gi
```

### Dashboard Deployment

**dashboard-deployment.yaml:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: dashboard-service
  namespace: sage
spec:
  type: LoadBalancer  # Or ClusterIP with Ingress
  selector:
    app: dashboard
  ports:
    - port: 8080
      targetPort: 8080

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dashboard
  namespace: sage
spec:
  replicas: 3  # Scale as needed
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
  selector:
    matchLabels:
      app: dashboard
  template:
    metadata:
      labels:
        app: dashboard
    spec:
      containers:
      - name: dashboard
        image: your-registry/sage-dashboard:latest
        ports:
        - containerPort: 8080
        envFrom:
        - configMapRef:
            name: sage-config
        - secretRef:
            name: sage-secrets
        volumeMounts:
        - name: uploads
          mountPath: /app/uploads
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "6Gi"
            cpu: "4"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
      volumes:
      - name: uploads
        persistentVolumeClaim:
          claimName: uploads-pvc

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: uploads-pvc
  namespace: sage
spec:
  accessModes:
    - ReadWriteMany  # Required for multiple pods
  storageClassName: "nfs-storage"  # Shared storage
  resources:
    requests:
      storage: 200Gi
```

### MCP Server Deployment

**mcp-deployment.yaml:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: mcp-service
  namespace: sage
spec:
  type: ClusterIP
  selector:
    app: mcp-server
  ports:
    - port: 8000
      targetPort: 8000

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-server
  namespace: sage
spec:
  replicas: 2
  selector:
    matchLabels:
      app: mcp-server
  template:
    metadata:
      labels:
        app: mcp-server
    spec:
      containers:
      - name: mcp-server
        image: your-registry/sage-mcp:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: sage-config
        - secretRef:
            name: sage-secrets
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "4Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
```

### Ingress Configuration

**ingress.yaml:**
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: sage-ingress
  namespace: sage
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"  # Upload size limit
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - sage.yourdomain.com
    secretName: sage-tls
  rules:
  - host: sage.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: dashboard-service
            port:
              number: 8080
      - path: /mcp
        pathType: Prefix
        backend:
          service:
            name: mcp-service
            port:
              number: 8000
```

### Deploy to Kubernetes

```bash
# Apply configurations
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secrets.yaml
kubectl apply -f qdrant-statefulset.yaml
kubectl apply -f dashboard-deployment.yaml
kubectl apply -f mcp-deployment.yaml
kubectl apply -f ingress.yaml

# Check status
kubectl get all -n sage
kubectl get pvc -n sage
kubectl logs -n sage deployment/dashboard -f

# Scale deployment
kubectl scale deployment/dashboard -n sage --replicas=5
```

---

## Environment Variables & Secrets

### Production .env.production

```bash
# Qdrant configuration
QDRANT_HOST=qdrant-service
QDRANT_PORT=6333
COLLECTION_NAME=sage_docs
JOBS_COLLECTION=sage_jobs

# Embedding configuration (remote GPU)
EMBEDDING_MODE=remote
VLLM_EMBEDDING_URL=http://gpu-server.internal:8000
VLLM_MODEL_NAME=nomic-ai/nomic-embed-text-v1.5
DENSE_VECTOR_SIZE=768
USE_NOMIC_PREFIX=true

# PDF processing (remote GPU)
OLMOCR_SERVER=http://gpu-server.internal:8000/v1
OLMOCR_MODEL=allenai/olmOCR-2-7B-1025-FP8
PDF_TIMEOUT=900

# Performance tuning
WORKER_PROCESSES=8
INGESTION_CONCURRENCY=200
MAX_BATCH_TOKENS=5000

# Upload limits
MAX_FILE_SIZE=104857600
MAX_ZIP_ENTRIES=1000
MAX_ZIP_TOTAL_SIZE=524288000

# Chunking
CHUNK_SIZE=1000
CHUNK_OVERLAP=100
MAX_CHUNK_CHARS=4000
MAX_CHUNK_TOKENS=500

# Secrets (use secrets manager in production)
VLLM_API_KEY=${VLLM_API_KEY}
OLMOCR_API_KEY=${OLMOCR_API_KEY}
```

### Secrets Management Best Practices

**1. Use Environment-Specific Secrets**
```bash
# Development
.env.development

# Staging
.env.staging

# Production
.env.production  # Never commit!
```

**2. Use Secrets Manager (Kubernetes)**
```bash
# Create from file
kubectl create secret generic sage-secrets \
  --from-file=.env.production \
  --namespace=sage

# Create from literals
kubectl create secret generic sage-secrets \
  --from-literal=VLLM_API_KEY=sk-xxx \
  --from-literal=OLMOCR_API_KEY=sk-yyy \
  --namespace=sage
```

**3. Use HashiCorp Vault (Docker)**
```yaml
services:
  dashboard:
    environment:
      - VLLM_API_KEY=${VAULT_VLLM_API_KEY}
      - OLMOCR_API_KEY=${VAULT_OLMOCR_API_KEY}
```

---

## Scaling Strategies

### Horizontal Scaling

**Dashboard Service:**
```bash
# Docker Compose (manual)
docker-compose -f docker-compose.prod.yml up -d --scale dashboard=3

# Kubernetes (auto)
kubectl scale deployment/dashboard -n sage --replicas=5
```

**Considerations:**
- **Shared Storage:** Use NFS/S3 for `/uploads` directory
- **Load Balancer:** Distribute traffic evenly
- **Job State:** Persisted in Qdrant (shared across instances)
- **Session Affinity:** Not required (stateless API)

### Vertical Scaling

**Increase Resources:**
```yaml
# docker-compose.prod.yml
services:
  dashboard:
    deploy:
      resources:
        limits:
          memory: 12g  # Increased from 6g
          cpus: '8'    # Increased from 4
```

**When to Vertically Scale:**
- Large embedding models (>1GB)
- High concurrent uploads
- Memory-intensive PDF processing

### Auto-Scaling (Kubernetes)

**hpa.yaml:**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: dashboard-hpa
  namespace: sage
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: dashboard
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Qdrant Scaling

**Single Node (Default):**
- Suitable for small to medium deployments
- Simpler to manage

**Qdrant Cluster (Advanced):**
- Requires Qdrant Cloud or self-hosted cluster setup
- Sharding by collection
- Replication for HA

```bash
# Qdrant Cloud (managed)
QDRANT_HOST=your-cluster.qdrant.tech
QDRANT_PORT=6333
QDRANT_API_KEY=your-api-key
```

---

## Monitoring & Observability

### Health Checks

**Endpoint Monitoring:**
```bash
# Dashboard health
curl http://localhost:8080/health

# Qdrant health
curl http://localhost:6333/collections

# MCP health
curl http://localhost:8000/health
```

**Automated Monitoring (Uptime Kuma, Pingdom):**
```yaml
monitors:
  - name: SAGE Dashboard
    url: https://sage.yourdomain.com/health
    interval: 60s
    
  - name: Qdrant
    url: http://qdrant:6333/collections
    interval: 60s
```

### Logging

**Centralized Logging (ELK Stack):**
```yaml
# docker-compose.prod.yml
services:
  dashboard:
    logging:
      driver: "fluentd"
      options:
        fluentd-address: "fluentd.internal:24224"
        tag: "sage.dashboard"
```

**Structured Logging:**
```python
# Enable JSON logging
import logging
import json_logging

json_logging.init_fastapi(enable_json=True)
json_logging.init_request_instrument(app)
```

**Log Aggregation Queries:**
```bash
# Find errors in last hour
grep -i "error" /var/log/sage/dashboard.log | tail -100

# Count uploads by status
awk '/upload.*status/ {print $NF}' dashboard.log | sort | uniq -c

# Average processing time
grep "Processing time" dashboard.log | awk '{sum+=$NF; count++} END {print sum/count}'
```

### Metrics Collection

**Prometheus Metrics:**
```python
# Add to dashboard/server.py
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()
Instrumentator().instrument(app).expose(app)
```

**Key Metrics:**
- Upload rate (files/minute)
- Processing time (p50, p95, p99)
- Search latency (milliseconds)
- Error rate (percentage)
- Queue depth (pending jobs)
- Qdrant collection size (points)
- Memory usage (MB)
- CPU usage (percentage)

**Grafana Dashboard:**
```json
{
  "dashboard": {
    "title": "SAGE Operations",
    "panels": [
      {"title": "Upload Rate", "type": "graph"},
      {"title": "Search Latency", "type": "graph"},
      {"title": "Error Rate", "type": "stat"},
      {"title": "Active Jobs", "type": "gauge"}
    ]
  }
}
```

### Alerting

**Alert Rules (Prometheus):**
```yaml
groups:
- name: sage_alerts
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status="5xx"}[5m]) > 0.05
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High error rate detected"
      
  - alert: SlowSearchQueries
    expr: histogram_quantile(0.95, rate(search_duration_seconds_bucket[5m])) > 2
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "95th percentile search latency > 2s"
      
  - alert: QdrantDown
    expr: up{job="qdrant"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Qdrant is down"
```

---

## Backup & Recovery

### Qdrant Backup Strategy

**1. Snapshot-Based Backup (Recommended):**
```bash
# Create snapshot
curl -X POST "http://localhost:6333/collections/sage_docs/snapshots"

# List snapshots
curl "http://localhost:6333/collections/sage_docs/snapshots"

# Download snapshot
curl "http://localhost:6333/collections/sage_docs/snapshots/snapshot_name" \
  --output sage_docs_backup.snapshot

# Store in S3/BackupServer
aws s3 cp sage_docs_backup.snapshot s3://backups/sage/$(date +%Y%m%d)/
```

**2. Automated Backup (Cron):**
```bash
#!/bin/bash
# /opt/sage/backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/mnt/backups/sage"
QDRANT_URL="http://localhost:6333"

# Create snapshot
SNAPSHOT=$(curl -sX POST "$QDRANT_URL/collections/sage_docs/snapshots" | jq -r '.result.name')

# Download
curl -s "$QDRANT_URL/collections/sage_docs/snapshots/$SNAPSHOT" \
  --output "$BACKUP_DIR/sage_docs_$DATE.snapshot"

# Upload to S3
aws s3 cp "$BACKUP_DIR/sage_docs_$DATE.snapshot" \
  s3://your-bucket/sage-backups/

# Cleanup old local backups (keep 7 days)
find "$BACKUP_DIR" -name "*.snapshot" -mtime +7 -delete

# Delete snapshot from Qdrant
curl -sX DELETE "$QDRANT_URL/collections/sage_docs/snapshots/$SNAPSHOT"
```

**Crontab:**
```bash
# Run daily at 2 AM
0 2 * * * /opt/sage/backup.sh >> /var/log/sage-backup.log 2>&1
```

**3. Volume Backup (Filesystem Level):**
```bash
# Stop Qdrant first
docker-compose stop qdrant

# Backup data directory
tar czf qdrant_backup_$(date +%Y%m%d).tar.gz /mnt/data/qdrant

# Restart Qdrant
docker-compose start qdrant
```

### Restore Procedure

**1. Restore from Snapshot:**
```bash
# Upload snapshot to Qdrant
curl -X PUT "http://localhost:6333/collections/sage_docs/snapshots/upload" \
  -F "file=@sage_docs_backup.snapshot"

# Or restore from file on server
curl -X PUT "http://localhost:6333/collections/sage_docs/snapshots/recover" \
  -H "Content-Type: application/json" \
  -d '{"location": "/qdrant/storage/snapshots/sage_docs_backup.snapshot"}'
```

**2. Full Recovery Workflow:**
```bash
# 1. Stop services
docker-compose down

# 2. Clear old data
rm -rf /mnt/data/qdrant/*

# 3. Start Qdrant only
docker-compose up -d qdrant

# 4. Wait for Qdrant to be ready
sleep 10

# 5. Restore snapshot
curl -X PUT "http://localhost:6333/collections/sage_docs/snapshots/recover" \
  -H "Content-Type: application/json" \
  -d '{"location": "/path/to/backup.snapshot"}'

# 6. Start remaining services
docker-compose up -d

# 7. Verify
curl http://localhost:8080/api/status
```

### Job State Recovery

Since job state is stored in Qdrant (`sage_jobs` collection), it persists across restarts and is included in Qdrant backups.

---

## Security Hardening

### Network Security

**1. Firewall Rules (iptables):**
```bash
# Allow only from specific IPs
iptables -A INPUT -p tcp --dport 6333 -s 10.0.0.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 6333 -j DROP

# Allow dashboard from internet
iptables -A INPUT -p tcp --dport 8080 -j ACCEPT  # Consider limiting
```

**2. Docker Network Isolation:**
```yaml
# docker-compose.prod.yml
networks:
  frontend:
    name: sage_frontend
  backend:
    name: sage_backend
    internal: true

services:
  dashboard:
    networks:
      - frontend
      - backend
      
  qdrant:
    networks:
      - backend  # Not exposed to internet
```

**3. Kubernetes NetworkPolicy:**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: qdrant-network-policy
  namespace: sage
spec:
  podSelector:
    matchLabels:
      app: qdrant
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: dashboard
    - podSelector:
        matchLabels:
          app: mcp-server
```

### API Authentication

**Add API Key Middleware (FastAPI):**
```python
# dashboard/server.py
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

API_KEYS = set(os.getenv("API_KEYS", "").split(","))
security = HTTPBearer()

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials not in API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )
    return credentials.credentials

# Protect endpoints
@app.post("/api/upload", dependencies=[Depends(verify_api_key)])
async def upload_document(...):
    ...
```

**Usage:**
```bash
curl -X POST http://localhost:8080/api/upload \
  -H "Authorization: Bearer your-api-key" \
  -F "file=@doc.md" \
  -F "library=react"
```

### HTTPS/TLS

**1. Nginx Reverse Proxy:**
```nginx
# /etc/nginx/sites-available/sage
server {
    listen 443 ssl http2;
    server_name sage.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/sage.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sage.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 100M;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**2. Traefik (Docker):**
```yaml
# docker-compose.prod.yml
services:
  traefik:
    image: traefik:v2.10
    command:
      - "--providers.docker=true"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.email=admin@yourdomain.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - letsencrypt:/letsencrypt

  dashboard:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.dashboard.rule=Host(`sage.yourdomain.com`)"
      - "traefik.http.routers.dashboard.entrypoints=websecure"
      - "traefik.http.routers.dashboard.tls.certresolver=letsencrypt"
```

### File Upload Security

Already implemented in `sage_core/validation.py`:
- File size limits
- Extension whitelist
- MIME type checking
- ZIP bomb detection
- Path traversal prevention

**Additional Hardening:**
```python
# Add virus scanning (optional)
import pyclamd

def scan_for_malware(content: bytes) -> bool:
    cd = pyclamd.ClamdUnixSocket()
    result = cd.scan_stream(content)
    return result is None  # None = clean
```

---

## Performance Optimization

### Database Optimization

**Qdrant Tuning:**
```yaml
# qdrant config.yaml
storage:
  # Use mmap for large collections
  mmap_threshold: 20000

  # Optimize for write-heavy workloads
  wal_capacity_mb: 64

  # Enable on-disk index for very large collections
  on_disk_payload: true

# Performance profile
service:
  max_request_size_mb: 100
  
  # Increase for high concurrency
  grpc_port: 6334
```

**Collection Optimization:**
```python
# Enable HNSW index parameters for faster search
client.update_collection(
    collection_name="sage_docs",
    hnsw_config=models.HnswConfigDiff(
        m=16,  # Number of neighbors (higher = better recall, slower)
        ef_construct=100,  # Construction time (higher = better quality)
    )
)
```

### Application Tuning

**Connection Pooling:**
```python
# Use persistent Qdrant client
_qdrant_client = QdrantClient(
    host=QDRANT_HOST,
    port=QDRANT_PORT,
    timeout=30,
    prefer_grpc=True  # Faster than HTTP for bulk operations
)
```

**Batch Uploads:**
```bash
# Upload ZIP instead of individual files
zip -r docs.zip *.md
curl -X POST http://localhost:8080/api/upload \
  -F "file=@docs.zip" \
  -F "library=react"
```

**Async Processing:**
```bash
# Use async endpoint for large PDFs
curl -X POST http://localhost:8080/api/upload/async \
  -F "file=@large.pdf" \
  -F "library=manuals"
```

### Resource Limits

**Docker:**
```yaml
# Prevent OOM
services:
  dashboard:
    deploy:
      resources:
        limits:
          memory: 6g
        reservations:
          memory: 2g
```

**Kubernetes:**
```yaml
resources:
  requests:
    memory: "2Gi"
    cpu: "1"
  limits:
    memory: "6Gi"
    cpu: "4"
```

---

## Disaster Recovery

### RTO & RPO Targets

**Recovery Time Objective (RTO):** < 1 hour  
**Recovery Point Objective (RPO):** < 24 hours

### DR Plan

**1. Backup Validation (Weekly):**
```bash
#!/bin/bash
# Test restore procedure

# Get latest backup
BACKUP=$(aws s3 ls s3://backups/sage/ | tail -1 | awk '{print $4}')

# Spin up test environment
docker-compose -f docker-compose.test.yml up -d qdrant

# Restore backup
curl -X PUT "http://localhost:6333/collections/sage_docs/snapshots/recover" \
  -d '{"location": "/backups/'$BACKUP'"}'

# Run smoke tests
pytest tests/test_disaster_recovery.py

# Cleanup
docker-compose -f docker-compose.test.yml down
```

**2. Failover Procedure:**
```bash
# 1. Detect failure
if ! curl -f http://primary-server:8080/health; then
  echo "Primary server down, initiating failover"
  
  # 2. Switch DNS to secondary
  aws route53 change-resource-record-sets --hosted-zone-id Z123 \
    --change-batch file://failover-dns.json
  
  # 3. Verify secondary health
  curl -f http://secondary-server:8080/health
  
  # 4. Alert team
  slack-notify "SAGE failover completed"
fi
```

**3. Data Recovery Matrix:**

| Scenario | Recovery Method | RTO | RPO |
|----------|----------------|-----|-----|
| Service crash | Auto-restart | <1 min | 0 |
| Data corruption | Restore from snapshot | <30 min | <24h |
| Complete server loss | Restore on new server | <60 min | <24h |
| Human error (delete) | Point-in-time restore | <15 min | <24h |
| Regional outage | Failover to DR region | <60 min | <24h |

---

## Maintenance Windows

**Recommended Schedule:**
- **Updates:** Weekly, Sunday 2-4 AM
- **Backups:** Daily, 2 AM
- **Validation:** Weekly, Sunday 4 AM
- **Cleanup:** Monthly, first Sunday

**Maintenance Checklist:**
```bash
# 1. Announce maintenance
echo "Starting maintenance window"

# 2. Drain connections (K8s)
kubectl cordon node-1
kubectl drain node-1 --ignore-daemonsets

# 3. Backup
./backup.sh

# 4. Update services
docker-compose pull
docker-compose up -d --build

# 5. Run smoke tests
pytest tests/test_smoke.py

# 6. Re-enable traffic (K8s)
kubectl uncordon node-1

# 7. Monitor for errors
tail -f /var/log/sage/dashboard.log
```

---

This deployment guide provides a production-ready foundation for SAGE. Adjust configurations based on your specific requirements, traffic patterns, and infrastructure constraints.
