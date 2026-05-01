"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorBanner } from "@/components/shared/ErrorBanner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreateWorkspace, useWorkspaces } from "@/lib/hooks/useWorkspaces";

export default function WorkspacesPage() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const workspaces = useWorkspaces();
  const createWorkspace = useCreateWorkspace();

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await createWorkspace.mutateAsync({ name, description });
    setName("");
    setDescription("");
    setOpen(false);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Workspaces</h1>
          <p className="text-sm text-muted-foreground">Group isolated research projects without merging provenance.</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>Create workspace</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create workspace</DialogTitle>
              <DialogDescription>Start a container for related research projects.</DialogDescription>
            </DialogHeader>
            <form className="space-y-4" onSubmit={onSubmit}>
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input id="name" value={name} onChange={(event) => setName(event.target.value)} required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea id="description" value={description} onChange={(event) => setDescription(event.target.value)} />
              </div>
              <ErrorBanner error={createWorkspace.error} />
              <Button type="submit" disabled={createWorkspace.isPending}>
                {createWorkspace.isPending ? "Creating..." : "Create"}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <ErrorBanner error={workspaces.error} />
      {workspaces.data?.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {workspaces.data.map((workspace) => (
            <Link key={workspace.id} href={`/workspaces/${workspace.id}`}>
              <Card className="h-full transition-colors hover:bg-muted/40">
                <CardHeader>
                  <CardTitle>{workspace.name}</CardTitle>
                  <CardDescription>{workspace.description || "No description yet."}</CardDescription>
                </CardHeader>
              </Card>
            </Link>
          ))}
        </div>
      ) : workspaces.isLoading ? (
        <Card><CardContent className="py-8">Loading workspaces...</CardContent></Card>
      ) : (
        <EmptyState title="No workspaces yet" description="Create a workspace to begin organizing research projects." />
      )}
    </div>
  );
}
