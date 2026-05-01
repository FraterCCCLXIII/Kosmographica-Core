import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { UUID } from "@/lib/types";

export function useClusters(projectId: UUID) {
  return useQuery({ queryKey: ["clusters", projectId], queryFn: () => api.listClusters(projectId) });
}

export function useGenerateClusters(projectId: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.generateClusters(projectId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["clusters", projectId] })
  });
}

export function useCluster(clusterId?: UUID) {
  return useQuery({
    queryKey: ["cluster", clusterId],
    queryFn: () => api.getCluster(clusterId!),
    enabled: Boolean(clusterId)
  });
}
