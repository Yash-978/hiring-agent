// import { useState } from "react";
// import { useNavigate } from "react-router-dom";
// import { useAuth } from "@/auth/useAuth";
// import { Button } from "@/components/ui/button";
// import { Input } from "@/components/ui/input";
// import { Label } from "@/components/ui/label";
// import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
// import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
// import { AlertCircle, Loader2 } from "lucide-react";

// const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

// export function Login() {
//   const { login, register } = useAuth();
//   const navigate = useNavigate();

//   const [email, setEmail] = useState("");
//   const [password, setPassword] = useState("");
//   const [error, setError] = useState("");
//   const [isLoading, setIsLoading] = useState(false);

//   const [companyName, setCompanyName] = useState("");
//   const [signupEmail, setSignupEmail] = useState("");
//   const [signupPassword, setSignupPassword] = useState("");
//   const [confirmPassword, setConfirmPassword] = useState("");
//   const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
//   const [signupError, setSignupError] = useState("");
//   const [isSignupLoading, setIsSignupLoading] = useState(false);

//   const handleSubmit = async (e: React.FormEvent) => {
//     e.preventDefault();
//     setError("");
//     setIsLoading(true);
//     try {
//       await login(email, password);
//       navigate("/candidates");
//     } catch (err) {
//       setError(err instanceof Error ? err.message : "Login failed");
//     } finally {
//       setIsLoading(false);
//     }
//   };

//   const handleSignup = async (e: React.FormEvent) => {
//     e.preventDefault();
//     setSignupError("");

//     const errors: Record<string, string> = {};
//     if (!companyName.trim()) {
//       errors.companyName = "Company name is required.";
//     }
//     if (!signupEmail.trim()) {
//       errors.email = "Email is required.";
//     } else if (!EMAIL_PATTERN.test(signupEmail.trim())) {
//       errors.email = "Enter a valid email address.";
//     }
//     if (!signupPassword) {
//       errors.password = "Password is required.";
//     } else if (signupPassword.length < 8) {
//       errors.password = "Password must be at least 8 characters.";
//     }
//     if (!confirmPassword) {
//       errors.confirmPassword = "Please confirm your password.";
//     } else if (confirmPassword !== signupPassword) {
//       errors.confirmPassword = "Passwords do not match.";
//     }
//     setFieldErrors(errors);
//     if (Object.keys(errors).length > 0) {
//       return;
//     }

//     setIsSignupLoading(true);
//     try {
//       await register(companyName.trim(), signupEmail.trim(), signupPassword);
//       navigate("/candidates");
//     } catch (err) {
//       setSignupError(err instanceof Error ? err.message : "Could not create account");
//     } finally {
//       setIsSignupLoading(false);
//     }
//   };

//   return (
//     <div className="flex min-h-screen items-center justify-center bg-background p-4">
//       <Card className="w-full max-w-md">
//         <CardHeader className="text-center">
//           <CardTitle className="text-2xl">Welcome</CardTitle>
//           <CardDescription>Sign in or create a new company account</CardDescription>
//         </CardHeader>
//         <CardContent>
//           <Tabs defaultValue="signin" className="gap-4">
//             <TabsList className="w-full">
//               <TabsTrigger value="signin">Sign in</TabsTrigger>
//               <TabsTrigger value="signup">Create account</TabsTrigger>
//             </TabsList>

//             <TabsContent value="signin">
//               <form onSubmit={handleSubmit} className="space-y-4">
//                 {error && (
//                   <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 p-3 rounded-md">
//                     <AlertCircle className="h-4 w-4 flex-shrink-0" />
//                     <span>{error}</span>
//                   </div>
//                 )}
//                 <div className="space-y-2">
//                   <Label htmlFor="email">Email</Label>
//                   <Input
//                     id="email"
//                     type="email"
//                     placeholder="admin@demo.test"
//                     value={email}
//                     onChange={(e) => setEmail(e.target.value)}
//                     disabled={isLoading}
//                     required
//                     autoComplete="email"
//                   />
//                 </div>
//                 <div className="space-y-2">
//                   <Label htmlFor="password">Password</Label>
//                   <Input
//                     id="password"
//                     type="password"
//                     placeholder="••••••••"
//                     value={password}
//                     onChange={(e) => setPassword(e.target.value)}
//                     disabled={isLoading}
//                     required
//                     autoComplete="current-password"
//                   />
//                 </div>
//                 <Button type="submit" className="w-full" disabled={isLoading}>
//                   {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
//                   {isLoading ? "Signing in..." : "Sign in"}
//                 </Button>
//               </form>
//             </TabsContent>

