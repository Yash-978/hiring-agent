import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { DecisionDialog } from "@/components/DecisionDialog";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { AnalysisView } from "@/components/AnalysisView";
import { ScoreDisplay } from "@/components/ScoreDisplay";
import {
  AlertCircle,
  CheckCircle,
  Clock,
  User as UserIcon,
  FileText,
  Shield,
  AlertTriangle,
  Briefcase,
  Calendar,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/auth/useAuth";
import {
  apiRequest,
  approveApproval,
  rejectApproval,
  getApprovalCounts,
  type Approval,
} from "@/api/client";

type ApprovalStatus = "pending" | "approved" | "rejected";

function formatDate(dateString?: string | null): string {
  if (!dateString) return "—";
  const date = new Date(dateString);
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.max(0, Math.floor(diffMs / 1000));
  const diffMin = Math.floor(diffSec / 60);
  const diffHours = Math.floor(diffMin / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSec < 60) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return "yesterday";
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

function formatCreatedBy(requestedBy: number, requestedByName?: string | null): string {
  if (requestedByName) return requestedByName;
  return `user #${requestedBy}`;
}

interface ApprovalPayloadView {
  skills?: string[];
  reasoning?: string;
  missing_skills?: string[];
  letter_content?: string;
  salary?: number;
  currency?: string;
  start_date?: string;
}

function getPayloadView(payload: Record<string, unknown> | null): ApprovalPayloadView {
  if (!payload) return {};
  return {
    skills: Array.isArray(payload.skills) ? (payload.skills as string[]) : undefined,
    reasoning: typeof payload.reasoning === "string" ? payload.reasoning : undefined,
    missing_skills: Array.isArray(payload.missing_skills) ? (payload.missing_skills as string[]) : undefined,
    letter_content: typeof payload.letter_content === "string" ? payload.letter_content : undefined,
    salary: typeof payload.salary === "number" ? payload.salary : undefined,
    currency: typeof payload.currency === "string" ? payload.currency : undefined,
    start_date: typeof payload.start_date === "string" ? payload.start_date : undefined,
  };
}

function renderOfferLetterDetails(payload: Record<string, unknown> | null) {
  if (!payload) return null;
  const { letter_content, salary, currency, start_date } = getPayloadView(payload);

  return (
    <div className="space-y-4 rounded-lg border bg-card p-4">
      <h4 className="font-semibold text-sm flex items-center gap-2">
        <FileText className="h-4 w-4" /> Offer Details
      </h4>
      <div className="grid gap-4 sm:grid-cols-2 text-sm">
        <div>
          <Label className="font-medium text-muted-foreground">Offered Salary</Label>
          <p className="text-base font-semibold mt-1">
            {typeof salary === "number" ? salary.toLocaleString() : "—"}
            {currency ? ` ${currency}` : ""}
          </p>
        </div>
        <div>
          <Label className="font-medium text-muted-foreground">Proposed Start Date</Label>
          <p className="text-base font-medium mt-1 flex items-center gap-1.5">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            {start_date ?? "—"}
          </p>
        </div>
      </div>
      {letter_content && (
        <div className="space-y-1.5">
          <Label className="font-medium text-muted-foreground">Drafted Offer Letter</Label>
          <ScrollArea className="h-64 border rounded-md p-3 bg-muted/40">
            <pre className="whitespace-pre-wrap text-xs font-mono leading-relaxed">
              {letter_content}
            </pre>
          </ScrollArea>
        </div>
      )}
    </div>
  );
}

function renderShortlistPayload(payload: Record<string, unknown> | null) {
  if (!payload) return null;
  const { skills, reasoning, missing_skills } = getPayloadView(payload);

  if (!skills && !reasoning && !missing_skills) return null;

  return (
    <div className="space-y-3 rounded-lg border bg-card p-4 text-sm">
      <h4 className="font-semibold text-sm">Shortlist Decision Rationale</h4>
      {skills && skills.length > 0 && (
        <div>
          <Label className="font-medium text-muted-foreground">Matched Skills</Label>
          <div className="flex flex-wrap gap-1.5 mt-1">
            {skills.map((skill) => (
              <Badge key={skill} variant="secondary" className="text-xs">
                {skill}
              </Badge>
            ))}
          </div>
        </div>
      )}
      {reasoning && (
        <div>
          <Label className="font-medium text-muted-foreground">Agent Reasoning</Label>
          <p className="mt-1 text-sm text-foreground/90 whitespace-pre-wrap">{reasoning}</p>
        </div>
      )}
      {missing_skills && missing_skills.length > 0 && (
        <div>
          <Label className="font-medium text-muted-foreground">Missing Criteria</Label>
          <div className="flex flex-wrap gap-1.5 mt-1">
            {missing_skills.map((skill) => (
              <Badge key={skill} variant="destructive" className="text-xs">
                {skill}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function Approvals() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const currentUserRole = user?.role ?? "member";
  const isMember = currentUserRole === "member";

  const [searchParams, setSearchParams] = useSearchParams();
  const statusParam = searchParams.get("status");
  const currentStatus: ApprovalStatus =
    statusParam === "approved" || statusParam === "rejected" || statusParam === "pending"
      ? statusParam
      : "pending";

  const [selectedApprovalId, setSelectedApprovalId] = useState<number | null>(null);
  const [mobileDetailOpen, setMobileDetailOpen] = useState(false);

  const [decisionState, setDecisionState] = useState<{
    open: boolean;
    mode: "approve" | "reject";
  }>({
    open: false,
    mode: "approve",
  });

  const { data: counts } = useQuery({
    queryKey: ["approvals-counts"],
    queryFn: getApprovalCounts,
  });

  const {
    data: approvals,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["approvals", currentStatus],
    queryFn: () => apiRequest<Approval[]>(`/approvals?status=${currentStatus}`),
  });

  // Derive active selection during render: if current selectedId is not in list, auto-select first item
  const activeApprovalId =
    selectedApprovalId && approvals?.some((a) => a.id === selectedApprovalId)
      ? selectedApprovalId
      : approvals?.[0]?.id ?? null;

  const selectedApproval = approvals?.find((a) => a.id === activeApprovalId) ?? null;

  const nextItemToSelect = (decidedId: number) => {
    if (!approvals) return;
    const currentIndex = approvals.findIndex((a) => a.id === decidedId);
    if (currentIndex !== -1) {
      if (currentIndex + 1 < approvals.length) {
        setSelectedApprovalId(approvals[currentIndex + 1].id);
      } else if (currentIndex > 0) {
        setSelectedApprovalId(approvals[currentIndex - 1].id);
      } else {
        setSelectedApprovalId(null);
      }
    }
  };

  const approveMutation = useMutation({
    mutationFn: ({ id, note }: { id: number; note?: string }) => approveApproval(id, note),
    onSuccess: (_, variables) => {
      toast.success("Approved successfully");
      nextItemToSelect(variables.id);
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
      queryClient.invalidateQueries({ queryKey: ["approvals-counts"] });
      queryClient.invalidateQueries({ queryKey: ["application-analysis"] });
      queryClient.invalidateQueries({ queryKey: ["candidates"] });
    },
    onError: (err: Error) => {
      if (err.message.includes("409") || err.message.includes("already decided")) {
        queryClient.invalidateQueries({ queryKey: ["approvals"] });
        queryClient.invalidateQueries({ queryKey: ["approvals-counts"] });
      }
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, note }: { id: number; note: string }) => rejectApproval(id, note),
    onSuccess: (_, variables) => {
      toast.success("Rejected successfully");
      nextItemToSelect(variables.id);
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
      queryClient.invalidateQueries({ queryKey: ["approvals-counts"] });
      queryClient.invalidateQueries({ queryKey: ["application-analysis"] });
      queryClient.invalidateQueries({ queryKey: ["candidates"] });
    },
    onError: (err: Error) => {
      if (err.message.includes("409") || err.message.includes("already decided")) {
        queryClient.invalidateQueries({ queryKey: ["approvals"] });
        queryClient.invalidateQueries({ queryKey: ["approvals-counts"] });
      }
    },
  });

  const handleTabChange = (val: string) => {
    setSearchParams({ status: val });
  };

  const handleDecisionConfirm = async (note?: string) => {
    if (!selectedApproval) return;
    if (decisionState.mode === "approve") {
      await approveMutation.mutateAsync({ id: selectedApproval.id, note });
    } else {
      if (!note || note.trim().length < 3) {
        throw new Error("Rejection reason must be at least 3 characters.");
      }
      await rejectMutation.mutateAsync({ id: selectedApproval.id, note: note.trim() });
    }
  };

  const renderDetailContent = (approval: Approval) => {
    const isPending = approval.status === "pending";
    const isDecided = approval.status === "approved" || approval.status === "rejected";
    const appId =
      approval.application_id ??
      (approval.target_type === "application" ? approval.target_id : undefined);

    return (
      <div className="space-y-6">
        {/* Header Summary */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b pb-4">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-xl font-bold tracking-tight">
                {approval.candidate_name ?? `Candidate #${approval.target_id}`}
              </h2>
              <Badge variant={approval.action_type === "shortlist" ? "default" : "outline"}>
                {approval.action_type.replace("_", " ")}
              </Badge>
              <Badge
                variant={
                  approval.status === "approved"
                    ? "secondary"
                    : approval.status === "rejected"
                    ? "destructive"
                    : "outline"
                }
                className="capitalize"
              >
                {approval.status}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground mt-1 flex items-center gap-1.5">
              <Briefcase className="h-4 w-4" />
              {approval.job_title ?? `Job #${approval.target_id}`}
            </p>
            <div className="mt-2">
              <ScoreDisplay score={approval.score} />
            </div>
          </div>

          <div className="text-xs text-muted-foreground space-y-1">
            <div className="flex items-center gap-1.5">
              <UserIcon className="h-3.5 w-3.5" />
              <span>Requested by: {formatCreatedBy(approval.requested_by, approval.requested_by_name)}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5" />
              <span>Submitted: {formatDate(approval.created_at)}</span>
            </div>
          </div>
        </div>

        {/* Decided banner if decided */}
        {isDecided && (
          <div
            className={`rounded-lg border p-4 ${
              approval.status === "approved"
                ? "border-green-200 bg-green-50/60 text-green-900 dark:bg-green-950/20 dark:border-green-800 dark:text-green-200"
                : "border-red-200 bg-red-50/60 text-red-900 dark:bg-red-950/20 dark:border-red-800 dark:text-red-200"
            }`}
          >
            <div className="flex items-center gap-2 font-semibold text-sm mb-2">
              <CheckCircle className="h-4 w-4" />
              <span className="capitalize">{approval.status} Decision</span>
            </div>
            <div className="grid gap-1.5 text-xs sm:text-sm">
              <div className="flex items-center gap-1.5">
                <UserIcon className="h-3.5 w-3.5" />
                <span>
                  Decided by: {approval.decided_by_user_id ? `user #${approval.decided_by_user_id}` : "Administrator"}
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5" />
                <span>Decided at: {formatDate(approval.decided_at)}</span>
              </div>
              <div className="flex items-start gap-1.5 mt-1">
                <FileText className="h-3.5 w-3.5 mt-0.5" />
                <span>
                  <strong className="font-medium">Note:</strong> {approval.decision_note || "No note provided"}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Shortlist details payload */}
        {approval.action_type === "shortlist" && renderShortlistPayload(approval.payload)}

        {/* Offer letter details */}
        {approval.action_type === "offer_letter" && renderOfferLetterDetails(approval.payload)}

        {/* Full Analysis View */}
        {appId && (
          <div className="space-y-3">
            <h3 className="text-base font-semibold">Candidate Assessment</h3>
            <AnalysisView applicationId={appId} />
          </div>
        )}

        {/* Decision Area (only for pending) */}
        {isPending && (
          <div className="pt-4 border-t">
            {isMember ? (
              <div className="flex items-center gap-2 rounded-md bg-muted p-3 text-sm text-muted-foreground">
                <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                <p>You don't have permission to decide approvals. Contact an admin or approver.</p>
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <Button
                  onClick={() => setDecisionState({ open: true, mode: "approve" })}
                  className="min-w-28"
                  disabled={approveMutation.isPending || rejectMutation.isPending}
                >
                  Approve
                </Button>
                <Button
                  variant="destructive"
                  onClick={() => setDecisionState({ open: true, mode: "reject" })}
                  className="min-w-28"
                  disabled={approveMutation.isPending || rejectMutation.isPending}
                >
                  Reject
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Approvals</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Review and decide pending candidate shortlist and offer letter requests.
        </p>
      </div>

      {/* Tabs directly under header */}
      <Tabs value={currentStatus} onValueChange={handleTabChange} className="w-full">
        <TabsList className="w-full grid grid-cols-3 h-11">
          <TabsTrigger value="pending" className="flex items-center justify-center gap-2">
            <span>Pending</span>
            <Badge variant="secondary" className="px-2 py-0.5 text-xs font-mono">
              {counts?.pending ?? 0}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="approved" className="flex items-center justify-center gap-2">
            <span>Approved</span>
            <Badge variant="secondary" className="px-2 py-0.5 text-xs font-mono">
              {counts?.approved ?? 0}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="rejected" className="flex items-center justify-center gap-2">
            <span>Rejected</span>
            <Badge variant="secondary" className="px-2 py-0.5 text-xs font-mono">
              {counts?.rejected ?? 0}
            </Badge>
          </TabsTrigger>
        </TabsList>
      </Tabs>

      {/* Master-Detail Content */}
      {isLoading ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-5 space-y-3">
            {[1, 2, 3].map((i) => (
              <Card key={i} className="p-4">
                <Skeleton className="h-5 w-40 mb-2" />
                <Skeleton className="h-4 w-28 mb-3" />
                <div className="flex gap-2">
                  <Skeleton className="h-6 w-16" />
                  <Skeleton className="h-6 w-20" />
                </div>
              </Card>
            ))}
          </div>
          <div className="hidden lg:block lg:col-span-7">
            <Card className="p-6">
              <Skeleton className="h-7 w-60 mb-4" />
              <Skeleton className="h-4 w-40 mb-6" />
              <Skeleton className="h-48 w-full" />
            </Card>
          </div>
        </div>
      ) : error ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-3 py-12 text-center text-destructive">
            <AlertCircle className="h-10 w-10" />
            <h3 className="text-lg font-medium">Failed to load approvals</h3>
            <p className="text-sm text-muted-foreground max-w-md">
              {error instanceof Error ? error.message : "An error occurred while fetching approvals."}
            </p>
            <Button onClick={() => refetch()} variant="outline" className="mt-2">
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : !approvals || approvals.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
            {currentStatus === "pending" ? (
              <>
                <CheckCircle className="h-12 w-12 text-green-500 mb-1" />
                <h3 className="text-lg font-medium">You are all caught up</h3>
                <p className="text-sm text-muted-foreground">
                  There are no pending approval requests at the moment.
                </p>
              </>
            ) : (
              <>
                <Shield className="h-12 w-12 text-muted-foreground/40 mb-1" />
                <h3 className="text-lg font-medium">Nothing here yet</h3>
                <p className="text-sm text-muted-foreground">
                  No {currentStatus} approvals found.
                </p>
              </>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Approval Cards */}
          <div className="lg:col-span-5 space-y-3">
            {approvals.map((approval) => {
              const isSelected = approval.id === selectedApprovalId;
              const score = approval.score;

              return (
                <Card
                  key={approval.id}
                  tabIndex={0}
                  role="button"
                  aria-pressed={isSelected}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelectedApprovalId(approval.id);
                      setMobileDetailOpen(true);
                    }
                  }}
                  onClick={() => {
                    setSelectedApprovalId(approval.id);
                    setMobileDetailOpen(true);
                  }}
                  className={`p-4 cursor-pointer transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                    isSelected
                      ? "border-primary bg-primary/5 shadow-sm"
                      : "hover:border-foreground/30 hover:bg-muted/40"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <h3 className="font-semibold text-base truncate">
                        {approval.candidate_name ?? `Candidate #${approval.target_id}`}
                      </h3>
                      <p className="text-xs text-muted-foreground truncate mt-0.5">
                        {approval.job_title ?? `Job #${approval.target_id}`}
                      </p>
                    </div>
                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                      {formatRelativeTime(approval.created_at)}
                    </span>
                  </div>

                  <div className="mt-3 flex items-center gap-2 flex-wrap">
                    <Badge variant={approval.action_type === "shortlist" ? "default" : "outline"} className="text-xs">
                      {approval.action_type.replace("_", " ")}
                    </Badge>
                    <ScoreDisplay score={score} />
                  </div>
                </Card>
              );
            })}
          </div>

          {/* Right Column: Desktop Detail Panel */}
          <div className="hidden lg:block lg:col-span-7">
            {selectedApproval ? (
              <Card className="p-6">{renderDetailContent(selectedApproval)}</Card>
            ) : (
              <Card className="p-12 text-center text-muted-foreground">
                <p>Select an approval from the list to view details.</p>
              </Card>
            )}
          </div>
        </div>
      )}

      {/* Mobile Detail Dialog (Screen < lg) */}
      <Dialog open={mobileDetailOpen} onOpenChange={setMobileDetailOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Approval Details</DialogTitle>
          </DialogHeader>
          {selectedApproval && renderDetailContent(selectedApproval)}
        </DialogContent>
      </Dialog>

      {/* Reusable Decision Dialog */}
      {selectedApproval && (
        <DecisionDialog
          open={decisionState.open}
          onOpenChange={(open) => setDecisionState((prev) => ({ ...prev, open }))}
          mode={decisionState.mode}
          targetType={selectedApproval.action_type}
          onConfirm={handleDecisionConfirm}
        />
      )}
    </div>
  );
}