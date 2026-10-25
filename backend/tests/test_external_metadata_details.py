from __future__ import annotations

from datetime import date

from app.api.schemas import DatasetRecord
from app.discovery.dataverse import HarvardDataverseService
from app.discovery.search import DiscoveryService
from app.discovery.zenodo import ZenodoService


class _Response:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.content = b"{}"

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _Client:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def get(self, url: str, params=None, headers=None):
        self.calls.append({"url": url, "params": params or {}})
        return _Response(self.payload)


def test_dataverse_verify_exposes_citation_metadata_beyond_doi() -> None:
    payload = {
        "data": {
            "latestVersion": {
                "versionState": "RELEASED",
                "versionNumber": 1,
                "versionMinorNumber": 0,
                "files": [
                    {
                        "label": "sleep.tab",
                        "dataFile": {
                            "id": 11,
                            "filename": "sleep.tab",
                            "contentType": "text/tab-separated-values",
                            "filesize": 2048,
                            "md5": "abc",
                        },
                    }
                ],
                "metadataBlocks": {
                    "citation": {
                        "fields": [
                            {"typeName": "title", "value": "Adolescent Sleep Need Waking EEG"},
                            {
                                "typeName": "dsDescription",
                                "value": [
                                    {
                                        "dsDescriptionValue": {
                                            "value": "EEG recordings related to adolescent sleep need."
                                        }
                                    }
                                ],
                            },
                            {
                                "typeName": "author",
                                "value": [{"authorName": {"value": "Example Author"}}],
                            },
                            {"typeName": "subject", "value": ["Medicine, Health and Life Sciences"]},
                            {
                                "typeName": "keyword",
                                "value": [{"keywordValue": {"value": "sleep"}}],
                            },
                            {
                                "typeName": "producer",
                                "value": [{"producerName": {"value": "Harvard Dataverse"}}],
                            },
                            {"typeName": "distributionDate", "value": "2018"},
                            {
                                "typeName": "timePeriodCovered",
                                "value": [
                                    {
                                        "timePeriodCoveredStart": {"value": "2011"},
                                        "timePeriodCoveredEnd": {"value": "2013"},
                                    }
                                ],
                            },
                            {"typeName": "license", "value": "CC0 1.0"},
                        ]
                    }
                },
            }
        }
    }
    seed = DatasetRecord(
        id="dataverse:doi:10.7910/DVN/EVNUZS",
        source="Harvard Dataverse",
        source_id="doi:10.7910/DVN/EVNUZS",
        title="Placeholder",
        description=None,
        landing_page_url="https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/EVNUZS",
        doi="doi:10.7910/DVN/EVNUZS",
    )
    verified = HarvardDataverseService(client=_Client(payload)).verify(
        seed, today=date(2026, 10, 25)
    )
    assert verified.title == "Adolescent Sleep Need Waking EEG"
    assert "EEG recordings" in (verified.description or "")
    assert verified.authors == ["Example Author"]
    assert verified.publisher == "Harvard Dataverse"
    assert verified.publication_date == "2018"
    assert verified.keywords == ["sleep"]
    assert verified.subjects == ["Medicine, Health and Life Sciences"]
    assert verified.temporal_coverage == ["2011–2013"]
    assert verified.license == "CC0 1.0"
    assert verified.doi == "doi:10.7910/DVN/EVNUZS"
    assert verified.download_resources
    result = DiscoveryService._result_from_semantic_score(verified, 0.55, [])
    assert result.authors == ["Example Author"]
    assert result.keywords == ["sleep"]
    assert result.publisher == "Harvard Dataverse"


def test_zenodo_record_exposes_creators_keywords_and_files() -> None:
    item = {
        "id": 12345,
        "doi": "10.5281/zenodo.12345",
        "links": {"html": "https://zenodo.org/records/12345"},
        "metadata": {
            "upload_type": "dataset",
            "title": "Caffeine intake diary",
            "description": "<p>Self-reported caffeine intake.</p>",
            "doi": "10.5281/zenodo.12345",
            "version": "1.2",
            "publication_date": "2024-01-15",
            "creators": [{"name": "Ada Researcher"}],
            "keywords": ["caffeine", "sleep"],
            "subjects": [{"term": "Psychology"}],
            "license": {"id": "cc-by-4.0"},
        },
        "files": [
            {
                "id": "diary.csv",
                "key": "diary.csv",
                "size": 4096,
                "checksum": "md5:abc",
                "mimetype": "text/csv",
                "links": {"self": "https://zenodo.org/api/records/12345/files/diary.csv"},
            }
        ],
    }
    record = ZenodoService(client=_Client({}))._record_from_item(item)
    assert record.authors == ["Ada Researcher"]
    assert record.keywords == ["caffeine", "sleep"]
    assert record.publication_date == "2024-01-15"
    assert record.publisher == "Zenodo"
    assert record.description == "Self-reported caffeine intake."
    assert record.license == "cc-by-4.0"
    assert record.download_resources[0].filename == "diary.csv"
    result = DiscoveryService._result_from_semantic_score(record, 0.4, [])
    assert result.authors == ["Ada Researcher"]
    assert result.publication_date == "2024-01-15"
