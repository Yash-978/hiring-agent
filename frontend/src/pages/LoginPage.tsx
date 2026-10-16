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
          <Login mode={mode} onSwitchMode={setMode} />
        </CardContent>

        <CardFooter className="justify-center text-center text-sm text-muted-foreground">
          Demo: admin@demo.test / demo123
        </CardFooter>
      </Card>
    </div>
  );
}