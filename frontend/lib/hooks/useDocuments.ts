import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { DocumentStatus, UUID } from "@/lib/types";

const ACTIVE_DOCUMENT_STATUSES = new Set<DocumentStatus>([
  "pending",
  "processing",
  "parsing",
  "chunking",
  "embedding",
  "extracting"
]);

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
      return status && ACTIVE_DOCUMENT_STATUSES.has(status) ? 2000 : false;
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

export function useProcessingTimeline(documentId?: UUID) {
  return useQuery({
    queryKey: ["processing-timeline", documentId],
    queryFn: () => api.getProcessingTimeline(documentId!),
    enabled: Boolean(documentId),
    refetchInterval: (query) => {
      const status = query.state.data?.document_status;
      return status && ACTIVE_DOCUMENT_STATUSES.has(status) ? 2000 : false;
    }
  });
}

export function useReprocessDocument(documentId?: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.triggerProcessing(documentId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["document", documentId] });
      queryClient.invalidateQueries({ queryKey: ["document-status", documentId] });
      queryClient.invalidateQueries({ queryKey: ["processing-timeline", documentId] });
    }
  });
}

export function useRetryProcessingJob(documentId?: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: UUID) => api.retryProcessingJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["document", documentId] });
      queryClient.invalidateQueries({ queryKey: ["document-status", documentId] });
      queryClient.invalidateQueries({ queryKey: ["processing-timeline", documentId] });
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

export function useUploadDocuments(projectId: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { files: File[] }) => {
      const results = await Promise.allSettled(
        input.files.map(async (file) => ({
          fileName: file.name,
          document: await api.uploadDocument({ projectId, file })
        }))
      );
      const uploaded = results.flatMap((result) => (result.status === "fulfilled" ? [result.value.document] : []));
      const failed = results.flatMap((result, index) =>
        result.status === "rejected"
          ? [{ fileName: input.files[index]?.name ?? "Unknown file", error: result.reason }]
          : []
      );
      if (!uploaded.length && failed.length) {
        throw new Error(`Upload failed for ${failed.map((failure) => failure.fileName).join(", ")}`);
      }
      return { uploaded, failed };
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["documents", projectId] })
  });
}

export function useDeleteDocument(projectId: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: UUID) => api.deleteDocument(documentId),
    onSuccess: (_, documentId) => {
      queryClient.invalidateQueries({ queryKey: ["documents", projectId] });
      queryClient.removeQueries({ queryKey: ["document", documentId] });
      queryClient.removeQueries({ queryKey: ["document-status", documentId] });
      queryClient.removeQueries({ queryKey: ["document-chunks", documentId] });
      queryClient.removeQueries({ queryKey: ["document-graph-summary", documentId] });
      queryClient.removeQueries({ queryKey: ["processing-timeline", documentId] });
    }
  });
}
