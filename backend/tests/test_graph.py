from app.api.schemas import DatasetRecord, DatasetVariable, ResearchInterpretation
from app.graph.service import DatasetKnowledgeGraph


def fixture_record(identifier: str, title: str, variables: list[str], description: str, geography: list[str], time: list[str]) -> DatasetRecord:
    return DatasetRecord(
        id=f"fixture:{identifier}",
        source="Invented fixture repository",
        source_id=identifier,
        title=title,
        description=description,
        variables=[DatasetVariable(name=value) for value in variables],
        geographic_coverage=geography,
        temporal_coverage=time,
    )


def test_graph_connects_complementary_datasets_without_declaring_joinability() -> None:
    rainfall = fixture_record(
        "rainfall",
        "Nepal rainfall by district and year",
        ["district", "year", "rainfall_mm"],
        "Annual rainfall observations for Nepal districts.",
        ["Nepal"],
        ["2010-2020"],
    )
    crops = fixture_record(
        "crops",
        "Nepal crop production by district and year",
        ["district", "year", "crop_production_tonnes"],
        "Annual crop production observations for Nepal districts.",
        ["Nepal"],
        ["2010-2020"],
    )
    unrelated = fixture_record(
        "education",
        "US education outcomes",
        ["school_id", "graduation_rate"],
        "Education outcomes for schools in the United States.",
        ["United States"],
        ["2010-2020"],
    )
    interpretation = ResearchInterpretation(
        original_research_question="How does rainfall affect crop production in Nepal?",
        research_subject="agriculture",
        independent_variables=["rainfall"],
        dependent_variables=["crop production"],
        target_population="Nepal",
        synonyms=[],
        search_terms=["rainfall", "crop", "production"],
    )

    payload = DatasetKnowledgeGraph().build([rainfall, crops, unrelated], interpretation)
    edges = [edge.data for edge in payload.edges]
    pair_edges = [
        edge for edge in edges
        if {edge["source"], edge["target"]} == {"dataset:fixture:rainfall", "dataset:fixture:crops"}
    ]

    assert {edge["relationship_type"] for edge in pair_edges} >= {
        "SHARES_VARIABLE", "OVERLAPPING_COVERAGE", "POTENTIAL_JOIN"
    }
    potential_join = next(edge for edge in pair_edges if edge["relationship_type"] == "POTENTIAL_JOIN")
    assert potential_join["verification_status"] == "unverified_potential"
    assert "not verified" in potential_join["evidence"]
    assert not any(
        {edge["source"], edge["target"]} == {"dataset:fixture:rainfall", "dataset:fixture:education"}
        and edge["relationship_type"] in {"SHARES_VARIABLE", "OVERLAPPING_COVERAGE", "POTENTIAL_JOIN"}
        for edge in edges
    )


def test_graph_does_not_turn_unknown_coverage_into_overlap() -> None:
    first = fixture_record("first", "Rainfall", ["district", "year"], "Nepal rainfall", [], [])
    second = fixture_record("second", "Crops", ["district", "year"], "Nepal crops", [], [])

    payload = DatasetKnowledgeGraph().build([first, second])
    relationships = {edge.data["relationship_type"] for edge in payload.edges}

    assert "SHARES_VARIABLE" in relationships
    assert "OVERLAPPING_COVERAGE" not in relationships
    assert "POTENTIAL_JOIN" not in relationships


def test_graph_ids_and_output_order_are_stable() -> None:
    records = [
        fixture_record("b", "B", ["year"], "B", ["Nepal"], ["2020"]),
        fixture_record("a", "A", ["year"], "A", ["Nepal"], ["2020"]),
    ]

    first = DatasetKnowledgeGraph().build(records).model_dump()
    second = DatasetKnowledgeGraph().build(list(reversed(records))).model_dump()

    assert first == second
    assert all(item["data"]["id"].startswith(("dataset:", "variable:", "geography:", "time_period:")) for item in first["nodes"])
    assert all("evidence" in item["data"] and "verification_status" in item["data"] for item in first["edges"])
