import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import api from "@/lib/api";
import { getUserColor } from "@/lib/colors";
import { useAuth } from "@/contexts/AuthContext";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    UserPlus,
    Users,
    Trash2,
    Link,
    Copy,
    Check,
    Crown,
    Shield,
    User as UserIcon,
    Loader2,
} from "lucide-react";
import { toast } from "sonner";

interface Member {
    user_id: string;
    email: string;
    full_name: string;
    role: string;
    joined_at: string;
}

export function WorkspaceMembersPage() {
    const { workspaceId } = useParams();
    const { user } = useAuth();
    const [members, setMembers] = useState<Member[]>([]);
    const [loading, setLoading] = useState(true);
    const [inviteEmail, setInviteEmail] = useState("");
    const [inviteRole, setInviteRole] = useState("viewer");
    const [inviting, setInviting] = useState(false);
    const [inviteLink, setInviteLink] = useState<string | null>(null);
    const [linkCopied, setLinkCopied] = useState(false);
    const [generatingLink, setGeneratingLink] = useState(false);

    useEffect(() => {
        if (workspaceId) loadMembers();
    }, [workspaceId]);

    const loadMembers = async () => {
        try {
            const res = await api.get(`/workspaces/${workspaceId}/members`);
            setMembers(res.data.members || []);
        } catch {
            toast.error("Failed to load members");
        } finally {
            setLoading(false);
        }
    };

    const inviteMember = async () => {
        if (!inviteEmail.trim()) return;
        setInviting(true);
        try {
            await api.post(`/workspaces/${workspaceId}/invite`, {
                email: inviteEmail.trim(),
                role: inviteRole,
            });
            toast.success(`Invited ${inviteEmail}`);
            setInviteEmail("");
            loadMembers();
        } catch (err: any) {
            toast.error(err.response?.data?.detail || "Failed to invite member");
        } finally {
            setInviting(false);
        }
    };

    const generateInviteLink = async () => {
        setGeneratingLink(true);
        try {
            const res = await api.post(`/workspaces/${workspaceId}/invite-link`, {
                role: inviteRole,
                expires_hours: 48,
            });
            const token = res.data.invite_token;
            const link = `${window.location.origin}/join/${token}`;
            setInviteLink(link);
        } catch {
            toast.error("Failed to generate invite link");
        } finally {
            setGeneratingLink(false);
        }
    };

    const copyLink = () => {
        if (inviteLink) {
            navigator.clipboard.writeText(inviteLink);
            setLinkCopied(true);
            toast.success("Link copied!");
            setTimeout(() => setLinkCopied(false), 2000);
        }
    };

    const removeMember = async (userId: string, email: string) => {
        if (!confirm(`Remove ${email} from workspace?`)) return;
        try {
            await api.delete(`/workspaces/${workspaceId}/members/${userId}`);
            toast.success(`Removed ${email}`);
            setMembers((prev) => prev.filter((m) => m.user_id !== userId));
        } catch (err: any) {
            toast.error(err.response?.data?.detail || "Failed to remove member");
        }
    };

    const roleIcon = (role: string) => {
        if (role === "owner") return <Crown className="w-3.5 h-3.5 text-amber-500" />;
        if (role === "editor") return <Shield className="w-3.5 h-3.5 text-blue-500" />;
        return <UserIcon className="w-3.5 h-3.5 text-muted-foreground" />;
    };

    const roleBadgeVariant = (role: string) => {
        if (role === "owner") return "default" as const;
        if (role === "editor") return "secondary" as const;
        return "outline" as const;
    };

    return (
        <div className="p-6 max-w-2xl mx-auto space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
                    <Users className="w-6 h-6" />
                    Team Members
                </h1>
                <p className="text-muted-foreground text-sm mt-1">
                    Manage who has access to this workspace
                </p>
            </div>

            {/* Invite by Email */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                        <UserPlus className="w-4 h-4" />
                        Invite Members
                    </CardTitle>
                    <CardDescription>Add collaborators by email address</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex gap-2">
                        <Input
                            placeholder="colleague@university.edu"
                            type="email"
                            value={inviteEmail}
                            onChange={(e) => setInviteEmail(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && inviteMember()}
                            className="flex-1"
                        />
                        <Select value={inviteRole} onValueChange={setInviteRole}>
                            <SelectTrigger className="w-28">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="viewer">Viewer</SelectItem>
                                <SelectItem value="editor">Editor</SelectItem>
                            </SelectContent>
                        </Select>
                        <Button onClick={inviteMember} disabled={inviting || !inviteEmail.trim()}>
                            {inviting ? <Loader2 className="w-4 h-4 animate-spin" /> : "Invite"}
                        </Button>
                    </div>

                    <Separator />

                    {/* Invite Link */}
                    <div>
                        <p className="text-sm text-muted-foreground mb-2">Or share an invite link</p>
                        <div className="flex gap-2">
                            <Button
                                variant="outline"
                                onClick={generateInviteLink}
                                disabled={generatingLink}
                                className="gap-2"
                            >
                                {generatingLink ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                    <Link className="w-4 h-4" />
                                )}
                                Generate Link
                            </Button>
                            {inviteLink && (
                                <div className="flex-1 flex gap-2">
                                    <Input value={inviteLink} readOnly className="text-xs" />
                                    <Button size="icon" variant="outline" onClick={copyLink}>
                                        {linkCopied ? (
                                            <Check className="w-4 h-4 text-green-500" />
                                        ) : (
                                            <Copy className="w-4 h-4" />
                                        )}
                                    </Button>
                                </div>
                            )}
                        </div>
                        {inviteLink && (
                            <p className="text-xs text-muted-foreground mt-1">
                                Expires in 48 hours • Role: {inviteRole}
                            </p>
                        )}
                    </div>
                </CardContent>
            </Card>

            {/* Members List */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                        <Users className="w-4 h-4" />
                        Members
                        <Badge variant="secondary" className="ml-auto text-xs">
                            {members.length}
                        </Badge>
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {loading ? (
                        <div className="flex items-center justify-center py-8">
                            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                        </div>
                    ) : members.length === 0 ? (
                        <p className="text-sm text-muted-foreground text-center py-8">
                            No members yet. Invite someone above!
                        </p>
                    ) : (
                        <div className="space-y-1">
                            {members.map((member, i) => (
                                <div key={member.user_id}>
                                    {i > 0 && <Separator className="my-2" />}
                                    <div className="flex items-center justify-between py-2">
                                        <div className="flex items-center gap-3">
                                            <div className={`w-9 h-9 rounded-full flex items-center justify-center ${getUserColor(member.user_id).bg}`}>
                                                <span className={`text-sm font-medium ${getUserColor(member.user_id).text}`}>
                                                    {member.full_name?.charAt(0)?.toUpperCase() || "?"}
                                                </span>
                                            </div>
                                            <div>
                                                <p className="text-sm font-medium text-foreground">
                                                    {member.full_name}
                                                    {member.user_id === user?.id && (
                                                        <span className="text-muted-foreground ml-1">(you)</span>
                                                    )}
                                                </p>
                                                <p className="text-xs text-muted-foreground">{member.email}</p>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Badge variant={roleBadgeVariant(member.role)} className="gap-1 text-xs capitalize">
                                                {roleIcon(member.role)}
                                                {member.role}
                                            </Badge>
                                            {member.role !== "owner" && member.user_id !== user?.id && (
                                                <Button
                                                    size="icon"
                                                    variant="ghost"
                                                    className="h-8 w-8 text-muted-foreground hover:text-destructive"
                                                    onClick={() => removeMember(member.user_id, member.email)}
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
