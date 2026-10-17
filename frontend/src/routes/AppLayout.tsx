import { useAuth } from "@/auth/useAuth";
import { Link, useLocation, Outlet } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { LogOut, Users, FileCheck, AlertTriangle, Briefcase } from "lucide-react";
import { useMeta } from "@/lib/useMeta";

const navigation = [
  { name: "Candidates", href: "/candidates", icon: Users },
  { name: "Jobs", href: "/jobs", icon: Briefcase },
  { name: "Approvals", href: "/approvals", icon: FileCheck },
];

export function AppLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const { data: meta } = useMeta();

  return (
    <div className="flex h-screen bg-background">
      <aside className="w-64 border-r bg-card flex flex-col">
        <div className="p-4 border-b">
          <h1 className="text-xl font-bold">Hiring Agent</h1>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href;
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                }`}
              >
                <item.icon className="h-4 w-4" />
                {item.name}
              </Link>
            );
          })}
        </nav>
        <div className="p-4 border-t">
          <div className="flex items-center gap-3 px-3 py-2 text-sm text-muted-foreground">
            <span className="truncate">{user?.email}</span>
          </div>
          <Button
            variant="ghost"
            className="w-full justify-start gap-2 mt-2"
            onClick={logout}
          >
            <LogOut className="h-4 w-4" />
            Logout
          </Button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto flex flex-col">
        {meta?.demo_mode && (
          <div
            role="status"
            className="w-full bg-amber-500/15 border-b border-amber-500/30 px-4 py-2 text-center text-xs sm:text-sm font-medium text-amber-900 dark:text-amber-200 flex items-center justify-center gap-2"
          >
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
            <span>Demo mode: scores come from a simple keyword matcher, not a real AI</span>
          </div>
        )}
        <div className="flex-1">
          <Outlet />
        </div>
      </main>
    </div>
  );
}