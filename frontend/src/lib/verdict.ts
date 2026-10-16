export type BadgeVariant =
  | "default"
  | "secondary"
  | "destructive"
  | "outline";

export const VERDICT_LABELS: Record<string, string> = {
  met: "Met",
  partial: "Partial",
  not_met: "Not met",
  unknown: "Unknown",
};

export const KIND_LABELS: Record<string, string> = {
  must_have: "Must-have",
  nice_to_have: "Nice-to-have",
  experience: "Experience",
};

export const BREAKDOWN_ORDER = ["must_have", "nice_to_have", "experience"] as const;

export const BREAKDOWN_COLORS: Record<string, string> = {
  must_have: "#0ea5e9",
  nice_to_have: "#8b5cf6",
  experience: "#f59e0b",
};

export function verdictLabel(verdict: string): string {
  return VERDICT_LABELS[verdict] ?? verdict;
}

export function kindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}

export function verdictBadgeVariant(verdict: string): BadgeVariant {
  switch (verdict) {
    case "met":
      return "default";
    case "partial":
      return "secondary";
    case "not_met":
      return "destructive";
    default:
      return "outline";
  }
}

export function confidenceBadgeVariant(confidence: string): BadgeVariant {
  switch (confidence.toLowerCase()) {
    case "high":
      return "default";
    case "medium":
      return "secondary";
    case "low":
      return "destructive";
    default:
      return "outline";
  }
}

export function verdictCellClass(verdict: string): string {
  switch (verdict) {
    case "met":
      return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400";
    case "partial":
      return "bg-amber-500/15 text-amber-700 dark:text-amber-400";
    case "not_met":
      return "bg-destructive/15 text-destructive";
    default:
      return "bg-muted text-muted-foreground";
  }
}
