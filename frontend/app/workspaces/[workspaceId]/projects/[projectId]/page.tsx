"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useDocuments } from "@/lib/hooks/useDocuments";
import { useGraphEdges, useGraphNodes } from "@/lib/hooks/useGraph";

export default function ProjectDashboardPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>();
  const documents = useDocuments(projectId);
  const nodes = useGraphNodes(projectId);
  const edges = useGraphEdges(projectId);
  const documentCount = documents.data?.length ?? 0;
  const entityCount = nodes.data?.filter((node) => node.node_type === "entity").length ?? 0;
  const chunkCount = nodes.data?.filter((node) => node.node_type === "chunk").length ?? 0;
  const edgeCount = edges.data?.length ?? 0;
  const base = `/workspaces/${workspaceId}/projects/${projectId}`;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Project dashboard</h1>
        <p className="text-sm text-muted-foreground">A project-local view of documents, chunks, entities, and graph edges.</p>
      </div>
      <ErrorBanner error={documents.error || nodes.error || edges.error} />
      <div className="grid gap-4 md:grid-cols-4">
        {[["Documents", documentCount], ["Chunks", chunkCount], ["Entities", entityCount], ["Edges", edgeCount]].map(([label, value]) => (
          <Card key={label}>
            <CardHeader><CardDescription>{label}</CardDescription><CardTitle>{value}</CardTitle></CardHeader>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Recent processing jobs</CardTitle>
          <CardDescription>Job history endpoints are not listable yet, so document statuses are shown here.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {documents.data?.slice(0, 5).map((document) => (
            <div key={document.id} className="flex justify-between rounded-md border p-3 text-sm">
              <span>{document.title}</span>
              <span className="text-muted-foreground">{document.status}</span>
            </div>
          ))}
        </CardContent>
      </Card>
      <div className="flex flex-wrap gap-3">
        <Link href={`${base}/documents`}><Button>Documents</Button></Link>
        <Link href={`${base}/graph`}><Button variant="secondary">Graph</Button></Link>
        <Link href={`${base}/chat`}><Button variant="secondary">Chat</Button></Link>
      </div>
    </div>
  );
}
