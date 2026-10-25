import type { DatasetAnalysisResponse, ExploratoryAnalysisResponse } from "../types";
import { EvidenceTag } from "./EvidenceTag";
import { DescriptiveFigure } from "./DescriptiveFigure";

const criterionNames: Record<string, string> = {
  research_question_and_outcome_alignment: "Question and outcome alignment", required_variable_coverage: "Required variable coverage",
  sample_size_considerations: "Sample size considerations", data_quality_and_completeness: "Data quality and completeness",
  documentation_and_provenance: "Documentation and provenance", population_and_temporal_relevance: "Population and temporal relevance",
};

function assessmentCopy(computed: boolean, hasAssessment: boolean, analysis: DatasetAnalysisResponse) {
  if (computed && hasAssessment) {
    return {
      title: "Suitability assessment",
      tag: "Python suitability score",
      tagExplanation: "The number is computed from Gemini's criterion scores. It is not semantic similarity and it is not a probability.",
      body: analysis.assessment?.score_explanation ?? "Suitability score computed from validated criteria.",
    };
  }
  if (computed) {
    const warning = analysis.warnings.find((item) => /AI suitability|Gemini|assessment unavailable/i.test(item));
    return {
      title: "Assessment unavailable",
      tag: "Live AI assessment unavailable",
      tagExplanation: "This live analysis kept the verified statistical profile. No Gemini suitability score was invented.",
      body: warning
        ?? (analysis.ai_assessment_status === "unavailable"
          ? "Live Gemini suitability assessment was unavailable for this analysis. The computed profile above remains valid."
          : "No live Gemini suitability assessment is available for this analysis."),
    };
  }
  return {
    title: "Assessment unavailable",
    tag: "AI assessment unavailable",
    tagExplanation: "No authentic cached Gemini assessment or suitability score is present.",
    body: analysis.assessment?.score_explanation ?? "No verifiable cached AI assessment is available.",
  };
}

