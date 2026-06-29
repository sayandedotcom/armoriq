"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ShieldCheck,
  ShieldAlert,
  Activity,
  FileText,
  MessageSquare,
  Send,
  Check,
  X,
  Shield,
  Plus,
  Trash2,
} from "lucide-react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Rule {
  id: string;
  name: string;
  rule_type: string;
  enabled: boolean;
  priority: number;
  config: Record<string, unknown>;
}

interface Approval {
  id: string;
  tool_call: {
    id: string;
    name: string;
    server_name: string;
    arguments: Record<string, unknown>;
  };
  status: string;
  created_at: string;
  expires_at: string;
}

interface LogEntry {
  id: string;
  conversation_id: string;
  tool_name: string | null;
  tool_arguments: Record<string, unknown> | null;
  decision: string | null;
  rule_id: string | null;
  rule_name: string | null;
  reason: string | null;
  token_used: number;
  timestamp: string;
}

interface ChatMessage {
  role: "user" | "model";
  content: string;
}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<
    "rules" | "approvals" | "logs" | "chat"
  >("rules");
  const [rules, setRules] = useState<Rule[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [conversationId] = useState("default");

  const [newRule, setNewRule] = useState({
    name: "",
    rule_type: "block_tool",
    priority: 0,
    config: {},
  });

  useEffect(() => {
    fetchRules();
    fetchApprovals();
    fetchLogs();
    connectWebSocket();

    const interval = setInterval(() => {
      fetchApprovals();
      fetchLogs();
    }, 5000);

    return () => {
      clearInterval(interval);
      ws?.close();
    };
  }, []);

  const connectWebSocket = useCallback(() => {
    const socket = new WebSocket(WS_URL);

    socket.onopen = () => {
      setConnected(true);
      console.log("WebSocket connected");
    };

    socket.onclose = () => {
      setConnected(false);
      console.log("WebSocket disconnected");
      setTimeout(connectWebSocket, 3000);
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "chat_response") {
          setChatMessages((prev) => [
            ...prev,
            { role: "model", content: data.content },
          ]);
          setChatLoading(false);
        } else if (data.type === "approval_updated") {
          fetchApprovals();
        } else if (
          data.type === "rule_created" ||
          data.type === "rule_updated" ||
          data.type === "rule_deleted"
        ) {
          fetchRules();
        }
      } catch (e) {
        console.error("WebSocket message error:", e);
      }
    };

    setWs(socket);
  }, []);

  const fetchRules = async () => {
    try {
      const res = await fetch(`${API_URL}/rules`);
      const data = await res.json();
      setRules(data.rules || []);
    } catch (e) {
      console.error("Failed to fetch rules:", e);
    }
  };

  const fetchApprovals = async () => {
    try {
      const res = await fetch(`${API_URL}/approvals`);
      const data = await res.json();
      setApprovals(data.approvals || []);
    } catch (e) {
      console.error("Failed to fetch approvals:", e);
    }
  };

  const fetchLogs = async () => {
    try {
      const res = await fetch(`${API_URL}/logs?limit=50`);
      const data = await res.json();
      setLogs(data.logs || []);
    } catch (e) {
      console.error("Failed to fetch logs:", e);
    }
  };

  const createRule = async () => {
    if (!newRule.name) return;
    try {
      await fetch(`${API_URL}/rules`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newRule),
      });
      setNewRule({
        name: "",
        rule_type: "block_tool",
        priority: 0,
        config: {},
      });
      fetchRules();
    } catch (e) {
      console.error("Failed to create rule:", e);
    }
  };

  const toggleRule = async (rule: Rule) => {
    try {
      await fetch(`${API_URL}/rules/${rule.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !rule.enabled }),
      });
      fetchRules();
    } catch (e) {
      console.error("Failed to toggle rule:", e);
    }
  };

  const deleteRule = async (ruleId: string) => {
    try {
      await fetch(`${API_URL}/rules/${ruleId}`, { method: "DELETE" });
      fetchRules();
    } catch (e) {
      console.error("Failed to delete rule:", e);
    }
  };

  const handleApproval = async (
    approvalId: string,
    action: "approve" | "reject",
  ) => {
    try {
      await fetch(`${API_URL}/approvals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approval_id: approvalId, action }),
      });
      fetchApprovals();
    } catch (e) {
      console.error("Failed to handle approval:", e);
    }
  };

  const sendChat = async () => {
    if (!chatInput.trim() || chatLoading) return;

    const userMessage = chatInput;
    setChatMessages((prev) => [
      ...prev,
      { role: "user", content: userMessage },
    ]);
    setChatInput("");
    setChatLoading(true);

    try {
      await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage,
          conversation_id: conversationId,
        }),
      });
    } catch (e) {
      console.error("Failed to send chat:", e);
      setChatLoading(false);
    }
  };

  const navItems: Array<{
    id: "rules" | "approvals" | "logs" | "chat";
    label: string;
    icon: React.ElementType;
    badge?: number;
  }> = [
    { id: "rules", label: "Rules", icon: ShieldCheck },
    { id: "approvals", label: "Approvals", icon: ShieldAlert, badge: approvals.length },
    { id: "logs", label: "Activity", icon: Activity },
    { id: "chat", label: "Chat", icon: MessageSquare },
  ];

  return (
    <div className="min-h-screen flex flex-col font-sans bg-background">
      <header className="sticky top-0 z-50 w-full border-b bg-card">
        <div className="container mx-auto flex h-16 max-w-7xl items-center justify-between px-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary">
              <Shield className="h-5 w-5 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-foreground">
                ArmorIQ
              </h1>
              <p className="text-xs text-muted-foreground font-medium tracking-wide uppercase">
                Agent Control Center
              </p>
            </div>
          </div>
          <nav className="flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <Button
                  key={item.id}
                  variant={isActive ? "secondary" : "ghost"}
                  size="sm"
                  onClick={() => setActiveTab(item.id)}
                  className={`gap-2 ${isActive ? "bg-primary/10 text-primary hover:bg-primary/20" : ""}`}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                  {item.badge !== undefined && (
                    <Badge
                      variant="secondary"
                      className="ml-2 h-5 w-5 rounded-full p-0 flex items-center justify-center bg-amber-500/20 text-amber-500 text-xs"
                    >
                      {item.badge}
                    </Badge>
                  )}
                </Button>
              );
            })}
          </nav>
          <div className="flex items-center gap-3">
            <Badge
              variant={connected ? "outline" : "destructive"}
              className="gap-1.5 px-3 py-1 font-mono uppercase"
            >
              <span className={`relative flex h-2 w-2`}>
                <span
                  className={`relative inline-flex rounded-full h-2 w-2 ${connected ? "bg-emerald-500" : "bg-destructive"}`}
                ></span>
              </span>
              <span>{connected ? "Connected" : "Disconnected"}</span>
            </Badge>
          </div>
        </div>
      </header>

      <main className="flex-1 container max-w-7xl mx-auto px-4 py-8 w-full">
        <Tabs
          value={activeTab}
          className="w-full space-y-8"
        >
          <TabsContent
            value="rules"
            className="space-y-6 m-0 animate-in fade-in slide-in-from-bottom-4 duration-300"
          >
            <div className="grid gap-6 md:grid-cols-[1fr_300px] lg:grid-cols-[1fr_400px]">
              <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-2xl flex items-center gap-2">
                      <ShieldCheck className="h-6 w-6 text-primary" />
                      Active Policies
                    </CardTitle>
                    <CardDescription>
                      Manage and monitor security rules enforced on agents.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-0">
                    {rules.length === 0 ? (
                      <div className="flex flex-col items-center justify-center py-12 text-center">
                        <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mb-4">
                          <FileText className="h-6 w-6 text-muted-foreground" />
                        </div>
                        <h3 className="text-lg font-medium">
                          No rules configured
                        </h3>
                        <p className="text-sm text-muted-foreground mt-1 max-w-sm">
                          Create a rule from the right panel to start securing
                          your agent interactions.
                        </p>
                      </div>
                    ) : (
                      <div className="divide-y">
                        {rules.map((rule) => (
                          <div
                            key={rule.id}
                            className="p-6 flex items-center justify-between hover:bg-muted/50 transition-colors group"
                          >
                            <div className="flex items-center gap-4">
                              <Switch
                                checked={rule.enabled}
                                onCheckedChange={() => toggleRule(rule)}
                              />
                              <div>
                                <h4 className="font-semibold text-foreground tracking-tight">
                                  {rule.name}
                                </h4>
                                <div className="flex items-center gap-2 mt-1">
                                  <Badge
                                    variant="secondary"
                                    className="text-xs font-normal"
                                  >
                                    {rule.rule_type.replace("_", " ")}
                                  </Badge>
                                  <span className="text-xs text-muted-foreground font-medium flex items-center gap-1">
                                    Priority:{" "}
                                    <span className="text-foreground">
                                      {rule.priority}
                                    </span>
                                  </span>
                                </div>
                              </div>
                            </div>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => deleteRule(rule.id)}
                              className="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
              <div>
                <Card className="sticky top-24">
                  <CardHeader className="pb-4 border-b">
                    <CardTitle className="text-lg">Create Rule</CardTitle>
                    <CardDescription>
                      Add a new security constraint.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4 pt-6">
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Rule Name</label>
                      <Input
                        placeholder="e.g. Block File Deletion"
                        value={newRule.name}
                        onChange={(e) =>
                          setNewRule({ ...newRule, name: e.target.value })
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Rule Type</label>
                      <Select
                        value={newRule.rule_type}
                        onValueChange={(val) =>
                          setNewRule({ ...newRule, rule_type: val })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select type" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="block_tool">Block Tool</SelectItem>
                          <SelectItem value="require_approval">
                            Require Approval
                          </SelectItem>
                          <SelectItem value="input_validation">
                            Input Validation
                          </SelectItem>
                          <SelectItem value="token_budget">
                            Token Budget
                          </SelectItem>
                          <SelectItem value="prompt_injection_guard">
                            Prompt Injection Guard
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">
                        Priority (higher = earlier)
                      </label>
                      <Input
                        type="number"
                        placeholder="0"
                        value={newRule.priority}
                        onChange={(e) =>
                          setNewRule({
                            ...newRule,
                            priority: parseInt(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                  </CardContent>
                  <CardFooter className="pt-2">
                    <Button
                      onClick={createRule}
                      className="w-full gap-2"
                      disabled={!newRule.name}
                    >
                      <Plus className="h-4 w-4" /> Add Rule
                    </Button>
                  </CardFooter>
                </Card>
              </div>
            </div>
          </TabsContent>

          <TabsContent
            value="approvals"
            className="m-0 animate-in fade-in slide-in-from-bottom-4 duration-300"
          >
            <Card>
              <CardHeader>
                <CardTitle className="text-2xl flex items-center gap-2 text-amber-500">
                  <ShieldAlert className="h-6 w-6" />
                  Pending Approvals
                </CardTitle>
                <CardDescription>
                  Tool executions requiring human authorization.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0 border-t">
                {approvals.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center mb-4">
                      <ShieldCheck className="h-8 w-8 text-muted-foreground opacity-50" />
                    </div>
                    <h3 className="text-lg font-medium text-foreground">
                      All clear
                    </h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      No pending approvals at the moment.
                    </p>
                  </div>
                ) : (
                  <div className="grid gap-4 p-6">
                    {approvals.map((approval) => (
                      <Card
                        key={approval.id}
                        className="bg-muted/30 border-border overflow-hidden"
                      >
                        <div className="flex flex-col md:flex-row md:items-center justify-between p-5 gap-4">
                          <div className="space-y-1.5 flex-1">
                            <div className="flex items-center gap-2">
                              <h4 className="font-semibold text-lg">
                                {approval.tool_call.name}
                              </h4>
                              <Badge
                                variant="outline"
                                className="bg-background text-xs"
                              >
                                {approval.tool_call.server_name}
                              </Badge>
                            </div>
                            <ScrollArea className="h-24 w-full rounded-md border bg-background p-3">
                              <pre className="text-xs text-muted-foreground font-mono">
                                {JSON.stringify(
                                  approval.tool_call.arguments,
                                  null,
                                  2,
                                )}
                              </pre>
                            </ScrollArea>
                          </div>
                          <div className="flex flex-row md:flex-col gap-3 min-w-[120px]">
                            <Button
                              onClick={() =>
                                handleApproval(approval.id, "approve")
                              }
                              className="flex-1 gap-2 bg-emerald-600 hover:bg-emerald-700 text-white"
                            >
                              <Check className="h-4 w-4" /> Approve
                            </Button>
                            <Button
                              variant="destructive"
                              onClick={() =>
                                handleApproval(approval.id, "reject")
                              }
                              className="flex-1 gap-2"
                            >
                              <X className="h-4 w-4" /> Reject
                            </Button>
                          </div>
                        </div>
                      </Card>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent
            value="logs"
            className="m-0 animate-in fade-in slide-in-from-bottom-4 duration-300"
          >
            <Card>
              <CardHeader>
                <CardTitle className="text-2xl flex items-center gap-2">
                  <Activity className="h-6 w-6 text-primary" />
                  Activity Stream
                </CardTitle>
                <CardDescription>
                  Real-time log of agent decisions and tool executions.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0 border-t">
                <ScrollArea className="h-[600px] w-full">
                  {logs.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-16 text-center">
                      <Activity className="h-12 w-12 text-muted-foreground opacity-20 mb-4" />
                      <p className="text-muted-foreground">
                        No activity recorded yet.
                      </p>
                    </div>
                  ) : (
                    <div className="divide-y">
                      {logs
                        .slice()
                        .reverse()
                        .map((log) => (
                          <div
                            key={log.id}
                            className={`p-4 hover:bg-muted/50 transition-colors flex gap-4 items-start ${
                              log.decision === "deny"
                                ? "log-blocked"
                                : log.decision === "require_approval"
                                  ? "log-pending"
                                  : "log-allowed"
                            }`}
                          >
                            <div className="flex-1 space-y-1">
                              <div className="flex items-center gap-3">
                                <span className="font-semibold text-foreground tracking-tight">
                                  {log.tool_name || "System Event"}
                                </span>
                                <Badge
                                  variant="outline"
                                  className={`text-[10px] uppercase tracking-wider font-bold border-0 ${
                                    log.decision === "deny"
                                      ? "bg-destructive/20 text-destructive-foreground"
                                      : log.decision === "require_approval"
                                        ? "bg-amber-500/20 text-amber-500"
                                        : "bg-emerald-500/20 text-emerald-500"
                                  }`}
                                >
                                  {log.decision || "unknown"}
                                </Badge>
                                <span className="text-xs text-muted-foreground ml-auto font-medium font-mono">
                                  {new Date(log.timestamp).toLocaleTimeString()}
                                </span>
                              </div>

                              {log.reason && (
                                <p className="text-sm text-foreground/80 mt-2">
                                  {log.reason}
                                </p>
                              )}

                              {log.rule_name && (
                                <div className="flex items-center gap-1.5 mt-2 text-xs text-muted-foreground">
                                  <Shield className="h-3 w-3" />
                                  Triggered by:{" "}
                                  <span className="font-semibold">
                                    {log.rule_name}
                                  </span>
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                    </div>
                  )}
                </ScrollArea>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent
            value="chat"
            className="m-0 animate-in fade-in slide-in-from-bottom-4 duration-300"
          >
            <Card className="flex flex-col h-[700px]">
              <CardHeader className="border-b pb-4">
                <CardTitle className="text-2xl flex items-center gap-2">
                  <MessageSquare className="h-6 w-6 text-primary" />
                  Agent Interface
                </CardTitle>
                <CardDescription>
                  Direct interaction with the controlled agent.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex-1 p-0 overflow-hidden relative">
                <ScrollArea className="h-full w-full p-6">
                  <div className="space-y-6 pb-20">
                    {chatMessages.length === 0 && !chatLoading && (
                      <div className="h-full flex flex-col items-center justify-center text-muted-foreground opacity-60 pt-20">
                        <MessageSquare className="h-12 w-12 mb-4" />
                        <p>Start a conversation with the agent</p>
                      </div>
                    )}
                    {chatMessages.map((msg, i) => (
                      <div
                        key={i}
                        className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} animate-in fade-in slide-in-from-bottom-2`}
                      >
                        <div
                          className={`max-w-[80%] rounded-lg px-5 py-3 shadow-sm ${
                            msg.role === "user"
                              ? "bg-primary text-primary-foreground"
                              : "bg-muted text-foreground"
                          }`}
                        >
                          <p className="text-sm leading-relaxed whitespace-pre-wrap">
                            {msg.content}
                          </p>
                        </div>
                      </div>
                    ))}
                    {chatLoading && (
                      <div className="flex justify-start animate-in fade-in">
                        <div className="bg-muted rounded-lg px-5 py-4 shadow-sm flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-primary/60 animate-bounce"></div>
                          <div className="w-2 h-2 rounded-full bg-primary/60 animate-bounce [animation-delay:-.3s]"></div>
                          <div className="w-2 h-2 rounded-full bg-primary/60 animate-bounce [animation-delay:-.5s]"></div>
                        </div>
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </CardContent>
              <CardFooter className="border-t p-4 bg-background">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    sendChat();
                  }}
                  className="flex w-full items-center space-x-2"
                >
                  <Input
                    placeholder="Type a command for the agent..."
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    disabled={chatLoading}
                    className="flex-1 h-12"
                  />
                  <Button
                    type="submit"
                    disabled={chatLoading || !chatInput.trim()}
                    className="h-12 w-12"
                    size="icon"
                  >
                    <Send className="h-5 w-5" />
                  </Button>
                </form>
              </CardFooter>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
