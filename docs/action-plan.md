> **⚠️ ARCHIVED DOCUMENT**  
> This action plan was created when vault service was active and includes references to it.  
> The vault service has since been **removed** from SAGE architecture (Phase 1).  
> Refer to [03-Developer-Internals.md](03-Developer-Internals.md) for current architecture.

Maturity: early production with solid foundations (centralized core library, background
   ingestion, tests) but notable gaps in security hardening, operational readiness, and consistency across services.
   Strengths: clear architecture, shared sage_core, upload validation, async ingestion with durable job state, decent
   docs. Key risks: no auth/authorization, duplicated/ divergent ingestion logic across dashboard/vault/refinery,
   incomplete resource isolation for heavy parsers, embedding/model/runtime configuration drift, limited observability
    and CI, and potential DoS via OCR/PDF and remote embedding paths.
     - Major Architectural Findings

     - Split ingestion/search implementations (dashboard/ingest.py vs sage_core vs vault/refinery) risk divergence and
    inconsistent behavior; refinery/vault replicate chunking/processing logic instead of importing sage_core.
     - Background work via ProcessPoolExecutor is good, but queueing/backpressure, retries, and failure isolation are
   minimal; no dead-letter handling.
     - Core dependencies (models, tokenizer, collection schema) are scattered via environment; schema creation appears
