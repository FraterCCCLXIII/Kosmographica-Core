import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { UUID } from "@/lib/types";

export function useEntities(projectId: UUID) {
  return useQuery({ queryKey: ["entities", projectId], queryFn: () => api.listEntities(projectId) });
}

export function useEntityDetail(entityId?: UUID) {
  return useQuery({
    queryKey: ["entity-detail", entityId],
    queryFn: () => api.getEntityDetail(entityId!),
    enabled: Boolean(entityId)
  });
}
