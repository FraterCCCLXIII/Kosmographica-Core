"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { useParams } from "next/navigation";
import { FormEvent, useState } from "react";

import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useProjects } from "@/lib/hooks/useProjects";
import type { RAGResponse } from "@/lib/types";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  response?: RAGResponse;
}

export default function ChatPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>();
  const [mode, setMode] = useState("single");
  const [selectedProjectIds, setSelectedProjectIds] = useState<Set<string>>(new Set([projectId]));
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const projects = useProjects(workspaceId);
  const canonicalEntities = useQuery({
    queryKey: ["global-canonical-entities", workspaceId],
    queryFn: () => api.listGlobalCanonicalEntities(workspaceId)
  });
  const globalEnabled = Boolean(canonicalEntities.data?.length);
  const query = useMutation({
    mutationFn: (input: { question: string; mode: string }) =>
      input.mode === "comparative"
        ? api.comparativeQuery({ question: input.question, project_ids: Array.from(selectedProjectIds), k: 8 })
        : api.ragQuery({ question: input.question, mode: input.mode, project_id: projectId, k: 8 }),
    onSuccess: (response, variables) => {
      setMessages((current) => [
        ...current,
        { role: "user", content: variables.question },
        { role: "assistant", content: response.answer, response }
      ]);
      setQuestion("");
    }
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (question.trim() && (mode !== "comparative" || selectedProjectIds.size > 0)) query.mutate({ question, mode });
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
        <h1 className="text-2xl font-semibold">RAG chat</h1>
        <p className="text-sm text-muted-foreground">Answers must cite retrieved chunks and say when evidence is insufficient.</p>
      </div>
      <ErrorBanner error={query.error} />
      <div className="space-y-4">
        {messages.map((message, index) => (
          <Card key={index} className={message.role === "user" ? "ml-auto max-w-3xl bg-muted/40" : "max-w-4xl"}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between text-base">
                {message.role === "user" ? "You" : "Kosmographica"}
                {message.response ? <StatusBadge status={message.response.confidence} /> : null}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 whitespace-pre-wrap text-sm">
              <p>{message.content}</p>
              {message.response ? (
                <>
                  <div>
                    {message.response.confidence_rationale ? (
                      <p className="mb-3 rounded-md border bg-muted/40 p-3 text-muted-foreground">
                        {message.response.confidence_rationale}
                      </p>
                    ) : null}
                    <h3 className="mb-2 font-medium">Citations</h3>
                    <div className="space-y-2">
                      {message.response.citations.map((citation) => (
                        <div key={citation.chunk_id} className="rounded-md border p-3">
                          <p className="font-mono text-xs">[{citation.chunk_id}]</p>
                          <p className="text-muted-foreground">{citation.citation}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                  <Accordion type="single" collapsible>
                    <AccordionItem value="chunks">
                      <AccordionTrigger>Retrieved chunks</AccordionTrigger>
                      <AccordionContent className="space-y-3">
                        {message.response.retrieved_chunks.map((chunk) => (
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
                        {message.response.graph_paths.length ? message.response.graph_paths.map((path, pathIndex) => (
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
        ))}
      </div>
      <form onSubmit={onSubmit} className="sticky bottom-0 space-y-3 rounded-lg border bg-background p-4">
        <div className="flex gap-3">
          <Select value={mode} onValueChange={setMode}>
            <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="single">Single</SelectItem>
              <SelectItem value="comparative">Comparative</SelectItem>
              <SelectItem value="global" disabled={!globalEnabled}>Global</SelectItem>
            </SelectContent>
          </Select>
          <Button type="submit" disabled={query.isPending} className="ml-auto">
            <Send className="mr-2 h-4 w-4" />
            {query.isPending ? "Asking..." : "Ask"}
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
        {mode === "global" ? (
          <p className="text-sm text-muted-foreground">
            Global mode uses promoted canonical entities. It is available because this workspace has {canonicalEntities.data?.length ?? 0} canonical entity record(s).
          </p>
        ) : !globalEnabled ? (
          <p className="text-sm text-muted-foreground">Global mode unlocks after at least one entity is promoted to a workspace canonical entity.</p>
        ) : null}
        <Textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a cited question about this project..." />
      </form>
    </div>
  );
}
