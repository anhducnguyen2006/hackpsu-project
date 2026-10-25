"""Eligible discovery results require supported public tabular resources."""

from __future__ import annotations

from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from app.api.schemas import DatasetRecord, DatasetResult, ResearchInterpretation, UCIRecord
from app.discovery.dataverse import DataverseRepositoryError, HarvardDataverseService
from app.discovery.eligibility import ELIGIBLE_STATUSES, assess_tabular_file, summarize_files
from app.discovery.search import DiscoveryService, SearchConcept
from app.discovery.zenodo import ZenodoService
from app.main import app
from tests.auth_tokens import bearer


class Response:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
        self.content = b"{}"

    def json(self) -> object:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class Client:
    def __init__(self, routes: dict[str, Response] | None = None, response: Response | None = None) -> None:
        self.routes = routes or {}
        self.response = response
        self.calls: list[str] = []

    def get(self, url: str, **kwargs):
        self.calls.append(url)
        if "access/datafile" in url or "/files/" in url and "api/records" in url and kwargs.get("stream"):
            raise AssertionError(f"discovery downloaded a file: {url}")
        persistent_id = (kwargs.get("params") or {}).get("persistentId")
        if persistent_id and persistent_id in self.routes:
            return self.routes[persistent_id]
        if self.response is not None and "api/search" in url:
            return self.response
        for key, response in self.routes.items():
            if key in url:
                return response
        if self.response is not None:
            return self.response
        raise AssertionError(url)


def _uci(dataset_id: str, title: str, *, available: bool | None = True) -> UCIRecord:
    return UCIRecord(
        dataset_id=f"uci:{dataset_id}",
        title=title,
        description=title,
        repository_url=f"https://archive.ics.uci.edu/dataset/{dataset_id}",
        variables=["rainfall", "yield"],
        data_available=available,
    )


def _dataverse_file(
    filename: str,
    content_type: str,
    *,
    file_id: int = 10,
    original_name: str | None = None,
    original_format: str | None = None,
    size: int = 128,
    restricted: bool = False,
    embargo: str | None = None,
) -> dict:
    item = {
        "label": original_name or filename,
        "restricted": restricted,
        "dataFile": {
            "id": file_id,
            "filename": filename,
            "contentType": content_type,
            "filesize": size,
            "originalFileName": original_name,
            "originalFileFormat": original_format,
            "checksum": {"type": "MD5", "value": "abc123"},
        },
    }
    if embargo:
        item["embargo"] = {"dateAvailable": embargo}
    return item


def _dataverse_payload(files: list[dict] | None, *, state: str = "RELEASED") -> dict:
    version: dict = {
        "versionNumber": 2,
        "versionMinorNumber": 0,
        "versionState": state,
    }
    if files is not None:
        version["files"] = files
    return {"status": "OK", "data": {"latestVersion": version}}


def _record(source_id: str = "doi:10.5072/FK2/ABC") -> DatasetRecord:
    return DatasetRecord(
        id=f"dataverse:{source_id}",
        source="Harvard Dataverse",
        source_id=source_id,
        title="Rainfall and crops",
        landing_page_url="https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.5072/FK2/ABC",
        doi=source_id,
    )


