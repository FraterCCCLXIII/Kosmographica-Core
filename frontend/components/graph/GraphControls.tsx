"use client";

import { Pause, Play, RotateCcw, Search, ZoomIn, ZoomOut } from "lucide-react";

import type { GraphFilters } from "@/components/graph/GraphCanvas";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { GraphEdge, GraphNode } from "@/lib/types";

interface GraphControlsProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  filters: GraphFilters;
  searchQuery: string;
  isLayoutRunning: boolean;
  onFiltersChange: (filters: GraphFilters) => void;
  onSearchChange: (value: string) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetLayout: () => void;
  onToggleLayout: () => void;
}

export function GraphControls({
  nodes,
  edges,
  filters,
  searchQuery,
  isLayoutRunning,
  onFiltersChange,
  onSearchChange,
  onZoomIn,
  onZoomOut,
  onResetLayout,
  onToggleLayout
}: GraphControlsProps) {
  const nodeTypes = unique(nodes.map((node) => node.node_type));
  const edgeTypes = unique(edges.map((edge) => edge.edge_type));
  const traditions = unique(nodes.map((node) => stringMetadata(node.metadata.tradition)).filter(Boolean));
  const regions = unique(nodes.map((node) => stringMetadata(node.metadata.region)).filter(Boolean));

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Graph controls</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <Label htmlFor="graph-search">Search label</Label>
          <div className="relative">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input id="graph-search" className="pl-8" value={searchQuery} onChange={(event) => onSearchChange(event.target.value)} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <Button variant="outline" onClick={onZoomIn}><ZoomIn className="mr-2 h-4 w-4" />Zoom in</Button>
          <Button variant="outline" onClick={onZoomOut}><ZoomOut className="mr-2 h-4 w-4" />Zoom out</Button>
          <Button variant="outline" onClick={onResetLayout}><RotateCcw className="mr-2 h-4 w-4" />Reset</Button>
          <Button variant="outline" onClick={onToggleLayout}>
            {isLayoutRunning ? <Pause className="mr-2 h-4 w-4" /> : <Play className="mr-2 h-4 w-4" />}
            {isLayoutRunning ? "Pause" : "Resume"}
          </Button>
        </div>

        <Checklist
          title="Node types"
          values={nodeTypes}
          selected={filters.nodeTypes}
          onToggle={(value) => onFiltersChange({ ...filters, nodeTypes: toggleSet(filters.nodeTypes, value) })}
        />
        <Checklist
          title="Edge types"
          values={edgeTypes}
          selected={filters.edgeTypes}
          onToggle={(value) => onFiltersChange({ ...filters, edgeTypes: toggleSet(filters.edgeTypes, value) })}
        />

        <div className="space-y-3">
          <h3 className="text-sm font-medium">Metadata filters</h3>
          <SelectLike label="Tradition" value={filters.tradition ?? ""} values={traditions} onChange={(tradition) => onFiltersChange({ ...filters, tradition: tradition || undefined })} />
          <SelectLike label="Region" value={filters.region ?? ""} values={regions} onChange={(region) => onFiltersChange({ ...filters, region: region || undefined })} />
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label>Date from</Label>
              <Input value={filters.dateFrom ?? ""} onChange={(event) => onFiltersChange({ ...filters, dateFrom: event.target.value || undefined })} />
            </div>
            <div className="space-y-1">
              <Label>Date to</Label>
              <Input value={filters.dateTo ?? ""} onChange={(event) => onFiltersChange({ ...filters, dateTo: event.target.value || undefined })} />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function Checklist({ title, values, selected, onToggle }: { title: string; values: string[]; selected: Set<string>; onToggle: (value: string) => void }) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium">{title}</h3>
      <div className="space-y-2">
        {values.map((value) => (
          <label key={value} className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={selected.size === 0 || selected.has(value)} onChange={() => onToggle(value)} />
            <span>{value}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

function SelectLike({ label, value, values, onChange }: { label: string; value: string; values: string[]; onChange: (value: string) => void }) {
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Any</option>
        {values.map((item) => <option key={item} value={item}>{item}</option>)}
      </select>
    </div>
  );
}

function toggleSet(source: Set<string>, value: string) {
  const next = new Set(source);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

function unique(values: string[]) {
  return Array.from(new Set(values)).sort();
}

function stringMetadata(value: unknown) {
  return typeof value === "string" ? value : "";
}
