"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

export function Header() {
  const params = useParams<{ workspaceId?: string; projectId?: string }>();
  return (
    <header className="border-b bg-background px-6 py-4">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/workspaces" className="font-medium text-foreground">
          Kosmographica
        </Link>
        {params.workspaceId ? (
          <>
            <span>/</span>
            <Link href={`/workspaces/${params.workspaceId}`}>workspace {params.workspaceId.slice(0, 8)}</Link>
          </>
        ) : null}
        {params.projectId ? (
          <>
            <span>/</span>
            <Link href={`/workspaces/${params.workspaceId}/projects/${params.projectId}`}>project {params.projectId.slice(0, 8)}</Link>
          </>
        ) : null}
      </div>
    </header>
  );
}
