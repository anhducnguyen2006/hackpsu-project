from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from ucimlrepo import fetch_ucirepo


class UCIRepositoryError(RuntimeError):
    """Raised when a UCI dataset cannot be fetched or safely profiled."""


class UCIStudentPerformanceAdapter:
    """Small UCI adapter kept independent from the HTTP route layer."""

    dataset_id = 320
    fallback_source_url = "https://archive.ics.uci.edu/dataset/320/student+performance"

    def fetch_and_profile(self) -> dict[str, Any]:
        try:
            repository_dataset = fetch_ucirepo(id=self.dataset_id)
            metadata = self._metadata(repository_dataset)
            dataframe = self._original_dataframe(repository_dataset)
            profile = self._profile(dataframe)
        except UCIRepositoryError:
            raise
        except Exception as error:
            raise UCIRepositoryError(
                f"Unable to fetch or profile UCI dataset {self.dataset_id}: {error}"
            ) from error

        return {
            "dataset_id": f"uci:{self.dataset_id}",
            "title": metadata.get("name", "Student Performance"),
            "source": "UCI Machine Learning Repository",
            "description": metadata.get("abstract"),
            "repository_url": metadata.get("repository_url", self.fallback_source_url),
            "data_status": "analyzed",
            "metadata": self._json_safe(metadata),
            "profile": profile,
        }

    @staticmethod
    def _metadata(repository_dataset: Any) -> dict[str, Any]:
        metadata = getattr(repository_dataset, "metadata", None)
        if metadata is None:
            raise UCIRepositoryError("UCI response did not include metadata.")
        to_dict = getattr(metadata, "to_dict", None)
        if callable(to_dict):
            metadata = to_dict()
        if not isinstance(metadata, dict):
            raise UCIRepositoryError("UCI metadata had an unexpected format.")
        return metadata

    @staticmethod
    def _original_dataframe(repository_dataset: Any) -> pd.DataFrame:
        data = getattr(repository_dataset, "data", None)
        dataframe = getattr(data, "original", None)
        if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
            raise UCIRepositoryError(
                "UCI response did not include a non-empty original DataFrame."
            )
        return dataframe

    def _profile(self, dataframe: pd.DataFrame) -> dict[str, Any]:
        columns = []
        for name in dataframe.columns:
            series = dataframe[name]
            entry: dict[str, Any] = {
                "name": str(name),
                "data_type": str(series.dtype),
                "missing_count": int(series.isna().sum()),
                "missing_fraction": float(series.isna().mean()),
                "unique_count": int(series.nunique(dropna=True)),
            }
            if pd.api.types.is_numeric_dtype(series):
                entry["summary"] = self._numeric_summary(series)
            else:
                entry["categorical_summary"] = self._categorical_summary(series)
            columns.append(entry)

        return {
            "row_count": int(dataframe.shape[0]),
            "column_count": int(dataframe.shape[1]),
            "columns": columns,
        }

    @staticmethod
    def _numeric_summary(series: pd.Series) -> dict[str, Any]:
        summary = series.describe()
        return {
            key: UCIStudentPerformanceAdapter._json_safe(value)
            for key, value in summary.to_dict().items()
        }

    @staticmethod
    def _categorical_summary(series: pd.Series) -> dict[str, Any]:
        counts = series.value_counts(dropna=False).head(10)
        return {
            "top_values": [
                {
                    "value": UCIStudentPerformanceAdapter._json_safe(value),
                    "count": int(count),
                }
                for value, count in counts.items()
            ]
        }

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): UCIStudentPerformanceAdapter._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [UCIStudentPerformanceAdapter._json_safe(item) for item in value]
        if isinstance(value, (np.integer, np.floating)):
            value = value.item()
        if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
            return None
        if pd.isna(value):
            return None
        return value
