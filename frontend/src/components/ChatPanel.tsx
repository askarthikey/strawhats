import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import api from "@/lib/api";
import type { ChatMessage, Citation, Paper } from "@/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Send,
  Loader2,
  Trash2,
  Bot,
  User,
  BookOpen,
  Copy,
  Check,
  X,
  Filter,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import mermaid from "mermaid";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";

// Initialize mermaid
mermaid.initialize({
  startOnLoad: false,
  theme: "dark",
  securityLevel: "loose",
  fontFamily: "inherit",
});

// Sanitize Mermaid code to fix common LLM issues
// Parentheses inside node labels like A[Text (info)] confuse the parser —
// they must be quoted: A["Text (info)"]
function sanitizeMermaidCode(code: string): string {
  return code.split("\n").map(line => {
    // Quote contents of [...] node labels that contain ( or ) or &
    line = line.replace(
      /(\w+)\[([^\]"]+)\]/g,
      (_m, id, content) => {
        if (/[()&]/.test(content)) {
          return `${id}["${content}"]`;
        }
        return _m;
      }
    );
    // Quote contents of {...} decision labels that contain ( or ) or &
    line = line.replace(
      /(\w+)\{([^}"]+)\}/g,
      (_m, id, content) => {
        if (/[()&]/.test(content)) {
          return `${id}{"${content}"}`;
        }
        return _m;
      }
    );
    return line;
  }).join("\n");
}

// Mermaid diagram renderer
function MermaidDiagram({ code }: { code: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState<string>("");
  const id = useMemo(() => `mermaid-${Math.random().toString(36).slice(2, 9)}`, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const sanitized = sanitizeMermaidCode(code.trim());
        const { svg: renderedSvg } = await mermaid.render(id, sanitized);
        if (!cancelled) setSvg(renderedSvg);
      } catch (err: any) {
        // Mermaid injects error elements into the DOM on failure — clean them up
        const errorEl = document.getElementById(`d${id}`);
        if (errorEl) errorEl.remove();
        // Also remove any stray mermaid error containers
        document.querySelectorAll(`[id="${id}"]`).forEach((el) => el.remove());
        document.querySelectorAll('.mermaid-error').forEach((el) => el.remove());
        // Remove any element that Mermaid may have appended at the end of body
        const bodyChildren = document.body.children;
        for (let i = bodyChildren.length - 1; i >= 0; i--) {
          const child = bodyChildren[i] as HTMLElement;
          if (child.id?.startsWith('d') && child.querySelector?.('svg')) {
            // Mermaid error SVGs
            if (child.textContent?.includes('Syntax error')) {
              child.remove();
            }
          }
        }
        if (!cancelled) setError(err?.message || "Failed to render diagram");
      }
    })();
    return () => { cancelled = true; };
  }, [code, id]);

  if (error) {
    return (
      <div className="bg-destructive/10 border border-destructive/30 rounded p-2 text-xs text-destructive">
        Diagram error: {error}
        <pre className="mt-1 text-[10px] opacity-70 overflow-x-auto">{code}</pre>
      </div>
    );
  }

  const exportSvg = () => {
    if (!svg) return;
    const blob = new Blob([svg], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "diagram.svg";
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportPng = () => {
    if (!svg || !containerRef.current) return;
    const svgEl = containerRef.current.querySelector("svg");
    if (!svgEl) return;
    const canvas = document.createElement("canvas");
    const bbox = svgEl.getBoundingClientRect();
    canvas.width = bbox.width * 2;
    canvas.height = bbox.height * 2;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(2, 2);
    const img = new Image();
    const svgData = new XMLSerializer().serializeToString(svgEl);
    img.onload = () => {
      ctx.drawImage(img, 0, 0);
      const a = document.createElement("a");
      a.href = canvas.toDataURL("image/png");
      a.download = "diagram.png";
      a.click();
    };
    img.src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(svgData)));
  };

  return (
    <div className="my-2 rounded-lg border border-border overflow-hidden group/diagram">
      <div className="flex items-center justify-end gap-1 px-2 py-1 bg-surface/50 border-b border-border opacity-0 group-hover/diagram:opacity-100 transition-opacity">
        <button onClick={() => navigator.clipboard.writeText(code)} className="px-2 py-0.5 text-[10px] bg-primary/10 hover:bg-primary/20 text-primary rounded" title="Copy Mermaid code">
          Copy Code
        </button>
        <button onClick={exportSvg} className="px-2 py-0.5 text-[10px] bg-primary/10 hover:bg-primary/20 text-primary rounded" title="Export as SVG">
          SVG
        </button>
        <button onClick={exportPng} className="px-2 py-0.5 text-[10px] bg-primary/10 hover:bg-primary/20 text-primary rounded" title="Export as PNG">
          PNG
        </button>
      </div>
      <div
        ref={containerRef}
        className="p-2 bg-background/50 overflow-x-auto flex justify-center"
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    </div>
  );
}

// Recharts chart renderer
const COLORS = ["#8884d8", "#82ca9d", "#ffc658", "#ff7c7c", "#8dd1e1", "#d084d0", "#ffb347", "#87ceeb"];

function RechartsRenderer({ code }: { code: string }) {
  const [error, setError] = useState<string>("");
  const chartRef = useRef<HTMLDivElement>(null);
  const config = useMemo(() => {
    try {
      return JSON.parse(code.trim());
    } catch (err: any) {
      setError("Invalid chart JSON");
      return null;
    }
  }, [code]);

  if (error || !config) {
    return (
      <div className="bg-destructive/10 border border-destructive/30 rounded p-2 text-xs text-destructive">
        Chart error: {error}
      </div>
    );
  }

  const { type, title, data, xKey = "name", series = [] } = config;

  const exportPng = () => {
    if (!chartRef.current) return;
    const svgEl = chartRef.current.querySelector("svg");
    if (!svgEl) return;
    const canvas = document.createElement("canvas");
    const bbox = svgEl.getBoundingClientRect();
    canvas.width = bbox.width * 2;
    canvas.height = bbox.height * 2;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "#1a1a2e";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.scale(2, 2);
    const img = new Image();
    const svgData = new XMLSerializer().serializeToString(svgEl);
    img.onload = () => {
      ctx.drawImage(img, 0, 0);
      const a = document.createElement("a");
      a.href = canvas.toDataURL("image/png");
      a.download = `${title || "chart"}.png`;
      a.click();
    };
    img.src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(svgData)));
  };

  const exportJson = () => {
    navigator.clipboard.writeText(JSON.stringify(config, null, 2));
  };

  return (
    <div className="my-2 rounded-lg border border-border overflow-hidden group/chart">
      <div className="flex items-center justify-between px-3 py-1.5 bg-surface/50 border-b border-border">
        {title && <p className="text-xs font-medium text-foreground">{title}</p>}
        <div className="flex items-center gap-1 ml-auto opacity-0 group-hover/chart:opacity-100 transition-opacity">
          <button onClick={exportJson} className="px-2 py-0.5 text-[10px] bg-primary/10 hover:bg-primary/20 text-primary rounded" title="Copy chart data">
            Copy Data
          </button>
          <button onClick={exportPng} className="px-2 py-0.5 text-[10px] bg-primary/10 hover:bg-primary/20 text-primary rounded" title="Export as PNG">
            PNG
          </button>
        </div>
      </div>
      <div ref={chartRef} className="p-3 bg-background/50">
        <ResponsiveContainer width="100%" height={250}>
          {type === "pie" ? (
            <PieChart>
              <Pie
                data={data}
                dataKey={series[0]?.key || "value"}
                nameKey={xKey}
                cx="50%"
                cy="50%"
                outerRadius={80}
                label={({ name, value }: any) => `${name}: ${value}`}
              >
                {data.map((_: any, i: number) => (
                  <Cell key={i} fill={series[0]?.color || COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          ) : type === "line" ? (
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis dataKey={xKey} tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Legend />
              {series.map((s: any, i: number) => (
                <Line key={i} type="monotone" dataKey={s.key} stroke={s.color || COLORS[i]} name={s.name || s.key} strokeWidth={2} />
              ))}
            </LineChart>
          ) : (
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis dataKey={xKey} tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Legend />
              {series.map((s: any, i: number) => (
                <Bar key={i} dataKey={s.key} fill={s.color || COLORS[i]} name={s.name || s.key} />
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// Custom code component for ReactMarkdown that renders mermaid and recharts
const markdownCodeComponent: Components["code"] = ({ className, children, ...props }) => {
  const match = /language-(\w+)/.exec(className || "");
  const lang = match?.[1];
  const codeString = String(children).replace(/\n$/, "");

  if (lang === "mermaid") {
    return <MermaidDiagram code={codeString} />;
  }
  if (lang === "recharts") {
    return <RechartsRenderer code={codeString} />;
  }
  if (lang === "latex") {
    return (
      <div className="relative my-2 group">
        <button
          onClick={() => {
            navigator.clipboard.writeText(codeString);
          }}
          className="absolute top-2 right-2 px-2 py-1 text-[10px] bg-primary/20 hover:bg-primary/30 text-primary rounded opacity-0 group-hover:opacity-100 transition-opacity"
          title="Copy LaTeX"
        >
          Copy LaTeX
        </button>
        <code className={className} {...props}>
          {children}
        </code>
      </div>
    );
  }

  // Default: render as code block
  return (
    <code className={className} {...props}>
      {children}
    </code>
  );
};

interface ChatPanelProps {
  workspaceId: string;
  papers: Paper[];
  onClose: () => void;
}

export function ChatPanel({ workspaceId, papers, onClose }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [selectedPaperIds, setSelectedPaperIds] = useState<string[]>([]);
  const [showPaperFilter, setShowPaperFilter] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load chat history
  useEffect(() => {
    if (!workspaceId) return;
    const loadHistory = async () => {
      try {
        const res = await api.get(`/chat/history/${workspaceId}`);
        const historyData = res.data?.history || res.data || [];
        const history: ChatMessage[] = historyData.map(
          (log: { _id?: string; id?: string; question: string; answer: string; citations?: Citation[]; created_at: string }) => [
            {
              id: `${log._id || log.id}-q`,
              role: "user" as const,
              content: log.question,
              timestamp: log.created_at,
            },
            {
              id: `${log._id || log.id}-a`,
              role: "assistant" as const,
              content: log.answer,
              citations: log.citations || [],
              timestamp: log.created_at,
            },
          ]
        ).flat();
        setMessages(history);
      } catch {
        // No history
      } finally {
        setLoadingHistory(false);
      }
    };
    loadHistory();
  }, [workspaceId]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const togglePaper = (paperId: string) => {
    setSelectedPaperIds((prev) =>
      prev.includes(paperId)
        ? prev.filter((id) => id !== paperId)
        : [...prev, paperId]
    );
  };

  const sendMessage = useCallback(async () => {
    if (!input.trim() || isStreaming || !workspaceId) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: input.trim(),
      timestamp: new Date().toISOString(),
    };

    const assistantMsg: ChatMessage = {
      id: `assistant-${Date.now()}`,
      role: "assistant",
      content: "",
      citations: [],
      timestamp: new Date().toISOString(),
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setInput("");
    setIsStreaming(true);

    try {
      const token = localStorage.getItem("token");
      const body: Record<string, unknown> = {
        question: userMsg.content,
        workspace_id: workspaceId,
        provider: "gemini",
        chat_history: messages
          .filter((m) => !m.isStreaming)
          .slice(-6)
          .map((m) => ({ role: m.role, content: m.content })),
      };

      // Add paper_ids filter if papers are selected
      if (selectedPaperIds.length > 0) {
        body.paper_ids = selectedPaperIds;
      }

      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let fullContent = "";
      let citations: Citation[] = [];

      if (reader) {
        let buffer = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data:")) {
              const raw = line.slice(5).trim();
              if (!raw) continue;
              try {
                const data = JSON.parse(raw);
                if (data.type === "token" && data.token) {
                  fullContent += data.token;
                  setMessages((prev) => {
                    const updated = [...prev];
                    const last = updated[updated.length - 1];
                    if (last.role === "assistant") {
                      last.content = fullContent;
                    }
                    return updated;
                  });
                } else if (data.type === "citations" && data.citations) {
                  citations = data.citations;
                } else if (data.type === "error") {
                  toast.error(data.error || "Generation error");
                }
              } catch {
                // Ignore malformed SSE
              }
            }
          }
        }
      }

      // Finalize message
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last.role === "assistant") {
          last.content = fullContent;
          last.citations = citations;
          last.isStreaming = false;
        }
        return updated;
      });
    } catch (err) {
      console.error("Chat error:", err);
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last.role === "assistant") {
          last.content = "Sorry, an error occurred. Please try again.";
          last.isStreaming = false;
        }
        return updated;
      });
      toast.error("Failed to get response");
    } finally {
      setIsStreaming(false);
      inputRef.current?.focus();
    }
  }, [input, isStreaming, workspaceId, messages, selectedPaperIds]);

  const clearHistory = async () => {
    if (!workspaceId) return;
    try {
      await api.delete(`/chat/history/${workspaceId}`);
      setMessages([]);
      toast.success("Chat history cleared");
    } catch {
      toast.error("Failed to clear history");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const indexedPapers = papers.filter((p) => p.status === "indexed");

  return (
    <div className="flex flex-col h-full bg-background border-l border-border">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-primary" />
          <h3 className="font-semibold text-sm text-foreground">AI Chat</h3>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={clearHistory} title="Clear history">
            <Trash2 className="w-3.5 h-3.5" />
          </Button>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose} title="Close chat">
            <X className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* Paper context filter */}
      <div className="px-4 py-2 border-b border-border shrink-0">
        <button
          onClick={() => setShowPaperFilter(!showPaperFilter)}
          className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors w-full"
        >
          <Filter className="w-3 h-3" />
          <span>
            {selectedPaperIds.length === 0
              ? "All papers (click to filter)"
              : `${selectedPaperIds.length} paper${selectedPaperIds.length > 1 ? "s" : ""} selected`}
          </span>
          {selectedPaperIds.length > 0 && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setSelectedPaperIds([]);
              }}
              className="ml-auto text-xs text-muted-foreground hover:text-foreground"
            >
              Clear
            </button>
          )}
        </button>

        {showPaperFilter && (
          <div className="mt-2 max-h-32 overflow-y-auto space-y-1">
            {indexedPapers.length === 0 ? (
              <p className="text-xs text-muted-foreground py-2">No indexed papers yet.</p>
            ) : (
              indexedPapers.map((paper) => (
                <label
                  key={paper.id}
                  className="flex items-center gap-2 py-1 px-1 rounded hover:bg-surface-hover cursor-pointer text-xs"
                >
                  <Checkbox
                    checked={selectedPaperIds.includes(paper.id)}
                    onCheckedChange={() => togglePaper(paper.id)}
                    className="h-3.5 w-3.5"
                  />
                  <span className="truncate text-foreground">{paper.title}</span>
                </label>
              ))
            )}
          </div>
        )}
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 px-4" ref={scrollRef}>
        <div className="py-4 space-y-4">
          {loadingHistory ? (
            <div className="flex justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            </div>
          ) : messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Bot className="w-8 h-8 text-primary/40 mb-3" />
              <p className="text-xs text-muted-foreground max-w-[200px]">
                Ask questions about your papers. Select specific papers to narrow the context.
              </p>
              <div className="grid gap-2 mt-4 w-full">
                {[
                  "Summarize key findings",
                  "Compare methodologies",
                  "What research gaps exist?",
                ].map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => setInput(prompt)}
                    className="text-left p-2 rounded border border-border hover:bg-surface-hover transition-colors text-xs text-muted-foreground"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <ChatBubble key={msg.id} message={msg} />
            ))
          )}
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="border-t border-border px-4 py-3 shrink-0">
        <div className="flex gap-2">
          <Textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your papers..."
            className="min-h-[36px] max-h-24 resize-none text-sm"
            rows={1}
            disabled={isStreaming}
          />
          <Button
            onClick={sendMessage}
            disabled={!input.trim() || isStreaming}
            size="icon"
            className="shrink-0 h-9 w-9"
          >
            {isStreaming ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Send className="w-3.5 h-3.5" />
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

function ChatBubble({ message }: { message: ChatMessage }) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";

  const copyContent = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={cn("flex gap-2", isUser && "justify-end")}>
      {!isUser && (
        <div className="w-6 h-6 rounded bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
          <Bot className="w-3 h-3 text-primary" />
        </div>
      )}

      <div className={cn("max-w-[90%] space-y-1", isUser && "order-first")}>
        <div
          className={cn(
            "rounded-lg px-3 py-2 text-sm",
            isUser
              ? "bg-primary text-primary-foreground ml-auto"
              : "bg-muted text-foreground"
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap text-xs">{message.content}</p>
          ) : (
            <div className="prose prose-sm prose-invert max-w-none text-xs [&_p]:mb-1 [&_ul]:mb-1 [&_ol]:mb-1">
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeKatex, rehypeHighlight]}
                components={{ code: markdownCodeComponent }}
              >
                {message.content}
              </ReactMarkdown>
              {message.isStreaming && (
                <span className="inline-block w-1.5 h-3 bg-primary animate-pulse ml-0.5" />
              )}
            </div>
          )}
        </div>

        {/* Citations */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="flex flex-wrap gap-1 px-0.5">
            {message.citations.map((cite, i) => (
              <Badge
                key={i}
                variant="outline"
                className="text-[10px] cursor-pointer hover:bg-surface-hover py-0"
                title={cite.snippet}
              >
                <BookOpen className="w-2.5 h-2.5 mr-0.5" />
                [{i + 1}] {cite.title?.slice(0, 20)}...
              </Badge>
            ))}
          </div>
        )}

        {/* Copy button */}
        {!isUser && !message.isStreaming && message.content && (
          <div className="flex justify-end">
            <button
              onClick={copyContent}
              className="text-muted-foreground hover:text-foreground transition-colors p-0.5"
            >
              {copied ? (
                <Check className="w-3 h-3 text-primary" />
              ) : (
                <Copy className="w-3 h-3" />
              )}
            </button>
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-6 h-6 rounded bg-surface flex items-center justify-center shrink-0 mt-0.5">
          <User className="w-3 h-3 text-muted-foreground" />
        </div>
      )}
    </div>
  );
}
