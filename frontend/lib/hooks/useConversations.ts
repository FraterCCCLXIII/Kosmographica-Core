import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Conversation, JsonObject, UUID } from "@/lib/types";

interface ConversationListOptions {
  projectId?: UUID | "none";
  limit?: number;
  offset?: number;
  query?: string;
  dateFrom?: string;
  dateTo?: string;
}

export const RECENT_CONVERSATION_LIMIT = 20;

export function useConversations(workspaceId?: UUID, options: ConversationListOptions = {}) {
  return useQuery({
    queryKey: ["conversations", workspaceId, options],
    queryFn: () => api.listConversations(workspaceId!, options),
    enabled: Boolean(workspaceId)
  });
}

export function useRecentConversations(workspaceId?: UUID) {
  return useConversations(workspaceId, { limit: RECENT_CONVERSATION_LIMIT });
}

export function useConversation(workspaceId?: UUID, conversationId?: UUID) {
  return useQuery({
    queryKey: ["conversation", workspaceId, conversationId],
    queryFn: () => api.getConversation(workspaceId!, conversationId!),
    enabled: Boolean(workspaceId && conversationId),
    refetchInterval: (query) => {
      const messages = query.state.data?.messages ?? [];
      return messages.some((message) => message.status === "generating" || message.status === "queued") ? 2000 : false;
    }
  });
}

export function useCreateConversation(workspaceId?: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      workspace_id: UUID;
      project_id?: UUID | null;
      title?: string;
      mode?: string;
      context?: JsonObject;
      metadata?: JsonObject;
    }) => api.createConversation(input),
    onSuccess: (conversation) => {
      queryClient.invalidateQueries({ queryKey: ["conversations", workspaceId ?? conversation.workspace_id] });
    }
  });
}

export function useSendConversationMessage(workspaceId?: UUID, conversationId?: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { content: string; mode?: string; k?: number; filters?: JsonObject; project_ids?: UUID[]; metadata?: JsonObject }) =>
      api.sendConversationMessage(workspaceId!, conversationId!, input),
    onSuccess: (conversation) => {
      queryClient.setQueryData<Conversation>(["conversation", workspaceId, conversationId], conversation);
      queryClient.invalidateQueries({ queryKey: ["conversations", workspaceId] });
    }
  });
}

export function useUpdateConversation(workspaceId?: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { conversationId: UUID; title?: string; status?: string; context?: JsonObject; metadata?: JsonObject }) =>
      api.updateConversation(workspaceId!, input.conversationId, {
        title: input.title,
        status: input.status,
        context: input.context,
        metadata: input.metadata
      }),
    onSuccess: (conversation) => {
      queryClient.setQueryData<Conversation>(["conversation", workspaceId, conversation.id], conversation);
      queryClient.invalidateQueries({ queryKey: ["conversations", workspaceId] });
    }
  });
}

export function useDeleteConversation(workspaceId?: UUID) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (conversationId: UUID) => api.deleteConversation(workspaceId!, conversationId),
    onSuccess: (_, conversationId) => {
      queryClient.invalidateQueries({ queryKey: ["conversations", workspaceId] });
      queryClient.removeQueries({ queryKey: ["conversation", workspaceId, conversationId] });
    }
  });
}
