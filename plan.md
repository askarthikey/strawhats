# ResearchHub AI — Implementation Plan

**Source:** Generated from README.md master specification  
**Stack:** FastAPI (Python) + React + TypeScript + Tailwind + shadcn/ui  
**Theme:** Supabase (green #3ECF8E + dark #1C1C1C)  
**LLM:** Ollama (Llama 3.2) with Gemini API fallback  
**Database:** MongoDB Atlas M0  
**Vectors:** Pinecone free tier  
**Storage:** Cloudinary (raw uploads for PDFs)  
**Auth:** JWT + Email/Password  
**Ports:** Backend 8000, Frontend 3000  

---

## Project Structure

```
genai_hack/
├── backend/
│   ├── .venv/
│   ├── requirements.txt
│   ├── .env
│   ├── app/
│   │   ├── main.py                  # FastAPI app entry + CORS + lifespan
│   │   ├── config.py                # Settings via pydantic-settings
│   │   ├── database.py              # MongoDB Atlas connection (motor)
│   │   ├── auth/
│   │   │   ├── router.py            # /auth/register, /auth/login, /auth/me
│   │   │   ├── schemas.py           # Pydantic models
│   │   │   ├── service.py           # JWT creation, password hashing
│   │   │   └── dependencies.py      # get_current_user dependency
│   │   ├── papers/
│   │   │   ├── router.py            # /papers/import, /papers/upload, /papers/batch
│   │   │   ├── schemas.py
│   │   │   ├── service.py           # Ingestion logic, dedup, metadata normalization
│   │   │   ├── ingestion.py         # OpenAlex, Crossref, arXiv, PubMed clients
│   │   │   └── processing.py        # PDF extraction, chunking, embedding
│   │   ├── search/
│   │   │   ├── router.py            # /search/semantic, /search/hybrid
│   │   │   ├── schemas.py
│   │   │   └── service.py           # Pinecone query, MMR, hybrid retrieval
│   │   ├── chat/
│   │   │   ├── router.py            # /chat/stream (SSE), /chat/history
│   │   │   ├── schemas.py
│   │   │   ├── service.py           # RAG pipeline: retrieve → rerank → generate
│   │   │   └── prompts.py           # System prompts, prompt templates
│   │   ├── workspaces/
│   │   │   ├── router.py            # /workspaces CRUD, invites, permissions
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   ├── drafts/
│   │   │   ├── router.py            # /drafts CRUD, versions, diff, rollback
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   ├── references/
│   │   │   ├── router.py            # /references/bibtex, /references/ris
│   │   │   └── service.py
│   │   ├── latex/
│   │   │   ├── router.py            # /latex/generate, /latex/compile
│   │   │   └── service.py
│   │   ├── admin/
│   │   │   ├── router.py            # /admin/health, /admin/metrics
│   │   │   └── service.py
│   │   ├── storage/
│   │   │   └── supabase_client.py   # Supabase Storage bucket operations
│   │   ├── embeddings/
│   │   │   └── service.py           # sentence-transformers embed, batch embed
│   │   ├── llm/
│   │   │   ├── ollama_client.py     # Ollama Llama 3.2 client (streaming)
│   │   │   ├── gemini_client.py     # Google Gemini API client (streaming)
│   │   │   └── provider.py          # LLM provider selector/factory
│   │   └── utils/
│   │       ├── pinecone_client.py   # Pinecone init, upsert, query
│   │       ├── citations.py         # Parse [[CITE:chunk_id]], resolve metadata
│   │       └── helpers.py           # Common utilities
│   └── tests/
│       ├── test_ingestion.py
│       ├── test_chunking.py
│       ├── test_search.py
│       └── test_chat.py
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── components.json              # shadcn/ui config
│   ├── .env
│   ├── public/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx                  # Router setup
│   │   ├── index.css                # Tailwind + Supabase theme CSS vars
│   │   ├── lib/
│   │   │   ├── utils.ts             # cn() helper
│   │   │   ├── api.ts               # Axios/fetch instance
│   │   │   └── auth.ts              # JWT storage, auth context
│   │   ├── components/
│   │   │   ├── ui/                  # shadcn components (button, input, card, skeleton, dialog, etc.)
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.tsx      # Dark sidebar with Supabase theme
│   │   │   │   ├── Header.tsx
│   │   │   │   └── AppLayout.tsx
│   │   │   ├── chat/
│   │   │   │   ├── ChatPane.tsx     # Streaming chat with SSE
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   ├── CitationCard.tsx
│   │   │   │   └── ChatSkeleton.tsx
│   │   │   ├── papers/
│   │   │   │   ├── PaperCard.tsx
│   │   │   │   ├── PaperImport.tsx
│   │   │   │   ├── PaperUpload.tsx
│   │   │   │   ├── PaperViewer.tsx  # PDF viewer with highlights
│   │   │   │   └── PaperSkeleton.tsx
│   │   │   ├── search/
│   │   │   │   ├── SearchBar.tsx
│   │   │   │   ├── SearchResults.tsx
│   │   │   │   └── SearchSkeleton.tsx
│   │   │   ├── workspace/
│   │   │   │   ├── WorkspaceCard.tsx
│   │   │   │   ├── WorkspaceMembers.tsx
│   │   │   │   └── ActivityFeed.tsx
│   │   │   ├── drafts/
│   │   │   │   ├── DraftEditor.tsx  # Markdown editor with auto-save
│   │   │   │   ├── VersionHistory.tsx
│   │   │   │   └── DiffView.tsx
│   │   │   ├── literature/
│   │   │   │   └── LiteratureMap.tsx # D3/force-graph canvas
│   │   │   ├── latex/
│   │   │   │   └── LaTeXPanel.tsx
│   │   │   ├── references/
│   │   │   │   └── ReferenceExport.tsx
│   │   │   └── prompts/
│   │   │       └── PromptSelector.tsx
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── RegisterPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── WorkspacePage.tsx
│   │   │   ├── ChatPage.tsx
│   │   │   ├── SearchPage.tsx
│   │   │   ├── PapersPage.tsx
│   │   │   ├── DraftsPage.tsx
│   │   │   ├── LiteratureMapPage.tsx
│   │   │   ├── SettingsPage.tsx
│   │   │   └── AdminPage.tsx
│   │   ├── hooks/
│   │   │   ├── useAuth.ts
│   │   │   ├── useSSE.ts            # SSE streaming hook
│   │   │   ├── useWorkspace.ts
│   │   │   └── usePapers.ts
│   │   ├── contexts/
│   │   │   ├── AuthContext.tsx
│   │   │   └── WorkspaceContext.tsx
│   │   └── types/
│   │       └── index.ts             # All TypeScript interfaces
│   └── index.html
└── README.md
```

---

## Phase 0: Environment & Scaffolding

### Step 1: Backend Setup
- Create `backend/` directory
- `cd backend && python -m venv .venv`
- Create `requirements.txt`:
  - fastapi, uvicorn[standard], motor, pydantic[email], pydantic-settings
  - python-jose[cryptography], passlib[bcrypt], python-multipart
  - httpx, pymupdf, pdfplumber, sentence-transformers
  - pinecone-client, supabase, sse-starlette, ujson
  - python-dotenv, tiktoken, scikit-learn
  - google-generativeai, bibtexparser, diff-match-patch, pytest
- `.venv\Scripts\pip install -r requirements.txt`

### Step 2: Backend .env
```
MONGODB_URI=mongodb+srv://...
PINECONE_API_KEY=...
PINECONE_INDEX=researchhub
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=...
GEMINI_API_KEY=...
OLLAMA_BASE_URL=http://localhost:11434
JWT_SECRET=your-super-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=1440
```

### Step 3: Frontend Setup
- `npx create-vite@latest frontend --template react-ts`
- `cd frontend && npm install`
- `npm install -D tailwindcss @tailwindcss/typography postcss autoprefixer`
- `npx tailwindcss init -p`
- `npx shadcn@latest init` (dark mode, Supabase green theme)
- `npm install react-router-dom axios react-markdown remark-gfm react-pdf lucide-react react-force-graph-2d @uiw/react-md-editor diff`

### Step 4: Supabase Theme CSS Variables
```css
@layer base {
  :root {
    --background: 0 0% 11%;         /* #1C1C1C */
    --foreground: 0 0% 93%;         /* #EDEDED */
    --card: 0 0% 14%;               /* #232323 */
    --card-foreground: 0 0% 93%;
    --popover: 0 0% 14%;
    --popover-foreground: 0 0% 93%;
    --primary: 153 72% 53%;         /* #3ECF8E */
    --primary-foreground: 0 0% 9%;
    --secondary: 0 0% 17%;          /* #2A2A2A */
    --secondary-foreground: 0 0% 93%;
    --muted: 0 0% 17%;
    --muted-foreground: 0 0% 56%;   /* #8F8F8F */
    --accent: 153 72% 53%;
    --accent-foreground: 0 0% 9%;
    --destructive: 0 84% 60%;
    --destructive-foreground: 0 0% 93%;
    --border: 0 0% 20%;             /* #333333 */
    --input: 0 0% 20%;
    --ring: 153 72% 53%;
    --radius: 0.5rem;
  }
}
```

### Step 5: shadcn Components to Install
```
button input card skeleton dialog dropdown-menu avatar badge tabs tooltip sheet separator scroll-area select textarea toast sonner
```

---

## Phase 1: Backend Core — Config, Database, Auth

### Step 6: app/config.py
- `pydantic_settings.BaseSettings` loading all env vars
- Fields: MONGODB_URI, PINECONE_API_KEY, PINECONE_INDEX, SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY, OLLAMA_BASE_URL, JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_MINUTES

### Step 7: app/database.py
- `motor.motor_asyncio.AsyncIOMotorClient` singleton
- Database getter function
- Startup index creation: unique on users.email, papers.doi; compound on chunks.paper_id+chunk_id; text index on papers.title+abstract

### Step 8: app/auth/
- `schemas.py`: UserCreate, UserLogin, UserResponse, TokenResponse
- `service.py`: hash_password (bcrypt), verify_password, create_access_token (JWT), decode_token
- `dependencies.py`: get_current_user FastAPI dependency
- `router.py`: POST /auth/register, POST /auth/login, GET /auth/me

### Step 9: app/main.py
- FastAPI app with lifespan (startup: connect MongoDB, init Pinecone, load embedding model; shutdown: close)
- CORS middleware (allow localhost:3000)
- Include all routers with prefixes

---

## Phase 2: Storage, Ingestion & Document Processing

### Step 10: app/storage/supabase_client.py
- Supabase client init
- upload_pdf(file, paper_id) → upload to "papers" bucket
- get_pdf_url(paper_id) → signed URL
- delete_pdf(paper_id)

### Step 11: app/papers/ingestion.py
- Async httpx clients for: OpenAlex, Crossref, arXiv, PubMed, Unpaywall
- All return normalized PaperMetadata schema
- Respect rate limits, set user-agent

### Step 12: app/papers/processing.py
- extract_text_from_pdf(pdf_bytes) → structured text with page numbers (PyMuPDF)
- chunk_text(text, target_tokens=1000, overlap_tokens=200) → list of ChunkData
- detect_code_blocks(text) → code snippets
- detect_tables(pdf_bytes) → tables as CSV

### Step 13: app/embeddings/service.py
- Load all-MiniLM-L6-v2 model (384 dims, cached singleton)
- embed_text(text) → vector
- embed_batch(texts) → list of vectors
- LRU cache for repeated queries

### Step 14: app/utils/pinecone_client.py
- init_pinecone() → create/get index (384 dims, cosine)
- upsert_chunks(chunks_with_embeddings, namespace) → batch upsert
- query_similar(vector, top_k, namespace, filters) → matches
- delete_by_paper(paper_id, namespace)

### Step 15: app/papers/service.py
- import_paper(doi_or_query, workspace_id) → full pipeline: search APIs → dedup → MongoDB → PDF fetch → Supabase upload → extract → chunk → embed → Pinecone upsert
- upload_paper(file, workspace_id, user_id) → upload → extract → chunk → embed → upsert
- batch_import(doi_list, workspace_id) → background task

### Step 16: app/papers/router.py
- POST /papers/search-external
- POST /papers/import
- POST /papers/upload
- POST /papers/batch-import
- GET /papers/{paper_id}
- GET /papers/
- DELETE /papers/{paper_id}

---

## Phase 3: Search & RAG Chat

### Step 17: app/search/service.py
- semantic_search(query, workspace_id, top_k=10) → embed → Pinecone query → resolve metadata
- hybrid_search(query, workspace_id, top_k=10) → combine semantic + MongoDB text search
- mmr_rerank(results, query_vector, lambda=0.7) → MMR diversity reranking

### Step 18: app/search/router.py
- POST /search/semantic
- POST /search/hybrid

### Step 19: app/llm/ollama_client.py
- generate_stream(prompt, system_prompt, temperature=0.0) → async generator of tokens
- generate(prompt, system_prompt) → full response
- Health check

### Step 20: app/llm/gemini_client.py
- generate_stream(prompt, system_prompt, temperature=0.0) → async generator of tokens
- generate(prompt, system_prompt) → full response

### Step 21: app/llm/provider.py
- get_llm_provider(preference) → Ollama or Gemini client
- Fallback: Ollama → Gemini if unavailable

### Step 22: app/chat/prompts.py
- RAG_SYSTEM_PROMPT with [[CITE:chunk_id]] enforcement
- SUMMARIZE, COMPARE, EXTRACT_METHODS, GENERATE_REVIEW templates
- build_context_block(chunks) → formatted context
- Copyright guard (no verbatim >25 words)

### Step 23: app/chat/service.py
- rag_generate(question, workspace_id, user_id, chat_history, template, provider):
  1. Embed question
  2. Retrieve top-k chunks (Pinecone)
  3. MMR rerank
  4. Token budget trimming
  5. Build prompt (system + context + history + question)
  6. Stream LLM generation
  7. Parse [[CITE:chunk_id]] → resolve citations
  8. Store chat log in MongoDB
  9. Yield {token, citations[], done} events

### Step 24: app/utils/citations.py
- parse_citations(text) → extract [[CITE:chunk_id]]
- resolve_citations(chunk_ids, db) → [{paper_id, title, page, snippet, score, chunk_id}]

### Step 25: app/chat/router.py
- POST /chat/stream (SSE endpoint)
- GET /chat/history/{workspace_id}
- DELETE /chat/history/{workspace_id}

---

## Phase 4: Workspaces, Drafts & Collaboration

### Step 26: app/workspaces/
- schemas.py: WorkspaceCreate, WorkspaceResponse, InviteRequest, MemberRole enum
- service.py: CRUD, member management (Owner/Editor/Commenter/Viewer), invite links
- router.py: POST/GET/PUT/DELETE /workspaces/, POST /workspaces/{id}/invite, POST /workspaces/{id}/join, GET /workspaces/{id}/members

### Step 27: app/drafts/
- schemas.py: DraftCreate, DraftUpdate, DraftResponse, VersionResponse
- service.py: CRUD, auto-save, snapshot, version history, diff, rollback, branch
- router.py: POST/GET/PUT/DELETE /drafts/, POST /drafts/{id}/snapshot, GET /drafts/{id}/versions, GET /drafts/{id}/versions/{v1}/diff/{v2}, POST /drafts/{id}/rollback/{version_id}

---

## Phase 5: References, LaTeX & Admin

### Step 28: app/references/
- service.py: to_bibtex(paper_ids), to_ris(paper_ids)
- router.py: POST /references/bibtex, POST /references/ris

### Step 29: app/latex/
- service.py: generate_latex(prompt, type) via LLM
- router.py: POST /latex/generate, POST /latex/compile

### Step 30: app/admin/
- service.py: health checks, metrics collection
- router.py: GET /admin/health, GET /admin/metrics

---

## Phase 6: Frontend — Theme, Layout & Auth

### Step 31: Supabase Theme + shadcn Config
- index.css with CSS variables (see Phase 0 Step 4)
- tailwind.config.ts mapped to CSS variables
- components.json configured for dark Supabase palette

### Step 32: Layout Components
- Sidebar.tsx — dark #1C1C1C, green active indicators, nav: Dashboard/Chat/Search/Papers/Drafts/Map/Settings, workspace selector, collapsible
- Header.tsx — breadcrumbs, user avatar dropdown
- AppLayout.tsx — sidebar + header + content outlet

### Step 33: Auth Pages
- LoginPage.tsx — dark card, green buttons, email/password
- RegisterPage.tsx — matching style
- AuthContext.tsx — JWT management, protected routes
- useAuth.ts hook

### Step 34: API Client
- lib/api.ts — Axios with base URL localhost:8000, JWT interceptor

### Step 35: Router
- App.tsx — React Router v6, all routes, auth/workspace providers

---

## Phase 7: Frontend — Core Feature Pages

### Step 36: Dashboard
- DashboardPage.tsx — workspace list, create dialog, activity feed, skeletons

### Step 37: Chat (Core RAG Interface)
- ChatPane.tsx — SSE streaming, message list, auto-scroll, input + template selector
- MessageBubble.tsx — markdown render, inline citation chips
- CitationCard.tsx — expandable: paper title, page, snippet, score, PDF link
- ChatSkeleton.tsx — shimmer loading
- useSSE.ts — SSE hook for /chat/stream

### Step 38: Search
- SearchBar.tsx — mode toggle (semantic/hybrid), filters
- SearchResults.tsx — ranked cards with scores, snippets
- SearchSkeleton.tsx

### Step 39: Papers
- PaperCard.tsx — metadata + status badge
- PaperImport.tsx — external API search modal
- PaperUpload.tsx — drag-and-drop PDF upload
- PaperViewer.tsx — PDF viewer (react-pdf) with highlights
- PaperSkeleton.tsx

### Step 40: Drafts
- DraftEditor.tsx — markdown editor, auto-save, insert-citation
- VersionHistory.tsx — version timeline
- DiffView.tsx — side-by-side diff

### Step 41: Literature Map
- LiteratureMap.tsx — force-directed graph (react-force-graph-2d), nodes by cluster

### Step 42: Supporting Components
- PromptSelector.tsx — template dropdown
- ReferenceExport.tsx — format selector + download
- LaTeXPanel.tsx — generation + syntax highlight + copy

---

## Phase 8: Frontend — Workspace & Settings

### Step 43: WorkspacePage.tsx — tabs: Papers/Chat/Drafts/Map/Members, settings, invite dialog
### Step 44: SettingsPage.tsx — profile, LLM preference, API keys
### Step 45: AdminPage.tsx — health dashboard, metrics, usage stats

---

## Phase 9: Polish & Testing

### Step 46: Error handling — toast notifications, fallback UI, SSE retry
### Step 47: Skeleton loading on every async page
### Step 48: Backend tests — test_ingestion, test_chunking, test_search, test_chat
### Step 49: Startup scripts — run.bat for backend (activate venv + uvicorn)
### Step 50: .env.example with all documented variables

---

## Verification Checklist

- [ ] `GET /admin/health` → MongoDB, Pinecone, Ollama, Supabase status
- [ ] Register → Login → JWT → Access protected endpoints
- [ ] Import paper by DOI → MongoDB + Pinecone + Supabase Storage verified
- [ ] RAG chat → streaming + [[CITE:chunk_id]] citations resolved
- [ ] Semantic search → ranked results with snippets
- [ ] Drafts: Create → Edit → Snapshot → Versions → Diff → Rollback
- [ ] All pages load with skeletons → data populates → consistent Supabase theme
- [ ] `cd backend && .venv\Scripts\python -m pytest tests/ -v`
- [ ] `cd frontend && npm run dev` → localhost:3000

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM | Ollama (Llama 3.2) → Gemini fallback | Local-first, free, with cloud backup |
| Embeddings | all-MiniLM-L6-v2 (384d) | Lightweight, no API key needed |
| PDF storage | Supabase Storage | User requested, free tier available |
| Background tasks | FastAPI BackgroundTasks | No Redis dependency needed |
| Streaming | SSE (not WebSocket) | Simpler for one-directional chat |
| Theme | Supabase green #3ECF8E + dark #1C1C1C | User requested |
| UI library | shadcn/ui + Tailwind + skeletons | Consistent, accessible |
| MongoDB indexes | unique users.email, papers.doi; compound chunks.paper_id+chunk_id; text on papers.title+abstract | Performance + dedup |
| Package manager | npm (frontend) | User requested |
| Node frontend | React + TypeScript + Vite | User requested |
