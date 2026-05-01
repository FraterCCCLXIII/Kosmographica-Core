import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { UUID } from "@/lib/types";

export function useProjects(workspaceId: UUID) {
  return useQuery({ queryKey: ["projects", workspaceId], queryFn: () => api.listProjects(workspaceId) });
}

export function useCreateProject(workspaceId: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.createProject.bind(null, workspaceId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects", workspaceId] })
  });
}
