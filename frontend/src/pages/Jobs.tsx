import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { SkillsChipsInput } from "@/components/SkillsChipsInput";
import {
  Briefcase,
  Plus,
  Edit,
  GitCompare,
  AlertCircle,
  Loader2,
  Users,
} from "lucide-react";
import { toast } from "sonner";
import {
  getJobs,
  createJob,
  updateJob,
  type Job,
  type JobCreate,
  type JobUpdate,
  ApiError,
} from "@/api/client";

function normalizeTitle(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, " ");
}

export function Jobs() {
  const queryClient = useQueryClient();
  const [isNewJobOpen, setIsNewJobOpen] = useState(false);
  const [editingJob, setEditingJob] = useState<Job | null>(null);

  // New Job state
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newMinYears, setNewMinYears] = useState<string>("");
  const [newMustHave, setNewMustHave] = useState<string[]>([]);
  const [newNiceToHave, setNewNiceToHave] = useState<string[]>([]);
  const [newJobConflict, setNewJobConflict] = useState<{
    message: string;
    existingJob?: Job;
  } | null>(null);

  // Edit Job state
  const [editDescription, setEditDescription] = useState("");
  const [editStatus, setEditStatus] = useState("open");
  const [editMinYears, setEditMinYears] = useState<string>("");
  const [editMustHave, setEditMustHave] = useState<string[]>([]);
  const [editNiceToHave, setEditNiceToHave] = useState<string[]>([]);
  const [editError, setEditError] = useState<string | null>(null);

  const {
    data: jobs,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["jobs"],
    queryFn: getJobs,
  });

  const createMutation = useMutation({
    mutationFn: (data: JobCreate) => createJob(data),
    onSuccess: () => {
      toast.success("Job created successfully");
      setIsNewJobOpen(false);
      resetNewJobForm();
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (err: unknown) => {
      if (err instanceof ApiError && err.status === 409) {
        const errorData = err.data as Record<string, unknown> | undefined;
        const existingJobId = typeof errorData?.existing_job_id === "number" ? errorData.existing_job_id : undefined;
        const existing = existingJobId ? jobs?.find((j) => j.id === existingJobId) : undefined;
        setNewJobConflict({
          message: "A job with this title already exists.",
          existingJob: existing,
        });
      } else {
        toast.error(err instanceof Error ? err.message : "Failed to create job");
      }
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: JobUpdate }) => updateJob(id, data),
    onSuccess: () => {
      toast.success("Job requirements updated successfully");
      setEditingJob(null);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (err: unknown) => {
      setEditError(err instanceof Error ? err.message : "Failed to update job");
    },
  });

  const resetNewJobForm = () => {
    setNewTitle("");
    setNewDescription("");
    setNewMinYears("");
    setNewMustHave([]);
    setNewNiceToHave([]);
    setNewJobConflict(null);
  };

  const openNewJobModal = () => {
    resetNewJobForm();
    setIsNewJobOpen(true);
  };

  const openEditModal = (job: Job) => {
    setEditingJob(job);
    setEditDescription(job.description || "");
    setEditStatus(job.status || "open");
    setEditMinYears(job.min_years_experience != null ? String(job.min_years_experience) : "");
    setEditMustHave(job.must_have_skills || []);
    setEditNiceToHave(job.nice_to_have_skills || []);
    setEditError(null);
  };

  // Live duplicate title check (case and spacing insensitive)
  const normalizedTypedTitle = normalizeTitle(newTitle);
  const clientDuplicateJob = normalizedTypedTitle
    ? jobs?.find((j) => normalizeTitle(j.title) === normalizedTypedTitle)
    : undefined;

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newDescription.trim() || clientDuplicateJob) return;

    createMutation.mutate({
      title: newTitle.trim(),
      description: newDescription.trim(),
      status: "open",
      min_years_experience: newMinYears ? parseFloat(newMinYears) : undefined,
      must_have_skills: newMustHave,
      nice_to_have_skills: newNiceToHave,
    });
  };

  const handleEditSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingJob) return;

    updateMutation.mutate({
      id: editingJob.id,
      data: {
        description: editDescription.trim(),
        status: editStatus,
        min_years_experience: editMinYears ? parseFloat(editMinYears) : null,
        must_have_skills: editMustHave,
        nice_to_have_skills: editNiceToHave,
      },
    });
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Jobs</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage job postings, skill requirements, and candidate pipelines.
          </p>
        </div>
        <Button onClick={openNewJobModal} className="w-full sm:w-auto">
          <Plus className="h-4 w-4 mr-2" />
          New Job
        </Button>
      </div>

      {/* Main Table / States */}
      {isLoading ? (
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
          </CardHeader>
          <CardContent className="space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b">
                <Skeleton className="h-5 w-48" />
                <Skeleton className="h-5 w-20" />
                <Skeleton className="h-5 w-16" />
                <Skeleton className="h-8 w-28" />
              </div>
            ))}
          </CardContent>
        </Card>
      ) : error ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-3 py-12 text-center text-destructive">
            <AlertCircle className="h-10 w-10" />
            <h3 className="text-lg font-medium">Failed to load jobs</h3>
            <p className="text-sm text-muted-foreground max-w-md">
              {error instanceof Error ? error.message : "An unexpected error occurred."}
            </p>
            <Button onClick={() => refetch()} variant="outline" className="mt-2">
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : !jobs || jobs.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
            <Briefcase className="h-12 w-12 text-muted-foreground/40 mb-1" />
            <h3 className="text-lg font-medium">No jobs posted yet</h3>
            <p className="text-sm text-muted-foreground max-w-sm">
              Create your first job posting to start evaluating and comparing candidates.
            </p>
            <Button onClick={openNewJobModal} className="mt-2">
              <Plus className="h-4 w-4 mr-2" />
              Create First Job
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-center">Candidates</TableHead>
                  <TableHead>Must-Have Skills</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell className="font-semibold text-foreground">
                      <div className="max-w-xs sm:max-w-md truncate">
                        {job.title}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={job.status === "open" ? "default" : "secondary"}
                        className="capitalize text-xs"
                      >
                        {job.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center">
                      <span className="inline-flex items-center gap-1 text-sm font-medium">
                        <Users className="h-3.5 w-3.5 text-muted-foreground" />
                        {job.candidate_count ?? 0}
                      </span>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1 max-w-md">
                        {job.must_have_skills && job.must_have_skills.length > 0 ? (
                          job.must_have_skills.map((skill) => (
                            <Badge key={skill} variant="outline" className="text-xs font-normal">
                              {skill}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-xs text-muted-foreground italic">None specified</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right space-x-2 whitespace-nowrap">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openEditModal(job)}
                        className="inline-flex items-center gap-1.5"
                      >
                        <Edit className="h-3.5 w-3.5" />
                        Edit requirements
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        asChild
                      >
                        <Link
                          to={`/jobs/${job.id}/compare`}
                          className="inline-flex items-center gap-1.5"
                        >
                          <GitCompare className="h-3.5 w-3.5" />
                          Compare
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* New Job Dialog */}
      <Dialog open={isNewJobOpen} onOpenChange={setIsNewJobOpen}>
        <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto">
          <form onSubmit={handleCreateSubmit} className="space-y-4">
            <DialogHeader>
              <DialogTitle>Create New Job</DialogTitle>
              <DialogDescription>
                Add a new job opening with description and skill requirements.
              </DialogDescription>
            </DialogHeader>

            {/* Live Client Duplicate Warning */}
            {clientDuplicateJob && (
              <div
                role="alert"
                className="p-3 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-900 dark:text-amber-200 text-sm flex items-center justify-between gap-2"
              >
                <span>A job with this title already exists.</span>
                <button
                  type="button"
                  onClick={() => {
                    setIsNewJobOpen(false);
                    openEditModal(clientDuplicateJob);
                  }}
                  className="underline text-primary font-semibold hover:opacity-80 whitespace-nowrap"
                >
                  Open it
                </button>
              </div>
            )}

            {/* Server 409 Conflict Warning */}
            {newJobConflict && !clientDuplicateJob && (
              <div
                role="alert"
                className="p-3 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-900 dark:text-amber-200 text-sm flex items-center justify-between gap-2"
              >
                <span>{newJobConflict.message}</span>
                {newJobConflict.existingJob && (
                  <button
                    type="button"
                    onClick={() => {
                      setIsNewJobOpen(false);
                      openEditModal(newJobConflict.existingJob!);
                    }}
                    className="underline text-primary font-semibold hover:opacity-80 whitespace-nowrap"
                  >
                    Open it
                  </button>
                )}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="new-job-title">Job Title</Label>
              <Input
                id="new-job-title"
                value={newTitle}
                onChange={(e) => {
                  setNewTitle(e.target.value);
                  if (newJobConflict) setNewJobConflict(null);
                }}
                placeholder="e.g. Senior Frontend Engineer"
                disabled={createMutation.isPending}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="new-job-description">Description</Label>
              <Textarea
                id="new-job-description"
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                placeholder="Provide a comprehensive job description..."
                rows={4}
                disabled={createMutation.isPending}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="new-job-years">Minimum Years of Experience</Label>
              <Input
                id="new-job-years"
                type="number"
                step="0.5"
                min="0"
                value={newMinYears}
                onChange={(e) => setNewMinYears(e.target.value)}
                placeholder="e.g. 3"
                disabled={createMutation.isPending}
              />
            </div>

            <SkillsChipsInput
              id="new-job-must-have"
              label="Must-Have Skills"
              skills={newMustHave}
              onChange={setNewMustHave}
              placeholder="e.g. React, TypeScript (press Enter to add)"
              disabled={createMutation.isPending}
            />

            <SkillsChipsInput
              id="new-job-nice-to-have"
              label="Nice-To-Have Skills"
              skills={newNiceToHave}
              onChange={setNewNiceToHave}
              placeholder="e.g. GraphQL, Tailwind (press Enter to add)"
              disabled={createMutation.isPending}
            />

            <DialogFooter className="pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsNewJobOpen(false)}
                disabled={createMutation.isPending}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={
                  createMutation.isPending ||
                  !newTitle.trim() ||
                  !newDescription.trim() ||
                  Boolean(clientDuplicateJob)
                }
              >
                {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create Job
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Edit Requirements Dialog */}
      <Dialog
        open={Boolean(editingJob)}
        onOpenChange={(open) => {
          if (!open) setEditingJob(null);
        }}
      >
        <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto">
          <form onSubmit={handleEditSubmit} className="space-y-4">
            <DialogHeader>
              <DialogTitle>Edit Requirements: {editingJob?.title}</DialogTitle>
              <DialogDescription>
                Modify skill requirements, description, and experience thresholds.
              </DialogDescription>
            </DialogHeader>

            {editError && (
              <div
                role="alert"
                className="p-3 rounded-md bg-destructive/10 text-destructive text-sm flex items-center gap-2"
              >
                <AlertCircle className="h-4 w-4 flex-shrink-0" />
                <span>{editError}</span>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="edit-job-status">Status</Label>
              <Select
                value={editStatus}
                onValueChange={setEditStatus}
                disabled={updateMutation.isPending}
              >
                <SelectTrigger id="edit-job-status">
                  <SelectValue placeholder="Select status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="open">Open</SelectItem>
                  <SelectItem value="closed">Closed</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-job-description">Description</Label>
              <Textarea
                id="edit-job-description"
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                placeholder="Job description..."
                rows={4}
                disabled={updateMutation.isPending}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-job-years">Minimum Years of Experience</Label>
              <Input
                id="edit-job-years"
                type="number"
                step="0.5"
                min="0"
                value={editMinYears}
                onChange={(e) => setEditMinYears(e.target.value)}
                placeholder="e.g. 3"
                disabled={updateMutation.isPending}
              />
            </div>

            <SkillsChipsInput
              id="edit-job-must-have"
              label="Must-Have Skills"
              skills={editMustHave}
              onChange={setEditMustHave}
              placeholder="e.g. Python, SQL (press Enter to add)"
              disabled={updateMutation.isPending}
            />

            <SkillsChipsInput
              id="edit-job-nice-to-have"
              label="Nice-To-Have Skills"
              skills={editNiceToHave}
              onChange={setEditNiceToHave}
              placeholder="e.g. Docker, Redis (press Enter to add)"
              disabled={updateMutation.isPending}
            />

            <DialogFooter className="pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditingJob(null)}
                disabled={updateMutation.isPending}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={updateMutation.isPending || !editDescription.trim()}
              >
                {updateMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Save Requirements
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
