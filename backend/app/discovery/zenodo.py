from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import PurePosixPath
from typing import Any

import httpx
from pydantic import ValidationError

from app.api.schemas import DatasetRecord, DownloadResource
from app.config import settings

logger = logging.getLogger(__name__)


class ZenodoRepositoryError(RuntimeError):
    """Raised when the Zenodo records search service cannot be used."""


class ZenodoService:
    """Search published Zenodo records using the documented records API."""

    source = "Zenodo"

    def __init__(
        self,
        client: httpx.Client | None = None,
        api_url: str = settings.zenodo_api_url,
        default_limit: int = settings.zenodo_results_limit,
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
            "status": "published",
            "sort": "bestmatch",
            "page": 1,
            "size": limit or self.default_limit,
            "all_versions": "false",
            "type": "dataset",
        }
        try:
            response = self.client.get(
                self.api_url, params=params, headers={"Accept": "application/json"}
            )
            self._raise_for_status(response)
            payload = response.json()
        except ZenodoRepositoryError:
            raise
        except Exception as error:
            raise ZenodoRepositoryError(f"Zenodo search failed: {error}") from error

        items = self._items(payload)
        if items is None:
            raise ZenodoRepositoryError(
                "Zenodo returned an unexpected records search response."
            )
        records: list[DatasetRecord] = []
        for item in items:
            if not isinstance(item, dict):
                logger.warning("Ignoring invalid Zenodo search item.")
                continue
            try:
                records.append(self._record_from_item(item))
            except (ValidationError, TypeError, ValueError) as error:
                logger.warning("Ignoring invalid Zenodo dataset item: %s", error)
        return records

    def verify_analyzable(self, record: DatasetRecord) -> DatasetRecord | None:
        """Resolve published files through the analysis adapter without downloading."""
        from app.analysis.source_providers import SourceProviderError, ZenodoAnalysisProvider

        try:
            provider = ZenodoAnalysisProvider(client=self.client)
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
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError("record has no metadata object")
        upload_type = metadata.get("upload_type")
        if upload_type is not None and str(upload_type).lower() != "dataset":
            raise ValueError("record is not a dataset")
        raw_source_id = item.get("id")
        source_id = (
            str(raw_source_id).strip()
            if isinstance(raw_source_id, (int, str))
            else None
        )
        title = cls._text(metadata.get("title"))
        if not source_id or not title:
            raise ValueError("record has no stable ID or title")
        links = item.get("links") if isinstance(item.get("links"), dict) else {}
        landing_page_url = cls._text(links.get("html") or links.get("self_html"))
        if landing_page_url is None:
            raise ValueError("record has no verified landing page URL")
        resources = cls._resources(item.get("files"))
        if not resources:
            raise ValueError("record has no supported public tabular resource")
        license_value = metadata.get("license")
        license_name = cls._license_name(license_value)
        return DatasetRecord(
            id=f"zenodo:{source_id}",
            source=cls.source,
            source_id=source_id,
            title=title,
            description=cls._text(metadata.get("description")),
            landing_page_url=landing_page_url,
            download_resources=resources,
            subjects=cls._subjects(metadata.get("subjects")),
            doi=cls._text(metadata.get("doi")),
            license=license_name,
            data_available=True if resources else None,
        )

    @classmethod
    def _resources(cls, value: object) -> list[DownloadResource]:
        if not isinstance(value, list):
            return []
        resources: list[DownloadResource] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            links = item.get("links")
            url = links.get("self") if isinstance(links, dict) else None
            filename = cls._text(item.get("key") or item.get("filename"))
            mimetype = cls._text(item.get("mimetype"))
            file_format = cls._format(mimetype, filename)
            if not isinstance(url, str) or not file_format:
                continue
            try:
                resources.append(DownloadResource(url=url, format=file_format))
            except ValidationError:
                logger.warning("Ignoring invalid Zenodo file resource.")
        return resources

    @staticmethod
    def _format(mimetype: str | None, filename: str | None) -> str | None:
        if mimetype:
            normalized = mimetype.split(";", 1)[0].strip().lower()
            if normalized in {"text/csv", "text/comma-separated-values"}:
                return "csv"
            if normalized in {"text/tab-separated-values", "text/tsv"}:
                return "tsv"
            return None
        if filename:
            suffix = PurePosixPath(filename).suffix.lstrip(".").lower()
            if suffix in {"csv", "tsv", "tab"}:
                return "tsv" if suffix in {"tsv", "tab"} else "csv"
        return None

    @classmethod
    def _subjects(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        subjects: list[str] = []
        for item in value:
            subject = item.get("term") if isinstance(item, dict) else item
            normalized = cls._text(subject)
            if normalized and normalized not in subjects:
                subjects.append(normalized)
        return subjects

    @staticmethod
    def _license_name(value: object) -> str | None:
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, dict):
            for key in ("id", "title"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
        return None

    @staticmethod
    def _text(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _items(payload: object) -> list[object] | None:
        if isinstance(payload, dict):
            hits = payload.get("hits")
            if isinstance(hits, dict) and isinstance(hits.get("hits"), list):
                return hits["hits"]
            if isinstance(payload.get("hits"), list):
                return payload["hits"]
        if isinstance(payload, list):
            return payload
        return None

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code == 429:
            raise ZenodoRepositoryError("Zenodo rate limit reached (HTTP 429).")
        try:
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise ZenodoRepositoryError(
                f"Zenodo returned HTTP {response.status_code}."
            ) from error
