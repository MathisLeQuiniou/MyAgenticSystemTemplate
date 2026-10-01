import dagre from "@dagrejs/dagre";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMemo } from "react";
import type { GraphDescription } from "../api/types";
import type { NodeVisit } from "../lib/trace";

const NODE_W = 150;
const NODE_H = 44;
const TERMINAL_SIZE = 18;
const GROUP_PAD = 28;

interface Props {
  graph: GraphDescription;
  visits: Map<string, NodeVisit>;
  edgesTaken: Set<string>;
  selectedNode: string | null;
  onSelectNode: (id: string | null) => void;
}

type AgentNodeData = { label: string; visit?: NodeVisit; selected: boolean; kind: string };

function AgentNode({ data }: NodeProps<Node<AgentNodeData>>) {
  const { label, visit, selected, kind } = data;
  if (kind !== "node") {
    return (
      <div className={`flow-terminal ${visit ? "visited" : ""}`} title={kind === "start" ? "START" : "END"}>
        <Handle type="target" position={Position.Top} />
        <Handle type="source" position={Position.Bottom} />
      </div>
    );
  }
  const status = visit?.status ?? "idle";
  return (
    <div className={`flow-node status-${status} ${selected ? "selected" : ""}`}>
      <Handle type="target" position={Position.Top} />
      <span className="flow-node-label">{label}</span>
      {visit && <span className="flow-node-order">{visit.order.join(", ")}</span>}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}

function GroupNode({ data }: NodeProps<Node<{ label: string; visited: boolean }>>) {
  return (
    <div className={`flow-group ${data.visited ? "visited" : ""}`}>
      <span className="flow-group-label">{data.label}</span>
    </div>
  );
}

const nodeTypes = { agent: AgentNode, group: GroupNode };

function layout(graph: GraphDescription) {
  const g = new dagre.graphlib.Graph({ compound: true });
  g.setGraph({ rankdir: "TB", nodesep: 40, ranksep: 50, marginx: 10, marginy: 10 });
  g.setDefaultEdgeLabel(() => ({}));

  const groups = new Set(graph.nodes.map((n) => n.parent).filter(Boolean) as string[]);
  groups.forEach((grp) => g.setNode(grp, { label: grp, paddingTop: GROUP_PAD, paddingLeft: 16, paddingRight: 16, paddingBottom: 12 }));
  for (const n of graph.nodes) {
    const size = n.kind === "node" ? { width: NODE_W, height: NODE_H } : { width: TERMINAL_SIZE, height: TERMINAL_SIZE };
    g.setNode(n.id, { label: n.label, ...size });
    if (n.parent) g.setParent(n.id, n.parent);
  }
  for (const e of graph.edges) g.setEdge(e.source, e.target);
  dagre.layout(g);
  return { g, groups };
}

export function GraphView({ graph, visits, edgesTaken, selectedNode, onSelectNode }: Props) {
  const laidOut = useMemo(() => layout(graph), [graph]);

  const { nodes, edges } = useMemo(() => {
    const { g, groups } = laidOut;
    const nodes: Node[] = [];
    const touched = new Set([...edgesTaken].flatMap((e) => e.split("->")));
    const topLeft = (id: string) => {
      const n = g.node(id);
      return { x: n.x - n.width / 2, y: n.y - n.height / 2 };
    };

    // Groups first: React Flow requires parents before children.
    groups.forEach((grp) => {
      const n = g.node(grp);
      const visited = [...visits.keys()].some((k) => k.startsWith(grp + ":"));
      nodes.push({
        id: grp,
        type: "group",
        position: topLeft(grp),
        data: { label: grp, visited },
        style: { width: n.width, height: n.height },
        selectable: false,
        draggable: false,
      });
    });
    for (const n of graph.nodes) {
      const pos = topLeft(n.id);
      const parentPos = n.parent ? topLeft(n.parent) : { x: 0, y: 0 };
      const isStartEnd = n.kind !== "node";
      nodes.push({
        id: n.id,
        type: "agent",
        position: { x: pos.x - parentPos.x, y: pos.y - parentPos.y },
        parentId: n.parent ?? undefined,
        extent: n.parent ? "parent" : undefined,
        data: {
          label: n.label,
          kind: n.kind,
          selected: selectedNode === n.id,
          visit: isStartEnd ? (touched.has(n.id) ? ({ nodeId: n.id, order: [], status: "ok" } as NodeVisit) : undefined) : visits.get(n.id),
        },
        draggable: false,
      });
    }

    const edges: Edge[] = graph.edges.map((e) => {
      const taken = edgesTaken.has(`${e.source}->${e.target}`);
      return {
        id: `${e.source}->${e.target}`,
        source: e.source,
        target: e.target,
        label: e.label ?? undefined,
        animated: taken,
        className: taken ? "edge-taken" : e.conditional ? "edge-conditional" : "",
        markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
        zIndex: 1,
      };
    });
    return { nodes, edges };
  }, [laidOut, graph, visits, edgesTaken, selectedNode]);

  return (
    <div className="graph-view">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        nodesConnectable={false}
        onNodeClick={(_, node) => {
          if (node.type !== "agent" || (node.data as AgentNodeData).kind !== "node") return;
          onSelectNode(selectedNode === node.id ? null : node.id);
        }}
        onPaneClick={() => onSelectNode(null)}
        minZoom={0.3}
      >
        <Background gap={18} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
