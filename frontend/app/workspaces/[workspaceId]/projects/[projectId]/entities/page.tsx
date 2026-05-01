"use client";

import { useParams } from "next/navigation";

import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useGraphNodes } from "@/lib/hooks/useGraph";

export default function EntitiesPage() {
  const { projectId } = useParams<{ projectId: string }>();
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
              <CardContent className="text-sm text-muted-foreground">{String(entity.metadata.entity_type ?? "entity")}</CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState title="No entities yet" description="Run document ingestion and graph construction to populate entity nodes." />
      )}
    </div>
  );
}
