from __future__ import annotations

import pandas as pd

from app.api.schemas import AnalysisRequest, ResearchInterpretation, UCIRecord
from app.analysis.service import DatasetAnalysisService
from app.profiling.profiler import DataProfiler


def _interpretation() -> ResearchInterpretation:
    return ResearchInterpretation(
        original_research_question="Does study time affect grades?",
        research_subject="student performance",
        independent_variables=["study time"],
        dependent_variables=["grades"],
        target_population="students",
        synonyms=[],
        search_terms=["study", "grades", "students"],
    )


class FakeRepository:
    def __init__(self, dataframe: pd.DataFrame | None = None) -> None:
        self.dataframe = dataframe if dataframe is not None else pd.DataFrame(
            {"studytime": [1, 2, 3], "G3": [10, 12, 15]}
        )
        self.fetch_calls = 0
        self.metadata = UCIRecord(
            dataset_id="uci:320",
            title="Student Performance",
            description="Student performance dataset.",
            repository_url="https://archive.ics.uci.edu/dataset/320",
            variables=["studytime", "G3"],
            variable_descriptions={
                "studytime": "weekly study time",
                "G3": "final grade",
            },
            data_available=True,
        )

    def get_metadata(self, dataset_id: int) -> UCIRecord:
        return self.metadata

    def fetch_dataset(self, dataset_id: int):
        self.fetch_calls += 1
        return self.metadata, self.dataframe, {}


class NoAssessmentGemini:
    def interpret(self, question: str) -> ResearchInterpretation:
        return _interpretation()


def _request() -> AnalysisRequest:
    return AnalysisRequest(research_question="Does study time affect grades?")


def test_first_request_profiles_and_second_request_reuses_persisted_profile(monkeypatch) -> None:
    cache: dict[tuple[int, str, str], dict] = {}
    monkeypatch.setattr("app.analysis.service.upsert_dataset", lambda dataset: 320)
    monkeypatch.setattr(
        "app.analysis.service.get_dataset_profile",
        lambda dataset_id, source_version, profiler_version: cache.get(
            (dataset_id, source_version, profiler_version)
        ),
    )
    monkeypatch.setattr(
        "app.analysis.service.save_dataset_profile",
        lambda dataset_id, source_version, profiler_version, profile: cache.__setitem__(
            (dataset_id, source_version, profiler_version), profile.model_dump(mode="json")
        ) or 1,
    )

    repository = FakeRepository()
    first_service = DatasetAnalysisService(repository, NoAssessmentGemini())
    first = first_service.analyze("uci:320", _request())
    assert first.profile is not None

    second_service = DatasetAnalysisService(repository, NoAssessmentGemini())
    second_service.profiler.profile = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("Pandas profiling should not run on a cache hit")
    )
    second = second_service.analyze("uci:320", _request())

    assert second.profile is not None
    assert second.profile.model_dump() == first.profile.model_dump()


def test_source_version_change_invalidates_profile(monkeypatch) -> None:
    cache: dict[tuple[int, str, str], dict] = {}
    versions: list[str] = []
    monkeypatch.setattr("app.analysis.service.upsert_dataset", lambda dataset: 320)
    monkeypatch.setattr(
        "app.analysis.service.get_dataset_profile",
        lambda dataset_id, source_version, profiler_version: (
            versions.append(source_version) or cache.get((dataset_id, source_version, profiler_version))
        ),
    )
    monkeypatch.setattr(
        "app.analysis.service.save_dataset_profile",
        lambda dataset_id, source_version, profiler_version, profile: cache.__setitem__(
            (dataset_id, source_version, profiler_version), profile.model_dump(mode="json")
        ) or 1,
    )

    repository = FakeRepository()
    first_service = DatasetAnalysisService(repository, NoAssessmentGemini())
    first_service.analyze("uci:320", _request())
    repository.dataframe = pd.DataFrame({"studytime": [1, 2, 4], "G3": [10, 12, 20]})
    second_service = DatasetAnalysisService(repository, NoAssessmentGemini())
    second_service.analyze("uci:320", _request())

    assert len(set(versions)) == 2


def test_profiler_version_change_invalidates_profile(monkeypatch) -> None:
    cache: dict[tuple[int, str, str], dict] = {}
    monkeypatch.setattr("app.analysis.service.upsert_dataset", lambda dataset: 320)
    monkeypatch.setattr(
        "app.analysis.service.get_dataset_profile",
        lambda dataset_id, source_version, profiler_version: cache.get(
            (dataset_id, source_version, profiler_version)
        ),
    )
    monkeypatch.setattr(
        "app.analysis.service.save_dataset_profile",
        lambda dataset_id, source_version, profiler_version, profile: cache.__setitem__(
            (dataset_id, source_version, profiler_version), profile.model_dump(mode="json")
        ) or 1,
    )

    repository = FakeRepository()
    first_service = DatasetAnalysisService(repository, NoAssessmentGemini())
    first_service.analyze("uci:320", _request())
    second_service = DatasetAnalysisService(repository, NoAssessmentGemini())
    second_service.profiler.PROFILER_VERSION = f"{first_service.profiler.PROFILER_VERSION}-next"
    calls = 0
    original_profile = second_service.profiler.profile

    def count_profile(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_profile(*args, **kwargs)

    second_service.profiler.profile = count_profile
    second_service.analyze("uci:320", _request())

    assert calls == 1


def test_profile_cache_database_failure_does_not_corrupt_analysis(monkeypatch) -> None:
    monkeypatch.setattr("app.analysis.service.upsert_dataset", lambda dataset: 320)
    monkeypatch.setattr(
        "app.analysis.service.get_dataset_profile",
        lambda *args: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )
    monkeypatch.setattr(
        "app.analysis.service.save_dataset_profile",
        lambda *args: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )

    response = DatasetAnalysisService(FakeRepository(), NoAssessmentGemini()).analyze(
        "uci:320", _request()
    )

    assert response.data_status == "analyzed"
    assert response.profile is not None
    assert any("cache unavailable" in warning for warning in response.warnings)


def test_source_version_is_not_a_permanent_constant() -> None:
    first = DatasetAnalysisService._source_version(
        pd.DataFrame({"value": [1, 2]}), {}
    )
    second = DatasetAnalysisService._source_version(
        pd.DataFrame({"value": [1, 3]}), {}
    )

    assert first.startswith("sha256:")
    assert first != second
