import { Badge } from "@/components/ui/badge";
import type { DocumentStatus, JobStatus } from "@/lib/types";

type Status = DocumentStatus | JobStatus | string;

export function StatusBadge({ status }: { status: Status }) {
  const variant =
    status === "failed"
      ? "destructive"
      : status === "ready" || status === "graph_ready" || status === "succeeded"
        ? "default"
        : status === "processing" || status === "running" || status === "queued" || status === "pending"
          ? "secondary"
          : "outline";

  return <Badge variant={variant}>{status.replaceAll("_", " ")}</Badge>;
}
