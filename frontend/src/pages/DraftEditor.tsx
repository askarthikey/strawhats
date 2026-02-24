import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
    ArrowLeft,
    Bold,
    Italic,
    Heading1,
    Heading2,
    Heading3,
    List,
    ListOrdered,
    Code,
    Quote,
    Table,
    Minus,
    Link,
    Image,
    Sparkles,
    Cloud,
    CloudOff,
    Users,
    Loader2,
    Wand2,
    CheckCircle,
    Eye,
    EyeOff,
    FileText,
    Play,
    Download,
    AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";
import "katex/dist/katex.min.css";

type EditorMode = "markdown" | "latex";

const DEFAULT_LATEX_TEMPLATE = `\\documentclass{article}
\\usepackage{amsmath, amssymb, booktabs, graphicx, hyperref}
\\usepackage[margin=1in]{geometry}

\\title{Your Paper Title}
\\author{Author Name}
\\date{\\today}

\\begin{document}
\\maketitle

\\section{Introduction}
Your content here...

\\end{document}
`;

interface ActiveUser {
    user_id: string;
    full_name: string;
    color: string;
    cursor?: { line: number; ch: number } | null;
}

interface CursorOverlay {
    user_id: string;
    full_name: string;
    color: string;
    position: { line: number; ch: number };
}

