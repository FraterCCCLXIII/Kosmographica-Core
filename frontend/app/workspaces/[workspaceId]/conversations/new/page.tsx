"use client";

import { FormEvent, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";

import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useCreateConversation } from "@/lib/hooks/useConversations";
import { useProjects } from "@/lib/hooks/useProjects";
import type { JsonObject } from "@/lib/types";

export default function NewConversationPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialProjectId = searchParams.get("project_id");
  const [title, setTitle] = useState("New conversation");
  const [mode, setMode] = useState("single");
  const [projectId, setProjectId] = useState<string>(initialProjectId ?? "none");
  const [openingQuestion, setOpeningQuestion] = useState("");
  const projects = useProjects(workspaceId);
  const createConversation = useCreateConversation(workspaceId);
  const context = useMemo(() => contextFromSearchParams(searchParams), [searchParams]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const conversation = await createConversation.mutateAsync({
      workspace_id: workspaceId,
      project_id: projectId === "none" ? null : projectId,
      title,
      mode,
      context,
      metadata: openingQuestion.trim() ? { opening_question: openingQuestion.trim() } : {}
    });
    router.push(`/workspaces/${workspaceId}/conversations/${conversation.id}`);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">New conversation</h1>
        <p className="text-sm text-muted-foreground">
          Start a persistent research thread. Project and graph context can be captured now and used by agent tools later.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Conversation setup</CardTitle>
          <CardDescription>Choose the scope for this thread before asking questions.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={onSubmit}>
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" value={title} onChange={(event) => setTitle(event.target.value)} required />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Mode</Label>
                <Select value={mode} onValueChange={setMode}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="single">Single</SelectItem>
                    <SelectItem value="comparative">Comparative</SelectItem>
                    <SelectItem value="global">Global</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Project</Label>
                <Select value={projectId} onValueChange={setProjectId}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Workspace-level</SelectItem>
                    {(projects.data ?? []).map((project) => (
                      <SelectItem key={project.id} value={project.id}>{project.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="opening-question">Opening question</Label>
              <Textarea
                id="opening-question"
                value={openingQuestion}
                onChange={(event) => setOpeningQuestion(event.target.value)}
                placeholder="Optional note to remember why this conversation was started."
              />
            </div>
            {Object.keys(context).length ? (
              <div className="space-y-2">
                <Label>Captured context</Label>
                <pre className="overflow-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(context, null, 2)}</pre>
              </div>
            ) : null}
            <ErrorBanner error={createConversation.error || projects.error} />
            <Button type="submit" disabled={createConversation.isPending}>
              {createConversation.isPending ? "Creating..." : "Create conversation"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function contextFromSearchParams(searchParams: Pick<URLSearchParams, "get">): JsonObject {
  const context: JsonObject = {};
  const selectedNodeIds = csv(searchParams.get("selected_node_ids"));
  const edgeFilters = csv(searchParams.get("edge_filters"));
  const activeDocumentId = searchParams.get("active_document_id") ?? searchParams.get("document_id");
  const clusterId = searchParams.get("cluster_id");
  const activeQuery = searchParams.get("query");
  if (selectedNodeIds.length) context.selected_node_ids = selectedNodeIds;
  if (edgeFilters.length) context.edge_filters = edgeFilters;
  if (activeDocumentId) context.active_document_id = activeDocumentId;
  if (clusterId) context.cluster_id = clusterId;
  if (activeQuery) context.active_query = activeQuery;
  return context;
}

function csv(value: string | null) {
  return value?.split(",").map((item) => item.trim()).filter(Boolean) ?? [];
}
