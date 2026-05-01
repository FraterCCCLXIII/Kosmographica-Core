"use client";

import { Network } from "lucide-react";

import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { GraphEdge, GraphNode } from "@/lib/types";

interface NodeSidePanelProps {
  node?: GraphNode;
  nodes: GraphNode[];
  edges: GraphEdge[];
  onExpandNeighborhood: (nodeId: string) => void;
  isExpanding?: boolean;
}

export function NodeSidePanel({ node, nodes, edges, onExpandNeighborhood, isExpanding = false }: NodeSidePanelProps) {
  if (!node) {
    return (
      <Card className="h-full">
        <CardHeader>
          <CardTitle>Node details</CardTitle>
          <CardDescription>Select a node to inspect provenance and connected evidence.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const connectedEdges = edges.filter((edge) => edge.source_node_id === node.id || edge.target_node_id === node.id);
  const connectedNodeById = new Map(nodes.map((item) => [item.id, item]));
  const chunkText = typeof node.metadata.text === "string" ? node.metadata.text : undefined;
  const citation = typeof node.metadata.citation === "string" ? node.metadata.citation : undefined;
  const mentioningChunks = connectedEdges
    .filter((edge) => edge.edge_type === "mentions" || edge.edge_type === "chunk_mentions_entity")
    .map((edge) => connectedNodeById.get(edge.source_node_id))
    .filter((item): item is GraphNode => Boolean(item && item.node_type === "chunk"));

  return (
    <Card className="h-full overflow-hidden">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>{node.label}</CardTitle>
            <CardDescription>{node.id}</CardDescription>
          </div>
          <StatusBadge status={node.node_type} />
        </div>
      </CardHeader>
      <CardContent className="max-h-[660px] space-y-5 overflow-auto">
        <section className="space-y-2">
          <h3 className="text-sm font-medium">Metadata</h3>
          <pre className="overflow-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(node.metadata, null, 2)}</pre>
        </section>

        {node.node_type === "chunk" ? (
          <section className="space-y-2">
            <h3 className="text-sm font-medium">Chunk evidence</h3>
            <p className="text-sm text-muted-foreground">{citation ?? String(node.metadata.document_id ?? "Citation not included in node metadata.")}</p>
            <div className="rounded-md border p-3 text-sm">
              {chunkText ?? "Full chunk text is not included in the current graph node response."}
            </div>
          </section>
        ) : null}

        {node.node_type === "entity" ? (
          <section className="space-y-2">
            <h3 className="text-sm font-medium">Mentioning chunks</h3>
            {mentioningChunks.length ? mentioningChunks.map((chunk) => (
              <div key={chunk.id} className="rounded-md border p-3 text-sm">
                <p className="font-medium">{chunk.label}</p>
                <p className="text-muted-foreground">{chunk.id}</p>
              </div>
            )) : <p className="text-sm text-muted-foreground">No chunk mention edges are loaded for this node.</p>}
          </section>
        ) : null}

        {node.node_type === "document" ? (
          <section className="space-y-2">
            <h3 className="text-sm font-medium">Document metadata</h3>
            <p className="text-sm text-muted-foreground">Source type: {String(node.metadata.source_type ?? "unknown")}</p>
            <p className="text-sm text-muted-foreground">Source URI: {String(node.metadata.source_uri ?? "not provided")}</p>
          </section>
        ) : null}

        <section className="space-y-2">
          <h3 className="text-sm font-medium">Connected edges</h3>
          {connectedEdges.map((edge) => {
            const otherNodeId = edge.source_node_id === node.id ? edge.target_node_id : edge.source_node_id;
            const otherNode = connectedNodeById.get(otherNodeId);
            return (
              <div key={edge.id} className="rounded-md border p-3 text-sm">
                <p className="font-medium">{edge.edge_type}</p>
                <p className="text-muted-foreground">to {otherNode?.label ?? otherNodeId}</p>
                <p className="text-muted-foreground">evidence chunk {edge.evidence_chunk_id}</p>
              </div>
            );
          })}
        </section>

        <Button className="w-full" disabled={isExpanding} onClick={() => onExpandNeighborhood(node.id)}>
          <Network className="mr-2 h-4 w-4" />
          {isExpanding ? "Expanding..." : "Expand neighborhood"}
        </Button>
      </CardContent>
    </Card>
  );
}
