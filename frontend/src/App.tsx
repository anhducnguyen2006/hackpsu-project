import { FormEvent, useState } from "react";
import type { DatasetCardData } from "./types";

const demoDataset: DatasetCardData = {
  dataset_id: "uci:320",
  title: "Student Performance",
  source: "UCI Machine Learning Repository",
  description:
    "Student achievement in secondary education of two Portuguese schools.",
  repository_url:
    "https://archive.ics.uci.edu/dataset/320/student+performance",
  data_status: "metadata_only",
};

function App() {
  const [question, setQuestion] = useState("");
  const [searched, setSearched] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSearched(true);
  }

  return (
    <main className="page-shell">
      <header className="hero">
        <p className="eyebrow">AI-assisted research workflow</p>
        <h1>Research Dataset Discovery</h1>
        <p className="subtitle">
          Find real datasets and understand whether they can support your
          research question.
        </p>
      </header>

      <form className="search-panel" onSubmit={handleSubmit}>
        <label htmlFor="research-question">Research question</label>
        <div className="search-row">
          <input
            id="research-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="e.g. How does study time relate to student performance?"
          />
          <button type="submit">Search</button>
        </div>
      </form>

      <section className="results" aria-live="polite">
        <div className="section-heading">
          <h2>Datasets</h2>
          <span className="status-pill">UCI source</span>
        </div>
        {!searched ? (
          <p className="empty-state">
            Enter a research question to see verified dataset results.
          </p>
        ) : (
          <article className="dataset-card">
            <div className="card-content">
              <p className="card-source">{demoDataset.source}</p>
              <h3>{demoDataset.title}</h3>
              <p>{demoDataset.description}</p>
              <span className="status-pill">Metadata preview</span>
            </div>
            <button
              className="secondary-button"
              onClick={() =>
                setExpanded(
                  expanded === demoDataset.dataset_id
                    ? null
                    : demoDataset.dataset_id,
                )
              }
            >
              {expanded === demoDataset.dataset_id ? "Hide details" : "Details"}
            </button>
            {expanded === demoDataset.dataset_id && (
              <div className="details-panel">
                <p>
                  Preliminary relevance and research suitability are separate
                  evaluations. Detailed suitability will appear after verified
                  data is inspected.
                </p>
                <a
                  href={demoDataset.repository_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  View original UCI dataset
                </a>
              </div>
            )}
          </article>
        )}
      </section>
    </main>
  );
}

export default App;

