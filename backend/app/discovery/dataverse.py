from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

import httpx
from pydantic import ValidationError

from app.api.schemas import DatasetRecord, DatasetVariable
from app.config import settings

logger = logging.getLogger(__name__)


class DataverseRepositoryError(RuntimeError):
    """Raised when the Harvard Dataverse search service cannot be used."""


class HarvardDataverseService:
    """Search the documented Harvard Dataverse dataset search endpoint."""

    source = "Harvard Dataverse"

    def __init__(
        self,
        client: httpx.Client | None = None,
        api_url: str = settings.dataverse_api_url,
        default_limit: int = settings.dataverse_results_limit,
    ) -> None:
        self.client = client or httpx.Client(
            timeout=settings.external_request_timeout_seconds,
            follow_redirects=True,
        )
        self.api_url = api_url
        self.default_limit = default_limit

    def search(
        self, search_terms: Iterable[str], limit: int | None = None
    ) -> list[DatasetRecord]:
        terms = [term.strip() for term in search_terms if term.strip()]
        if not terms:
            return []
        params = {
            "q": " ".join(terms),
            "type": "dataset",
            "sort": "score",
            "order": "desc",
            "per_page": limit or self.default_limit,
            "start": 0,
            "query_entities": "true",
        }
        try:
            response = self.client.get(self.api_url, params=params)
            self._raise_for_status(response)
            payload = response.json()
        except DataverseRepositoryError:
            raise
        except Exception as error:
            raise DataverseRepositoryError(
                f"Harvard Dataverse search failed: {error}"
            ) from error

        data = payload.get("data") if isinstance(payload, dict) else None
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise DataverseRepositoryError(
                "Harvard Dataverse returned an unexpected search response."
            )

        records: list[DatasetRecord] = []
        for item in items:
            if not isinstance(item, dict):
                logger.warning("Ignoring invalid Harvard Dataverse search item.")
                continue
            try:
                records.append(self._record_from_item(item))
            except (ValidationError, TypeError, ValueError) as error:
                logger.warning(
                    "Ignoring invalid Harvard Dataverse dataset item: %s", error
                )
        return records

    def verify_analyzable(self, record: DatasetRecord) -> DatasetRecord | None:
        """Resolve published files through the analysis adapter without downloading."""
        from app.analysis.source_providers import DataverseAnalysisProvider, SourceProviderError

        try:
            provider = DataverseAnalysisProvider(client=self.client)
            verified = provider.resolve(record.id)
            resources = provider.resources(verified)
        except SourceProviderError:
            return None
        if not resources:
            return None
        return verified.model_copy(
            update={
                "data_available": True,
                "analysis_eligibility": "supported_resource_verified",
            }
        )

    @classmethod
    def _record_from_item(cls, item: dict[str, Any]) -> DatasetRecord:
        if item.get("type") not in (None, "dataset"):
            raise ValueError("search result is not a dataset")
        source_id = cls._text(item.get("global_id") or item.get("identifier"))
        if not source_id:
            raise ValueError("dataset has no stable Dataverse identifier")
        title = cls._text(item.get("name") or item.get("title"))
        if not title:
            raise ValueError("dataset has no title")
        landing_page_url = cls._text(item.get("url"))
        if landing_page_url is None:
            raise ValueError("dataset has no verified landing page URL")
        global_id = source_id
        doi = (
            global_id
            if global_id.lower().startswith("doi:")
            else cls._text(item.get("doi"))
        )
        file_count = item.get("fileCount")
        data_available = file_count > 0 if isinstance(file_count, int) else None
        return DatasetRecord(
            id=f"dataverse:{source_id}",
            source=cls.source,
            source_id=source_id,
            title=title,
            description=cls._text(item.get("description")),
            landing_page_url=landing_page_url,
            variables=cls._variables(item.get("variables")),
            subjects=cls._text_list(item.get("subjects")),
            doi=doi,
            data_available=data_available,
        )

    @staticmethod
    def _variables(value: object) -> list[DatasetVariable]:
        if not isinstance(value, list):
            return []
        variables: list[DatasetVariable] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            variables.append(
                DatasetVariable(
                    name=name,
                    description=item.get("description"),
                    data_type=item.get("data_type"),
                    unit=item.get("unit"),
                )
            )
        return variables

    @staticmethod
    def _text(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized or None

    @classmethod
    def _text_list(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in (cls._text(entry) for entry in value) if item]

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code == 429:
            raise DataverseRepositoryError(
                "Harvard Dataverse rate limit reached (HTTP 429)."
            )
        try:
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise DataverseRepositoryError(
                f"Harvard Dataverse returned HTTP {response.status_code}."
            ) from error
