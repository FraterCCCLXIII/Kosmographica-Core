"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useEntityDetail } from "@/lib/hooks/useEntities";

export default function EntityDetailPage() {
  const { workspaceId, projectId, entityId } = useParams<{ workspaceId: string; projectId: string; entityId: string }>();
  const detail = useEntityDetail(entityId);
  const graphNodeId = detail.data?.graph_node?.id;

  return (
    <div className="space-y-6">
      <ErrorBanner error={detail.error} />
      {detail.isLoading ? <p className="text-sm text-muted-foreground">Loading entity...</p> : null}
      {detail.data ? (
        <>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold">{detail.data.entity.canonical_name}</h1>
              <p className="text-sm text-muted-foreground">{detail.data.entity.id}</p>
            </div>
            <div className="flex gap-2">
              <StatusBadge status={detail.data.entity.entity_type} />
              <Link
                className="inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-3 text-sm font-medium hover:bg-muted"
                href={`/workspaces/${workspaceId}/projects/${projectId}/graph${graphNodeId ? `?nodeId=${graphNodeId}` : `?query=${encodeURIComponent(detail.data.entity.canonical_name)}`}`}
              >
                Open graph around entity
              </Link>
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className="space-y-4">
              <Card>
                <CardHeader><CardTitle>Mentioning chunks</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  {detail.data.chunks.length ? detail.data.chunks.map((chunk) => (
                    <div key={chunk.id} className="rounded-md border p-3 text-sm">
                      <p className="font-medium">{chunk.citation}</p>
                      <p className="mt-2 whitespace-pre-wrap text-muted-foreground">{chunk.text}</p>
                    </div>
                  )) : <EmptyState title="No chunks" description="No source chunks are linked to this entity." />}
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle>Related claims</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  {detail.data.claims.length ? detail.data.claims.map((claim) => (
                    <div key={claim.id} className="rounded-md border p-3 text-sm">
                      <p className="font-medium">{claim.subject} {claim.predicate} {claim.object}</p>
                      <p className="text-muted-foreground">Confidence {claim.confidence.toFixed(2)}</p>
                      <p className="mt-2 text-muted-foreground">{claim.evidence_text}</p>
                    </div>
                  )) : <p className="text-sm text-muted-foreground">No directly related claims found.</p>}
                </CardContent>
              </Card>
            </div>

            <div className="space-y-4">
              <Card>
                <CardHeader><CardTitle>Entity metadata</CardTitle></CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <p>Aliases: {detail.data.entity.aliases.length ? detail.data.entity.aliases.join(", ") : "None"}</p>
                  <pre className="overflow-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(detail.data.entity.metadata, null, 2)}</pre>
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle>Connected graph nodes</CardTitle></CardHeader>
                <CardContent className="space-y-2 text-sm">
                  {detail.data.connected_nodes.slice(0, 20).map((node) => (
                    <p key={node.id} className="rounded-md border p-2">{node.label} <span className="text-muted-foreground">({node.node_type})</span></p>
                  ))}
                </CardContent>
              </Card>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
