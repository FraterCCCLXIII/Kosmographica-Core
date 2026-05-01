import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { UUID } from "@/lib/types";

export const DEFAULT_GRAPH_EDGE_TYPES = ["contains", "mentions", "supports_claim"];
export const MAX_EDGES_DEFAULT = 500;

export function useGraphNodes(projectId: UUID) {
  return useQuery({ queryKey: ["graph-nodes", projectId], queryFn: () => api.getGraphNodes(projectId) });
}

export function useGraphEdges(projectId: UUID) {
  return useQuery({
    queryKey: ["graph-edges", projectId, DEFAULT_GRAPH_EDGE_TYPES, MAX_EDGES_DEFAULT],
    queryFn: () => api.getGraphEdges(projectId, { edgeTypes: DEFAULT_GRAPH_EDGE_TYPES, limit: MAX_EDGES_DEFAULT })
  });
}

export function useGraphStats(projectId: UUID) {
  return useQuery({ queryKey: ["graph-stats", projectId], queryFn: () => api.getGraphStats(projectId) });
}
