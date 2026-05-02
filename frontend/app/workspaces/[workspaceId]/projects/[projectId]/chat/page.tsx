"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { Card, CardContent } from "@/components/ui/card";
import { useConversations } from "@/lib/hooks/useConversations";

export default function ChatPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>();
  const router = useRouter();
  const conversations = useConversations(workspaceId, { projectId, limit: 1 });

  useEffect(() => {
    if (!conversations.data) return;
    const [latestConversation] = conversations.data.items;
    if (latestConversation) {
      router.replace(`/workspaces/${workspaceId}/conversations/${latestConversation.id}`);
      return;
    }
    router.replace(`/workspaces/${workspaceId}/conversations/new?project_id=${projectId}`);
  }, [conversations.data, projectId, router, workspaceId]);

  return (
    <div className="mx-auto max-w-2xl">
      <ErrorBanner error={conversations.error} />
      <Card>
        <CardContent className="py-8 text-sm text-muted-foreground">
          Redirecting to the latest project conversation...
        </CardContent>
      </Card>
    </div>
  );
}
