import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertCircle,
  AlertTriangle,
  Inbox,
  Mail,
  MapPin,
  Phone,
  Sparkles,
} from "lucide-react";
import { ApiError } from "@/api/client";
import { getApplicationAnalysis } from "@/api/analysis";
import {
  BREAKDOWN_COLORS,
  BREAKDOWN_ORDER,
  confidenceBadgeVariant,
  kindLabel,
  verdictBadgeVariant,
  verdictLabel,
} from "@/lib/verdict";
import type { ApplicationAnalysis } from "@/api/types";

interface AnalysisViewProps {
  applicationId: number;
}

export function AnalysisView({ applicationId }: AnalysisViewProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["application-analysis", applicationId],
    queryFn: () => getApplicationAnalysis(applicationId),
  });

  if (isLoading) {
    return <AnalysisSkeleton />;
  }

  if (error) {
    if (error instanceof ApiError && error.status === 404) {
      return (
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-2 py-12 text-center text-muted-foreground">
            <Inbox className="h-8 w-8" />
            <p className="font-medium">No analysis yet</p>
            <p className="text-sm">
              Run an analysis on this resume to see the agent's review here.
            </p>
          </CardContent>
        </Card>
      );
    }
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center gap-2 py-12 text-center text-destructive">
          <AlertCircle className="h-8 w-8" />
          <p className="font-medium">Could not load the analysis</p>
          <p className="text-sm">
            {error instanceof Error ? error.message : "Unknown error"}
          </p>
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return null;
  }

  return <AnalysisContent analysis={data} />;
}

function AnalysisContent({ analysis }: { analysis: ApplicationAnalysis }) {
  const { candidate } = analysis;
  const years = candidate.total_years_experience;
  const breakdownData = BREAKDOWN_ORDER.filter(
    (kind) => analysis.breakdown[kind]
  ).map((kind) => ({
    kind,
    label: kindLabel(kind),
    value: Math.round(analysis.breakdown[kind].ratio * 100),
  }));

  return (
    <div className="space-y-4">
      {analysis.flags.length > 0 && (
        <Card className="border-amber-500/40 bg-amber-500/5">
          <CardContent className="flex gap-3 py-4">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" />
            <div className="space-y-1">
              <p className="text-sm font-medium">Flags to check</p>
              <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground">
                {analysis.flags.map((flag, index) => (
                  <li key={`${flag}-${index}`}>{flag}</li>
                ))}
              </ul>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="space-y-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <CardTitle className="text-xl">
                {candidate.full_name ?? "Unknown candidate"}
              </CardTitle>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
                {candidate.current_title && <span>{candidate.current_title}</span>}
                {years != null && (
                  <span>
                    {years} {years === 1 ? "year" : "years"} experience
                  </span>
                )}
              </div>
            </div>
            <div className="text-right">
              <div className="text-4xl font-bold leading-none">
                {analysis.score.toFixed(1)}
              </div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground">
                score
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
            {candidate.email && (
              <span className="flex items-center gap-1.5">
                <Mail className="h-3.5 w-3.5" /> {candidate.email}
              </span>
            )}
            {candidate.phone && (
              <span className="flex items-center gap-1.5">
                <Phone className="h-3.5 w-3.5" /> {candidate.phone}
              </span>
            )}
            {candidate.location && (
              <span className="flex items-center gap-1.5">
                <MapPin className="h-3.5 w-3.5" /> {candidate.location}
              </span>
            )}
          </div>

          <div className="rounded-md border bg-muted/40 p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                <Sparkles className="h-3.5 w-3.5" /> Suggestion, you decide
              </span>
              <Badge
                variant={confidenceBadgeVariant(analysis.confidence)}
                className="capitalize"
              >
                {analysis.confidence || "unknown"} confidence
              </Badge>
            </div>
            <p className="mt-2 text-sm">
              {analysis.recommendation || "No recommendation provided."}
            </p>
          </div>

          {candidate.skills.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {candidate.skills.map((skill) => (
                <Badge key={skill} variant="secondary" className="font-normal">
                  {skill}
                </Badge>
              ))}
            </div>
          )}
        </CardHeader>

        <Separator />

        <CardContent className="space-y-6 pt-6">
          <div className="space-y-2">
            <p className="text-sm font-medium">Score breakdown</p>
            {breakdownData.length > 0 ? (
              <div className="h-40 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={breakdownData}
                    layout="vertical"
                    margin={{ top: 4, right: 40, bottom: 4, left: 8 }}
                  >
                    <XAxis
                      type="number"
                      domain={[0, 100]}
                      hide
                    />
                    <YAxis
                      type="category"
                      dataKey="label"
                      width={90}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip cursor={{ fill: "transparent" }} />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={18}>
                      {breakdownData.map((entry) => (
                        <Cell
                          key={entry.kind}
                          fill={BREAKDOWN_COLORS[entry.kind] ?? "#64748b"}
                        />
                      ))}
                      <LabelList
                        dataKey="value"
                        position="right"
                        className="fill-foreground text-xs"
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No breakdown available.
              </p>
            )}
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">Criteria</p>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Criterion</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Verdict</TableHead>
                    <TableHead>Evidence</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {analysis.criteria.length === 0 ? (
                    <TableRow>
                      <TableCell
                        colSpan={4}
                        className="text-center text-muted-foreground"
                      >
                        No criteria were extracted
                      </TableCell>
                    </TableRow>
                  ) : (
                    analysis.criteria.map((criterion, index) => (
                      <TableRow key={`${criterion.criterion}-${index}`}>
                        <TableCell className="font-medium align-top">
                          {criterion.criterion}
                        </TableCell>
                        <TableCell className="align-top">
                          <Badge variant="outline" className="font-normal">
                            {kindLabel(criterion.kind)}
                          </Badge>
                        </TableCell>
                        <TableCell className="align-top">
                          <div className="flex flex-col items-start gap-1">
                            <Badge
                              variant={verdictBadgeVariant(criterion.verdict)}
                            >
                              {verdictLabel(criterion.verdict)}
                            </Badge>
                            {!criterion.evidence_verified && (
                              <span className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400">
                                <AlertTriangle className="h-3 w-3" /> unverified
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="max-w-xs whitespace-normal align-top">
                          {criterion.evidence ? (
                            <blockquote className="border-l-2 pl-2 text-sm italic text-muted-foreground">
                              {criterion.evidence}
                            </blockquote>
                          ) : (
                            <span className="text-sm text-muted-foreground">
                              No evidence quoted
                            </span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <ListBlock title="Strengths" items={analysis.strengths} />
            <ListBlock title="Concerns" items={analysis.concerns} />
            <ListBlock
              title="Questions for candidate"
              items={analysis.questions_for_candidate}
            />
          </div>

          {(analysis.model || analysis.prompt_version) && (
            <p className="text-xs text-muted-foreground">
              {analysis.model && `Model: ${analysis.model}`}
              {analysis.model && analysis.prompt_version && " · "}
              {analysis.prompt_version && `Prompt: ${analysis.prompt_version}`}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="space-y-1.5">
      <p className="text-sm font-medium">{title}</p>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">None noted</p>
      ) : (
        <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground">
          {items.map((item, index) => (
            <li key={`${item}-${index}`}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function AnalysisSkeleton() {
  return (
    <Card>
      <CardHeader className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-2">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-32" />
          </div>
          <Skeleton className="h-10 w-20" />
        </div>
        <Skeleton className="h-4 w-64" />
        <Skeleton className="h-16 w-full" />
      </CardHeader>
      <CardContent className="space-y-4">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-40 w-full" />
      </CardContent>
    </Card>
  );
}
