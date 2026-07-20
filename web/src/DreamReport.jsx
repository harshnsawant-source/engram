import React from "react";

const SECTIONS = [
  ["learned", "Learned", (x) => x.statement],
  ["strengthened", "Strengthened", (x) => x.statement],
  ["superseded", "Superseded", (x) => x.statement],
  ["went_dormant", "Faded into dormancy", (x) => x],
];

export default function DreamReport({ report }) {
  if (!report) return <div className="placeholder">no dreams yet — press Sleep</div>;
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
