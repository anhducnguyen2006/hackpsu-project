"""External analysis retrieves one re-resolved provider file and parses it."""

from __future__ import annotations

import socket

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.api.schemas import DatasetAnalysisCommand, DatasetRecord, DownloadResource
from app.discovery.dataverse import HarvardDataverseService
from app.ingestion.guard import DownloadRejected, assert_public_host, validate_provider_url
from app.ingestion.parse import parse_table
from app.ingestion.retrieve import SelectionError, list_resources, load_table
from app.main import app
from tests.auth_tokens import bearer


class Peer:
    def __init__(self, address: str = "8.8.8.8") -> None:
        self.address = address

    def get_extra_info(self, name: str):
        if name in {"peername", "server_addr"}:
            return (self.address, 443)
        return None


class Response:
    def __init__(
        self,
        payload: object | None = None,
        *,
        body: bytes = b"",
        status_code: int = 200,
        content_type: str = "application/json",
        location: str | None = None,
        peer: str = "8.8.8.8",
    ) -> None:
        self.payload = payload
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        if location:
            self.headers["location"] = location
        self._body = body
        self.extensions = {"network_stream": Peer(peer)}
        self.content = body

    def json(self) -> object:
        return self.payload

    def iter_bytes(self):
        if self._body:
            yield self._body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class Client:
    def __init__(self, routes: dict[str, Response]) -> None:
        self.routes = routes
        self.calls: list[str] = []

    def get(self, url: str, **kwargs):
        self.calls.append(url)
        for key, response in self.routes.items():
            if key in url:
                return response
        raise AssertionError(url)

    def close(self) -> None:
        return None


def _public(host: str) -> set[str]:
    del host
    return {"8.8.8.8"}


def _dataverse_payload(files: list[dict], title: str = "Rainfall and crops") -> dict:
    return {
        "status": "OK",
        "data": {
            "latestVersion": {
                "versionNumber": 1,
                "versionMinorNumber": 0,
                "versionState": "RELEASED",
                "metadataBlocks": {
                    "citation": {"fields": [{"typeName": "title", "value": title}]}
                },
                "files": files,
            }
        },
    }


def _file(filename: str, content_type: str, file_id: int, *, original: str | None = None) -> dict:
    return {
        "label": original or filename,
        "restricted": False,
        "dataFile": {
            "id": file_id,
            "filename": filename,
            "contentType": content_type,
            "originalFileName": original,
            "originalFileFormat": "text/csv" if original and original.endswith(".csv") else None,
            "filesize": 32,
            "checksum": {"type": "MD5", "value": "abc"},
        },
    }


def _record(source_id: str = "doi:10.1/csv") -> DatasetRecord:
    return DatasetRecord(
        id=f"dataverse:{source_id}",
        source="Harvard Dataverse",
        source_id=source_id,
        title="Pending provider metadata",
        landing_page_url="https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.1/csv",
        doi=source_id,
    )


def test_parser_accepts_csv_and_tab_and_rejects_disguised_payloads() -> None:
    csv_frame = parse_table(
        b"rainfall,yield\n10,3\n20,5\n",
        filename="rainfall.csv",
        declared_format="csv",
        content_type="text/csv",
    )
    assert list(csv_frame.columns) == ["rainfall", "yield"]
    assert float(csv_frame["rainfall"].mean()) == 15
    tab_frame = parse_table(
        b"rainfall\tyield\n1\t2\n",
        filename="survey.tab",
        declared_format="tab",
        content_type="text/tab-separated-values",
    )
    assert list(tab_frame.columns) == ["rainfall", "yield"]
    with pytest.raises(DownloadRejected, match="HTML"):
        parse_table(b"<html><body>rainfall,yield</body></html>", filename="data.csv", declared_format="csv", content_type="text/plain")
    with pytest.raises(DownloadRejected, match="binary|PDF|archive"):
        parse_table(b"%PDF-1.7\n%rainfall,yield\n", filename="data.csv", declared_format="csv", content_type="text/csv")
    with pytest.raises(DownloadRejected, match="binary|archive"):
        parse_table(b"PK\x03\x04csv", filename="data.csv", declared_format="csv", content_type="text/plain")


