# ResearchHub AI — Master Specification (Combined)

**Source materials:**
- Original project specification (uploaded file). fileciteturn0file0
- Retrieval-Augmented Generation (RAG) specification (added & expanded).

> This master markdown merges the full ResearchHub AI feature specification with a detailed RAG subsection and implementation guidance. Use this as the single source-of-truth for engineering, demo, and judging.

---

## Table of Contents
1. Executive summary
2. Core product features (detailed)
3. Workspace UX: drafts, versioning, permissions
4. LLM features: LaTeX/code generation, prompt templates, safety
4.x Retrieval-Augmented Generation (RAG)
5. Backend architecture & concurrency management
6. Ingestion & web APIs (safe scraping)
7. Search, embeddings, and Pinecone design
8. Provenance, citations & explainability
9. Streaming & frontend UX
10. Data model (MongoDB schemas)
11. APIs & example endpoints
12. Security, privacy, and legal considerations
13. Testing & quality assurance
14. Hackathon MVP picks & 48-hour plan
15. Checklist & deliverables
16. Appendix: sample prompts and LaTeX generation examples

---

# 1. Executive summary
ResearchHub AI is an agentic research assistant that allows teams to ingest literature, run semantic search, and get citation-grounded answers powered by **Llama 3.2**. It must be fast (streaming UI), reliable (provenance), and student-cost-friendly (Pinecone free tier + MongoDB Atlas M0). This document defines the complete feature set and implementation guidance.

(Original project description and workflow — see uploaded file for full context). fileciteturn0file0

---

# 2. Core product features (detailed)

### A. Discovery & Ingestion
- API-first ingestion (OpenAlex, Crossref, arXiv, PubMed).
- Metadata normalization (title, authors[], doi, year, venue, abstract, pdf_url, license).
- DOI-first deduplication; fallback title/author/year hash.
- OA PDF automatic fetch via Unpaywall when allowed.
- Manual paper import via upload (PDF) — user-owned documents.
- Batch ingestion job support (CSV/DOI lists).

### B. Document Processing
- PDF extraction: PyMuPDF / pdfplumber; OCR with Tesseract for scanned documents.
- Chunking: 1000-token target, 200-token overlap (tweakable).
- Store chunk metadata: `{paper_id, chunk_id, page_number, char_start, char_end, checksum}`.
- Table & figure extraction + CSV export.
- Code block detection in papers (LaTeX, pseudo-code) and extraction.

### C. Semantic Search & Retrieval
- Embedding model: sentence-transformers or Llama-compatible embedding model.
- Vector store: Pinecone index (namespace per workspace optionally).
- Top-k retrieval + MMR (maximal marginal relevance) option.
- Hybrid retrieval: keyword + semantic filter.

### D. Chat & Synthesis
- Workspace-contextual chat (conversational memory).
- Multi-document synthesis (summaries, compare, contrast).
- Citation-grounded answers with chunk-level citations.
- Streaming token-level responses with progressive citation cards.

### E. Provenance & Explainability
- For every answer, return `citations: [{paper_id,title,page, snippet,score,chunk_id}]`.
- UI shows snippet highlights and links to open PDF at exact page and char offsets.
- Response confidence and retrieval scores shown.

### F. Productivity Features
- LaTeX generation: generate LaTeX snippets (equations, tables, algorithm pseudocode), compile preview (optional), and export.
- Code generation: export runnable code snippets (Python, Bash) from methods or reproducibility sections.
- Reference export: BibTeX, RIS, direct push to Zotero/EndNote.
- Saved prompts & templates (literature review, intro paragraph, methods summary).
- Saved semantic queries & alerts (email/in-app).

### G. Workspace & Collaboration
- Multiple workspaces per user and shared workspaces for teams.
- Roles & permissions: Owner, Editor, Viewer.
- Drafts: Each workspace supports Draft objects for in-progress writeups.
- Versioning: Draft version history with diff & rollback.
- Inline comments & annotations on PDF (per user).
- Activity feed & workspace analytics.

