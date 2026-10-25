from __future__ import annotations

import ipaddress
import json
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import PurePosixPath
from tempfile import SpooledTemporaryFile
from typing import Any, Protocol
from urllib.parse import urljoin, urlparse

import httpx
import pandas as pd

from app.api.schemas import AnalysisResource, DatasetRecord, DatasetVariable
from app.config import settings
from app.discovery.uci import UCIRepositoryService, dataset_record_from_uci


class SourceProviderError(RuntimeError):
    """Raised when a recognized repository cannot provide a safe resource."""


@dataclass(frozen=True)
class DownloadedTabular:
    resource: AnalysisResource
    dataframe: pd.DataFrame


class SourceAnalysisProvider(Protocol):
    source: str

    def resolve(self, dataset_id: str) -> DatasetRecord:
        ...

    def resources(self, dataset: DatasetRecord) -> list[AnalysisResource]:
        ...

    def download(
        self, dataset: DatasetRecord, resource: AnalysisResource
    ) -> pd.DataFrame:
        ...


class UCIAnalysisProvider:
    """Adapter for the existing structured UCI retrieval service."""

    source = "UCI Machine Learning Repository"

    def __init__(self, repository: UCIRepositoryService | None = None) -> None:
        self.repository = repository or UCIRepositoryService(
            catalog_ttl=settings.uci_catalog_ttl_seconds
        )

    def resolve(self, dataset_id: str) -> DatasetRecord:
        numeric_id = self._numeric_id(dataset_id)
        return dataset_record_from_uci(self.repository.get_metadata(numeric_id))

    def resources(self, dataset: DatasetRecord) -> list[AnalysisResource]:
        return [
            AnalysisResource(
                resource_id=f"uci-dataset:{dataset.source_id}",
                dataset_id=dataset.id,
                source=self.source,
                filename=f"{dataset.source_id}.csv",
                format="csv",
                version=None,
                source_url=dataset.landing_page_url,
                eligible=dataset.data_available is not False,
                eligibility_reason="UCI SDK verified tabular dataset."
                if dataset.data_available is not False
                else "UCI metadata reports that data is unavailable.",
            )
        ]

    def download(self, dataset: DatasetRecord, resource: AnalysisResource) -> pd.DataFrame:
        expected = f"uci-dataset:{dataset.source_id}"
        if resource.resource_id != expected:
            raise SourceProviderError("Resource ID is invalid for this provider.")
        _, dataframe, _ = self.repository.fetch_dataset(self._numeric_id(dataset.id))
        return dataframe

    @staticmethod
    def _numeric_id(dataset_id: str) -> int:
        if not dataset_id.startswith("uci:"):
            raise SourceProviderError("Dataset ID must use the verified uci:<integer> format.")
        try:
            numeric_id = int(dataset_id[4:])
        except ValueError as error:
            raise SourceProviderError("Dataset ID must use the verified uci:<integer> format.") from error
        if numeric_id <= 0:
            raise SourceProviderError("Dataset ID must use the verified uci:<integer> format.")
        return numeric_id