def test_private_and_unapproved_destinations_are_rejected(monkeypatch) -> None:
    def private(*_args, **_kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", private)
    with pytest.raises(DownloadRejected, match="public"):
        assert_public_host("dataverse.harvard.edu")
    with pytest.raises(DownloadRejected):
        validate_provider_url("http://dataverse.harvard.edu/api/access/datafile/1")
    with pytest.raises(DownloadRejected):
        validate_provider_url("https://user:pass@dataverse.harvard.edu/api/access/datafile/1")
    with pytest.raises(DownloadRejected):
        validate_provider_url("https://evil.example/api/access/datafile/1")
    with pytest.raises(DownloadRejected):
        validate_provider_url("https://169.254.169.254/latest/meta-data")


def test_dataverse_csv_and_tab_parse_without_using_a_client_url() -> None:
    csv_client = Client({
        "datasets/:persistentId": Response(_dataverse_payload([
            _file("rainfall.csv", "text/csv", 11),
        ])),
    })
    download = Client({
        "/api/access/datafile/11": Response(body=b"rainfall,yield\n10,3\n", content_type="text/csv"),
    })
    record, resource, frame, inconclusive = load_table(
        "dataverse:doi:10.1/csv",
        None,
        metadata_client=csv_client,
        download_client=download,
        resolve=_public,
    )
    assert record.title == "Rainfall and crops"
    assert resource.file_id == "11"
    assert str(resource.url).endswith("/api/access/datafile/11")
    assert inconclusive is False
    assert int(frame["yield"].iloc[0]) == 3
    assert all("access/datafile/11" in url for url in download.calls)

    tab_download = Client({
        "/api/access/datafile/12": Response(
            body=b"survey\tyield\n1\t4\n",
            content_type="text/tab-separated-values",
        ),
    })
    tab_meta = Client({
        "datasets/:persistentId": Response(_dataverse_payload([
            _file("survey.tab", "text/tab-separated-values", 12, original="survey.csv"),
        ])),
    })
    _, tab_resource, tab_frame, _ = load_table(
        "dataverse:doi:10.1/csv",
        "12",
        metadata_client=tab_meta,
        download_client=tab_download,
        resolve=_public,
    )
    assert tab_resource.format == "tab"
    assert tab_resource.original_filename == "survey.csv"
    assert list(tab_frame.columns) == ["survey", "yield"]


def test_multiple_files_require_an_explicit_choice_and_redirects_are_rechecked() -> None:
    meta = Client({
        "datasets/:persistentId": Response(_dataverse_payload([
            _file("rainfall.csv", "text/csv", 11),
            _file("crops.csv", "text/csv", 12),
        ])),
    })
    with pytest.raises(SelectionError, match="resource_id"):
        load_table("dataverse:doi:10.1/csv", None, metadata_client=meta, download_client=Client({}), resolve=_public)

    class Sequence:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self._responses = [
                Response(status_code=302, location="https://evil.example/steal.csv", content_type="text/plain"),
            ]

        def get(self, url: str, **kwargs):
            self.calls.append(url)
            return self._responses.pop(0)

        def close(self) -> None:
            return None

    evil = Sequence()
    with pytest.raises(DownloadRejected, match="approved provider"):
        load_table(
            "dataverse:doi:10.1/csv",
            "11",
            metadata_client=meta,
            download_client=evil,
            resolve=_public,
        )
    assert evil.calls == ["https://dataverse.harvard.edu/api/access/datafile/11"]


def test_zenodo_csv_parses_and_inconclusive_csv_requires_explicit_verification() -> None:
    published = {
        "id": 42,
        "links": {"self_html": "https://zenodo.org/records/42"},
        "metadata": {"upload_type": "dataset", "title": "Rainfall table", "doi": "10.5281/zenodo.42", "version": "1"},
        "files": [{
            "id": "data.csv",
            "key": "data.csv",
            "size": 20,
            "checksum": "md5:abc",
            "mimetype": "text/csv",
            "links": {"self": "https://zenodo.org/api/records/42/files/data.csv/content"},
        }],
    }
    record, resource, frame, inconclusive = load_table(
        "zenodo:42",
        None,
        metadata_client=Client({"records/42": Response(published)}),
        download_client=Client({
            "/files/data.csv/content": Response(body=b"rainfall,yield\n2,4\n", content_type="text/csv"),
        }),
        resolve=_public,
    )
    assert record.eligibility_status == "supported_resource_verified"
    assert resource.filename == "data.csv"
    assert inconclusive is False
    assert int(frame["yield"].iloc[0]) == 4

    untyped = {
        "id": 23077368,
        "links": {"self_html": "https://zenodo.org/records/23077368"},
        "metadata": {"resource_type": {"type": "dataset"}, "title": "Water storage", "version": "2025-10-31"},
        "files": [
            {"key": "schema.json", "size": 10, "links": {"self": "https://zenodo.org/api/records/23077368/files/schema.json/content"}},
            {"key": "data.csv", "size": 20, "links": {"self": "https://zenodo.org/api/records/23077368/files/data.csv/content"}},
        ],
    }
    listed = list_resources("zenodo:23077368", client=Client({"records/23077368": Response(untyped)}))
    assert listed.resources == []
    assert listed.eligibility_status == "unverified"
    assert [item.filename for item in listed.verification_candidates] == ["data.csv"]
    with pytest.raises(SelectionError, match="resource_id"):
        load_table(
            "zenodo:23077368",
            None,
            metadata_client=Client({"records/23077368": Response(untyped)}),
            download_client=Client({}),
            resolve=_public,
        )
    _, verified, parsed, inconclusive = load_table(
        "zenodo:23077368",
        "data.csv",
        metadata_client=Client({"records/23077368": Response(untyped)}),
        download_client=Client({
            "/files/data.csv/content": Response(body=b"rainfall,yield\n8,9\n", content_type="text/plain"),
        }),
        resolve=_public,
    )
    assert inconclusive is True
    assert verified.eligible is True
    assert int(parsed["rainfall"].iloc[0]) == 8


def test_analysis_command_rejects_a_client_supplied_url() -> None:
    with pytest.raises(ValueError):
        DatasetAnalysisCommand.model_validate({
            "dataset_id": "zenodo:42",
            "research_question": "How does rainfall affect crop yield?",
            "url": "https://evil.example/data.csv",
        })


def test_analyze_route_parses_a_provider_file_and_stays_authenticated(monkeypatch) -> None:
    from app.api.routes import datasets as datasets_route

    frame = pd.DataFrame({"rainfall": [10, 20], "yield": [3, 5]})
    resource = DownloadResource(
        url="https://dataverse.harvard.edu/api/access/datafile/11",
        format="csv",
        file_id="11",
        filename="rainfall.csv",
        content_type="text/csv",
        access_status="public",
        eligible=True,
    )
    record = DatasetRecord(
        id="dataverse:doi:10.1/csv",
        source="Harvard Dataverse",
        source_id="doi:10.1/csv",
        title="Rainfall and crops",
        landing_page_url="https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.1/csv",
        doi="doi:10.1/csv",
        download_resources=[resource],
        eligibility_status="supported_resource_verified",
        download_performed=False,
    )

    def fake_load(dataset_id: str, resource_id: str | None, **kwargs):
        assert dataset_id == "dataverse:doi:10.1/csv"
        assert resource_id == "11"
        assert "url" not in kwargs
        return record, resource, frame, False

    def refuse_database():
        raise RuntimeError("TigerData is not available in this test")

    monkeypatch.setattr("app.analysis.service.load_table", fake_load)
    monkeypatch.setattr("app.research.repository.get_connection", refuse_database)
    body = {
        "dataset_id": "dataverse:doi:10.1/csv",
        "research_question": "How does rainfall affect crop yield?",
        "resource_id": "11",
    }
    anonymous = TestClient(app).post("/api/v1/datasets/analyze", json=body)
    assert anonymous.status_code == 401
    response = TestClient(app).post("/api/v1/datasets/analyze", headers=bearer(), json=body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["download_performed"] is True
    assert payload["eligibility_status"] == "download_verified"
    assert payload["profile"]["row_count"] == 2
    assert payload["profile"]["columns"][0]["numeric_summary"]["mean"] == 15
    assert payload["analyzed_resource"]["file_id"] == "11"
    assert any("cache unavailable" in warning for warning in payload["warnings"])
    resources = TestClient(app).post("/api/v1/datasets/resources", json={"dataset_id": "uci:320"})
    assert resources.status_code == 401
    listed = TestClient(app).post(
        "/api/v1/datasets/resources",
        headers=bearer(),
        json={"dataset_id": "uci:320"},
    )
    assert listed.status_code == 200
    assert listed.json()["resources"] == []
    assert "native" in listed.json()["note"]
    del datasets_route
