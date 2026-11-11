import React, { useMemo, useState } from "react";

// Memory map. Consolidated facts sit in the middle, raw episodes ring them.
// Size = current strength; faded (dormant) memories are faint and dashed.
// `focus` is a set of memory ids to highlight (e.g. the ones a reply cited).

const GOLDEN = 137.508;
const C = 300;

function layout(nodes) {
  const facts = nodes.filter((n) => n.type === "fact");
  const episodes = nodes.filter((n) => n.type === "episode");
  const pos = {};
  const place = (list, r0, spread) =>
    list.forEach((n, i) => {
      const a = ((i * GOLDEN + 18) % 360) * (Math.PI / 180);
      const r = r0 + ((i * 7) % 3) * spread;
      pos[n.id] = { x: C + r * Math.cos(a), y: C + r * Math.sin(a) };
    });
  place(facts, facts.length > 6 ? 70 : 60, 26);
  place(episodes, 190, 30);
  return pos;
}

export default function MemoryGraph({ graph, focus }) {
  const [hover, setHover] = useState(null);
  const pos = useMemo(() => layout(graph.nodes), [graph]);
  const edges = graph.edges.filter((e) => pos[e.source] && pos[e.target]);
  const superseded = useMemo(
    () => new Set(graph.edges.filter((e) => e.kind === "supersedes").map((e) => e.target)),
    [graph],
  );
  const lit = focus && focus.size > 0;

  if (graph.nodes.length === 0) return <div className="placeholder">no memories yet</div>;

  return (
    <div className="graphwrap">
      <svg viewBox="0 0 600 600" className="graph" role="img" aria-label="Memory map: facts in the centre, episodes around them">
        <circle cx={C} cy={C} r="120" className="ring" />
        <circle cx={C} cy={C} r="230" className="ring" />
        {edges.map((e, i) => {
          const on = lit && (focus.has(e.source) || focus.has(e.target));
          return (
            <line key={i} x1={pos[e.source].x} y1={pos[e.source].y}
              x2={pos[e.target].x} y2={pos[e.target].y}
              className={`edge ${e.kind} ${on ? "on" : ""} ${lit && !on ? "dim" : ""}`} />
          );
        })}
        {graph.nodes.map((n) => {
          const p = pos[n.id];
          const r = 4.5 + 10 * n.strength;
          const on = lit && focus.has(n.id);
          const cls = ["node", n.type, n.dormant ? "dormant" : "", superseded.has(n.id) ? "superseded" : "",
            on ? "on" : "", lit && !on ? "dim" : ""].join(" ");
          return (
            <g key={n.id} className={cls} transform={`translate(${p.x} ${p.y})`}
              onMouseEnter={() => setHover(n)} onMouseLeave={() => setHover(null)}>
              {on && <circle r={r + 7} className="halo" />}
              <circle r={r} style={{ opacity: n.dormant ? 0.3 : 0.45 + 0.55 * n.strength }} />
            </g>
          );
        })}
      </svg>
      <div className="legend">
        <span><i className="sw fact" /> fact (consolidated)</span>
        <span><i className="sw episode" /> episode (raw)</span>
        <span><i className="sw dormant" /> fading</span>
        <span><i className="ln" /> came from</span>
        <span><i className="ln dashed" /> replaced by</span>
      </div>
      <div className={`nodecard ${hover ? "show" : ""}`}>
        {hover ? (
          <>
            <span className="mono">{hover.type} · strength {(hover.strength * 100).toFixed(0)}%{hover.dormant ? " · fading" : ""}</span>
            <span className="nodelabel">{hover.label}</span>
          </>
        ) : (
          <span className="mono muted">hover a memory · bigger means stronger</span>
        )}
      </div>
    </div>
  );
}
