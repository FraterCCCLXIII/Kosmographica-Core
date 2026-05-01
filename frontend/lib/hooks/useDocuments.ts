import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { UUID } from "@/lib/types";

export function useDocuments(projectId: UUID) {
  return useQuery({ queryKey: ["documents", projectId], queryFn: () => api.listDocuments(projectId) });
}

export function useDocumentStatus(documentId?: UUID) {
  return useQuery({
    queryKey: ["document-status", documentId],
    queryFn: () => api.getDocumentStatus(documentId!),
    enabled: Boolean(documentId),
    refetchInterval: (query) => {
      const status = query.state.data?.document_status;
      return status === "pending" || status === "processing" ? 2000 : false;
    }
  });
}

export function useUploadDocument(projectId: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { file: File; title?: string }) => api.uploadDocument({ projectId, ...input }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents", projectId] })
  });
}
