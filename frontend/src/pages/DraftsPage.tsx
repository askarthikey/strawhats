import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import api from "@/lib/api";
import type { Draft } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  PenTool,
  Plus,
  Loader2,
  Trash2,
  Save,
  History,
  ArrowLeft,
  FileText,
} from "lucide-react";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function DraftsPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDraft, setSelectedDraft] = useState<Draft | null>(null);
  const [editContent, setEditContent] = useState("");
  const [editTitle, setEditTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [previewMode, setPreviewMode] = useState(false);

  const loadDrafts = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const res = await api.get(`/drafts/?workspace_id=${workspaceId}`);
      setDrafts(res.data);
    } catch {
      toast.error("Failed to load drafts");
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    loadDrafts();
  }, [loadDrafts]);

  const createDraft = async () => {
    if (!workspaceId || !newTitle.trim()) return;
    setCreating(true);
    try {
      const res = await api.post("/drafts/", {
        title: newTitle.trim(),
        content: "",
        workspace_id: workspaceId,
      });
      setDrafts((prev) => [res.data, ...prev]);
      setShowCreate(false);
      setNewTitle("");
      setSelectedDraft(res.data);
      setEditContent("");
      setEditTitle(res.data.title);
      toast.success("Draft created");
    } catch {
      toast.error("Failed to create draft");
    } finally {
      setCreating(false);
    }
  };

  const saveDraft = async () => {
    if (!selectedDraft) return;
    setSaving(true);
    try {
      const res = await api.put(`/drafts/${selectedDraft.id}`, {
        title: editTitle,
        content: editContent,
      });
      setSelectedDraft(res.data);
      setDrafts((prev) =>
        prev.map((d) => (d.id === selectedDraft.id ? res.data : d))
      );
      toast.success("Draft saved");
    } catch {
      toast.error("Failed to save draft");
    } finally {
      setSaving(false);
    }
  };

  const deleteDraft = async (id: string) => {
    if (!confirm("Delete this draft?")) return;
    try {
      await api.delete(`/drafts/${id}`);
      setDrafts((prev) => prev.filter((d) => d.id !== id));
      if (selectedDraft?.id === id) {
        setSelectedDraft(null);
      }
      toast.success("Draft deleted");
    } catch {
      toast.error("Failed to delete draft");
    }
  };

  const openDraft = (draft: Draft) => {
    setSelectedDraft(draft);
    setEditContent(draft.content);
    setEditTitle(draft.title);
    setPreviewMode(false);
  };

  // Draft editor view
  if (selectedDraft) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center justify-between px-6 py-3 border-b border-border">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => setSelectedDraft(null)}>
              <ArrowLeft className="w-4 h-4 mr-1" />
              Back
            </Button>
            <Input
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              className="font-semibold border-none bg-transparent text-lg px-0 focus-visible:ring-0 w-auto"
            />
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              v{selectedDraft.version}
            </Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPreviewMode(!previewMode)}
            >
              {previewMode ? "Edit" : "Preview"}
            </Button>
            <Button size="sm" onClick={saveDraft} disabled={saving}>
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin mr-1" />
              ) : (
                <Save className="w-4 h-4 mr-1" />
              )}
              Save
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {previewMode ? (
            <div className="max-w-3xl mx-auto p-8">
              <div className="markdown-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {editContent || "*Empty draft*"}
                </ReactMarkdown>
              </div>
            </div>
          ) : (
            <Textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              placeholder="Start writing your draft in Markdown..."
              className="w-full h-full border-none rounded-none resize-none focus-visible:ring-0 p-8 text-sm leading-relaxed font-mono"
            />
          )}
        </div>
      </div>
    );
  }

  // Drafts list view
  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Drafts</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Write and collaborate on research documents
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="w-4 h-4 mr-2" />
          New Draft
        </Button>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-4">
                <Skeleton className="h-5 w-48 mb-2" />
                <Skeleton className="h-4 w-32" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : drafts.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <PenTool className="w-12 h-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">No drafts yet</h3>
            <p className="text-muted-foreground text-sm mb-6 text-center">
              Create a draft to start writing your research paper.
            </p>
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="w-4 h-4 mr-2" />
              New Draft
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {drafts.map((draft) => (
            <Card
              key={draft.id}
              className="cursor-pointer hover:border-border-hover transition-colors group"
              onClick={() => openDraft(draft)}
            >
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <FileText className="w-5 h-5 text-muted-foreground" />
                    <div>
                      <h3 className="font-medium text-foreground">{draft.title}</h3>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        v{draft.version} · Updated{" "}
                        {new Date(draft.updated_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteDraft(draft.id);
                      }}
                    >
                      <Trash2 className="w-4 h-4 text-destructive" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Draft</DialogTitle>
            <DialogDescription>Start a new research document</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>Title</Label>
              <Input
                placeholder="e.g., Literature Review Section 3"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>
              Cancel
            </Button>
            <Button onClick={createDraft} disabled={creating || !newTitle.trim()}>
              {creating && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
