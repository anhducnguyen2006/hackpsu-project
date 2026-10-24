from __future__ import annotations

import pandas as pd

from app.api.schemas import (
    ExploratoryAnalysisResponse,
    ExploratoryCategory,
)


class ExploratoryAnalysisError(ValueError):
    """Raised when requested variables cannot support the exploratory analysis."""


class ExploratoryAnalyzer:
    def analyze(
        self,
        dataset_id: str,
        dataframe: pd.DataFrame,
        independent_variable: str,
        outcome_variable: str,
    ) -> ExploratoryAnalysisResponse:
        missing_columns = [
            column
            for column in (independent_variable, outcome_variable)
            if column not in dataframe.columns
        ]
        if missing_columns:
            raise ExploratoryAnalysisError(
                f"Requested variable(s) are not verified dataset columns: {', '.join(missing_columns)}."
            )
        independent = dataframe[independent_variable]
        outcome_source = dataframe[outcome_variable]
        if not pd.api.types.is_numeric_dtype(outcome_source):
            raise ExploratoryAnalysisError(
                "The outcome variable must contain numeric values for this exploratory workflow."
            )
        outcome = pd.to_numeric(outcome_source, errors="coerce")
        if independent.nunique(dropna=True) > 20:
            raise ExploratoryAnalysisError(
                "The independent variable has too many distinct values for a categorical comparison."
            )
        if independent.nunique(dropna=True) < 2:
            raise ExploratoryAnalysisError(
                "The independent variable must contain at least two observed categories."
            )

        valid = independent.notna() & outcome.notna()
        grouped = pd.DataFrame(
            {"independent": independent[valid], "outcome": outcome[valid]}
        ).groupby("independent", sort=True)["outcome"]
        categories = [
            ExploratoryCategory(
                category=self._safe_value(category),
                observations=int(values.count()),
                mean_outcome=self._safe_float(values.mean()),
                median_outcome=self._safe_float(values.median()),
                standard_deviation=self._safe_float(values.std())
                if len(values) > 1
                else None,
            )
            for category, values in grouped
        ]
        return ExploratoryAnalysisResponse(
            dataset_id=dataset_id,
            independent_variable=independent_variable,
            outcome_variable=outcome_variable,
            independent_measurement_type=(
                "ordinal_or_encoded_numeric"
                if pd.api.types.is_numeric_dtype(independent)
                else "categorical"
            ),
            outcome_measurement_type="numeric",
            categories=categories,
            missing_independent_count=int(independent.isna().sum()),
            missing_outcome_count=int(outcome.isna().sum()),
            excluded_observation_count=int((~valid).sum()),
            analyzed_observation_count=int(valid.sum()),
            limitations=[
                "These are descriptive group summaries, not a causal analysis.",
                "Encoded ordinal categories are displayed as groups; their numeric codes are not treated as exact units.",
                "Observed records may not represent independent participants, and no statistical significance or power claim is made.",
            ],
        )

    @staticmethod
    def _safe_float(value: object) -> float | None:
        return float(value) if pd.notna(value) else None

    @staticmethod
    def _safe_value(value: object) -> object:
        return value.item() if hasattr(value, "item") else value
