import { forwardRef } from "react";
import { cn } from "@/lib/utils";

export const Sidebar = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("w-64 border-r bg-card flex flex-col", className)}
      {...props}
    />
  )
);
Sidebar.displayName = "Sidebar";