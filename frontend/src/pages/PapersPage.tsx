import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import api from "@/lib/api";
import type { Paper, PaperMetadata } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

const STATUS_CONFIG: Record<string, { icon: React.ElementType; color: string; label: string }> = {
  pending: { icon: Clock, color: "text-yellow-500", label: "Pending" },
  processing: { icon: RefreshCw, color: "text-blue-400", label: "Processing" },
  indexed: { icon: CheckCircle2, color: "text-primary", label: "Indexed" },
  failed: { icon: AlertCircle, color: "text-destructive", label: "Failed" },
};

export function PapersPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const [papers, setPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<PaperMetadata[]>([]);
  const [searching, setSearching] = useState(false);
  const [importing, setImporting] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [showBatchImport, setShowBatchImport] = useState(false);
  const [batchDois, setBatchDois] = useState("");
  const [batchImporting, setBatchImporting] = useState(false);

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

  const searchPapers = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const res = await api.get(
        `/papers/search/external?query=${encodeURIComponent(searchQuery)}&source=openalex&limit=10`
      );
      setSearchResults(res.data);
    } catch {
      toast.error("Search failed");
    } finally {
      setSearching(false);
    }
  };

  const importPaper = async (metadata: PaperMetadata) => {
    if (!workspaceId) return;
    setImporting(metadata.doi || metadata.title);
    try {
      const res = await api.post("/papers/import", {
        metadata,
        workspace_id: workspaceId,
      });
      setPapers((prev) => [res.data, ...prev]);
      setSearchResults((prev) => prev.filter((p) => p.doi !== metadata.doi));
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
    const dois = batchDois
      .split("\n")
      .map((d) => d.trim())
      .filter(Boolean);
    if (dois.length === 0) return;

    setBatchImporting(true);
    try {
      const res = await api.post("/papers/batch-import", {
        dois,
        workspace_id: workspaceId,
      });
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

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Papers</h1>
          <p className="text-muted-foreground text-sm mt-1">
            {papers.length} papers in this workspace
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowBatchImport(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Batch Import
          </Button>
          <Button variant="outline" onClick={() => setShowUpload(true)}>
            <Upload className="w-4 h-4 mr-2" />
            Upload PDF
          </Button>
        </div>
      </div>

      <Tabs defaultValue="library">
        <TabsList>
          <TabsTrigger value="library">Library ({papers.length})</TabsTrigger>
          <TabsTrigger value="discover">Discover</TabsTrigger>
        </TabsList>

        {/* Library Tab */}
        <TabsContent value="library" className="mt-4">
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Card key={i}>
                  <CardContent className="p-4">
                    <Skeleton className="h-5 w-3/4 mb-2" />
                    <Skeleton className="h-4 w-1/2 mb-3" />
                    <div className="flex gap-2">
                      <Skeleton className="h-6 w-20" />
                      <Skeleton className="h-6 w-16" />
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : papers.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="flex flex-col items-center justify-center py-16">
                <FileText className="w-12 h-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-medium mb-2">No papers yet</h3>
                <p className="text-muted-foreground text-sm mb-6 text-center max-w-md">
                  Import papers from academic databases or upload PDFs to start building your research library.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {papers.map((paper) => {
                const statusConfig = STATUS_CONFIG[paper.status] || STATUS_CONFIG.pending;
                const StatusIcon = statusConfig.icon;
                return (
                  <Card key={paper.id} className="hover:border-border-hover transition-colors">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <h3 className="font-medium text-foreground line-clamp-2 mb-1">
                            {paper.title}
                          </h3>
                          <p className="text-sm text-muted-foreground line-clamp-1">
                            {paper.authors?.join(", ") || "Unknown authors"}
                          </p>
                          <div className="flex items-center gap-2 mt-2 flex-wrap">
                            <Badge
                              variant="outline"
                              className={cn("text-xs", statusConfig.color)}
                            >
                              <StatusIcon className="w-3 h-3 mr-1" />
                              {statusConfig.label}
                            </Badge>
                            {paper.year && (
                              <Badge variant="secondary" className="text-xs">
                                {paper.year}
                              </Badge>
                            )}
                            {paper.venue && (
                              <Badge variant="secondary" className="text-xs">
                                {paper.venue.slice(0, 30)}
                              </Badge>
                            )}
                            {paper.chunk_count > 0 && (
                              <Badge variant="secondary" className="text-xs">
                                {paper.chunk_count} chunks
                              </Badge>
                            )}
                            {paper.doi && (
                              <a
                                href={`https://doi.org/${paper.doi}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-primary hover:underline flex items-center gap-1"
                              >
                                DOI <ExternalLink className="w-3 h-3" />
                              </a>
                            )}
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="shrink-0"
                          onClick={() => deletePaper(paper.id)}
                        >
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

        {/* Discover Tab */}
        <TabsContent value="discover" className="mt-4 space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="Search academic databases (OpenAlex, Crossref, etc.)"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && searchPapers()}
            />
            <Button onClick={searchPapers} disabled={searching}>
              {searching ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Search className="w-4 h-4" />
              )}
            </Button>
          </div>

          {searching ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Card key={i}>
                  <CardContent className="p-4">
                    <Skeleton className="h-5 w-3/4 mb-2" />
                    <Skeleton className="h-4 w-1/2" />
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : searchResults.length > 0 ? (
            <div className="space-y-3">
              {searchResults.map((result, i) => (
                <Card key={i} className="hover:border-border-hover transition-colors">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium text-foreground line-clamp-2 mb-1">
                          {result.title}
                        </h3>
                        <p className="text-sm text-muted-foreground line-clamp-1">
                          {result.authors?.join(", ")}
                        </p>
                        {result.abstract && (
                          <p className="text-xs text-muted-foreground mt-2 line-clamp-3">
                            {result.abstract}
                          </p>
                        )}
                        <div className="flex items-center gap-2 mt-2">
                          {result.year && (
                            <Badge variant="secondary" className="text-xs">
                              {result.year}
                            </Badge>
                          )}
                          <Badge variant="outline" className="text-xs">
                            {result.source}
                          </Badge>
                        </div>
                      </div>
                      <Button
                        size="sm"
                        onClick={() => importPaper(result)}
                        disabled={importing === (result.doi || result.title)}
                      >
                        {importing === (result.doi || result.title) ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <>
                            <Plus className="w-4 h-4 mr-1" />
                            Import
                          </>
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : null}
        </TabsContent>
      </Tabs>

      {/* Upload Dialog */}
      <Dialog open={showUpload} onOpenChange={setShowUpload}>
        <DialogContent>
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
              <Button type="button" variant="outline" onClick={() => setShowUpload(false)}>
                Cancel
              </Button>
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
        <DialogContent>
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
            <Button variant="outline" onClick={() => setShowBatchImport(false)}>
              Cancel
            </Button>
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
