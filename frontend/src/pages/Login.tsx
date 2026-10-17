import { useState, type ComponentProps, type FormEvent } from "react";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { AlertCircle, Loader2 } from "lucide-react";

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export type Mode = "signin" | "signup";

type FieldName = "companyName" | "email" | "password" | "confirmPassword";
type FieldErrors = Partial<Record<FieldName, string>>;

interface LoginProps {
  mode: Mode;
  onSwitchMode: (mode: Mode) => void;
}

function Field({
  id,
  label,
  error,
  ...inputProps
}: { id: string; label: string; error?: string } & ComponentProps<typeof Input>) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        {...inputProps}
      />
      {error && (
        <p id={`${id}-error`} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

export function Login({ mode, onSwitchMode }: LoginProps) {
  const { login, register } = useAuth();

  const [companyName, setCompanyName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [isLoading, setIsLoading] = useState(false);

  const isSignup = mode === "signup";

  const switchMode = (next: Mode) => {
    if (next === mode || isLoading) return;
    onSwitchMode(next);
    setError("");
    setFieldErrors({});
    setPassword("");
    setConfirmPassword("");
  };

  const validate = (): FieldErrors => {
    const errors: FieldErrors = {};
    if (isSignup && !companyName.trim()) {
      errors.companyName = "Company name is required.";
    }
    if (!email.trim()) {
      errors.email = "Email is required.";
    } else if (!EMAIL_PATTERN.test(email.trim())) {
      errors.email = "Enter a valid email address.";
    }
    if (!password) {
      errors.password = "Password is required.";
    } else if (isSignup && password.length < 8) {
      errors.password = "Password must be at least 8 characters.";
    }
    if (isSignup) {
      if (!confirmPassword) {
        errors.confirmPassword = "Please confirm your password.";
      } else if (confirmPassword !== password) {
        errors.confirmPassword = "Passwords do not match.";
      }
    }
    return errors;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    const errors = validate();
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setIsLoading(true);
    try {
      if (isSignup) {
        await register(companyName.trim(), email.trim(), password);
      } else {
        await login(email.trim(), password);
      }
      // AuthContext navigates to /candidates after success.
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : isSignup
            ? "Could not create account"
            : "Login failed",
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div
        role="group"
        aria-label="Choose sign in or create account"
        className="grid grid-cols-2 gap-1 rounded-lg bg-muted p-1"
      >
        {(["signin", "signup"] as const).map((m) => (
          <button
            key={m}
            type="button"
            aria-pressed={mode === m}
            disabled={isLoading}
            onClick={() => switchMode(m)}
            className={cn(
              "rounded-md px-3 py-2 text-sm font-medium transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              mode === m
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {m === "signin" ? "Sign in" : "Create account"}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        {error && (
          <div
            role="alert"
            className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive"
          >
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {isSignup && (
          <Field
            id="company-name"
            label="Company name"
            placeholder="Acme Inc"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            disabled={isLoading}
            autoComplete="organization"
            error={fieldErrors.companyName}
          />
        )}

        <Field
          id="email"
          label="Email"
          type="email"
          placeholder="you@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={isLoading}
          autoComplete="email"
          error={fieldErrors.email}
        />

        <Field
          id="password"
          label="Password"
          type="password"
          placeholder={isSignup ? "At least 8 characters" : "Your password"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={isLoading}
          autoComplete={isSignup ? "new-password" : "current-password"}
          error={fieldErrors.password}
        />

        {isSignup && (
          <Field
            id="confirm-password"
            label="Confirm password"
            type="password"
            placeholder="Repeat your password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            disabled={isLoading}
            autoComplete="new-password"
            error={fieldErrors.confirmPassword}
          />
        )}

        <Button type="submit" className="w-full" disabled={isLoading}>
          {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {isSignup ? "Create account" : "Sign in"}
        </Button>
      </form>

      <p className="text-center text-sm text-muted-foreground">
        {isSignup ? "Already have an account?" : "New here?"}{" "}
        <button
          type="button"
          disabled={isLoading}
          onClick={() => switchMode(isSignup ? "signin" : "signup")}
          className="font-medium text-foreground underline-offset-4 hover:underline"
        >
          {isSignup ? "Sign in" : "Create a company account"}
        </button>
      </p>
    </div>
  );
}