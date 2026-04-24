import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  FileText,
  PenTool,
  Users,
  MessageSquare,
  TrendingUp,
  ChevronDown,
  ChevronRight,
  Crown,
  Award,
  Medal,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  Legend,
} from "recharts";

/* ===== Types ===== */
interface DraftDetail {
  draft_id: string;
  draft_title: string;
  contribution_pct: number;
}

interface Contributor {
  user_id: string;
  name: string;
  email: string;
  role: string;
  papers_added: number;
  draft_contributions: number;
  draft_details: DraftDetail[];
  total_score: number;
}

interface AnalyticsData {
  workspace_id: string;
  workspace_name: string;
  summary: {
    total_papers: number;
    indexed_papers: number;
    pending_papers: number;
    processing_papers: number;
    failed_papers: number;
    total_drafts: number;
    total_draft_versions: number;
    total_members: number;
    total_chat_sessions: number;
  };
  papers_by_source: { source: string; count: number }[];
  contributors: Contributor[];
  activity_timeline: { month: string; papers: number; drafts: number }[];
}

/* ===== Palette ===== */
const SOURCE_COLORS: Record<string, string> = {
  openalex: "#3ECF8E",
  arxiv: "#F97316",
  crossref: "#8B5CF6",
  pubmed: "#EC4899",
  upload: "#06B6D4",
  unknown: "#6B7280",
};

const STATUS_COLORS: Record<string, string> = {
  indexed: "#3ECF8E",
  pending: "#F59E0B",
  processing: "#3B82F6",
  failed: "#EF4444",
};

const RANK_ICONS = [Crown, Award, Medal];
const RANK_COLORS = ["#FFD700", "#C0C0C0", "#CD7F32"];

/* ===== Custom chart tooltip ===== */
function ChartTooltipContent({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2 shadow-xl">
      <p className="text-xs text-muted-foreground mb-1">{label}</p>
      {payload.map((entry: any, i: number) => (
        <p key={i} className="text-sm font-medium" style={{ color: entry.color }}>
          {entry.name}: {entry.value}
        </p>
      ))}
    </div>
  );
}