def test_dataverse_public_csv_tab_pdf_restricted_embargo_and_oversize(monkeypatch) -> None:
    monkeypatch.setattr("app.discovery.dataverse.settings.discovery_max_resource_bytes", 1_000)
    cases = {
        "doi:10.1/csv": _dataverse_payload([
            _dataverse_file("rainfall.csv", "text/csv", file_id=11, size=100),
        ]),
        "doi:10.1/tab": _dataverse_payload([
            _dataverse_file(
                "survey.tab",
                "text/tab-separated-values",
                file_id=12,
                original_name="survey.csv",
                original_format="text/csv",
                size=100,
            ),
        ]),
        "doi:10.1/pdf": _dataverse_payload([
            _dataverse_file("paper.pdf", "application/pdf", file_id=13, size=100),
        ]),
        "doi:10.1/both": _dataverse_payload([
            _dataverse_file("paper.pdf", "application/pdf", file_id=14, size=100),
            _dataverse_file("observations.csv", "text/csv", file_id=15, size=100),
        ]),
        "doi:10.1/restricted": _dataverse_payload([
            _dataverse_file("secret.csv", "text/csv", file_id=16, size=100, restricted=True),
        ]),
        "doi:10.1/embargo": _dataverse_payload([
            _dataverse_file("later.csv", "text/csv", file_id=17, size=100, embargo="2099-01-01"),
        ]),
        "doi:10.1/huge": _dataverse_payload([
            _dataverse_file("huge.csv", "text/csv", file_id=18, size=50_000),
        ]),
        "doi:10.1/missing": _dataverse_payload(None),
    }
    service = HarvardDataverseService(client=Client(routes={key: Response(payload) for key, payload in cases.items()}))
    verified = {
        key: service.verify(_record(key), today=date(2026, 10, 25))
        for key in cases
    }
    assert verified["doi:10.1/csv"].eligibility_status == "supported_resource_verified"
    assert verified["doi:10.1/csv"].download_resources[0].file_id == "11"
    assert verified["doi:10.1/csv"].source_version == "2.0"
    assert verified["doi:10.1/csv"].download_performed is False
    assert verified["doi:10.1/tab"].download_resources[0].format == "tab"
    assert verified["doi:10.1/tab"].download_resources[0].original_filename == "survey.csv"
    assert verified["doi:10.1/pdf"].eligibility_status == "unsupported"
    assert verified["doi:10.1/both"].eligibility_status == "supported_resource_verified"
    assert [resource.filename for resource in verified["doi:10.1/both"].download_resources] == ["observations.csv"]
    assert verified["doi:10.1/restricted"].eligibility_status == "restricted"
    assert verified["doi:10.1/embargo"].eligibility_status == "restricted"
    assert "embargo" in (verified["doi:10.1/embargo"].eligibility_reason or "")
    assert verified["doi:10.1/huge"].eligibility_status == "unsupported"
    assert verified["doi:10.1/missing"].eligibility_status == "unverified"
    assert all("access/datafile" not in url for url in service.client.calls)


def test_dataverse_file_count_does_not_make_a_search_hit_eligible() -> None:
    client = Client(response=Response({
        "data": {"items": [{
            "type": "dataset",
            "global_id": "doi:10.1/count",
            "name": "Sounds like data",
            "url": "https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.1/count",
            "fileCount": 4,
        }]}
    }))
    records = HarvardDataverseService(client=client).search(["rainfall"])
    assert records[0].data_available is None
    assert records[0].eligibility_status == "unverified"
    assert records[0].download_resources == []


def _zenodo(record_id: int, metadata: dict, files: object | None = None, access: dict | None = None) -> dict:
    item = {
        "id": record_id,
        "links": {"self_html": f"https://zenodo.org/records/{record_id}"},
        "metadata": metadata,
    }
    if files is not None:
        item["files"] = files
    if access is not None:
        item["access"] = access
    return item


def _csv_file(name: str = "data.csv", media: str = "text/csv", size: int = 20) -> dict:
    return {
        "id": name,
        "key": name,
        "size": size,
        "checksum": "md5:abc",
        "mimetype": media,
        "links": {"self": f"https://zenodo.org/api/records/1/files/{name}"},
    }


