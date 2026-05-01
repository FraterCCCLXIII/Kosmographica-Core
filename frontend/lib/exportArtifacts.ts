import type { Cluster, Document, GraphEdge, GraphNode, RAGResponse, UUID } from "@/lib/types";

type ExportFormat = "json" | "markdown";

interface ProjectSummaryPayload {
  project_id: UUID;
  generated_at: string;
  counts: {
    documents: number;
    chunks: number;
    entities: number;
    graph_nodes: number;
    graph_edges: number;
  };
  documents: Array<Pick<Document, "id" | "title" | "status" | "source_type" | "source_uri">>;
  provenance: string;
}

interface GraphExportPayload {
  project_id: UUID;
  generated_at: string;
  query: string;
  seed_node_ids: string[];
  limits?: { depth: number; nodeLimit: number; edgeLimit: number };
  nodes: GraphNode[];
  edges: GraphEdge[];
  provenance: string;
}

interface SelectedGraphExportPayload {
  project_id: UUID;
  generated_at: string;
  selected_node_ids: string[];
  nodes: GraphNode[];
  evidence_edges: GraphEdge[];
  provenance: string;
}

type RagExportPayload = RAGResponse & {
  project_id: UUID;
  generated_at: string;
  question: string;
  provenance: string;
};

interface ClusterExportPayload {
  project_id: UUID;
  generated_at: string;
  cluster: Cluster;
  provenance: string;
}

export function downloadJson(filename: string, data: unknown) {
  downloadText(`${filename}.json`, JSON.stringify(data, null, 2), "application/json");
}

export function downloadMarkdown(filename: string, markdown: string) {
  downloadText(`${filename}.md`, markdown, "text/markdown;charset=utf-8");
}

