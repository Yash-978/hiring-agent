import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  Brain,
  CheckCircle,
  Download,
  FileCheck,
  FileText,
  Loader2,
  Shield,
  User,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import {
  apiRequest,
  createOfferDraft,
  downloadLetter,
  getApplicationAudit,
  type Application,
  type Approval,
  type AuditLogRead,
} from "@/api/client";
import { AnalysisView } from "@/components/AnalysisView";
import { ResumePanel } from "@/components/ResumePanel";
import { ScoreDisplay } from "@/components/ScoreDisplay";

type BadgeVariant = "default" | "secondary" | "destructive" | "outline";
type JsonObject = Record<string, unknown>;

const statusColors: Record<string, BadgeVariant> = {
  new: "default",
  analyzed: "secondary",
  "shortlist pending": "secondary",
  shortlisted: "secondary",
  rejected: "destructive",
  "offer pending": "outline",
  "offer drafted": "outline",
  hired: "secondary",
};

const actorTypeBadge: Record<string, { variant: BadgeVariant; icon: ReactNode }> = {
  agent: { variant: "default", icon: <Brain className="h-3 w-3" /> },
  user: { variant: "secondary", icon: <User className="h-3 w-3" /> },
  system: { variant: "outline", icon: <Shield className="h-3 w-3" /> },
};

const actorCircle: Record<string, string> = {
  agent: "border-primary bg-primary/10",
  user: "border-secondary bg-secondary/10",
  system: "border-muted bg-muted/50",
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

function asObject(value: unknown): JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonObject)
    : {};
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function latest<T extends { id: number }>(items: T[]): T | undefined {
  return [...items].sort((a, b) => b.id - a.id)[0];
}

interface OfferView {
  approval: Approval;
  letterId: number;
  content: string;
}

/**
 * Finds the offer for this application.
 * If the approvals carry an application_id in their payload we match on it.
 * Otherwise (older data) we fall back to the newest offer approval, which is
 * only correct while a company has a single offer. The proper fix is a backend
 * endpoint GET /applications/{id}/offer.
 */
