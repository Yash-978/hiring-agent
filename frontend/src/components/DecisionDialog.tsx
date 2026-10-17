import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { AlertCircle, Loader2 } from "lucide-react";

export interface DecisionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "approve" | "reject";
  targetType: string;
  onConfirm: (note?: string) => Promise<void>;
}

interface DecisionDialogFormProps {
  mode: "approve" | "reject";
  targetType: string;
  onConfirm: (note?: string) => Promise<void>;
  onClose: () => void;
}

function DecisionDialogForm({
  mode,
  targetType,
  onConfirm,
  onClose,
}: DecisionDialogFormProps) {
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [touched, setTouched] = useState(false);

  const isReject = mode === "reject";
  const trimmed = note.trim();
  const isValidReject = trimmed.length >= 3;
  const isSubmitDisabled = isSubmitting || (isReject && !isValidReject);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isReject && !isValidReject) {
      setTouched(true);
      setError("Rejection reason must be at least 3 characters.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await onConfirm(trimmed || undefined);
      onClose();
    } catch (err: unknown) {
      // Keep dialog open and show server message
      const msg = err instanceof Error ? err.message : "An unexpected error occurred.";
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const humanType = targetType.replace("_", " ");

  const nextStepDescription = () => {
    if (isReject) {
      return "A note explaining the reason is required.";
    }
    if (targetType === "shortlist") {
      return "Candidate moves to interview scheduling.";
    }
    return `This will approve the ${humanType} request. You may include an optional note.`;
  };

  return (
    <form onSubmit={handleSubmit} noValidate>
      <DialogHeader>
        <DialogTitle>
          {isReject ? `Reject this ${humanType}?` : `Approve this ${humanType}?`}
        </DialogTitle>
        <DialogDescription>{nextStepDescription()}</DialogDescription>
      </DialogHeader>

      {error && (
        <div
          role="alert"
          className="mt-3 flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive"
        >
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="py-4 space-y-2">
        <Label htmlFor="decision-dialog-note">
          {isReject ? "Reason (required)" : "Note (optional)"}
        </Label>
        <Textarea
          id="decision-dialog-note"
          value={note}
          onChange={(e) => {
            setNote(e.target.value);
            setTouched(true);
            if (error) setError(null);
          }}
          placeholder={
            isReject
              ? "Explain why you're rejecting this request..."
              : "Add any context or instructions..."
          }
          rows={3}
          disabled={isSubmitting}
          required={isReject}
          aria-invalid={isReject && touched && !isValidReject}
        />

        {isReject && (
          <div className="flex justify-between items-center text-xs">
            {touched && !isValidReject ? (
              <span className="text-destructive font-medium">
                Must be at least 3 characters
              </span>
            ) : (
              <span className="text-muted-foreground">Min 3 characters</span>
            )}
            <span className="text-muted-foreground font-mono">
              {trimmed.length} / 3
            </span>
          </div>
        )}
      </div>

      <DialogFooter>
        <Button
          type="button"
          variant="outline"
          onClick={onClose}
          disabled={isSubmitting}
        >
          Cancel
        </Button>
        <Button
          type="submit"
          variant={isReject ? "destructive" : "default"}
          disabled={isSubmitDisabled}
        >
          {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {isReject ? "Reject" : "Approve"}
        </Button>
      </DialogFooter>
    </form>
  );
}

export function DecisionDialog({
  open,
  onOpenChange,
  mode,
  targetType,
  onConfirm,
}: DecisionDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        {open && (
          <DecisionDialogForm
            key={`${mode}-${targetType}`}
            mode={mode}
            targetType={targetType}
            onConfirm={onConfirm}
            onClose={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
