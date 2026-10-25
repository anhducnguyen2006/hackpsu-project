/** Verified editorial summaries, not quotations or platform screenshots. */
export interface ResearchEvidence {
  id: string;
  source: string;
  category: 'discussion' | 'forum' | 'study' | 'note' | 'reporting' | 'technical';
  headline: string;
  summary: string;
  url: string;
  originalTitle: string;
  verifiedOn: string;
  treatment: 'Editorial paraphrase';
  /** Passage checked when verifying the original source. */
  support: string;
}

export const RESEARCH_EVIDENCE: ResearchEvidence[] = [
  {
    "id": "cleaning-context",
    "source": "Reddit · r/datascience",
    "category": "discussion",
    "headline": "Cleaning needs context.",
    "summary": "Understanding the source can mean waiting on other teams.",
    "url": "https://www.reddit.com/r/datascience/comments/1qsxuaa/why_is_data_cleaning_hard/",
    "originalTitle": "Why is data cleaning hard?",
    "verifiedOn": "2026-10-25",
    "treatment": "Editorial paraphrase",
    "support": "Opening post: operational and IT knowledge required for cleaning."
  },
  {
    "id": "dataset-hunt",
    "source": "Reddit · r/datasets",
    "category": "discussion",
    "headline": "Beyond the same familiar datasets.",
    "summary": "A practitioner asks where to find data for a real problem.",
    "url": "https://www.reddit.com/r/datasets/comments/1vxo890/where_do_you_guys_find_datasets_for_real_world/",
    "originalTitle": "Where do you guys find datasets for real world data science projects?",
    "verifiedOn": "2026-10-25",
    "treatment": "Editorial paraphrase",
    "support": "Opening post: difficulty finding a large, less commonly used dataset."
  },
  {
    "id": "tedious-cleaning",
    "source": "Reddit · r/dataanalysis",
    "category": "forum",
    "headline": "The work before the analysis.",
    "summary": "Missing IDs and inconsistent names complicate reconciliation.",
    "url": "https://www.reddit.com/r/dataanalysis/comments/1kivp3q/what_are_the_most_tedious_parts_of_cleaning_data/",
    "originalTitle": "What are the most tedious parts of cleaning data for you?",
    "verifiedOn": "2026-10-25",
    "treatment": "Editorial paraphrase",
    "support": "Comments by Hot_Coconut_5567 and 3-ma: missing IDs, spellings and joins."
  },
  {
    "id": "hidden-settings",
    "source": "Reddit · r/AskAcademia",
    "category": "discussion",
    "headline": "One undocumented setting.",
    "summary": "A researcher describes months spent trying to replicate a result.",
    "url": "https://www.reddit.com/r/AskAcademia/comments/1jw8e1w/whats_an_unspoken_research_rule_you_learned_too/",
    "originalTitle": "What's an unspoken research rule you learned TOO LATE?",
    "verifiedOn": "2026-10-25",
    "treatment": "Editorial paraphrase",
    "support": "Opening post: an unmentioned RStudio setting prevented replication; personal account, not independently replicated."
  },
  {
    "id": "metadata-gaps",
    "source": "Harvard Data Science Review",
    "category": "study",
    "headline": "Found it. Can I use it?",
    "summary": "Inconsistent metadata makes comparing datasets harder.",
    "url": "https://hdsr.mitpress.mit.edu/pub/psnc8zsr/release/2",
    "originalTitle": "Discovering Datasets on the Web Scale: Challenges and Recommendations for Google Dataset Search",
    "verifiedOn": "2026-10-25",
    "treatment": "Editorial paraphrase",
    "support": "Section 4.2: metadata shortcomings, inconsistent dates and differing fields."
  },
  {
    "id": "scattered-sources",
    "source": "Harvard Data Science Review",
    "category": "note",
    "headline": "Another portal. Another search.",
    "summary": "Researchers struggle to reach the underlying data across sites.",
    "url": "https://hdsr.mitpress.mit.edu/pub/psnc8zsr/release/2",
    "originalTitle": "Discovering Datasets on the Web Scale: Challenges and Recommendations for Google Dataset Search",
    "verifiedOn": "2026-10-25",
    "treatment": "Editorial paraphrase",
    "support": "Sections 4.2 and 5.2: unfamiliar providers, multiple clicks and missing download links."
  },
  {
    "id": "spreadsheet-genes",
    "source": "Retraction Watch",
    "category": "reporting",
    "headline": "When a gene becomes a date.",
    "summary": "Spreadsheet auto-formatting can corrupt scientific identifiers.",
    "url": "https://retractionwatch.com/2023/09/20/guest-post-genomics-has-a-spreadsheet-problem/",
    "originalTitle": "Guest post: Genomics has a spreadsheet problem",
    "verifiedOn": "2026-10-25",
    "treatment": "Editorial paraphrase",
    "support": "Authors describe gene-to-date and five-digit conversions; no claim that study conclusions were affected."
  },
  {
    "id": "mixed-units",
    "source": "PLOS Computational Biology",
    "category": "technical",
    "headline": "One column. Several conventions.",
    "summary": "Mixed units and date formats obstruct reuse.",
    "url": "https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005097",
    "originalTitle": "Ten Simple Rules for Digital Data Storage",
    "verifiedOn": "2026-10-25",
    "treatment": "Editorial paraphrase",
    "support": "Rule 2 and Figure 1: mixed units, observational units, dates and coordinates."
  },
  {
    "id": "undocumented-variables",
    "source": "PLOS Computational Biology",
    "category": "note",
    "headline": "The file needs a memory.",
    "summary": "A README should explain variables, missing values and context.",
    "url": "https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005510",
    "originalTitle": "Good enough practices in scientific computing",
    "verifiedOn": "2026-10-25",
    "treatment": "Editorial paraphrase",
    "support": "Data management recommendations: document variables, units, missing values and metadata."
  },
  {
    "id": "tidy-data",
    "source": "tidyr · Hadley Wickham",
    "category": "technical",
    "headline": "Headers that hide the variables.",
    "summary": "Presentation tables often need restructuring before analysis.",
    "url": "https://tidyr.tidyverse.org/articles/tidy-data",
    "originalTitle": "Tidy data",
    "verifiedOn": "2026-10-25",
    "treatment": "Editorial paraphrase",
    "support": "Section Messy data: headers are values, not variable names; variables in both rows and columns."
  },
  {
    "id": "dataset-fit",
    "source": "DataFinder · ACL research",
    "category": "study",
    "headline": "Relevant is more than a keyword.",
    "summary": "A research question constrains size, modality and domain.",
    "url": "https://arxiv.org/abs/2305.16636",
    "originalTitle": "DataFinder: Scientific Dataset Recommendation from Natural Language Descriptions",
    "verifiedOn": "2026-10-25",
    "treatment": "Editorial paraphrase",
    "support": "Abstract: explicit and implicit research constraints; difficulty of dataset indexing and recommendation."
  },
  {
    "id": "missing-observations",
    "source": "Gaffney & Matias · research",
    "category": "study",
    "headline": "A large corpus. Important gaps.",
    "summary": "Missing observations can bias conclusions drawn from reused data.",
    "url": "https://arxiv.org/abs/1803.05046",
    "originalTitle": "Caveat Emptor, Computational Social Science: Large-Scale Missing Data in a Widely-Published Reddit Corpus",
    "verifiedOn": "2026-10-25",
    "treatment": "Editorial paraphrase",
    "support": "Abstract: substantial missing observations and risks to research validity in a Reddit corpus."
  },
  {
    "id": "request-access",
    "source": "Scientific Data · Nature Portfolio",
    "category": "reporting",
    "headline": "Available on request?",
    "summary": "A study finds that promised access does not always yield data.",
    "url": "https://www.nature.com/articles/s41597-021-00981-0",
    "originalTitle": "Data sharing practices and data availability upon request differ across scientific disciplines",
    "verifiedOn": "2026-10-25",
    "treatment": "Editorial paraphrase",
    "support": "Discussion: fewer than half of datasets stated to be available upon request were obtained."
  },
  {
    "id": "search-requirements",
    "source": "ICPSR · University of Michigan",
    "category": "note",
    "headline": "The search is part of the work.",
    "summary": "Finding data that meets a research question can take time.",
    "url": "https://www.icpsr.umich.edu/sites/icpsr/teaching-learning/build-your-data-skills/how-to-find-a-dataset",
    "originalTitle": "How to Find a Dataset",
    "verifiedOn": "2026-10-25",
    "treatment": "Editorial paraphrase",
    "support": "Message from author and Steps 1–4: finding datasets that meet specific needs is time consuming."
  },
  {
    "id": "suitability",
    "source": "George Washington University",
    "category": "note",
    "headline": "A dataset is only a beginning.",
    "summary": "Researchers still need to check coverage, variables and fit.",
    "url": "https://libguides.gwu.edu/research-data/search-strategies",
    "originalTitle": "Find Research Datasets: Search Strategies",
    "verifiedOn": "2026-10-25",
    "treatment": "Editorial paraphrase",
    "support": "Start With Your Research Question and evaluating data: who, what, where and when."
  },
  {
    "id": "repository-search",
    "source": "University of Maryland · HSHSL",
    "category": "technical",
    "headline": "Where should the search start?",
    "summary": "Relevant variables may be scattered across research repositories.",
    "url": "https://guides.hshsl.umaryland.edu/finding-data/searching",
    "originalTitle": "Finding Data: Search Strategy for Datasets",
    "verifiedOn": "2026-10-25",
    "treatment": "Editorial paraphrase",
    "support": "Search strategy: identify repositories with re3data; choose variables that can test the research question."
  },
  {
    "id": "csv-friction",
    "source": "Reddit · r/dataanalyst",
    "category": "forum",
    "headline": "The CSV still will not load.",
    "summary": "A practitioner describes missing values and formats across tools.",
    "url": "https://www.reddit.com/r/dataanalyst/comments/1o8ll95/does_anyone_else_feel_like_data_cleaning_eats_up/",
    "originalTitle": "Does anyone else feel like data cleaning eats up your entire day?",
    "verifiedOn": "2026-10-25",
    "treatment": "Editorial paraphrase",
    "support": "Opening post: Excel, Power BI and Colab; missing values, renaming and CSV format compatibility."
  },
  {
    "id": "unanswered-requests",
    "source": "Reddit · r/AskAcademia",
    "category": "discussion",
    "headline": "The paper is public. The data?",
    "summary": "A researcher asks what to do when data requests go unanswered.",
    "url": "https://www.reddit.com/r/AskAcademia/comments/16gjn27/does_the_statement_data_will_be_made_available_on/",
    "originalTitle": "Does the statement \"Data will be made available on request\" in articles hold any meaning at all?",
    "verifiedOn": "2026-10-25",
    "treatment": "Editorial paraphrase",
    "support": "Opening post: personal experience requesting data and code; replies include different experiences."
  }
];
