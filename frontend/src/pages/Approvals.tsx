import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription, DialogClose } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { AnalysisView } from "@/components/AnalysisView";
import { Loader2, AlertCircle, CheckCircle, Clock, User as UserIcon, FileText, Shield, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/auth/useAuth";
import { apiRequest, approveApproval, rejectApproval, type Approval } from "@/api/client";

type ApprovalStatus = "pending" | "approved" | "rejected";

const statusColors: Record<ApprovalStatus, "default" | "secondary" | "destructive" | "outline"> = {
  pending: "default",
  approved: "secondary",
  rejected: "destructive",
};

const actionTypeColors: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  shortlist: "default",
  offer_letter: "outline",
};

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatCreatedBy(requestedBy: number): string {
  return `user #${requestedBy}`;
}

function getPayloadSummary(payload: Record<string, unknown> | null): string {
  if (!payload) return "No details available";
  return JSON.stringify(payload, null, 2);
}

interface ApprovalPayloadView {
  skills?: string[];
  reasoning?: string;
  missing_skills?: string[];
  letter_content?: string;
}

function getPayloadView(payload: Record<string, unknown> | null): ApprovalPayloadView {
  if (!payload) return {};
  return {
    skills: Array.isArray(payload.skills) ? (payload.skills as string[]) : undefined,
    reasoning: typeof payload.reasoning === "string" ? payload.reasoning : undefined,
    missing_skills: Array.isArray(payload.missing_skills) ? (payload.missing_skills as string[]) : undefined,
    letter_content: typeof payload.letter_content === "string" ? payload.letter_content : undefined,
  };
}