//             <TabsContent value="signup">
//               <form onSubmit={handleSignup} className="space-y-4">
//                 {signupError && (
//                   <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 p-3 rounded-md">
//                     <AlertCircle className="h-4 w-4 flex-shrink-0" />
//                     <span>{signupError}</span>
//                   </div>
//                 )}
//                 <div className="space-y-2">
//                   <Label htmlFor="company-name">Company name</Label>
//                   <Input
//                     id="company-name"
//                     type="text"
//                     placeholder="Acme Inc"
//                     value={companyName}
//                     onChange={(e) => setCompanyName(e.target.value)}
//                     disabled={isSignupLoading}
//                     required
//                     autoComplete="organization"
//                   />
//                   {fieldErrors.companyName && (
//                     <p className="text-sm text-destructive">{fieldErrors.companyName}</p>
//                   )}
//                 </div>
//                 <div className="space-y-2">
//                   <Label htmlFor="signup-email">Email</Label>
//                   <Input
//                     id="signup-email"
//                     type="email"
//                     placeholder="admin@acme.com"
//                     value={signupEmail}
//                     onChange={(e) => setSignupEmail(e.target.value)}
//                     disabled={isSignupLoading}
//                     required
//                     autoComplete="email"
//                   />
//                   {fieldErrors.email && (
//                     <p className="text-sm text-destructive">{fieldErrors.email}</p>
//                   )}
//                 </div>
//                 <div className="space-y-2">
//                   <Label htmlFor="signup-password">Password</Label>
//                   <Input
//                     id="signup-password"
//                     type="password"
//                     placeholder="At least 8 characters"
//                     value={signupPassword}
//                     onChange={(e) => setSignupPassword(e.target.value)}
//                     disabled={isSignupLoading}
//                     required
//                     autoComplete="new-password"
//                   />
//                   {fieldErrors.password && (
//                     <p className="text-sm text-destructive">{fieldErrors.password}</p>
//                   )}
//                 </div>
//                 <div className="space-y-2">
//                   <Label htmlFor="confirm-password">Confirm password</Label>
//                   <Input
//                     id="confirm-password"
//                     type="password"
//                     placeholder="••••••••"
//                     value={confirmPassword}
//                     onChange={(e) => setConfirmPassword(e.target.value)}
//                     disabled={isSignupLoading}
//                     required
//                     autoComplete="new-password"
//                   />
//                   {fieldErrors.confirmPassword && (
//                     <p className="text-sm text-destructive">{fieldErrors.confirmPassword}</p>
//                   )}
//                 </div>
//                 <Button type="submit" className="w-full" disabled={isSignupLoading}>
//                   {isSignupLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
//                   {isSignupLoading ? "Creating account..." : "Create account"}
//                 </Button>
//               </form>
//             </TabsContent>
//           </Tabs>
//         </CardContent>
//         <CardFooter className="text-center text-sm text-muted-foreground">
//           Demo: admin@demo.test / demo123
//         </CardFooter>
//       </Card>
//     </div>
//   );
// }
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/auth/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { AlertCircle, Loader2 } from "lucide-react";

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

type Mode = "signin" | "signup";

export function Login() {
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState<Mode>("signin");

  // shared fields
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  // signup-only fields
  const [companyName, setCompanyName] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);

  const isSignup = mode === "signup";

  const switchMode = (next: Mode) => {
    if (next === mode || isLoading) return;
    setMode(next);
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
        setError(err instanceof Error ? err.message : "Could not create account");
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
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">
            {isSignup ? "Create your account" : "Welcome back"}
          </CardTitle>
          <CardDescription>
            {isSignup
              ? "Set up a new company account to get started"
              : "Sign in to your company account to continue"}
          </CardDescription>
        </CardHeader>

        <CardContent>
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
                  <p className="text-sm text-destructive">{fieldErrors.companyName}</p>
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
                  <p className="text-sm text-destructive">{fieldErrors.confirmPassword}</p>
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
        </CardContent>

        <CardFooter className="justify-center text-center text-sm text-muted-foreground">
          Demo: admin@demo.test / demo123
        </CardFooter>
      </Card>
    </div>
  );
}