def test_zenodo_classifies_modern_legacy_and_ineligible_records() -> None:
    published_csv = ZenodoService(client=Client())._record_from_item(_zenodo(
        23077368,
        {"resource_type": {"id": "dataset"}, "title": "Rainfall", "doi": "10.5281/zenodo.23077368", "version": "1.0"},
        [_csv_file("rainfall.csv")],
        {"files": "public", "record": "public"},
    ))
    published_tsv = ZenodoService(client=Client())._record_from_item(_zenodo(
        2,
        {"upload_type": "dataset", "title": "Crops"},
        [_csv_file("crop_data.tsv", "text/tab-separated-values")],
    ))
    pdf_only = ZenodoService(client=Client())._record_from_item(_zenodo(
        3,
        {"upload_type": "dataset", "title": "Rainfall paper"},
        [_csv_file("paper.pdf", "application/pdf")],
    ))
    csv_and_pdf = ZenodoService(client=Client())._record_from_item(_zenodo(
        4,
        {"resource_type": {"id": "dataset"}, "title": "Rainfall with notes"},
        [_csv_file("data.csv"), _csv_file("README.pdf", "application/pdf")],
    ))
    restricted = ZenodoService(client=Client())._record_from_item(_zenodo(
        5,
        {"upload_type": "dataset", "title": "Closed files"},
        [_csv_file("hidden.csv")],
        {"files": "restricted"},
    ))
    embargoed = ZenodoService(client=Client())._record_from_item(_zenodo(
        15,
        {"upload_type": "dataset", "title": "Embargoed files"},
        [_csv_file("later.csv")],
        {"files": "embargoed"},
    ))
    modern_entries = ZenodoService(client=Client())._record_from_item(_zenodo(
        6,
        {"resource_type": {"id": "dataset"}, "title": "Modern files"},
        {"entries": {"observations.csv": _csv_file("observations.csv")}},
    ))
    mismatch = ZenodoService(client=Client())._record_from_item(_zenodo(
        7,
        {"upload_type": "dataset", "title": "Mislabelled"},
        [_csv_file("data.csv", "application/octet-stream")],
    ))
    missing_files = ZenodoService(client=Client())._record_from_item(_zenodo(
        8,
        {"upload_type": "dataset", "title": "No file list"},
    ))
    publication = ZenodoService(client=Client(response=Response({"hits": {"hits": [_zenodo(
        9, {"upload_type": "publication", "title": "Paper only", "doi": "10.5281/zenodo.9"}
    )]}}))).search(["rainfall"])

    assert published_csv.eligibility_status == "supported_resource_verified"
    assert published_csv.doi == "10.5281/zenodo.23077368"
    assert published_csv.source_version == "1.0"
    assert published_csv.download_performed is False
    assert published_tsv.download_resources[0].format == "tsv"
    assert pdf_only.eligibility_status == "unsupported"
    assert [item.filename for item in csv_and_pdf.download_resources] == ["data.csv"]
    assert restricted.eligibility_status == "restricted"
    assert embargoed.eligibility_status == "restricted"
    assert "embargoed" in (embargoed.eligibility_reason or "")
    assert modern_entries.download_resources[0].filename == "observations.csv"
    assert mismatch.eligibility_status == "unsupported"
    assert missing_files.eligibility_status == "unverified"
    assert publication == []
    untyped_csv = ZenodoService(client=Client())._record_from_item(_zenodo(
        23077368,
        {"resource_type": {"type": "dataset"}, "title": "Monthly water storage", "doi": "10.5281/zenodo.23077368"},
        [
            {"key": "schema.json", "size": 585, "links": {"self": "https://zenodo.org/api/records/23077368/files/schema.json/content"}},
            {"key": "data.csv", "size": 392118, "links": {"self": "https://zenodo.org/api/records/23077368/files/data.csv/content"}},
            {"key": "data.parquet", "size": 67591, "links": {"self": "https://zenodo.org/api/records/23077368/files/data.parquet/content"}},
        ],
    ))
    assert untyped_csv.eligibility_status == "unverified"
    assert untyped_csv.download_resources == []
    assert "data.csv" in (untyped_csv.eligibility_reason or "")
    assert untyped_csv.download_performed is False


def test_filename_alone_is_not_treated_as_a_verified_resource() -> None:
    assessment = assess_tabular_file(
        url="https://example.test/data.csv",
        filename="data.csv",
        content_type=None,
        max_bytes=1000,
    )
    status, _, resources = summarize_files([assessment], files_declared=True)
    assert status == "unverified"
    assert resources == []
    assert assessment.eligible is False


def test_provider_timeout_and_rate_limit_do_not_hide_other_results() -> None:
    class TimeoutClient(Client):
        def get(self, url: str, **kwargs):
            self.calls.append(url)
            if "datasets/:persistentId" in url:
                raise httpx.TimeoutException("timed out")
            return Response({"data": {"items": []}})

    class LimitedClient(Client):
        def get(self, url: str, **kwargs):
            self.calls.append(url)
            return Response({}, status_code=429)

    timeout = HarvardDataverseService(client=TimeoutClient())
    with pytest.raises(DataverseRepositoryError, match="timed out"):
        timeout.verify(_record("doi:10.1/timeout"))
    limited = ZenodoService(client=LimitedClient())
    with pytest.raises(Exception, match="429"):
        limited.verify(DatasetRecord(
            id="zenodo:1",
            source="Zenodo",
            source_id="1",
            title="Pending",
            landing_page_url="https://zenodo.org/records/1",
        ))


class _Repo:
    def __init__(self, records: list[UCIRecord]) -> None:
        self.records = records

    def discover_catalog(self) -> list[UCIRecord]:
        return self.records

    def get_metadata(self, dataset_id: int) -> UCIRecord:
        return next(record for record in self.records if record.dataset_id == f"uci:{dataset_id}")


