import { useParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useQuery } from "@tanstack/react-query";
import { apiRequest, type Candidate } from "@/api/client";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";

export function CandidateDetailPage() {
  const { id } = useParams<{ id: string }>();
  const candidateId = Number(id);

  const { data: candidate, isLoading, error } = useQuery({
    queryKey: ["candidate", candidateId],
    queryFn: () => apiRequest<Candidate>(`/candidates/${candidateId}`),
    enabled: !isNaN(candidateId),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (error || !candidate) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="text-center py-8 text-destructive">
            Failed to load candidate: {error instanceof Error ? error.message : "Not found"}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4 max-w-3xl">
      <Button variant="ghost" size="sm" asChild className="mb-4">
        <Link to="/candidates">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Candidates
        </Link>
      </Button>
      <Card>
        <CardHeader>
          <CardTitle>{candidate.full_name}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="text-sm font-medium text-muted-foreground">Email</label>
              <p>{candidate.email}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">Status</label>
              <Badge variant="secondary">{candidate.parsed_data ? "Parsed" : "Raw"}</Badge>
            </div>
          </div>
          {candidate.resume_text && (
            <div>
              <label className="text-sm font-medium text-muted-foreground">Resume</label>
              <pre className="mt-2 p-4 bg-muted rounded-md whitespace-pre-wrap text-sm">
                {candidate.resume_text}
              </pre>
            </div>
          )}
          {candidate.parsed_data && Object.keys(candidate.parsed_data).length > 0 && (
            <div>
              <label className="text-sm font-medium text-muted-foreground">Parsed Data</label>
              <pre className="mt-2 p-4 bg-muted rounded-md whitespace-pre-wrap text-sm">
                {JSON.stringify(candidate.parsed_data, null, 2)}
              </pre>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}