export function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function exportProjectSummary(input: {
  projectId: UUID;
  documents: Document[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  format: ExportFormat;
}) {
  const payload: ProjectSummaryPayload = {
    project_id: input.projectId,
    generated_at: new Date().toISOString(),
    counts: {
      documents: input.documents.length,
      chunks: input.nodes.filter((node) => node.node_type === "chunk").length,
      entities: input.nodes.filter((node) => node.node_type === "entity").length,
      graph_nodes: input.nodes.length,
      graph_edges: input.edges.length
    },
    documents: input.documents.map((document) => ({
      id: document.id,
      title: document.title,
      status: document.status,
      source_type: document.source_type,
      source_uri: document.source_uri
    })),
    provenance: "Project summary uses the currently loaded project documents, graph nodes, and graph edges."
  };
  if (input.format === "json") downloadJson(`kosmographica-project-summary-${input.projectId}`, payload);
  else downloadMarkdown(`kosmographica-project-summary-${input.projectId}`, projectSummaryMarkdown(payload));
}

export function exportGraphSearch(input: {
  projectId: UUID;
  query?: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  seedNodeIds?: string[];
  limits?: { depth: number; nodeLimit: number; edgeLimit: number };
  format: ExportFormat;
}) {
  const payload: GraphExportPayload = {
    project_id: input.projectId,
    generated_at: new Date().toISOString(),
    query: input.query ?? "bounded graph overview",
    seed_node_ids: input.seedNodeIds ?? [],
    limits: input.limits,
    nodes: input.nodes,
    edges: input.edges,
    provenance: "Graph export contains only the currently loaded bounded graph/search result."
  };
  if (input.format === "json") downloadJson(`kosmographica-graph-${input.projectId}`, payload);
  else downloadMarkdown(`kosmographica-graph-${input.projectId}`, graphMarkdown(payload));
}

export function exportSelectedGraphEvidence(input: {
  projectId: UUID;
  selectedNodeIds: string[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  format: ExportFormat;
}) {
  const selected = new Set(input.selectedNodeIds);
  const selectedNodes = input.nodes.filter((node) => selected.has(node.id));
  const evidenceEdges = input.edges.filter((edge) => selected.has(edge.source_node_id) || selected.has(edge.target_node_id));
  const payload: SelectedGraphExportPayload = {
    project_id: input.projectId,
    generated_at: new Date().toISOString(),
    selected_node_ids: input.selectedNodeIds,
    nodes: selectedNodes,
    evidence_edges: evidenceEdges,
    provenance: "Selection export includes selected nodes and currently loaded edges touching those nodes."
  };
  if (input.format === "json") downloadJson(`kosmographica-selection-${input.projectId}`, payload);
  else downloadMarkdown(`kosmographica-selection-${input.projectId}`, selectedGraphMarkdown(payload));
}

export function exportRagAnswer(input: { projectId: UUID; question: string; response: RAGResponse; format: ExportFormat }) {
  const payload: RagExportPayload = {
    project_id: input.projectId,
    generated_at: new Date().toISOString(),
    question: input.question,
    ...input.response,
    provenance: "RAG export includes validated citations, retrieved chunks, graph paths, and confidence rationale."
  };
  if (input.format === "json") downloadJson(`kosmographica-rag-answer-${input.projectId}`, payload);
  else downloadMarkdown(`kosmographica-rag-answer-${input.projectId}`, ragMarkdown(payload));
}

export function exportClusterReport(input: { projectId: UUID; cluster: Cluster; format: ExportFormat }) {
  const payload: ClusterExportPayload = {
    project_id: input.projectId,
    generated_at: new Date().toISOString(),
    cluster: input.cluster,
    provenance: "Cluster export includes stored cluster metadata, source chunks, top entities, claims, and algorithm details."
  };
  if (input.format === "json") downloadJson(`kosmographica-cluster-${input.cluster.id}`, payload);
  else downloadMarkdown(`kosmographica-cluster-${input.cluster.id}`, clusterMarkdown(payload));
}

function downloadText(filename: string, content: string, type: string) {
  downloadBlob(filename, new Blob([content], { type }));
}

function projectSummaryMarkdown(payload: ProjectSummaryPayload) {
  const counts = payload.counts;
  return [
    `# Project Summary`,
    "",
    `Project: ${payload.project_id}`,
    `Generated: ${payload.generated_at}`,
    "",
    `## Counts`,
    `- Documents: ${counts.documents}`,
    `- Chunks: ${counts.chunks}`,
    `- Entities: ${counts.entities}`,
    `- Graph nodes: ${counts.graph_nodes}`,
    `- Graph edges: ${counts.graph_edges}`,
    "",
    `## Documents`,
    ...payload.documents.map((document) => `- ${document.title} (${document.status}) - ${document.source_uri ?? document.source_type}`),
    "",
    `## Provenance`,
    payload.provenance
  ].join("\n");
}

function graphMarkdown(payload: GraphExportPayload) {
  return [
    `# Graph Export`,
    "",
    `Project: ${payload.project_id}`,
    `Query: ${payload.query}`,
    `Generated: ${payload.generated_at}`,
    payload.limits ? `Limits: depth ${payload.limits.depth}, nodes ${payload.limits.nodeLimit}, edges ${payload.limits.edgeLimit}` : "",
    "",
    `## Nodes (${payload.nodes.length})`,
    ...payload.nodes.map((node) => `- ${node.label} (${node.node_type}) [${node.id}]`),
    "",
    `## Edges (${payload.edges.length})`,
    ...payload.edges.map((edge) => `- ${edge.edge_type}: ${edge.source_node_id} -> ${edge.target_node_id}; evidence ${edge.evidence_chunk_id}`),
    "",
    `## Provenance`,
    payload.provenance
  ].join("\n");
}

function selectedGraphMarkdown(payload: SelectedGraphExportPayload) {
  return [
    `# Selected Graph Evidence`,
    "",
    `Project: ${payload.project_id}`,
    `Generated: ${payload.generated_at}`,
    "",
    `## Selected Nodes`,
    ...payload.nodes.map((node) => `- ${node.label} (${node.node_type}) [${node.id}]`),
    "",
    `## Evidence Edges`,
    ...payload.evidence_edges.map((edge) => `- ${edge.edge_type}: ${edge.source_node_id} -> ${edge.target_node_id}; evidence ${edge.evidence_chunk_id}`),
    "",
    `## Provenance`,
    payload.provenance
  ].join("\n");
}

function ragMarkdown(payload: RagExportPayload) {
  return [
    `# RAG Answer`,
    "",
    `Project: ${payload.project_id}`,
    `Generated: ${payload.generated_at}`,
    "",
    `## Question`,
    payload.question,
    "",
    `## Answer`,
    payload.answer,
    "",
    `## Confidence`,
    `${payload.confidence}: ${payload.confidence_rationale ?? "No rationale provided."}`,
    "",
    `## Citations`,
    ...payload.citations.map((citation) => `- [${citation.chunk_id}] ${citation.citation}`),
    "",
    `## Retrieved Chunks`,
    ...payload.retrieved_chunks.map((chunk) => `- [${chunk.chunk_id}] score ${chunk.similarity_score.toFixed(3)}: ${chunk.text}`),
    "",
    `## Provenance`,
    payload.provenance
  ].join("\n");
}

function clusterMarkdown(payload: ClusterExportPayload) {
  const metadata = payload.cluster.metadata;
  return [
    `# Cluster Report`,
    "",
    `Project: ${payload.project_id}`,
    `Cluster: ${payload.cluster.label}`,
    `Generated: ${payload.generated_at}`,
    "",
    `## Summary`,
    payload.cluster.description ?? "",
    "",
    `## Algorithm`,
    payload.cluster.algorithm,
    "",
    `## Metadata`,
    "```json",
    JSON.stringify(metadata, null, 2),
    "```",
    "",
    `## Provenance`,
    payload.provenance
  ].join("\n");
}
