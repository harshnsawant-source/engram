import React, { useEffect, useRef, useState } from "react";
import { post } from "./api.js";
import MemoryGraph from "./MemoryGraph.jsx";
import DreamReport from "./DreamReport.jsx";

const MAX_TURNS = 30;
const MAX_SLEEPS = 10;
const TABS = ["graph", "episodes", "facts", "dream"];

export default function App() {
  const [store, setStore] = useState(null);
  const [t, setT] = useState(0);
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [messages, setMessages] = useState([]);
  const [dream, setDream] = useState(null);
  const [tab, setTab] = useState("graph");
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState(0);
  const [sleeps, setSleeps] = useState(0);
  const [error, setError] = useState(null);
  const logRef = useRef(null);

  useEffect(() => {
    logRef.current?.scrollTo(0, logRef.current.scrollHeight);
  }, [messages]);

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

  async function send() {
    const message = input.trim();
    if (!message || busy || turns >= MAX_TURNS) return;
    setInput("");
    setMessages((m) => [...m, { who: "you", text: message }]);
    setBusy(true); setError(null);
    try {
      const out = await post("/api/chat", { store, t, message });
      setStore(out.store); setT(out.t); setGraph(out.graph);
      setMessages((m) => [...m, { who: "engram", text: out.reply.text,
                                  refused: out.reply.refused,
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
    setBusy(true); setError(null);
    try {
      const out = await post("/api/sleep", { store, t });
      setStore(out.store); setT(out.t); setGraph(out.graph); setDream(out.report);
      setSleeps((n) => n + 1); setTab("dream");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const episodes = store?.episodes ?? [];
  const facts = store?.facts ?? [];

  return (
    <div className="app">
      <header>
        <h1>Engram</h1>
        <p className="tagline">episodic memory · consolidation while it sleeps ·
          a forgetting curve · refuses to make things up</p>
        <div className="day">day {Math.floor(t)}</div>
      </header>
      <main>
        <section className="chat">
          <div className="log" ref={logRef}>
            <div className="msg engram intro">
              Hi — I remember things. Tell me about your day, ask me about mine,
              then press <b>Sleep</b> and watch the memories consolidate.
            </div>
            {messages.map((m, i) => (
              <div key={i} className={"msg " + m.who + (m.refused ? " refused" : "")}>
                {m.text}
                {m.citations?.length > 0 && (
                  <span className="cite">· {m.citations.length} memories cited</span>
                )}
              </div>
            ))}
            {busy && <div className="msg engram busy">thinking…</div>}
            {error && <div className="msg error">{error}</div>}
          </div>
          <div className="composer">
            <input value={input} maxLength={500} disabled={busy || turns >= MAX_TURNS}
              placeholder={turns >= MAX_TURNS ? "session turn limit reached" : "say something worth remembering…"}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()} />
            <button onClick={send} disabled={busy || turns >= MAX_TURNS}>Send</button>
            <button className="sleep" onClick={sleepNow}
              disabled={busy || sleeps >= MAX_SLEEPS}>Sleep 💤</button>
          </div>
        </section>
        <section className="panel">
          <nav>
            {TABS.map((name) => (
              <button key={name} className={tab === name ? "on" : ""}
                onClick={() => setTab(name)}>{name}</button>
            ))}
          </nav>
          {tab === "graph" && <MemoryGraph graph={graph} />}
          {tab === "episodes" && (
            <ul className="mems">
              {[...episodes].reverse().map((e) => (
                <li key={e.id}>
                  <span className="dot episode" />
                  <span className="text">{e.text}</span>
                  {e.consolidated && <span className="tag">consolidated</span>}
                </li>
              ))}
            </ul>
          )}
          {tab === "facts" && (
            <ul className="mems">
              {facts.length === 0 && <li className="muted">no facts yet — sleep on it</li>}
              {[...facts].reverse().map((f) => (
                <li key={f.id} className={f.superseded_by ? "superseded" : ""}>
                  <span className="dot fact" />
                  <span className="text">{f.statement}</span>
                  {f.superseded_by && <span className="tag">superseded</span>}
                </li>
              ))}
            </ul>
          )}
          {tab === "dream" && <DreamReport report={dream} store={store} />}
        </section>
      </main>
      <footer>
        <a href="https://github.com/harshnsawant-source/engram">source & measured evals on GitHub</a>
      </footer>
    </div>
  );
}
