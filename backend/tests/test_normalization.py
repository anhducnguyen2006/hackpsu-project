import pytest
from pydantic import ValidationError

from app.api.schemas import DatasetRecord, UCIRecord
from app.discovery.uci import dataset_record_from_uci


def test_uci_record_is_adapted_without_fabricating_metadata() -> None:
    record = UCIRecord(
        dataset_id="uci:320",
        title=" Student Performance ",
        description="Student performance data.",
        repository_url="https://archive.ics.uci.edu/dataset/320",
        subject_area="Social Science",
        variables=["studytime", "G3"],
        variable_descriptions={"studytime": "weekly study time"},
        data_available=True,
    )

    normalized = dataset_record_from_uci(record)

    assert normalized.id == "uci:320"
    assert normalized.source == "UCI Machine Learning Repository"
    assert normalized.source_id == "320"
    assert str(normalized.landing_page_url) == "https://archive.ics.uci.edu/dataset/320"
    assert [variable.model_dump() for variable in normalized.variables] == [
        {"name": "studytime", "description": "weekly study time", "data_type": None, "unit": None},
        {"name": "G3", "description": None, "data_type": None, "unit": None},
    ]
    assert normalized.download_resources == []
    assert normalized.subjects == ["Social Science"]
    assert normalized.geographic_coverage == []
    assert normalized.temporal_coverage == []
    assert normalized.doi is None
    assert normalized.license is None


def test_dataset_record_normalizes_urls_formats_and_empty_metadata() -> None:
    record = DatasetRecord(
        id="  test-source:abc-123 ",
        source=" Test Source ",
        source_id=" abc-123 ",
        title=" Example dataset ",
        description=" ",
        landing_page_url=" https://example.org/datasets/abc-123 ",
        download_resources=[{"url": "https://example.org/data.csv", "format": ".CSV"}],
        subjects=[" ecology ", "ecology", " "],
        geographic_coverage=None,
        temporal_coverage=[" 2020 ", "2020"],
    )

    assert record.id == "test-source:abc-123"
    assert record.source == "Test Source"
    assert record.title == "Example dataset"
    assert record.description is None
    assert str(record.landing_page_url) == "https://example.org/datasets/abc-123"
    assert record.download_resources[0].format == "csv"
    assert record.subjects == ["ecology"]
    assert record.geographic_coverage == []
    assert record.temporal_coverage == ["2020"]
    assert record.data_available is None


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "320", "source": "UCI", "source_id": "320", "title": "Dataset"},
        {"id": "uci:321", "source": "UCI", "source_id": "320", "title": "Dataset"},
        {
            "id": "uci:320",
            "source": "UCI",
            "source_id": "320",
            "title": "Dataset",
            "landing_page_url": "ftp://example.org/data",
        },
    ],
)
def test_dataset_record_rejects_unsafe_identifiers_and_urls(payload: dict) -> None:
    with pytest.raises(ValidationError):
        DatasetRecord.model_validate(payload)


def test_dataset_record_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        DatasetRecord(
            id="uci:320",
            source="UCI",
            source_id="320",
            title="Dataset",
            unverified_claim="not allowed",
        )
