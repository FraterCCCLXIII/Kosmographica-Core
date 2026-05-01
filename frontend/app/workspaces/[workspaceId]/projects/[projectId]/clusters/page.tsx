"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useClusters, useGenerateClusters } from "@/lib/hooks/useClusters";

export default function ClustersPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>();
  const clusters = useClusters(projectId);
  const generate = useGenerateClusters(projectId);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
        <h1 className="text-2xl font-semibold">Clusters</h1>
          <p className="text-sm text-muted-foreground">Conservative document and evidence clusters generated from chunks, entities, and claims.</p>
        </div>
        <Button disabled={generate.isPending} onClick={() => generate.mutate()}>
          {generate.isPending ? "Generating..." : "Generate clusters"}
        </Button>
      </div>
      <ErrorBanner error={clusters.error || generate.error} />
      {clusters.data?.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {clusters.data.map((cluster) => (
            <Card key={cluster.id}>
              <CardHeader><CardTitle>{cluster.label}</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-sm">
                <p className="text-muted-foreground">{cluster.description}</p>
                <p>{Array.isArray(cluster.metadata.chunk_ids) ? cluster.metadata.chunk_ids.length : 0} chunk(s)</p>
                <p className="text-muted-foreground">{cluster.algorithm}</p>
                <Link
                  className="inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-3 text-sm font-medium hover:bg-muted"
                  href={`/workspaces/${workspaceId}/projects/${projectId}/clusters/${cluster.id}`}
                >
                  Inspect cluster
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState title="No clusters yet" description="Generate conservative clusters once documents are graph-ready." />
      )}
    </div>
  );
}
