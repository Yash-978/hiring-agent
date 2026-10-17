import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus, Loader2, FileText, AlertCircle, BarChart3 } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { apiRequest, apiUpload, ApiError, type Application, type Job, type CandidateCreate, type ApplicationCreate, type JobCreate } from "@/api/client";
import { ScoreDisplay } from "@/components/ScoreDisplay";

const statusColors: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  new: "default",
  "shortlist pending": "secondary",
  shortlisted: "secondary",
  rejected: "destructive",
  "offer pending": "outline",
  hired: "secondary",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant={statusColors[status] ?? "outline"} className="capitalize">
      {status}
    </Badge>
  );
}

function ApplicationSkeleton() {
  return (
    <TableRow>
      <TableCell><Skeleton className="h-4 w-3/4" /></TableCell>
      <TableCell><Skeleton className="h-4 w-1/2" /></TableCell>
      <TableCell><Skeleton className="h-6 w-24" /></TableCell>
      <TableCell><Skeleton className="h-6 w-16" /></TableCell>
      <TableCell><Skeleton className="h-4 w-24" /></TableCell>
    </TableRow>
  );
}

function NewJobDialog({ onSuccess }: { onSuccess: () => void }) {
  const [isOpen, setIsOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const mutation = useMutation({
    mutationFn: (data: JobCreate) => apiRequest<Job>("/jobs", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => {
      toast.success("Job created");
      onSuccess();
      setIsOpen(false);
      setTitle("");
      setDescription("");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;
    setIsLoading(true);
    mutation.mutate({ title, description, status: "open" });
    setIsLoading(false);
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <Plus className="h-4 w-4 mr-2" />
          New job
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create new job</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="title">Title</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Senior Backend Engineer"
                disabled={isLoading}
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Job description..."
                disabled={isLoading}
                required
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setIsOpen(false)} disabled={isLoading}>
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading || !title.trim() || !description.trim()}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

interface NewCandidateDialogProps {
  onSuccess: () => void;
  jobs: Job[];
}

function NewCandidateDialog({ onSuccess, jobs }: NewCandidateDialogProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [jobId, setJobId] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [conflictError, setConflictError] = useState<{
    message: string;
    existingAppId?: number;
  } | null>(null);

  const queryClient = useQueryClient();

  const uniqueJobs = Array.from(new Map(jobs.map((job) => [job.id, job])).values());

  const createCandidateMutation = useMutation({
    mutationFn: (data: CandidateCreate) => apiRequest<{ id: number }>("/candidates", { method: "POST", body: JSON.stringify(data) }),
  });

  const createApplicationMutation = useMutation({
    mutationFn: (data: ApplicationCreate) => apiRequest<Application>("/applications", { method: "POST", body: JSON.stringify(data) }),
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim() || !email.trim() || !jobId || !resumeFile) return;

    setIsLoading(true);
    setConflictError(null);
    try {
      // 1. Create candidate
      const candidate = await createCandidateMutation.mutateAsync({
        full_name: fullName,
        email,
        resume_text: "",
      });

      // 2. Create application
      const application = await createApplicationMutation.mutateAsync({
        candidate_id: candidate.id,
        job_id: Number(jobId),
      });

      // 3. Analyze with file upload
      setAnalyzing(true);
      const formData = new FormData();
      formData.append("file", resumeFile);

      await apiUpload<Application>(`/applications/${application.id}/analyze`, formData);

      toast.success("Candidate added and analysis complete");
      queryClient.invalidateQueries({ queryKey: ["applications"] });
      setIsOpen(false);
      setFullName("");
      setEmail("");
      setJobId("");
      setResumeFile(null);
      setConflictError(null);
      onSuccess();
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 409) {
        const errorData = err.data as Record<string, unknown> | undefined;
        const existingAppId =
          typeof errorData?.existing_application_id === "number"
            ? errorData.existing_application_id
            : undefined;
        setConflictError({
          message: err.message || "This candidate has already applied to this job.",
          existingAppId,
        });
      } else {
        toast.error(err instanceof Error ? err.message : "Failed to add candidate");
      }
    } finally {
      setIsLoading(false);
      setAnalyzing(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="h-4 w-4 mr-2" />
          New candidate
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Add new candidate</DialogTitle>
          </DialogHeader>

          {conflictError && (
            <div
              role="alert"
              className="mt-3 p-3 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-sm flex items-start gap-2"
            >
              <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <p className="font-medium">{conflictError.message}</p>
                {conflictError.existingAppId && (
                  <Link
                    to={`/candidates/${conflictError.existingAppId}`}
                    className="text-primary underline font-medium text-xs mt-1 inline-block hover:opacity-80"
                    onClick={() => setIsOpen(false)}
                  >
                    View existing candidate application &rarr;
                  </Link>
                )}
              </div>
            </div>
          )}

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="fullName">Full name</Label>
              <Input
                id="fullName"
                value={fullName}
                onChange={(e) => {
                  setFullName(e.target.value);
                  if (conflictError) setConflictError(null);
                }}
                placeholder="e.g. Alice Smith"
                disabled={isLoading}
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (conflictError) setConflictError(null);
                }}
                placeholder="alice@example.com"
                disabled={isLoading}
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="jobId">Job</Label>
              <Select
                value={jobId}
                onValueChange={(val) => {
                  setJobId(val);
                  if (conflictError) setConflictError(null);
                }}
                disabled={isLoading}
                required
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a job" />
                </SelectTrigger>
                <SelectContent>
                  {uniqueJobs.map((job) => (
                    <SelectItem key={job.id} value={String(job.id)}>
                      {job.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="resume">Resume (PDF or TXT)</Label>
              <Input
                id="resume"
                type="file"
                accept=".pdf,.txt"
                onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
                disabled={isLoading}
                required
              />
              {resumeFile && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <FileText className="h-4 w-4" />
                  <span>{resumeFile.name}</span>
                  <span>({(resumeFile.size / 1024).toFixed(1)} KB)</span>
                </div>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setIsOpen(false)} disabled={isLoading || analyzing}>
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading || analyzing || !fullName.trim() || !email.trim() || !jobId || !resumeFile}>
              {analyzing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {analyzing ? "Analyzing..." : isLoading ? "Creating..." : "Add candidate"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function Candidates() {
  const { data: applications, isLoading, error } = useQuery({
    queryKey: ["applications"],
    queryFn: () => apiRequest<Application[]>("/applications"),
  });

  const { data: jobs } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => apiRequest<Job[]>("/jobs"),
  });

  const queryClient = useQueryClient();

  const handleSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ["jobs"] });
    queryClient.invalidateQueries({ queryKey: ["applications"] });
  };

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <CardHeader><CardTitle>Candidates</CardTitle></CardHeader>
          <NewJobDialog onSuccess={handleSuccess} />
        </div>
        <Card>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Candidate</TableHead>
                  <TableHead>Job</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead className="text-right">Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {[...Array(5)].map((_, i) => (
                  <ApplicationSkeleton key={i} />
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="text-center py-8 text-destructive">
            <AlertCircle className="h-8 w-8 mx-auto mb-2" />
            <p>Failed to load applications</p>
            <p className="text-sm text-muted-foreground mt-1">{error instanceof Error ? error.message : "Unknown error"}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <CardHeader><CardTitle>Candidates</CardTitle></CardHeader>
        <div className="flex gap-2">
          <NewJobDialog onSuccess={handleSuccess} />
          <NewCandidateDialog onSuccess={handleSuccess} jobs={jobs ?? []} />
        </div>
      </div>
      {jobs?.length ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Compare candidates by job</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {jobs.map((job) => (
              <Button key={job.id} variant="outline" size="sm" asChild>
                <Link to={`/jobs/${job.id}/compare`}>
                  <BarChart3 className="mr-2 h-4 w-4" />
                  Compare: {job.title}
                  <Badge variant="secondary" className="ml-2 font-normal">
                    {job.candidate_count}
                  </Badge>
                </Link>
              </Button>
            ))}
          </CardContent>
        </Card>
      ) : null}
      <Card>
        <CardContent>
          {!applications?.length ? (
            <div className="text-center py-12">
              <FileText className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
              <h3 className="text-lg font-medium mb-2">No candidates yet</h3>
              <p className="text-muted-foreground mb-4">Click "New candidate" to add your first candidate with a resume.</p>
              <Button onClick={() => {}} asChild>
                <a href="#new-candidate">Add candidate</a>
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Candidate</TableHead>
                  <TableHead>Job</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead className="text-right">Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {applications?.map((app) => (
                  <TableRow key={app.id}>
                    <TableCell className="font-medium">
                      <a href={`/candidates/${app.id}`} className="hover:underline text-primary">
                        {app.candidate_name}
                      </a>
                    </TableCell>
                    <TableCell>{app.job_title}</TableCell>
                    <TableCell><StatusBadge status={app.status} /></TableCell>
                    <TableCell><ScoreDisplay score={app.score} /></TableCell>
                    <TableCell className="text-right text-muted-foreground">
                      {new Date(app.created_at).toLocaleDateString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}