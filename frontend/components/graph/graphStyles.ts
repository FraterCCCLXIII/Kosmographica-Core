export const nodeTypeColors: Record<string, string> = {
  document: "#2563eb",
  chunk: "#64748b",
  entity: "#16a34a",
  concept: "#9333ea",
  claim: "#ea580c"
};

export const edgeTypeColors: Record<string, string> = {
  contains: "#94a3b8",
  mentions: "#22c55e",
  chunk_mentions_entity: "#22c55e",
  chunk_mentions_concept: "#a855f7",
  semantically_similar: "#0ea5e9",
  co_occurs_with: "#f59e0b"
};

export function colorForNodeType(nodeType: string) {
  return nodeTypeColors[nodeType] ?? "#0f172a";
}

export function colorForEdgeType(edgeType: string) {
  return edgeTypeColors[edgeType] ?? "#cbd5e1";
}
