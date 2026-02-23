import { useState, useEffect } from "react";
import api from "@/lib/api";
import type { HealthCheck, Metrics } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  RefreshCw,
  Database,
  Server,
  Cpu,
  Cloud,
  FileText,
  Users,
  MessageSquare,
  FolderOpen,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";

export function AdminPage() {
  const [health, setHealth] = useState<HealthCheck | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loadingHealth, setLoadingHealth] = useState(true);
  const [loadingMetrics, setLoadingMetrics] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    try {
      const [healthRes, metricsRes] = await Promise.all([
        api.get("/admin/health"),
        api.get("/admin/metrics"),
      ]);
      setHealth(healthRes.data);
      setMetrics(metricsRes.data);
    } catch {
      toast.error("Failed to load admin data");
    } finally {
      setLoadingHealth(false);
      setLoadingMetrics(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const refresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
    toast.success("Refreshed");
  };

  const serviceIcons: Record<string, React.ElementType> = {
    mongodb: Database,
    pinecone: Server,
    ollama: Cpu,
    gemini: Cpu,
    cloudinary: Cloud,
  };

  const metricCards = metrics
    ? [
        { label: "Users", value: metrics.users, icon: Users },
        { label: "Workspaces", value: metrics.workspaces, icon: FolderOpen },
        { label: "Papers", value: metrics.papers, icon: FileText },
        { label: "Chunks", value: metrics.chunks, icon: Database },
        { label: "Chat Logs", value: metrics.chat_logs, icon: MessageSquare },
        { label: "Drafts", value: metrics.drafts, icon: FileText },
      ]
    : [];

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Admin</h1>
          <p className="text-muted-foreground text-sm mt-1">System health and metrics</p>
        </div>
        <Button variant="outline" onClick={refresh} disabled={refreshing}>
          {refreshing ? (
            <Loader2 className="w-4 h-4 animate-spin mr-2" />
          ) : (
            <RefreshCw className="w-4 h-4 mr-2" />
          )}
          Refresh
        </Button>
      </div>

      {/* Health Status */}
      <Card className="mb-6">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">Service Health</CardTitle>
              <CardDescription>Status of connected services</CardDescription>
            </div>
            {health && (
              <Badge
                variant={health.status === "healthy" ? "default" : "destructive"}
              >
                {health.status}
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {loadingHealth ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex items-center justify-between">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-6 w-20" />
                </div>
              ))}
            </div>
          ) : health ? (
            <div className="space-y-3">
              {Object.entries(health.services).map(([name, service]) => {
                const Icon = serviceIcons[name] || Server;
                return (
                  <div key={name}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Icon className="w-4 h-4 text-muted-foreground" />
                        <span className="text-sm font-medium capitalize">{name}</span>
                      </div>
                      <Badge
                        variant={
                          service.status === "healthy"
                            ? "default"
                            : service.status === "configured"
                            ? "secondary"
                            : service.status === "unavailable"
                            ? "outline"
                            : "destructive"
                        }
                        className="text-xs"
                      >
                        {service.status}
                      </Badge>
                    </div>
                    {service.error && (
                      <p className="text-xs text-destructive ml-6 mt-1">{service.error}</p>
                    )}
                    <Separator className="mt-3" />
                  </div>
                );
              })}
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* Metrics */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Metrics</CardTitle>
          <CardDescription>Database statistics</CardDescription>
        </CardHeader>
        <CardContent>
          {loadingMetrics ? (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="p-4 rounded-lg bg-surface">
                  <Skeleton className="h-8 w-16 mb-2" />
                  <Skeleton className="h-4 w-20" />
                </div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {metricCards.map(({ label, value, icon: Icon }) => (
                <div key={label} className="p-4 rounded-lg bg-surface">
                  <div className="flex items-center gap-2 mb-1">
                    <Icon className="w-4 h-4 text-primary" />
                    <span className="text-2xl font-bold text-foreground">{value}</span>
                  </div>
                  <span className="text-xs text-muted-foreground">{label}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
