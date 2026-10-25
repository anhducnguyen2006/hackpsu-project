from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

import networkx as nx

from app.api.schemas import DatasetRecord, GraphEdge, GraphNode, KnowledgeGraphResponse, ResearchInterpretation


class DatasetKnowledgeGraph:
    """Build a small, deterministic Cytoscape graph from verified records only."""

    def __init__(self, max_datasets: int = 12, max_nodes: int = 250, max_edges: int = 600) -> None:
        self.max_datasets = max_datasets
        self.max_nodes = max_nodes
        self.max_edges = max_edges

    def build(
        self,
        records: Sequence[DatasetRecord],
        interpretation: ResearchInterpretation | None = None,
        semantic_similarity: Mapping[tuple[str, str], float] | None = None,
    ) -> KnowledgeGraphResponse:
        bounded = sorted(records, key=lambda record: record.id)[: self.max_datasets]
        graph = nx.MultiDiGraph()
        for record in bounded:
            graph.add_node(self.dataset_id(record), type="DATASET", label=record.title, source=record.source)
            self._add_record_nodes(graph, record)

        concept_matches: dict[str, set[str]] = {}
        if interpretation is not None:
            concept_matches = self._add_concept_nodes(graph, bounded, interpretation)
        self._add_dataset_relationships(graph, bounded, semantic_similarity or {}, concept_matches)

        node_ids = sorted(graph.nodes)[: self.max_nodes]
        nodes = [GraphNode(data={"id": node_id, **dict(graph.nodes[node_id])}) for node_id in node_ids]
        edges = [
            GraphEdge(data={"id": edge_id, "source": source, "target": target, **dict(attributes)})
            for edge_id, source, target, attributes in self._sorted_edges(graph)
            if source in node_ids and target in node_ids
        ]
        return KnowledgeGraphResponse(nodes=nodes, edges=edges[: self.max_edges])

    @staticmethod
    def dataset_id(record: DatasetRecord) -> str:
        return f"dataset:{record.id}"

    @classmethod
    def _add_record_nodes(cls, graph: nx.MultiDiGraph, record: DatasetRecord) -> None:
        dataset_id = cls.dataset_id(record)
        for variable in sorted(record.variables, key=lambda item: cls._normal_key(item.name)):
            variable_id = f"variable:{cls._normal_key(variable.name)}"
            graph.add_node(variable_id, type="VARIABLE", label=variable.name)
            evidence = f"Verified variable metadata: {variable.name}"
            if variable.description:
                evidence += f" ({variable.description})"
            cls._add_edge(graph, dataset_id, variable_id, "HAS_VARIABLE", evidence, "verified_metadata")
        for value in sorted(record.geographic_coverage, key=cls._normal_key):
            coverage_id = f"geography:{cls._normal_key(value)}"
            graph.add_node(coverage_id, type="GEOGRAPHY", label=value)
            cls._add_edge(graph, dataset_id, coverage_id, "COVERS_GEOGRAPHY", f"Verified geographic coverage: {value}", "verified_metadata")
        for value in sorted(record.temporal_coverage, key=cls._normal_key):
            coverage_id = f"time_period:{cls._normal_key(value)}"
            graph.add_node(coverage_id, type="TIME_PERIOD", label=value)
            cls._add_edge(graph, dataset_id, coverage_id, "COVERS_TIME", f"Verified temporal coverage: {value}", "verified_metadata")

    @classmethod
    def _add_concept_nodes(
        cls, graph: nx.MultiDiGraph, records: Sequence[DatasetRecord], interpretation: ResearchInterpretation
    ) -> dict[str, set[str]]:
        matched_concepts: dict[str, set[str]] = {}
        concepts = cls._concepts(interpretation)
        for concept_id, concept_type, text in concepts:
            node_id = f"concept:{concept_id}"
            graph.add_node(node_id, type="RESEARCH_CONCEPT", label=text, concept_type=concept_type)
            terms = cls._tokens(text)
            for record in records:
                fields = cls._record_fields(record)
                matched_fields = sorted(field for field, values in fields.items() if terms & values)
                if not matched_fields:
                    continue
                matched_concepts.setdefault(record.id, set()).add(concept_id)
                matched = sorted(terms & set().union(*(fields[field] for field in matched_fields)))
                cls._add_edge(
                    graph,
                    node_id,
                    cls.dataset_id(record),
                    "SEMANTICALLY_RELATED",
                    f"Verified metadata matched research concept '{text}' in {', '.join(matched_fields)}: {', '.join(matched)}",
                    "verified_metadata",
                )
        return matched_concepts

    @classmethod
    def _add_dataset_relationships(
        cls,
        graph: nx.MultiDiGraph,
        records: Sequence[DatasetRecord],
        semantic_similarity: Mapping[tuple[str, str], float],
        concept_matches: Mapping[str, set[str]],
    ) -> None:
        for left_index, left in enumerate(records):
            for right in records[left_index + 1 :]:
                left_variables = {cls._normal_key(variable.name) for variable in left.variables}
                right_variables = {cls._normal_key(variable.name) for variable in right.variables}
                shared_variables = sorted(left_variables & right_variables)
                shared_geography = sorted({cls._normal_key(value) for value in left.geographic_coverage} & {cls._normal_key(value) for value in right.geographic_coverage})
                shared_time = sorted({cls._normal_key(value) for value in left.temporal_coverage} & {cls._normal_key(value) for value in right.temporal_coverage})
                pair = (left.id, right.id)
                reverse_pair = (right.id, left.id)
                similarity = semantic_similarity.get(pair, semantic_similarity.get(reverse_pair))
                if similarity is not None and similarity >= 0.75:
                    cls._add_edge(graph, cls.dataset_id(left), cls.dataset_id(right), "SEMANTICALLY_RELATED", f"Explicit embedding similarity: {similarity:.4f}", "embedding_signal")
                left_concepts = concept_matches.get(left.id, set())
                right_concepts = concept_matches.get(right.id, set())
                if left_concepts and right_concepts and left_concepts != right_concepts:
                    cls._add_edge(graph, cls.dataset_id(left), cls.dataset_id(right), "SEMANTICALLY_RELATED", "Complementary verified metadata matches separate research concepts; this relationship does not establish a join.", "verified_metadata")
                if shared_variables:
                    cls._add_edge(graph, cls.dataset_id(left), cls.dataset_id(right), "SHARES_VARIABLE", f"Matching verified variable names: {', '.join(shared_variables)}; names alone do not verify a join.", "metadata_supported")
                # A coverage overlap requires both documented dimensions. A shared
                # year without a shared geography (or vice versa) is too weak to
                # connect otherwise unrelated datasets.
                if shared_geography and shared_time:
                    evidence = []
                    if shared_geography:
                        evidence.append(f"geography={', '.join(shared_geography)}")
                    if shared_time:
                        evidence.append(f"time={', '.join(shared_time)}")
                    cls._add_edge(graph, cls.dataset_id(left), cls.dataset_id(right), "OVERLAPPING_COVERAGE", f"Matching documented coverage: {'; '.join(evidence)}", "metadata_supported")
                if shared_variables and shared_geography and shared_time:
                    cls._add_edge(graph, cls.dataset_id(left), cls.dataset_id(right), "POTENTIAL_JOIN", "Verified variable-name and documented-coverage overlap support investigation of a join; joinability is not verified.", "unverified_potential")

    @staticmethod
    def _concepts(interpretation: ResearchInterpretation) -> list[tuple[str, str, str]]:
        values: list[tuple[str, str, str]] = [("research_subject", "research_subject", interpretation.research_subject)]
        values.extend((f"independent_variable:{index}", "independent_variable", value) for index, value in enumerate(interpretation.independent_variables))
        values.extend((f"dependent_variable:{index}", "dependent_variable", value) for index, value in enumerate(interpretation.dependent_variables))
        if interpretation.target_population:
            values.append(("population_or_geography", "population_or_geography", interpretation.target_population))
        return [(key, kind, text) for key, kind, text in values if text.strip()]

    @classmethod
    def _record_fields(cls, record: DatasetRecord) -> dict[str, set[str]]:
        return {
            "title": cls._tokens(record.title),
            "description": cls._tokens(record.description or ""),
            "subjects": cls._tokens(" ".join(record.subjects)),
            "variables": cls._tokens(" ".join(variable.name for variable in record.variables)),
            "geographic_coverage": cls._tokens(" ".join(record.geographic_coverage)),
            "temporal_coverage": cls._tokens(" ".join(record.temporal_coverage)),
        }

    @staticmethod
    def _tokens(value: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9]+", value.casefold()) if len(token) > 2}

    @staticmethod
    def _normal_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")

    @staticmethod
    def _add_edge(graph: nx.MultiDiGraph, source: str, target: str, relationship_type: str, evidence: str, verification_status: str) -> None:
        edge_id = f"edge:{relationship_type.casefold()}:{source}>{target}"
        graph.add_edge(source, target, key=edge_id, id=edge_id, relationship_type=relationship_type, evidence=evidence, verification_status=verification_status)

    @staticmethod
    def _sorted_edges(graph: nx.MultiDiGraph) -> list[tuple[str, str, str, dict[str, Any]]]:
        return sorted(
            ((attributes["id"], source, target, attributes) for source, target, _, attributes in graph.edges(keys=True, data=True)),
            key=lambda item: item[0],
        )
