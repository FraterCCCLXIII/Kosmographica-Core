"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { DocumentDebugDialog } from "@/components/documents/DocumentDebugDialog";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  useDeleteDocument,
  useDocument,
  useDocumentChunks,
  useDocumentGraphSummary,
  useDocumentStatus,
  useProcessingTimeline,
  useReprocessDocument,
  useRetryProcessingJob
} from "@/lib/hooks/useDocuments";

export default function DocumentDetailPage() {
  const { workspaceId, projectId, documentId } = useParams<{ workspaceId: string; projectId: string; documentId: string }>();
  const router = useRouter();
  const document = useDocument(documentId);
  const status = useDocumentStatus(documentId);
  const chunks = useDocumentChunks(documentId);
  const summary = useDocumentGraphSummary(documentId);
  const timeline = useProcessingTimeline(documentId);
  const reprocess = useReprocessDocument(documentId);
  const retryJob = useRetryProcessingJob(documentId);
  const deleteDocument = useDeleteDocument(projectId);
  const failedJob = timeline.data?.jobs.slice().reverse().find((job) => job.status === "failed");

  async function deleteFailedDocument(title: string) {
    if (!window.confirm(`Delete failed document "${title}"?`)) return;
    try {
      await deleteDocument.mutateAsync(documentId);
      router.push(`/workspaces/${workspaceId}/projects/${projectId}/documents`);
    } catch {
      // The mutation state feeds ErrorBanner; avoid an unhandled runtime error.
    }
  }

  return (
    <div className="space-y-6">
      <ErrorBanner error={document.error || status.error || chunks.error || summary.error || timeline.error || reprocess.error || retryJob.error || deleteDocument.error} />
      {document.data ? (
        <>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold">{document.data.title}</h1>
              <p className="text-sm text-muted-foreground">{document.data.id}</p>
            </div>
            <div className="flex gap-2">
              <StatusBadge status={status.data?.document_status ?? document.data.status} />
              <DocumentDebugDialog documentId={documentId} title={document.data.title} />
              <Button variant="outline" disabled={reprocess.isPending} onClick={() => reprocess.mutate()}>
                {reprocess.isPending ? "Reprocessing..." : "Reprocess"}
              </Button>
              <Button
                variant="outline"
                disabled={!failedJob || retryJob.isPending}
                onClick={() => failedJob && retryJob.mutate(failedJob.id ?? failedJob.job_id!)}
              >
                {retryJob.isPending ? "Retrying..." : "Retry failed"}
              </Button>
              {document.data.status === "failed" ? (
                <Button
                  variant="destructive"
                  disabled={deleteDocument.isPending}
                  onClick={() => void deleteFailedDocument(document.data.title)}
                >
                  {deleteDocument.isPending ? "Deleting..." : "Delete failed"}
                </Button>
              ) : null}
              <Link
                className="inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-3 text-sm font-medium hover:bg-muted"
                href={`/workspaces/${workspaceId}/projects/${projectId}/graph?query=${encodeURIComponent(document.data.title)}&documentId=${documentId}`}
              >
                Open graph for this document
              </Link>
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className="space-y-4">
              <Card>
                <CardHeader><CardTitle>Chunks</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  {chunks.data?.length ? chunks.data.map((chunk) => (
                    <div key={chunk.id} className="rounded-md border p-3 text-sm">
                      <p className="font-medium">{chunk.citation}</p>
                      <p className="text-muted-foreground">{chunk.token_count} tokens</p>
                      <p className="mt-2 whitespace-pre-wrap">{chunk.text}</p>
                    </div>
                  )) : <EmptyState title="No chunks" description="This document has not been chunked yet." />}
                </CardContent>
              </Card>
            </div>

            <div className="space-y-4">
              <Card>
                <CardHeader><CardTitle>Processing</CardTitle></CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <p>Status: {status.data?.document_status ?? document.data.status}</p>
                  {status.data?.job ? (
                    <pre className="overflow-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(status.data.job, null, 2)}</pre>
                  ) : <p className="text-muted-foreground">No processing job found.</p>}
                  <div className="space-y-2">
                    <p className="font-medium">Stage timeline</p>
                    {timeline.data?.stages.length ? timeline.data.stages.map((stage) => (
                      <div key={`${stage.job_id}-${stage.name}`} className="rounded-md border p-2">
                        <div className="flex items-center justify-between gap-2">
                          <span>{stage.name.replaceAll("_", " ")}</span>
                          <StatusBadge status={stage.status} />
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {stage.started_at ? `Started ${new Date(stage.started_at).toLocaleString()}` : "Not started"}
                          {stage.completed_at ? ` · Completed ${new Date(stage.completed_at).toLocaleString()}` : ""}
                        </p>
                        {stage.error ? <p className="text-xs text-destructive">{stage.error}</p> : null}
                      </div>
                    )) : <p className="text-muted-foreground">No stage timeline recorded yet.</p>}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle>Graph summary</CardTitle></CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <div>
                    <p className="font-medium">Node counts</p>
                    <pre className="overflow-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(summary.data?.node_counts ?? {}, null, 2)}</pre>
                  </div>
                  <div>
                    <p className="font-medium">Edge counts</p>
                    <pre className="overflow-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(summary.data?.edge_counts ?? {}, null, 2)}</pre>
                  </div>
                  <div>
                    <p className="font-medium">Top entities</p>
                    {summary.data?.top_entities.length ? summary.data.top_entities.map((entity) => (
                      <p key={entity.id} className="text-muted-foreground">{entity.canonical_name}</p>
                    )) : <p className="text-muted-foreground">No entities linked yet.</p>}
                  </div>
                  <div>
                    <p className="font-medium">Top claims</p>
                    {summary.data?.top_claims.length ? summary.data.top_claims.map((claim) => (
                      <p key={claim.id} className="text-muted-foreground">{claim.subject} {claim.predicate} {claim.object}</p>
                    )) : <p className="text-muted-foreground">No claims linked yet.</p>}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle>Metadata</CardTitle></CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <p>Source: {document.data.source_type}</p>
                  <p className="break-all text-muted-foreground">{document.data.source_uri}</p>
                  <pre className="overflow-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(document.data.metadata, null, 2)}</pre>
                </CardContent>
              </Card>
            </div>
          </div>
        </>
      ) : <p className="text-sm text-muted-foreground">Loading document...</p>}
    </div>
  );
}
