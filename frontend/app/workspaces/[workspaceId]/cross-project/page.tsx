"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useProjects } from "@/lib/hooks/useProjects";
import type { LinkSuggestion } from "@/lib/types";

export default function CrossProjectPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const queryClient = useQueryClient();
  const [selectedSuggestion, setSelectedSuggestion] = useState<LinkSuggestion | null>(null);
  const [rationale, setRationale] = useState("");
  const projects = useProjects(workspaceId);
  const projectNames = new Map((projects.data ?? []).map((project) => [project.id, project.name]));
  const suggestions = useQuery({
    queryKey: ["cross-project-suggestions", workspaceId],
    queryFn: () => api.listCrossProjectSuggestions(workspaceId)
  });
  const links = useQuery({
    queryKey: ["cross-project-links", workspaceId],
    queryFn: () => api.listCrossProjectLinks(workspaceId)
  });
  const canonicals = useQuery({
    queryKey: ["global-canonical-entities", workspaceId],
    queryFn: () => api.listGlobalCanonicalEntities(workspaceId)
  });
  const canonicalConcepts = useQuery({
    queryKey: ["global-canonical-concepts", workspaceId],
    queryFn: () => api.listGlobalCanonicalConcepts(workspaceId)
  });
  const confirm = useMutation({
    mutationFn: () => api.confirmCrossProjectLink(workspaceId, { suggestion: selectedSuggestion!, rationale }),
    onSuccess: async () => {
      setSelectedSuggestion(null);
      setRationale("");
      await queryClient.invalidateQueries({ queryKey: ["cross-project-suggestions", workspaceId] });
      await queryClient.invalidateQueries({ queryKey: ["cross-project-links", workspaceId] });
    }
  });
  const reject = useMutation({
    mutationFn: (suggestionId: string) => api.rejectCrossProjectLink(workspaceId, suggestionId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["cross-project-suggestions", workspaceId] });
      await queryClient.invalidateQueries({ queryKey: ["cross-project-links", workspaceId] });
    }
  });
  const promote = useMutation({
    mutationFn: (entityId: string) => api.promoteToGlobalCanonical(workspaceId, entityId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["cross-project-links", workspaceId] });
      await queryClient.invalidateQueries({ queryKey: ["global-canonical-entities", workspaceId] });
    }
  });

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Cross-project links</h1>
          <p className="text-sm text-muted-foreground">
            Suggestions are opt-in only. Confirmed links preserve confidence, rationale, and source chunk samples.
          </p>
        </div>
        <Link href={`/workspaces/${workspaceId}`}>
          <Button variant="outline">Back to projects</Button>
        </Link>
      </div>

      <ErrorBanner error={suggestions.error || links.error || canonicals.error || canonicalConcepts.error || confirm.error || reject.error || promote.error} />

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Suggestions</h2>
        {suggestions.data?.length ? (
          <div className="grid gap-4">
            {suggestions.data.map((suggestion) => (
              <Card key={suggestion.suggestion_id}>
                <CardHeader>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <CardTitle>
                        {suggestion.source_entity.canonical_name} / {suggestion.target_entity.canonical_name}
                      </CardTitle>
                      <CardDescription>
                        {projectNames.get(suggestion.source_project_id) ?? suggestion.source_project_id} -&gt; {projectNames.get(suggestion.target_project_id) ?? suggestion.target_project_id}
                      </CardDescription>
                    </div>
                    <StatusBadge status={`confidence ${suggestion.confidence.toFixed(2)}`} />
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <SampleChunks title="Source evidence" chunks={suggestion.source_entity.sample_chunks} />
                    <SampleChunks title="Target evidence" chunks={suggestion.target_entity.sample_chunks} />
                  </div>
                  <div className="rounded-md bg-muted/40 p-3 text-sm">
                    <p className="font-medium">Why this was suggested</p>
                    <p className="mt-1 text-muted-foreground">
                      Both projects contain a {suggestion.source_entity.entity_type} entity with matching names and sampled chunk evidence. Similarity score: {suggestion.similarity_score.toFixed(2)}.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={() => setSelectedSuggestion(suggestion)}>Confirm</Button>
                    <Button variant="outline" onClick={() => reject.mutate(suggestion.suggestion_id)}>Reject</Button>
                    <Button variant="secondary" onClick={() => promote.mutate(suggestion.source_entity.id)}>
                      Promote source canonical
                    </Button>
                    <Button variant="secondary" onClick={() => promote.mutate(suggestion.target_entity.id)}>
                      Promote target canonical
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <EmptyState title="No link suggestions" description="Suggestions appear when matching entity names are found across isolated projects." />
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Confirmed links</h2>
        {links.data?.length ? (
          <div className="grid gap-3">
            {links.data.map((link) => (
              <Card key={link.id}>
                <CardHeader>
                  <CardTitle>{link.link_type}</CardTitle>
                  <CardDescription>
                    {projectNames.get(link.source_project_id) ?? link.source_project_id} / {link.source_ref_type}:{link.source_ref_id} -&gt; {projectNames.get(link.target_project_id) ?? link.target_project_id} / {link.target_ref_type}:{link.target_ref_id}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <p><strong>Confidence:</strong> {link.confidence.toFixed(2)}</p>
                  <p><strong>Rationale:</strong> {link.rationale}</p>
                  <details>
                    <summary className="cursor-pointer font-medium">View evidence metadata</summary>
                    <pre className="mt-2 overflow-auto rounded-md bg-muted p-3 text-xs">{JSON.stringify(link.metadata, null, 2)}</pre>
                  </details>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <EmptyState title="No confirmed links" description="Confirm suggestions only when the evidence supports a cross-project relationship." />
        )}
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Global canonical entities</CardTitle>
            <CardDescription>Promoted records for workspace-level browsing without merging project-local provenance.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {canonicals.data?.length ? canonicals.data.map((entity) => (
              <div key={entity.id} className="rounded-md border p-3 text-sm">
                <p className="font-medium">{entity.canonical_name}</p>
                <p className="text-muted-foreground">{entity.entity_type} - {entity.aliases.length} alias(es)</p>
              </div>
            )) : (
              <p className="text-sm text-muted-foreground">No canonical entities have been promoted yet.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Global canonical concepts</CardTitle>
            <CardDescription>Workspace-level concept records for comparative research browsing.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {canonicalConcepts.data?.length ? canonicalConcepts.data.map((concept) => (
              <div key={concept.id} className="rounded-md border p-3 text-sm">
                <p className="font-medium">{concept.name}</p>
                <p className="text-muted-foreground">{concept.aliases.length} alias(es)</p>
              </div>
            )) : (
              <p className="text-sm text-muted-foreground">No canonical concepts have been created yet.</p>
            )}
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Comparative graph boundaries</CardTitle>
          <CardDescription>Cross-project edges are review records and are only used when explicitly enabled.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>Project graphs stay isolated by default. Confirmed links preserve source and target project IDs so comparative views can show boundaries clearly.</p>
          <p>Open a project graph from the sidebar to inspect local context, then return here to compare reviewed cross-project relationships.</p>
        </CardContent>
      </Card>

      <Dialog open={Boolean(selectedSuggestion)} onOpenChange={(open) => !open && setSelectedSuggestion(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm cross-project link</DialogTitle>
            <DialogDescription>Provide an explicit rationale. This will not merge project graphs.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Label htmlFor="rationale">Rationale</Label>
            <Textarea id="rationale" value={rationale} onChange={(event) => setRationale(event.target.value)} />
            <Button disabled={!rationale.trim() || confirm.isPending} onClick={() => confirm.mutate()}>
              {confirm.isPending ? "Confirming..." : "Confirm link"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SampleChunks({ title, chunks }: { title: string; chunks: LinkSuggestion["source_entity"]["sample_chunks"] }) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium">{title}</h3>
      {chunks.length ? chunks.map((chunk) => (
        <div key={chunk.chunk_id} className="rounded-md border p-3 text-sm">
          <p className="font-medium">{chunk.citation}</p>
          <p className="mt-1 text-muted-foreground">{chunk.text}</p>
        </div>
      )) : <p className="text-sm text-muted-foreground">No sample chunks available.</p>}
    </div>
  );
}
