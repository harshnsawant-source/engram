import React, { useEffect, useMemo, useRef, useState } from "react";
import { post } from "./api.js";
import MemoryGraph from "./MemoryGraph.jsx";
import DreamReport from "./DreamReport.jsx";

const MAX_TURNS = 30;
const MAX_SLEEPS = 10;
const TABS = [
  ["graph", "Map"],
  ["facts", "Facts"],
  ["episodes", "Episodes"],
  ["dream", "Last night"],
];

// Three clicks that show the three behaviours: recall with citations,
// refusal, and learning something new (which only sticks after Sleep).
const STARTERS = [
  { kind: "recall", text: "What did Biscuit do with my key?" },
  { kind: "refuse", text: "What is my sister's name?" },
  { kind: "teach", text: "I just started learning the violin." },
];

const CITE = /\s*\[([0-9a-f]{8})\]/g;

// Split a reply into text and footnote markers, numbering ids in order of use.
function footnoted(text, citations) {
  const order = [];
  const parts = [];
  let last = 0;
  for (const m of text.matchAll(CITE)) {
    parts.push(text.slice(last, m.index));
    if (!order.includes(m[1])) order.push(m[1]);
    parts.push({ n: order.indexOf(m[1]) + 1, id: m[1] });
    last = m.index + m[0].length;
  }
  parts.push(text.slice(last));
  for (const id of citations || []) if (!order.includes(id)) order.push(id);
  return { parts, order };
}

