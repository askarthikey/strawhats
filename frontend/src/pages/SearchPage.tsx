import { useState } from "react";
import { useParams } from "react-router-dom";
import api from "@/lib/api";
import type { SearchResult } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Search as SearchIcon, Loader2, FileText, BookOpen } from "lucide-react";
import { toast } from "sonner";

export function SearchPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchMode, setSearchMode] = useState<"semantic" | "hybrid">("hybrid");

  const handleSearch = async () => {
    if (!query.trim() || !workspaceId) return;
    setLoading(true);
    try {
      const endpoint = searchMode === "semantic" ? "/search/semantic" : "/search/hybrid";
      const res = await api.post(endpoint, {
        query: query.trim(),
        workspace_id: workspaceId,
        top_k: 20,
      });
      setResults(res.data);
    } catch {
      toast.error("Search failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground mb-1">Search</h1>
        <p className="text-muted-foreground text-sm">
          Semantic search across your research papers
        </p>
      </div>

      <div className="space-y-4">
        <Tabs value={searchMode} onValueChange={(v) => setSearchMode(v as "semantic" | "hybrid")}>
          <TabsList>
            <TabsTrigger value="hybrid">Hybrid Search</TabsTrigger>
            <TabsTrigger value="semantic">Semantic Only</TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="flex gap-2">
          <Input
            placeholder="Search your papers..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="text-base"
          />
          <Button onClick={handleSearch} disabled={loading || !query.trim()}>
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <SearchIcon className="w-4 h-4" />
            )}
          </Button>
        </div>

        {/* Results */}
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="p-4">
                  <Skeleton className="h-4 w-48 mb-2" />
                  <Skeleton className="h-16 w-full mb-2" />
                  <Skeleton className="h-4 w-24" />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : results.length > 0 ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              {results.length} results found
            </p>
            {results.map((result, i) => (
              <Card key={i} className="hover:border-border-hover transition-colors">
                <CardContent className="p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <BookOpen className="w-4 h-4 text-primary shrink-0" />
                      <span className="font-medium text-sm text-foreground line-clamp-1">
                        {result.paper_title}
                      </span>
                    </div>
                    <Badge variant="outline" className="text-xs shrink-0 ml-2">
                      {(result.score * 100).toFixed(0)}% match
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed line-clamp-4">
                    {result.text}
                  </p>
                  <div className="flex items-center gap-2 mt-3">
                    <Badge variant="secondary" className="text-xs">
                      <FileText className="w-3 h-3 mr-1" />
                      Page {result.page_number}
                    </Badge>
                    <Badge variant="secondary" className="text-xs">
                      Chunk #{result.chunk_index}
                    </Badge>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
