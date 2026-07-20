import React, { useMemo, useState } from "react";

const COLORS = { fact: "#8b5cf6", episode: "#0891b2", dormant: "#4b5563" };
const GOLDEN = 137.508;

function layout(nodes) {
  const facts = nodes.filter((n) => n.type === "fact");
  const episodes = nodes.filter((n) => n.type === "episode");
  const pos = {};
  const place = (list, r0) =>
    list.forEach((n, i) => {
      const a = ((i * GOLDEN) % 360) * (Math.PI / 180);
      const r = r0 + (i % 3) * 22;
      pos[n.id] = { x: 300 + r * Math.cos(a), y: 300 + r * Math.sin(a) };
    });
  place(facts, 90);
  place(episodes, 200);
  return pos;
}

const EDGE_STYLE = {
  provenance: { stroke: "#6b7280", dash: "", opacity: 0.35 },
  supersedes: { stroke: "#f59e0b", dash: "7 4", opacity: 0.8 },
  similar: { stroke: "#8b5cf6", dash: "2 5", opacity: 0.3 },
};

export default function MemoryGraph({ graph }) {
  const [hover, setHover] = useState(null);
  const pos = useMemo(() => layout(graph.nodes), [graph]);
  const byId = useMemo(
    () => Object.fromEntries(graph.nodes.map((n) => [n.id, n])), [graph]);
  const edges = graph.edges.filter((e) => pos[e.source] && pos[e.target]);

  return (
    <div className="graphwrap">
      <svg viewBox="0 0 600 600" className="graph">
        {edges.map((e, i) => {
          const s = EDGE_STYLE[e.kind] || EDGE_STYLE.provenance;
          return (
            <line key={i} x1={pos[e.source].x} y1={pos[e.source].y}
              x2={pos[e.target].x} y2={pos[e.target].y} stroke={s.stroke}
              strokeDasharray={s.dash} strokeOpacity={s.opacity} strokeWidth="1.5" />
          );
        })}
        {graph.nodes.map((n) => {
          const p = pos[n.id];
          const superseded = n.type === "fact" &&
            graph.edges.some((e) => e.kind === "supersedes" && e.target === n.id);
          const r = 5 + 9 * n.strength;
          const fill = n.dormant ? COLORS.dormant : COLORS[n.type];
          return (
            <circle key={n.id} cx={p.x} cy={p.y} r={r}
              fill={superseded ? "none" : fill}
              stroke={fill} strokeWidth={superseded ? 2 : 0}
              fillOpacity={n.dormant ? 0.35 : 0.4 + 0.6 * n.strength}
              onMouseEnter={() => setHover(n)} onMouseLeave={() => setHover(null)}>
              <title>{n.label}</title>
            </circle>
          );
        })}
      </svg>
      <div className="legend">
        <span><i className="sw" style={{ background: COLORS.fact }} /> fact</span>
        <span><i className="sw" style={{ background: COLORS.episode }} /> episode</span>
        <span><i className="sw" style={{ background: COLORS.dormant }} /> dormant</span>
        <span><i className="ln solid" /> provenance</span>
        <span><i className="ln dashed" /> supersedes</span>
        <span><i className="ln dotted" /> similar</span>
      </div>
      {hover && (
        <div className="nodecard">
          <b>{hover.type}</b> · strength {(hover.strength * 100).toFixed(0)}%
          {hover.dormant ? " · dormant" : ""}
          <div className="nodelabel">{hover.label}</div>
        </div>
      )}
    </div>
  );
}
