import type {
  Document,
  DocumentStatusResponse,
  CrossProjectLink,
  GraphEdge,
  GraphNode,
  GlobalCanonicalEntity,
  JsonObject,
  LinkSuggestion,
  ListResponse,
  ProcessingJob,
  Project,
  RAGResponse,
  SearchResult,
  UUID,
  Workspace
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly details?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: init?.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store"
  });

  if (!response.ok) {
    let details: unknown;
    try {
      details = await response.json();
    } catch {
      details = await response.text();
    }
    const message =
      typeof details === "object" && details && "detail" in details ? String(details.detail) : response.statusText;
    throw new ApiError(response.status, message, details);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function body(value: unknown): RequestInit {
  return { method: "POST", body: JSON.stringify(value) };
}

function listItems<T>(response: ListResponse<T>): T[] {
  return response.data.items ?? [];
}

export const api = {
  async listWorkspaces(): Promise<Workspace[]> {
    return listItems(await request<ListResponse<Workspace>>("/workspaces"));
  },
  async createWorkspace(input: { name: string; description?: string }): Promise<Workspace> {
    const response = await request<{ data: Workspace }>("/workspaces", body(input));
    return response.data;
  },
  async getWorkspace(workspaceId: UUID): Promise<Workspace> {
    const response = await request<{ data: Workspace }>(`/workspaces/${workspaceId}`);
    return response.data;
  },
  async updateWorkspace(workspaceId: UUID, input: Partial<Workspace>): Promise<Workspace> {
    const response = await request<{ data: Workspace }>(`/workspaces/${workspaceId}`, {
      method: "PUT",
      body: JSON.stringify(input)
    });
    return response.data;
  },
  async deleteWorkspace(workspaceId: UUID): Promise<void> {
    await request(`/workspaces/${workspaceId}`, { method: "DELETE" });
  },
  async listProjects(workspaceId: UUID): Promise<Project[]> {
    return listItems(await request<ListResponse<Project>>(`/workspaces/${workspaceId}/projects`));
  },
  async createProject(workspaceId: UUID, input: Partial<Project> & { name: string }): Promise<Project> {
    const response = await request<{ data: Project }>(`/workspaces/${workspaceId}/projects`, body(input));
    return response.data;
  },
  async listDocuments(projectId: UUID): Promise<Document[]> {
    return listItems(await request<ListResponse<Document>>(`/projects/${projectId}/documents`));
  },
  async getDocument(documentId: UUID): Promise<Document> {
    const response = await request<{ data: Document }>(`/documents/${documentId}`);
    return response.data;
  },
  async deleteDocument(documentId: UUID): Promise<void> {
    await request(`/documents/${documentId}`, { method: "DELETE" });
  },
  async uploadDocument(input: { projectId: UUID; file: File; title?: string }): Promise<{ document_id: UUID; job_id: UUID; status: string }> {
    const formData = new FormData();
    formData.append("project_id", input.projectId);
    formData.append("file", input.file);
    if (input.title) {
      formData.append("title", input.title);
    }
    const response = await request<{ data: { document_id: UUID; job_id: UUID; status: string } }>("/documents/upload", {
      method: "POST",
      body: formData
    });
    return response.data;
  },
  async getDocumentStatus(documentId: UUID): Promise<DocumentStatusResponse["data"]> {
    const response = await request<DocumentStatusResponse>(`/documents/${documentId}/status`);
    return response.data;
  },
  async triggerProcessing(documentId: UUID): Promise<{ data: JsonObject }> {
    return request(`/processing/documents/${documentId}`, { method: "POST" });
  },
  async getProcessingJob(jobId: UUID): Promise<{ data: ProcessingJob }> {
    return request(`/processing/jobs/${jobId}`);
  },
  async getGraphNodes(projectId: UUID): Promise<GraphNode[]> {
    return listItems(await request<ListResponse<GraphNode>>(`/projects/${projectId}/graph/nodes`));
  },
  async getGraphEdges(projectId: UUID): Promise<GraphEdge[]> {
    return listItems(await request<ListResponse<GraphEdge>>(`/projects/${projectId}/graph/edges`));
  },
  async getSubgraph(projectId: UUID, options?: { nodeId?: UUID; depth?: number }): Promise<{ nodes: GraphNode[]; edges: GraphEdge[] }> {
    const params = new URLSearchParams();
    if (options?.nodeId) params.set("node_id", options.nodeId);
    if (options?.depth) params.set("depth", String(options.depth));
    const query = params.toString();
    const response = await request<{ data: { nodes: GraphNode[]; edges: GraphEdge[] } }>(`/projects/${projectId}/graph/subgraph${query ? `?${query}` : ""}`);
    return response.data;
  },
  async saveResearchNote(input: { project_id: UUID; title: string; body: string; graph_node_ids: UUID[]; chunk_ids?: UUID[]; metadata?: JsonObject }): Promise<void> {
    await request("/research-notes", body(input));
  },
  async vectorSearch(input: { query: string; project_id: UUID; k?: number; filters?: JsonObject }): Promise<SearchResult[]> {
    return request<SearchResult[]>("/search/vector", body(input));
  },
  async ragQuery(input: { question: string; project_id: UUID; mode: string; k?: number }): Promise<RAGResponse> {
    return request<RAGResponse>("/search/query", body(input));
  },
  async comparativeQuery(input: { question: string; project_ids: UUID[]; k?: number }): Promise<RAGResponse> {
    return request<RAGResponse>("/search/comparative", body(input));
  },
  async listCrossProjectSuggestions(workspaceId: UUID): Promise<LinkSuggestion[]> {
    return request<LinkSuggestion[]>(`/workspaces/${workspaceId}/cross-project/suggestions`);
  },
  async listCrossProjectLinks(workspaceId: UUID): Promise<CrossProjectLink[]> {
    return request<CrossProjectLink[]>(`/workspaces/${workspaceId}/cross-project/links`);
  },
  async confirmCrossProjectLink(workspaceId: UUID, input: { suggestion: LinkSuggestion; rationale: string }): Promise<CrossProjectLink> {
    return request<CrossProjectLink>(`/workspaces/${workspaceId}/cross-project/links/confirm`, body(input));
  },
  async rejectCrossProjectLink(workspaceId: UUID, suggestionId: UUID | string): Promise<CrossProjectLink> {
    return request<CrossProjectLink>(`/workspaces/${workspaceId}/cross-project/links/reject`, body({ suggestion_id: suggestionId }));
  },
  async promoteToGlobalCanonical(workspaceId: UUID, entityId: UUID): Promise<GlobalCanonicalEntity> {
    return request<GlobalCanonicalEntity>(`/workspaces/${workspaceId}/cross-project/canonical/promote`, body({ entity_id: entityId }));
  },
  async exportProject(projectId: UUID, format: "json" | "graphml" | "csv" | "markdown"): Promise<Blob> {
    const response = await fetch(`${API_BASE_URL}/export/${projectId}/${format}`, { cache: "no-store" });
    if (!response.ok) {
      throw new ApiError(response.status, response.statusText);
    }
    return response.blob();
  }
};
