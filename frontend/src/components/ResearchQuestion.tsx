import { useState, type FormEvent } from "react";

export function ResearchQuestion({ exampleQuestion, onExploreExample }: { exampleQuestion: string; onExploreExample: () => void }) {
  const [question, setQuestion] = useState("");
  const [status, setStatus] = useState("");
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setStatus("Static preview: live search is not connected"); }
  return <section className="landing-page" aria-labelledby="landing-title">
    <div className="landing-grid">
      <div className="landing-intro">
        <p className="eyebrow">Research instrument / 01 — Question</p>
        <h1 id="landing-title">From question<br />to evidence.</h1>
        <p className="landing-deck">Find research datasets and inspect the evidence behind every match.</p>
        <form onSubmit={submit} className="question-form">
          <label htmlFor="research-question">Research question</label>
          <textarea id="research-question" rows={3} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Write your research question here" />
          <div className="question-actions"><button className="primary-action" type="submit">Find datasets</button><span className="muted">Live search is unavailable in this preview.</span></div>
          {status && <p role="status" className="form-status">{status}</p>}
        </form>
        <div className="example-callout"><span className="data-label">Cached example question</span><p>{exampleQuestion}</p><button className="secondary-action" type="button" onClick={onExploreExample}>Explore the example</button></div>
      </div>
      <aside className="workflow-panel" aria-label="Illustrative workflow">
        <div className="workflow-header"><span className="eyebrow">Fig. 01 / Method</span><strong>Illustrative workflow</strong></div>
        <ol className="workflow-list"><li><span>01</span><strong>Question</strong><small>Research intent</small></li><li><span>02</span><strong>Interpretation</strong><small>Concepts and terms</small></li><li><span>03</span><strong>UCI datasets</strong><small>Documented metadata</small></li><li><span>04</span><strong>Profile</strong><small>Computed description</small></li></ol>
        <p className="workflow-caption">A map of the review process. No dataset finding is represented here.</p>
      </aside>
    </div>
    <div className="provenance-strip"><span><b>01 / Source</b> UCI repository metadata</span><span><b>02 / Profile</b> Cached computed statistics</span><span><b>03 / Interpretation</b> Keyword fallback example</span></div>
  </section>;
}
