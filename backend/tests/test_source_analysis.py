from __future__ import annotations

import socket

import httpx
import pandas as pd
import pytest

from app.analysis.providers import (
    BoundedDownloader,
    HarvardDataverseAnalysisProvider,
    ResourceProviderError,
    SecureDownloadError,
    ZenodoAnalysisProvider,
    parse_tabular,
)
from app.analysis.service import DatasetAnalysisService
from app.api.schemas import (
    DatasetResourceListing,
    SourceAnalysisRequest,
)


def _allow_test_dns(monkeypatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )


def _transport(responses: dict[str, httpx.Response]):
    def handler(request: httpx.Request) -> httpx.Response:
        response = responses.get(str(request.url))
        if response is None:
            return httpx.Response(404, request=request)
        return response

    return httpx.MockTransport(handler)


def test_dataverse_lists_public_csv_and_tsv_but_excludes_restricted_and_other_files(
    monkeypatch,
) -> None:
    _allow_test_dns(monkeypatch)
    metadata_url = "https://dataverse.harvard.edu/api/datasets/:persistentId?persistentId=doi%3A10.5072%2FFK2%2FABC"
    client = httpx.Client(
        transport=_transport(
            {
                metadata_url: httpx.Response(
                    200,
                    json={
                        "data": {
                            "latestVersion": {
                                "versionNumber": 2,
                                "metadata": {
                                    "title": "Climate observations",
                                    "description": "Observed rainfall.",
                                    "subjects": [{"subject": "Earth Science"}],
                                },
                                "files": [
                                    {
                                        "dataFile": {
                                            "id": 11,
                                            "filename": "observations.csv",
                                            "filesize": 25,
                                            "restricted": False,
                                        }
                                    },
                                    {
                                        "dataFile": {
                                            "id": 12,
                                            "filename": "observations.tsv",
                                            "restricted": False,
                                        }
                                    },
                                    {
                                        "dataFile": {
                                            "id": 13,
                                            "filename": "restricted.csv",
                                            "restricted": True,
                                        }
                                    },
                                    {
                                        "dataFile": {
                                            "id": 14,
                                            "filename": "notes.pdf",
                                            "restricted": False,
                                        }
                                    },
                                ],
                            }
                        }
                    },
                ),
                "https://dataverse.harvard.edu/api/access/datafile/11": httpx.Response(
                    200,
                    headers={"content-type": "text/csv"},
                    content=b"rainfall,yield\n1,4\n2,5\n",
                ),
            }
        )
    )
    provider = HarvardDataverseAnalysisProvider(client=client)

    listing = provider.list_resources("dataverse:doi:10.5072/FK2/ABC")

    assert listing.dataset.id == "dataverse:doi:10.5072/FK2/ABC"
    assert listing.status == "compatible_tabular_file_available"
    assert [resource.resource_id for resource in listing.resources] == [
        "dataverse:file:11",
        "dataverse:file:12",
    ]
    assert listing.resources[0].version == "2"
    dataset, resource, dataframe = provider.download(
        "dataverse:doi:10.5072/FK2/ABC", "dataverse:file:11"
    )
    assert dataset.doi == "doi:10.5072/FK2/ABC"
    assert resource.status == "parsed"
    assert dataframe.shape == (2, 2)


def test_zenodo_lists_only_published_csv_and_preserves_provenance(monkeypatch) -> None:
    _allow_test_dns(monkeypatch)
    url = "https://zenodo.org/api/records/12345"
    client = httpx.Client(
        transport=_transport(
            {
                url: httpx.Response(
                    200,
                    json={
                        "is_published": True,
                        "metadata": {
                            "title": "Rainfall",
                            "description": "Observed rainfall.",
                            "doi": "10.5281/zenodo.12345",
                            "license": {"id": "cc-by-4.0"},
                        },
                        "links": {"html": "https://zenodo.org/records/12345"},
                        "files": [
                            {
                                "key": "rainfall.csv",
                                "size": 20,
                                "checksum": "md5:abc",
                                "links": {
                                    "self": "https://zenodo.org/api/files/abc/rainfall.csv"
                                },
                            },
                            {
                                "key": "paper.pdf",
                                "links": {
                                    "self": "https://zenodo.org/api/files/abc/paper.pdf"
                                },
                            },
                        ],
                    },
                ),
                "https://zenodo.org/api/files/abc/rainfall.csv": httpx.Response(
                    200,
                    headers={"content-type": "text/csv"},
                    content=b"rainfall,yield\n1,4\n2,5\n",
                ),
            }
        )
    )
    provider = ZenodoAnalysisProvider(client=client)
    listing = provider.list_resources("zenodo:12345")

    assert listing.dataset.doi == "10.5281/zenodo.12345"
    assert len(listing.resources) == 1
    assert listing.resources[0].resource_id == "zenodo:file:12345:rainfall.csv"
    assert listing.resources[0].checksum == "md5:abc"
    _, resource, dataframe = provider.download(
        "zenodo:12345", "zenodo:file:12345:rainfall.csv"
    )
    assert resource.status == "parsed"
    assert dataframe.shape == (2, 2)


