from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

import httpx
from pydantic import ValidationError

from app.api.schemas import DatasetRecord
from app.config import settings
from app.discovery.eligibility import (
    FileAssessment,
    assess_tabular_file,
    inconclusive_resource,
    summarize_files,
)

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
        self._verified: dict[str, DatasetRecord] = {}

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

    def verify(self, record: DatasetRecord) -> DatasetRecord:
        """Load the published record when search did not include files."""
        cached = self._verified.get(record.source_id)
        if cached is not None:
            return cached
        url = self.api_url.rstrip("/") + f"/{record.source_id}"
        try:
            response = self.client.get(url, headers={"Accept": "application/json"})
            self._raise_for_status(response)
            content = getattr(response, "content", b"")
            if isinstance(content, (bytes, bytearray)) and len(content) > 2_000_000:
                raise ZenodoRepositoryError("Zenodo metadata response exceeded the size limit.")
            payload = response.json()
        except ZenodoRepositoryError:
            raise
        except Exception as error:
            raise ZenodoRepositoryError(f"Zenodo record lookup failed: {error}") from error
        if not isinstance(payload, dict):
            verified = record.model_copy(update={
                "eligibility_status": "verification_failed",
                "eligibility_reason": "Zenodo record lookup did not return an object.",
                "data_available": False,
                "download_performed": False,
            })
        else:
            verified = self._record_from_item(payload)
        if len(self._verified) > 128:
            self._verified.clear()
        self._verified[record.source_id] = verified
        return verified

    @classmethod
    def _record_from_item(cls, item: dict[str, Any]) -> DatasetRecord:
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError("record has no metadata object")
        if not cls._is_dataset(metadata):
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
        files_declared = "files" in item
        record_access = cls._record_file_access(item.get("access"))
        candidates: list = []
        assessments = cls._file_assessments(item.get("files"), record_access, candidates)
        status, reason, resources = summarize_files(assessments, files_declared=files_declared)
        if record_access in {"restricted", "embargoed"} and not resources:
            status = "restricted"
            reason = f"Zenodo reports file access as {record_access}."
        license_name = cls._license_name(metadata.get("license"))
        version = metadata.get("version")
        source_version = version.strip() if isinstance(version, str) and version.strip() else None
        return DatasetRecord(
            id=f"zenodo:{source_id}",
            source=cls.source,
            source_id=source_id,
            title=title,
            description=cls._text(metadata.get("description")),
            landing_page_url=landing_page_url,
            download_resources=resources,
            verification_candidates=candidates,
            subjects=cls._subjects(metadata.get("subjects")),
            doi=cls._text(metadata.get("doi") or item.get("doi")),
            license=license_name,
            data_available=True if resources else False if files_declared else None,
            eligibility_status=status,
            eligibility_reason=reason,
            download_performed=False,
            source_version=source_version,
        )

    @staticmethod
    def _is_dataset(metadata: dict[str, Any]) -> bool:
        upload_type = metadata.get("upload_type")
        if isinstance(upload_type, str) and upload_type.strip():
            return upload_type.strip().lower() == "dataset"
        resource_type = metadata.get("resource_type")
        if isinstance(resource_type, dict):
            kind = resource_type.get("id") or resource_type.get("type")
            return isinstance(kind, str) and kind.strip().lower() == "dataset"
        if isinstance(resource_type, str):
            return resource_type.strip().lower() == "dataset"
        return False

    @staticmethod
    def _record_file_access(value: object) -> str:
        if not isinstance(value, dict):
            return "public"
        files = value.get("files") or value.get("status")
        if not isinstance(files, str):
            return "public"
        normalized = files.strip().lower()
        if normalized in {"restricted", "embargoed"}:
            return normalized
        if normalized in {"open", "public"}:
            return "public"
        return "unverified"

    @classmethod
    def _file_assessments(
        cls, value: object, record_access: str, candidates: list | None = None
    ) -> list[FileAssessment]:
        items = cls._file_dicts(value)
        assessments: list[FileAssessment] = []
        for item in items:
            links = item.get("links") if isinstance(item.get("links"), dict) else {}
            url = links.get("self") or links.get("content")
            filename = cls._text(item.get("key") or item.get("filename"))
            file_access = record_access
            item_access = item.get("access")
            if isinstance(item_access, dict) and isinstance(item_access.get("status"), str):
                file_access = cls._record_file_access({"files": item_access["status"]})
            if item.get("restricted") is True:
                file_access = "restricted"
            file_id = item.get("id")
            file_id_text = str(file_id).strip() if isinstance(file_id, (int, str)) and str(file_id).strip() else None
            size = item.get("size") or item.get("filesize")
            size_bytes = size if isinstance(size, int) and size >= 0 else None
            checksum = item.get("checksum")
            checksum_text = checksum.strip() if isinstance(checksum, str) and checksum.strip() else None
            content_type = cls._text(item.get("mimetype") or item.get("content_type"))
            file_url = url if isinstance(url, str) else None
            if candidates is not None:
                candidate = inconclusive_resource(
                    url=file_url,
                    filename=filename,
                    content_type=content_type,
                    size_bytes=size_bytes,
                    checksum=checksum_text,
                    file_id=file_id_text,
                    access_status=file_access,
                    max_bytes=settings.discovery_max_resource_bytes,
                )
                if candidate is not None:
                    candidates.append(candidate)
            try:
                assessments.append(assess_tabular_file(
                    url=file_url,
                    filename=filename,
                    content_type=content_type,
                    size_bytes=size_bytes,
                    checksum=checksum_text,
                    file_id=file_id_text,
                    access_status=file_access,
                    max_bytes=settings.discovery_max_resource_bytes,
                ))
            except ValidationError:
                logger.warning("Ignoring invalid Zenodo file resource.")
        return assessments

    @staticmethod
    def _file_dicts(value: object) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            entries = value.get("entries")
            if isinstance(entries, dict):
                files: list[dict[str, Any]] = []
                for key, entry in entries.items():
                    if isinstance(entry, dict):
                        item = dict(entry)
                        item.setdefault("key", key)
                        files.append(item)
                return files
            if isinstance(entries, list):
                return [item for item in entries if isinstance(item, dict)]
        return []

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