---

# 3. Workspace UX: Drafts, Versioning, Permissions

### Drafts
- Draft is a first-class entity: `{draft_id, workspace_id, title, content_markdown, author_id, created_at, updated_at, version}`.
- Auto-save every N seconds; manual Save as Snapshot (version).
- Drafts can include citations and embedded snippets; store list of referenced chunk_ids to maintain provenance.

### Versioning
- On each publish or snapshot: create a new version object `{version_id, draft_id, author, timestamp, diff_summary}`.
- Provide UI to compare versions (side-by-side diff), rollback, or branch (create new draft from version).

### Permissions
- Roles: Owner (full), Editor (edit + invite), Commenter (annotate), Viewer (read-only).
- Workspace invites by email or shareable link with expiration.
- Per-document sharing with granular rights (view-only, comment, edit).

---

# 4. LLM features: LaTeX / Code generation, prompt templates, safety

(Full LLM feature guidance — generation, templates, code extraction, LaTeX, and copyright constraints are included.)

### LaTeX Generation
- Feature: generate LaTeX for equations, tables, figures, algorithm pseudocode.
- Quick export to .tex and optional server-side compile preview (dockerized pdfLaTeX) with resource limits.

### Code Generation
- Detect code blocks; provide "Generate runnable example" producing minimal scripts + test scaffolding.

### Prompt Templates & Safety
- Pre-defined system messages for research tasks: Summarize, Compare, Extract Methods, Generate Review.
- Default low temperature for factual synthesis; optional creative mode.
- Copyright rules: do not produce verbatim >25 words from a single source unless user uploaded and consents.

---

# 4.x Retrieval-Augmented Generation (RAG)

**Purpose:** RAG combines a fast retriever (vector + optional keyword filters) with a generative model (**Llama 3.2**) so answers are grounded in retrieved evidence.

## Core design
- **Two-/Three-stage pipeline:** Retrieve → (Optional Re-rank / Condense) → Generate.
- **Chunk budgeting:** enforce token budget so generator prompt + context ≤ model context window.
- **Citation protocol:** model must append `[[CITE:chunk_id]]` tokens inline; post-process to resolve chunk metadata.
- **Hybrid retrieval:** combine lexical + semantic retrieval when needed for exact matches.
- **Context condensation:** send condensed summaries for long text where necessary; allow full context viewing on demand.

## Prompt engineering (recommended template)
- System: low temperature, citation enforcement, instruction to not invent facts beyond provided chunks.
- Context: list of retrieved chunks in `[chunk_id | paper_title | page] snippet` format.

## Relevance & faithfulness strategies
- Cross-encoder reranker for high precision (re-score top candidates).
- MMR for diversity in survey-like queries.
- Optional fact-check pass post-generation comparing claims against retrieved chunks.
- Conservative defaults: low temperature, explicit refusal when unsupported.

## Provenance & explainability
- Always return `used_chunks`, `model_params`, `retrieval_trace` and retrieval/reranker scores.
- Confidence metric per claim (heuristic from reranker + generator alignment).

## Streaming & UX
- Stream tokens via SSE/WebSocket and stream citation-resolve messages when `[[CITE:*]]` is emitted.
- Client progressively renders tokens and shows citation cards when resolved.

## Backend constraints
- Batch retrieval and embed calls; use LRU caches for repeated queries.
- Semaphore + rate limit to cap concurrent rerank/generation tasks.
- Fallback on Pinecone or reranker failures (cached or lexical results).

## Safety & copyright
- Do not return verbatim >25 words from any single source unless user owns the document and explicitly consents.
- Filter PII and sensitive content unless user owns the document and requests it.

## Metrics & demo scenarios
- Track retrieval latency, reranker latency, generation latency, precision@k, hallucination rate.
- Demo: side-by-side baseline vs RAG vs RAG+reranker to showcase factuality and provenance.

---

# 5. Backend architecture & concurrency management

(Complete architecture recommendations: FastAPI, worker queue, embedding batching, semaphores, circuit breaker, monitoring.)

