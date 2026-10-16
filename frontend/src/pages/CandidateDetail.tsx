import { useParams } from "react-router-dom";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { ArrowLeft, Brain, Shield, User, FileText, AlertTriangle, CheckCircle, XCircle, Download, Loader2, AlertCircle, FileCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { apiRequest, getApplicationAudit, createOfferDraft, downloadLetter, type Application, type Approval, type AuditLogRead, type Letter } from "@/api/client";
import { AnalysisView } from "@/components/AnalysisView";
import { ResumePanel } from "@/components/ResumePanel";

const statusColors: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  new: "default",
  analyzed: "secondary",
  "shortlist pending": "secondary",
  shortlisted: "secondary",
  rejected: "destructive",
  "offer pending": "outline",
  "offer drafted": "outline",
  hired: "secondary",
};

const actorTypeBadge: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }> = {
  agent: { variant: "default", icon: <Brain className="h-3 w-3" /> },
  user: { variant: "secondary", icon: <User className="h-3 w-3" /> },
  system: { variant: "outline", icon: <Shield className="h-3 w-3" /> },
};

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant={statusColors[status] ?? "outline"} className="capitalize">
      {status}
    </Badge>
  );
}

function AuditTimeline({ auditLogs }: { auditLogs: AuditLogRead[] }) {
  if (!auditLogs.length) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          No audit events recorded for this application.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          Audit Timeline
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[400px]">
          <div className="space-y-4">
            {auditLogs.map((log, index) => {
              const badgeConfig = actorTypeBadge[log.actor_type] ?? { variant: "outline" as const, icon: <AlertTriangle className="h-3 w-3" /> };
              const isLast = index === auditLogs.length - 1;

              return (
                <div key={log.id} className="relative flex gap-4">
                  <div className="flex flex-col items-center flex-shrink-0">
                    <div
                      className={`relative flex items-center justify-center w-8 h-8 rounded-full border-2 ${
                        log.actor_type === "agent"
                          ? "border-primary bg-primary/10"
                          : log.actor_type === "user"
                          ? "border-secondary bg-secondary/10"
                          : "border-muted bg-muted/50"
                      }`}
                    >
                      {badgeConfig.icon}
                    </div>
                    {!isLast && (
                      <div className="absolute top-8 bottom-0 left-3 w-0.5 bg-border" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0 pt-1 pb-4">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant={badgeConfig.variant} className="gap-1">
                        {badgeConfig.icon}
                        {log.actor_type.charAt(0).toUpperCase() + log.actor_type.slice(1)}
                      </Badge>
                      <span className="text-sm text-muted-foreground">{log.actor_name}</span>
                    </div>
                    <div className="flex items-center gap-3 text-sm text-muted-foreground mb-2">
                      <span className="font-medium capitalize">{log.action.replace(/_/g, " ")}</span>
                      <span>on</span>
                      <span>{log.entity_type} #{log.entity_id}</span>
                    </div>
                    <div className="text-xs text-muted-foreground mb-2">
                      {formatDate(log.created_at)}
                    </div>
                    {log.details && Object.keys(log.details).length > 0 && (
                      <div className="bg-muted/50 rounded-md p-3 text-xs overflow-auto max-h-48">
                        <pre className="font-mono whitespace-pre-wrap">
                          {JSON.stringify(log.details, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

function ApprovalsSection({ approvals, applicationId }: { approvals: Approval[]; applicationId: number }) {
  const appApprovals = approvals.filter(a => a.target_type === "application" && a.target_id === applicationId);

  if (!appApprovals.length) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          No approvals for this application yet.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield className="h-5 w-5" />
          Approvals
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {appApprovals.map((approval) => (
            <div key={approval.id} className="border rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge variant="outline">{approval.action_type.replace("_", " ")}</Badge>
                  <Badge variant={
                    approval.status === "approved" ? "secondary" :
                    approval.status === "rejected" ? "destructive" :
                    "default"
                  } className="capitalize">
                    {approval.status}
                  </Badge>
                </div>
                <span className="text-sm text-muted-foreground">
                  Requested by: user #{approval.requested_by}
                </span>
              </div>

              <div className="grid gap-2 sm:grid-cols-2 text-sm">
                <div>
                  <span className="font-medium text-muted-foreground">Created: </span>
                  {formatDate(approval.created_at)}
                </div>
                {approval.decided_at && (
                  <div>
                    <span className="font-medium text-muted-foreground">Decided: </span>
                    {formatDate(approval.decided_at)}
                  </div>
                )}
                {approval.decided_by_user_id && (
                  <div>
                    <span className="font-medium text-muted-foreground">Decided by: </span>
                    user #{approval.decided_by_user_id}
                  </div>
                )}
                {approval.decision_note && (
                  <div className="sm:col-span-2">
                    <span className="font-medium text-muted-foreground">Note: </span>
                    {approval.decision_note}
                  </div>
                )}
              </div>

              {approval.payload && Object.keys(approval.payload).length > 0 && (
                <div className="border-t pt-3">
                  <span className="font-medium text-muted-foreground text-sm">Payload:</span>
                  <pre className="mt-1 p-2 bg-muted rounded-md text-xs overflow-auto max-h-48">
                    {JSON.stringify(approval.payload, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function OfferSection({
  application,
  approvals,
  onEditOffer,
}: {
  application: Application;
  approvals: Approval[];
  onEditOffer: () => void;
}) {
  // Find shortlist approval
  const shortlistApproval = approvals.find(
    a => a.target_type === "application" && a.target_id === application.id && a.action_type === "shortlist"
  );

  // Find offer approval
  const offerApproval = approvals.find(
    a => a.target_type === "letter" && a.action_type === "offer_letter"
  );

  // Find letter
  const letter = approvals.find(a => a.target_type === "letter" && a.action_type === "offer_letter")?.payload as Letter | undefined;

  const isShortlistApproved = shortlistApproval?.status === "approved";
  const isOfferPending = offerApproval?.status === "pending";
  const isOfferApproved = offerApproval?.status === "approved";
  const isOfferRejected = offerApproval?.status === "rejected";

  const handleDownload = async () => {
    if (!letter?.id) return;
    try {
      const blob = await downloadLetter(letter.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `offer_letter_${letter.id}.docx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success("Letter downloaded");
    } catch (err) {
      if (err instanceof Error) {
        if (err.message.includes("403") || err.message.includes("not approved")) {
          toast.error("Offer approval must be approved before downloading.");
        } else if (err.message.includes("404") || err.message.includes("not generated")) {
          toast.error("Letter not generated yet. Please wait for approval.");
        } else {
          toast.error(err.message);
        }
      } else {
        toast.error("Failed to download letter");
      }
    }
  };

  if (!isShortlistApproved) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Create Offer
          </CardTitle>
        </CardHeader>
        <CardContent className="text-center py-8">
          <AlertCircle className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
          <h3 className="text-lg font-medium mb-2">Awaiting Shortlist Approval</h3>
          <p className="text-muted-foreground mb-4">
            The shortlist approval must be approved before you can create an offer.
          </p>
          <Badge variant="default" className="capitalize">
            {shortlistApproval?.status ?? "pending"}
          </Badge>
        </CardContent>
      </Card>
    );
  }

  // Shortlist approved - show offer form or letter
  if (isOfferPending) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileCheck className="h-5 w-5" />
            Offer Draft Created
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <Badge variant="outline">Awaiting Approval</Badge>
            <Badge variant="outline" className="capitalize">Offer pending</Badge>
          </div>
          <p className="text-muted-foreground">
            The offer draft has been created and is awaiting approval.
          </p>
          {letter && (
            <div className="border rounded-md p-4 bg-muted/50 max-h-64 overflow-auto">
              <label className="font-medium text-sm text-muted-foreground mb-2 block">Draft Letter Content</label>
              <pre className="whitespace-pre-wrap text-sm font-mono">
                {letter.content}
              </pre>
            </div>
          )}
          <div className="flex gap-2">
            <Button variant="outline" asChild>
              <Link to="/approvals">
                <FileCheck className="h-4 w-4 mr-2" />
                View in Approvals
              </Link>
            </Button>
            <Button variant="outline" onClick={onEditOffer}>
              Edit Offer
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isOfferApproved) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CheckCircle className="h-5 w-5 text-green-600" />
            Offer Approved
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="capitalize">Approved</Badge>
          </div>
          <p className="text-muted-foreground">
            The offer has been approved. You can now download the offer letter.
          </p>
          {letter && (
            <div className="border rounded-md p-4 bg-muted/50 max-h-64 overflow-auto">
              <label className="font-medium text-sm text-muted-foreground mb-2 block">Offer Letter Content</label>
              <pre className="whitespace-pre-wrap text-sm font-mono">
                {letter.content}
              </pre>
            </div>
          )}
          {letter && (
            <Button onClick={handleDownload} className="w-full sm:w-auto">
              <Download className="h-4 w-4 mr-2" />
              Download Letter (.docx)
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  if (isOfferRejected) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <XCircle className="h-5 w-5 text-destructive" />
            Offer Rejected
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2">
            <Badge variant="destructive" className="capitalize">Rejected</Badge>
          </div>
          <p className="text-muted-foreground">
            The offer was rejected. You can create a new offer draft.
          </p>
          {offerApproval?.decision_note && (
            <div className="bg-destructive/10 border border-destructive/20 rounded-md p-3">
              <span className="font-medium text-sm text-destructive">Rejection reason: </span>
              {offerApproval.decision_note}
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  // No offer yet - show create button
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          Create Offer
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-muted-foreground">
          Shortlist approved. Create an offer draft for this candidate.
        </p>
      </CardContent>
    </Card>
  );
}

export function CandidateDetail() {
  const { id } = useParams<{ id: string }>();
  const applicationId = Number(id);
  const queryClient = useQueryClient();

  const { data: application, isLoading: appLoading, error: appError } = useQuery({
    queryKey: ["application", applicationId],
    queryFn: () => apiRequest<Application>(`/applications/${applicationId}`),
    enabled: !isNaN(applicationId),
  });

  const { data: approvals } = useQuery({
    queryKey: ["approvals"],
    queryFn: () => apiRequest<Approval[]>("/approvals"),
    enabled: !isNaN(applicationId),
  });

  const { data: auditLogs } = useQuery({
    queryKey: ["application-audit", applicationId],
    queryFn: () => getApplicationAudit(applicationId),
    enabled: !isNaN(applicationId),
  });

  const [showOfferForm, setShowOfferForm] = useState(false);
  const [salary, setSalary] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [startDate, setStartDate] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleOfferCreated = () => {
    queryClient.invalidateQueries({ queryKey: ["approvals"] });
    queryClient.invalidateQueries({ queryKey: ["application", applicationId] });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!salary || !startDate || !application) return;
    setIsSubmitting(true);
    try {
      await createOfferDraft(application.id, {
        salary: parseFloat(salary),
        currency,
        start_date: startDate,
      });
      toast.success("Offer draft created");
      handleOfferCreated();
      setShowOfferForm(false);
      setSalary("");
      setStartDate("");
    } catch (err) {
      if (err instanceof Error) {
        if (err.message.includes("403") || err.message.includes("Shortlist approval")) {
          toast.error("Shortlist must be approved before creating an offer.");
        } else {
          toast.error(err.message);
        }
      } else {
        toast.error("Failed to create offer draft");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (appLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (appError || !application) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="text-center py-8 text-destructive">
            Failed to load application: {appError instanceof Error ? appError.message : "Not found"}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <Button variant="ghost" size="sm" asChild className="mb-4">
        <Link to="/candidates">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Candidates
        </Link>
      </Button>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle>{application.candidate_name}</CardTitle>
              <div className="flex items-center gap-3 mt-2 text-sm text-muted-foreground">
                <span className="flex items-center gap-1">
                  <FileText className="h-4 w-4" />
                  {application.job_title}
                </span>
                <StatusBadge status={application.status} />
              </div>
            </div>
            <div className="text-right text-sm text-muted-foreground">
              Application #{application.id}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <Separator />

          <div className="grid gap-4 md:grid-cols-3">
            <div className="md:col-span-2 space-y-4">
              {application.score !== null && (
                <div className="bg-primary/5 border border-primary/20 rounded-lg p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Brain className="h-5 w-5 text-primary" />
                      <span className="font-medium">Match Score</span>
                    </div>
                    <span className="text-2xl font-bold text-primary">
                      {application.score.toFixed(1)} / 100
                    </span>
                  </div>
                  {application.score_reasoning && (
                    <p className="mt-2 text-sm text-muted-foreground">{application.score_reasoning}</p>
                  )}
                </div>
              )}

              {(() => {
                const skills = (application.payload?.skills as string[]) ?? [];
                const missingSkills = (application.payload?.missing_skills as string[]) ?? [];
                const yearsExp = application.payload?.years_experience;
                return (
                  <>
                    {skills.length > 0 && (
                      <div>
                        <label className="text-sm font-medium text-muted-foreground">Matched Skills</label>
                        <div className="flex flex-wrap gap-2 mt-2">
                          {skills.map((skill: string) => (
                            <Badge key={skill} variant="secondary">
                              {skill}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    {missingSkills.length > 0 && (
                      <div>
                        <label className="text-sm font-medium text-muted-foreground">Missing Skills</label>
                        <div className="flex flex-wrap gap-2 mt-2">
                          {missingSkills.map((skill: string) => (
                            <Badge key={skill} variant="destructive">
                              {skill}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    {yearsExp !== undefined && (
                      <div>
                        <label className="text-sm font-medium text-muted-foreground">Years Experience</label>
                        <p className="text-lg font-semibold mt-1">
                          {String(yearsExp)}
                        </p>
                      </div>
                    )}
                  </>
                );
              })()}
            </div>

            <div className="space-y-4">
              <div className="bg-muted/50 rounded-lg p-4">
                <label className="text-sm font-medium text-muted-foreground">Status</label>
                <div className="mt-1">
                  <StatusBadge status={application.status} />
                </div>
              </div>

              <div className="bg-muted/50 rounded-lg p-4">
                <label className="text-sm font-medium text-muted-foreground">Created</label>
                <p className="mt-1 text-sm">{formatDate(application.created_at)}</p>
              </div>
            </div>
          </div>

          <Separator />

          <ApprovalsSection approvals={approvals ?? []} applicationId={application.id} />

          <Separator />

          <OfferSection
            application={application}
            approvals={approvals ?? []}
            onEditOffer={() => setShowOfferForm(true)}
          />

          <Separator />

          <AuditTimeline auditLogs={auditLogs ?? []} />
        </CardContent>
      </Card>

      <AnalysisView applicationId={application.id} />

      <ResumePanel applicationId={application.id} />

      <Dialog open={showOfferForm} onOpenChange={setShowOfferForm}>
        <DialogContent className="sm:max-w-[500px]">
          <form onSubmit={handleSubmit}>
            <DialogHeader>
              <DialogTitle>Create Offer Draft</DialogTitle>
              <DialogDescription>
                Fill in the offer details. The shortlist must be approved.
              </DialogDescription>
            </DialogHeader>
            <DialogContent className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="salary">Salary</Label>
                <Input
                  id="salary"
                  type="number"
                  step="1000"
                  min="0"
                  value={salary}
                  onChange={(e) => setSalary(e.target.value)}
                  placeholder="e.g. 120000"
                  disabled={isSubmitting}
                  required
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="currency">Currency</Label>
                <Select value={currency} onValueChange={setCurrency} disabled={isSubmitting} required>
                  <SelectTrigger>
                    <SelectValue placeholder="Select currency" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="USD">USD ($)</SelectItem>
                    <SelectItem value="EUR">EUR (€)</SelectItem>
                    <SelectItem value="GBP">GBP (£)</SelectItem>
                    <SelectItem value="CAD">CAD ($)</SelectItem>
                    <SelectItem value="AUD">AUD ($)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="startDate">Start Date</Label>
                <Input
                  id="startDate"
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  disabled={isSubmitting}
                  required
                  min={new Date().toISOString().split("T")[0]}
                />
              </div>
            </DialogContent>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowOfferForm(false)} disabled={isSubmitting}>
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting || !salary || !startDate}>
                {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {isSubmitting ? "Creating..." : "Create Offer"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}