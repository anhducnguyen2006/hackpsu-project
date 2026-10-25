from __future__ import annotations

import ipaddress
import io
import socket
import threading
from pathlib import PurePosixPath
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx
import pandas as pd
from pydantic import ValidationError

from app.api.schemas import DatasetRecord, DatasetResource, DatasetResourceListing
from app.config import settings


class ResourceProviderError(RuntimeError):
    """Raised when a recognized repository cannot resolve or retrieve a resource."""


class UnsupportedResourceError(ResourceProviderError):
    """Raised when a repository has no supported public tabular resource."""


class SecureDownloadError(ResourceProviderError):
    """Raised when a resource violates download safety constraints."""


class ResourceProvider(Protocol):
    source: str

    def list_resources(self, dataset_id: str) -> DatasetResourceListing:
        ...

    def download(self, dataset_id: str, resource_id: str) -> tuple[DatasetRecord, DatasetResource, pd.DataFrame]:
        ...


SUPPORTED_FORMATS = {"csv", "tsv", "tab"}
PROVIDER_HOSTS = {
    "dataverse": {"dataverse.harvard.edu"},
    "zenodo": {"zenodo.org"},
}


def _safe_https_url(value: str, allowed_hosts: set[str]) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise SecureDownloadError("Resource URL must use HTTPS.")
    host = parsed.hostname.lower().rstrip(".")
    if host not in allowed_hosts:
        raise SecureDownloadError("Resource URL host is not an approved repository host.")
    try:
        addresses = {
            ipaddress.ip_address(info[4][0])
            for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        }
    except OSError as error:
        raise SecureDownloadError("Resource host could not be resolved safely.") from error
    if any(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
        for address in addresses
    ):
        raise SecureDownloadError("Resource host resolves to a private or reserved address.")
    return value


class BoundedDownloader:
    def __init__(
        self,
        client: httpx.Client,
        allowed_hosts: set[str],
        max_bytes: int = settings.analysis_max_download_bytes,
        max_redirects: int = settings.analysis_max_redirects,
    ) -> None:
        self.client = client
        self.allowed_hosts = allowed_hosts
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self._semaphore = threading.BoundedSemaphore(
            max(1, settings.analysis_download_concurrency)
        )

    def read(self, url: str) -> tuple[bytes, str | None]:
        current = _safe_https_url(url, self.allowed_hosts)
        for _ in range(self.max_redirects + 1):
            with self._semaphore:
                with self.client.stream("GET", current, follow_redirects=False) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise SecureDownloadError(
                                "Resource redirect did not include a destination."
                            )
                        current = _safe_https_url(
                            str(httpx.URL(current).join(location)),
                            self.allowed_hosts,
                        )
                        continue
                    if response.status_code >= 400:
                        raise ResourceProviderError(
                            f"Resource download returned HTTP {response.status_code}."
                        )
                    declared_length = response.headers.get("content-length")
                    try:
                        declared_size = int(declared_length) if declared_length else None
                    except ValueError as error:
                        raise SecureDownloadError(
                            "Resource content length was invalid."
                        ) from error
                    if declared_size is not None and declared_size > self.max_bytes:
                        raise SecureDownloadError(
                            "Resource exceeds the configured download limit."
                        )
                    chunks: list[bytes] = []
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > self.max_bytes:
                            raise SecureDownloadError(
                                "Resource exceeds the configured download limit."
                            )
                        chunks.append(chunk)
                    payload = b"".join(chunks)
                    if not payload:
                        raise ResourceProviderError("Resource download was empty.")
                    return payload, response.headers.get("content-type")
        raise SecureDownloadError("Resource exceeded the redirect limit.")


def parse_tabular(payload: bytes, filename: str, content_type: str | None) -> pd.DataFrame:
    suffix = PurePosixPath(filename).suffix.lower().lstrip(".")
    if suffix not in SUPPORTED_FORMATS:
        raise UnsupportedResourceError("Only CSV and TSV resources are supported.")
    if not payload:
        raise SecureDownloadError("Resource is empty.")
    if payload[:4] in {b"PK\x03\x04", b"\x1f\x8b\x08", b"%PDF"} or b"\x00" in payload[:4096]:
        raise UnsupportedResourceError("Archives, PDFs, and compressed files are not tabular resources.")
    if content_type and any(
        marker in content_type.lower()
        for marker in (
            "pdf",
            "zip",
            "gzip",
            "html",
            "json",
            "octet-stream",
            "application/x-binary",
        )
    ):
        raise UnsupportedResourceError("Resource content type is not a supported tabular format.")
    try:
        dataframe = pd.read_csv(
            io.BytesIO(payload),
            sep="\t" if suffix in {"tsv", "tab"} else ",",
            low_memory=False,
        )
    except (
        ValueError,
        UnicodeDecodeError,
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
    ) as error:
        raise ResourceProviderError("Resource could not be parsed as a valid tabular file.") from error
    if dataframe.empty or dataframe.shape[0] > settings.analysis_max_rows:
        raise SecureDownloadError("Resource is empty or exceeds the supported row limit.")
    if dataframe.shape[1] == 0 or dataframe.shape[1] > settings.analysis_max_columns:
        raise SecureDownloadError("Resource exceeds the supported column limit.")
    return dataframe