/* ===== Stat card ===== */
function StatCard({
  icon: Icon,
  label,
  value,
  accent,
  sub,
}: {
  icon: any;
  label: string;
  value: number;
  accent: string;
  sub?: string;
}) {
  return (
    <Card className="relative overflow-hidden group hover:border-primary/30 transition-all duration-300">
      <div
        className="absolute inset-0 opacity-[0.04] group-hover:opacity-[0.08] transition-opacity"
        style={{ background: `linear-gradient(135deg, ${accent}, transparent)` }}
      />
      <CardContent className="pt-5 pb-4 px-5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">{label}</p>
            <p className="text-3xl font-bold text-foreground tabular-nums">{value}</p>
            {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
          </div>
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
            style={{ background: `${accent}15`, color: accent }}
          >
            <Icon className="w-5 h-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

/* ===== Contributor row ===== */
function ContributorRow({
  contributor,
  rank,
  maxScore,
}: {
  contributor: Contributor;
  rank: number;
  maxScore: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const barWidth = maxScore > 0 ? (contributor.total_score / maxScore) * 100 : 0;
  const RankIcon = rank < 3 ? RANK_ICONS[rank] : null;
  const rankColor = rank < 3 ? RANK_COLORS[rank] : undefined;

  const roleColors: Record<string, string> = {
    owner: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    editor: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    commenter: "bg-purple-500/15 text-purple-400 border-purple-500/30",
    viewer: "bg-gray-500/15 text-gray-400 border-gray-500/30",
  };

  return (
    <div className="border-b border-border/50 last:border-0">
      <button
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface-hover/50 transition-colors text-left"
        onClick={() => setExpanded(!expanded)}
      >
        {/* Rank */}
        <div className="w-7 flex items-center justify-center shrink-0">
          {RankIcon ? (
            <RankIcon className="w-4 h-4" style={{ color: rankColor }} />
          ) : (
            <span className="text-xs text-muted-foreground font-mono">#{rank + 1}</span>
          )}
        </div>

        {/* Avatar circle */}
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
          style={{
            background: `hsl(${(contributor.name.charCodeAt(0) * 37) % 360}, 50%, 25%)`,
            color: `hsl(${(contributor.name.charCodeAt(0) * 37) % 360}, 70%, 70%)`,
          }}
        >
          {contributor.name.charAt(0).toUpperCase()}
        </div>

        {/* Name + role */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-foreground truncate">{contributor.name}</span>
            <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${roleColors[contributor.role] || ""}`}>
              {contributor.role}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground truncate">{contributor.email}</p>
        </div>

        {/* Stats */}
        <div className="hidden sm:flex items-center gap-4 text-xs text-muted-foreground shrink-0">
          <span className="flex items-center gap-1">
            <FileText className="w-3 h-3" />
            {contributor.papers_added} papers
          </span>
          <span className="flex items-center gap-1">
            <PenTool className="w-3 h-3" />
            {contributor.draft_contributions.toFixed(1)} drafts
          </span>
        </div>

        {/* Contribution bar */}
        <div className="w-24 sm:w-32 shrink-0">
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 bg-surface rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${barWidth}%`,
                  background: `linear-gradient(90deg, #3ECF8E, #06B6D4)`,
                }}
              />
            </div>
            <span className="text-xs font-mono text-muted-foreground w-8 text-right">
              {contributor.total_score.toFixed(1)}
            </span>
          </div>
        </div>

        {/* Expand */}
        <div className="shrink-0 text-muted-foreground">
          {contributor.draft_details.length > 0 ? (
            expanded ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )
          ) : (
            <div className="w-4" />
          )}
        </div>
      </button>

      {/* Expanded draft details */}
      {expanded && contributor.draft_details.length > 0 && (
        <div className="px-4 pb-3 pl-[4.5rem]">
          <div className="rounded-lg bg-background/50 border border-border/30 overflow-hidden">
            <div className="grid grid-cols-[1fr_80px_100px] gap-2 px-3 py-1.5 text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border/30">
              <span>Draft</span>
              <span className="text-right">Contribution</span>
              <span></span>
            </div>
            {contributor.draft_details.map((d) => (
              <div
                key={d.draft_id}
                className="grid grid-cols-[1fr_80px_100px] gap-2 px-3 py-2 text-sm items-center hover:bg-surface-hover/30"
              >
                <span className="text-foreground truncate">{d.draft_title}</span>
                <span className="text-right font-mono text-xs text-muted-foreground">
                  {d.contribution_pct.toFixed(1)}%
                </span>
                <div className="h-1.5 bg-surface rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${d.contribution_pct}%`,
                      background: `linear-gradient(90deg, #3ECF8E, #06B6D4)`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ===== Main Page ===== */
export function AnalyticsPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!workspaceId) return;
    setLoading(true);
    api
      .get(`/workspaces/${workspaceId}/analytics`)
      .then((res) => setData(res.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [workspaceId]);

  if (loading) {
    return (
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        <Skeleton className="h-8 w-56" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Skeleton className="h-72 lg:col-span-2" />
          <Skeleton className="h-72" />
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <TrendingUp className="w-12 h-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium text-foreground mb-2">No analytics data</h3>
            <p className="text-muted-foreground text-sm text-center max-w-md">
              Start importing papers and writing drafts to see your workspace analytics here.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const { summary, papers_by_source, contributors, activity_timeline } = data;
  const maxScore = contributors.length > 0 ? Math.max(...contributors.map((c) => c.total_score)) : 1;

  // Paper status data for bar chart
  const statusData = [
    { status: "Indexed", count: summary.indexed_papers, fill: STATUS_COLORS.indexed },
    { status: "Processing", count: summary.processing_papers, fill: STATUS_COLORS.processing },
    { status: "Pending", count: summary.pending_papers, fill: STATUS_COLORS.pending },
    { status: "Failed", count: summary.failed_papers, fill: STATUS_COLORS.failed },
  ].filter((d) => d.count > 0);

  // Format month label
  const formatMonth = (m: string) => {
    const [y, mo] = m.split("-");
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${months[parseInt(mo) - 1]} ${y.slice(2)}`;
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6" id="analytics-page">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Analytics</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Workspace activity overview for <span className="text-foreground font-medium">{data.workspace_name}</span>
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={FileText} label="Total Papers" value={summary.total_papers} accent="#3ECF8E" sub={`${summary.indexed_papers} indexed`} />
        <StatCard icon={PenTool} label="Drafts Written" value={summary.total_drafts} accent="#8B5CF6" sub={`${summary.total_draft_versions} versions`} />
        <StatCard icon={Users} label="Team Members" value={summary.total_members} accent="#F97316" />
        <StatCard icon={MessageSquare} label="AI Chat Sessions" value={summary.total_chat_sessions} accent="#06B6D4" />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Activity timeline — IEEE style */}
        <Card className="lg:col-span-2 overflow-hidden">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-primary" />
              Submission Timeline
            </CardTitle>
            <p className="text-xs text-muted-foreground">Papers and drafts over the last 12 months</p>
          </CardHeader>
          <CardContent className="pr-2">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={activity_timeline} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gradPapers" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3ECF8E" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3ECF8E" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gradDrafts" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                  <XAxis dataKey="month" tickFormatter={formatMonth} tick={{ fill: "#8F8F8F", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} tick={{ fill: "#8F8F8F", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <RechartsTooltip content={<ChartTooltipContent />} />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                  <Area type="monotone" dataKey="papers" name="Papers" stroke="#3ECF8E" fill="url(#gradPapers)" strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 0, fill: "#3ECF8E" }} />
                  <Area type="monotone" dataKey="drafts" name="Drafts" stroke="#8B5CF6" fill="url(#gradDrafts)" strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 0, fill: "#8B5CF6" }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Papers by source — donut */}
        <Card className="overflow-hidden">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Papers by Source</CardTitle>
            <p className="text-xs text-muted-foreground">Distribution of imported papers</p>
          </CardHeader>
          <CardContent>
            {papers_by_source.length === 0 ? (
              <div className="h-52 flex items-center justify-center text-sm text-muted-foreground">
                No papers yet
              </div>
            ) : (
              <>
                <div className="h-44">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={papers_by_source}
                        cx="50%"
                        cy="50%"
                        innerRadius={45}
                        outerRadius={70}
                        dataKey="count"
                        nameKey="source"
                        strokeWidth={2}
                        stroke="#1C1C1C"
                      >
                        {papers_by_source.map((entry) => (
                          <Cell key={entry.source} fill={SOURCE_COLORS[entry.source] || SOURCE_COLORS.unknown} />
                        ))}
                      </Pie>
                      <RechartsTooltip content={<ChartTooltipContent />} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 justify-center">
                  {papers_by_source.map((s) => (
                    <div key={s.source} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <div
                        className="w-2.5 h-2.5 rounded-full shrink-0"
                        style={{ background: SOURCE_COLORS[s.source] || SOURCE_COLORS.unknown }}
                      />
                      <span className="capitalize">{s.source}</span>
                      <span className="font-mono text-foreground">{s.count}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Second row: Status breakdown + empty space or extra chart */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Paper status breakdown */}
        <Card className="overflow-hidden">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Paper Status</CardTitle>
            <p className="text-xs text-muted-foreground">Processing pipeline overview</p>
          </CardHeader>
          <CardContent>
            {statusData.length === 0 ? (
              <div className="h-40 flex items-center justify-center text-sm text-muted-foreground">
                No papers yet
              </div>
            ) : (
              <div className="h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={statusData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }} barSize={32}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                    <XAxis dataKey="status" tick={{ fill: "#8F8F8F", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis allowDecimals={false} tick={{ fill: "#8F8F8F", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <RechartsTooltip content={<ChartTooltipContent />} />
                    <Bar dataKey="count" name="Papers" radius={[4, 4, 0, 0]}>
                      {statusData.map((entry, i) => (
                        <Cell key={i} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Contributor leaderboard */}
        <Card className="lg:col-span-2 overflow-hidden">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Users className="w-4 h-4 text-primary" />
              Contributor Leaderboard
            </CardTitle>
            <p className="text-xs text-muted-foreground">
              Ranked by total contributions (papers imported + weighted draft edits)
            </p>
          </CardHeader>
          <CardContent className="p-0">
            {contributors.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                No contributions recorded yet
              </div>
            ) : (
              <div className="divide-y divide-border/30">
                {contributors.map((c, i) => (
                  <ContributorRow key={c.user_id} contributor={c} rank={i} maxScore={maxScore} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
