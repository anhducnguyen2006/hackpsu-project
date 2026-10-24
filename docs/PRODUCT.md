# Product Definition

Last verified: 2026-10-24

## Overview

ResearchLens helps researchers decide whether public datasets are plausible starting points for a research question. It connects natural-language discovery with verified repository metadata and deterministic initial profiling.

## Problem and users

Researchers often spend time locating datasets, understanding variables, cleaning data, and checking whether a dataset can support an intended analysis. Primary users are students, academic researchers, and exploratory analysts evaluating public data.

## Value proposition

ResearchLens makes the first evaluation pass faster and more transparent by showing provenance, variable evidence, descriptive statistics, limitations, and explicit uncertainty in one workflow.

## Core journey

**Research Question → Dataset Discovery → Statistical Profiling → AI Suitability Evaluation → Dataset Comparison → Research Decision**

Gemini interprets questions, evaluates semantic relevance of verified datasets, and interprets computed evidence. Python performs statistical calculations and weighted score arithmetic. The product does not prove or disprove a hypothesis and does not establish causation.

## Current MVP

- UCI catalog discovery and metadata enrichment
- Gemini interpretation and semantic reranking with keyword fallback
- Student Performance and other UCI tabular profiling
- Missingness, duplicates, numeric/categorical summaries, and measurement labels
- Research-variable evidence and limitations
- Heuristic suitability scoring when validated criteria exist
- Descriptive grouped exploratory analysis and responsive SVG visualization
- Dataset comparison
- Explicit cached DEMO_MODE
- Loading, error, empty, timeout, and retry states

## Scope limitations

Only UCI is implemented. There is no authentication, saved project, persistent database, deployment system, causal inference, significance testing, power analysis, or automated cleaning pipeline. Scores are heuristic and evidence-dependent.

## HackPSU pitch

“ResearchLens turns a research question into a transparent first look at real public datasets. It combines Gemini’s semantic interpretation with verified UCI metadata and reproducible Pandas statistics, so researchers can see not just what looks relevant, but what the data actually contains—and where the evidence stops.”

## Future opportunities

Additional repository adapters, durable provenance, researcher workspaces, richer validated statistical methods, and exportable reports are possible future work. Each would require explicit evidence and privacy decisions.
