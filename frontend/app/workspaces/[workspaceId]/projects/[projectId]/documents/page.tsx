"use client";

import { UploadCloud } from "lucide-react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { DragEvent, useState } from "react";

import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useDocumentStatus, useDocuments, useUploadDocument } from "@/lib/hooks/useDocuments";

function UploadProgress({ documentId }: { documentId?: string }) {
  const status = useDocumentStatus(documentId);
  if (!documentId) return null;
  return (
    <div className="rounded-md border p-3 text-sm">
      <div className="flex items-center justify-between">
        <span>Latest upload</span>
        {status.data ? <StatusBadge status={status.data.document_status} /> : <span>Checking...</span>}
      </div>
      {status.data?.job?.error_message ? <p className="mt-2 text-destructive">{status.data.job.error_message}</p> : null}
    </div>
  );
}

export default function DocumentsPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>();
  const [latestDocumentId, setLatestDocumentId] = useState<string>();
  const documents = useDocuments(projectId);
  const upload = useUploadDocument(projectId);

  async function uploadFile(file: File) {
    try {
      const result = await upload.mutateAsync({ file });
      setLatestDocumentId(result.document_id);
    } catch {
      // The mutation state feeds ErrorBanner; avoid an unhandled runtime error.
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    const file = event.dataTransfer.files.item(0);
    if (file) void uploadFile(file);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Documents</h1>
        <p className="text-sm text-muted-foreground">Upload source files and track ingestion into cited chunks and graph evidence.</p>
      </div>
      <ErrorBanner error={documents.error || upload.error} />
      <Card>
        <CardContent
          onDragOver={(event) => event.preventDefault()}
          onDrop={onDrop}
          className="mt-6 flex flex-col items-center gap-4 rounded-md border border-dashed p-10 text-center"
        >
          <UploadCloud className="h-8 w-8 text-muted-foreground" />
          <div>
            <p className="font-medium">Drag a PDF, DOCX, HTML, TXT, or MD file here</p>
            <p className="text-sm text-muted-foreground">The file is saved locally and processed asynchronously.</p>
          </div>
          <Button disabled={upload.isPending} onClick={() => document.getElementById("file-upload")?.click()}>
            {upload.isPending ? "Uploading..." : "Choose file"}
          </Button>
          <input
            id="file-upload"
            className="hidden"
            type="file"
            accept=".pdf,.docx,.html,.htm,.txt,.md"
            onChange={(event) => {
              const file = event.target.files?.item(0);
              if (file) void uploadFile(file);
            }}
          />
        </CardContent>
      </Card>
      <UploadProgress documentId={latestDocumentId} />
      <Card>
        <CardHeader>
          <CardTitle>Document library</CardTitle>
          <CardDescription>Statuses reflect the backend ingestion pipeline.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {documents.data?.length ? (
            documents.data.map((document) => (
              <div key={document.id} className="flex items-center justify-between gap-3 rounded-md border p-3">
                <div>
                  <p className="font-medium">{document.title}</p>
                  <p className="text-sm text-muted-foreground">{document.source_type} · {document.id}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Link
                    className="inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-3 text-sm font-medium hover:bg-muted"
                    href={`/workspaces/${workspaceId}/projects/${projectId}/documents/${document.id}`}
                  >
                    Inspect
                  </Link>
                  <Link
                    className="inline-flex h-9 items-center justify-center rounded-md border border-input bg-background px-3 text-sm font-medium hover:bg-muted"
                    href={`/workspaces/${workspaceId}/projects/${projectId}/graph?query=${encodeURIComponent(document.title)}&documentId=${document.id}`}
                  >
                    Graph
                  </Link>
                  <StatusBadge status={document.status} />
                </div>
              </div>
            ))
          ) : (
            <EmptyState title="No documents yet" description="Upload a source document to begin building the graph." />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