function renderShortlistDetails(payload: Record<string, unknown> | null) {
  if (!payload) return <p className="text-muted-foreground text-sm">No details available</p>;

  const { skills, reasoning, missing_skills: missingSkills } = getPayloadView(payload);

  return (
    <div className="space-y-3 text-sm">
      <div>
        <Label className="font-medium text-muted-foreground">Score</Label>
        <p className="text-lg font-semibold mt-1">
          {typeof payload.score === "number" ? payload.score.toFixed(1) : "—"} / 10
        </p>
      </div>
      {skills && (
        <div>
          <Label className="font-medium text-muted-foreground">Matched Skills</Label>
          <div className="flex flex-wrap gap-1 mt-1">
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
          <Label className="font-medium text-muted-foreground">Reasoning</Label>
          <p className="mt-1 whitespace-pre-wrap">{reasoning}</p>
        </div>
      )}
      {missingSkills && missingSkills.length > 0 && (
        <div>
          <Label className="font-medium text-muted-foreground">Missing Skills</Label>
          <div className="flex flex-wrap gap-1 mt-1">
            {missingSkills.map((skill) => (
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

function renderOfferLetterDetails(payload: Record<string, unknown> | null) {
  if (!payload) return <p className="text-muted-foreground text-sm">No details available</p>;

  const { letter_content: letterContent } = getPayloadView(payload);

  return (
    <div className="space-y-3 text-sm">
      <div className="grid gap-2 sm:grid-cols-2">
        <div>
          <Label className="font-medium text-muted-foreground">Salary</Label>
          <p className="text-lg font-semibold mt-1">
            {typeof payload.salary === "number" ? payload.salary.toLocaleString() : "—"}
            {payload.currency ? ` ${payload.currency}` : ""}
          </p>
        </div>
        <div>
          <Label className="font-medium text-muted-foreground">Start Date</Label>
          <p className="mt-1">{payload.start_date as string ?? "—"}</p>
        </div>
      </div>
      {letterContent && (
        <div>
          <Label className="font-medium text-muted-foreground">Letter Content</Label>
          <ScrollArea className="mt-1 h-64 border rounded-md p-3 bg-muted/50">
            <pre className="whitespace-pre-wrap text-sm font-mono">
              {letterContent}
            </pre>
          </ScrollArea>
        </div>
      )}
    </div>
  );
}

function ApprovalCard({
  approval,
  onApprove,
  onReject,
  isApproving,
  isRejecting,
  currentUserRole,
}: {
  approval: Approval;
  onApprove: (note?: string) => void;
  onReject: (note: string) => void;
  isApproving: boolean;
  isRejecting: boolean;
  currentUserRole: string;
}) {
  const isPending = approval.status === "pending";
  const isDecided = approval.status === "approved" || approval.status === "rejected";
  const isMember = currentUserRole === "member";

  return (
    <Card className="overflow-hidden transition-shadow hover:shadow-md">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <Badge variant={actionTypeColors[approval.action_type] ?? "default"}>
                {approval.action_type.replace("_", " ")}
              </Badge>
              <Badge variant={statusColors[approval.status as ApprovalStatus] ?? "outline"} className="capitalize">
                {approval.status}
              </Badge>
            </div>
            <div className="mt-2 flex items-center gap-4 text-sm text-muted-foreground flex-wrap">
              <span className="flex items-center gap-1">
                <UserIcon className="h-3.5 w-3.5" />
                Requested by: {formatCreatedBy(approval.requested_by)}
              </span>
              <span className="flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                Created: {formatDate(approval.created_at)}
              </span>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label className="font-medium text-muted-foreground">Candidate</Label>
            <p className="font-medium mt-1">
              {approval.payload?.candidate_name as string ?? `Candidate #${approval.target_id}`}
            </p>
          </div>
          <div>
            <Label className="font-medium text-muted-foreground">Job</Label>
            <p className="font-medium mt-1">
              {approval.payload?.job_title as string ?? `Job #${approval.target_id}`}
            </p>
          </div>
        </div>

        <div className="border-t pt-4">
          <Label className="font-medium text-muted-foreground">Details</Label>
          {approval.action_type === "shortlist" ? (
            <>
              <AnalysisView applicationId={approval.target_id} />
              <div className="mt-4">{renderShortlistDetails(approval.payload)}</div>
            </>
          ) : approval.action_type === "offer_letter" ? (
            renderOfferLetterDetails(approval.payload)
          ) : (
            <pre className="mt-1 p-3 bg-muted rounded-md text-xs overflow-auto max-h-64">
              {getPayloadSummary(approval.payload)}
            </pre>
          )}
        </div>

        {isDecided && approval.decided_by_user_id && approval.decided_at && (
          <div className="border-t pt-4 bg-green-50/50 rounded-md p-3">
            <div className="flex items-center gap-2 text-sm text-green-800 mb-2">
              <CheckCircle className="h-4 w-4" />
              <span className="font-medium capitalize">{approval.status}</span>
            </div>
            <div className="grid gap-1 text-sm text-green-700 ml-6">
              <div className="flex items-center gap-1">
                <UserIcon className="h-3.5 w-3.5" />
                Decided by: user #{approval.decided_by_user_id}
              </div>
              <div className="flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                At: {formatDate(approval.decided_at)}
              </div>
              {approval.decision_note && (
                <div className="flex items-center gap-1">
                  <FileText className="h-3.5 w-3.5" />
                  Note: {approval.decision_note}
                </div>
              )}
            </div>
          </div>
        )}

        {isPending && !isMember && (
          <div className="flex items-center gap-2 border-t pt-4">
            <Dialog>
              <DialogTrigger asChild>
                <Button
                  onClick={() => onApprove()}
                  disabled={isApproving || isRejecting}
                  className="flex-1 sm:flex-none"
                >
                  {isApproving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Approve
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Approve this request?</DialogTitle>
                  <DialogDescription>
                    This will approve the {approval.action_type.replace("_", " ")} request. You can add an optional note.
                  </DialogDescription>
                </DialogHeader>
                <ApproveDialogContent
                  onConfirm={(note) => onApprove(note)}
                  isLoading={isApproving}
                />
              </DialogContent>
            </Dialog>

            <Dialog>
              <DialogTrigger asChild>
                <Button
                  variant="destructive"
                  disabled={isApproving || isRejecting}
                  className="flex-1 sm:flex-none"
                >
                  {isRejecting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Reject
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Reject this request?</DialogTitle>
                  <DialogDescription>
                    This will reject the {approval.action_type.replace("_", " ")} request. A note is required.
                  </DialogDescription>
                </DialogHeader>
                <RejectDialogContent
                  onConfirm={(note) => onReject(note)}
                  isLoading={isRejecting}
                />
              </DialogContent>
            </Dialog>
          </div>
        )}

        {isPending && isMember && (
          <div className="flex items-center gap-2 border-t pt-4">
            <AlertTriangle className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            <p className="text-sm text-muted-foreground flex-1">
              You don't have permission to decide approvals. Contact an admin or approver.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ApproveDialogContent({ onConfirm, isLoading }: { onConfirm: (note?: string) => void; isLoading: boolean }) {
  const [note, setNote] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onConfirm(note.trim() || undefined);
  };

  return (
    <form onSubmit={handleSubmit}>
      <DialogContent className="sm:max-w-[500px]">
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="approve-note">Note (optional)</Label>
            <Textarea
              id="approve-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Add a note for the approval..."
              rows={3}
              disabled={isLoading}
            />
          </div>
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={isLoading}>
              Cancel
            </Button>
          </DialogClose>
          <Button type="submit" disabled={isLoading}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Approve
          </Button>
        </DialogFooter>
      </DialogContent>
    </form>
  );
}

function RejectDialogContent({ onConfirm, isLoading }: { onConfirm: (note: string) => void; isLoading: boolean }) {
  const [note, setNote] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!note.trim()) return;
    onConfirm(note.trim());
  };

  return (
    <form onSubmit={handleSubmit}>
      <DialogContent className="sm:max-w-[500px]">
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="reject-note">Note (required)</Label>
            <Textarea
              id="reject-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Explain why you're rejecting this request..."
              rows={3}
              disabled={isLoading}
              required
            />
          </div>
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={isLoading}>
              Cancel
            </Button>
          </DialogClose>
          <Button type="submit" variant="destructive" disabled={isLoading || !note.trim()}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Reject
          </Button>
        </DialogFooter>
      </DialogContent>
    </form>
  );
}

function ApprovalsList({ status, currentUserRole }: { status: ApprovalStatus; currentUserRole: string }) {
  const queryClient = useQueryClient();

  const { data: approvals, isLoading, error } = useQuery({
    queryKey: ["approvals", status],
    queryFn: () => apiRequest<Approval[]>(`/approvals?status=${status}`),
  });

  const approveMutation = useMutation({
    mutationFn: ({ id, note }: { id: number; note?: string }) => approveApproval(id, note),
    onSuccess: () => {
      toast.success("Approved successfully");
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
    },
    onError: (err: Error) => {
      if (err.message.includes("409") || err.message.includes("already decided")) {
        toast.error("This approval has already been decided. Refreshing...");
        queryClient.invalidateQueries({ queryKey: ["approvals"] });
      } else {
        toast.error(err.message);
      }
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, note }: { id: number; note: string }) => rejectApproval(id, note),
    onSuccess: () => {
      toast.success("Rejected successfully");
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
    },
    onError: (err: Error) => {
      if (err.message.includes("409") || err.message.includes("already decided")) {
        toast.error("This approval has already been decided. Refreshing...");
        queryClient.invalidateQueries({ queryKey: ["approvals"] });
      } else {
        toast.error(err.message);
      }
    },
  });

  const handleApprove = (id: number, note?: string) => {
    approveMutation.mutate({ id, note });
  };

  const handleReject = (id: number, note: string) => {
    rejectMutation.mutate({ id, note });
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <Card key={i} className="animate-pulse">
            <CardHeader>
              <div className="h-4 w-24 bg-muted rounded" />
            </CardHeader>
            <CardContent>
              <div className="h-4 w-3/4 bg-muted rounded mb-2" />
              <div className="h-4 w-1/2 bg-muted rounded" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="text-center py-8 text-destructive">
          <AlertCircle className="h-8 w-8 mx-auto mb-2" />
          <p>Failed to load approvals</p>
          <p className="text-sm text-muted-foreground mt-1">{error instanceof Error ? error.message : "Unknown error"}</p>
          <Button onClick={() => queryClient.invalidateQueries({ queryKey: ["approvals", status] })} className="mt-4">
            Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!approvals?.length) {
    return (
      <Card>
        <CardContent className="text-center py-12">
          <Shield className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
          <h3 className="text-lg font-medium mb-2">No {status} approvals</h3>
          <p className="text-muted-foreground">There are no {status} approval requests at the moment.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {approvals?.map((approval) => (
        <ApprovalCard
          key={approval.id}
          approval={approval}
          onApprove={(note) => handleApprove(approval.id, note)}
          onReject={(note) => handleReject(approval.id, note)}
          isApproving={approveMutation.isPending && approveMutation.variables?.id === approval.id}
          isRejecting={rejectMutation.isPending && rejectMutation.variables?.id === approval.id}
          currentUserRole={currentUserRole}
        />
      ))}
    </div>
  );
}

export function Approvals() {
  const { user } = useAuth();
  const currentUserRole = user?.role ?? "member";

  return (
    <div className="p-6 space-y-6">
      <CardHeader>
        <CardTitle>Approvals</CardTitle>
      </CardHeader>

      <Tabs defaultValue="pending" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="pending">Pending</TabsTrigger>
          <TabsTrigger value="approved">Approved</TabsTrigger>
          <TabsTrigger value="rejected">Rejected</TabsTrigger>
        </TabsList>

        <TabsContent value="pending" className="mt-4">
          <ApprovalsList status="pending" currentUserRole={currentUserRole} />
        </TabsContent>

        <TabsContent value="approved" className="mt-4">
          <ApprovalsList status="approved" currentUserRole={currentUserRole} />
        </TabsContent>

        <TabsContent value="rejected" className="mt-4">
          <ApprovalsList status="rejected" currentUserRole={currentUserRole} />
        </TabsContent>
      </Tabs>
    </div>
  );
}