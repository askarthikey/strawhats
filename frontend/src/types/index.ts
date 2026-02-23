/* ===== User & Auth ===== */
export interface User {
  id: string;
  email: string;
  full_name: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

/* ===== Workspace ===== */
export interface Workspace {
  id: string;
  name: string;
  description: string;
  owner_id: string;
  members: WorkspaceMember[];
  created_at: string;
  updated_at: string;
}

export interface WorkspaceMember {
  user_id: string;
  role: "owner" | "editor" | "viewer";
  email?: string;
  name?: string;
}

/* ===== Paper ===== */
export type PaperStatus = "pending" | "processing" | "indexed" | "failed";

export interface Paper {
  id: string;
  title: string;
  authors: string[];
  doi: string | null;
  year: number | null;
  venue: string | null;
  abstract: string | null;
  pdf_url: string | null;
  source: string;
  workspace_id: string;
  status: PaperStatus;
  storage_path: string | null;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface PaperMetadata {
  title: string;
  authors: string[];
  doi: string | null;
  year: number | null;
  venue: string | null;
  abstract: string | null;
  pdf_url: string | null;
  license: string | null;
  source: string;
}

/* ===== Search ===== */
export interface SearchResult {
  chunk_id: string;
  paper_id: string;
  paper_title: string;
  text: string;
  score: number;
  page_number: number;
  chunk_index: number;
}

export interface SearchRequest {
  query: string;
  workspace_id: string;
  top_k?: number;
  threshold?: number;
}

/* ===== Chat ===== */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  timestamp: string;
  isStreaming?: boolean;
}

export interface Citation {
  chunk_id: string;
  paper_id: string;
  paper_title: string;
  text_preview: string;
  page_number: number;
  citation_number: number;
}

export interface ChatRequest {
  query: string;
  workspace_id: string;
  mode?: "qa" | "summarize" | "compare" | "extract_methods" | "review";
  paper_ids?: string[];
  chat_history?: Array<{ role: string; content: string }>;
}

export interface ChatStreamEvent {
  event: "token" | "citations" | "done" | "error";
  data: string;
}

/* ===== Draft ===== */
export interface Draft {
  id: string;
  title: string;
  content: string;
  workspace_id: string;
  created_by: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface DraftVersion {
  id: string;
  draft_id: string;
  version: number;
  content: string;
  created_at: string;
  created_by: string;
}

/* ===== Admin ===== */
export interface HealthCheck {
  status: "healthy" | "degraded";
  services: Record<string, { status: string; error?: string }>;
}

export interface Metrics {
  users: number;
  workspaces: number;
  papers: number;
  chunks: number;
  chat_logs: number;
  drafts: number;
  [key: string]: number;
}
