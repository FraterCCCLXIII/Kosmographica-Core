"use client";

import { EmptyState } from "@/components/shared/EmptyState";

export default function ClustersPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Clusters</h1>
        <p className="text-sm text-muted-foreground">Cluster schema exists, but clustering implementation is deferred until post-MVP.</p>
      </div>
      <EmptyState title="Clusters are deferred" description="UMAP and HDBSCAN are schema-only for the MVP per project rules." />
    </div>
  );
}
