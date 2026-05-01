"use client";

import { useMutation } from "@tanstack/react-query";
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
import type { RAGResponse } from "@/lib/types";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  response?: RAGResponse;
}

export default function ChatPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [mode, setMode] = useState("single");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const query = useMutation({
    mutationFn: (input: { question: string; mode: string }) =>
      input.mode === "comparative"
        ? api.comparativeQuery({ question: input.question, project_ids: [projectId], k: 8 })
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
    if (question.trim()) query.mutate({ question, mode });
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
              <SelectItem value="global">Global</SelectItem>
            </SelectContent>
          </Select>
          <Button type="submit" disabled={query.isPending} className="ml-auto">
            <Send className="mr-2 h-4 w-4" />
            {query.isPending ? "Asking..." : "Ask"}
          </Button>
        </div>
        <Textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a cited question about this project..." />
      </form>
    </div>
  );
}
