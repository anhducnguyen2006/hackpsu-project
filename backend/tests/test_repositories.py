from __future__ import annotations

from typing import Iterable

import pytest

from app.api.schemas import (
    DatasetRecord,
    DownloadResource,
    RelevanceAssessmentBatch,
    ResearchInterpretation,
    UCIRecord,
)
from app.discovery.dataverse import HarvardDataverseService
from app.discovery.search import DiscoveryService
from app.discovery.zenodo import ZenodoService


class FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def json(self) -> object:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict] = []

    def get(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.response


def test_dataverse_search_uses_documented_dataset_filter() -> None:
    client = FakeClient(
        FakeResponse(
            {
                "status": "OK",
                "data": {
                    "items": [
                        {
                            "type": "dataset",
                            "global_id": "doi:10.5072/FK2/ABC",
                            "name": "Climate observations",
                            "description": "Verified observations.",
                            "url": "https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.5072/FK2/ABC",
                            "subjects": ["Earth Science"],
                            "fileCount": 2,
                        }
                    ]
                },
            }
        )
    )

    records = HarvardDataverseService(client=client).search(["climate", "rainfall"])

    assert len(records) == 1
    assert records[0].id == "dataverse:doi:10.5072/FK2/ABC"
    assert records[0].doi == "doi:10.5072/FK2/ABC"
    assert records[0].data_available is None
    assert records[0].eligibility_status == "unverified"
    assert client.calls[0]["params"]["q"] == "climate rainfall"
    assert client.calls[0]["params"]["type"] == "dataset"
    assert client.calls[0]["params"]["per_page"] == 5


def test_dataverse_skips_invalid_items_and_handles_rate_limits() -> None:
    client = FakeClient(
        FakeResponse(
            {
                "status": "OK",
                "data": {
                    "items": [
                        {"type": "dataset", "name": "Missing identifier"},
                        {"type": "dataverse", "name": "Collection"},
                    ]
                },
            }
        )
    )
    assert HarvardDataverseService(client=client).search(["science"]) == []

    with pytest.raises(Exception, match="429"):
        HarvardDataverseService(
            client=FakeClient(FakeResponse({}, status_code=429))
        ).search(["science"])


def test_zenodo_search_uses_published_dataset_filter_and_maps_files() -> None:
    client = FakeClient(
        FakeResponse(
            {
                "hits": {
                    "hits": [
                        {
                            "id": 12345,
                            "links": {"html": "https://zenodo.org/records/12345"},
                            "metadata": {
                                "upload_type": "dataset",
                                "title": "Climate observations",
                                "description": "Verified observations.",
                                "doi": "10.5281/zenodo.12345",
                                "subjects": [{"term": "Earth Science"}],
                                "license": {"id": "cc-by-4.0"},
                            },
                            "files": [
                                {
                                    "key": "observations.csv",
                                    "mimetype": "text/csv",
                                    "links": {
                                        "self": "https://zenodo.org/api/files/abc/observations.csv"
                                    },
                                }
                            ],
                        }
                    ]
                }
            }
        )
    )

    records = ZenodoService(client=client).search(["climate"])

    assert len(records) == 1
    assert records[0].id == "zenodo:12345"
    assert records[0].download_resources[0].format == "csv"
    assert records[0].eligibility_status == "supported_resource_verified"
    assert records[0].download_performed is False
    assert records[0].license == "cc-by-4.0"
    assert client.calls[0]["params"] == {
        "q": "climate",
        "status": "published",
        "sort": "bestmatch",
        "page": 1,
        "size": 5,
        "all_versions": "false",
        "type": "dataset",
    }


def test_zenodo_skips_non_dataset_and_handles_rate_limits() -> None:
    client = FakeClient(
        FakeResponse(
            {
                "hits": {
                    "hits": [
                        {
                            "id": 1,
                            "links": {"html": "https://zenodo.org/records/1"},
                            "metadata": {"upload_type": "publication", "title": "Paper"},
                        }
                    ]
                }
            }
        )
    )
    assert ZenodoService(client=client).search(["science"]) == []

    with pytest.raises(Exception, match="429"):
        ZenodoService(client=FakeClient(FakeResponse({}, status_code=429))).search(
            ["science"]
        )


def test_zenodo_accepts_current_self_html_landing_link() -> None:
    client = FakeClient(
        FakeResponse(
            {
                "hits": {
                    "hits": [
                        {
                            "id": 67890,
                            "links": {"self_html": "https://zenodo.org/records/67890"},
                            "metadata": {
                                "resource_type": {"type": "dataset"},
                                "title": "Rainfall observations",
                            },
                        }
                    ]
                }
            }
        )
    )

    records = ZenodoService(client=client).search(["rainfall"])

    assert str(records[0].landing_page_url) == "https://zenodo.org/records/67890"


def _interpretation() -> ResearchInterpretation:
    return ResearchInterpretation(
        original_research_question="Does rainfall affect crop yield?",
        research_subject="agriculture",
        independent_variables=["rainfall"],
        dependent_variables=["crop yield"],
        target_population="crops",
        synonyms=[],
        search_terms=["rainfall", "crop", "yield"],
    )


class FakeUCIRepository:
    def discover_catalog(self) -> list[UCIRecord]:
        return [
            UCIRecord(
                dataset_id="uci:1",
                title="Rainfall and crop yield",
                description="Agricultural observations.",
                repository_url="https://archive.ics.uci.edu/dataset/1",
                variables=["rainfall", "yield"],
            )
        ]

    def get_metadata(self, dataset_id: int) -> UCIRecord:
        return self.discover_catalog()[0]


class FakeGemini:
    def interpret(self, question: str) -> ResearchInterpretation:
        return _interpretation()

    def rerank(self, question, interpretation, candidates):
        return RelevanceAssessmentBatch(
            assessments=[
                {
                    "dataset_id": candidate.dataset_id,
                    "preliminary_relevance_score": 80,
                    "score_confidence": "medium",
                    "relevance_explanation": "Verified metadata match.",
                    "matched_research_variables": ["rainfall"],
                    "missing_or_unverified_variables": [],
                    "classification": "relevant",
                }
                for candidate in candidates
            ]
        )


class FakeEmbedding:
    def score_queries(self, queries, candidates):
        return [
            {candidate.id: 0.9 - index * 0.01 for index, candidate in enumerate(candidates)}
            for _ in queries
        ]

    def rank(self, question, candidates, top_k):
        return [(candidate, 0.9 - index * 0.01) for index, candidate in enumerate(candidates[:top_k])]


class FakeProvider:
    def __init__(self, source: str, records: list[DatasetRecord], error: Exception | None = None):
        self.source = source
        self.records = records
        self.error = error
        self.queries: list[str] = []

    def search(self, search_terms: Iterable[str]) -> list[DatasetRecord]:
        self.queries.append(" ".join(search_terms))
        if self.error:
            raise self.error
        return self.records


def _external_record(source: str, source_id: str, doi: str | None = None) -> DatasetRecord:
    source_name = {
        "dataverse": "Harvard Dataverse",
        "zenodo": "Zenodo",
    }.get(source.lower(), source)
    source_prefix = source_name.lower().replace(" ", "-")
    return DatasetRecord(
        id=f"{source_prefix}:{source_id}",
        source=source_name,
        source_id=source_id,
        title=f"Rainfall crop yield {source_id}",
        description="Verified agricultural metadata.",
        landing_page_url=f"https://{source.lower()}.example/records/{source_id}",
        doi=doi,
        data_available=True,
        download_resources=[
            DownloadResource(
                url=f"https://{source.lower()}.example/files/{source_id}.csv",
                format="csv",
                filename=f"{source_id}.csv",
                content_type="text/csv",
                access_status="public",
                eligible=True,
            )
        ],
        eligibility_status="supported_resource_verified",
        eligibility_reason="Trusted repository metadata lists a public CSV resource.",
        download_performed=False,
    )


def test_multiple_sources_are_aggregated_and_terms_are_forwarded() -> None:
    dataverse = FakeProvider("Harvard Dataverse", [_external_record("dataverse", "1")])
    zenodo = FakeProvider("Zenodo", [_external_record("zenodo", "2")])

    _, datasets, warnings, mode = DiscoveryService(
        FakeUCIRepository(),
        FakeGemini(),
        [dataverse, zenodo],
        FakeEmbedding(),
    ).search("Does rainfall affect crop yield?", 8)

    assert {dataset.source for dataset in datasets} == {
        "UCI Machine Learning Repository",
        "Harvard Dataverse",
        "Zenodo",
    }
    assert any("rainfall" in query for query in dataverse.queries)
    assert any("crop" in query for query in dataverse.queries)
    assert any("yield" in query for query in zenodo.queries)
    assert len(dataverse.queries) == 1
    assert len(zenodo.queries) == 1
    assert warnings == []
    assert mode == "keyword_fallback"


def test_external_provider_results_are_cached_for_repeated_searches() -> None:
    dataverse = FakeProvider("Harvard Dataverse", [_external_record("dataverse", "1")])
    service = DiscoveryService(
        FakeUCIRepository(),
        FakeGemini(),
        [dataverse],
        FakeEmbedding(),
    )

    service.search("Does rainfall affect crop yield?", 8)
    service.search("Does rainfall affect crop yield?", 4)

    assert len(dataverse.queries) == 1


def test_duplicate_dois_are_removed_before_reranking() -> None:
    duplicate_a = _external_record("dataverse", "one", "doi:10.5281/ABC")
    duplicate_b = _external_record("zenodo", "two", "https://doi.org/10.5281/ABC")

    _, datasets, _, _ = DiscoveryService(
        FakeUCIRepository(),
        FakeGemini(),
        [FakeProvider("Dataverse", [duplicate_a]), FakeProvider("Zenodo", [duplicate_b])],
        FakeEmbedding(),
    ).search("Does rainfall affect crop yield?", 8)

    assert len(
        [
            dataset
            for dataset in datasets
            if dataset.source in {"Harvard Dataverse", "Zenodo"}
        ]
    ) == 1


def test_one_source_failure_does_not_discard_other_sources() -> None:
    good = FakeProvider("Zenodo", [_external_record("zenodo", "good")])
    broken = FakeProvider("Harvard Dataverse", [], RuntimeError("timeout"))

    _, datasets, warnings, _ = DiscoveryService(
        FakeUCIRepository(), FakeGemini(), [broken, good], FakeEmbedding()
    ).search("Does rainfall affect crop yield?", 8)

    assert any(dataset.source == "Zenodo" for dataset in datasets)
    assert any("Harvard Dataverse unavailable" in warning for warning in warnings)


def test_empty_external_results_preserve_empty_result_behavior() -> None:
    _, datasets, warnings, mode = DiscoveryService(
        FakeUCIRepository(),
        FakeGemini(),
        [FakeProvider("Harvard Dataverse", []), FakeProvider("Zenodo", [])],
        FakeEmbedding(),
    ).search("Does rainfall affect crop yield?", 8)

    assert datasets
    assert warnings == []
    assert mode == "keyword_fallback"
