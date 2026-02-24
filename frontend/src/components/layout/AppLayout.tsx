import { Outlet, useParams, Navigate, useLocation } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { useAuth } from "@/contexts/AuthContext";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";
import { useEffect, useState } from "react";
import api from "@/lib/api";

export function AppLayout() {
  const { user, isLoading } = useAuth();
  const { workspaceId } = useParams();
  const location = useLocation();
  const [workspaceName, setWorkspaceName] = useState<string>("");

  useEffect(() => {
    if (workspaceId) {
      api.get(`/workspaces/${workspaceId}`)
        .then((res) => setWorkspaceName(res.data.name || ""))
        .catch(() => setWorkspaceName(""));
    } else {
      setWorkspaceName("");
    }
  }, [workspaceId]);

  // Build breadcrumbs from path
  const buildBreadcrumbs = () => {
    const crumbs: { label: string; path?: string }[] = [];
    const path = location.pathname;

    if (path === "/dashboard") {
      crumbs.push({ label: "Dashboard" });
    } else if (path === "/admin") {
      crumbs.push({ label: "Admin" });
    } else if (path === "/settings") {
      crumbs.push({ label: "Settings" });
    } else if (workspaceId) {
      crumbs.push({ label: "Dashboard", path: "/dashboard" });
      crumbs.push({ label: workspaceName || "Workspace", path: `/workspace/${workspaceId}/papers` });

      if (path.includes("/papers")) crumbs.push({ label: "Research" });
      else if (path.includes("/drafts/")) crumbs.push({ label: "Drafts", path: `/workspace/${workspaceId}/drafts` }, { label: "Editor" });
      else if (path.includes("/drafts")) crumbs.push({ label: "Drafts" });
      else if (path.includes("/members")) crumbs.push({ label: "Members" });
    }

    return crumbs;
  };

  if (isLoading) {
    return (
      <div className="flex h-screen bg-background">
        {/* Sidebar skeleton */}
        <div className="w-60 border-r border-border p-4 space-y-3">
          <Skeleton className="h-8 w-32" />
          <div className="space-y-2 mt-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        </div>
        {/* Content skeleton */}
        <div className="flex-1 p-6 space-y-4">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-4 w-96" />
          <div className="grid grid-cols-3 gap-4 mt-8">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-40 w-full" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <TooltipProvider>
      <div className="flex h-screen bg-background overflow-hidden">
        <Sidebar workspaceId={workspaceId} />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header breadcrumbs={buildBreadcrumbs()} />
          <main className="flex-1 overflow-y-auto">
            <Outlet />
          </main>
        </div>
      </div>
    </TooltipProvider>
  );
}
