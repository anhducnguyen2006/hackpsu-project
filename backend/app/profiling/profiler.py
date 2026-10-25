from __future__ import annotations

import re
from typing import Iterable

import numpy as np
import pandas as pd

from app.api.schemas import (
    CategoryCount,
    ColumnProfile,
    CorrelationResult,
    DataProfile,
    NumericSummary,
    ResearchInterpretation,
    ResearchVariableEvidence,
)


class DataProfiler:
    """Deterministic Pandas/NumPy profiling with conservative measurement labels."""

    # Bump when the profile algorithm or its serialized shape changes.
    PROFILER_VERSION = "data-profiler-v4"

    def profile(
        self,
        dataframe: pd.DataFrame,
        interpretation: ResearchInterpretation | None = None,
        variable_descriptions: dict[str, str] | None = None,
        variable_types: dict[str, str] | None = None,
    ) -> DataProfile:
        descriptions = variable_descriptions or {}
        types = variable_types or {}
        columns = [
            self._column_profile(
                dataframe[name],
                descriptions.get(str(name)),
                types.get(str(name)),
            )
            for name in dataframe.columns
        ]
        evidence = (
            self._research_evidence(dataframe, interpretation, descriptions)
            if interpretation
            else []
        )
        roles: dict[str, set[str]] = {}
        if interpretation:
            for variable in interpretation.independent_variables:
                for column in self._matched_columns(dataframe, variable, descriptions):
                    roles.setdefault(column, set()).add("independent")
            for variable in interpretation.dependent_variables:
                for column in self._matched_columns(dataframe, variable, descriptions):
                    roles.setdefault(column, set()).add("outcome")
            for column in columns:
                column.research_roles = sorted(roles.get(column.name, set()))
        correlations = self._correlations(dataframe, evidence)
        flags = [
            f"{column.name} is constant."
            for column in columns
            if column.is_constant
        ]
        flags.extend(
            f"{column.name} has fewer than 10% nonmissing observations."
            for column in columns
            if column.is_near_empty
        )
        if len(dataframe) != len(dataframe.drop_duplicates()):
            flags.append("Duplicate rows are present; row count may overstate unique records.")
        flags.append(
            "Row count is not necessarily the number of independent participants."
        )
        return DataProfile(
            row_count=int(len(dataframe)),
            column_count=int(len(dataframe.columns)),
            column_names=[str(name) for name in dataframe.columns],
            duplicate_row_count=int(dataframe.duplicated().sum()),
            columns=columns,
            research_variable_evidence=evidence,
            correlations=correlations,
            quality_flags=flags,
        )

    def _column_profile(
        self,
        series: pd.Series,
        variable_description: str | None = None,
        declared_type: str | None = None,
    ) -> ColumnProfile:
        nonmissing = series.dropna()
        unique_count = int(nonmissing.nunique())
        identifier_like = self._identifier_like(series)
        numeric = pd.api.types.is_numeric_dtype(series)
        source_measurement_type = self._declared_measurement_type(declared_type)
        if identifier_like:
            measurement_type = "identifier_like"
        elif source_measurement_type is not None:
            measurement_type = source_measurement_type
        elif self._is_binary(series, variable_description):
            measurement_type = "binary"
        elif numeric and unique_count <= 10 and self._ordinal_context(
            str(series.name), variable_description
        ):
            measurement_type = "ordinal"
        elif numeric:
            measurement_type = (
                "discrete_numeric"
                if self._is_discrete_numeric(series)
                else "continuous"
            )
        else:
            measurement_type = "categorical"
        show_numeric_summary = measurement_type in {"continuous", "discrete_numeric"}
        show_categories = measurement_type in {"binary", "ordinal", "categorical"}
        return ColumnProfile(
            name=str(series.name),
            variable_description=variable_description,
            data_type=str(series.dtype),
            measurement_type=measurement_type,
            missing_count=int(series.isna().sum()),
            missing_fraction=float(series.isna().mean()),
            unique_count=unique_count,
            is_constant=unique_count <= 1,
            is_near_empty=float(series.notna().mean()) < 0.10,
            numeric_summary=self._numeric_summary(series) if show_numeric_summary else None,
            categorical_summary=(
                self._categorical_summary(series)
                if show_categories
                else []
            ),
        )

    @staticmethod
    def _declared_measurement_type(declared_type: str | None) -> str | None:
        normalized = (declared_type or "").strip().lower().replace("-", "_")
        return {
            "binary": "binary",
            "categorical": "categorical",
            "integer": "discrete_numeric",
            "continuous": "continuous",
        }.get(normalized)

    @staticmethod
    def _is_binary(series: pd.Series, description: str | None) -> bool:
        if pd.api.types.is_bool_dtype(series):
            return True
        text = (description or "").lower()
        if re.search(r"\bbinary\b", text):
            return True
        nonmissing = series.dropna()
        if pd.api.types.is_numeric_dtype(series):
            return set(nonmissing.tolist()).issubset({0, 1})
        return int(nonmissing.nunique()) == 2

    @staticmethod
    def _ordinal_context(name: str, description: str | None) -> bool:
        """Identify numeric fields whose values represent ordered categories."""
        text = f"{name} {description or ''}".lower()
        if re.search(r"\b(age|year|height|weight|amount|quantity|count|duration)\b", text):
            return False
        return True

    @staticmethod
    def _is_discrete_numeric(series: pd.Series) -> bool:
        """Identify quantitative values recorded only at whole-number increments."""
        if pd.api.types.is_integer_dtype(series):
            return True
        numeric = pd.to_numeric(series.dropna(), errors="coerce")
        if numeric.empty or numeric.isna().any():
            return False
        return bool(np.isclose(numeric, np.round(numeric)).all())

    def _matched_columns(
        self, dataframe: pd.DataFrame, variable: str, descriptions: dict[str, str]
    ) -> list[str]:
        return [
            str(column)
            for column in dataframe.columns
            if self._semantic_match(
                variable,
                f"{column} {descriptions.get(str(column), '')}",
            )
        ]

    @staticmethod
    def _numeric_summary(series: pd.Series) -> NumericSummary:
        numeric = pd.to_numeric(series, errors="coerce").dropna()
        if numeric.empty:
            return NumericSummary(count=0)
        return NumericSummary(
            count=int(numeric.count()),
            mean=DataProfiler._safe_float(numeric.mean()),
            median=DataProfiler._safe_float(numeric.median()),
            standard_deviation=DataProfiler._safe_float(numeric.std()),
            minimum=DataProfiler._safe_float(numeric.min()),
            percentile_25=DataProfiler._safe_float(numeric.quantile(0.25)),
            percentile_75=DataProfiler._safe_float(numeric.quantile(0.75)),
            maximum=DataProfiler._safe_float(numeric.max()),
        )

    @staticmethod
    def _categorical_summary(series: pd.Series) -> list[CategoryCount]:
        return [
            CategoryCount(value=DataProfiler._safe_value(value), count=int(count))
            for value, count in series.value_counts(dropna=False).head(10).items()
        ]

    def _research_evidence(
        self,
        dataframe: pd.DataFrame,
        interpretation: ResearchInterpretation,
        variable_descriptions: dict[str, str],
    ) -> list[ResearchVariableEvidence]:
        variables = (
            interpretation.independent_variables
            + interpretation.dependent_variables
            + interpretation.synonyms
        )
        evidence = []
        for variable in dict.fromkeys(variables):
            tokens = self._tokens([variable])
            matches = self._matched_columns(dataframe, variable, variable_descriptions)
            usable = int(dataframe[matches].notna().all(axis=1).sum()) if matches else 0
            pairs = {}
            for index, first in enumerate(matches):
                for second in matches[index + 1:]:
                    pairs[f"{first} + {second}"] = int(
                        dataframe[[first, second]].dropna().shape[0]
                    )
            notes = []
            if matches and all(
                self._column_profile(dataframe[column]).measurement_type
                == "ordinal"
                for column in matches
            ):
                notes.append(
                    "Numeric storage may encode ordered categories; values are not assumed to be exact units."
                )
            evidence.append(
                ResearchVariableEvidence(
                    research_variable=variable,
                    matched_columns=matches,
                    usable_observations=usable,
                    matched_pairs=pairs,
                    notes=notes,
                )
            )
        return evidence

    @staticmethod
    def _correlations(
        dataframe: pd.DataFrame, evidence: list[ResearchVariableEvidence]
    ) -> list[CorrelationResult]:
        relevant = [
            column
            for item in evidence
            for column in item.matched_columns
        ]
        results = []
        for index, first in enumerate(dict.fromkeys(relevant)):
            for second in list(dict.fromkeys(relevant))[index + 1:]:
                pair = dataframe[[first, second]].apply(pd.to_numeric, errors="coerce").dropna()
                if len(pair) < 3:
                    continue
                correlation = pair[first].corr(pair[second])
                results.append(
                    CorrelationResult(
                        column_a=first,
                        column_b=second,
                        pair_count=int(len(pair)),
                        pearson_correlation=DataProfiler._safe_float(correlation),
                        limitation=(
                            "Pearson correlation measures association only and does not establish causation; "
                            "ordinal encodings may not represent equal intervals."
                        ),
                    )
                )
        return results

    @staticmethod
    def _identifier_like(series: pd.Series) -> bool:
        name = str(series.name).lower()
        return (
            name in {"id", "index"}
            or name.endswith("_id")
            or (len(series.dropna()) > 20 and series.nunique(dropna=True) / len(series.dropna()) > 0.98)
        )

    @staticmethod
    def _tokens(values: Iterable[str]) -> set[str]:
        return {
            token
            for value in values
            for token in re.findall(r"[a-z0-9]+", value.lower())
            if len(token) > 2
        }

    @staticmethod
    def _semantic_match(variable: str, column_text: str) -> bool:
        normalized_variable = re.sub(r"[^a-z0-9]", "", variable.lower())
        normalized_column = re.sub(r"[^a-z0-9]", "", column_text.lower())
        if normalized_variable and normalized_variable in normalized_column:
            return True
        variable_tokens = {
            token.rstrip("s") for token in re.findall(r"[a-z0-9]+", variable.lower())
        }
        column_tokens = {
            token.rstrip("s") for token in re.findall(r"[a-z0-9]+", column_text.lower())
        }
        if len(variable_tokens) == 1:
            return bool(variable_tokens & column_tokens)
        if variable_tokens.issubset(column_tokens):
            return True
        outcome_terms = {"performance", "outcome", "result", "achievement"}
        measured_terms = {"grade", "score", "outcome", "result", "performance"}
        return bool(variable_tokens & outcome_terms) and bool(column_tokens & measured_terms)

    @staticmethod
    def _safe_float(value: object) -> float | None:
        number = float(value)
        return number if np.isfinite(number) else None

    @staticmethod
    def _safe_value(value: object) -> object:
        if pd.isna(value):
            return None
        if isinstance(value, (np.integer, np.floating)):
            return value.item()
        return value
