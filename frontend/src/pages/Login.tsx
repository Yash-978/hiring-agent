import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertCircle, Loader2 } from "lucide-react";

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export type Mode = "signin" | "signup";

interface LoginProps {
  mode: Mode;
  onSwitchMode: (mode: Mode) => void;
}

export function Login({ mode, onSwitchMode }: LoginProps) {
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);

  const isSignup = mode === "signup";

  const switchMode = (next: Mode) => {
    if (next === mode || isLoading) return;
    onSwitchMode(next);
    setError("");
    setFieldErrors({});
    setConfirmPassword("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setFieldErrors({});

    // ---------- CREATE ACCOUNT ----------
    if (isSignup) {
      const errors: Record<string, string> = {};

      if (!companyName.trim()) {
        errors.companyName = "Company name is required.";
      }
      if (!email.trim()) {
        errors.email = "Email is required.";
      } else if (!EMAIL_PATTERN.test(email.trim())) {
        errors.email = "Enter a valid email address.";
      }
      if (!password) {
        errors.password = "Password is required.";
      } else if (password.length < 8) {
        errors.password = "Password must be at least 8 characters.";
      }
      if (!confirmPassword) {
        errors.confirmPassword = "Please confirm your password.";
      } else if (confirmPassword !== password) {
        errors.confirmPassword = "Passwords do not match.";
      }

      setFieldErrors(errors);
      if (Object.keys(errors).length > 0) return;

      setIsLoading(true);
      try {
        await register(companyName.trim(), email.trim(), password);
        navigate("/candidates");
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Could not create account"
        );
      } finally {
        setIsLoading(false);
      }
      return;
    }

    // ---------- SIGN IN ----------
    setIsLoading(true);
    try {
      await login(email, password);
      navigate("/candidates");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* ---------- SIGNUP-ONLY FIELD ---------- */}
      {isSignup && (
        <div className="space-y-2">
          <Label htmlFor="company-name">Company name</Label>
          <Input
            id="company-name"
            type="text"
            placeholder="Acme Inc"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            disabled={isLoading}
            autoComplete="organization"
          />
          {fieldErrors.companyName && (
            <p className="text-sm text-destructive">
              {fieldErrors.companyName}
            </p>
          )}
        </div>
      )}

      {/* ---------- SHARED FIELDS ---------- */}
      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          placeholder="admin@demo.test"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={isLoading}
          required
          autoComplete="email"
        />
        {fieldErrors.email && (
          <p className="text-sm text-destructive">{fieldErrors.email}</p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          placeholder={isSignup ? "At least 8 characters" : "••••••••"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={isLoading}
          required
          autoComplete={isSignup ? "new-password" : "current-password"}
        />
        {fieldErrors.password && (
          <p className="text-sm text-destructive">{fieldErrors.password}</p>
        )}
      </div>

      {/* ---------- SIGNUP-ONLY FIELD ---------- */}
      {isSignup && (
        <div className="space-y-2">
          <Label htmlFor="confirm-password">Confirm password</Label>
          <Input
            id="confirm-password"
            type="password"
            placeholder="••••••••"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            disabled={isLoading}
            autoComplete="new-password"
          />
          {fieldErrors.confirmPassword && (
            <p className="text-sm text-destructive">
              {fieldErrors.confirmPassword}
            </p>
          )}
        </div>
      )}

      {/* ---------- TWO BUTTONS AT THE BOTTOM ---------- */}
      <div className="flex flex-col gap-2 pt-2 sm:flex-row">
        <Button
          type={isSignup ? "button" : "submit"}
          variant={isSignup ? "outline" : "default"}
          className="w-full sm:flex-1"
          disabled={isLoading}
          onClick={isSignup ? () => switchMode("signin") : undefined}
        >
          {!isSignup && isLoading && (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          )}
          Sign in
        </Button>

        <Button
          type={isSignup ? "submit" : "button"}
          variant={isSignup ? "default" : "outline"}
          className="w-full sm:flex-1"
          disabled={isLoading}
          onClick={isSignup ? undefined : () => switchMode("signup")}
        >
          {isSignup && isLoading && (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          )}
          Create account
        </Button>
      </div>
    </form>
  );
}