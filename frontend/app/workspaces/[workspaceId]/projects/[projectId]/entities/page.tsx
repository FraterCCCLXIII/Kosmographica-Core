"use client";

import { useParams } from "next/navigation";
import Link from "next/link";

import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useGraphNodes } from "@/lib/hooks/useGraph";

export default function EntitiesPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>();
  const nodes = useGraphNodes(projectId);
  const entities = nodes.data?.filter((node) => node.node_type === "entity") ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Entities</h1>
        <p className="text-sm text-muted-foreground">Entity graph nodes extracted from cited chunks.</p>
      </div>
      <ErrorBanner error={nodes.error} />
      {entities.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {entities.map((entity) => (
            <Card key={entity.id}>
              <CardHeader><CardTitle>{entity.label}</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-sm text-muted-foreground">
                <p>{String(entity.metadata.entity_type ?? "entity")}</p>
                <p>{Array.isArray(entity.metadata.source_chunk_ids) ? entity.metadata.source_chunk_ids.length : 0} source chunk(s)</p>
                <Link
                  className="inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-3 text-sm font-medium hover:bg-muted"
                  href={`/workspaces/${workspaceId}/projects/${projectId}/graph?nodeId=${entity.id}`}
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
