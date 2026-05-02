"use client";

import { Send } from "lucide-react";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { exportRagAnswer } from "@/lib/exportArtifacts";
import { useConversation, useSendConversationMessage } from "@/lib/hooks/useConversations";
import { useProjects } from "@/lib/hooks/useProjects";
import type { ConversationMessage, RAGResponse } from "@/lib/types";

export default function ConversationPage() {
  const { workspaceId, conversationId } = useParams<{ workspaceId: string; conversationId: string }>();
  const conversation = useConversation(workspaceId, conversationId);
  const [mode, setMode] = useState("single");
  const [question, setQuestion] = useState("");
  const projects = useProjects(workspaceId);
  const [selectedProjectIds, setSelectedProjectIds] = useState<Set<string>>(new Set());
  const sendMessage = useSendConversationMessage(workspaceId, conversationId);
  const projectId = conversation.data?.project_id ?? undefined;
  const messages = conversation.data?.messages ?? [];

  useEffect(() => {
    if (!conversation.data) return;
    setMode(conversation.data.mode);
    setSelectedProjectIds(new Set(conversation.data.project_id ? [conversation.data.project_id] : []));
  }, [conversation.data]);

  const hasGeneratingMessage = useMemo(
    () => messages.some((message) => message.status === "generating" || message.status === "queued"),
    [messages]
  );

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = question.trim();
    if (!content) return;
    await sendMessage.mutateAsync({
      content,
      mode,
      project_ids: mode === "comparative" ? Array.from(selectedProjectIds) : undefined
    });
    setQuestion("");
  }

  function toggleProject(projectIdValue: string) {
    setSelectedProjectIds((current) => {
      const next = new Set(current);
      if (next.has(projectIdValue) && next.size > 1) next.delete(projectIdValue);
      else next.add(projectIdValue);
      return next;
    });
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">{conversation.data?.title ?? "Conversation"}</h1>
        <p className="text-sm text-muted-foreground">
          Persistent RAG conversation with citations, graph paths, and workspace-scoped history.
        </p>
      </div>
      <ErrorBanner error={conversation.error || sendMessage.error} />
      <div className="space-y-4 pb-48">
        {conversation.isLoading ? <Card><CardContent className="py-8">Loading conversation...</CardContent></Card> : null}
        {messages.map((message, index) => (
          <MessageCard
            key={message.id}
            message={message}
            mode={String(message.metadata.mode ?? mode)}
            projectId={projectId}
            previousUserMessage={messages[index - 1]?.content}
          />
        ))}
        {!messages.length && !conversation.isLoading ? (
          <Card>
            <CardContent className="py-8 text-sm text-muted-foreground">
              Ask a cited question to start building this research thread.
            </CardContent>
          </Card>
        ) : null}
      </div>
      <form onSubmit={onSubmit} className="sticky bottom-0 z-10 space-y-3 rounded-lg border bg-background p-4">
        <div className="flex gap-3">
          <Select value={mode} onValueChange={setMode}>
            <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="single">Single</SelectItem>
              <SelectItem value="comparative">Comparative</SelectItem>
              <SelectItem value="global">Global</SelectItem>
            </SelectContent>
          </Select>
          <Button type="submit" disabled={sendMessage.isPending || hasGeneratingMessage} className="ml-auto">
            <Send className="mr-2 h-4 w-4" />
            {sendMessage.isPending || hasGeneratingMessage ? "Asking..." : "Ask"}
          </Button>
        </div>
        {mode === "comparative" ? (
          <div className="rounded-md border p-3">
            <p className="mb-2 text-sm font-medium">Compare projects</p>
            <div className="grid gap-2 md:grid-cols-2">
              {(projects.data ?? []).map((project) => (
                <label key={project.id} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={selectedProjectIds.has(project.id)} onChange={() => toggleProject(project.id)} />
                  <span>{project.name}</span>
                </label>
              ))}
            </div>
          </div>
        ) : null}
        <Textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a cited question about this workspace..." />
      </form>
    </div>
  );
}