def test_no_supported_files_is_explicitly_unsupported(monkeypatch) -> None:
    _allow_test_dns(monkeypatch)
    url = "https://zenodo.org/api/records/9"
    client = httpx.Client(
        transport=_transport(
            {
                url: httpx.Response(
                    200,
                    json={
                        "is_published": True,
                        "metadata": {"title": "Paper"},
                        "links": {"html": "https://zenodo.org/records/9"},
                        "files": [{"key": "model.bin", "links": {"self": "https://zenodo.org/files/model.bin"}}],
                    },
                )
            }
        )
    )
    listing = ZenodoAnalysisProvider(client=client).list_resources("zenodo:9")

    assert listing.status == "unsupported"
    assert listing.resources == []
    assert listing.warnings


def test_unavailable_zenodo_record_is_reported(monkeypatch) -> None:
    _allow_test_dns(monkeypatch)
    url = "https://zenodo.org/api/records/404"
    client = httpx.Client(
        transport=_transport({url: httpx.Response(404, json={"message": "not found"})})
    )

    with pytest.raises(ResourceProviderError, match="metadata request failed"):
        ZenodoAnalysisProvider(client=client).list_resources("zenodo:404")


def test_bounded_downloader_rejects_unapproved_hosts_redirects_and_oversized_content(
    monkeypatch,
) -> None:
    _allow_test_dns(monkeypatch)
    downloader = BoundedDownloader(
        httpx.Client(
            transport=_transport(
                {
                    "https://zenodo.org/file.csv": httpx.Response(
                        302, headers={"location": "https://example.com/file.csv"}
                    ),
                }
            )
        ),
        {"zenodo.org"},
        max_bytes=4,
    )

    with pytest.raises(SecureDownloadError, match="approved repository"):
        downloader.read("https://zenodo.org/file.csv")

    with pytest.raises(SecureDownloadError, match="HTTPS"):
        downloader.read("http://127.0.0.1/file.csv")

    oversized = BoundedDownloader(
        httpx.Client(
            transport=_transport(
                {
                    "https://zenodo.org/large.csv": httpx.Response(
                        200,
                        headers={"content-length": "5"},
                        content=b"12345",
                    )
                }
            )
        ),
        {"zenodo.org"},
        max_bytes=4,
    )
    with pytest.raises(SecureDownloadError, match="download limit"):
        oversized.read("https://zenodo.org/large.csv")


@pytest.mark.parametrize(
    ("filename", "payload"),
    [
        ("data.csv", b"a,b\n1,2\n"),
        ("data.tsv", b"a\tb\n1\t2\n"),
    ],
)
def test_parse_supported_tabular_files(filename: str, payload: bytes) -> None:
    dataframe = parse_tabular(payload, filename, "text/plain")
    assert list(dataframe.columns) == ["a", "b"]
    assert dataframe.shape == (1, 2)


def test_parse_rejects_invalid_empty_and_binary_files() -> None:
    with pytest.raises(ResourceProviderError):
        parse_tabular(b'a,b\n"1,2\n', "data.csv", "text/csv")
    with pytest.raises(SecureDownloadError):
        parse_tabular(b"", "data.csv", "text/csv")
    with pytest.raises(Exception, match="Archives"):
        parse_tabular(b"%PDF-1.7", "data.csv", "application/pdf")


class FakeSourceProvider:
    source = "Zenodo"

    def __init__(self, dataframe: pd.DataFrame) -> None:
        self.dataframe = dataframe

    def list_resources(self, dataset_id: str) -> DatasetResourceListing:
        raise AssertionError("listing is not part of this service test")

    def download(self, dataset_id: str, resource_id: str):
        from app.api.schemas import DatasetRecord, DatasetResource

        dataset = DatasetRecord(
            id=dataset_id,
            source=self.source,
            source_id="123",
            title="Rainfall",
            landing_page_url="https://zenodo.org/records/123",
            doi="10.5281/zenodo.123",
        )
        resource = DatasetResource(
            resource_id=resource_id,
            dataset_id=dataset_id,
            filename="rainfall.csv",
            format="csv",
            source_url="https://zenodo.org/files/rainfall.csv",
            status="parsed",
        )
        return dataset, resource, self.dataframe


class GeminiUnavailable:
    def interpret(self, question: str):
        raise RuntimeError("Gemini unavailable")

    def assess_suitability(self, *args, **kwargs):
        raise RuntimeError("Gemini unavailable")


def test_source_analysis_preserves_profile_when_gemini_is_unavailable() -> None:
    provider = FakeSourceProvider(pd.DataFrame({"rainfall": [1, None, 3], "yield": [4, 5, 6]}))
    service = DatasetAnalysisService(
        repository=None,
        gemini=GeminiUnavailable(),
        zenodo_provider=provider,
    )

    response = service.analyze_source(
        SourceAnalysisRequest(
            dataset_id="zenodo:123",
            resource_id="zenodo:file:123:rainfall.csv",
            research_question="Does rainfall relate to crop yield?",
        )
    )

    assert response.data_status == "analyzed"
    assert response.profile is not None
    assert response.profile.row_count == 3
    assert response.ai_assessment_status == "unavailable"
    assert any("AI suitability" in warning for warning in response.warnings)


def test_invalid_provider_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="supports dataverse"):
        from app.analysis.providers import provider_for_dataset

        provider_for_dataset("uci:320", object(), object())