class _Gemini:
    def interpret(self, question: str) -> ResearchInterpretation:
        return ResearchInterpretation(
            original_research_question=question,
            research_subject="crop yield",
            independent_variables=["rainfall"],
            dependent_variables=["crop yield"],
            synonyms=["precipitation"],
            search_terms=["rainfall", "crop", "yield"],
        )


class _Scores:
    def score_queries(self, queries, candidates):
        rows = []
        for _query in queries:
            row = {}
            for candidate in candidates:
                title = candidate.title.lower()
                if "paper" in title or "heart" in title or "health" in title:
                    row[candidate.id] = 0.04
                elif "rainfall" in title or "crop" in title:
                    row[candidate.id] = 0.83
                else:
                    row[candidate.id] = 0.05
            rows.append(row)
        return rows


def _eligible_zenodo(source_id: str, title: str) -> DatasetRecord:
    from app.api.schemas import DownloadResource

    return DatasetRecord(
        id=f"zenodo:{source_id}",
        source="Zenodo",
        source_id=source_id,
        title=title,
        landing_page_url=f"https://zenodo.org/records/{source_id}",
        download_resources=[
            DownloadResource(
                url=f"https://zenodo.org/api/records/{source_id}/files/data.csv",
                format="csv",
                filename="data.csv",
                content_type="text/csv",
                access_status="public",
                eligible=True,
            )
        ],
        eligibility_status="supported_resource_verified",
        eligibility_reason="Provider metadata lists data.csv.",
        download_performed=False,
    )


def test_discovery_keeps_only_eligible_relevant_records_and_orders_stably() -> None:
    available = _uci("1", "Rainfall and crop yield")
    unavailable = _uci("2", "Unavailable rainfall", available=False)
    paraphrase = _uci("9", "Hours of academic effort")
    dataverse = HarvardDataverseService(client=Client(routes={
        "api/search": Response({"data": {"items": [
            {
                "type": "dataset",
                "global_id": "doi:10.1/pdf",
                "name": "Rainfall paper",
                "url": "https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.1/pdf",
                "fileCount": 3,
            },
            {
                "type": "dataset",
                "global_id": "doi:10.1/csv",
                "name": "Rainfall and crop yield",
                "url": "https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.1/csv",
            },
        ]}}),
        "doi:10.1/pdf": Response(_dataverse_payload([
            _dataverse_file("paper.pdf", "application/pdf", file_id=1),
        ])),
        "doi:10.1/csv": Response(_dataverse_payload([
            _dataverse_file("rainfall.csv", "text/csv", file_id=2),
        ])),
    }))
    service = DiscoveryService(_Repo([available, unavailable, paraphrase]), _Gemini(), [dataverse], _Scores())
    _interpretation, datasets, warnings, mode, ranking = service.search_with_status(
        "How does rainfall affect crop yield?", 12
    )
    ids = [dataset.dataset_id for dataset in datasets]
    assert "uci:2" not in ids
    assert "dataverse:doi:10.1/pdf" not in ids
    assert "uci:1" in ids
    assert "dataverse:doi:10.1/csv" in ids
    assert all(dataset.eligibility_status in ELIGIBLE_STATUSES for dataset in datasets)
    assert all(dataset.download_performed is False for dataset in datasets)
    assert all(dataset.score_type == "semantic_similarity" for dataset in datasets)
    assert "probability" in datasets[0].relevance_explanation
    assert mode == "gemini"
    assert ranking == "semantic_embeddings"
    assert warnings == []
    graph = service.graph_for_search("How does rainfall affect crop yield?", 12)
    labels = [str(node.data.get("id")) for node in graph.nodes]
    assert all("doi:10.1/pdf" not in node_id for node_id in labels)
    assert any("dataverse:doi:10.1/csv" in node_id for node_id in labels)
    assert all("access/datafile" not in url for url in dataverse.client.calls)

    class SlowProvider:
        source = "Zenodo"

        def search(self, terms: list[str]):
            query = " ".join(terms)
            if query == "beta":
                return [_eligible_zenodo("2", "Beta rainfall")]
            return [_eligible_zenodo("1", "Alpha rainfall")]

    ordered = DiscoveryService(_Repo([]), _Gemini(), [SlowProvider()], _Scores())
    concepts = [SearchConcept("a", "search_term", "alpha"), SearchConcept("b", "search_term", "beta")]
    assert [record.id for record in ordered._search_external(concepts, [])] == ["zenodo:1", "zenodo:2"]


