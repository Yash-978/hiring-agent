import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  LabelList,
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { AlertCircle, ArrowDownUp, Inbox, Users } from "lucide-react";
import { ApiError } from "@/api/client";
import { getJobComparison } from "@/api/analysis";
import {
  BREAKDOWN_COLORS,
  BREAKDOWN_ORDER,
  kindLabel,
  verdictCellClass,
  verdictLabel,
} from "@/lib/verdict";
import { cn } from "@/lib/utils";
import type { CompareCandidate, CompareCriterion } from "@/api/types";

const RADAR_COLORS = ["#0ea5e9", "#8b5cf6", "#f59e0b", "#10b981"];
const MAX_SELECTED = 4;
const LEGEND_VERDICTS = ["met", "partial", "not_met", "unknown"];

type SortDirection = "desc" | "asc";

export function JobCompare() {
  const { id } = useParams<{ id: string }>();
  const jobId = Number(id);

  const { data, isLoading, error } = useQuery({
    queryKey: ["job-comparison", jobId],
    queryFn: () => getJobComparison(jobId),
    enabled: Number.isFinite(jobId),
  });

  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [selectedIds, setSelectedIds] = useState<number[] | null>(null);

  if (isLoading) {
    return <CompareSkeleton />;
  }

  if (error) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <div className="p-6">
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-2 py-12 text-center">
            <AlertCircle className={cn("h-8 w-8", notFound ? "text-muted-foreground" : "text-destructive")} />
            <p className="font-medium">
              {notFound ? "Job not found" : "Could not load the comparison"}
            </p>
            <p className="text-sm text-muted-foreground">
              {error instanceof Error ? error.message : "Unknown error"}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  if (data.candidates.length === 0) {
    return (
      <div className="p-6 space-y-4">
        <h1 className="text-2xl font-semibold">{data.job.title}</h1>
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-2 py-12 text-center text-muted-foreground">
            <Inbox className="h-8 w-8" />
            <p className="font-medium">No analyzed candidates yet</p>
            <p className="text-sm">
              Analyze resumes for this job to compare candidates here.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const sortedCandidates = [...data.candidates].sort((a, b) =>
    sortDirection === "desc" ? b.score - a.score : a.score - b.score
  );

  const selected = (
    selectedIds ?? sortedCandidates.slice(0, MAX_SELECTED).map((c) => c.application_id)
  )
    .map((candidateId) =>
      sortedCandidates.find((c) => c.application_id === candidateId)
    )
    .filter((c): c is CompareCandidate => Boolean(c));

  const chartData = sortedCandidates.map((candidate) => ({
    name: candidate.name,
    score: candidate.score,
  }));

  const radarData = BREAKDOWN_ORDER.map((kind) => {
    const row: Record<string, string | number> = { kind: kindLabel(kind) };
    for (const candidate of selected) {
      row[String(candidate.application_id)] = Math.round(
        (candidate.breakdown[kind] ?? 0) * 100
      );
    }
    return row;
  });

  const criterionColumns = collectCriteria(sortedCandidates);

  const toggleSelected = (candidateId: number) => {
    const current = selected.map((c) => c.application_id);
    if (current.includes(candidateId)) {
      setSelectedIds(current.filter((value) => value !== candidateId));
    } else if (current.length < MAX_SELECTED) {
      setSelectedIds([...current, candidateId]);
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">{data.job.title}</h1>
        <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Users className="h-3.5 w-3.5" /> {data.candidates.length} analyzed
          </span>
          {data.job.must_have_skills.length > 0 && (
            <span className="flex flex-wrap items-center gap-1.5">
              Must-have:
              {data.job.must_have_skills.map((skill) => (
                <Badge key={skill} variant="secondary" className="font-normal">
                  {skill}
                </Badge>
              ))}
            </span>
          )}
          {data.job.nice_to_have_skills.length > 0 && (
            <span className="flex flex-wrap items-center gap-1.5">
              Nice-to-have:
              {data.job.nice_to_have_skills.map((skill) => (
                <Badge key={skill} variant="outline" className="font-normal">
                  {skill}
                </Badge>
              ))}
            </span>
          )}
        </div>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">Score ranking</CardTitle>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() =>
              setSortDirection((current) => (current === "desc" ? "asc" : "desc"))
            }
          >
            <ArrowDownUp className="mr-2 h-4 w-4" />
            {sortDirection === "desc" ? "High to low" : "Low to high"}
          </Button>
        </CardHeader>
        <CardContent>
          <div style={{ height: Math.max(220, chartData.length * 44) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartData}
                layout="vertical"
                margin={{ top: 4, right: 40, bottom: 4, left: 8 }}
              >
                <XAxis type="number" domain={[0, 100]} hide />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={160}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip cursor={{ fill: "transparent" }} />
                <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={18} fill="#0ea5e9">
                  <LabelList
                    dataKey="score"
                    position="right"
                    formatter={(value: unknown) =>
                      typeof value === "number" ? value.toFixed(1) : String(value ?? "")
                    }
                    className="fill-foreground text-xs"
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="space-y-3">
          <CardTitle className="text-base">Compare selected candidates</CardTitle>
          <div className="flex flex-wrap gap-2">
            {sortedCandidates.map((candidate) => {
              const isSelected = selected.some(
                (c) => c.application_id === candidate.application_id
              );
              return (
                <Button
                  key={candidate.application_id}
                  type="button"
                  size="sm"
                  variant={isSelected ? "default" : "outline"}
                  onClick={() => toggleSelected(candidate.application_id)}
                  disabled={!isSelected && selected.length >= MAX_SELECTED}
                >
                  {candidate.name}
                </Button>
              );
            })}
          </div>
          <p className="text-xs text-muted-foreground">
            Select up to {MAX_SELECTED} candidates to compare.
          </p>
        </CardHeader>
        <CardContent>
          {selected.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Select at least one candidate to see the comparison.
            </p>
          ) : (
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData} outerRadius="75%">
                  <PolarGrid />
                  <PolarAngleAxis dataKey="kind" />
                  <PolarRadiusAxis domain={[0, 100]} />
                  {selected.map((candidate, index) => {
                    const color = RADAR_COLORS[index % RADAR_COLORS.length];
                    return (
                      <Radar
                        key={candidate.application_id}
                        name={candidate.name}
                        dataKey={String(candidate.application_id)}
                        stroke={color}
                        fill={color}
                        fillOpacity={0.2}
                      />
                    );
                  })}
                  <Legend />
                  <Tooltip />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="space-y-3">
          <CardTitle className="text-base">Skills matrix</CardTitle>
          <div className="flex flex-wrap gap-3 text-xs">
            {LEGEND_VERDICTS.map((verdict) => (
              <span key={verdict} className="flex items-center gap-1.5">
                <span
                  className={cn(
                    "inline-block h-3 w-3 rounded",
                    verdictCellClass(verdict)
                  )}
                />
                {verdictLabel(verdict)}
              </span>
            ))}
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Candidate</TableHead>
                  {criterionColumns.map((column) => (
                    <TableHead key={column.criterion} className="whitespace-nowrap">
                      {column.criterion}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedCandidates.map((candidate) => (
                  <TableRow key={candidate.application_id}>
                    <TableCell className="font-medium">
                      <Link
                        to={`/candidates/${candidate.application_id}`}
                        className="text-primary hover:underline"
                      >
                        {candidate.name}
                      </Link>
                    </TableCell>
                    {criterionColumns.map((column) => {
                      const verdict = verdictFor(candidate, column.criterion);
                      return (
                        <TableCell
                          key={column.criterion}
                          className={cn(
                            "text-center align-middle text-xs",
                            verdict
                              ? verdictCellClass(verdict)
                              : "text-muted-foreground"
                          )}
                        >
                          {verdict ? verdictLabel(verdict) : "—"}
                        </TableCell>
                      );
                    })}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <div className="grid gap-4 md:grid-cols-3">
            {BREAKDOWN_ORDER.map((kind) => (
              <div key={kind} className="space-y-1">
                <p className="flex items-center gap-1.5 text-sm font-medium">
                  <span
                    className="inline-block h-3 w-3 rounded"
                    style={{ backgroundColor: BREAKDOWN_COLORS[kind] }}
                  />
                  {kindLabel(kind)}
                </p>
                <p className="text-xs text-muted-foreground">
                  Average across analyzed candidates
                </p>
                <p className="text-lg font-semibold">
                  {Math.round(averageRatio(data.candidates, kind) * 100)}%
                </p>
              </div>
            ))}
          </div>
          <Separator className="my-4" />
          <p className="text-xs text-muted-foreground">
            Scores and criteria come from the stored resume analysis. Sorting and
            selection are yours to decide.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function collectCriteria(candidates: CompareCandidate[]): CompareCriterion[] {
  const seen = new Map<string, CompareCriterion>();
  for (const candidate of candidates) {
    for (const criterion of candidate.criteria) {
      if (!seen.has(criterion.criterion)) {
        seen.set(criterion.criterion, criterion);
      }
    }
  }
  return [...seen.values()];
}

function verdictFor(
  candidate: CompareCandidate,
  criterion: string
): string | null {
  const match = candidate.criteria.find((c) => c.criterion === criterion);
  return match ? match.verdict : null;
}

function averageRatio(candidates: CompareCandidate[], kind: string): number {
  if (candidates.length === 0) {
    return 0;
  }
  const total = candidates.reduce(
    (sum, candidate) => sum + (candidate.breakdown[kind] ?? 0),
    0
  );
  return total / candidates.length;
}

function CompareSkeleton() {
  return (
    <div className="p-6 space-y-4">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-64 w-full" />
      <Skeleton className="h-80 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}