class SafeRepositoryClient:
    """Bounded HTTP access for fixed, provider-approved HTTPS hosts."""

    def __init__(
        self,
        client: Any,
        allowed_hosts: set[str],
        *,
        resolve_host: bool = True,
    ) -> None:
        self.client = client
        self.allowed_hosts = allowed_hosts
        self.resolve_host = resolve_host

    def get_json(self, url: str, **kwargs: Any) -> dict[str, Any]:
        response = self._request(url, **kwargs)
        self._raise_for_status(response)
        content = self._response_content(response)
        if len(content) > settings.analysis_max_metadata_bytes:
            raise SourceProviderError("Repository metadata response exceeds the size limit.")
        try:
            payload = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SourceProviderError("Repository returned invalid JSON metadata.") from error
        if not isinstance(payload, dict):
            raise SourceProviderError("Repository returned an unexpected metadata response.")
        return payload

    def download(self, url: str, format_name: str) -> pd.DataFrame:
        with self._stream_response(url) as response:
            headers = getattr(response, "headers", {}) or {}
            content_length = self._content_length(headers)
            if content_length is not None and content_length > settings.analysis_max_download_bytes:
                raise SourceProviderError("The selected file exceeds the download size limit.")
            content_type = str(headers.get("content-type", "")).lower()
            if content_type and any(
                blocked in content_type
                for blocked in ("application/zip", "application/pdf", "application/octet-stream")
            ):
                raise SourceProviderError("The selected resource is not a supported text table.")
            self._raise_for_status(response)
            with SpooledTemporaryFile(max_size=settings.analysis_max_download_bytes, mode="w+b") as stream:
                written = 0
                for chunk in self._iter_bytes(response):
                    written += len(chunk)
                    if written > settings.analysis_max_download_bytes:
                        raise SourceProviderError("The selected file exceeds the download size limit.")
                    if b"\x00" in chunk:
                        raise SourceProviderError("The selected resource is not a text table.")
                    stream.write(chunk)
                if written == 0:
                    raise SourceProviderError("The selected file is empty.")
                stream.seek(0)
                try:
                    dataframe = pd.read_csv(
                        stream,
                        sep="\t" if format_name == "tsv" else ",",
                        encoding="utf-8",
                    )
                except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as error:
                    raise SourceProviderError("The selected file is not a valid CSV or TSV table.") from error
        if dataframe.empty or len(dataframe.columns) == 0:
            raise SourceProviderError("The selected table is empty.")
        if len(dataframe) > settings.analysis_max_rows:
            raise SourceProviderError("The selected table exceeds the row limit.")
        if len(dataframe.columns) > settings.analysis_max_columns:
            raise SourceProviderError("The selected table exceeds the column limit.")
        return dataframe

    @contextmanager
    def _stream_response(self, url: str):
        current = url
        for _ in range(settings.analysis_max_redirects + 1):
            self._validate_url(current)
            try:
                stream = getattr(self.client, "stream", None)
                if callable(stream):
                    context = stream("GET", current, follow_redirects=False)
                else:
                    context = _ResponseContext(self.client.get(current, follow_redirects=False))
                with context as response:
                    if getattr(response, "status_code", 0) in {301, 302, 303, 307, 308}:
                        location = (getattr(response, "headers", {}) or {}).get("location")
                        if not location:
                            raise SourceProviderError("The repository returned an unsafe redirect.")
                        current = urljoin(current, location)
                        continue
                    yield response
                    return
            except (httpx.TimeoutException, TimeoutError) as error:
                raise SourceProviderError("The repository request timed out.") from error
            except SourceProviderError:
                raise
            except Exception as error:
                raise SourceProviderError("The repository request failed.") from error
        raise SourceProviderError("The repository returned too many redirects.")

    def _request(self, url: str, **kwargs: Any) -> Any:
        current = url
        for _ in range(settings.analysis_max_redirects + 1):
            self._validate_url(current)
            request_kwargs = dict(kwargs)
            request_kwargs.setdefault("follow_redirects", False)
            try:
                response = self.client.get(current, **request_kwargs)
            except (httpx.TimeoutException, TimeoutError) as error:
                raise SourceProviderError("The repository request timed out.") from error
            except Exception as error:
                raise SourceProviderError("The repository request failed.") from error
            if getattr(response, "status_code", 0) in {301, 302, 303, 307, 308}:
                location = (getattr(response, "headers", {}) or {}).get("location")
                if not location:
                    raise SourceProviderError("The repository returned an unsafe redirect.")
                current = urljoin(current, location)
                continue
            return response
        raise SourceProviderError("The repository returned too many redirects.")

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or not hostname or hostname not in self.allowed_hosts:
            raise SourceProviderError("The repository URL is not an approved HTTPS destination.")
        if parsed.username or parsed.password or (parsed.port not in (None, 443)):
            raise SourceProviderError("The repository URL contains an unsafe authority.")
        if self.resolve_host:
            try:
                addresses = {
                    result[4][0]
                    for result in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
                }
            except OSError as error:
                raise SourceProviderError("The repository host could not be resolved.") from error
            if not addresses or any(self._is_private_address(address) for address in addresses):
                raise SourceProviderError("The repository host resolves to a private or local network.")

    @staticmethod
    def _is_private_address(address: str) -> bool:
        parsed = ipaddress.ip_address(address)
        return (
            parsed.is_private
            or parsed.is_loopback
            or parsed.is_link_local
            or parsed.is_reserved
            or parsed.is_multicast
            or parsed.is_unspecified
        )

    @staticmethod
    def _response_content(response: Any) -> bytes:
        content = getattr(response, "content", None)
        if content is not None:
            return bytes(content)
        text = getattr(response, "text", None)
        return str(text).encode("utf-8") if text is not None else b""

    @staticmethod
    def _content_length(headers: Any) -> int | None:
        try:
            value = headers.get("content-length")
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            raise SourceProviderError("The repository returned an invalid content length.")

    @staticmethod
    def _raise_for_status(response: Any) -> None:
        try:
            response.raise_for_status()
        except Exception as error:
            raise SourceProviderError("The repository file could not be accessed.") from error

    @staticmethod
    def _iter_bytes(response: Any) -> Iterator[bytes]:
        iter_bytes = getattr(response, "iter_bytes", None)
        if callable(iter_bytes):
            yield from iter_bytes()
            return
        content = getattr(response, "content", b"")
        yield bytes(content)


