import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Login, type Mode } from "./Login";

export function LoginPage() {
  const [mode, setMode] = useState<Mode>("signin");
  const isSignup = mode === "signup";

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-semibold tracking-tight">Hiring Agent</h1>
          <p className="text-sm text-muted-foreground">
            Agents prepare. Humans decide.
          </p>
        </div>

        <Card>
          <CardHeader className="text-center">
            <CardTitle className="text-xl">
              {isSignup ? "Create your account" : "Welcome back"}
            </CardTitle>
            <CardDescription>
              {isSignup
                ? "Set up a new company account to get started"
                : "Sign in to your company account to continue"}
            </CardDescription>
          </CardHeader>

          <CardContent>
            <Login mode={mode} onSwitchMode={setMode} />
          </CardContent>

          {import.meta.env.DEV && !isSignup && (
            <CardFooter className="justify-center text-xs text-muted-foreground">
              Demo: admin@demo.test / demo123
            </CardFooter>
          )}
        </Card>
      </div>
    </main>
  );
}