import React from "react";

export default function DreamReport({ report, store }) {
  if (!report) return <div className="placeholder">no dreams yet — press Sleep</div>;

  // went_dormant is a list of bare memory ids; resolve each to its readable text
  // (episode text / fact statement) from the store, falling back to the id.
  const textById = {};
  for (const e of store?.episodes ?? []) textById[e.id] = e.text;
  for (const f of store?.facts ?? []) textById[f.id] = f.statement;

  const SECTIONS = [
    ["learned", "Learned", (x) => x.statement],
    ["strengthened", "Strengthened", (x) => x.statement],
    ["superseded", "Superseded", (x) => x.statement],
    ["went_dormant", "Faded into dormancy", (x) => textById[x] ?? x],
  ];

  const quiet = SECTIONS.every(([key]) => (report[key] || []).length === 0);
  return (
    <div className="dream">
      <div className="dreamhead">
        night of day {Math.floor(report.day)} ·
        {" "}{report.episodes_consolidated} episodes consolidated
      </div>
      {quiet && <div className="muted">a quiet night — nothing new to keep</div>}
      {SECTIONS.map(([key, title, label]) =>
        (report[key] || []).length === 0 ? null : (
          <div key={key} className="dreamsec">
            <h3>{title}</h3>
            <ul>
              {report[key].map((item, i) => (
                <li key={i} className="fadein" style={{ animationDelay: `${i * 90}ms` }}>
                  {label(item)}
                </li>
              ))}
            </ul>
          </div>
        ))}
    </div>
  );
}
