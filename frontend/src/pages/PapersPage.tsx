import { useState, useEffect, useRef, useCallback } from "react";
import { useParams } from "react-router-dom";
import api from "@/lib/api";
import type { Paper, PaperMetadata, SearchResult } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Search,
  Upload,
  FileText,
  Loader2,
  Trash2,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  Clock,
  RefreshCw,
  Plus,
  MessageSquare,
  BookOpen,
  Download,
  Copy,
  Check,
  GripVertical,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { ChatPanel } from "@/components/ChatPanel";

const STATUS_CONFIG: Record<string, { icon: React.ElementType; color: string; label: string }> = {
  pending: { icon: Clock, color: "text-yellow-500", label: "Pending" },
  processing: { icon: RefreshCw, color: "text-blue-400", label: "Processing" },
  indexed: { icon: CheckCircle2, color: "text-primary", label: "Indexed" },
  failed: { icon: AlertCircle, color: "text-destructive", label: "Failed" },
};

const MIN_CHAT_WIDTH = 280;
const MAX_CHAT_FRACTION = 0.6;
const DEFAULT_CHAT_WIDTH = 384;

export function PapersPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const [papers, setPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(true);

  // Discover tab state
  const [discoverQuery, setDiscoverQuery] = useState("");
  const [discoverResults, setDiscoverResults] = useState<PaperMetadata[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [importing, setImporting] = useState<string | null>(null);

  // Library search state
  const [librarySearch, setLibrarySearch] = useState("");
  const [semanticResults, setSemanticResults] = useState<SearchResult[]>([]);
  const [searchingLibrary, setSearchingLibrary] = useState(false);

  // Chat panel
  const [showChat, setShowChat] = useState(false);
  const [chatWidth, setChatWidth] = useState(DEFAULT_CHAT_WIDTH);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Upload & batch import
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [showBatchImport, setShowBatchImport] = useState(false);
  const [batchDois, setBatchDois] = useState("");
  const [batchImporting, setBatchImporting] = useState(false);

  // References state
  const [bibtex, setBibtex] = useState("");
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  // Paper processing status
  const [statusMessages, setStatusMessages] = useState<Record<string, string>>({});
  const wsRef = useRef<WebSocket | null>(null);
  const wsReconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wsReconnectAttempts = useRef(0);

  // Responsive: detect mobile
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const loadPapers = async () => {
    if (!workspaceId) return;
    try {
      const res = await api.get(`/papers/?workspace_id=${workspaceId}`);
      setPapers(res.data);
    } catch {
      toast.error("Failed to load papers");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPapers();
  }, [workspaceId]);

  // WebSocket for real-time paper processing status with reconnection
  const connectWs = useCallback(() => {
    if (!workspaceId) return;
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws/papers/status/${workspaceId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      wsReconnectAttempts.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "paper_status") {
          setPapers((prev) =>
            prev.map((p) =>
              p.id === data.paper_id
                ? {
                  ...p,
                  status: data.status,
                  status_reason: data.message || p.status_reason,
                  chunk_count: data.chunk_count || p.chunk_count,
                }
                : p
            )
          );
          setStatusMessages((prev) => ({ ...prev, [data.paper_id]: data.message || "" }));
          if (data.status === "indexed") {
            toast.success(`"${data.title || "Paper"}" indexed (${data.chunk_count} chunks)`);
          } else if (data.status === "failed") {
            toast.error(`"${data.title || "Paper"}" failed: ${data.message}`);
          }
        }
      } catch {
        // ignore
      }
    };

    ws.onclose = () => {
      // Reconnect with exponential backoff
      if (wsReconnectAttempts.current < 10) {
        const delay = Math.min(1000 * Math.pow(2, wsReconnectAttempts.current), 30000);
        wsReconnectAttempts.current += 1;
        wsReconnectTimer.current = setTimeout(connectWs, delay);
      }
    };

    ws.onerror = () => {
      // onclose will fire after onerror, so reconnection happens there
    };
  }, [workspaceId]);

  useEffect(() => {
    connectWs();
    return () => {
      if (wsReconnectTimer.current) clearTimeout(wsReconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connectWs]);

  // ---- Drag-to-resize chat panel ----
  const handleDragStart = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  useEffect(() => {
    if (!isDragging) return;

    const handlePointerMove = (e: PointerEvent) => {
      if (!containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const maxWidth = containerRect.width * MAX_CHAT_FRACTION;
      const newWidth = Math.max(MIN_CHAT_WIDTH, Math.min(containerRect.right - e.clientX, maxWidth));
      setChatWidth(newWidth);
    };

    const handlePointerUp = () => {
      setIsDragging(false);
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, [isDragging]);

  // Discover search
  const searchDiscover = async () => {
    if (!discoverQuery.trim()) return;
    setDiscovering(true);
    try {
      const res = await api.post("/papers/search-external", {
        query: discoverQuery.trim(),
        source: "openalex",
        limit: 10,
      });
      setDiscoverResults(res.data.papers || []);
    } catch {
      toast.error("Search failed");
    } finally {
      setDiscovering(false);
    }
  };

  // Library semantic search
  const searchLibrary = async () => {
    if (!librarySearch.trim() || !workspaceId) return;
    setSearchingLibrary(true);
    try {
      const res = await api.post("/search/hybrid", {
        query: librarySearch.trim(),
        workspace_id: workspaceId,
        top_k: 20,
      });
      setSemanticResults(res.data.results || []);
    } catch {
      toast.error("Search failed");
    } finally {
      setSearchingLibrary(false);
    }
  };

  const importPaper = async (metadata: PaperMetadata) => {
    if (!workspaceId) return;
    setImporting(metadata.doi || metadata.title);
    try {
      const res = await api.post(
        `/papers/import-metadata?workspace_id=${encodeURIComponent(workspaceId)}`,
        metadata,
      );
      setPapers((prev) => [res.data, ...prev]);
      setDiscoverResults((prev) => prev.filter((p) => p.doi !== metadata.doi));
      toast.success(`Imported: ${metadata.title.slice(0, 50)}...`);
    } catch {
      toast.error("Import failed");
    } finally {
      setImporting(null);
    }
  };

  const uploadPdf = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!workspaceId) return;
    const form = e.currentTarget;
    const formData = new FormData(form);
    formData.append("workspace_id", workspaceId);
    setUploading(true);
    try {
      const res = await api.post("/papers/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setPapers((prev) => [res.data, ...prev]);
      setShowUpload(false);
      toast.success("PDF uploaded and processing started");
    } catch {
      toast.error("Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const batchImport = async () => {
    if (!workspaceId || !batchDois.trim()) return;
    const dois = batchDois.split("\n").map((d) => d.trim()).filter(Boolean);
    if (dois.length === 0) return;
    setBatchImporting(true);
    try {
      const res = await api.post("/papers/batch-import", { dois, workspace_id: workspaceId });
      toast.success(`Imported ${res.data.imported}, skipped ${res.data.skipped}, failed ${res.data.failed}`);
      setShowBatchImport(false);
      setBatchDois("");
      loadPapers();
    } catch {
      toast.error("Batch import failed");
    } finally {
      setBatchImporting(false);
    }
  };

  const deletePaper = async (paperId: string) => {
    if (!workspaceId || !confirm("Delete this paper and all its data?")) return;
    try {
      await api.delete(`/papers/${paperId}?workspace_id=${workspaceId}`);
      setPapers((prev) => prev.filter((p) => p.id !== paperId));
      toast.success("Paper deleted");
    } catch {
      toast.error("Failed to delete paper");
    }
  };

  // References
  const generateBibtex = async () => {
    if (!workspaceId) return;
    setGenerating(true);
    try {
      const paperIds = papers.map((p) => p.id);
      if (paperIds.length === 0) { toast.error("No papers"); setGenerating(false); return; }
      const res = await api.post("/references/bibtex", { paper_ids: paperIds });
      setBibtex(res.data);
      toast.success("BibTeX generated");
    } catch {
      toast.error("Failed to generate BibTeX");
    } finally {
      setGenerating(false);
    }
  };

  const citeKey = (paper: Paper) => {
    const firstAuthor = (paper.authors?.[0] || "unknown").split(" ").pop()?.toLowerCase() || "unknown";
    return `${firstAuthor}${paper.year || "nd"}`;
  };

  const latexEntry = (paper: Paper) => {
    const key = citeKey(paper);
    const authors = paper.authors?.join(" and ") || "Unknown";
    return `@article{${key},\n  author = {${authors}},\n  title = {${paper.title}},\n  year = {${paper.year || "n.d."}},${paper.venue ? `\n  journal = {${paper.venue}},` : ""}${paper.doi ? `\n  doi = {${paper.doi}},` : ""}\n}`;
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    toast.success("Copied!");
    setTimeout(() => setCopied(null), 2000);
  };

  const downloadFile = (content: string, filename: string) => {
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  };

  // Filter papers in library by text search
  const filteredPapers = librarySearch.trim() && semanticResults.length === 0 && !searchingLibrary
    ? papers.filter((p) =>
      p.title.toLowerCase().includes(librarySearch.toLowerCase()) ||
      p.authors?.some((a) => a.toLowerCase().includes(librarySearch.toLowerCase()))
    )
    : papers;

  return (
    <div ref={containerRef} className="flex h-full overflow-hidden relative">
      {/* Drag overlay to prevent iframe/selection interference */}
      {isDragging && (
        <div className="fixed inset-0 z-50 cursor-col-resize" style={{ userSelect: "none" }} />
      )}

      {/* Main content */}
      <div
        className="flex-1 min-w-0 overflow-y-auto transition-all duration-200"
        style={showChat && !isMobile ? { marginRight: 0 } : {}}
      >
        <div className="p-4 sm:p-6 max-w-6xl mx-auto">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-3">
            <div>
              <h1 className="text-2xl font-bold text-foreground">Research</h1>
              <p className="text-muted-foreground text-sm mt-1">
                {papers.length} papers in this workspace
              </p>
            </div>
            <div className="flex gap-2 flex-wrap">
              <Button
                variant={showChat ? "default" : "outline"}
                onClick={() => setShowChat(!showChat)}
                className="gap-2"
              >
                <MessageSquare className="w-4 h-4" />
                <span className="hidden sm:inline">AI Chat</span>
              </Button>
              <Button variant="outline" onClick={() => setShowBatchImport(true)}>
                <Plus className="w-4 h-4 mr-1 sm:mr-2" />
                <span className="hidden sm:inline">Batch</span>
              </Button>
              <Button variant="outline" onClick={() => setShowUpload(true)}>
                <Upload className="w-4 h-4 mr-1 sm:mr-2" />
                <span className="hidden sm:inline">Upload</span>
              </Button>
            </div>
          </div>

          <Tabs defaultValue="library">
            <TabsList className="w-full sm:w-auto">
              <TabsTrigger value="library" className="text-xs sm:text-sm">Library ({papers.length})</TabsTrigger>
              <TabsTrigger value="discover" className="text-xs sm:text-sm">Discover</TabsTrigger>
              <TabsTrigger value="references" className="text-xs sm:text-sm">References</TabsTrigger>
            </TabsList>

            {/* ============ LIBRARY TAB ============ */}
            <TabsContent value="library" className="mt-4 space-y-4">
              {/* Search bar in library */}
              <div className="flex gap-2">
                <Input
                  placeholder="Search your papers (semantic + text)..."
                  value={librarySearch}
                  onChange={(e) => {
                    setLibrarySearch(e.target.value);
                    if (!e.target.value.trim()) setSemanticResults([]);
                  }}
                  onKeyDown={(e) => e.key === "Enter" && searchLibrary()}
                />
                <Button onClick={searchLibrary} disabled={searchingLibrary || !librarySearch.trim()}>
                  {searchingLibrary ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                </Button>
              </div>

              {/* Semantic search results */}
              {semanticResults.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-sm text-muted-foreground font-medium">
                      {semanticResults.length} search results
                    </p>
                    <Button variant="ghost" size="sm" onClick={() => { setSemanticResults([]); setLibrarySearch(""); }}>
                      Clear results
                    </Button>
                  </div>
                  {semanticResults.map((result, i) => (
                    <Card key={i} className="hover:border-border-hover transition-colors">
                      <CardContent className="p-3 sm:p-4">
                        <div className="flex items-start justify-between mb-1">
                          <div className="flex items-center gap-2 min-w-0">
                            <BookOpen className="w-4 h-4 text-primary shrink-0" />
                            <span className="font-medium text-sm text-foreground line-clamp-1">
                              {result.paper_title}
                            </span>
                          </div>
                          <Badge variant="outline" className="text-xs shrink-0 ml-2">
                            {(result.score * 100).toFixed(0)}%
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground leading-relaxed line-clamp-3 ml-6">
                          {result.snippet}
                        </p>
                        <div className="flex items-center gap-2 mt-2 ml-6 flex-wrap">
                          <Badge variant="secondary" className="text-xs">
                            <FileText className="w-3 h-3 mr-1" />
                            Page {result.page_number || "?"}
                          </Badge>
                          {result.year && <Badge variant="secondary" className="text-xs">{result.year}</Badge>}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                  <Separator />
                </div>
              )}

              {/* Paper list */}
              {loading ? (
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Card key={i}><CardContent className="p-4"><Skeleton className="h-5 w-3/4 mb-2" /><Skeleton className="h-4 w-1/2" /></CardContent></Card>
                  ))}
                </div>
              ) : filteredPapers.length === 0 ? (
                <Card className="border-dashed">
                  <CardContent className="flex flex-col items-center justify-center py-16">
                    <FileText className="w-12 h-12 text-muted-foreground mb-4" />
                    <h3 className="text-lg font-medium mb-2">
                      {papers.length === 0 ? "No papers yet" : "No matching papers"}
                    </h3>
                    <p className="text-muted-foreground text-sm mb-6 text-center max-w-md">
                      {papers.length === 0
                        ? "Import papers from academic databases or upload PDFs to start building your research library."
                        : "Try a different search query or clear the search."}
                    </p>
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-3">
                  {filteredPapers.map((paper) => {
                    const statusConfig = STATUS_CONFIG[paper.status] || STATUS_CONFIG.pending;
                    const StatusIcon = statusConfig.icon;
                    return (
                      <Card key={paper.id} className="hover:border-border-hover transition-colors">
                        <CardContent className="p-3 sm:p-4">
                          <div className="flex items-start justify-between gap-2 sm:gap-4">
                            <div className="flex-1 min-w-0">
                              <h3 className="font-medium text-foreground line-clamp-2 mb-1 text-sm sm:text-base">{paper.title}</h3>
                              <p className="text-xs sm:text-sm text-muted-foreground line-clamp-1">
                                {paper.authors?.join(", ") || "Unknown authors"}
                              </p>
                              <div className="flex items-center gap-1.5 sm:gap-2 mt-2 flex-wrap">
                                <Badge variant="outline" className={cn("text-xs", statusConfig.color)}>
                                  <StatusIcon className="w-3 h-3 mr-1" />
                                  {statusConfig.label}
                                </Badge>
                                {statusMessages[paper.id] && (
                                  <span className="text-xs text-blue-500 animate-pulse">{statusMessages[paper.id]}</span>
                                )}
                                {/* Show specific status_reason for pending/failed papers */}
                                {(paper.status === "pending" || paper.status === "failed") && paper.status_reason && !statusMessages[paper.id] && (
                                  <span className={cn(
                                    "text-xs",
                                    paper.status === "pending" ? "text-yellow-500" : "text-destructive"
                                  )}>
                                    {paper.status_reason}
                                  </span>
                                )}
                                {paper.year && <Badge variant="secondary" className="text-xs">{paper.year}</Badge>}
                                {paper.venue && <Badge variant="secondary" className="text-xs hidden sm:inline-flex">{paper.venue.slice(0, 30)}</Badge>}
                                {paper.chunk_count > 0 && <Badge variant="secondary" className="text-xs">{paper.chunk_count} chunks</Badge>}
                                {paper.doi && (
                                  <a href={`https://doi.org/${paper.doi}`} target="_blank" rel="noopener noreferrer"
                                    className="text-xs text-primary hover:underline flex items-center gap-1">
                                    DOI <ExternalLink className="w-3 h-3" />
                                  </a>
                                )}
                              </div>
                            </div>
                            <Button variant="ghost" size="icon" className="shrink-0" onClick={() => deletePaper(paper.id)}>
                              <Trash2 className="w-4 h-4 text-destructive" />
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )}
            </TabsContent>

            {/* ============ DISCOVER TAB ============ */}
            <TabsContent value="discover" className="mt-4 space-y-4">
              <div className="flex gap-2">
                <Input
                  placeholder="Search academic databases (OpenAlex, Crossref, etc.)"
                  value={discoverQuery}
                  onChange={(e) => setDiscoverQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && searchDiscover()}
                />
                <Button onClick={searchDiscover} disabled={discovering}>
                  {discovering ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                </Button>
              </div>

              {discovering ? (
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Card key={i}><CardContent className="p-4"><Skeleton className="h-5 w-3/4 mb-2" /><Skeleton className="h-4 w-1/2" /></CardContent></Card>
                  ))}
                </div>
              ) : discoverResults.length > 0 ? (
                <div className="space-y-3">
                  {discoverResults.map((result, i) => (
                    <Card key={i} className="hover:border-border-hover transition-colors">
                      <CardContent className="p-3 sm:p-4">
                        <div className="flex items-start justify-between gap-2 sm:gap-4">
                          <div className="flex-1 min-w-0">
                            <h3 className="font-medium text-foreground line-clamp-2 mb-1 text-sm sm:text-base">{result.title}</h3>
                            <p className="text-xs sm:text-sm text-muted-foreground line-clamp-1">{result.authors?.join(", ")}</p>
                            {result.abstract && (
                              <p className="text-xs text-muted-foreground mt-2 line-clamp-3">{result.abstract}</p>
                            )}
                            <div className="flex items-center gap-2 mt-2 flex-wrap">
                              {result.year && <Badge variant="secondary" className="text-xs">{result.year}</Badge>}
                              <Badge variant="outline" className="text-xs">{result.source}</Badge>
                            </div>
                          </div>
                          <Button size="sm" onClick={() => importPaper(result)} disabled={importing === (result.doi || result.title)}>
                            {importing === (result.doi || result.title) ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <><Plus className="w-4 h-4 mr-1" />Import</>
                            )}
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : null}
            </TabsContent>

            {/* ============ REFERENCES TAB ============ */}
            <TabsContent value="references" className="mt-4 space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <p className="text-sm text-muted-foreground">
                  Export citations for {papers.length} papers
                </p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={generateBibtex} disabled={generating || papers.length === 0}>
                    {generating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                    Generate BibTeX
                  </Button>
                </div>
              </div>

              {/* Quick cite keys */}
              {papers.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Quick Citations</CardTitle>
                    <CardDescription className="text-xs">Click to copy \\cite{"{key}"} commands</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-1">
                      {papers.map((paper, i) => (
                        <div key={paper.id}>
                          {i > 0 && <Separator className="my-1.5" />}
                          <div className="flex items-center justify-between py-1">
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-foreground truncate">{paper.title}</p>
                              <p className="text-xs text-muted-foreground">
                                {paper.authors?.slice(0, 3).join(", ")}
                                {(paper.authors?.length || 0) > 3 ? " et al." : ""}
                                {paper.year ? ` (${paper.year})` : ""}
                              </p>
                            </div>
                            <div className="flex items-center gap-1 ml-2 shrink-0">
                              <Button
                                variant="ghost" size="sm" className="h-7 text-xs gap-1"
                                onClick={() => copyToClipboard(`\\cite{${citeKey(paper)}}`, paper.id)}
                              >
                                {copied === paper.id ? <Check className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
                                <span className="hidden sm:inline">\cite{`{${citeKey(paper)}}`}</span>
                              </Button>
                              {paper.doi && (
                                <a href={`https://doi.org/${paper.doi}`} target="_blank" rel="noopener noreferrer"
                                  className="text-xs text-primary hover:underline flex items-center gap-0.5">
                                  <ExternalLink className="w-3 h-3" />
                                </a>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* BibTeX / LaTeX output */}
              {bibtex && (
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm">BibTeX Output</CardTitle>
                      <div className="flex gap-1">
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => copyToClipboard(bibtex, "bibtex")}>
                          {copied === "bibtex" ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => downloadFile(bibtex, "references.bib")}>
                          <Download className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <pre className="bg-[#1a1a2e] rounded-lg p-4 text-sm text-green-400 overflow-x-auto max-h-64 font-mono border border-border">
                      {bibtex}
                    </pre>
                  </CardContent>
                </Card>
              )}

              {/* LaTeX preview */}
              {papers.length > 0 && (
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="text-sm">LaTeX Bibliography</CardTitle>
                        <CardDescription className="text-xs">Auto-generated entries</CardDescription>
                      </div>
                      <div className="flex gap-1">
                        <Button variant="ghost" size="icon" className="h-7 w-7"
                          onClick={() => copyToClipboard(papers.map(latexEntry).join("\n\n"), "latex")}>
                          {copied === "latex" ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7"
                          onClick={() => downloadFile(papers.map(latexEntry).join("\n\n"), "references.bib")}>
                          <Download className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <pre className="bg-[#1a1a2e] rounded-lg p-4 text-sm text-amber-400 overflow-x-auto max-h-64 font-mono border border-border">
                      {papers.map(latexEntry).join("\n\n")}
                    </pre>
                  </CardContent>
                </Card>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </div>

      {/* Chat Panel — desktop: side panel with resize handle; mobile: full-width overlay */}
      {showChat && workspaceId && (
        <>
          {/* Mobile: full-width overlay */}
          {isMobile ? (
            <div className="fixed inset-0 z-40 bg-background flex flex-col">
              <ChatPanel
                workspaceId={workspaceId}
                papers={papers}
                onClose={() => setShowChat(false)}
              />
            </div>
          ) : (
            <>
              {/* Drag handle */}
              <div
                onPointerDown={handleDragStart}
                className={cn(
                  "w-1.5 shrink-0 cursor-col-resize group relative z-10",
                  "hover:bg-primary/20 active:bg-primary/30 transition-colors",
                  isDragging && "bg-primary/30"
                )}
              >
                <div className="absolute inset-y-0 -left-1 -right-1" />
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <GripVertical className="w-3 h-3 text-muted-foreground" />
                </div>
              </div>

              {/* Chat panel with dynamic width */}
              <div
                className="shrink-0 h-full overflow-hidden"
                style={{ width: `${chatWidth}px` }}
              >
                <ChatPanel
                  workspaceId={workspaceId}
                  papers={papers}
                  onClose={() => setShowChat(false)}
                />
              </div>
            </>
          )}
        </>
      )}

      {/* Upload Dialog */}
      <Dialog open={showUpload} onOpenChange={setShowUpload}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Upload PDF</DialogTitle>
            <DialogDescription>Upload a research paper PDF for processing</DialogDescription>
          </DialogHeader>
          <form onSubmit={uploadPdf} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="pdf-file">PDF File</Label>
              <Input id="pdf-file" name="file" type="file" accept=".pdf" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pdf-title">Title (optional)</Label>
              <Input id="pdf-title" name="title" placeholder="Paper title" />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowUpload(false)}>Cancel</Button>
              <Button type="submit" disabled={uploading}>
                {uploading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                Upload
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Batch Import Dialog */}
      <Dialog open={showBatchImport} onOpenChange={setShowBatchImport}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Batch Import by DOI</DialogTitle>
            <DialogDescription>Enter one DOI per line</DialogDescription>
          </DialogHeader>
          <Textarea
            value={batchDois}
            onChange={(e) => setBatchDois(e.target.value)}
            placeholder={"10.1234/example.2024.001\n10.5678/another.paper.002"}
            rows={6}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowBatchImport(false)}>Cancel</Button>
            <Button onClick={batchImport} disabled={batchImporting || !batchDois.trim()}>
              {batchImporting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Import All
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
