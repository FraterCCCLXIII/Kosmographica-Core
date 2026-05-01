"use client";

import { useParams } from "next/navigation";
import Link from "next/link";

import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useEntities } from "@/lib/hooks/useEntities";

export default function EntitiesPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>();
  const entities = useEntities(projectId);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Entities</h1>
        <p className="text-sm text-muted-foreground">Entity graph nodes extracted from cited chunks.</p>
      </div>
      <ErrorBanner error={entities.error} />
      {entities.data?.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {entities.data.map((entity) => (
            <Card key={entity.id}>
              <CardHeader><CardTitle>{entity.canonical_name}</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-sm text-muted-foreground">
                <p>{entity.entity_type}</p>
                <p>{Array.isArray(entity.metadata.source_chunk_ids) ? entity.metadata.source_chunk_ids.length : 0} source chunk(s)</p>
                <Link
                  className="mr-2 inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-3 text-sm font-medium hover:bg-muted"
                  href={`/workspaces/${workspaceId}/projects/${projectId}/entities/${entity.id}`}
                >
                  Inspect
                </Link>
                <Link
                  className="inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-3 text-sm font-medium hover:bg-muted"
                  href={`/workspaces/${workspaceId}/projects/${projectId}/graph?query=${encodeURIComponent(entity.canonical_name)}`}
                >
                  View in graph
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState title="No entities yet" description="Run document ingestion and graph construction to populate entity nodes." />
      )}
    </div>
  );
}
