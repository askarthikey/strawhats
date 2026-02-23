import { useState } from "react";
import { useParams } from "react-router-dom";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, Download, Copy, Check } from "lucide-react";
import { toast } from "sonner";

export function ReferencesPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const [bibtex, setBibtex] = useState("");
  const [ris, setRis] = useState("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const generateRefs = async (format: "bibtex" | "ris") => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      // Get all papers in workspace first
      const papersRes = await api.get(`/papers/?workspace_id=${workspaceId}`);
      const paperIds = papersRes.data.map((p: { id: string }) => p.id);

      if (paperIds.length === 0) {
        toast.error("No papers in this workspace");
        setLoading(false);
        return;
      }

      const res = await api.post(`/references/${format}`, {
        paper_ids: paperIds,
      });

      if (format === "bibtex") {
        setBibtex(res.data);
      } else {
        setRis(res.data);
      }
    } catch {
      toast.error(`Failed to generate ${format.toUpperCase()}`);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const downloadFile = (content: string, filename: string) => {
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">References</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Export your paper references in BibTeX or RIS format
        </p>
      </div>

      <Tabs defaultValue="bibtex">
        <TabsList>
          <TabsTrigger value="bibtex">BibTeX</TabsTrigger>
          <TabsTrigger value="ris">RIS</TabsTrigger>
        </TabsList>

        <TabsContent value="bibtex" className="mt-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base">BibTeX Export</CardTitle>
                  <CardDescription>Generate BibTeX entries for all papers</CardDescription>
                </div>
                <Button onClick={() => generateRefs("bibtex")} disabled={loading}>
                  {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                  Generate
                </Button>
              </div>
            </CardHeader>
            {bibtex && (
              <CardContent>
                <div className="relative">
                  <pre className="bg-code-bg rounded-lg p-4 text-sm text-foreground overflow-x-auto max-h-96 font-mono">
                    {bibtex}
                  </pre>
                  <div className="absolute top-2 right-2 flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => copyToClipboard(bibtex)}
                    >
                      {copied ? (
                        <Check className="w-4 h-4 text-primary" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => downloadFile(bibtex, "references.bib")}
                    >
                      <Download className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            )}
          </Card>
        </TabsContent>

        <TabsContent value="ris" className="mt-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base">RIS Export</CardTitle>
                  <CardDescription>Generate RIS entries for all papers</CardDescription>
                </div>
                <Button onClick={() => generateRefs("ris")} disabled={loading}>
                  {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                  Generate
                </Button>
              </div>
            </CardHeader>
            {ris && (
              <CardContent>
                <div className="relative">
                  <pre className="bg-code-bg rounded-lg p-4 text-sm text-foreground overflow-x-auto max-h-96 font-mono">
                    {ris}
                  </pre>
                  <div className="absolute top-2 right-2 flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => copyToClipboard(ris)}
                    >
                      {copied ? (
                        <Check className="w-4 h-4 text-primary" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => downloadFile(ris, "references.ris")}
                    >
                      <Download className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            )}
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