class HarvardDataverseAnalysisProvider:
    source = "Harvard Dataverse"

    def __init__(
        self,
        client: httpx.Client | None = None,
        api_url: str = "https://dataverse.harvard.edu/api/search",
    ) -> None:
        self.client = client or httpx.Client(timeout=settings.external_request_timeout_seconds)
        self.api_url = api_url
        self.metadata_url = "https://dataverse.harvard.edu/api/datasets/:persistentId"
        self.allowed_hosts = PROVIDER_HOSTS["dataverse"]
        self.downloader = BoundedDownloader(self.client, self.allowed_hosts)

    def list_resources(self, dataset_id: str) -> DatasetResourceListing:
        persistent_id = self._source_id(dataset_id, "dataverse")
        payload = self._get_json(
            self.metadata_url,
            {"persistentId": persistent_id},
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ResourceProviderError("Dataverse returned no published dataset metadata.")
        dataset = self._dataset(data, persistent_id)
        version = data.get("latestVersion") if isinstance(data.get("latestVersion"), dict) else {}
        resources = self._resources(
            version.get("files"),
            dataset.id,
            persistent_id,
            str(version.get("versionNumber") or "") or None,
        )
        status = "compatible_tabular_file_available" if resources else "unsupported"
        return DatasetResourceListing(
            dataset=dataset,
            resources=resources,
            status=status,
            warnings=[] if resources else ["No public CSV or TSV files were found."],
        )

    def download(self, dataset_id: str, resource_id: str):
        listing = self.list_resources(dataset_id)
        match = next((item for item in listing.resources if item.resource_id == resource_id), None)
        if match is None:
            raise ResourceProviderError("Resource ID is not available for this dataset.")
        payload, content_type = self.downloader.read(str(match.source_url))
        dataframe = parse_tabular(payload, match.filename, content_type)
        return listing.dataset, match.model_copy(update={"status": "parsed", "accessible": True}), dataframe

    def _get_json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        _safe_https_url(url, self.allowed_hosts)
        try:
            response = self.client.get(url, params=params, follow_redirects=False)
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            raise ResourceProviderError(f"Dataverse metadata request failed: {error}") from error
        if not isinstance(payload, dict):
            raise ResourceProviderError("Dataverse returned an invalid metadata response.")
        return payload

    @classmethod
    def _dataset(cls, data: dict[str, Any], persistent_id: str) -> DatasetRecord:
        metadata = data.get("latestVersion", {}).get("metadata", {}) if isinstance(data.get("latestVersion"), dict) else {}
        title = metadata.get("title") or data.get("name") or persistent_id
        return DatasetRecord(
            id=f"dataverse:{persistent_id}",
            source=cls.source,
            source_id=persistent_id,
            title=str(title),
            description=metadata.get("description"),
            landing_page_url=f"https://dataverse.harvard.edu/dataset.xhtml?persistentId={persistent_id}",
            subjects=[
                str(subject.get("subject"))
                for subject in metadata.get("subjects", [])
                if isinstance(subject, dict) and subject.get("subject")
            ],
            doi=persistent_id if persistent_id.lower().startswith("doi:") else metadata.get("alternativeURL"),
        )

    @classmethod
    def _resources(
        cls,
        files: object,
        dataset_id: str,
        persistent_id: str,
        version: str | None,
    ) -> list[DatasetResource]:
        if not isinstance(files, list):
            return []
        resources: list[DatasetResource] = []
        for entry in files:
            data_file = entry.get("dataFile") if isinstance(entry, dict) else None
            if not isinstance(data_file, dict) or data_file.get("restricted"):
                continue
            file_id = data_file.get("id")
            filename = data_file.get("filename") or data_file.get("label")
            if not isinstance(file_id, int) or not isinstance(filename, str):
                continue
            file_format = PurePosixPath(filename).suffix.lower().lstrip(".")
            if file_format not in SUPPORTED_FORMATS:
                continue
            normalized_format = "tsv" if file_format == "tab" else file_format
            try:
                resources.append(
                    DatasetResource(
                        resource_id=f"dataverse:file:{file_id}",
                        dataset_id=dataset_id,
                        filename=filename,
                        format=normalized_format,
                        size_bytes=data_file.get("filesize"),
                        version=version,
                        source_url=f"https://dataverse.harvard.edu/api/access/datafile/{file_id}",
                        status="compatible_tabular_file",
                    )
                )
            except ValidationError:
                continue
        return resources

    @staticmethod
    def _source_id(dataset_id: str, prefix: str) -> str:
        expected = f"{prefix}:"
        if not dataset_id.startswith(expected) or len(dataset_id) == len(expected):
            raise ValueError(f"Dataset ID must use the verified {prefix}:<identifier> format.")
        return dataset_id[len(expected):]


class ZenodoAnalysisProvider:
    source = "Zenodo"

    def __init__(
        self,
        client: httpx.Client | None = None,
        api_url: str = "https://zenodo.org/api/records/",
    ) -> None:
        self.client = client or httpx.Client(timeout=settings.external_request_timeout_seconds)
        self.api_url = api_url.rstrip("/") + "/"
        self.allowed_hosts = PROVIDER_HOSTS["zenodo"]
        self.downloader = BoundedDownloader(self.client, self.allowed_hosts)

    def list_resources(self, dataset_id: str) -> DatasetResourceListing:
        record_id = self._source_id(dataset_id, "zenodo")
        _safe_https_url(self.api_url, self.allowed_hosts)
        try:
            response = self.client.get(f"{self.api_url}{record_id}", follow_redirects=False)
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            raise ResourceProviderError(f"Zenodo metadata request failed: {error}") from error
        if not isinstance(payload, dict) or payload.get("is_published") is False:
            raise ResourceProviderError("Zenodo record is not a verified published record.")
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        title = metadata.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ResourceProviderError("Zenodo record has no verified title.")
        dataset = DatasetRecord(
            id=f"zenodo:{record_id}",
            source=self.source,
            source_id=record_id,
            title=title,
            description=metadata.get("description"),
            landing_page_url=(payload.get("links") or {}).get("html") or (payload.get("links") or {}).get("self_html"),
            doi=metadata.get("doi"),
            license=self._license(metadata.get("license")),
            subjects=self._subjects(metadata.get("subjects")),
        )
        record_version = str(
            payload.get("version") or metadata.get("version") or ""
        ) or None
        resources = self._resources(
            payload.get("files"), dataset.id, record_id, record_version
        )
        return DatasetResourceListing(
            dataset=dataset,
            resources=resources,
            status="compatible_tabular_file_available" if resources else "unsupported",
            warnings=[] if resources else ["No public CSV or TSV files were found."],
        )

    def download(self, dataset_id: str, resource_id: str):
        listing = self.list_resources(dataset_id)
        match = next((item for item in listing.resources if item.resource_id == resource_id), None)
        if match is None:
            raise ResourceProviderError("Resource ID is not available for this dataset.")
        payload, content_type = self.downloader.read(str(match.source_url))
        dataframe = parse_tabular(payload, match.filename, content_type)
        return listing.dataset, match.model_copy(update={"status": "parsed", "accessible": True}), dataframe

    @classmethod
    def _resources(
        cls,
        files: object,
        dataset_id: str,
        record_id: str,
        version: str | None,
    ) -> list[DatasetResource]:
        if not isinstance(files, list):
            return []
        resources: list[DatasetResource] = []
        for entry in files:
            if not isinstance(entry, dict) or entry.get("checksum") is None and entry.get("key") is None:
                continue
            filename = entry.get("key") or entry.get("filename")
            links = entry.get("links") if isinstance(entry.get("links"), dict) else {}
            url = links.get("self")
            if not isinstance(filename, str) or not isinstance(url, str):
                continue
            try:
                _safe_https_url(url, PROVIDER_HOSTS["zenodo"])
            except SecureDownloadError:
                continue
            file_format = PurePosixPath(filename).suffix.lower().lstrip(".")
            if file_format not in SUPPORTED_FORMATS:
                continue
            normalized_format = "tsv" if file_format == "tab" else file_format
            try:
                resources.append(
                    DatasetResource(
                        resource_id=f"zenodo:file:{record_id}:{filename}",
                        dataset_id=dataset_id,
                        filename=filename,
                        format=normalized_format,
                        size_bytes=entry.get("size"),
                        checksum=entry.get("checksum"),
                        version=version,
                        source_url=url,
                        status="compatible_tabular_file",
                    )
                )
            except ValidationError:
                continue
        return resources

    @staticmethod
    def _source_id(dataset_id: str, prefix: str) -> str:
        expected = f"{prefix}:"
        if not dataset_id.startswith(expected) or len(dataset_id) == len(expected):
            raise ValueError(f"Dataset ID must use the verified {prefix}:<record-id> format.")
        return dataset_id[len(expected):]

    @staticmethod
    def _subjects(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [
            str(item.get("term"))
            for item in value
            if isinstance(item, dict) and item.get("term")
        ]

    @staticmethod
    def _license(value: object) -> str | None:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return value.get("id") or value.get("title")
        return None


def provider_for_dataset(
    dataset_id: str,
    dataverse: HarvardDataverseAnalysisProvider,
    zenodo: ZenodoAnalysisProvider,
) -> ResourceProvider:
    if dataset_id.startswith("dataverse:"):
        return dataverse
    if dataset_id.startswith("zenodo:"):
        return zenodo
    raise ValueError("Source-neutral analysis supports dataverse: and zenodo: dataset IDs.")
