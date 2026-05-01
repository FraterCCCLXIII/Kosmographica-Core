"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCluster } from "@/lib/hooks/useClusters";

export default function ClusterDetailPage() {
  const { workspaceId, projectId, clusterId } = useParams<{ workspaceId: string; projectId: string; clusterId: string }>();
  const cluster = useCluster(clusterId);
  const topEntities = (Array.isArray(cluster.data?.metadata.top_entities) ? cluster.data.metadata.top_entities : []) as Array<Record<string, unknown>>;
  const sourceChunks = (Array.isArray(cluster.data?.metadata.source_chunks) ? cluster.data.metadata.source_chunks : []) as Array<Record<string, unknown>>;
  const claims = (Array.isArray(cluster.data?.metadata.claims) ? cluster.data.metadata.claims : []) as Array<Record<string, unknown>>;

  return (
    <div className="space-y-6">
      <ErrorBanner error={cluster.error} />
      {cluster.data ? (
        <>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold">{cluster.data.label}</h1>
              <p className="text-sm text-muted-foreground">{cluster.data.description}</p>
            </div>
            <div className="flex gap-2">
              <Link href={`/workspaces/${workspaceId}/projects/${projectId}/graph?query=${encodeURIComponent(cluster.data.label)}`}>
                <Button variant="outline">Open graph for cluster</Button>
              </Link>
              <Link href={`/workspaces/${workspaceId}/projects/${projectId}/chat`}>
                <Button>Ask RAG about this cluster</Button>
              </Link>
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
            <Card>
              <CardHeader><CardTitle>Source chunks</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-sm">
                {sourceChunks.length ? sourceChunks.map((chunk, index) => (
                  <div key={String(chunk.id ?? index)} className="rounded-md border p-3">
                    <p className="font-mono text-xs">{String(chunk.id ?? "")}</p>
                    <p className="text-muted-foreground">{String(chunk.citation ?? "")}</p>
                  </div>
                )) : <EmptyState title="No source chunks" description="This cluster has no source chunk metadata." />}
              </CardContent>
            </Card>

            <div className="space-y-4">
              <Card>
                <CardHeader><CardTitle>Top entities</CardTitle></CardHeader>
                <CardContent className="space-y-2 text-sm">
                  {topEntities.length ? topEntities.map((entity, index) => (
                    <p key={String(entity.name ?? index)}>{String(entity.name ?? "")} <span className="text-muted-foreground">({String(entity.count ?? 0)})</span></p>
                  )) : <p className="text-muted-foreground">No entities found.</p>}
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle>Claims</CardTitle></CardHeader>
                <CardContent className="space-y-2 text-sm">
                  {claims.length ? claims.map((claim, index) => (
                    <p key={String(claim.id ?? index)} className="rounded-md border p-2">{String(claim.text ?? "")}</p>
                  )) : <p className="text-muted-foreground">No claims found.</p>}
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle>Metadata</CardTitle></CardHeader>
                <CardContent>
                  <pre className="overflow-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(cluster.data.metadata, null, 2)}</pre>
                </CardContent>
              </Card>
            </div>
          </div>
        </>
      ) : <p className="text-sm text-muted-foreground">Loading cluster...</p>}
    </div>
  );
}
