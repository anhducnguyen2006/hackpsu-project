from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date
from typing import Any

import httpx
from pydantic import ValidationError

from app.api.schemas import DatasetRecord, DatasetVariable
from app.config import settings
from app.discovery.eligibility import (
    FileAssessment,
    assess_tabular_file,
    embargo_status,
    inconclusive_resource,
    summarize_files,
)

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
        self._verified: dict[str, DatasetRecord] = {}

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
        # fileCount is not evidence of a public tabular file. Search hits stay
        # unverified until published version metadata is inspected.
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
            data_available=None,
            eligibility_status="unverified",
            eligibility_reason="Dataverse search did not include file metadata.",
            download_performed=False,
        )

    def verify(self, record: DatasetRecord, today: date | None = None) -> DatasetRecord:
        """Resolve published file metadata. Does not download file bytes."""
        persistent_id = record.doi or record.source_id
        cached = self._verified.get(persistent_id)
        if cached is not None:
            return cached
        url = self._dataset_metadata_url()
        try:
            response = self.client.get(url, params={"persistentId": persistent_id})
            self._raise_for_status(response)
            self._reject_oversized(response)
            payload = response.json()
        except DataverseRepositoryError:
            raise
        except Exception as error:
            raise DataverseRepositoryError(
                f"Harvard Dataverse metadata lookup failed: {error}"
            ) from error
        verified = self._apply_version_metadata(record, payload, today or date.today())
        if len(self._verified) > 128:
            self._verified.clear()
        self._verified[persistent_id] = verified
        return verified

    def _dataset_metadata_url(self) -> str:
        root = self.api_url.split("/api/", 1)[0].rstrip("/")
        return f"{root}/api/datasets/:persistentId/"

    def _apply_version_metadata(
        self, record: DatasetRecord, payload: object, today: date
    ) -> DatasetRecord:
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return self._failed(record, "Dataverse dataset metadata had no data object.")
        version = data.get("latestVersion")
        if not isinstance(version, dict):
            return self._failed(record, "Dataverse dataset metadata had no published version.")
        state = str(version.get("versionState") or "").upper()
        if state != "RELEASED":
            return record.model_copy(update={
                "eligibility_status": "unsupported",
                "eligibility_reason": "Dataverse dataset is not a released published version.",
                "data_available": False,
                "download_performed": False,
                "download_resources": [],
            })
        version_number = version.get("versionNumber")
        minor = version.get("versionMinorNumber")
        source_version = None
        if isinstance(version_number, int):
            source_version = f"{version_number}.{minor}" if isinstance(minor, int) else str(version_number)
        files = version.get("files")
        files_declared = isinstance(files, list)
        candidates: list = []
        assessments = [
            self._assess_file(item, today, candidates)
            for item in files
            if isinstance(item, dict)
        ] if files_declared else []
        status, reason, resources = summarize_files(assessments, files_declared=files_declared)
        title = self._citation_title(version) or record.title
        return record.model_copy(update={
            "title": title,
            "eligibility_status": status,
            "eligibility_reason": reason,
            "download_resources": resources,
            "verification_candidates": candidates,
            "data_available": status == "supported_resource_verified",
            "download_performed": False,
            "source_version": source_version,
        })

    def _assess_file(
        self, item: dict[str, Any], today: date, candidates: list | None = None
    ) -> FileAssessment:
        data_file = item.get("dataFile") if isinstance(item.get("dataFile"), dict) else {}
        file_id = data_file.get("id")
        file_id_text = str(file_id) if isinstance(file_id, int) or (
            isinstance(file_id, str) and file_id.strip()
        ) else None
        access = "public"
        embargo = item.get("embargo") if isinstance(item.get("embargo"), dict) else None
        if embargo is not None:
            embargo_state = embargo_status(
                embargo.get("dateAvailable") if isinstance(embargo.get("dateAvailable"), str) else None,
                today,
            )
            if embargo_state == "unverified":
                access = "unverified"
            elif embargo_state == "embargoed":
                access = "embargoed"
        if item.get("restricted") is True or data_file.get("restricted") is True:
            access = "restricted"
        filename = data_file.get("filename") if isinstance(data_file.get("filename"), str) else None
        original_name = data_file.get("originalFileName") if isinstance(data_file.get("originalFileName"), str) else None
        if original_name is None and isinstance(item.get("label"), str):
            original_name = item.get("label")
        size = data_file.get("filesize")
        size_bytes = size if isinstance(size, int) and size >= 0 else None
        checksum = None
        checksum_value = data_file.get("checksum")
        if isinstance(checksum_value, dict) and isinstance(checksum_value.get("value"), str):
            checksum = checksum_value["value"]
        elif isinstance(data_file.get("md5"), str):
            checksum = data_file["md5"]
        url = None
        if file_id_text:
            root = self.api_url.split("/api/", 1)[0].rstrip("/")
            url = f"{root}/api/access/datafile/{file_id_text}"
        content_type = data_file.get("contentType") if isinstance(data_file.get("contentType"), str) else None
        original_format = data_file.get("originalFileFormat") if isinstance(data_file.get("originalFileFormat"), str) else None
        if candidates is not None:
            candidate = inconclusive_resource(
                url=url,
                filename=filename,
                original_filename=original_name,
                content_type=content_type,
                original_format=original_format,
                size_bytes=size_bytes,
                checksum=checksum,
                file_id=file_id_text,
                access_status=access,
                max_bytes=settings.discovery_max_resource_bytes,
            )
            if candidate is not None:
                candidates.append(candidate)
        return assess_tabular_file(
            url=url,
            filename=filename,
            original_filename=original_name,
            content_type=content_type,
            original_format=original_format,
            size_bytes=size_bytes,
            checksum=checksum,
            file_id=file_id_text,
            access_status=access,
            max_bytes=settings.discovery_max_resource_bytes,
        )

    @staticmethod
    def _citation_title(version: dict[str, Any]) -> str | None:
        blocks = version.get("metadataBlocks")
        citation = blocks.get("citation") if isinstance(blocks, dict) else None
        fields = citation.get("fields") if isinstance(citation, dict) else None
        if not isinstance(fields, list):
            return None
        for field in fields:
            if (
                isinstance(field, dict)
                and field.get("typeName") == "title"
                and isinstance(field.get("value"), str)
                and field["value"].strip()
            ):
                return field["value"].strip()
        return None

    @staticmethod
    def _failed(record: DatasetRecord, reason: str) -> DatasetRecord:
        return record.model_copy(update={
            "eligibility_status": "verification_failed",
            "eligibility_reason": reason,
            "data_available": False,
            "download_performed": False,
            "download_resources": [],
        })

    @staticmethod
    def _reject_oversized(response: httpx.Response) -> None:
        content = getattr(response, "content", b"")
        if isinstance(content, (bytes, bytearray)) and len(content) > 2_000_000:
            raise DataverseRepositoryError(
                "Harvard Dataverse metadata response exceeded the size limit."
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