function findOffer(approvals: Approval[], applicationId: number): OfferView | null {
  const offers = approvals.filter(
    (a) => a.target_type === "letter" && a.action_type === "offer_letter",
  );
  const tagged = offers.filter((a) => asObject(a.payload).application_id !== undefined);
  const matching =
    tagged.length > 0
      ? tagged.filter((a) => Number(asObject(a.payload).application_id) === applicationId)
      : offers;
  const approval = latest(matching);
  if (!approval) return null;

  const payload = asObject(approval.payload);
  const content =
    typeof payload.letter_content === "string"
      ? payload.letter_content
      : typeof payload.content === "string"
        ? payload.content
        : "";

  return { approval, letterId: approval.target_id, content };
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
              const badgeConfig = actorTypeBadge[log.actor_type] ?? {
                variant: "outline" as const,
                icon: <AlertTriangle className="h-3 w-3" />,
              };
              const isLast = index === auditLogs.length - 1;

              return (
                <div key={log.id} className="relative flex gap-4">
                  <div className="flex flex-shrink-0 flex-col items-center">
                    <div
                      className={`relative flex h-8 w-8 items-center justify-center rounded-full border-2 ${actorCircle[log.actor_type] ?? "border-muted bg-muted/50"
                        }`}
                    >
                      {badgeConfig.icon}
                    </div>
                    {!isLast && (
                      <div className="absolute bottom-0 left-3 top-8 w-0.5 bg-border" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1 pb-4 pt-1">
                    <div className="mb-1 flex items-center gap-2">
                      <Badge variant={badgeConfig.variant} className="gap-1">
                        {badgeConfig.icon}
                        {log.actor_type.charAt(0).toUpperCase() + log.actor_type.slice(1)}
                      </Badge>
                      <span className="text-sm text-muted-foreground">{log.actor_name}</span>
                    </div>
                    <div className="mb-2 flex items-center gap-3 text-sm text-muted-foreground">
                      <span className="font-medium capitalize">
                        {log.action.replace(/_/g, " ")}
                      </span>
                      <span>on</span>
                      <span>
                        {log.entity_type} #{log.entity_id}
                      </span>
                    </div>
                    <div className="mb-2 text-xs text-muted-foreground">
                      {formatDate(log.created_at)}
                    </div>
                    {log.details && Object.keys(log.details).length > 0 && (
                      <div className="max-h-48 overflow-auto rounded-md bg-muted/50 p-3 text-xs">
                        <pre className="whitespace-pre-wrap font-mono">
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

function ApprovalsSection({
  approvals,
  applicationId,
}: {
  approvals: Approval[];
  applicationId: number;
}) {
  const appApprovals = approvals.filter(
    (a) => a.target_type === "application" && a.target_id === applicationId,
  );

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
            <div key={approval.id} className="space-y-3 rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge variant="outline">{approval.action_type.replace(/_/g, " ")}</Badge>
                  <Badge
                    variant={
                      approval.status === "approved"
                        ? "secondary"
                        : approval.status === "rejected"
                          ? "destructive"
                          : "default"
                    }
                    className="capitalize"
                  >
                    {approval.status}
                  </Badge>
                </div>
                <span className="text-sm text-muted-foreground">
                  Requested by: user #{approval.requested_by}
                </span>
              </div>

              <div className="grid gap-2 text-sm sm:grid-cols-2">
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
                  <span className="text-sm font-medium text-muted-foreground">Payload:</span>
                  <pre className="mt-1 max-h-48 overflow-auto rounded-md bg-muted p-2 text-xs">
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

function LetterPreview({ title, content }: { title: string; content: string }) {
  if (!content) return null;
  return (
    <div className="max-h-64 overflow-auto rounded-md border bg-muted/50 p-4">
      <span className="mb-2 block text-sm font-medium text-muted-foreground">{title}</span>
      <pre className="whitespace-pre-wrap font-mono text-sm">{content}</pre>
    </div>
  );
}

function OfferSection({
  application,
  approvals,
  onOpenOfferForm,
}: {
  application: Application;
  approvals: Approval[];
  onOpenOfferForm: () => void;
}) {
  const shortlistApproval = latest(
    approvals.filter(
      (a) =>
        a.target_type === "application" &&
        a.target_id === application.id &&
        a.action_type === "shortlist",
    ),
  );
  const offer = findOffer(approvals, application.id);
  const offerApproval = offer?.approval;

  const isShortlistApproved = shortlistApproval?.status === "approved";
  const isOfferPending = offerApproval?.status === "pending";
  const isOfferApproved = offerApproval?.status === "approved";
  const isOfferRejected = offerApproval?.status === "rejected";

  const handleDownload = async () => {
    if (!offer) return;
    try {
      const blob = await downloadLetter(offer.letterId);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `offer_letter_${offer.letterId}.docx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      toast.success("Letter downloaded");
    } catch (err) {
      if (err instanceof Error) {
        if (err.message.includes("403") || err.message.includes("not approved")) {
          toast.error("The offer must be approved before downloading.");
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
        <CardContent className="py-8 text-center">
          <AlertCircle className="mx-auto mb-4 h-12 w-12 text-muted-foreground/50" />
          <h3 className="mb-2 text-lg font-medium">Awaiting Shortlist Approval</h3>
          <p className="mb-4 text-muted-foreground">
            The shortlist approval must be approved before you can create an offer.
          </p>
          <Badge variant="default" className="capitalize">
            {shortlistApproval?.status ?? "pending"}
          </Badge>
        </CardContent>
      </Card>
    );
  }

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
          </div>
          <p className="text-muted-foreground">
            The offer draft has been created and is awaiting approval.
          </p>
          <LetterPreview title="Draft Letter Content" content={offer?.content ?? ""} />
          <div className="flex gap-2">
            <Button variant="outline" asChild>
              <Link to="/approvals">
                <FileCheck className="mr-2 h-4 w-4" />
                View in Approvals
              </Link>
            </Button>
            <Button variant="outline" onClick={onOpenOfferForm}>
              Create a new draft
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
          <Badge variant="secondary" className="capitalize">
            Approved
          </Badge>
          <p className="text-muted-foreground">
            The offer has been approved. You can now download the offer letter.
          </p>
          <LetterPreview title="Offer Letter Content" content={offer?.content ?? ""} />
          <Button onClick={handleDownload} className="w-full sm:w-auto">
            <Download className="mr-2 h-4 w-4" />
            Download Letter (.docx)
          </Button>
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
          <Badge variant="destructive" className="capitalize">
            Rejected
          </Badge>
          <p className="text-muted-foreground">
            The offer was rejected. You can create a new offer draft.
          </p>
          {offerApproval?.decision_note && (
            <div className="rounded-md border border-destructive/20 bg-destructive/10 p-3">
              <span className="text-sm font-medium text-destructive">Rejection reason: </span>
              {offerApproval.decision_note}
            </div>
          )}
          <Button onClick={onOpenOfferForm}>Create a new offer draft</Button>
        </CardContent>
      </Card>
    );
  }

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
        <Button onClick={onOpenOfferForm}>Create offer draft</Button>
      </CardContent>
    </Card>
  );
}

export function CandidateDetail() {
  const { id } = useParams<{ id: string }>();
  const applicationId = Number(id);
  const queryClient = useQueryClient();

  const {
    data: application,
    isLoading: appLoading,
    error: appError,
  } = useQuery({
    queryKey: ["application", applicationId],
    queryFn: () => apiRequest<Application>(`/applications/${applicationId}`),
    enabled: !Number.isNaN(applicationId),
  });

  const { data: approvals } = useQuery({
    queryKey: ["approvals"],
    queryFn: () => apiRequest<Approval[]>("/approvals"),
    enabled: !Number.isNaN(applicationId),
  });

  const { data: auditLogs } = useQuery({
    queryKey: ["application-audit", applicationId],
    queryFn: () => getApplicationAudit(applicationId),
    enabled: !Number.isNaN(applicationId),
  });

  const [showOfferForm, setShowOfferForm] = useState(false);
  const [salary, setSalary] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [startDate, setStartDate] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const refreshAfterOffer = () => {
    void queryClient.invalidateQueries({ queryKey: ["approvals"] });
    void queryClient.invalidateQueries({ queryKey: ["application", applicationId] });
    void queryClient.invalidateQueries({ queryKey: ["application-audit", applicationId] });
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!salary || !startDate || !application) return;

    const amount = Number(salary);
    if (!Number.isFinite(amount) || amount <= 0) {
      toast.error("Enter a valid salary greater than zero.");
      return;
    }

    setIsSubmitting(true);
    try {
      await createOfferDraft(application.id, {
        salary: amount,
        currency,
        start_date: startDate,
      });
      toast.success("Offer draft created");
      refreshAfterOffer();
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
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-primary" />
      </div>
    );
  }

  if (appError || !application) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="py-8 text-center text-destructive">
            Failed to load application:{" "}
            {appError instanceof Error ? appError.message : "Not found"}
          </CardContent>
        </Card>
      </div>
    );
  }

  const payload = asObject(application.payload);
  const skills = asStringArray(payload.skills);
  const missingSkills = asStringArray(payload.missing_skills);
  const yearsExp = payload.years_experience;
  const hasYears = yearsExp !== undefined && yearsExp !== null && yearsExp !== "";

  return (
    <div className="max-w-4xl space-y-6 p-6">
      <Button variant="ghost" size="sm" asChild className="mb-4">
        <Link to="/candidates">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Candidates
        </Link>
      </Button>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle>{application.candidate_name}</CardTitle>
              <div className="mt-2 flex items-center gap-3 text-sm text-muted-foreground">
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
            <div className="space-y-4 md:col-span-2">
              <div className="rounded-lg border border-primary/20 bg-primary/5 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Brain className="h-5 w-5 text-primary" />
                    <span className="font-medium">Match Score</span>
                  </div>
                  <ScoreDisplay score={application.score} />
                </div>
                {application.score_reasoning && (
                  <p className="mt-2 text-sm text-muted-foreground">
                    {application.score_reasoning}
                  </p>
                )}
              </div>

              {skills.length > 0 && (
                <div>
                  <span className="text-sm font-medium text-muted-foreground">
                    Matched Skills
                  </span>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {skills.map((skill) => (
                      <Badge key={skill} variant="secondary">
                        {skill}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {missingSkills.length > 0 && (
                <div>
                  <span className="text-sm font-medium text-muted-foreground">
                    Missing Skills
                  </span>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {missingSkills.map((skill) => (
                      <Badge key={skill} variant="destructive">
                        {skill}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {hasYears && (
                <div>
                  <span className="text-sm font-medium text-muted-foreground">
                    Years Experience
                  </span>
                  <p className="mt-1 text-lg font-semibold">{String(yearsExp)}</p>
                </div>
              )}
            </div>

            <div className="space-y-4">
              <div className="rounded-lg bg-muted/50 p-4">
                <span className="text-sm font-medium text-muted-foreground">Status</span>
                <div className="mt-1">
                  <StatusBadge status={application.status} />
                </div>
              </div>

              <div className="rounded-lg bg-muted/50 p-4">
                <span className="text-sm font-medium text-muted-foreground">Created</span>
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
            onOpenOfferForm={() => setShowOfferForm(true)}
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

            <div className="grid gap-4 py-4">
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
                <Select
                  value={currency}
                  onValueChange={setCurrency}
                  disabled={isSubmitting}
                  required
                >
                  <SelectTrigger id="currency">
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
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowOfferForm(false)}
                disabled={isSubmitting}
              >
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