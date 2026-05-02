"use client";

import { Trash2, UploadCloud } from "lucide-react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { DragEvent, useState } from "react";

import { DocumentDebugDialog } from "@/components/documents/DocumentDebugDialog";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useDeleteDocument, useDocumentStatus, useDocuments, useUploadDocuments } from "@/lib/hooks/useDocuments";

function UploadProgressItem({ documentId }: { documentId: string }) {
  const status = useDocumentStatus(documentId);
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="min-w-0">
        <span className="block truncate">{documentId}</span>
        {status.data?.job?.error_message ? <p className="mt-2 text-destructive">{status.data.job.error_message}</p> : null}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <DocumentDebugDialog documentId={documentId} />
        {status.data ? <StatusBadge status={status.data.document_status} /> : <span>Checking...</span>}
      </div>
    </div>
  );
}

function UploadProgress({ documentIds }: { documentIds: string[] }) {
  if (!documentIds.length) return null;
  return (
    <div className="space-y-2 rounded-md border p-3 text-sm">
      <p className="font-medium">Latest uploads</p>
      {documentIds.map((documentId) => (
        <UploadProgressItem key={documentId} documentId={documentId} />
      ))}
    </div>
  );
}

export default function DocumentsPage() {
  const { workspaceId, projectId } = useParams<{ workspaceId: string; projectId: string }>();
  const [latestDocumentIds, setLatestDocumentIds] = useState<string[]>([]);
  const [uploadWarning, setUploadWarning] = useState<string>();
  const documents = useDocuments(projectId);
  const upload = useUploadDocuments(projectId);
  const deleteDocument = useDeleteDocument(projectId);
  const pendingUploadCount = upload.variables?.files.length ?? 0;

  async function uploadFiles(files: File[]) {
    if (!files.length) return;
    setUploadWarning(undefined);
    try {
      const results = await upload.mutateAsync({ files });
      setLatestDocumentIds(results.uploaded.map((result) => result.document_id));
      if (results.failed.length) {
        setUploadWarning(`Some files could not be uploaded: ${results.failed.map((failure) => failure.fileName).join(", ")}`);
      }
    } catch {
      // The mutation state feeds ErrorBanner; avoid an unhandled runtime error.
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    void uploadFiles(Array.from(event.dataTransfer.files));
  }

  function deleteFailedDocument(documentId: string, title: string) {
    if (window.confirm(`Delete failed document "${title}"?`)) {
      deleteDocument.mutate(documentId);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Documents</h1>
        <p className="text-sm text-muted-foreground">Upload source files and track ingestion into cited chunks and graph evidence.</p>
      </div>
      <ErrorBanner error={documents.error || upload.error || uploadWarning || deleteDocument.error} />
      <Card>
        <CardContent
          onDragOver={(event) => event.preventDefault()}
          onDrop={onDrop}
          className="mt-6 flex flex-col items-center gap-4 rounded-md border border-dashed p-10 text-center"
        >
          <UploadCloud className="h-8 w-8 text-muted-foreground" />
          <div>
            <p className="font-medium">Drag PDF, EPUB, DOCX, HTML, TXT, MD, CSV, JSON, or XML files here</p>
            <p className="text-sm text-muted-foreground">Files are saved locally and processed asynchronously.</p>
          </div>
          <Button disabled={upload.isPending} onClick={() => document.getElementById("file-upload")?.click()}>
            {upload.isPending ? `Uploading ${pendingUploadCount} file${pendingUploadCount === 1 ? "" : "s"}...` : "Choose files"}
          </Button>
          <input
            id="file-upload"
            className="hidden"
            type="file"
            multiple
            accept=".pdf,.epub,.docx,.html,.htm,.txt,.text,.md,.markdown,.log,.csv,.tsv,.json,.xml,.rst"
            onChange={(event) => {
              void uploadFiles(Array.from(event.target.files ?? []));
              event.currentTarget.value = "";
            }}
          />
        </CardContent>
      </Card>
      <UploadProgress documentIds={latestDocumentIds} />
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
                  <DocumentDebugDialog documentId={document.id} title={document.title} />
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
                  {document.status === "failed" ? (
                    <Button
                      aria-label={`Delete failed document ${document.title}`}
                      disabled={deleteDocument.isPending}
                      size="sm"
                      variant="destructive"
                      onClick={() => deleteFailedDocument(document.id, document.title)}
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete
                    </Button>
                  ) : null}
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