Key components:
- FastAPI Async API Gateway (HTTP + SSE/WebSocket).
- Background Worker Pool (RQ / Dramatiq / Celery with Redis).
- Batch embedding workers, Pinecone client, MongoDB Atlas for metadata, optional Redis cache.
- Embedding batching, semaphores, circuit breakers, retries with backoff.

Low-level optimizations: HTTP keep-alive, ujson serialization, compressed batch upserts.

---

# 6. Ingestion & web APIs (safe scraping)

Preferred sources: OpenAlex, Crossref, arXiv, PubMed, Unpaywall, CORE.

Ingestion flow: metadata → (if OA) PDF fetch → extract text → chunk → batch embed → Pinecone upsert → mark indexed.

Scraping rules: respect robots.txt, throttle requests, set contact UA, avoid paywalled content.

---

# 7. Search, embeddings, and Pinecone design

Embedding strategy: lightweight sentence embeddings for chunks; store compact metadata both in Mongo and Pinecone metadata field.

Pinecone design: single index per environment; namespace per workspace optional; bulk upserts; metadata filtering.

Retrieval: cosine top-k, MMR, hybrid filters.

Cost-control: sandbox dataset for demo, caching, and smaller models for retrieval.

---

# 8. Provenance, citations & explainability

Citation tokens: enforce `[[CITE:chunk_id]]` in generator output.

Post-processing: parse tokens, resolve to `{paper_title, page, snippet, score}` and attach to responses.

UI: inline citations, side panel with snippets and open-at-offset links.

Audit logs: store `{request_id, workspace_id, user_id, timestamp, used_chunk_ids, model_params}`.

---

# 9. Streaming & frontend UX

Streaming: SSE or WebSockets for token streaming and async citation resolution.

Frontend components: chat pane with streaming, citations side-panel, DocSpace editor with versioning, literature map canvas, paper viewer with highlights.

---

# 10. Data model (MongoDB schemas)

(Users, Workspaces, Papers, Chunks, Drafts, Chat logs schemas provided.)

---

# 11. APIs & example endpoints

Authentication, Papers import/upload, Chat (streaming), Search, Drafts CRUD, Admin monitoring endpoints.

---

# 12. Security, privacy, and legal considerations

- Do not store paywalled PDFs without explicit permission.
- Copyright rules for verbatim text >25 words.
- Use HTTPS, secure JWTs, per-workspace isolation, retention & deletion UI for GDPR.

---

# 13. Testing & quality assurance

Unit tests for ingestion and chunking, integration tests for Pinecone, E2E tests for streaming and citation resolution, load testing and manual QA with a curated dataset.

---

# 14. Hackathon MVP picks & 48-hour plan

MVP: (1) Citation-grounded streaming chat, (2) Async ingestion pipeline, (3) Literature map.

48-hour plan: Setup → Backend core (ingestion pipeline) → Chat & UI with streaming and citation panel → Demo polish.

---

# 15. Checklist & deliverables

(Complete list of deliverables: repo, MongoDB, Pinecone, ingestion endpoints, workers, chunking, embeddings, chat endpoint with token streaming, UI, dataset, README, demo.)

---

# 16. Appendix — sample prompts & LaTeX examples

Include the sample prompts from the original spec (citation-enforcing prompt, LaTeX table generator, code generation prompt). For convenience, a minimal RAG prompt is included below.

**Minimal RAG prompt**

```
System: You are a factual research assistant. Use only the evidence provided below.
Append [[CITE:chunk_id]] whenever you use a fact.
If evidence is insufficient, say you do not have enough evidence.
Temperature: 0.0.

Context:
[chunk_12 | Paper A | p.4] ...
[chunk_19 | Paper B | p.7] ...

User: <question>
```

---

## Acknowledgements & source
This master file was created by merging the uploaded ResearchHub AI project document (see original file) and the RAG specification content added during the session. For the uploaded original project document, see here: fileciteturn0file0

---

_End of master specification._
