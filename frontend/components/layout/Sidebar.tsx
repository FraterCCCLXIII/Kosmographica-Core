"use client";

import { BookOpen, Boxes, ChevronLeft, ChevronRight, CircleDot, GitCompare, LayoutDashboard, MessageSquare, Network, Plus, Search, Tags } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { RECENT_CONVERSATION_LIMIT, useRecentConversations } from "@/lib/hooks/useConversations";
import { cn } from "@/lib/utils";

const navItems = [
  ["Dashboard", "", LayoutDashboard],
  ["Documents", "documents", BookOpen],
  ["Graph", "graph", Network],
  ["Chat", "chat", MessageSquare],
  ["Entities", "entities", Tags],
  ["Clusters", "clusters", Boxes],
  ["Cross-project links", "__cross_project", GitCompare]
] as const;

export function Sidebar() {
  const params = useParams<{ workspaceId?: string; projectId?: string }>();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const conversations = useRecentConversations(params.workspaceId);

  useEffect(() => {
    const stored = window.localStorage.getItem("kosmo-sidebar-collapsed");
    if (stored) setCollapsed(stored === "true");
  }, []);

  function toggleCollapsed() {
    setCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem("kosmo-sidebar-collapsed", String(next));
      return next;
    });
  }

  if (!params.workspaceId) {
    return null;
  }

  const projectBase = params.projectId ? `/workspaces/${params.workspaceId}/projects/${params.projectId}` : undefined;
  const newConversationHref = `/workspaces/${params.workspaceId}/conversations/new${params.projectId ? `?project_id=${params.projectId}` : ""}`;
  const conversationsHref = `/workspaces/${params.workspaceId}/conversations`;

  return (
    <aside
      className={cn(
        "hidden shrink-0 border-r bg-muted/30 transition-[width] duration-200 md:block",
        collapsed ? "w-16" : "w-72"
      )}
    >
      <div className="flex h-full max-h-[calc(100vh-57px)] flex-col">
        <div className="flex items-center justify-between gap-2 border-b p-3">
          {!collapsed ? (
            <Link href="/workspaces" className="truncate text-sm font-semibold">
              Kosmographica
            </Link>
          ) : null}
          <Button
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
            className={cn("shrink-0", collapsed && "mx-auto")}
            size="sm"
            variant="ghost"
            onClick={toggleCollapsed}
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </Button>
        </div>

        <nav className="space-y-1 p-3" aria-label="Workspace navigation">
          <SidebarLink href={newConversationHref} label="New Conversation" collapsed={collapsed} active={pathname === newConversationHref}>
            <Plus className="h-4 w-4" />
          </SidebarLink>
          <SidebarLink href="/workspaces" label="Workspaces" collapsed={collapsed} active={pathname === "/workspaces"}>
            <CircleDot className="h-4 w-4" />
          </SidebarLink>
          <SidebarLink href={conversationsHref} label="Conversation History" collapsed={collapsed} active={pathname === conversationsHref}>
            <Search className="h-4 w-4" />
          </SidebarLink>
        </nav>

        {projectBase ? (
          <nav className="border-t p-3" aria-label="Project navigation">
            {!collapsed ? <p className="mb-2 px-2 text-xs font-medium text-muted-foreground">Project</p> : null}
            <div className="space-y-1">
              {navItems.map(([label, path, Icon]) => {
                const href = path === "__cross_project" ? `/workspaces/${params.workspaceId}/cross-project` : path ? `${projectBase}/${path}` : projectBase;
                return (
                  <SidebarLink key={label} href={href} label={label} collapsed={collapsed} active={pathname === href}>
                    <Icon className="h-4 w-4" />
                  </SidebarLink>
                );
              })}
            </div>
          </nav>
        ) : null}

        {!collapsed ? (
          <section className="min-h-0 flex-1 border-t p-3" aria-label="Recent conversations">
            <div className="mb-2 flex items-center justify-between gap-2 px-2">
              <p className="text-xs font-medium text-muted-foreground">Recent Conversations</p>
              <span className="text-xs text-muted-foreground">{RECENT_CONVERSATION_LIMIT}</span>
            </div>
            <div className="max-h-[calc(100vh-390px)] space-y-1 overflow-y-auto pr-1">
              {conversations.data?.items.length ? (
                conversations.data.items.map((conversation) => (
                  <Link
                    key={conversation.id}
                    href={`/workspaces/${params.workspaceId}/conversations/${conversation.id}`}
                    className={cn(
                      "block truncate rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-background hover:text-foreground",
                      pathname === `/workspaces/${params.workspaceId}/conversations/${conversation.id}` && "bg-background text-foreground"
                    )}
                    title={conversation.title}
                  >
                    {conversation.title}
                  </Link>
                ))
              ) : (
                <p className="px-2 py-1.5 text-sm text-muted-foreground">
                  {conversations.isLoading ? "Loading..." : "No conversations yet."}
                </p>
              )}
            </div>
            <Link
              href={conversationsHref}
              className="mt-2 block rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-background hover:text-foreground"
            >
              Show more
            </Link>
          </section>
        ) : null}
      </div>
    </aside>
  );
}

function SidebarLink({
  href,
  label,
  active,
  collapsed,
  children
}: {
  href: string;
  label: string;
  active: boolean;
  collapsed: boolean;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-2 rounded-md px-2 py-2 text-sm text-muted-foreground hover:bg-background hover:text-foreground",
        active && "bg-background text-foreground",
        collapsed && "justify-center"
      )}
      title={collapsed ? label : undefined}
      aria-label={collapsed ? label : undefined}
    >
      <span className="shrink-0">{children}</span>
      {!collapsed ? <span className="truncate">{label}</span> : null}
    </Link>
  );
}
