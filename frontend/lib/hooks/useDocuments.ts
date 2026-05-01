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

export function useDocument(documentId?: UUID) {
  return useQuery({
    queryKey: ["document", documentId],
    queryFn: () => api.getDocument(documentId!),
    enabled: Boolean(documentId)
  });
}

export function useDocumentChunks(documentId?: UUID) {
  return useQuery({
    queryKey: ["document-chunks", documentId],
    queryFn: () => api.getDocumentChunks(documentId!, { limit: 100 }),
    enabled: Boolean(documentId)
  });
}

export function useDocumentGraphSummary(documentId?: UUID) {
  return useQuery({
    queryKey: ["document-graph-summary", documentId],
    queryFn: () => api.getDocumentGraphSummary(documentId!),
    enabled: Boolean(documentId)
  });
}

export function useUploadDocument(projectId: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { file: File; title?: string }) => api.uploadDocument({ projectId, ...input }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents", projectId] })
  });
}
