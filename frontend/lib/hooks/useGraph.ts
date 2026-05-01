import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { UUID } from "@/lib/types";

export function useGraphNodes(projectId: UUID) {
  return useQuery({ queryKey: ["graph-nodes", projectId], queryFn: () => api.getGraphNodes(projectId) });
}

export function useGraphEdges(projectId: UUID) {
  return useQuery({ queryKey: ["graph-edges", projectId], queryFn: () => api.getGraphEdges(projectId) });
}
