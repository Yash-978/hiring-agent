import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { useMeta } from "@/lib/useMeta";

export interface ScoreDisplayProps {
  score: number | null | undefined;
  modelName?: string | null;
  className?: string;
  showReasonWhenNull?: boolean;
}

export function ScoreDisplay({
  score,
  modelName,
  className = "",
  showReasonWhenNull = true,
}: ScoreDisplayProps) {
  const { data: meta } = useMeta();
  const activeModel = modelName || meta?.llm_model || "AI";

  if (score === null || score === undefined) {
    return (
      <span className={`inline-flex items-center gap-1.5 flex-wrap text-xs ${className}`}>
        <Badge variant="outline" className="font-mono text-xs bg-muted/60 text-muted-foreground">
          Not scored
        </Badge>
        {showReasonWhenNull && (
          <span className="text-xs text-muted-foreground">
            (
            <Link
              to="/jobs"
              className="text-primary hover:underline font-medium"
              onClick={(e) => e.stopPropagation()}
            >
              Add must-have skills to this job
            </Link>
            )
          </span>
        )}
        <Badge
          variant="outline"
          className="text-[10px] font-mono px-1.5 py-0 text-muted-foreground border-muted-foreground/30"
        >
          {activeModel}
        </Badge>
      </span>
    );
  }

  const numericScore = Number(score);
  const rounded = Math.round(numericScore);

  const colorClasses =
    numericScore < 50
      ? "bg-red-500/15 text-red-700 border-red-500/30 dark:bg-red-950/40 dark:text-red-400 dark:border-red-800"
      : numericScore < 75
      ? "bg-amber-500/15 text-amber-700 border-amber-500/30 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800"
      : "bg-green-500/15 text-green-700 border-green-500/30 dark:bg-green-950/40 dark:text-green-400 dark:border-green-800";

  return (
    <span className={`inline-flex items-center gap-1.5 flex-wrap ${className}`}>
      <Badge
        variant="outline"
        className={`font-mono text-xs font-semibold px-2 py-0.5 border ${colorClasses}`}
      >
        {rounded} / 100
      </Badge>
      <Badge
        variant="outline"
        className="text-[10px] font-mono px-1.5 py-0 text-muted-foreground border-muted-foreground/30"
      >
        {activeModel}
      </Badge>
    </span>
  );
}
