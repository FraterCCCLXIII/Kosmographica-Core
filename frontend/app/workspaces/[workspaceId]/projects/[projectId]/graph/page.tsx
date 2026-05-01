"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useCallback, useMemo, useRef, useState } from "react";

import { GraphCanvas, type GraphCanvasHandle, type GraphFilters } from "@/components/graph/GraphCanvas";
import { GraphControls } from "@/components/graph/GraphControls";
import { NodeSidePanel } from "@/components/graph/NodeSidePanel";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useGraphEdges, useGraphNodes } from "@/lib/hooks/useGraph";
import type { GraphEdge, GraphNode } from "@/lib/types";

export default function GraphPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const queryClient = useQueryClient();
  const canvasRef = useRef<GraphCanvasHandle | null>(null);
  const nodes = useGraphNodes(projectId);
  const edges = useGraphEdges(projectId);
  const [selectedNodeId, setSelectedNodeId] = useState<string>();
  const [selectedNodeIds, setSelectedNodeIds] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [filters, setFilters] = useState<GraphFilters>({
    nodeTypes: new Set(),
    edgeTypes: new Set()
  });
  const selectedNode = useMemo(
    () => nodes.data?.find((node) => node.id === selectedNodeId),
    [nodes.data, selectedNodeId]
  );

  const onNodeClick = useCallback((nodeId: string) => {
    setSelectedNodeId(nodeId);
    setSelectedNodeIds((current) => new Set(current).add(nodeId));
  }, []);

  const expandNeighborhood = useMutation({
    mutationFn: (nodeId: string) => api.getSubgraph(projectId, { nodeId, depth: 2 }),
    onSuccess: (subgraph) => {
      queryClient.setQueryData<GraphNode[]>(["graph-nodes", projectId], (current = []) => mergeById(current, subgraph.nodes));
      queryClient.setQueryData<GraphEdge[]>(["graph-edges", projectId], (current = []) => mergeById(current, subgraph.edges));
    }
  });

  const saveResearchMap = useMutation({
    mutationFn: () =>
      api.saveResearchNote({
        project_id: projectId,
        title: `Research map ${new Date().toLocaleString()}`,
        body: "Saved graph selection from the graph explorer.",
        graph_node_ids: Array.from(selectedNodeIds),
        metadata: { source: "graph_explorer" }
      })
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Graph explorer</h1>
          <p className="text-sm text-muted-foreground">
            Project-local graph nodes and evidence-backed edges rendered with Sigma.js.
          </p>
        </div>
        <Button disabled={selectedNodeIds.size === 0 || saveResearchMap.isPending} onClick={() => saveResearchMap.mutate()}>
          {saveResearchMap.isPending ? "Saving..." : "Save as Research Map"}
        </Button>
      </div>
      <ErrorBanner error={nodes.error || edges.error || expandNeighborhood.error || saveResearchMap.error} />
      {saveResearchMap.isSuccess ? (
        <div className="rounded-md border border-primary/30 bg-primary/10 p-3 text-sm">
          Research map save request completed.
        </div>
      ) : null}
      <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)_360px]">
        <GraphControls
          nodes={nodes.data ?? []}
          edges={edges.data ?? []}
          filters={filters}
          searchQuery={searchQuery}
          isLayoutRunning={canvasRef.current?.isLayoutRunning ?? false}
          onFiltersChange={setFilters}
          onSearchChange={setSearchQuery}
          onZoomIn={() => canvasRef.current?.zoomIn()}
          onZoomOut={() => canvasRef.current?.zoomOut()}
          onResetLayout={() => canvasRef.current?.resetLayout()}
          onToggleLayout={() => canvasRef.current?.toggleLayout()}
        />
        <Card>
          <CardContent className="p-2">
            {nodes.isLoading || edges.isLoading ? (
              <div className="flex h-[720px] items-center justify-center text-sm text-muted-foreground">Loading graph...</div>
            ) : (nodes.data?.length ?? 0) > 0 ? (
              <GraphCanvas
                ref={canvasRef}
                nodes={nodes.data ?? []}
                edges={edges.data ?? []}
                filters={filters}
                searchQuery={searchQuery}
                selectedNodeId={selectedNodeId}
                onNodeClick={onNodeClick}
              />
            ) : (
              <div className="flex h-[720px] items-center justify-center text-sm text-muted-foreground">
                No graph nodes yet. Ingest documents and run graph construction first.
              </div>
            )}
          </CardContent>
        </Card>
        <NodeSidePanel
          node={selectedNode}
          nodes={nodes.data ?? []}
          edges={edges.data ?? []}
          onExpandNeighborhood={(nodeId) => expandNeighborhood.mutate(nodeId)}
        />
      </div>
    </div>
  );
}

function mergeById<T extends { id: string }>(current: T[], incoming: T[]) {
  const byId = new Map(current.map((item) => [item.id, item]));
  for (const item of incoming) byId.set(item.id, item);
  return Array.from(byId.values());
}