export default function App() {
  const [store, setStore] = useState(null);
  const [t, setT] = useState(0);
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [messages, setMessages] = useState([]);
  const [dream, setDream] = useState(null);
  const [tab, setTab] = useState("graph");
  const [busy, setBusy] = useState(false);
  const [sleeping, setSleeping] = useState(false);
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState(0);
  const [sleeps, setSleeps] = useState(0);
  const [error, setError] = useState(null);
  const [focus, setFocus] = useState(null);
  const logRef = useRef(null);

  const textById = useMemo(() => {
    const m = {};
    for (const e of store?.episodes ?? []) m[e.id] = { text: e.text, type: "episode" };
    for (const f of store?.facts ?? []) m[f.id] = { text: f.statement, type: "fact" };
    return m;
  }, [store]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  useEffect(() => {
    document.documentElement.classList.toggle("night", sleeping);
  }, [sleeping]);

  // First load: one sleep over the seeded starter history so the panel is
  // alive before the visitor types anything.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setBusy(true);
      try {
        const out = await post("/api/sleep", { store: null, t: 0 });
        if (cancelled) return;
        setStore(out.store); setT(out.t); setGraph(out.graph); setDream(out.report);
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  async function send(text) {
    const message = (text ?? input).trim();
    if (!message || busy || turns >= MAX_TURNS) return;
    setInput("");
    setMessages((m) => [...m, { who: "you", text: message }]);
    setBusy(true); setError(null);
    try {
      const out = await post("/api/chat", { store, t, message });
      setStore(out.store); setT(out.t); setGraph(out.graph);
      // A statement (not a question) is stored as an episode; the engine still answers
      // from memory, so its refusal there means "nothing to recall yet", not a dodge.
      const asked = /\?\s*$/.test(message) || /^(who|what|when|where|why|how|which|do|does|did|is|are|can|could|will|would|have|has)\b/i.test(message);
      setMessages((m) => [...m, { who: "engram", text: out.reply.text,
                                  refused: out.reply.refused, statement: !asked,
                                  citations: out.reply.citations }]);
      setTurns((n) => n + 1);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function sleepNow() {
    if (busy || sleeps >= MAX_SLEEPS) return;
    setBusy(true); setSleeping(true); setError(null);
    const started = Date.now();
    try {
      const out = await post("/api/sleep", { store, t });
      // let the night be seen even when the server is quick
      const wait = Math.max(0, 1400 - (Date.now() - started));
      await new Promise((r) => setTimeout(r, wait));
      setStore(out.store); setT(out.t); setGraph(out.graph); setDream(out.report);
      setSleeps((n) => n + 1); setTab("dream");
    } catch (e) {
      setError(e.message);
    } finally {
      setSleeping(false); setBusy(false);
    }
  }

  const episodes = store?.episodes ?? [];
  const facts = store?.facts ?? [];
  const day = Math.floor(t);
  const showStarters = messages.length < 6 && turns < MAX_TURNS;

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <h1>Engram</h1>
          <p>A memory for AI assistants that sleeps, forgets, and refuses to make things up.</p>
        </div>
        <div className="top-right">
          <span className="day" aria-live="polite">
            <span className="glyph" aria-hidden>{sleeping ? "☾" : "☀"}</span>
            {sleeping ? `night ${day}` : `day ${day}`}
          </span>
          <a className="u" href="https://github.com/harshnsawant-source/engram">code &amp; evals</a>
        </div>
      </header>

      <ol className="how">
        <li><b>Tell it things.</b> Each message becomes an episode.</li>
        <li><b>Let it sleep.</b> Episodes consolidate into facts; unused memories fade.</li>
        <li><b>Ask it back.</b> It cites the memory it used, or says it doesn’t remember.</li>
        <li className="evals">In testing: refused 20/20 questions it had no memory for, with 0 made up · 10/10 retrieval · 3/3 provenance.</li>
      </ol>

      <main>
        <section className="chat" aria-label="Conversation">
          <div className="log" ref={logRef}>
            <div className="msg engram intro">
              I already remember a few things about you: a dog called Biscuit, a book club, a cousin who
              travels. Ask me about them, tell me something new, then put me to sleep.
            </div>
            {messages.map((m, i) => {
              if (m.who === "you") return <div key={i} className="msg you">{m.text}</div>;
              const { parts, order } = footnoted(m.text, m.citations);
              const ids = new Set(order);
              return (
                <div key={i} className={"msg engram" + (m.refused ? (m.statement ? " noted" : " refused") : "")}
                  onMouseEnter={() => ids.size && setFocus(ids)} onMouseLeave={() => setFocus(null)}>
                  <p>
                    {parts.map((p, j) => typeof p === "string" ? p : (
                      <sup key={j} className="fn"
                        onMouseEnter={() => setFocus(new Set([p.id]))}>{p.n}</sup>
                    ))}
                  </p>
                  {m.refused && !m.statement && <span className="refusal-note">no memory of this, so it refused</span>}
                  {m.refused && m.statement && <span className="noted-note">saved as a new episode · ask about it after it sleeps</span>}
                  {order.length > 0 && (
                    <ol className="notes">
                      {order.map((id) => (
                        <li key={id} onMouseEnter={() => setFocus(new Set([id]))}>
                          <span className={"kind " + (textById[id]?.type ?? "")}>{textById[id]?.type ?? "memory"}</span>
                          {textById[id]?.text ?? id}
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              );
            })}
            {busy && !sleeping && <div className="msg engram busy" aria-live="polite"><span className="dots"><i /><i /><i /></span></div>}
            {error && <div className="msg error">{error}</div>}
          </div>

          {showStarters && (
            <div className="starters" aria-label="Try one of these">
              {STARTERS.map((s) => (
                <button key={s.text} className={"starter " + s.kind} disabled={busy}
                  onClick={() => send(s.text)}>
                  <span className="mono">{s.kind === "recall" ? "recall" : s.kind === "refuse" ? "can't know" : "teach it"}</span>
                  {s.text}
                </button>
              ))}
            </div>
          )}

          <div className="composer">
            <input value={input} maxLength={500} disabled={busy || turns >= MAX_TURNS}
              aria-label="Message"
              placeholder={turns >= MAX_TURNS ? "session limit reached" : "Tell it something, or ask what it remembers"}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()} />
            <button className="send" onClick={() => send()} disabled={busy || !input.trim() || turns >= MAX_TURNS}>Send</button>
            <button className="sleep" onClick={sleepNow} disabled={busy || sleeps >= MAX_SLEEPS}
              title="Consolidate today's episodes into facts">
              <span aria-hidden>☾</span> Sleep
            </button>
          </div>
        </section>

        <section className="panel" aria-label="Memory">
          <nav role="tablist">
            {TABS.map(([key, name]) => (
              <button key={key} role="tab" aria-selected={tab === key} className={tab === key ? "on" : ""}
                onClick={() => setTab(key)}>
                {name}
                {key === "facts" && <span className="count">{facts.filter((f) => !f.superseded_by).length}</span>}
                {key === "episodes" && <span className="count">{episodes.length}</span>}
              </button>
            ))}
          </nav>
          <div className="panel-body">
            {tab === "graph" && <MemoryGraph graph={graph} focus={focus} />}
            {tab === "episodes" && (
              <ul className="mems">
                {[...episodes].reverse().map((e) => (
                  <li key={e.id} className={focus?.has(e.id) ? "on" : ""}>
                    <span className="dot episode" />
                    <span className="text">{e.text}</span>
                    {e.consolidated && <span className="tag">slept on</span>}
                  </li>
                ))}
              </ul>
            )}
            {tab === "facts" && (
              <ul className="mems">
                {facts.length === 0 && <li className="muted">No facts yet. They form while it sleeps.</li>}
                {[...facts].reverse().map((f) => (
                  <li key={f.id} className={(f.superseded_by ? "superseded " : "") + (focus?.has(f.id) ? "on" : "")}>
                    <span className="dot fact" />
                    <span className="text">{f.statement}</span>
                    {f.superseded_by && <span className="tag">replaced</span>}
                  </li>
                ))}
              </ul>
            )}
            {tab === "dream" && <DreamReport report={dream} store={store} />}
          </div>
        </section>
      </main>

      <div className={"nightfall " + (sleeping ? "show" : "")} aria-hidden={!sleeping}>
        <p><span className="moon">☾</span> Sleeping on day {day}…</p>
        <p className="sub">consolidating episodes into facts, letting unused memories fade</p>
      </div>

      <footer>
        Built by <a className="u" href="https://aviora-site.vercel.app">Harsh Sawant</a> · this demo’s memory lives in your browser tab and is gone when you close it · replies are written by Google’s Gemini API
      </footer>
    </div>
  );
}
