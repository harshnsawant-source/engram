import React from "react";

export default function DreamReport({ report, store }) {
  if (!report) return <div className="placeholder">nothing yet · press Sleep</div>;

  // went_dormant is a list of bare memory ids; resolve each to readable text.
  const textById = {};
  for (const e of store?.episodes ?? []) textById[e.id] = e.text;
  for (const f of store?.facts ?? []) textById[f.id] = f.statement;

  const SECTIONS = [
    ["learned", "Learned", "new facts distilled from the day", (x) => x.statement],
    ["strengthened", "Strengthened", "facts the day confirmed again", (x) => x.statement],
    ["superseded", "Replaced", "older facts the day contradicted", (x) => x.statement],
    ["went_dormant", "Faded", "memories unused long enough to fade", (x) => textById[x] ?? x],
  ];

  const quiet = SECTIONS.every(([key]) => (report[key] || []).length === 0);
  return (
    <div className="dream">
      <p className="dreamhead">
        <span className="moon" aria-hidden>☾</span> Night of day {Math.floor(report.day)} ·{" "}
        {report.episodes_consolidated} {report.episodes_consolidated === 1 ? "episode" : "episodes"} consolidated
      </p>
      {quiet && <p className="muted">A quiet night: nothing new worth keeping.</p>}
      {SECTIONS.map(([key, title, sub, label]) =>
        (report[key] || []).length === 0 ? null : (
          <section key={key} className={`dreamsec ${key}`}>
            <h3>{title} <span>{sub}</span></h3>
            <ul>
              {report[key].map((item, i) => (
                <li key={i} className="fadein" style={{ animationDelay: `${i * 90}ms` }}>
                  {String(label(item)).replace(/^[\s;:,.-]+/, "")}
                </li>
              ))}
            </ul>
          </section>
        ))}
    </div>
  );
}
