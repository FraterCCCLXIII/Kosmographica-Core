"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useParams } from "next/navigation";

import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useConversations } from "@/lib/hooks/useConversations";
import { useProjects } from "@/lib/hooks/useProjects";
import type { UUID } from "@/lib/types";

const PAGE_SIZE = 20;

export default function ConversationHistoryPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const [queryInput, setQueryInput] = useState("");
  const [query, setQuery] = useState("");
  const [projectFilter, setProjectFilter] = useState<UUID | "none" | "all">("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [offset, setOffset] = useState(0);
  const projects = useProjects(workspaceId);
  const conversations = useConversations(workspaceId, {
    limit: PAGE_SIZE,
    offset,
    query,
    dateFrom: dateFrom || undefined,
    dateTo: dateTo || undefined,
    projectId: projectFilter === "all" ? undefined : projectFilter
  });
  const total = conversations.data?.total ?? 0;
  const canGoBack = offset > 0;
  const canGoForward = offset + PAGE_SIZE < total;

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQuery(queryInput.trim());
    setOffset(0);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Conversation history</h1>
          <p className="text-sm text-muted-foreground">Search and reopen workspace-level research threads.</p>
        </div>
        <Link href={`/workspaces/${workspaceId}/conversations/new`}>
          <Button>New Conversation</Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
          <CardDescription>Filter by title, project attachment, or creation date.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px_160px_160px_auto]" onSubmit={onSubmit}>
            <div className="space-y-2">
              <Label htmlFor="query">Title</Label>
              <Input id="query" value={queryInput} onChange={(event) => setQueryInput(event.target.value)} placeholder="Search conversations..." />
            </div>
            <div className="space-y-2">
              <Label>Project</Label>
              <Select value={projectFilter} onValueChange={(value) => {
                setProjectFilter(value as UUID | "none" | "all");
                setOffset(0);
              }}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All conversations</SelectItem>
                  <SelectItem value="none">Workspace-level only</SelectItem>
                  {(projects.data ?? []).map((project) => (
                    <SelectItem key={project.id} value={project.id}>{project.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="date-from">From</Label>
              <Input id="date-from" type="date" value={dateFrom} onChange={(event) => {
                setDateFrom(event.target.value);
                setOffset(0);
              }} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="date-to">To</Label>
              <Input id="date-to" type="date" value={dateTo} onChange={(event) => {
                setDateTo(event.target.value);
                setOffset(0);
              }} />
            </div>
            <Button type="submit" className="self-end">Search</Button>
          </form>
        </CardContent>
      </Card>

      <ErrorBanner error={conversations.error || projects.error} />

      <div className="space-y-3">
        {conversations.data?.items.length ? conversations.data.items.map((conversation) => (
          <Link key={conversation.id} href={`/workspaces/${workspaceId}/conversations/${conversation.id}`}>
            <Card className="transition-colors hover:bg-muted/40">
              <CardHeader>
                <CardTitle className="text-base">{conversation.title}</CardTitle>
                <CardDescription>
                  {conversation.project_id ? `Project ${conversation.project_id.slice(0, 8)}` : "Workspace-level"} · {conversation.mode}
                </CardDescription>
              </CardHeader>
            </Card>
          </Link>
        )) : (
          <Card>
            <CardContent className="py-8 text-sm text-muted-foreground">
              {conversations.isLoading ? "Loading conversations..." : "No conversations matched these filters."}
            </CardContent>
          </Card>
        )}
      </div>

      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          Showing {total ? offset + 1 : 0}-{Math.min(offset + PAGE_SIZE, total)} of {total}
        </p>
        <div className="flex gap-2">
          <Button variant="outline" disabled={!canGoBack} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
            Previous
          </Button>
          <Button variant="outline" disabled={!canGoForward} onClick={() => setOffset(offset + PAGE_SIZE)}>
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
