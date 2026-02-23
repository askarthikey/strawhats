import { useState, useRef, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import api from "@/lib/api";
import type { ChatMessage, Citation } from "@/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Send, Loader2, Trash2, Bot, User, BookOpen, Copy, Check } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

const MODES = [
  { value: "qa", label: "Q&A" },
  { value: "summarize", label: "Summarize" },
  { value: "compare", label: "Compare" },
  { value: "extract_methods", label: "Methods" },
  { value: "review", label: "Review" },
];

export function ChatPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState("qa");
  const [isStreaming, setIsStreaming] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load chat history
  useEffect(() => {
    if (!workspaceId) return;
    const loadHistory = async () => {
      try {
        const res = await api.get(`/chat/history/${workspaceId}`);
        const history: ChatMessage[] = (res.data || []).map(
          (log: { _id?: string; id?: string; query: string; response: string; citations?: Citation[]; created_at: string }) => [
            {
              id: `${log._id || log.id}-q`,
              role: "user" as const,
              content: log.query,
              timestamp: log.created_at,
            },
            {
              id: `${log._id || log.id}-a`,
              role: "assistant" as const,
              content: log.response,
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
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          query: userMsg.content,
          workspace_id: workspaceId,
          mode,
        }),
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
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.event === "token") {
                  fullContent += data.data;
                  setMessages((prev) => {
                    const updated = [...prev];
                    const last = updated[updated.length - 1];
                    if (last.role === "assistant") {
                      last.content = fullContent;
                    }
                    return updated;
                  });
                } else if (data.event === "citations") {
                  citations = JSON.parse(data.data);
                } else if (data.event === "error") {
                  toast.error(data.data);
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
  }, [input, isStreaming, workspaceId, mode]);

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

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-border">
        <div className="flex items-center gap-3">
          <Bot className="w-5 h-5 text-primary" />
          <h2 className="font-semibold text-foreground">AI Chat</h2>
          <Select value={mode} onValueChange={setMode}>
            <SelectTrigger className="w-32 h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MODES.map((m) => (
                <SelectItem key={m.value} value={m.value}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button variant="ghost" size="sm" onClick={clearHistory}>
          <Trash2 className="w-4 h-4 mr-1" />
          Clear
        </Button>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 px-6" ref={scrollRef}>
        <div className="max-w-3xl mx-auto py-6 space-y-6">
          {loadingHistory ? (
            <div className="space-y-6">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="space-y-2">
                  <Skeleton className="h-10 w-3/4 ml-auto" />
                  <Skeleton className="h-24 w-full" />
                </div>
              ))}
            </div>
          ) : messages.length === 0 ? (
            <EmptyState />
          ) : (
            messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))
          )}
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="border-t border-border px-6 py-4">
        <div className="max-w-3xl mx-auto flex gap-3">
          <Textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your papers..."
            className="min-h-[44px] max-h-32 resize-none"
            rows={1}
            disabled={isStreaming}
          />
          <Button
            onClick={sendMessage}
            disabled={!input.trim() || isStreaming}
            size="icon"
            className="shrink-0 h-11 w-11"
          >
            {isStreaming ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-6">
        <Bot className="w-8 h-8 text-primary" />
      </div>
      <h3 className="text-lg font-semibold text-foreground mb-2">Start a conversation</h3>
      <p className="text-muted-foreground text-sm max-w-md mb-8">
        Ask questions about your imported papers. The AI will search through your research library and provide cited answers.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
        {[
          "Summarize the key findings across all papers",
          "What methods are used for data collection?",
          "Compare the approaches in my papers",
          "What are the main research gaps identified?",
        ].map((prompt) => (
          <button
            key={prompt}
            className="text-left p-3 rounded-lg border border-border bg-surface hover:bg-surface-hover transition-colors text-sm text-muted-foreground hover:text-foreground"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";

  const copyContent = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={cn("flex gap-3", isUser && "justify-end")}>
      {!isUser && (
        <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 mt-1">
          <Bot className="w-4 h-4 text-primary" />
        </div>
      )}

      <div className={cn("max-w-[85%] space-y-2", isUser && "order-first")}>
        <div
          className={cn(
            "rounded-xl px-4 py-3 text-sm",
            isUser
              ? "bg-chat-user text-foreground ml-auto"
              : "bg-chat-ai text-foreground"
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
              {message.isStreaming && (
                <span className="inline-block w-2 h-4 bg-primary animate-pulse ml-1" />
              )}
            </div>
          )}
        </div>

        {/* Citations */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="flex flex-wrap gap-2 px-1">
            {message.citations.map((cite, i) => (
              <Badge
                key={i}
                variant="outline"
                className="text-xs cursor-pointer hover:bg-surface-hover"
                title={cite.text_preview}
              >
                <BookOpen className="w-3 h-3 mr-1" />
                [{cite.citation_number}] {cite.paper_title?.slice(0, 30)}...
              </Badge>
            ))}
          </div>
        )}

        {/* Copy button for assistant messages */}
        {!isUser && !message.isStreaming && message.content && (
          <div className="flex justify-end px-1">
            <button
              onClick={copyContent}
              className="text-muted-foreground hover:text-foreground transition-colors p-1"
            >
              {copied ? (
                <Check className="w-3.5 h-3.5 text-primary" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-lg bg-surface flex items-center justify-center shrink-0 mt-1">
          <User className="w-4 h-4 text-muted-foreground" />
        </div>
      )}
    </div>
  );
}
