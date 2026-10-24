from __future__ import annotations

import time
from typing import Any

import httpx
import numpy as np
import pandas as pd
from ucimlrepo import fetch_ucirepo

from app.api.schemas import UCIRecord


class UCIRepositoryError(RuntimeError):
    """Raised when a UCI repository operation fails."""


class UCIRepositoryService:
    """Structured UCI catalog and dataset access, without parsing CLI output."""

    catalog_url = "https://archive.ics.uci.edu/api/datasets/list"
    metadata_url = "https://archive.ics.uci.edu/api/dataset"
    source = "UCI Machine Learning Repository"

    def __init__(self, client: httpx.Client | None = None, catalog_ttl: int = 900) -> None:
        self.client = client or httpx.Client(timeout=20)
        self.catalog_ttl = catalog_ttl
        self._catalog: list[UCIRecord] | None = None
        self._catalog_loaded_at = 0.0

    def discover_catalog(self, force_refresh: bool = False) -> list[UCIRecord]:
        if (
            not force_refresh
            and self._catalog is not None
            and time.monotonic() - self._catalog_loaded_at < self.catalog_ttl
        ):
            return self._catalog
        try:
            response = self.client.get(self.catalog_url, params={"filter": "python"})
            response.raise_for_status()
            payload = response.json()
            records = payload.get("data")
            if payload.get("status") != 200 or not isinstance(records, list):
                raise ValueError("Unexpected UCI catalog response.")
            self._catalog = [
                self._record_from_catalog(item)
                for item in records
                if isinstance(item, dict) and item.get("id") is not None
            ]
            self._catalog_loaded_at = time.monotonic()
            return self._catalog
        except Exception as error:
            raise UCIRepositoryError(f"Unable to load the UCI catalog: {error}") from error

    def get_metadata(self, dataset_id: int) -> UCIRecord:
        try:
            response = self.client.get(self.metadata_url, params={"id": dataset_id})
            response.raise_for_status()
            payload = response.json()
            metadata = payload.get("data")
            if payload.get("status") != 200 or not isinstance(metadata, dict):
                raise ValueError("Unexpected UCI dataset metadata response.")
            return self._record_from_metadata(metadata)
        except Exception as error:
            raise UCIRepositoryError(
                f"Unable to load UCI metadata for dataset {dataset_id}: {error}"
            ) from error

    def fetch_and_profile(self, dataset_id: int) -> dict[str, Any]:
        try:
            repository_dataset = fetch_ucirepo(id=dataset_id)
            metadata = self._metadata(repository_dataset)
            dataframe = self._original_dataframe(repository_dataset)
        except UCIRepositoryError:
            raise
        except Exception as error:
            raise UCIRepositoryError(
                f"Unable to fetch UCI dataset {dataset_id}: {error}"
            ) from error
        record = self._record_from_metadata(metadata)
        return {
            **record.model_dump(mode="json"),
            "data_status": "analyzed",
            "metadata": self._json_safe(metadata),
            "profile": self._profile(dataframe),
        }

    @classmethod
    def _record_from_catalog(cls, item: dict[str, Any]) -> UCIRecord:
        dataset_id = int(item["id"])
        return UCIRecord(
            dataset_id=f"uci:{dataset_id}",
            title=str(item.get("name", f"UCI dataset {dataset_id}")),
            repository_url=f"https://archive.ics.uci.edu/dataset/{dataset_id}",
            data_available=bool(item.get("url")),
        )

    @classmethod
    def _record_from_metadata(cls, metadata: dict[str, Any]) -> UCIRecord:
        dataset_id = int(metadata["uci_id"])
        variables = metadata.get("variables", [])
        variable_names = [
            str(variable["name"])
            for variable in variables
            if isinstance(variable, dict) and variable.get("name")
        ]
        return UCIRecord(
            dataset_id=f"uci:{dataset_id}",
            title=str(metadata.get("name", f"UCI dataset {dataset_id}")),
            description=metadata.get("abstract"),
            repository_url=metadata.get(
                "repository_url",
                f"https://archive.ics.uci.edu/dataset/{dataset_id}",
            ),
            subject_area=metadata.get("area"),
            variables=variable_names,
            instance_count=metadata.get("num_instances"),
            feature_count=metadata.get("num_features"),
            data_available=bool(metadata.get("data_url")),
        )

    @staticmethod
    def _metadata(repository_dataset: Any) -> dict[str, Any]:
        metadata = getattr(repository_dataset, "metadata", None)
        to_dict = getattr(metadata, "to_dict", None)
        if callable(to_dict):
            metadata = to_dict()
        if not isinstance(metadata, dict):
            raise UCIRepositoryError("UCI response did not include valid metadata.")
        return metadata

    @staticmethod
    def _original_dataframe(repository_dataset: Any) -> pd.DataFrame:
        dataframe = getattr(getattr(repository_dataset, "data", None), "original", None)
        if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
            raise UCIRepositoryError("UCI response did not include a non-empty DataFrame.")
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
        return {
            key: UCIRepositoryService._json_safe(value)
            for key, value in series.describe().to_dict().items()
        }

    @staticmethod
    def _categorical_summary(series: pd.Series) -> dict[str, Any]:
        return {
            "top_values": [
                {"value": UCIRepositoryService._json_safe(value), "count": int(count)}
                for value, count in series.value_counts(dropna=False).head(10).items()
            ]
        }

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): UCIRepositoryService._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [UCIRepositoryService._json_safe(item) for item in value]
        if isinstance(value, (np.integer, np.floating)):
            value = value.item()
        if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
            return None
        if value is None or value is pd.NA:
            return None
        return value


UCIStudentPerformanceAdapter = UCIRepositoryService
