"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { Document, Evidence, Quality, Rag } from "@/lib/types";
import { sourceLink } from "@/lib/types";
import holdout from "@/data/holdout.json";
import development from "@/data/development.json";
import retrieval from "@/data/retrieval.json";
const sections = [
  ["home", "/", "Overview", "01"],
  ["research", "/research", "Research assistant", "02"],
  ["compare", "/compare", "Compare reports", "03"],
  ["documents", "/documents", "Document library", "04"],
  ["quality", "/quality", "Data quality", "05"],
  ["evaluation", "/evaluation", "Evaluation", "06"],
];
type Health = { mode: string; database: string; embedding_backend: string };
type Governance = {
  registry: { principles?: string[] };
  records: {
    registry_key: string;
    payload_sha256: string;
    recorded_at: string;
    owner: string;
  }[];
  transfer_count: number;
  embedding_run_count: number;
};
type Comparison = {
  left: Rag;
  right: Rag;
  comparison: Rag | null;
  interpretation: string;
};
async function request<T>(endpoint: string, body?: unknown): Promise<T> {
  const response = await fetch("/api/backend/" + endpoint, {
    method: body ? "POST" : "GET",
    ...(body
      ? {
          body: JSON.stringify(body),
          headers: { "Content-Type": "application/json" },
        }
      : {}),
    cache: "no-store",
  });
  const value = await response.json();
  if (!response.ok)
    throw new Error(value.error || "Research service is unavailable.");
  return value;
}
function pct(value: number | null | undefined) {
  return value == null ? "Not measured" : (value * 100).toFixed(1) + "%";
}
function Metric({
  label,
  value,
  note,
}: {
  label: string;
  value: React.ReactNode;
  note: string;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}
function Sources({ evidence }: { evidence: Evidence[] }) {
  return (
    <div className="sources">
      {evidence.map((source) => (
        <details key={source.chunk_id}>
          <summary>
            <span className="source-number">{source.chunk_id}</span>
            <span>
              {source.title}
              <small>
                PDF page {source.page} · {source.organization} · Published{" "}
                {source.publication_date}
              </small>
            </span>
          </summary>
          <p className="excerpt">{source.text}</p>
          {sourceLink(source) && (
            <a
              className="text-link"
              href={sourceLink(source)!}
              target="_blank"
              rel="noreferrer"
            >
              Open official PDF at page {source.page} ↗
            </a>
          )}
        </details>
      ))}
    </div>
  );
}
function Answer({ result }: { result: Rag }) {
  return (
    <section className="answer" aria-live="polite">
      <div className="answer-meta">
        <span className={result.abstained ? "badge amber" : "badge"}>
          {result.abstained
            ? "Insufficient matching evidence"
            : result.mode === "llm"
              ? "LLM-selected source quotations"
              : "Retrieval-only evidence"}
        </span>
        <span>{(result.latency_ms / 1000).toFixed(1)} seconds</span>
      </div>
      <p className="answer-text">{result.answer}</p>
      {result.claims?.map((claim) => {
        const source = result.evidence.find(
          (s) => s.chunk_id === claim.chunk_id,
        );
        return source && sourceLink(source) ? (
          <a
            className="citation"
            key={claim.chunk_id}
            href={sourceLink(source)!}
            target="_blank"
            rel="noreferrer"
          >
            [{claim.chunk_id}] {source.title} · p. {source.page} ↗
          </a>
        ) : null;
      })}
      <p className="fine">
        Exact source quotations can still miss the requested measure or context.
        Verify the reporting period, units and original table before use.
      </p>
      <Sources evidence={result.evidence} />
    </section>
  );
}
export default function Workspace({ page }: { page: string }) {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null),
    [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [docs, setDocs] = useState<Document[]>([]),
    [quality, setQuality] = useState<Quality | null>(null),
    [health, setHealth] = useState<Health | null>(null),
    [gov, setGov] = useState<Governance | null>(null);
  const [question, setQuestion] = useState(""),
    [selected, setSelected] = useState(""),
    [mode, setMode] = useState("hybrid"),
    [answer, setAnswer] = useState<Rag | null>(null),
    [left, setLeft] = useState(""),
    [right, setRight] = useState(""),
    [topic, setTopic] = useState("urban CPI annual increase"),
    [comparison, setComparison] = useState<Comparison | null>(null),
    [search, setSearch] = useState("");
  useEffect(() => {
    let active = true;
    fetch("/api/session", { cache: "no-store" })
      .then((r) => r.json())
      .then((value) => {
        if (active) setAuthenticated(value.authenticated === true);
      })
      .catch(() => {
        if (active) {
          setError("Unable to check your session.");
          setAuthenticated(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    if (!authenticated) return;
    let active = true;
    Promise.all([
      request<Document[]>("documents"),
      request<Quality>("quality"),
      request<Health>("health"),
    ])
      .then(([d, q, h]) => {
        if (!active) return;
        setDocs(d);
        setQuality(q);
        setHealth(h);
        setLeft(
          String(
            d.find((x) => x.title.includes("October 2026"))?.id ||
              d[0]?.id ||
              "",
          ),
        );
        setRight(
          String(
            d.find(
              (x) =>
                x.title.includes("September 2026") && x.title.includes("CPI"),
            )?.id ||
              d[1]?.id ||
              "",
          ),
        );
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    if (page === "quality")
      request<Governance>("governance")
        .then((v) => {
          if (active) setGov(v);
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    return () => {
      active = false;
    };
  }, [authenticated, page]);
  async function login(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const value = await response.json();
      if (!response.ok) throw new Error(value.error);
      setPassword("");
      setAuthenticated(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign-in is unavailable.");
    } finally {
      setBusy(false);
    }
  }
  async function logout() {
    await fetch("/api/session", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    setAuthenticated(false);
    setDocs([]);
    setQuality(null);
    setAnswer(null);
    setComparison(null);
  }
  async function ask(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setAnswer(null);
    try {
      setAnswer(
        await request<Rag>("ask", {
          question,
          retrieval_mode: mode,
          filters: selected ? { document_id: Number(selected) } : {},
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Research request failed.");
    } finally {
      setBusy(false);
    }
  }
  async function compare(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setComparison(null);
    try {
      setComparison(
        await request<Comparison>("compare", {
          left_id: Number(left),
          right_id: Number(right),
          topic,
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Comparison failed.");
    } finally {
      setBusy(false);
    }
  }
  const title = sections.find((s) => s[0] === page)?.[2] || "Overview";
  const filtered = docs.filter((d) =>
    (d.title + " " + d.document_type + " " + d.organization)
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  return (
    <div className="shell">
      <aside className="sidebar">
        <Link href="/" className="brand">
          <span className="brand-mark">F</span>
          <span>
            FinRAG<small>RWANDA FINANCIAL INTELLIGENCE</small>
          </span>
        </Link>
        <p className="nav-heading">RESEARCH WORKSPACE</p>
        <nav aria-label="Main navigation">
          {sections.map(([key, url, label, n]) => (
            <Link
              key={key}
              href={url}
              aria-current={page === key ? "page" : undefined}
              className={page === key ? "nav-link active" : "nav-link"}
            >
              <span>{n}</span>
              {label}
              {page === key && <b>↗</b>}
            </Link>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="status-dot" />
          Experimental research prototype
          <p>
            Original holdout statistic coverage
            <br />
            <strong>41.7%</strong>
          </p>
          <small>Independent human review pending.</small>
        </div>
        <a
          className="repo-link"
          href="https://github.com/Ruganji-Prince/FINRAG"
          target="_blank"
          rel="noreferrer"
        >
          View the engineering evidence ↗
        </a>
      </aside>
      <div className="main-wrap">
        <header className="topbar">
          <span>PUBLICATIONS / EVIDENCE / RESEARCH</span>
          <div>
            <span className="badge subtle">Rwanda · Official sources</span>
            {authenticated && (
              <button className="quiet" onClick={logout}>
                Sign out
              </button>
            )}
          </div>
        </header>
        <main id="main">
          <div className="page-heading">
            <div>
              <p className="eyebrow">THE RESEARCH DESK</p>
              <h1>{title}</h1>
            </div>
            <span className="date-label">Traceable to the original PDF</span>
          </div>
          {error && (
            <div className="error" role="alert">
              {error}
              <button
                className="quiet"
                onClick={() => setError("")}
                aria-label="Dismiss error"
              >
                Close
              </button>
            </div>
          )}
          {authenticated === null ? (
            <div className="panel loading" role="status">
              Opening your workspace...
            </div>
          ) : !authenticated ? (
            <section className="login-grid">
              <div className="login-copy">
                <span className="eyebrow">
                  OFFICIAL DATA. VISIBLE EVIDENCE.
                </span>
                <h2>
                  Financial research,
                  <br />
                  with a source for every quote.
                </h2>
                <p>
                  Explore Rwanda's economic publications through document
                  retrieval, cited research and side-by-side report comparisons.
                </p>
                <div className="honesty">
                  <strong>Research prototype</strong>
                  <p>
                    The original independent-from-tuning holdout achieved 41.7%
                    expected-statistic coverage. Source authenticity does not
                    establish answer relevance.
                  </p>
                </div>
              </div>
              <form className="panel login-form" onSubmit={login}>
                <span className="badge">Private research access</span>
                <h2>Welcome to FinRAG</h2>
                <p>
                  Use the invitation code shared by the project owner. Your
                  session expires after one hour.
                </p>
                <label htmlFor="invitation">Invitation code</label>
                <input
                  id="invitation"
                  type="password"
                  autoComplete="current-password"
                  maxLength={256}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button className="primary" disabled={busy}>
                  {busy ? "Signing in..." : "Open research workspace"}
                </button>
                <small>
                  Public and official documents only. Do not submit personal,
                  account or confidential information.
                </small>
              </form>
            </section>
          ) : (
            <>
              {page === "home" && (
                <>
                  <section className="hero panel">
                    <div>
                      <span className="eyebrow">RESEARCH WITH PROVENANCE</span>
                      <h2>
                        Understand the numbers.
                        <br />
                        <em>Inspect the evidence.</em>
                      </h2>
                      <p>
                        Find reported statistics, compare publication vintages
                        and follow every quotation back to its official document
                        and page.
                      </p>
                      <div className="actions">
                        <Link className="primary" href="/research">
                          Start a research question →
                        </Link>
                        <Link className="secondary" href="/documents">
                          Explore publications
                        </Link>
                      </div>
                    </div>
                    <div className="pipeline" aria-label="Evidence pipeline">
                      <span>01 / OFFICIAL PUBLICATION</span>
                      <b>Source PDF</b>
                      <i>&darr;</i>
                      <b>Page-linked retrieval</b>
                      <i>&darr;</i>
                      <b className="pipeline-last">
                        Cited quotation or refusal
                      </b>
                      <small>Preserved source · date · page · hash</small>
                    </div>
                  </section>
                  <div className="metrics">
                    <Metric
                      label="Indexed publications"
                      value={quality?.documents ?? "--"}
                      note="Live corpus, not a curated claim"
                    />
                    <Metric
                      label="Searchable passages"
                      value={quality?.chunks?.toLocaleString() ?? "--"}
                      note="Original and supplementary evidence"
                    />
                    <Metric
                      label="Original holdout coverage"
                      value="41.7%"
                      note="Expected statistics; not human accuracy"
                    />
                  </div>
                  <section className="feature-grid">
                    {[
                      [
                        "02",
                        "Evidence-led research",
                        "Ask a precise question with a reporting period. Inspect the quoted source before drawing a conclusion.",
                        "/research",
                      ],
                      [
                        "03",
                        "Compare reporting periods",
                        "Keep definitions, units and publication vintages visible when placing figures side by side.",
                        "/compare",
                      ],
                      [
                        "04",
                        "An inspectable corpus",
                        "Review source links, publication-date notes, extraction quality and provenance hashes.",
                        "/quality",
                      ],
                    ].map(([n, label, text, url]) => (
                      <Link className="panel feature" key={n} href={url}>
                        <span>{n}</span>
                        <h3>{label}</h3>
                        <p>{text}</p>
                        <b>Explore</b>
                      </Link>
                    ))}
                  </section>
                  <p className="fine">
                    Live service:{" "}
                    {health
                      ? `${health.database} · ${health.embedding_backend} · answer provider: ${health.mode}`
                      : "Waiting for backend connection."}{" "}
                    The Streamlit application remains available as a separate
                    local fallback.
                  </p>
                </>
              )}
              {page === "research" && (
                <>
                  <p className="intro">
                    Ask about a specific statistic, scope and reporting period.
                    Answers publish source quotations; unsupported questions
                    should be refused.
                  </p>
                  <form className="panel research-form" onSubmit={ask}>
                    <div className="form-row">
                      <div>
                        <label htmlFor="report">Publication</label>
                        <select
                          id="report"
                          value={selected}
                          onChange={(e) => setSelected(e.target.value)}
                        >
                          <option value="">Search all publications</option>
                          {docs.map((d) => (
                            <option key={d.id} value={d.id}>
                              {d.title}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label htmlFor="retrieval">Retrieval method</label>
                        <select
                          id="retrieval"
                          value={mode}
                          onChange={(e) => setMode(e.target.value)}
                        >
                          <option value="hybrid">Hybrid</option>
                          <option value="keyword">Keyword</option>
                          <option value="vector">Semantic vector</option>
                        </select>
                      </div>
                    </div>
                    <label htmlFor="question">Research question</label>
                    <textarea
                      id="question"
                      placeholder="What was GDP growth in 2025?"
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      minLength={5}
                      maxLength={2000}
                      required
                      rows={4}
                    />
                    <div className="form-bottom">
                      <small>
                        {question.length}/2000 characters · Never submit
                        confidential information.
                      </small>
                      <button
                        className="primary"
                        disabled={busy || !docs.length}
                      >
                        {busy ? "Checking source evidence..." : "Find evidence"}
                      </button>
                    </div>
                  </form>
                  {busy && (
                    <p role="status" className="loading">
                      Retrieving and validating source evidence. This can take a
                      minute on CPU.
                    </p>
                  )}
                  {answer && <Answer result={answer} />}
                </>
              )}
              {page === "compare" && (
                <>
                  <p className="intro">
                    Compare a precise measure in two publications. Differences
                    may reflect reporting periods, definitions, rebasing or
                    revisions.
                  </p>
                  <form className="panel research-form" onSubmit={compare}>
                    <div className="form-row">
                      <div>
                        <label htmlFor="first">First publication</label>
                        <select
                          id="first"
                          value={left}
                          onChange={(e) => setLeft(e.target.value)}
                        >
                          {docs.map((d) => (
                            <option key={d.id} value={d.id}>
                              {d.title}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label htmlFor="second">Second publication</label>
                        <select
                          id="second"
                          value={right}
                          onChange={(e) => setRight(e.target.value)}
                        >
                          {docs.map((d) => (
                            <option key={d.id} value={d.id}>
                              {d.title}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <label htmlFor="topic">Measure to compare</label>
                    <input
                      id="topic"
                      value={topic}
                      onChange={(e) => setTopic(e.target.value)}
                      minLength={3}
                      maxLength={300}
                      required
                    />
                    <div className="form-bottom">
                      <small>
                        Both reports must support the requested comparison.
                      </small>
                      <button
                        className="primary"
                        disabled={busy || left === right || !docs.length}
                      >
                        {busy
                          ? "Comparing evidence..."
                          : "Compare publications"}
                      </button>
                    </div>
                  </form>
                  {comparison && (
                    <>
                      <div className="notice">{comparison.interpretation}</div>
                      {comparison.comparison && (
                        <Answer result={comparison.comparison} />
                      )}
                      <div className="comparison-grid">
                        <div>
                          <h2>First report evidence</h2>
                          <Sources evidence={comparison.left.evidence} />
                        </div>
                        <div>
                          <h2>Second report evidence</h2>
                          <Sources evidence={comparison.right.evidence} />
                        </div>
                      </div>
                    </>
                  )}
                </>
              )}
              {page === "documents" && (
                <>
                  <p className="intro">
                    Inspect the official publication, date basis and provenance
                    before using extracted figures. Some release days are
                    imputed or website-update proxies; see each rights/date
                    note.
                  </p>
                  <div className="library-toolbar">
                    <label htmlFor="library-search">Search the corpus</label>
                    <input
                      id="library-search"
                      type="search"
                      placeholder="Search by title, publisher or report type"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                    <small>{filtered.length} publications</small>
                  </div>
                  <div className="document-grid">
                    {filtered.map((d) => (
                      <article className="panel document" key={d.id}>
                        <div className="document-top">
                          <span className="doc-icon">PDF</span>
                          <span className="badge subtle">{d.organization}</span>
                        </div>
                        <h2>{d.title}</h2>
                        <p>
                          {d.document_type} · {d.publication_date}
                        </p>
                        {sourceLink(d) && (
                          <a
                            className="text-link"
                            href={sourceLink(d)!}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Open official publication ↗
                          </a>
                        )}
                        <details>
                          <summary>Rights, dates & provenance</summary>
                          <p>{d.usage_notes}</p>
                          <small>Retrieved {d.retrieved_at}</small>
                          <code className="hash">SHA256 {d.content_hash}</code>
                        </details>
                      </article>
                    ))}
                  </div>
                  {!filtered.length && (
                    <p className="panel">
                      No matching publications. Try another title or check
                      backend connectivity.
                    </p>
                  )}
                </>
              )}
              {page === "quality" && (
                <>
                  <p className="intro">
                    A visible record of extraction quality and source lineage.
                    Governance is DAMA-inspired engineering practice, not
                    institutional certification.
                  </p>
                  <div className="metrics">
                    <Metric
                      label="Publications"
                      value={quality?.documents ?? "--"}
                      note="Actually indexed"
                    />
                    <Metric
                      label="Duplicate refreshes skipped"
                      value={quality?.duplicate_runs ?? "--"}
                      note="Content-hash based deduplication"
                    />
                    <Metric
                      label="Failed ingestion runs"
                      value={quality?.failed_runs ?? "--"}
                      note="Audit count; requires operator review"
                    />
                  </div>
                  <div className="panel lineage">
                    <span>Official URL</span>
                    <b>↗</b>
                    <span>SHA256 & quality</span>
                    <b>↗</b>
                    <span>Page chunks</span>
                    <b>↗</b>
                    <span>Embedding index</span>
                    <b>↗</b>
                    <span>Cited evidence</span>
                  </div>
                  <section className="panel">
                    <h2>Extraction checks</h2>
                    <p className="fine">
                      {quality?.database} · Last successful ingestion{" "}
                      {quality?.last_success || "not available"}
                    </p>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Publication</th>
                            <th>Pages</th>
                            <th>Empty pages</th>
                            <th>Replacement characters</th>
                            <th>OCR review</th>
                          </tr>
                        </thead>
                        <tbody>
                          {quality?.quality.map((d) => (
                            <tr key={d.id}>
                              <td>{d.title}</td>
                              <td>{d.pages}</td>
                              <td>{d.empty_pages}</td>
                              <td>{d.replacement_characters}</td>
                              <td>
                                {d.ocr_required ? "Required" : "Not flagged"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                  {gov && (
                    <section className="panel governance">
                      <h2>Governance records</h2>
                      <p>
                        {gov.transfer_count} transfer records ·{" "}
                        {gov.embedding_run_count} embedding runs
                      </p>
                      <ul>
                        {gov.registry.principles?.map((p) => (
                          <li key={p}>{p}</li>
                        ))}
                      </ul>
                      {gov.records.map((r) => (
                        <details key={r.registry_key}>
                          <summary>{r.registry_key}</summary>
                          <p>
                            Owner: {r.owner} · Recorded {r.recorded_at}
                          </p>
                          <code className="hash">
                            SHA256 {r.payload_sha256}
                          </code>
                        </details>
                      ))}
                    </section>
                  )}
                </>
              )}
              {page === "evaluation" && (
                <>
                  <p className="intro">
                    Measured results, preserved limitations. The original
                    holdout is historical evidence; no new independently
                    verified accuracy improvement is claimed.
                  </p>
                  <div className="notice">
                    <strong>
                      Original holdout: {holdout.n} questions, 24 supported and
                      6 unsupported.
                    </strong>
                    <p>
                      Agent-authored after freezing the implementation.
                      Independent human ratings: zero. Exact quotation support
                      is not semantic relevance or financial correctness.
                    </p>
                  </div>
                  <div className="metrics">
                    <Metric
                      label="Expected-statistic coverage"
                      value={pct(
                        holdout.metrics?.mean_expected_anchor_coverage,
                      )}
                      note="10 of 24 supported questions"
                    />
                    <Metric
                      label="Exact citation / quote integrity"
                      value={pct(holdout.metrics?.citation_quote_integrity)}
                      note="Across 18 generated responses"
                    />
                    <Metric
                      label="Unsupported refusal rate"
                      value={pct(holdout.metrics?.unsupported_abstention_rate)}
                      note="6 of 6 unsupported requests"
                    />
                  </div>
                  <div className="evaluation-grid">
                    <section className="panel">
                      <span className="eyebrow">SAME HOLDOUT QUESTIONS</span>
                      <h2>Retrieval at five passages</h2>
                      {Object.entries(retrieval.metrics).map(
                        ([name, value]) => (
                          <div className="retrieval-row" key={name}>
                            <div>
                              <strong>{name}</strong>
                              <span>
                                Recall {pct(value.page_recall_at_5)} · MRR{" "}
                                {value.mrr_at_5.toFixed(3)}
                              </span>
                            </div>
                            <div className="bar">
                              <i
                                style={{
                                  width: value.page_recall_at_5 * 100 + "%",
                                }}
                              />
                            </div>
                          </div>
                        ),
                      )}
                      <p className="fine">
                        Keyword retrieval outperformed hybrid on this benchmark.
                        Ranking improvement is not assumed.
                      </p>
                    </section>
                    <section className="panel">
                      <span className="eyebrow">FAILURES REMAIN VISIBLE</span>
                      <h2>What still needs work</h2>
                      <ul className="limitations">
                        <li>
                          6 of 24 supported questions unnecessarily refused.
                        </li>
                        <li>
                          14 diagnostic failures retained, including
                          wrong-measure and table/graph fragment selections.
                        </li>
                        <li>
                          Mean request latency:{" "}
                          {(
                            (holdout.metrics?.mean_latency_ms || 0) / 1000
                          ).toFixed(2)}{" "}
                          seconds, including fast refusals.
                        </li>
                        <li>
                          New reliability changes await a new independent
                          holdout.
                        </li>
                      </ul>
                    </section>
                  </div>
                  <details className="panel">
                    <summary>
                      Development results and artifact provenance
                    </summary>
                    <p>
                      The tuned development set contains {development.n}{" "}
                      questions. Its{" "}
                      {pct(development.metrics?.mean_expected_anchor_coverage)}{" "}
                      anchor coverage is not an independent accuracy estimate
                      and is not directly comparable to the different holdout
                      set.
                    </p>
                    <code className="hash">
                      Holdout artifact SHA256 {holdout.source_sha256}
                    </code>
                    <p className="fine">
                      Saved run {holdout.run_at}. Data originates from the
                      preserved repository artifacts, not a fabricated live
                      score.
                    </p>
                  </details>
                </>
              )}
            </>
          )}
          <footer>
            <span>FinRAG · Experimental research prototype</span>
            <span>
              Independent project. Not affiliated with BNR or NISR. Verify every
              financial conclusion.
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
