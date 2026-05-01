"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { cn } from "@/lib/utils";

const navItems = [
  ["Dashboard", ""],
  ["Documents", "documents"],
  ["Graph", "graph"],
  ["Chat", "chat"],
  ["Entities", "entities"],
  ["Clusters", "clusters"]
] as const;

export function Sidebar() {
  const params = useParams<{ workspaceId?: string; projectId?: string }>();
  if (!params.workspaceId || !params.projectId) {
    return null;
  }
  const base = `/workspaces/${params.workspaceId}/projects/${params.projectId}`;
  return (
    <aside className="hidden w-60 shrink-0 border-r bg-muted/30 p-4 md:block">
      <nav className="space-y-1">
        {navItems.map(([label, path]) => (
          <Link
            key={label}
            href={path ? `${base}/${path}` : base}
            className={cn("block rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-background hover:text-foreground")}
          >
            {label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
