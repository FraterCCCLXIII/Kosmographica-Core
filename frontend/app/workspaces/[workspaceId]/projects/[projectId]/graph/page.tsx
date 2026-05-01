"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { GraphCanvas, type GraphCanvasHandle, type GraphFilters } from "@/components/graph/GraphCanvas";
import { GraphControls } from "@/components/graph/GraphControls";
import { NodeSidePanel } from "@/components/graph/NodeSidePanel";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { DEFAULT_GRAPH_EDGE_TYPES, MAX_EDGES_DEFAULT, useGraphEdges, useGraphNodes, useGraphStats } from "@/lib/hooks/useGraph";
import type { GraphEdge, GraphNode } from "@/lib/types";

const LARGE_GRAPH_NODE_LIMIT = 1_000;
const LARGE_GRAPH_EDGE_LIMIT = 2_000;

export default function GraphPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const canvasRef = useRef<GraphCanvasHandle | null>(null);
  const nodes = useGraphNodes(projectId);
  const edges = useGraphEdges(projectId);
  const stats = useGraphStats(projectId);
  const [selectedNodeId, setSelectedNodeId] = useState<string>();
  const [selectedNodeIds, setSelectedNodeIds] = useState<Set<string>>(new Set());
  const [isLayoutRunning, setIsLayoutRunning] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeGraph, setActiveGraph] = useState<{ nodes: GraphNode[]; edges: GraphEdge[]; query: string; seedNodeIds: string[] }>();
  const [filters, setFilters] = useState<GraphFilters>({
    nodeTypes: new Set(),
    edgeTypes: new Set()
  });
  const graphNodes = useMemo(() => activeGraph?.nodes ?? nodes.data ?? [], [activeGraph?.nodes, nodes.data]);
  const graphEdges = useMemo(() => activeGraph?.edges ?? edges.data ?? [], [activeGraph?.edges, edges.data]);
  const selectedNode = useMemo(
    () => graphNodes.find((node) => node.id === selectedNodeId),
    [graphNodes, selectedNodeId]
  );

  useEffect(() => {
    const nodeId = searchParams.get("nodeId");
    if (!nodeId) return;
    setSelectedNodeId(nodeId);
    setSelectedNodeIds((current) => new Set(current).add(nodeId));
  }, [searchParams]);

  const onNodeClick = useCallback((nodeId: string) => {
    setSelectedNodeId(nodeId);
    setSelectedNodeIds((current) => new Set(current).add(nodeId));
  }, []);

  const expandNeighborhood = useMutation({
    mutationFn: (nodeId: string) => api.getSubgraph(projectId, { nodeId, depth: 2 }),
    onSuccess: (subgraph) => {
      setActiveGraph((current) =>
        current
          ? {
              ...current,
              nodes: mergeById(current.nodes, subgraph.nodes),
              edges: mergeById(current.edges, subgraph.edges)
            }
          : undefined
      );
      queryClient.setQueryData<GraphNode[]>(["graph-nodes", projectId], (current = []) => mergeById(current, subgraph.nodes));
      queryClient.setQueryData<GraphEdge[]>(["graph-edges", projectId], (current = []) => mergeById(current, subgraph.edges));
    }
  });

  const searchGraph = useMutation({
    mutationFn: (query: string) =>
      api.searchGraph(projectId, {
        query,
        depth: 1,
        seedLimit: 20,
        nodeLimit: 250,
        edgeLimit: MAX_EDGES_DEFAULT,
        edgeTypes: DEFAULT_GRAPH_EDGE_TYPES
      }),
    onSuccess: (result) => {
      setActiveGraph({
        nodes: result.nodes,
        edges: result.edges,
        query: result.query,
        seedNodeIds: result.seed_node_ids
      });
      setSelectedNodeIds(new Set(result.seed_node_ids));
      setSelectedNodeId(result.seed_node_ids[0]);
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
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["research-notes", projectId] });
    }
  });

  const researchNotes = useQuery({
    queryKey: ["research-notes", projectId],
    queryFn: () => api.listResearchNotes(projectId)
  });

  const deleteResearchNote = useMutation({
    mutationFn: (noteId: string) => api.deleteResearchNote(noteId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["research-notes", projectId] });
    }
  });

  const isLargeGraph =
    (stats.data?.node_count ?? 0) > LARGE_GRAPH_NODE_LIMIT ||
    (stats.data?.edge_count ?? 0) > LARGE_GRAPH_EDGE_LIMIT;
  const shouldShowLargeGraphWarning = isLargeGraph && !activeGraph;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Graph explorer</h1>
          <p className="text-sm text-muted-foreground">
            Project-local graph nodes and evidence-backed edges rendered with Sigma.js.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" disabled={selectedNodeIds.size === 0} onClick={() => setSelectedNodeIds(new Set())}>
            Clear selection ({selectedNodeIds.size})
          </Button>
          <Button disabled={selectedNodeIds.size === 0 || saveResearchMap.isPending} onClick={() => saveResearchMap.mutate()}>
            {saveResearchMap.isPending ? "Saving..." : "Save as Research Map"}
          </Button>
        </div>
      </div>
      <ErrorBanner error={nodes.error || edges.error || stats.error || searchGraph.error || expandNeighborhood.error || saveResearchMap.error} />
      {saveResearchMap.isSuccess ? (
        <div className="rounded-md border border-primary/30 bg-primary/10 p-3 text-sm">
          Research map save request completed.
        </div>
      ) : null}
      <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)_360px]">
        <div className="space-y-4">
          <GraphControls
            nodes={graphNodes}
            edges={graphEdges}
            filters={filters}
            searchQuery={searchQuery}
            isLayoutRunning={isLayoutRunning}
            isSearchLoading={searchGraph.isPending}
            hasSearchResults={Boolean(activeGraph)}
            onFiltersChange={setFilters}
            onSearchChange={setSearchQuery}
            onSearchSubmit={() => {
              const query = searchQuery.trim();
              if (query) searchGraph.mutate(query);
            }}
            onClearSearch={() => {
              setSearchQuery("");
              setActiveGraph(undefined);
              setSelectedNodeId(undefined);
              setSelectedNodeIds(new Set());
            }}
            onZoomIn={() => canvasRef.current?.zoomIn()}
            onZoomOut={() => canvasRef.current?.zoomOut()}
            onResetLayout={() => canvasRef.current?.resetLayout()}
            onToggleLayout={() => canvasRef.current?.toggleLayout()}
          />
          <Card>
            <CardHeader>
              <CardTitle>Saved research maps</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {researchNotes.data?.filter((note) => note.metadata.source === "graph_explorer").length ? (
                researchNotes.data
                  .filter((note) => note.metadata.source === "graph_explorer")
                  .map((note) => (
                    <div key={note.id} className="rounded-md border p-3 text-sm">
                      <p className="font-medium">{note.title}</p>
                      <p className="text-muted-foreground">{note.graph_node_ids.length} node(s)</p>
                      <Button className="mt-2" size="sm" variant="outline" onClick={() => deleteResearchNote.mutate(note.id)}>
                        Delete
                      </Button>
                    </div>
                  ))
              ) : (
                <p className="text-sm text-muted-foreground">No saved graph selections yet.</p>
              )}
            </CardContent>
          </Card>
        </div>
        <Card>
          <CardContent className="p-2">
            {nodes.isLoading || edges.isLoading || stats.isLoading ? (
              <div className="flex h-[720px] items-center justify-center text-sm text-muted-foreground">Loading graph...</div>
            ) : shouldShowLargeGraphWarning ? (
              <LargeGraphWarning
                nodeCount={stats.data?.node_count ?? nodes.data?.length ?? 0}
                edgeCount={stats.data?.edge_count ?? 0}
                loadedEdgeCount={edges.data?.length ?? 0}
              />
            ) : graphNodes.length > 0 ? (
              <GraphCanvas
                ref={canvasRef}
                nodes={graphNodes}
                edges={graphEdges}
                filters={filters}
                searchQuery={activeGraph ? "" : searchQuery}
                selectedNodeId={selectedNodeId}
                selectedNodeIds={selectedNodeIds}
                onNodeClick={onNodeClick}
                onLayoutRunningChange={setIsLayoutRunning}
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
          nodes={graphNodes}
          edges={graphEdges}
          onExpandNeighborhood={(nodeId) => expandNeighborhood.mutate(nodeId)}
          isExpanding={expandNeighborhood.isPending}
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

function LargeGraphWarning({
  nodeCount,
  edgeCount,
  loadedEdgeCount
}: {
  nodeCount: number;
  edgeCount: number;
  loadedEdgeCount: number;
}) {
  return (
    <div className="flex h-[720px] items-center justify-center p-8">
      <div className="max-w-xl space-y-4 rounded-lg border bg-muted/30 p-6 text-center">
        <h2 className="text-lg font-semibold">Large graph detected</h2>
        <p className="text-sm text-muted-foreground">
          This project has {nodeCount.toLocaleString()} nodes and {edgeCount.toLocaleString()} edges. Rendering the full graph can freeze the browser.
        </p>
        <p className="text-sm text-muted-foreground">
          The page loaded a bounded overview of {loadedEdgeCount.toLocaleString()} edges using {DEFAULT_GRAPH_EDGE_TYPES.join(", ")} with a limit of {MAX_EDGES_DEFAULT}.
        </p>
        <p className="text-sm text-muted-foreground">
          Use node search or expand a specific neighborhood from an entity/document view. `co_occurs_with` edges are intentionally excluded from the default graph view.
        </p>
      </div>
    </div>
  );
}