export function AnalysisView({ analysis, exploration, presentation = "preview" }: { analysis: DatasetAnalysisResponse; exploration?: ExploratoryAnalysisResponse; presentation?: "preview" | "computed" }) {
  const { profile, assessment } = analysis;
  const computed = presentation === "computed";
  const suitability = computed ? assessment?.final_score ?? null : null;
  const copy = assessmentCopy(computed, Boolean(assessment), analysis);
  return <article className="analysis-page" aria-labelledby="analysis-title"><header className="analysis-masthead"><div><p className="eyebrow">Research instrument / 05 — Analysis</p><h1 id="analysis-title">Analysis</h1><p className="analysis-subtitle">{analysis.dataset.title} <span className="mono">/ {analysis.dataset.dataset_id}</span></p><a href={analysis.dataset.repository_url} target="_blank" rel="noreferrer">{computed ? "Original repository record" : "Original UCI source"}</a></div><div className="analysis-masthead-note"><EvidenceTag label={computed ? (analysis.download_performed ? "Download verified" : "Computed profile") : "Cached demo"} explanation={computed ? "Statistics come from the parsed provider file. Semantic similarity is not this suitability score." : "A previously computed Pandas profile copied from the repository demo; no live analysis runs here."} /><p>Descriptive evidence for review. Counts refer to observed records, not necessarily independent participants.</p>{computed && analysis.analyzed_resource?.filename && <p>Parsed file: {analysis.analyzed_resource.filename}</p>}{computed && analysis.source_doi && <p>DOI: {analysis.source_doi}</p>}{computed && analysis.source_version && <p>Source version: {analysis.source_version}</p>}{computed && analysis.analyzed_resource?.checksum && <p>Checksum: {analysis.analyzed_resource.checksum}</p>}{computed && analysis.history_saved === false && <p>This result was not saved to Past Research.</p>}</div></header>
    {profile ? <><section className="profile-section" aria-labelledby="profile-title"><div className="section-title-row"><div><span className="eyebrow">01 / Dataset profile</span><h2 id="profile-title">Computed profile</h2></div><EvidenceTag label="Computed profile" explanation={computed ? "Pandas statistics computed from the selected file in this response." : "Values are cached Pandas results from the example UCI retrieval."} /></div><div className="metric-row"><div><strong>{profile.row_count} observed records</strong><span>{computed ? "Rows in retrieved table" : "Rows in cached profile"}</span></div><div><strong>{profile.column_count} columns</strong><span>Full dataset profile</span></div><div><strong>{profile.duplicate_row_count} duplicate rows</strong><span>Observed duplicate rows</span></div></div>
      <div className="analysis-evidence"><span className="data-label">Research variable evidence</span><div className="evidence-grid">{profile.research_variable_evidence.map((item) => <div key={item.research_variable}><h3>{item.research_variable} → {item.matched_columns.join(", ")}</h3><p>{item.usable_observations} usable observations</p><p>{item.notes.join(" ")}</p></div>)}</div></div>
      <div className="variable-section"><div className="section-title-row"><div><span className="eyebrow">02 / Variable evidence</span><h2>Variable profiles</h2></div></div><p>{computed ? `Profiles for ${profile.column_count} columns in the retrieved table.` : `Displaying two cached variable profiles of ${profile.column_count} total columns. Other columns are not shown in this preview.`}</p><div className="table-scroll"><table className="variable-table"><caption>{computed ? "Column statistics from the retrieved file" : "Cached profiles for research variables"}</caption><thead><tr><th scope="col">Variable</th><th scope="col">Role / measurement</th><th scope="col">Observed values</th><th scope="col">Missing</th></tr></thead><tbody>{profile.columns.map((column) => <tr key={column.name}><th scope="row">{column.name}</th><td>{column.research_roles.join(", ")}<br /><span className="muted">{column.measurement_type === "ordinal_or_encoded_numeric" ? "ordinal / encoded numeric" : column.measurement_type}</span></td><td>{column.measurement_type === "ordinal_or_encoded_numeric" ? <div className="category-list">{[...column.categorical_summary].sort((a, b) => Number(a.value) - Number(b.value)).map((item) => <span key={String(item.value)}>{String(item.value)}: {item.count}</span>)}</div> : <div className="numeric-stats"><span>Mean <b>{column.numeric_summary?.mean?.toFixed(2) ?? "Unavailable"}</b></span><span>Median <b>{column.numeric_summary?.median ?? "Unavailable"}</b></span></div>}</td><td>{column.missing_count} of {profile.row_count} observed records</td></tr>)}</tbody></table></div></div>
      <div className="quality-section"><span className="eyebrow">03 / Quality &amp; limitations</span><h2>Read with care</h2><ul>{analysis.warnings.map((warning) => <li key={warning}>{warning}</li>)}{profile.quality_flags.map((flag) => <li key={flag}>{flag}</li>)}{assessment?.data_quality_issues.map((issue) => <li key={issue}>{issue}</li>)}{assessment?.population_limitations.map((issue) => <li key={issue}>{issue}</li>)}</ul></div>
    </section></> : <p>Computed profile unavailable.</p>}
    {exploration && (!computed || exploration.dataset_id === analysis.dataset.dataset_id) && <DescriptiveFigure exploration={exploration} />}
    <section className="assessment-section" aria-labelledby="assessment-title"><div className="section-title-row"><div><span className="eyebrow">05 / AI suitability</span><h2 id="assessment-title">{copy.title}</h2></div><EvidenceTag label={copy.tag} explanation={copy.tagExplanation} /></div><p>{copy.body}</p><div className="suitability-total"><span className="data-label">Overall suitability</span><strong>{suitability === null ? "Unavailable" : suitability}</strong></div>{assessment && <div className="criteria-grid">{Object.entries(assessment.criteria).map(([key, criterion]) => <div key={key}><span className="data-label">{criterionNames[key] ?? key}</span><strong>{criterion.score ?? "Unavailable"}</strong><p>{criterion.explanation}</p></div>)}</div>}</section>
  </article>;
}