function MessageCard({
  message,
  mode,
  projectId,
  previousUserMessage
}: {
  message: ConversationMessage;
  mode: string;
  projectId?: string;
  previousUserMessage?: string;
}) {
  const response = message.role === "assistant" && message.status === "complete" ? messageToRagResponse(message, mode) : undefined;
  return (
    <Card className={message.role === "user" ? "ml-auto max-w-3xl bg-muted/40" : "max-w-4xl"}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between text-base">
          {message.role === "user" ? "You" : "Kosmographica"}
          {message.role === "assistant" ? <StatusBadge status={message.confidence ?? message.status} /> : null}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 whitespace-pre-wrap text-sm">
        <p>{message.status === "generating" ? "Generating answer..." : message.content}</p>
        {message.status === "failed" ? (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-muted-foreground">
            {String(message.metadata.error ?? "The assistant response failed.")}
          </p>
        ) : null}
        {response ? (
          <>
            {projectId ? (
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    exportRagAnswer({
                      projectId,
                      question: previousUserMessage ?? "Question not available",
                      response,
                      format: "markdown"
                    })
                  }
                >
                  Export answer md
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    exportRagAnswer({
                      projectId,
                      question: previousUserMessage ?? "Question not available",
                      response,
                      format: "json"
                    })
                  }
                >
                  Export answer json
                </Button>
              </div>
            ) : null}
            <div>
              {response.confidence_rationale ? (
                <p className="mb-3 rounded-md border bg-muted/40 p-3 text-muted-foreground">
                  {response.confidence_rationale}
                </p>
              ) : null}
              <h3 className="mb-2 font-medium">Citations</h3>
              <div className="space-y-2">
                {response.citations.length ? response.citations.map((citation) => (
                  <div key={citation.chunk_id} className="rounded-md border p-3">
                    <p className="font-mono text-xs">[{citation.chunk_id}]</p>
                    <p className="text-muted-foreground">{citation.citation}</p>
                  </div>
                )) : <p className="text-sm text-muted-foreground">No citations were returned.</p>}
              </div>
            </div>
            <Accordion type="single" collapsible>
              <AccordionItem value="chunks">
                <AccordionTrigger>Retrieved chunks</AccordionTrigger>
                <AccordionContent className="space-y-3">
                  {response.retrieved_chunks.map((chunk) => (
                    <div key={chunk.chunk_id} className="rounded-md border p-3">
                      <p className="font-mono text-xs">[{chunk.chunk_id}] score {chunk.similarity_score.toFixed(3)}</p>
                      <p className="mt-2 text-muted-foreground">{chunk.text}</p>
                    </div>
                  ))}
                </AccordionContent>
              </AccordionItem>
              <AccordionItem value="graph-paths">
                <AccordionTrigger>Graph paths used</AccordionTrigger>
                <AccordionContent className="space-y-3">
                  {response.graph_paths.length ? response.graph_paths.map((path, pathIndex) => (
                    <div key={pathIndex} className="rounded-md border p-3">
                      <p className="font-medium">Path {pathIndex + 1}</p>
                      <p className="text-muted-foreground">{path.nodes.length} node(s), {path.edges.length} edge(s)</p>
                      <div className="mt-2 space-y-1">
                        {path.nodes.slice(0, 8).map((node) => (
                          <p key={node.id} className="text-xs">{node.node_type}: {node.label}</p>
                        ))}
                      </div>
                    </div>
                  )) : <p className="text-sm text-muted-foreground">No graph paths were used for this answer.</p>}
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}

function messageToRagResponse(message: ConversationMessage, mode: string): RAGResponse {
  return {
    answer: message.content,
    citations: message.citations,
    retrieved_chunks: message.retrieved_chunks,
    graph_paths: message.graph_paths,
    mode,
    confidence: message.confidence ?? "insufficient_evidence",
    confidence_rationale: typeof message.metadata.confidence_rationale === "string" ? message.metadata.confidence_rationale : ""
  };
}
