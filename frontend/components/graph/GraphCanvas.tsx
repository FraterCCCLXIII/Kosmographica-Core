"use client";

import Graph from "graphology";
import circular from "graphology-layout/circular";
import forceAtlas2 from "graphology-layout-forceatlas2";
import Sigma from "sigma";
import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";

import { colorForEdgeType, colorForNodeType } from "@/components/graph/graphStyles";
import type { GraphEdge, GraphNode, UUID } from "@/lib/types";

export interface GraphFilters {
  nodeTypes: Set<string>;
  edgeTypes: Set<string>;
  tradition?: string;
  region?: string;
  dateFrom?: string;
  dateTo?: string;
}

export interface GraphCanvasHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  resetLayout: () => void;
  toggleLayout: () => void;
  isLayoutRunning: boolean;
}

interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  filters: GraphFilters;
  searchQuery: string;
  selectedNodeId?: UUID;
  onNodeClick: (nodeId: UUID) => void;
}

export const GraphCanvas = forwardRef<GraphCanvasHandle, GraphCanvasProps>(
  ({ nodes, edges, filters, searchQuery, selectedNodeId, onNodeClick }, ref) => {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const sigmaRef = useRef<Sigma | null>(null);
    const graphRef = useRef<Graph | null>(null);
    const layoutTimerRef = useRef<number | null>(null);
    const [isLayoutRunning, setIsLayoutRunning] = useState(false);
    const dataSignature = useMemo(() => `${nodes.map((node) => node.id).join("|")}::${edges.map((edge) => edge.id).join("|")}`, [nodes, edges]);

    useImperativeHandle(ref, () => ({
      zoomIn: () => {
        const camera = sigmaRef.current?.getCamera();
        camera?.animatedZoom({ duration: 200 });
      },
      zoomOut: () => {
        const camera = sigmaRef.current?.getCamera();
        camera?.animatedUnzoom({ duration: 200 });
      },
      resetLayout: () => {
        const graph = graphRef.current;
        if (!graph) return;
        circular.assign(graph);
        runForceAtlas(graph, 500);
        sigmaRef.current?.refresh();
      },
      toggleLayout: () => {
        if (layoutTimerRef.current) {
          window.clearInterval(layoutTimerRef.current);
          layoutTimerRef.current = null;
          setIsLayoutRunning(false);
          return;
        }
        const graph = graphRef.current;
        if (!graph) return;
        layoutTimerRef.current = window.setInterval(() => {
          runForceAtlas(graph, 10);
          sigmaRef.current?.refresh();
        }, 120);
        setIsLayoutRunning(true);
      },
      isLayoutRunning
    }), [isLayoutRunning]);

    useEffect(() => {
      if (!containerRef.current) return;
      const graph = buildGraph(nodes, edges);
      circular.assign(graph);
      runForceAtlas(graph, 500);

      const sigma = new Sigma(graph, containerRef.current, {
        renderEdgeLabels: false,
        allowInvalidContainer: true
      });
      sigma.on("clickNode", ({ node }) => onNodeClick(String(node)));
      graphRef.current = graph;
      sigmaRef.current = sigma;

      return () => {
        if (layoutTimerRef.current) window.clearInterval(layoutTimerRef.current);
        layoutTimerRef.current = null;
        setIsLayoutRunning(false);
        sigma.kill();
        sigmaRef.current = null;
        graphRef.current = null;
      };
    }, [dataSignature, edges, nodes, onNodeClick]);

    useEffect(() => {
      const sigma = sigmaRef.current;
      if (!sigma) return;
      const normalizedSearch = searchQuery.trim().toLowerCase();
      sigma.setSetting("nodeReducer", (node, data) => {
        const nodeType = String(data.nodeType ?? "");
        const metadata = (data.metadata ?? {}) as Record<string, unknown>;
        const label = String(data.label ?? "");
        const hidden = !matchesNodeFilters(nodeType, metadata, filters);
        const isMatch = normalizedSearch.length > 0 && label.toLowerCase().includes(normalizedSearch);
        return {
          ...data,
          hidden,
          highlighted: isMatch || node === selectedNodeId,
          color: node === selectedNodeId ? "#dc2626" : isMatch ? "#facc15" : data.color,
          zIndex: isMatch || node === selectedNodeId ? 10 : data.zIndex
        };
      });
      sigma.setSetting("edgeReducer", (_edge, data) => {
        const edgeType = String(data.edgeType ?? "");
        return {
          ...data,
          hidden: filters.edgeTypes.size > 0 && !filters.edgeTypes.has(edgeType)
        };
      });
      sigma.refresh();
    }, [filters, searchQuery, selectedNodeId]);

    return <div ref={containerRef} className="h-[720px] min-h-[480px] rounded-lg border bg-card" />;
  }
);
GraphCanvas.displayName = "GraphCanvas";

function buildGraph(nodes: GraphNode[], edges: GraphEdge[]) {
  const graph = new Graph({ multi: true, type: "undirected" });
  const degreeMap = new Map<string, number>();
  for (const edge of edges) {
    degreeMap.set(edge.source_node_id, (degreeMap.get(edge.source_node_id) ?? 0) + 1);
    degreeMap.set(edge.target_node_id, (degreeMap.get(edge.target_node_id) ?? 0) + 1);
  }
  for (const node of nodes) {
    const degree = degreeMap.get(node.id) ?? 0;
    graph.addNode(node.id, {
      label: node.label,
      size: Math.min(18, 4 + Math.sqrt(degree + 1) * 2),
      color: colorForNodeType(node.node_type),
      nodeType: node.node_type,
      metadata: node.metadata,
      zIndex: node.node_type === "document" ? 2 : 1
    });
  }
  for (const edge of edges) {
    if (!graph.hasNode(edge.source_node_id) || !graph.hasNode(edge.target_node_id)) continue;
    graph.addEdgeWithKey(edge.id, edge.source_node_id, edge.target_node_id, {
      label: edge.edge_type,
      size: Math.max(1, Math.min(6, edge.weight)),
      color: colorForEdgeType(edge.edge_type),
      edgeType: edge.edge_type
    });
  }
  return graph;
}

function runForceAtlas(graph: Graph, iterations: number) {
  if (graph.order === 0) return;
  forceAtlas2.assign(graph, {
    iterations,
    settings: {
      ...forceAtlas2.inferSettings(graph),
      gravity: 1,
      scalingRatio: 10
    }
  });
}

function matchesNodeFilters(nodeType: string, metadata: Record<string, unknown>, filters: GraphFilters) {
  if (filters.nodeTypes.size > 0 && !filters.nodeTypes.has(nodeType)) return false;
  if (filters.tradition && String(metadata.tradition ?? "") !== filters.tradition) return false;
  if (filters.region && String(metadata.region ?? "") !== filters.region) return false;
  const date = String(metadata.date ?? "");
  if (filters.dateFrom && date && date < filters.dateFrom) return false;
  if (filters.dateTo && date && date > filters.dateTo) return false;
  return true;
}