export function DraftEditor() {
    const { workspaceId, draftId } = useParams<{
        workspaceId: string;
        draftId: string;
    }>();
    const { user } = useAuth();
    const navigate = useNavigate();

    const [title, setTitle] = useState("");
    const [content, setContent] = useState("");
    const [contentLatex, setContentLatex] = useState("");
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(true);
    const [connected, setConnected] = useState(false);
    const [activeUsers, setActiveUsers] = useState<ActiveUser[]>([]);
    const [remoteCursors, setRemoteCursors] = useState<CursorOverlay[]>([]);
    const [loading, setLoading] = useState(true);
    const [aiSuggesting, setAiSuggesting] = useState(false);
    const [aiSuggestion, setAiSuggestion] = useState("");
    const [showPreview, setShowPreview] = useState(false);
    const [ghostText, setGhostText] = useState("");
    const [ghostCursorPos, setGhostCursorPos] = useState(0);
    const [editorMode, setEditorMode] = useState<EditorMode>("markdown");
    const [compiling, setCompiling] = useState(false);
    const [pdfUrl, setPdfUrl] = useState<string | null>(null);
    const [compileErrors, setCompileErrors] = useState<string[]>([]);

    const wsRef = useRef<WebSocket | null>(null);
    const editorRef = useRef<HTMLTextAreaElement | null>(null);
    const saveTimerRef = useRef<NodeJS.Timeout | null>(null);
    const isRemoteUpdate = useRef(false);
    const ghostTimerRef = useRef<NodeJS.Timeout | null>(null);
    const abortRef = useRef<AbortController | null>(null);

    // Load draft initially
    useEffect(() => {
        if (!draftId) return;

        const loadDraft = async () => {
            try {
                const res = await api.get(`/drafts/${draftId}`);
                setTitle(res.data.title || "");
                setContent(res.data.content_markdown || "");
                if (res.data.content_latex) {
                    setContentLatex(res.data.content_latex);
                }
            } catch {
                toast.error("Failed to load draft");
            } finally {
                setLoading(false);
            }
        };
        loadDraft();
    }, [draftId]);

    // WebSocket connection
    useEffect(() => {
        if (!draftId) return;

        const token = localStorage.getItem("token") || "";
        const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/drafts/${draftId}?token=${token}`;
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
            setConnected(true);
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                switch (data.type) {
                    case "init":
                        setActiveUsers(data.active_users || []);
                        break;

                    case "document":
                        if (data.content !== undefined) {
                            isRemoteUpdate.current = true;
                            setContent(data.content);
                            if (data.content_latex) setContentLatex(data.content_latex);
                            if (data.title) setTitle(data.title);
                            setTimeout(() => {
                                isRemoteUpdate.current = false;
                            }, 50);
                        }
                        break;

                    case "operation":
                        if (data.user_id !== user?.id) {
                            isRemoteUpdate.current = true;
                            if (data.content_type === "latex") {
                                setContentLatex(data.content);
                            } else {
                                setContent(data.content);
                            }
                            setTimeout(() => {
                                isRemoteUpdate.current = false;
                            }, 50);
                        }
                        break;

                    case "cursor":
                        if (data.user_id !== user?.id) {
                            setRemoteCursors((prev) => {
                                const filtered = prev.filter(
                                    (c) => c.user_id !== data.user_id
                                );
                                if (data.position) {
                                    filtered.push({
                                        user_id: data.user_id,
                                        full_name: data.full_name,
                                        color: data.color,
                                        position: data.position,
                                    });
                                }
                                return filtered;
                            });
                        }
                        break;

                    case "user_join":
                        setActiveUsers(data.active_users || []);
                        toast.info(`${data.user?.full_name || "Someone"} joined`);
                        break;

                    case "user_leave":
                        setActiveUsers(data.active_users || []);
                        setRemoteCursors((prev) =>
                            prev.filter((c) => c.user_id !== data.user?.user_id)
                        );
                        break;

                    case "title_update":
                        if (data.user_id !== user?.id) {
                            setTitle(data.title);
                        }
                        break;

                    case "saved":
                        setSaved(true);
                        setSaving(false);
                        break;
                }
            } catch {
                // Ignore parse errors
            }
        };

        ws.onclose = () => {
            setConnected(false);
        };

        ws.onerror = () => {
            setConnected(false);
        };

        return () => {
            ws.close();
        };
    }, [draftId, user?.id]);

    // Cleanup ghost timers on unmount
    useEffect(() => {
        return () => {
            if (ghostTimerRef.current) clearTimeout(ghostTimerRef.current);
            if (abortRef.current) abortRef.current.abort();
        };
    }, []);

    const sendOperation = useCallback(
        (newContent: string) => {
            if (
                wsRef.current?.readyState === WebSocket.OPEN &&
                !isRemoteUpdate.current
            ) {
                wsRef.current.send(
                    JSON.stringify({
                        type: "operation",
                        content: newContent,
                        content_type: editorMode,
                        version: Date.now(),
                    })
                );
                setSaved(false);
                setSaving(true);

                // Mark as saved after debounce
                if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
                saveTimerRef.current = setTimeout(() => {
                    setSaving(false);
                    setSaved(true);
                }, 2500);
            }
        },
        [editorMode]
    );

    // --- Inline AI ghost text ---
    const fetchGhostSuggestion = useCallback(async (text: string, cursorPos: number) => {
        // Cancel any in-flight request
        if (abortRef.current) abortRef.current.abort();
        const controller = new AbortController();
        abortRef.current = controller;

        const contextBefore = text.substring(Math.max(0, cursorPos - 600), cursorPos);
        const contextAfter = text.substring(cursorPos, Math.min(text.length, cursorPos + 200));

        // Need at least some text before suggesting
        if (contextBefore.trim().length < 20) return;

        try {
            const token = localStorage.getItem("token") || "";
            const res = await fetch("/api/drafts/ai/inline-suggest", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`,
                },
                body: JSON.stringify({
                    context_before: contextBefore,
                    context_after: contextAfter,
                    full_title: title,
                }),
                signal: controller.signal,
            });

            if (!res.ok || !res.body) return;

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let suggestion = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                suggestion += decoder.decode(value, { stream: true });
                // Update ghost text in real time as tokens stream in
                setGhostText(suggestion);
                setGhostCursorPos(cursorPos);
            }
        } catch {
            // AbortError or network error — silently ignore
        }
    }, [title]);

    const acceptGhostText = useCallback(() => {
        if (!ghostText || !editorRef.current) return;
        const activeContent = editorMode === "latex" ? contentLatex : content;
        const before = activeContent.substring(0, ghostCursorPos);
        const after = activeContent.substring(ghostCursorPos);
        const newContent = before + ghostText + after;
        if (editorMode === "latex") {
            setContentLatex(newContent);
        } else {
            setContent(newContent);
        }
        sendOperation(newContent);
        setGhostText("");

        // Move cursor to end of inserted suggestion
        setTimeout(() => {
            const newPos = ghostCursorPos + ghostText.length;
            editorRef.current?.setSelectionRange(newPos, newPos);
            editorRef.current?.focus();
        }, 10);
    }, [ghostText, ghostCursorPos, content, contentLatex, editorMode, sendOperation]);

    const dismissGhostText = useCallback(() => {
        if (abortRef.current) abortRef.current.abort();
        if (ghostTimerRef.current) clearTimeout(ghostTimerRef.current);
        setGhostText("");
    }, []);

    // Handle content change
    const handleContentChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        const newContent = e.target.value;
        if (editorMode === "latex") {
            setContentLatex(newContent);
        } else {
            setContent(newContent);
        }
        sendOperation(newContent);

        // Dismiss current ghost text on any edit
        dismissGhostText();

        // Schedule new ghost text suggestion after 1.5s pause
        const cursorPos = e.target.selectionStart;
        ghostTimerRef.current = setTimeout(() => {
            fetchGhostSuggestion(newContent, cursorPos);
        }, 1500);
    };

    // Handle title change
    const handleTitleChange = (newTitle: string) => {
        setTitle(newTitle);
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(
                JSON.stringify({ type: "title_update", title: newTitle })
            );
        }
    };

    // Send cursor position
    const handleCursorChange = () => {
        const editor = editorRef.current;
        if (!editor || wsRef.current?.readyState !== WebSocket.OPEN) return;

        const activeContent = editorMode === "latex" ? contentLatex : content;
        const pos = editor.selectionStart;
        const lines = activeContent.substring(0, pos).split("\n");
        const line = lines.length - 1;
        const ch = lines[lines.length - 1].length;

        wsRef.current.send(
            JSON.stringify({
                type: "cursor",
                position: { line, ch },
                selection: editor.selectionStart !== editor.selectionEnd
                    ? {
                        start: editor.selectionStart,
                        end: editor.selectionEnd,
                    }
                    : null,
            })
        );
    };

    // Insert text at cursor
    const insertAtCursor = (before: string, after: string = "") => {
        const editor = editorRef.current;
        if (!editor) return;

        const activeContent = editorMode === "latex" ? contentLatex : content;
        const start = editor.selectionStart;
        const end = editor.selectionEnd;
        const selected = activeContent.substring(start, end);
        const newContent =
            activeContent.substring(0, start) +
            before +
            selected +
            after +
            activeContent.substring(end);

        if (editorMode === "latex") {
            setContentLatex(newContent);
        } else {
            setContent(newContent);
        }
        sendOperation(newContent);

        // Set cursor after inserted text
        setTimeout(() => {
            editor.focus();
            const newPos = start + before.length + selected.length;
            editor.setSelectionRange(newPos, newPos);
        }, 10);
    };

    // --- LaTeX Compilation ---
    const compileLatex = async () => {
        if (!contentLatex.trim()) {
            toast.info("Write some LaTeX content first");
            return;
        }
        setCompiling(true);
        setCompileErrors([]);
        setPdfUrl(null);

        try {
            const res = await api.post("/latex/compile", { source: contentLatex });
            if (res.data.success) {
                // Convert base64 to blob URL
                const binaryStr = atob(res.data.pdf_base64);
                const bytes = new Uint8Array(binaryStr.length);
                for (let i = 0; i < binaryStr.length; i++) {
                    bytes[i] = binaryStr.charCodeAt(i);
                }
                const blob = new Blob([bytes], { type: "application/pdf" });
                const url = URL.createObjectURL(blob);
                setPdfUrl(url);
                setShowPreview(true);
                toast.success("Compilation successful!");
            } else {
                setCompileErrors(res.data.errors || ["Unknown compilation error"]);
                toast.error("Compilation failed");
            }
        } catch (err: any) {
            toast.error("Compilation request failed");
            setCompileErrors([err?.response?.data?.detail || err.message || "Network error"]);
        } finally {
            setCompiling(false);
        }
    };

    const downloadPdf = () => {
        if (!pdfUrl) return;
        const a = document.createElement("a");
        a.href = pdfUrl;
        a.download = `${title || "document"}.pdf`;
        a.click();
    };

    // Cleanup PDF blob URL on unmount
    useEffect(() => {
        return () => {
            if (pdfUrl) URL.revokeObjectURL(pdfUrl);
        };
    }, [pdfUrl]);

    // AI suggestion
    const requestAiSuggestion = async () => {
        if (!content.trim()) {
            toast.info("Write some content first, then ask AI for suggestions");
            return;
        }
        setAiSuggesting(true);
        setAiSuggestion("");
        try {
            const res = await api.post("/drafts/ai/suggest", {
                context: content.substring(
                    Math.max(0, content.length - 500),
                    content.length
                ),
                workspace_id: workspaceId,
            });
            setAiSuggestion(res.data.suggestion || "No suggestion available.");
        } catch {
            toast.error("AI suggestion failed. Make sure Ollama is running.");
        } finally {
            setAiSuggesting(false);
        }
    };

    const acceptSuggestion = () => {
        if (aiSuggestion) {
            if (editorMode === "latex") {
                const newContent = contentLatex + "\n" + aiSuggestion;
                setContentLatex(newContent);
                sendOperation(newContent);
            } else {
                const newContent = content + "\n" + aiSuggestion;
                setContent(newContent);
                sendOperation(newContent);
            }
            setAiSuggestion("");
            toast.success("Suggestion added!");
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full">
            {/* Top Bar */}
            <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-card/50">
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => navigate(`/workspace/${workspaceId}/drafts`)}
                >
                    <ArrowLeft className="w-4 h-4" />
                </Button>

                <Input
                    value={title}
                    onChange={(e) => handleTitleChange(e.target.value)}
                    placeholder="Untitled Draft"
                    className="flex-1 border-none bg-transparent text-lg font-semibold focus-visible:ring-0 px-2 h-9"
                />

                {/* Status indicators */}
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    {saving && (
                        <span className="flex items-center gap-1">
                            <Loader2 className="w-3 h-3 animate-spin" /> Saving...
                        </span>
                    )}
                    {saved && !saving && (
                        <span className="flex items-center gap-1 text-green-500">
                            <CheckCircle className="w-3 h-3" /> Saved
                        </span>
                    )}
                    {connected ? (
                        <span className="flex items-center gap-1 text-green-500">
                            <Cloud className="w-3 h-3" /> Live
                        </span>
                    ) : (
                        <span className="flex items-center gap-1 text-destructive">
                            <CloudOff className="w-3 h-3" /> Offline
                        </span>
                    )}
                </div>

                {/* Active users */}
                {activeUsers.length > 0 && (
                    <div className="flex items-center gap-1">
                        <Users className="w-3.5 h-3.5 text-muted-foreground" />
                        <div className="flex -space-x-2">
                            {activeUsers.map((u) => (
                                <div
                                    key={u.user_id}
                                    className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white border-2 border-background"
                                    style={{ backgroundColor: u.color }}
                                    title={u.full_name}
                                >
                                    {u.full_name?.charAt(0)?.toUpperCase() || "?"}
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {/* Formatting Toolbar */}
            <div className="flex items-center gap-0.5 px-4 py-1.5 border-b border-border bg-card/30 overflow-x-auto">
                {/* Mode Toggle */}
                <div className="flex items-center bg-muted rounded-md p-0.5 mr-2">
                    <button
                        className={`px-2 py-1 text-xs rounded-sm transition-colors ${editorMode === "markdown" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
                        onClick={() => setEditorMode("markdown")}
                    >
                        Markdown
                    </button>
                    <button
                        className={`px-2 py-1 text-xs rounded-sm transition-colors ${editorMode === "latex" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
                        onClick={() => {
                            setEditorMode("latex");
                            if (!contentLatex.trim()) {
                                setContentLatex(DEFAULT_LATEX_TEMPLATE);
                            }
                        }}
                    >
                        LaTeX
                    </button>
                </div>

                <div className="w-px h-5 bg-border mx-1" />

                {editorMode === "markdown" ? (
                    <>
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => insertAtCursor("**", "**")} title="Bold">
                            <Bold className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => insertAtCursor("*", "*")} title="Italic">
                            <Italic className="w-3.5 h-3.5" />
                        </Button>
                        <div className="w-px h-5 bg-border mx-1" />
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => insertAtCursor("# ")} title="H1">
                            <Heading1 className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => insertAtCursor("## ")} title="H2">
                            <Heading2 className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => insertAtCursor("### ")} title="H3">
                            <Heading3 className="w-3.5 h-3.5" />
                        </Button>
                        <div className="w-px h-5 bg-border mx-1" />
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => insertAtCursor("- ")} title="Bullet List">
                            <List className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => insertAtCursor("1. ")} title="Numbered List">
                            <ListOrdered className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => insertAtCursor("`", "`")} title="Inline Code">
                            <Code className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => insertAtCursor("> ")} title="Blockquote">
                            <Quote className="w-3.5 h-3.5" />
                        </Button>
                        <div className="w-px h-5 bg-border mx-1" />
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => insertAtCursor("$$\n", "\n$$")} title="LaTeX Block">
                            <span className="text-xs font-mono">∑</span>
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => insertAtCursor("$", "$")} title="Inline LaTeX">
                            <span className="text-xs font-mono italic">x²</span>
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => insertAtCursor("---\n")} title="Divider">
                            <Minus className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => insertAtCursor("[", "](url)")} title="Link">
                            <Link className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => insertAtCursor("| Col 1 | Col 2 | Col 3 |\n|-------|-------|-------|\n| Cell  | Cell  | Cell  |\n")} title="Table">
                            <Table className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => insertAtCursor("```\n", "\n```")} title="Code Block">
                            <span className="text-xs font-mono">{"{}"}</span>
                        </Button>
                    </>
                ) : (
                    <>
                        {/* LaTeX-specific toolbar */}
                        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => insertAtCursor("\\textbf{", "}")} title="Bold">
                            <Bold className="w-3.5 h-3.5 mr-1" /> bf
                        </Button>
                        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => insertAtCursor("\\textit{", "}")} title="Italic">
                            <Italic className="w-3.5 h-3.5 mr-1" /> it
                        </Button>
                        <div className="w-px h-5 bg-border mx-1" />
                        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => insertAtCursor("\\section{", "}")} title="Section">
                            §1
                        </Button>
                        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => insertAtCursor("\\subsection{", "}")} title="Subsection">
                            §2
                        </Button>
                        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => insertAtCursor("\\subsubsection{", "}")} title="Subsubsection">
                            §3
                        </Button>
                        <div className="w-px h-5 bg-border mx-1" />
                        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => insertAtCursor("\\begin{equation}\n", "\n\\end{equation}")} title="Equation">
                            <span className="font-mono">∑</span>
                        </Button>
                        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => insertAtCursor("\\begin{itemize}\n  \\item ", "\n\\end{itemize}")} title="Itemize">
                            <List className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => insertAtCursor("\\begin{enumerate}\n  \\item ", "\n\\end{enumerate}")} title="Enumerate">
                            <ListOrdered className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => insertAtCursor("\\begin{figure}[h]\n  \\centering\n  \\includegraphics[width=0.8\\textwidth]{", "}\n  \\caption{Caption}\n  \\label{fig:label}\n\\end{figure}")} title="Figure">
                            <Image className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => insertAtCursor("\\begin{table}[h]\n  \\centering\n  \\begin{tabular}{lcc}\n    \\toprule\n    Col 1 & Col 2 & Col 3 \\\\\\\\\n    \\midrule\n    A & B & C \\\\\\\\\n    \\bottomrule\n  \\end{tabular}\n  \\caption{Caption}\n  \\label{tab:label}\n\\end{table}\n")} title="Table">
                            <Table className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => insertAtCursor("\\cite{", "}")} title="Citation">
                            <FileText className="w-3.5 h-3.5" />
                        </Button>
                        <div className="w-px h-5 bg-border mx-1" />
                        <Button
                            variant="default"
                            size="sm"
                            className="h-7 gap-1.5 text-xs"
                            onClick={compileLatex}
                            disabled={compiling}
                        >
                            {compiling ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                            Compile
                        </Button>
                        {pdfUrl && (
                            <Button variant="outline" size="sm" className="h-7 gap-1 text-xs" onClick={downloadPdf}>
                                <Download className="w-3 h-3" /> PDF
                            </Button>
                        )}
                    </>
                )}

                <div className="flex-1" />

                {/* AI Button */}
                <Button
                    variant="outline"
                    size="sm"
                    className="h-7 gap-1.5 text-xs"
                    onClick={requestAiSuggestion}
                    disabled={aiSuggesting}
                >
                    {aiSuggesting ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                        <Sparkles className="w-3 h-3" />
                    )}
                    AI Suggest
                </Button>

                {/* Preview Toggle */}
                <Button
                    variant={showPreview ? "secondary" : "outline"}
                    size="sm"
                    className="h-7 gap-1.5 text-xs"
                    onClick={() => setShowPreview(!showPreview)}
                >
                    {showPreview ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                    Preview
                </Button>
            </div>

            {/* Editor Area */}
            <div className="flex-1 flex overflow-hidden">
                {/* Main Editor */}
                <div className="flex-1 relative">
                    <textarea
                        ref={editorRef}
                        value={editorMode === "latex" ? contentLatex : content}
                        onChange={handleContentChange}
                        onClick={handleCursorChange}
                        onKeyUp={handleCursorChange}
                        onSelect={handleCursorChange}
                        onKeyDown={(e) => {
                            if (e.key === "Tab" && ghostText) {
                                e.preventDefault();
                                acceptGhostText();
                            } else if (e.key === "Escape" && ghostText) {
                                e.preventDefault();
                                dismissGhostText();
                            }
                        }}
                        className="w-full h-full resize-none bg-transparent text-foreground px-8 py-6 text-sm font-mono leading-relaxed focus:outline-none relative z-10 caret-foreground"
                        placeholder={editorMode === "markdown"
                            ? `Start writing your research paper...

Supports Markdown formatting:
  # Headings
  **Bold**, *Italic*
  - Bullet lists
  > Block quotes
  \`inline code\` and code blocks

LaTeX math:
  Inline: $E = mc^2$
  Block: $$\\sum_{i=1}^{n} x_i$$`
                            : `\\documentclass{article}
\\usepackage{amsmath, amssymb, booktabs, graphicx}

\\title{Your Paper Title}
\\author{Author Name}
\\date{\\today}

\\begin{document}
\\maketitle

\\section{Introduction}
Your content here...

\\end{document}`
                        }
                        spellCheck
                    />

                    {/* Ghost text overlay */}
                    {ghostText && ghostCursorPos === editorRef.current?.selectionStart && (
                        <div
                            className="absolute inset-0 pointer-events-none px-8 py-6 z-0 overflow-hidden"
                            aria-hidden="true"
                        >
                            <pre className="text-sm font-mono leading-relaxed whitespace-pre-wrap break-words m-0">
                                <span className="invisible">{(editorMode === "latex" ? contentLatex : content).substring(0, ghostCursorPos)}</span>
                                <span className="text-muted-foreground/50 italic">{ghostText}</span>
                            </pre>
                        </div>
                    )}

                    {/* Ghost text hint */}
                    {ghostText && (
                        <div className="absolute bottom-2 right-2 z-20 text-[10px] text-muted-foreground bg-card/80 backdrop-blur-sm px-2 py-1 rounded border border-border">
                            Tab to accept · Esc to dismiss
                        </div>
                    )}

                    {/* Remote cursor overlays */}
                    {remoteCursors.map((cursor) => (
                        <div
                            key={cursor.user_id}
                            className="absolute pointer-events-none z-10"
                            style={{
                                top: `${24 + cursor.position.line * 21}px`,
                                left: `${32 + cursor.position.ch * 8.4}px`,
                            }}
                        >
                            <div
                                className="w-0.5 h-5 animate-pulse"
                                style={{ backgroundColor: cursor.color }}
                            />
                            <div
                                className="absolute -top-5 left-0 px-1.5 py-0.5 rounded text-[10px] font-medium text-white whitespace-nowrap"
                                style={{ backgroundColor: cursor.color }}
                            >
                                {cursor.full_name}
                            </div>
                        </div>
                    ))}
                </div>

                {/* Preview Pane — Markdown or PDF */}
                {showPreview && (
                    <div className="flex-1 border-l border-border overflow-y-auto bg-background">
                        {editorMode === "markdown" ? (
                            <div className="px-8 py-6 prose prose-sm dark:prose-invert max-w-none">
                                {content.trim() ? (
                                    <ReactMarkdown
                                        remarkPlugins={[remarkGfm, remarkMath]}
                                        rehypePlugins={[rehypeKatex, rehypeHighlight]}
                                    >
                                        {content}
                                    </ReactMarkdown>
                                ) : (
                                    <p className="text-muted-foreground italic">Start writing to see preview...</p>
                                )}
                            </div>
                        ) : (
                            <div className="h-full flex flex-col">
                                {compileErrors.length > 0 && (
                                    <div className="px-4 py-3 bg-destructive/10 border-b border-destructive/20">
                                        <div className="flex items-center gap-2 mb-1">
                                            <AlertTriangle className="w-4 h-4 text-destructive" />
                                            <span className="text-sm font-medium text-destructive">Compilation Errors</span>
                                        </div>
                                        <div className="text-xs text-destructive/80 space-y-0.5 font-mono max-h-32 overflow-y-auto">
                                            {compileErrors.map((err, i) => (
                                                <div key={i}>{err}</div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                {pdfUrl ? (
                                    <iframe
                                        src={pdfUrl}
                                        className="flex-1 w-full"
                                        title="PDF Preview"
                                    />
                                ) : (
                                    <div className="flex-1 flex items-center justify-center text-muted-foreground">
                                        <div className="text-center">
                                            <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
                                            <p className="text-sm">Click <strong>Compile</strong> to generate PDF preview</p>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}

                {/* AI Suggestion Panel */}
                {aiSuggestion && (
                    <div className="w-80 border-l border-border bg-card/50 p-4 overflow-y-auto">
                        <div className="flex items-center gap-2 mb-3">
                            <Wand2 className="w-4 h-4 text-primary" />
                            <h3 className="text-sm font-semibold">AI Suggestion</h3>
                        </div>
                        <div className="text-sm text-muted-foreground whitespace-pre-wrap mb-4 bg-background/50 rounded-lg p-3 border border-border">
                            {aiSuggestion}
                        </div>
                        <div className="flex gap-2">
                            <Button size="sm" className="flex-1" onClick={acceptSuggestion}>
                                Accept
                            </Button>
                            <Button
                                size="sm"
                                variant="outline"
                                className="flex-1"
                                onClick={() => setAiSuggestion("")}
                            >
                                Dismiss
                            </Button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
