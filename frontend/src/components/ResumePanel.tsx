import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertCircle, FileText } from "lucide-react";
import { getApplicationAnalysis, getApplicationResume } from "@/api/analysis";

interface ResumePanelProps {
  applicationId: number;
}

export function ResumePanel({ applicationId }: ResumePanelProps) {
  const { data: analysis, isLoading: analysisLoading } = useQuery({
    queryKey: ["application-analysis", applicationId],
    queryFn: () => getApplicationAnalysis(applicationId),
  });

  const resumeAvailable = analysis?.resume_available ?? false;

  const { data, isLoading, error } = useQuery({
    queryKey: ["application-resume", applicationId],
    queryFn: () => getApplicationResume(applicationId),
    enabled: resumeAvailable,
  });

  const mediaType = data?.mediaType.toLowerCase() ?? "";
  const isPdf = mediaType.includes("pdf");
  const isText = mediaType.startsWith("text/") || mediaType.includes("json");
  const blob = data?.blob;

  const objectUrl = useMemo(
    () => (blob && isPdf ? URL.createObjectURL(blob) : null),
    [blob, isPdf]
  );

  useEffect(() => {
    return () => {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [objectUrl]);

  if (analysisLoading) {
    return <Skeleton className="h-64 w-full" />;
  }

  if (!resumeAvailable) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <FileText className="h-5 w-5" />
          Original resume
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && <Skeleton className="h-64 w-full" />}

        {error && (
          <div className="flex flex-col items-center justify-center gap-2 py-12 text-center text-destructive">
            <AlertCircle className="h-8 w-8" />
            <p className="font-medium">Could not load the resume</p>
            <p className="text-sm">
              {error instanceof Error ? error.message : "Unknown error"}
            </p>
          </div>
        )}

        {data && isPdf && objectUrl && (
          <iframe
            src={objectUrl}
            title="Original resume"
            className="h-[600px] w-full rounded-md border"
          />
        )}

        {data && isText && (
          <pre className="max-h-[600px] overflow-auto whitespace-pre-wrap rounded-md border bg-muted/40 p-4 text-sm">
            {data.text}
          </pre>
        )}

        {data && !isPdf && !isText && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            This file type cannot be previewed here.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