def test_provider_verification_failure_keeps_other_sources() -> None:
    class BrokenDataverse:
        source = "Harvard Dataverse"

        def search(self, terms: list[str]):
            return [DatasetRecord(
                id="dataverse:doi:10.1/pending",
                source=self.source,
                source_id="doi:10.1/pending",
                title="Rainfall pending",
                landing_page_url="https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.1/pending",
                doi="doi:10.1/pending",
                eligibility_status="unverified",
            )]

        def verify(self, record: DatasetRecord):
            raise DataverseRepositoryError("Harvard Dataverse rate limit reached (HTTP 429).")

    class ReadyZenodo:
        source = "Zenodo"

        def search(self, terms: list[str]):
            return [_eligible_zenodo("9", "Rainfall and crop yield")]

    _, datasets, warnings, _, _ = DiscoveryService(
        _Repo([]), _Gemini(), [BrokenDataverse(), ReadyZenodo()], _Scores()
    ).search_with_status("How does rainfall affect crop yield?", 8)
    assert [dataset.dataset_id for dataset in datasets] == ["zenodo:9"]
    assert any("429" in warning for warning in warnings)


def test_synonym_candidate_can_reach_ranking_without_token_overlap() -> None:
    catalog = [
        _uci("1", "Heart disease"),
        _uci("8", "Student housing survey"),
    ]
    catalog[0] = catalog[0].model_copy(update={
        "description": "Clinical records",
        "variables": ["diagnosis"],
    })

    class CardiovascularGemini:
        def interpret(self, question: str) -> ResearchInterpretation:
            return ResearchInterpretation(
                original_research_question=question,
                research_subject="circulatory illness",
                independent_variables=["cardiovascular conditions"],
                dependent_variables=["mortality"],
                synonyms=["circulatory illness"],
                search_terms=["cardiovascular", "conditions"],
            )

    class SynonymScores:
        def score_queries(self, queries, candidates):
            return [{
                candidate.id: 0.72 if "heart disease" in candidate.title.lower() else 0.03
                for candidate in candidates
            } for _ in queries]

    _, datasets, _, _, _ = DiscoveryService(
        _Repo(catalog), CardiovascularGemini(), [], SynonymScores()
    ).search_with_status("How do cardiovascular conditions affect mortality?", 8)
    assert [dataset.dataset_id for dataset in datasets] == ["uci:1"]


def test_low_scoring_eligible_records_do_not_fill_the_limit() -> None:
    class LowScores:
        def score_queries(self, queries, candidates):
            return [{candidate.id: 0.05 for candidate in candidates} for _ in queries]

    _, datasets, warnings, _, ranking = DiscoveryService(
        _Repo([_uci("1", "Rainfall and crop yield")]), _Gemini(), [], LowScores()
    ).search_with_status("How does rainfall affect crop yield?", 8)
    assert datasets == []
    assert ranking == "semantic_embeddings"
    assert any("relevance floor" in warning for warning in warnings)


def test_external_candidate_pool_is_bounded_and_deterministic(monkeypatch) -> None:
    monkeypatch.setattr("app.discovery.search.settings.discovery_candidate_limit", 3)

    class Many:
        source = "Zenodo"

        def search(self, terms: list[str]):
            query = " ".join(terms)
            start = 10 if query == "beta" else 1
            return [
                _eligible_zenodo(str(index), f"Rainfall {index}")
                for index in range(start, start + 5)
            ]

    service = DiscoveryService(_Repo([]), _Gemini(), [Many()], _Scores())
    concepts = [SearchConcept("a", "search_term", "alpha"), SearchConcept("b", "search_term", "beta")]
    first = [record.id for record in service._search_external(concepts, [])]
    second = [record.id for record in service._search_external(concepts, [])]
    assert first == second == ["zenodo:1", "zenodo:2", "zenodo:3"]


def test_curated_relevance_floor_separates_eight_cases() -> None:
    """The 0.20 floor sits below the retained crop-only score and above broad false positives.

    Pairs are fixture scores, not a live embedding run. PDF eligibility is independent
    of the cosine score.
    """
    cases = [
        ("relevant rainfall csv", 0.83, "supported_resource_verified", True),
        ("irrelevant heart study", 0.04, "supported_resource_verified", False),
        ("precipitation synonym", 0.62, "supported_resource_verified", True),
        ("broad health false positive", 0.13, "supported_resource_verified", False),
        ("relevant but missing a variable", 0.41, "supported_resource_verified", True),
        ("pdf title about rainfall", 0.91, "unsupported", False),
        ("csv plus documentation pdf", 0.77, "supported_resource_verified", True),
        ("weak but downloadable csv", 0.08, "supported_resource_verified", False),
    ]
    floor = 0.20
    included_names = []
    for name, score, status, expected in cases:
        included = status in ELIGIBLE_STATUSES and score >= floor
        assert included is expected
        if included:
            included_names.append(name)
    assert included_names == [
        "relevant rainfall csv",
        "precipitation synonym",
        "relevant but missing a variable",
        "csv plus documentation pdf",
    ]


