"use client";

import { AlertTriangle, Bug } from "lucide-react";
import type { ReactNode } from "react";

import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "@/components/ui/dialog";
import { useDocument, useDocumentStatus, useProcessingTimeline } from "@/lib/hooks/useDocuments";
import type { ProcessingJob, ProcessingStage, UUID } from "@/lib/types";

interface DocumentDebugDialogProps {
  documentId: UUID;
  title?: string;
}

export function DocumentDebugDialog({ documentId, title }: DocumentDebugDialogProps) {
  const document = useDocument(documentId);
  const status = useDocumentStatus(documentId);
  const timeline = useProcessingTimeline(documentId);
  const latestJob = status.data?.job ?? timeline.data?.jobs.at(-1) ?? null;
  const failedJob = findLast(timeline.data?.jobs, (job) => job.status === "failed");
  const failedStage = findLast(timeline.data?.stages, (stage) => stage.status === "failed");
  const activeStage = findLast(timeline.data?.stages, (stage) => stage.status === "running");
  const cause = getLikelyCause(failedStage, failedJob, latestJob);

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <Bug className="mr-2 h-4 w-4" />
          Debug
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Document debug</DialogTitle>
          <DialogDescription className="break-words">
            {document.data?.title ?? title ?? documentId}
          </DialogDescription>
        </DialogHeader>

        <ErrorBanner error={document.error || status.error || timeline.error} />

        <div className="grid gap-3 sm:grid-cols-3">
          <DebugStat
            label="Document status"
            value={<StatusBadge status={status.data?.document_status ?? document.data?.status ?? "unknown"} />}
          />
          <DebugStat label="Current step" value={activeStage?.name.replaceAll("_", " ") ?? getMetadataString(latestJob, "current_step") ?? "None"} />
          <DebugStat label="Failed step" value={failedStage?.name.replaceAll("_", " ") ?? getMetadataString(failedJob, "failed_step") ?? "None"} />
        </div>

        {cause ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p className="font-medium">Likely failure reason</p>
                <p className="break-words">{cause}</p>
              </div>
            </div>
          </div>
        ) : (
          <p className="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">
            No failure has been recorded yet. Watch the stage timeline for the step that stalls or fails.
          </p>
        )}

        <section className="space-y-2">
          <h3 className="text-sm font-medium">Stage timeline</h3>
          {timeline.data?.stages.length ? (
            <div className="space-y-2">
              {timeline.data.stages.map((stage) => (
                <div key={`${stage.job_id}-${stage.name}`} className="rounded-md border p-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{stage.name.replaceAll("_", " ")}</span>
                    <StatusBadge status={stage.status} />
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {formatStageTime(stage)}
                  </p>
                  {stage.error ? <p className="mt-2 break-words text-xs text-destructive">{stage.error}</p> : null}
                </div>
              ))}
            </div>
          ) : (
            <p className="rounded-md border p-3 text-sm text-muted-foreground">No stage timeline recorded yet.</p>
          )}
        </section>

        <section className="grid gap-3 lg:grid-cols-2">
          <DebugJson title="Latest job" value={latestJob} emptyText="No processing job found." />
          <DebugJson
            title="Source metadata"
            value={{
              id: documentId,
              source_type: document.data?.source_type,
              source_uri: document.data?.source_uri,
              metadata: document.data?.metadata
            }}
            emptyText="Document metadata is not loaded yet."
          />
        </section>

        <DebugJson title="All jobs" value={timeline.data?.jobs ?? null} emptyText="No jobs have been recorded for this document." />
      </DialogContent>
    </Dialog>
  );
}

function DebugStat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-md border p-3 text-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="mt-2 break-words">{value}</div>
    </div>
  );
}

function DebugJson({ title, value, emptyText }: { title: string; value: unknown; emptyText: string }) {
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-medium">{title}</h3>
      {value ? (
        <pre className="max-h-80 overflow-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(value, null, 2)}</pre>
      ) : (
        <p className="rounded-md border p-3 text-sm text-muted-foreground">{emptyText}</p>
      )}
    </section>
  );
}

function getLikelyCause(
  failedStage: ProcessingStage | null | undefined,
  failedJob: ProcessingJob | null | undefined,
  latestJob: ProcessingJob | null | undefined
) {
  return failedStage?.error ?? failedJob?.error_message ?? latestJob?.error_message ?? null;
}

function getMetadataString(job: ProcessingJob | null | undefined, key: string) {
  const value = job?.metadata?.[key];
  return typeof value === "string" ? value : null;
}

function formatStageTime(stage: ProcessingStage) {
  const started = stage.started_at ? `Started ${new Date(stage.started_at).toLocaleString()}` : "Not started";
  const completed = stage.completed_at ? `Completed ${new Date(stage.completed_at).toLocaleString()}` : null;
  return [started, completed].filter(Boolean).join(" · ");
}

function findLast<T>(items: T[] | undefined, predicate: (item: T) => boolean) {
  if (!items) return null;
  for (let index = items.length - 1; index >= 0; index -= 1) {
    if (predicate(items[index])) return items[index];
  }
  return null;
}
