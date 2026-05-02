import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { UUID } from "@/lib/types";

export const DEFAULT_GRAPH_EDGE_TYPES = ["contains", "mentions", "supports_claim"];
export const OPTIONAL_GRAPH_EDGE_TYPES = ["semantically_similar", "co_occurs_with"];
export const ALL_GRAPH_EDGE_TYPES = [...DEFAULT_GRAPH_EDGE_TYPES, ...OPTIONAL_GRAPH_EDGE_TYPES];
export const MAX_EDGES_DEFAULT = 500;
export const MAX_NODES_DEFAULT = 500;
export const MAX_EDGES_API_LIMIT = 10_000;

export function useGraphNodes(projectId: UUID) {
  return useQuery({
    queryKey: ["graph-nodes", projectId, MAX_NODES_DEFAULT],
    queryFn: () => api.getGraphNodes(projectId, { limit: MAX_NODES_DEFAULT })
  });
}

export function useGraphEdges(projectId: UUID, limit = MAX_EDGES_DEFAULT, edgeTypes: string[] = DEFAULT_GRAPH_EDGE_TYPES) {
  return useQuery({
    queryKey: ["graph-edges", projectId, edgeTypes, limit],
    queryFn: () => api.getGraphEdges(projectId, { edgeTypes, limit })
  });
}

export function useGraphStats(projectId: UUID) {
  return useQuery({ queryKey: ["graph-stats", projectId], queryFn: () => api.getGraphStats(projectId) });
}