def test_discovery_route_returns_eligible_records_and_stays_authenticated(monkeypatch) -> None:
    from app.api.routes import discovery as discovery_route

    service = DiscoveryService(
        _Repo([_uci("1", "Rainfall and crop yield"), _uci("2", "Closed", available=False)]),
        _Gemini(),
        [],
        _Scores(),
    )
    captured: dict[str, object] = {}

    def capture(question, normalized_question, datasets, embedding_service=None, *, user_sub, research_query_id=None):
        captured["user_sub"] = user_sub
        captured["datasets"] = datasets
        captured["research_query_id"] = research_query_id
        return 1

    monkeypatch.setattr(discovery_route, "service", service)
    monkeypatch.setattr(discovery_route, "persist_discovery_result", capture)
    monkeypatch.setattr(discovery_route.settings, "demo_mode", False)
    anonymous = TestClient(app).post(
        "/api/v1/discovery/search",
        json={"research_question": "How does rainfall affect crop yield?", "limit": 8},
    )
    assert anonymous.status_code == 401
    assert captured == {}
    response = TestClient(app).post(
        "/api/v1/discovery/search",
        headers=bearer(),
        json={"research_question": "How does rainfall affect crop yield?", "limit": 8},
    )
    assert response.status_code == 200
    payload = response.json()
    assert [item["dataset_id"] for item in payload["datasets"]] == ["uci:1"]
    assert payload["datasets"][0]["eligibility_status"] == "supported_resource_verified"
    assert payload["datasets"][0]["download_performed"] is False
    assert captured["user_sub"] == "auth0|user-a"
    assert captured["datasets"][0].eligibility_status == "supported_resource_verified"


def test_discovery_does_not_require_tigerdata(monkeypatch) -> None:
    def refuse_database():
        raise AssertionError("discovery must not open TigerData")

    monkeypatch.setattr("app.research.repository.get_connection", refuse_database)
    _, datasets, _, _, _ = DiscoveryService(
        _Repo([_uci("1", "Rainfall and crop yield")]), _Gemini(), [], _Scores()
    ).search_with_status("How does rainfall affect crop yield?", 8)
    assert datasets[0].dataset_id == "uci:1"


def test_persisted_metadata_keeps_eligibility_without_claiming_download(monkeypatch) -> None:
    from app.research import repository

    calls: list[tuple[str, tuple]] = []

    class Result:
        def fetchone(self):
            return (1,)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, query: str, params: tuple):
            calls.append((query, params))
            return Result()

        def commit(self) -> None:
            return None

        def rollback(self) -> None:
            return None

    monkeypatch.setattr(repository, "get_connection", lambda: Connection())
    result = DatasetResult(
        dataset_id="dataverse:doi:10.1/csv",
        title="Rainfall",
        repository_url="https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.1/csv",
        source="Harvard Dataverse",
        source_id="doi:10.1/csv",
        landing_page_url="https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.1/csv",
        data_status="available",
        eligibility_status="supported_resource_verified",
        eligibility_reason="Provider metadata lists rainfall.csv.",
        download_performed=False,
        relevance_explanation=(
            "Semantic similarity: 0.8300. This score ranks verified metadata against "
            "the research question; it is not a probability, scientific suitability "
            "score, or evidence of causation."
        ),
        score_type="semantic_similarity",
        semantic_similarity_score=0.83,
    )
    repository.persist_discovery_result(
        "How does rainfall affect crop yield?",
        "rainfall and crop yield",
        [result],
        user_sub="auth0|user-a",
    )
    query_insert = next(params for query, params in calls if "INSERT INTO research_queries" in query)
    dataset_insert = next(params for query, params in calls if "INSERT INTO datasets" in query)
    assert query_insert[-1] == "auth0|user-a"
    metadata = dataset_insert[-1]
    assert isinstance(metadata, Jsonb)
    assert metadata.obj["eligibility_status"] == "supported_resource_verified"
    assert metadata.obj["download_performed"] is False