Recommendations: converge all ingestion/chunking/embedding utilities on
    sage_core; expose a single ingestion service or shared package used by dashboard, vault, and refinery; centralize
   collection/schema management; introduce a real task queue (RQ/Celery/Redis) for retries and backpressure; document
   and enforce config via env schema.

     - Detailed Findings by Category

   Architecture

     - Findings: Multiple ingestion pipelines (dashboard.ingest, sage_core, refinery, vault) with overlapping but not
   identical logic and collection creation. No unified service boundary for processing; background jobs use in-memory
   executor only in dashboard.
     - Why It Matters: Divergence causes inconsistent indexing, schema drift, and harder maintenance; lack of
   queueing/backpressure can drop or stall uploads under load.
     - Recommended Improvements: Refactor all services to import ingestion/chunking/collection helpers from sage_core;
    expose ingestion as a single worker service with a queue; ensure collection creation uses one path.

   Code Quality

     - Findings: Good docstrings and typing in backend; duplication of chunking/token counting code across modules;
   some silent exception catches in ingestion and job management (broad except: pass).
     - Why It Matters: Duplication invites subtle bugs; silent failures hide ingestion errors and make debugging
   difficult.
     - Recommended Improvements: Deduplicate via shared helpers; replace broad except with logged, specific
   exceptions; add explicit error surfacing to clients.

   Correctness

     - Findings: Upload validation is solid, but downstream ingestion still writes files without verifying decode
   success; OCR path returns empty string on failure without propagating errors; get_document scroll limit is capped
   at 100 chunks (truncation risk).
     - Why It Matters: Lost content or partial documents reduce search quality; silent failures mask bad ingest; large
    documents may be truncated.
     - Recommended Improvements: Propagate ingestion errors to job status; add pagination/streaming for get_document;
   verify decode and reject unsupported encodings; add checksum/logging for stored files.

   Security

     - Findings: No authentication/authorization on any API or MCP; dashboard exposes upload/delete operations openly.
    OCR/Docx/Excel parsing runs in-process without sandboxing; remote embedding and OCR endpoints allow SSRF unless
   constrained. No rate limiting.
     - Why It Matters: Unauthenticated file upload/delete is a high-risk vulnerability; parser exploits can achieve
   RCE/DoS; SSRF can exfiltrate or pivot; lack of limits allows abuse.
     - Recommended Improvements: Add auth (at least token/API key) and role separation for upload/delete; sandbox
   heavy parsers (containerize or seccomp/AppArmor) and timeouts per job; enforce outbound allowlists for remote
   embedding/OCR URLs; add rate limiting/request size limits at the gateway; ensure uploads directory permissions are
   restrictive.

   Performance

     - Findings: Embeddings and OCR are CPU/GPU heavy; ProcessPool without queue sizing/backpressure; tokenizers
   lazily load per process; remote embeddings lack circuit breakers and caching.
     - Why It Matters: Under load, processes can thrash or exhaust memory; OCR can hang; remote calls can cascade
   failures.
     - Recommended Improvements: Configure bounded queues with backpressure; preload models in workers; add
   timeouts/retries/breakers for remote embedding; cache embeddings for identical chunks; monitor process pool
   saturation.

   Testing

     - Findings: Unit tests only cover chunking/validation/file_processing; no coverage for API routes, async upload
   flows, MCP tools, or end-to-end indexing/search. No CI visible.
     - Why It Matters: High-risk areas (auth absence, ingestion, search scoring) untested; regressions likely.
     - Recommended Improvements: Add integration tests for upload/search/delete, async job status, MCP tools; add
   smoke tests for collection creation; wire CI (pytest + lint).

   Operations

     - Findings: docker-compose present, but no health/readiness for MCP; dashboard has health/ready. No
   metrics/tracing; logging mostly basicConfig; secrets via env without template; no data retention/cleanup beyond
   jobs.
     - Why It Matters: Hard to operate/monitor in prod; failures in MCP unnoticed; env drift.
     - Recommended Improvements: Add health/ready to MCP; structured JSON logging and correlation IDs; metrics
   (Prometheus) around ingest/search latency, pool queue depth; env sample for required vars; backups/retention plan
   for Qdrant/uploads; add rate limiting and request size limits at proxy.

     - Priority-Ordered Action Plan

   P0 – Critical

     - Add authentication/authorization for dashboard/MCP upload/delete/search APIs; at minimum API key/token with
   RBAC. (Benefit: blocks unauthorized uploads/deletes; Effort: M)
     - Sandbox and bound heavy parsers (OCR/docx/excel) with strict timeouts and allowlisted outbound; enforce request
    size limits and rate limiting. (Benefit: reduces RCE/DoS/SSRF; Effort: M)
     - Unify ingestion logic on sage_core and enforce single collection schema; remove duplicated ingest/chunking
   paths. (Benefit: prevents drift and ingestion inconsistencies; Effort: M)

   P1 – High

     - Introduce proper task queue/backpressure and retries for uploads (Redis/RQ/Celery) instead of raw ProcessPool;
   add dead-letter handling. (Benefit: reliability under load; Effort: M)
     - Add integration tests for API (upload/search/delete/status), async upload status, and MCP tools; wire CI.
   (Benefit: regression safety; Effort: M)
     - Add outbound circuit breakers/timeouts for remote embeddings/OCR; cache/preload models in workers. (Benefit:
   stability; Effort: S-M)
     - Add health/ready endpoints to MCP; structured logging + request IDs across services. (Benefit: operability;
   Effort: S)

   P2 – Medium

     - Implement pagination/streaming for get_document and enforce chunk limits to avoid truncation. (Benefit:
   correctness for large docs; Effort: S)
     - Consolidate configuration into a single env schema with defaults and sample; validate on startup. (Benefit:
   reduces misconfig; Effort: S)
     - Add rate limiting and request body size caps at ingress (gateway/reverse proxy). (Benefit: DoS protection;
   Effort: S)
     - Add metrics for ingest/search latency, pool depth, Qdrant errors. (Benefit: observability; Effort: M)

   P3 – Nice to have

     - Upgrade embeddings to modern models (bge-m3 or nomic-embed-v1.5) with dimension checks and migration tooling.
   (Benefit: better relevance; Effort: S)
     - Provide optional rerank service behind feature flag with budgeted latency. (Benefit: improved results; Effort:
   M)
     - UI/UX improvements: clearer error surfacing, background task progress, stale job cleanup. (Benefit: usability;
   Effort: S)

     - Optional Strategic Improvements

     - Consolidate backend and MCP into a single FastAPI service exposing both HTTP and MCP transports, sharing
   sage_core for ingestion/search; reduces duplication and deployment surface. Tradeoff: tighter coupling and larger
   single binary, but simpler ops.
     - Introduce a dedicated ingestion worker service behind a message queue to isolate heavy parsing/OCR and allow
   horizontal scaling; tradeoff: more infra components but better resilience.
     - Add an API gateway (Traefik/Envoy) for TLS termination, auth, rate limiting, body limits, and outbound egress
   control; tradeoff: extra ops overhead, but critical for production hardening.