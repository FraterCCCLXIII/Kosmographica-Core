"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useState } from "react";

import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useCreateProject, useProjects } from "@/lib/hooks/useProjects";

export default function WorkspaceProjectsPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [domain, setDomain] = useState("");
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("text-embedding-3-small");
  const projects = useProjects(workspaceId);
  const createProject = useCreateProject(workspaceId);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await createProject.mutateAsync({
      name,
      description,
      domain,
      embedding_config: { provider, model }
    });
    setName("");
    setDescription("");
    setDomain("");
    setOpen(false);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Projects</h1>
          <p className="text-sm text-muted-foreground">Each project is isolated by default and can later opt into comparison.</p>
        </div>
        <div className="flex gap-2">
          <Link href={`/workspaces/${workspaceId}/cross-project`}>
            <Button variant="outline">Cross-project links</Button>
          </Link>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button>Create project</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create project</DialogTitle>
              <DialogDescription>Configure the research graph and embedding provider for this corpus.</DialogDescription>
            </DialogHeader>
            <form className="space-y-4" onSubmit={onSubmit}>
              <div className="space-y-2"><Label>Name</Label><Input value={name} onChange={(event) => setName(event.target.value)} required /></div>
              <div className="space-y-2"><Label>Description</Label><Textarea value={description} onChange={(event) => setDescription(event.target.value)} /></div>
              <div className="space-y-2"><Label>Domain</Label><Input value={domain} onChange={(event) => setDomain(event.target.value)} placeholder="religion, history, mythology..." /></div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Embedding provider</Label>
                  <Select value={provider} onValueChange={setProvider}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent><SelectItem value="openai">OpenAI</SelectItem></SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Embedding model</Label>
                  <Select value={model} onValueChange={setModel}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent><SelectItem value="text-embedding-3-small">text-embedding-3-small</SelectItem></SelectContent>
                  </Select>
                </div>
              </div>
              <ErrorBanner error={createProject.error} />
              <Button type="submit" disabled={createProject.isPending}>{createProject.isPending ? "Creating..." : "Create"}</Button>
            </form>
          </DialogContent>
          </Dialog>
        </div>
      </div>

      <ErrorBanner error={projects.error} />
      {projects.data?.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {projects.data.map((project) => (
            <Link key={project.id} href={`/workspaces/${workspaceId}/projects/${project.id}`}>
              <Card className="h-full transition-colors hover:bg-muted/40">
                <CardHeader>
                  <CardTitle>{project.name}</CardTitle>
                  <CardDescription>{project.domain || "No domain"} · {project.description || "No description"}</CardDescription>
                </CardHeader>
              </Card>
            </Link>
          ))}
        </div>
      ) : projects.isLoading ? (
        <p>Loading projects...</p>
      ) : (
        <EmptyState title="No projects yet" description="Create a project to start an isolated research graph." />
      )}
    </div>
  );
}