class _ResponseContext:
    def __init__(self, response: Any) -> None:
        self.response = response

    def __enter__(self) -> Any:
        return self.response

    def __exit__(self, *_args: Any) -> None:
        close = getattr(self.response, "close", None)
        if callable(close):
            close()


class DataverseAnalysisProvider:
    source = "Harvard Dataverse"
    _allowed_hosts = {"dataverse.harvard.edu"}
    _metadata_url = "https://dataverse.harvard.edu/api/datasets/:persistentId/"
    _file_url = "https://dataverse.harvard.edu/api/access/datafile/"

    def __init__(self, client: httpx.Client | None = None, *, resolve_host: bool = True) -> None:
        self.client = SafeRepositoryClient(
            client or httpx.Client(
                timeout=settings.external_request_timeout_seconds,
                follow_redirects=False,
            ),
            self._allowed_hosts,
            resolve_host=resolve_host,
        )

    def resolve(self, dataset_id: str) -> DatasetRecord:
        source_id = self._source_id(dataset_id)
        payload = self.client.get_json(self._metadata_url, params={"persistentId": source_id})
        data = payload.get("data")
        if not isinstance(data, dict):
            raise SourceProviderError("Dataverse returned no published dataset metadata.")
        latest = data.get("latestVersion")
        if not isinstance(latest, dict):
            raise SourceProviderError("Dataverse returned no published dataset version.")
        dataset = DatasetRecord(
            id=f"dataverse:{source_id}",
            source=self.source,
            source_id=source_id,
            title=str(data.get("name") or data.get("title") or "").strip(),
            description=self._text(data.get("description")),
            landing_page_url=self._text(
                data.get("persistentUrl")
                or f"https://dataverse.harvard.edu/dataset.xhtml?persistentId={source_id}"
            ),
            variables=self._variables(latest.get("metadataBlocks")),
            subjects=self._subjects(data.get("subject")),
            doi=source_id if source_id.lower().startswith("doi:") else self._text(data.get("datasetVersionId")),
            data_available=bool(latest.get("files")),
        )
        return dataset

    def resources(self, dataset: DatasetRecord) -> list[AnalysisResource]:
        payload = self.client.get_json(self._metadata_url, params={"persistentId": dataset.source_id})
        data = payload.get("data")
        latest = data.get("latestVersion") if isinstance(data, dict) else None
        files = latest.get("files") if isinstance(latest, dict) else None
        if not isinstance(files, list):
            return []
        version = str(latest.get("versionNumber")) if latest.get("versionNumber") is not None else None
        resources: list[AnalysisResource] = []
        for item in files:
            data_file = item.get("dataFile") if isinstance(item, dict) else None
            if not isinstance(data_file, dict):
                continue
            file_id = data_file.get("id")
            filename = self._text(data_file.get("filename"))
            if file_id is None or not filename:
                continue
            format_name = self._format(filename, data_file.get("contentType"))
            restricted = bool(item.get("restricted") or data_file.get("restricted"))
            size_bytes = self._int(data_file.get("filesize"))
            eligible = (
                format_name is not None
                and not restricted
                and (
                    size_bytes is None
                    or size_bytes <= settings.analysis_max_download_bytes
                )
            )
            if not eligible:
                continue
            reason = (
                "Public CSV or TSV file."
                if eligible
                else "Restricted or unsupported file format."
            )
            resources.append(
                AnalysisResource(
                    resource_id=f"dataverse-file:{file_id}",
                    dataset_id=dataset.id,
                    source=self.source,
                    filename=filename,
                    format=format_name,
                    mime_type=self._text(data_file.get("contentType")),
                    size_bytes=size_bytes,
                    checksum=self._text(data_file.get("checksum", {}).get("value"))
                    if isinstance(data_file.get("checksum"), dict)
                    else None,
                    version=version,
                    source_url=f"{self._file_url}{file_id}",
                    eligible=eligible,
                    eligibility_reason=reason,
                )
            )
        return resources

    def download(self, dataset: DatasetRecord, resource: AnalysisResource) -> pd.DataFrame:
        file_id = self._resource_id(resource.resource_id, "dataverse-file:")
        return self.client.download(f"{self._file_url}{file_id}", resource.format)

    @staticmethod
    def _source_id(dataset_id: str) -> str:
        if not dataset_id.startswith("dataverse:") or len(dataset_id) <= len("dataverse:"):
            raise SourceProviderError("Dataset ID must use the verified dataverse:<persistent-id> format.")
        return dataset_id.split(":", 1)[1]

    @staticmethod
    def _resource_id(resource_id: str, prefix: str) -> str:
        if not resource_id.startswith(prefix) or len(resource_id) == len(prefix):
            raise SourceProviderError("Resource ID is invalid for this provider.")
        return resource_id[len(prefix):]

    @staticmethod
    def _format(filename: str, content_type: object) -> str | None:
        suffix = PurePosixPath(filename).suffix.lower()
        content = (
            ""
            if content_type is None
            else str(content_type).lower().split(";", 1)[0].strip()
        )
        if content:
            if content in {"text/csv", "text/comma-separated-values"}:
                return "csv"
            if content in {"text/tab-separated-values", "text/tsv"}:
                return "tsv"
            return None
        if suffix == ".csv":
            return "csv"
        if suffix in {".tsv", ".tab"}:
            return "tsv"
        return None

    @classmethod
    def _variables(cls, blocks: object) -> list[DatasetVariable]:
        return []

    @staticmethod
    def _subjects(value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @staticmethod
    def _text(value: object) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @staticmethod
    def _int(value: object) -> int | None:
        return int(value) if isinstance(value, int) and value >= 0 else None


class ZenodoAnalysisProvider:
    source = "Zenodo"
    _allowed_hosts = {"zenodo.org"}
    _metadata_url = "https://zenodo.org/api/records/"

    def __init__(self, client: httpx.Client | None = None, *, resolve_host: bool = True) -> None:
        self.client = SafeRepositoryClient(
            client or httpx.Client(
                timeout=settings.external_request_timeout_seconds,
                follow_redirects=False,
            ),
            self._allowed_hosts,
            resolve_host=resolve_host,
        )

    def resolve(self, dataset_id: str) -> DatasetRecord:
        source_id = self._source_id(dataset_id)
        payload = self.client.get_json(f"{self._metadata_url}{source_id}")
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict) or str(metadata.get("upload_type", "dataset")).lower() != "dataset":
            raise SourceProviderError("Zenodo record is not a published dataset.")
        landing = (payload.get("links") or {}).get("html") or (payload.get("links") or {}).get("self_html")
        return DatasetRecord(
            id=f"zenodo:{source_id}",
            source=self.source,
            source_id=source_id,
            title=str(metadata.get("title") or "").strip(),
            description=self._text(metadata.get("description")),
            landing_page_url=landing,
            subjects=self._subjects(metadata.get("subjects")),
            doi=self._text(metadata.get("doi")),
            license=self._license(metadata.get("license")),
            data_available=bool(payload.get("files")),
        )

    def resources(self, dataset: DatasetRecord) -> list[AnalysisResource]:
        payload = self.client.get_json(f"{self._metadata_url}{dataset.source_id}")
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        version = self._text(metadata.get("version"))
        resources: list[AnalysisResource] = []
        files = payload.get("files")
        if not isinstance(files, list):
            return resources
        for item in files:
            if not isinstance(item, dict):
                continue
            filename = self._text(item.get("key") or item.get("filename"))
            links = item.get("links") if isinstance(item.get("links"), dict) else {}
            url = self._text(links.get("self"))
            if not filename or not url:
                continue
            format_name = self._format(filename, item.get("mimetype"))
            size_bytes = self._int(item.get("size"))
            eligible = (
                format_name is not None
                and (
                    size_bytes is None
                    or size_bytes <= settings.analysis_max_download_bytes
                )
            )
            if not eligible:
                continue
            resources.append(
                AnalysisResource(
                    resource_id=f"zenodo-file:{filename}",
                    dataset_id=dataset.id,
                    source=self.source,
                    filename=filename,
                    format=format_name,
                    mime_type=self._text(item.get("mimetype")),
                    size_bytes=size_bytes,
                    checksum=self._text(item.get("checksum")),
                    version=version,
                    source_url=url,
                    eligible=eligible,
                    eligibility_reason="Public CSV or TSV file." if eligible else "Unsupported file format.",
                )
            )
        return resources

    def download(self, dataset: DatasetRecord, resource: AnalysisResource) -> pd.DataFrame:
        if not resource.resource_id.startswith("zenodo-file:"):
            raise SourceProviderError("Resource ID is invalid for this provider.")
        return self.client.download(str(resource.source_url), resource.format)

    @staticmethod
    def _source_id(dataset_id: str) -> str:
        if not dataset_id.startswith("zenodo:") or not dataset_id[7:].isdigit():
            raise SourceProviderError("Dataset ID must use the verified zenodo:<record-id> format.")
        return dataset_id[7:]

    @staticmethod
    def _format(filename: str, content_type: object) -> str | None:
        suffix = PurePosixPath(filename).suffix.lower()
        content = "" if content_type is None else str(content_type).lower()
        if content:
            normalized = content.split(";", 1)[0].strip()
            if normalized in {"text/csv", "text/comma-separated-values"}:
                return "csv"
            if normalized in {"text/tab-separated-values", "text/tsv"}:
                return "tsv"
            return None
        if suffix == ".csv":
            return "csv"
        if suffix in {".tsv", ".tab"}:
            return "tsv"
        return None

    @staticmethod
    def _text(value: object) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @classmethod
    def _subjects(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [
            text
            for item in value
            if (text := cls._text(item.get("term") if isinstance(item, dict) else item))
        ]

    @staticmethod
    def _license(value: object) -> str | None:
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, dict):
            return value.get("id") or value.get("title")
        return None

    @staticmethod
    def _int(value: object) -> int | None:
        return int(value) if isinstance(value, int) and value >= 0 else None
