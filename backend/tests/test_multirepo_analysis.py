from __future__ import annotations

from contextlib import contextmanager

import pandas as pd
import pytest

from app.analysis.source_providers import (
    DataverseAnalysisProvider,
    SafeRepositoryClient,
    SourceProviderError,
    ZenodoAnalysisProvider,
)
from app.analysis.source_service import SourceAnalysisService
from app.api.schemas import (
    AnalysisResource,
    DatasetRecord,
    SourceAnalysisRequest,
)


class FakeResponse:
    def __init__(
        self,
        payload: object | None = None,
        *,
        content: bytes | None = None,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content if content is not None else _json(payload)

    def json(self) -> object:
        return _json(self.payload)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_bytes(self):
        yield self.content

    def close(self) -> None:
        return None


def _json(payload: object | None) -> bytes:
    import json

    if payload is None:
        return b""
    return json.dumps(payload).encode()


class RoutingClient:
    def __init__(self, payload: dict, file_content: bytes = b"rain, yield\n1,2\n2,3\n") -> None:
        self.payload = payload
        self.file_content = file_content
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        if "datafile" in url or "/api/files/" in url or url.endswith((".csv", ".tsv")):
            return FakeResponse(
                content=self.file_content,
                headers={"content-type": "text/csv"},
            )
        return FakeResponse(self.payload)

    @contextmanager
    def stream(self, method: str, url: str, **kwargs):
        response = self.get(url, **kwargs)
        yield response


def dataverse_payload(files: list[dict]) -> dict:
    return {
        "data": {
            "title": "Rainfall observations",
            "description": "Public observations.",
            "persistentUrl": "https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.5072/FK2/ABC",
            "subject": ["Earth Science"],
            "latestVersion": {
                "versionNumber": 2,
                "files": files,
            },
        }
    }


def dataverse_file(file_id: int, filename: str, *, restricted: bool = False) -> dict:
    content_type = (
        "text/csv"
        if filename.endswith(".csv")
        else "text/tab-separated-values"
        if filename.endswith((".tsv", ".tab"))
        else "application/pdf"
    )
    return {
        "restricted": restricted,
        "dataFile": {
            "id": file_id,
            "filename": filename,
            "contentType": content_type,
            "filesize": 20,
            "checksum": {"value": "sha256:abc"},
        },
    }


def test_dataverse_lists_public_csv_and_tsv_but_excludes_restricted_files() -> None:
    client = RoutingClient(
        dataverse_payload(
            [
                dataverse_file(11, "observations.csv"),
                dataverse_file(12, "observations.tsv"),
                dataverse_file(13, "private.csv", restricted=True),
                dataverse_file(14, "notes.pdf"),
            ]
        )
    )
    provider = DataverseAnalysisProvider(client=client, resolve_host=False)

    dataset = provider.resolve("dataverse:doi:10.5072/FK2/ABC")
    resources = provider.resources(dataset)

    assert dataset.id == "dataverse:doi:10.5072/FK2/ABC"
    assert [resource.resource_id for resource in resources] == [
        "dataverse-file:11",
        "dataverse-file:12",
    ]
    assert resources[1].format == "tsv"
    assert resources[0].version == "2"
    assert provider.download(dataset, resources[0]).shape == (2, 2)


def test_zenodo_lists_public_csv_and_preserves_provenance() -> None:
    payload = {
        "id": 123,
        "links": {"html": "https://zenodo.org/records/123"},
        "metadata": {
            "upload_type": "dataset",
            "title": "Rainfall observations",
            "description": "Public observations.",
            "doi": "10.5281/zenodo.123",
            "version": "1.2",
            "license": {"id": "cc-by-4.0"},
        },
        "files": [
            {
                "key": "observations.csv",
                "size": 20,
                "checksum": "md5:abc",
                "mimetype": "text/csv",
                "links": {"self": "https://zenodo.org/api/files/abc/observations.csv"},
            },
            {
                "key": "paper.pdf",
                "size": 20,
                "mimetype": "application/pdf",
                "links": {"self": "https://zenodo.org/api/files/abc/paper.pdf"},
            },
        ],
    }
    provider = ZenodoAnalysisProvider(
        client=RoutingClient(payload), resolve_host=False
    )

    dataset = provider.resolve("zenodo:123")
    resources = provider.resources(dataset)

    assert dataset.doi == "10.5281/zenodo.123"
    assert dataset.license == "cc-by-4.0"
    assert len(resources) == 1
    assert resources[0].checksum == "md5:abc"
    assert resources[0].version == "1.2"


def test_no_supported_dataverse_files_is_explicit() -> None:
    client = RoutingClient(dataverse_payload([dataverse_file(14, "notes.pdf")]))
    provider = DataverseAnalysisProvider(client=client, resolve_host=False)

    dataset = provider.resolve("dataverse:doi:10.5072/FK2/ABC")

    assert provider.resources(dataset) == []


def test_source_service_requires_explicit_selection_for_multiple_resources() -> None:
    class FakeProvider:
        source = "Harvard Dataverse"

        def resolve(self, dataset_id: str) -> DatasetRecord:
            return DatasetRecord(
                id=dataset_id,
                source=self.source,
                source_id="doi:10.5072/FK2/ABC",
                title="Observations",
                landing_page_url="https://dataverse.harvard.edu/dataset.xhtml?id=1",
            )

        def resources(self, dataset: DatasetRecord) -> list[AnalysisResource]:
            return [
                AnalysisResource(
                    resource_id="dataverse-file:1",
                    dataset_id=dataset.id,
                    source=self.source,
                    filename="a.csv",
                    format="csv",
                    source_url="https://dataverse.harvard.edu/api/access/datafile/1",
                    eligible=True,
                    eligibility_reason="Public CSV or TSV file.",
                ),
                AnalysisResource(
                    resource_id="dataverse-file:2",
                    dataset_id=dataset.id,
                    source=self.source,
                    filename="b.tsv",
                    format="tsv",
                    source_url="https://dataverse.harvard.edu/api/access/datafile/2",
                    eligible=True,
                    eligibility_reason="Public CSV or TSV file.",
                ),
            ]

        def download(self, dataset, resource):
            raise AssertionError("No resource should be downloaded before selection.")

    response = SourceAnalysisService([FakeProvider()]).analyze(
        SourceAnalysisRequest(
            dataset_id="dataverse:doi:10.5072/FK2/ABC",
            research_question="Does rainfall relate to yield?",
        )
    )

    assert response.status == "compatible_tabular_available"
    assert response.resource is None
    assert "select one explicitly" in response.warnings[0]


def test_safe_download_parses_csv_and_tsv() -> None:
    client = RoutingClient({}, file_content=b"rain\t yield\n1\t2\n")
    safe = SafeRepositoryClient(client, {"zenodo.org"}, resolve_host=False)

    dataframe = safe.download("https://zenodo.org/data.tsv", "tsv")

    assert list(dataframe.columns) == ["rain", " yield"]
    assert dataframe.iloc[0, 1] == 2


@pytest.mark.parametrize(
    "url",
    [
        "http://zenodo.org/data.csv",
        "https://localhost/data.csv",
        "https://127.0.0.1/data.csv",
        "https://evil.example/data.csv",
    ],
)
def test_safe_download_rejects_unapproved_destinations(url: str) -> None:
    safe = SafeRepositoryClient(RoutingClient({}), {"zenodo.org"}, resolve_host=False)

    with pytest.raises(SourceProviderError, match="approved HTTPS"):
        safe.download(url, "csv")


def test_safe_download_rejects_unsafe_redirect() -> None:
    class RedirectClient(RoutingClient):
        def __init__(self):
            super().__init__({})
            self.redirected = False

        def get(self, url: str, **kwargs):
            if not self.redirected:
                self.redirected = True
                return FakeResponse(
                    status_code=302,
                    headers={"location": "https://localhost/private.csv"},
                )
            return super().get(url, **kwargs)

    safe = SafeRepositoryClient(RedirectClient(), {"zenodo.org"}, resolve_host=False)

    with pytest.raises(SourceProviderError, match="approved HTTPS"):
        safe.download("https://zenodo.org/data.csv", "csv")


def test_safe_download_rejects_oversized_and_invalid_tables(monkeypatch) -> None:
    monkeypatch.setattr("app.analysis.source_providers.settings.analysis_max_download_bytes", 4)
    oversized = SafeRepositoryClient(
        RoutingClient({}, file_content=b"rain,yield\n1,2\n"),
        {"zenodo.org"},
        resolve_host=False,
    )
    with pytest.raises(SourceProviderError, match="size limit"):
        oversized.download("https://zenodo.org/data.csv", "csv")

    invalid = SafeRepositoryClient(
        RoutingClient({}, file_content=b"\x00\x01\x02"),
        {"zenodo.org"},
        resolve_host=False,
    )
    with pytest.raises(SourceProviderError, match="text table"):
        invalid.download("https://zenodo.org/data.csv", "csv")


def test_safe_download_rejects_invalid_csv_empty_files_and_timeouts() -> None:
    invalid = SafeRepositoryClient(
        RoutingClient({}, file_content=b"\xff\xfe\x00"),
        {"zenodo.org"},
        resolve_host=False,
    )
    with pytest.raises(SourceProviderError, match="text table"):
        invalid.download("https://zenodo.org/data.csv", "csv")

    empty = SafeRepositoryClient(
        RoutingClient({}, file_content=b""),
        {"zenodo.org"},
        resolve_host=False,
    )
    with pytest.raises(SourceProviderError, match="empty"):
        empty.download("https://zenodo.org/data.csv", "csv")

    class TimeoutClient(RoutingClient):
        def get(self, url: str, **kwargs):
            import httpx

            raise httpx.ReadTimeout("timed out")

    timed_out = SafeRepositoryClient(
        TimeoutClient({}), {"zenodo.org"}, resolve_host=False
    )
    with pytest.raises(SourceProviderError, match="timed out"):
        timed_out.get_json("https://zenodo.org/api/records/1")


def test_zenodo_unavailable_file_is_not_analyzed() -> None:
    class UnavailableClient(RoutingClient):
        def get(self, url: str, **kwargs):
            if "/api/files/" in url:
                return FakeResponse(status_code=404)
            return super().get(url, **kwargs)

    payload = {
        "id": 123,
        "links": {"html": "https://zenodo.org/records/123"},
        "metadata": {"upload_type": "dataset", "title": "Observations"},
        "files": [
            {
                "key": "observations.csv",
                "mimetype": "text/csv",
                "links": {"self": "https://zenodo.org/api/files/abc/observations.csv"},
            }
        ],
    }
    provider = ZenodoAnalysisProvider(
        client=UnavailableClient(payload), resolve_host=False
    )
    dataset = provider.resolve("zenodo:123")
    resource = provider.resources(dataset)[0]

    with pytest.raises(SourceProviderError, match="could not be accessed"):
        provider.download(dataset, resource)


def test_source_analysis_preserves_profile_when_gemini_is_unavailable() -> None:
    class FakeProvider:
        source = "Zenodo"

        def resolve(self, dataset_id: str) -> DatasetRecord:
            return DatasetRecord(
                id=dataset_id,
                source=self.source,
                source_id="123",
                title="Observations",
                landing_page_url="https://zenodo.org/records/123",
                doi="10.5281/zenodo.123",
            )

        def resources(self, dataset: DatasetRecord) -> list[AnalysisResource]:
            return [
                AnalysisResource(
                    resource_id="zenodo-file:observations.csv",
                    dataset_id=dataset.id,
                    source=self.source,
                    filename="observations.csv",
                    format="csv",
                    source_url="https://zenodo.org/api/files/abc/observations.csv",
                    eligible=True,
                    eligibility_reason="Public CSV or TSV file.",
                )
            ]

        def download(self, dataset, resource):
            return pd.DataFrame({"rain": [1, None, 3], "yield": [2, 4, 6]})

    class UnavailableGemini:
        def interpret(self, question):
            raise RuntimeError("Gemini unavailable")

        def assess_suitability(self, *args):
            raise RuntimeError("Gemini unavailable")

    response = SourceAnalysisService(
        [FakeProvider()], gemini=UnavailableGemini()
    ).analyze(
        SourceAnalysisRequest(
            dataset_id="zenodo:123",
            resource_id="zenodo-file:observations.csv",
            research_question="Does rainfall relate to yield?",
        )
    )

    assert response.status == "profile_available"
    assert response.profile is not None
    assert response.profile.row_count == 3
    assert response.profile.columns[0].missing_count == 1
    assert response.ai_assessment_status == "unavailable"
    assert response.provenance.doi == "10.5281/zenodo.123"


@pytest.mark.parametrize("dataset_id", ["", "https://evil.example/file.csv", "uci:320", "zenodo:not-an-id"])
def test_source_analysis_rejects_invalid_or_unsupported_ids(dataset_id: str) -> None:
    service = SourceAnalysisService([])

    with pytest.raises(ValueError):
        service.list_resources(dataset_id)
