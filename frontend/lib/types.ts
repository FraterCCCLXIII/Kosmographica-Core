export type UUID = string;

export type JsonObject = Record<string, unknown>;

export type DocumentStatus =
  | "pending"
  | "processing"
  | "ready"
  | "uploaded"
  | "parsing"
  | "parsed"
  | "chunking"
  | "chunked"
  | "embedding"
  | "embedded"
  | "extracting"
  | "graph_ready"
  | "failed";

export type JobStatus = "queued" | "running" | "retrying" | "succeeded" | "failed" | "cancelled";

export interface Workspace {
  id: UUID;
  name: string;
  description?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface Project {
  id: UUID;
  workspace_id: UUID;
  name: string;
  description?: string | null;
  domain?: string | null;
  ontology_config: JsonObject;
  embedding_config: JsonObject;
  extraction_config: JsonObject;
  graph_config: JsonObject;
  created_at?: string;
  updated_at?: string;
}

export interface Document {
  id: UUID;
  project_id: UUID;
  title: string;
  source_type: string;
  source_uri?: string | null;
  author?: string | null;
  date?: string | null;
  tradition?: string | null;
  region?: string | null;
  language?: string | null;
  metadata: JsonObject;
  raw_text?: string | null;
  status: DocumentStatus;
  created_at?: string;
  updated_at?: string;
}

export interface Chunk {
  id: UUID;
  project_id: UUID;
  document_id: UUID;
  chunk_index: number;
  text: string;
  token_count: number;
  citation: string;
  metadata: JsonObject;
  created_at?: string;
}

export interface Entity {
  id: UUID;
  project_id: UUID;
  canonical_name: string;
  entity_type: string;
  aliases: string[];
  description?: string | null;
  metadata: JsonObject;
  created_at?: string;
}

export interface Concept {
  id: UUID;
  project_id: UUID;
  name: string;
  description?: string | null;
  aliases: string[];
  metadata: JsonObject;
  created_at?: string;
}

export interface Claim {
  id: UUID;
  project_id: UUID;
  chunk_id: UUID;
  subject: string;
  predicate: string;
  object: string;
  confidence: number;
  evidence_text: string;
  metadata: JsonObject;
  created_at?: string;
}

export interface GraphNode {
  id: UUID;
  project_id: UUID;
  node_type: string;
  ref_id?: UUID | null;
  label: string;
  metadata: JsonObject;
  created_at?: string;
}

export interface GraphEdge {
  id: UUID;
  project_id: UUID;
  source_node_id: UUID;
  target_node_id: UUID;
  edge_type: string;
  weight: number;
  confidence: number;
  evidence_chunk_id: UUID;
  metadata: JsonObject;
  created_at?: string;
}

export interface GraphStats {
  project_id: UUID;
  node_count: number;
  edge_count: number;
  edge_types: Record<string, number>;
}

export interface SearchResult {
  chunk_id: UUID;
  document_id: UUID;
  text: string;
  citation: string;
  similarity_score: number;
  metadata: JsonObject;
  project_id?: UUID | null;
}

export interface Citation {
  chunk_id: UUID;
  document_id: UUID;
  citation: string;
  text: string;
}

export interface Subgraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface RAGResponse {
  answer: string;
  citations: Citation[];
  retrieved_chunks: SearchResult[];
  graph_paths: Subgraph[];
  mode: "single" | "comparative" | "global" | string;
  confidence: "high" | "medium" | "low" | "insufficient_evidence";
  confidence_rationale?: string;
}

export interface EntityDetail {
  entity: Entity;
  graph_node?: GraphNode | null;
  chunks: Chunk[];
  claims: Claim[];
  connected_nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface DocumentGraphSummary {
  document_id: UUID;
  node_counts: Record<string, number>;
  edge_counts: Record<string, number>;
  top_entities: Entity[];
  top_concepts: Concept[];
  top_claims: Claim[];
}

export interface ProcessingStage {
  name: string;
  job_id: UUID;
  status: JobStatus | string;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

export interface ProcessingTimeline {
  document_id: UUID;
  document_status: DocumentStatus;
  jobs: ProcessingJob[];
  stages: ProcessingStage[];
}

export interface Cluster {
  id: UUID;
  project_id: UUID;
  label: string;
  description?: string | null;
  algorithm: string;
  metadata: JsonObject;
  member_count?: number;
  created_at?: string | null;
}

export interface ProcessingJob {
  id?: UUID;
  job_id?: UUID;
  project_id?: UUID;
  document_id?: UUID | null;
  job_type: string;
  status: JobStatus;
  error_message?: string | null;
  metadata: JsonObject;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ResearchNote {
  id: UUID;
  project_id: UUID;
  title: string;
  body: string;
  query_text?: string | null;
  chunk_ids: UUID[];
  graph_node_ids: UUID[];
  metadata: JsonObject;
  created_at?: string;
  updated_at?: string;
}

export type ConversationMode = "single" | "comparative" | "global" | string;
export type ConversationStatus = "active" | "archived" | string;
export type ConversationMessageRole = "user" | "assistant" | "tool";
export type ConversationMessageStatus = "queued" | "generating" | "complete" | "failed";

export interface Conversation {
  id: UUID;
  workspace_id: UUID;
  project_id?: UUID | null;
  title: string;
  mode: ConversationMode;
  status: ConversationStatus;
  context: JsonObject;
  metadata: JsonObject;
  created_at?: string | null;
  updated_at?: string | null;
  messages?: ConversationMessage[];
}

export interface ConversationMessage {
  id: UUID;
  conversation_id: UUID;
  role: ConversationMessageRole;
  status: ConversationMessageStatus;
  content: string;
  citations: Citation[];
  retrieved_chunks: SearchResult[];
  graph_paths: Subgraph[];
  tool_calls: JsonObject[];
  confidence?: RAGResponse["confidence"] | null;
  metadata: JsonObject;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ConversationListResponse {
  items: Conversation[];
  total: number;
  limit: number;
  offset: number;
  workspace_id: UUID;
}

export interface EntitySummary {
  id: UUID;
  project_id: UUID;
  canonical_name: string;
  entity_type: string;
  sample_chunks: Array<{
    chunk_id: UUID;
    citation: string;
    text: string;
  }>;
}

export interface LinkSuggestion {
  suggestion_id: string;
  workspace_id: UUID;
  source_project_id: UUID;
  target_project_id: UUID;
  source_entity: EntitySummary;
  target_entity: EntitySummary;
  link_type: string;
  confidence: number;
  similarity_score: number;
}

export interface CrossProjectLink {
  id: UUID;
  workspace_id: UUID;
  source_project_id: UUID;
  target_project_id: UUID;
  source_ref_type: string;
  source_ref_id: UUID;
  target_ref_type: string;
  target_ref_id: UUID;
  link_type: string;
  confidence: number;
  rationale: string;
  metadata: JsonObject;
  created_at?: string | null;
}

export interface GlobalCanonicalEntity {
  id: UUID;
  workspace_id: UUID;
  canonical_name: string;
  entity_type: string;
  aliases: string[];
  description?: string | null;
  metadata: JsonObject;
  created_at?: string | null;
}

export interface GlobalCanonicalConcept {
  id: UUID;
  workspace_id: UUID;
  name: string;
  aliases: string[];
  description?: string | null;
  metadata: JsonObject;
  created_at?: string | null;
}

export interface ListResponse<T> {
  message?: string;
  data: {
    items?: T[];
    [key: string]: unknown;
  };
}

export interface DocumentStatusResponse {
  message: string;
  data: {
    document_id: UUID;
    document_status: DocumentStatus;
    job: ProcessingJob | null;
  };
}
