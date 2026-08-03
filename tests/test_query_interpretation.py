"""``domain.query_interpretation`` 단위 테스트 (task 3.1).

요구사항 2.1~2.11, 15.3(결정성)을 각 분기(BLANK/UNSUPPORTED/
INTERPRETATION_CHECK_NEEDED/SUPPORTED)별로 검증한다.
"""

from __future__ import annotations

import dataclasses
from itertools import permutations

from hypothesis import given, settings, strategies as st

from domain.enums import RagStage
from domain.ids import QueryId
from domain.query_interpretation import (
    BlankQueryInterpretation,
    InterpretationCheckNeededQueryInterpretation,
    NormalizationRules,
    SupportedQueryInterpretation,
    UnsupportedQueryInterpretation,
    interpret_query,
    normalize_for_fixture_match,
    relations_preserved,
)
from data.models_common import ActorActionEdge, NegationTargetEdge, RelationGraph
from data.validated_dataset import ValidatedDataset, validate_dataset
from domain.result import Ok
from fixtures.mock_dataset import build_mock_dataset


def _validated_dataset() -> ValidatedDataset:
    result = validate_dataset(build_mock_dataset())
    assert isinstance(result, Ok)
    return result.value


# --------------------------------------------------------------------------
# normalize_for_fixture_match
# --------------------------------------------------------------------------


def test_normalize_collapses_consecutive_whitespace_and_trims() -> None:
    rules = NormalizationRules()
    result = normalize_for_fixture_match("  경찰관이   현장에서   체포  ", rules)
    assert result.normalized_key == "경찰관이 현장에서 체포"


def test_normalize_preserves_original_raw_string() -> None:
    rules = NormalizationRules()
    raw = "  원문   그대로  "
    result = normalize_for_fixture_match(raw, rules)
    assert result.raw == raw  # 원문은 절대 수정하지 않는다.


def test_normalize_applies_unicode_nfc_form() -> None:
    rules = NormalizationRules()
    # 자모 분리(NFD) 형태의 "가"(ㄱ+ㅏ)를 NFC로 정규화하면 결합된 형태가 된다.
    decomposed = "\u1100\u1161"  # ㄱ + ㅏ (NFD 자모)
    result = normalize_for_fixture_match(decomposed, rules)
    assert result.normalized_key == "가"


# --------------------------------------------------------------------------
# relations_preserved
# --------------------------------------------------------------------------


def _graph(*edges: object) -> RelationGraph:
    return RelationGraph(actors=(), actions=(), times=(), negations=(), edges=tuple(edges))  # type: ignore[arg-type]


def test_relations_preserved_true_for_identical_edge_sets_regardless_of_order() -> None:
    edge_a = ActorActionEdge(type="ACTOR_ACTION", actor="경찰관", action="체포")
    edge_b = NegationTargetEdge(type="NEGATION_TARGET", negation="안", target="체포")
    before = _graph(edge_a, edge_b)
    after = _graph(edge_b, edge_a)  # 순서만 다름
    assert relations_preserved(before, after) is True


def test_relations_preserved_false_when_edge_set_differs() -> None:
    edge_a = ActorActionEdge(type="ACTOR_ACTION", actor="경찰관", action="체포")
    edge_c = ActorActionEdge(type="ACTOR_ACTION", actor="경찰관", action="수색")
    before = _graph(edge_a)
    after = _graph(edge_c)
    assert relations_preserved(before, after) is False


# --------------------------------------------------------------------------
# interpret_query: BLANK
# --------------------------------------------------------------------------


def test_interpret_query_blank_for_empty_string() -> None:
    dataset = _validated_dataset()
    result = interpret_query("", dataset)
    assert isinstance(result, BlankQueryInterpretation)
    assert result.kind == "BLANK"
    assert result.stage == RagStage.INPUT


def test_interpret_query_blank_for_whitespace_only() -> None:
    dataset = _validated_dataset()
    result = interpret_query("   \t\n  ", dataset)
    assert isinstance(result, BlankQueryInterpretation)


# --------------------------------------------------------------------------
# interpret_query: UNSUPPORTED
# --------------------------------------------------------------------------


def test_interpret_query_unsupported_for_unregistered_sentence() -> None:
    dataset = _validated_dataset()
    result = interpret_query("이것은 등록되지 않은 완전히 다른 문장입니다.", dataset)
    assert isinstance(result, UnsupportedQueryInterpretation)
    assert result.stage == RagStage.INPUT
    assert len(result.supported_scenarios) == 8


# --------------------------------------------------------------------------
# interpret_query: SUPPORTED
# --------------------------------------------------------------------------


def test_interpret_query_supported_for_registered_variant() -> None:
    dataset = _validated_dataset()
    query_fixture = dataset.queries_by_id[QueryId("query-arrest")]
    raw_example = query_fixture.variants[0].raw_example

    result = interpret_query(raw_example, dataset)

    assert isinstance(result, SupportedQueryInterpretation)
    assert result.stage == RagStage.INPUT
    assert result.query_id == QueryId("query-arrest")
    assert result.match == query_fixture.match
    assert len(result.term_correspondences) == 1
    correspondence = result.term_correspondences[0]
    assert correspondence.field_expression == "범행 직후 바로 잡기"
    assert correspondence.legal_search_terms == ("현행범체포",)


def test_interpret_query_supported_with_leading_trailing_whitespace() -> None:
    dataset = _validated_dataset()
    query_fixture = dataset.queries_by_id[QueryId("query-arrest")]
    raw_example = query_fixture.variants[0].raw_example

    result = interpret_query(f"   {raw_example}   ", dataset)

    assert isinstance(result, SupportedQueryInterpretation)
    assert result.query_id == QueryId("query-arrest")


# --------------------------------------------------------------------------
# interpret_query: INTERPRETATION_CHECK_NEEDED (relation not preserved / ambiguous)
# --------------------------------------------------------------------------


def test_interpret_query_check_needed_when_relation_not_preserved() -> None:
    dataset = _validated_dataset()
    mapping = dataset.term_mappings[0]
    # actor를 바꿔서 관계 보존이 실패하도록 만든다.
    broken_after = dataclasses.replace(
        mapping.relation_graph_before,
        edges=(ActorActionEdge(type="ACTOR_ACTION", actor="다른사람", action="다른행동"),),
    )
    broken_mapping = dataclasses.replace(mapping, relation_graph_after=broken_after)
    mutated_mappings = (broken_mapping,) + dataset.term_mappings[1:]
    mutated_dataset = dataclasses.replace(dataset, term_mappings=mutated_mappings)

    query_fixture = mutated_dataset.queries_by_id[QueryId("query-arrest")]
    raw_example = query_fixture.variants[0].raw_example

    result = interpret_query(raw_example, mutated_dataset)

    assert isinstance(result, InterpretationCheckNeededQueryInterpretation)
    assert result.reason == "RELATION_NOT_PRESERVED"
    assert result.stage == RagStage.INPUT


def test_interpret_query_check_needed_when_ambiguous_multiple_interpretations() -> None:
    dataset = _validated_dataset()
    mapping = dataset.term_mappings[0]
    before = mapping.relation_graph_before
    # relation_graph_before와 일치하지 않는 두 개의 후보로 복수 해석을 만든다.
    candidate_1 = dataclasses.replace(
        before,
        edges=(ActorActionEdge(type="ACTOR_ACTION", actor="후보1", action="행동1"),),
    )
    candidate_2 = dataclasses.replace(
        before,
        edges=(ActorActionEdge(type="ACTOR_ACTION", actor="후보2", action="행동2"),),
    )
    ambiguous_mapping = dataclasses.replace(
        mapping, relation_graph_after=(candidate_1, candidate_2)
    )
    mutated_mappings = (ambiguous_mapping,) + dataset.term_mappings[1:]
    mutated_dataset = dataclasses.replace(dataset, term_mappings=mutated_mappings)

    query_fixture = mutated_dataset.queries_by_id[QueryId("query-arrest")]
    raw_example = query_fixture.variants[0].raw_example

    result = interpret_query(raw_example, mutated_dataset)

    assert isinstance(result, InterpretationCheckNeededQueryInterpretation)
    assert result.reason == "AMBIGUOUS_RELATION"


def test_interpret_query_check_needed_when_unmapped_fragment_present() -> None:
    dataset = _validated_dataset()
    mapping = dataset.term_mappings[0]
    mapping_with_unsupported = dataclasses.replace(
        mapping, unsupported_fragments=("알 수 없는 표현",)
    )
    mutated_mappings = (mapping_with_unsupported,) + dataset.term_mappings[1:]
    mutated_dataset = dataclasses.replace(dataset, term_mappings=mutated_mappings)

    query_fixture = mutated_dataset.queries_by_id[QueryId("query-arrest")]
    raw_example = query_fixture.variants[0].raw_example

    result = interpret_query(raw_example, mutated_dataset)

    assert isinstance(result, InterpretationCheckNeededQueryInterpretation)
    assert result.reason == "UNMAPPED_EXPRESSION"
    assert result.unmapped_fragments == ("알 수 없는 표현",)


# --------------------------------------------------------------------------
# 결정성 (요구사항 2.17, 15.3)
# --------------------------------------------------------------------------


def test_interpret_query_is_deterministic_across_repeated_calls() -> None:
    dataset = _validated_dataset()
    query_fixture = dataset.queries_by_id[QueryId("query-arrest")]
    raw_example = query_fixture.variants[0].raw_example

    first = interpret_query(raw_example, dataset)
    second = interpret_query(raw_example, dataset)

    assert first == second


def test_interpret_query_is_deterministic_for_blank_and_unsupported_inputs() -> None:
    dataset = _validated_dataset()

    assert interpret_query("", dataset) == interpret_query("", dataset)
    assert interpret_query("미등록 문장", dataset) == interpret_query("미등록 문장", dataset)


# Feature: police-case-law-ai-bot, Property 24: 명시 시점 동일 핵심 사실의 문장 순열 불변성
# Validates: Requirements 8.12
@settings(max_examples=100, derandomize=True)
@given(
    fact_set_number=st.integers(min_value=0, max_value=1_000_000),
    sentence_order=st.permutations((0, 1, 2)),
)
def test_explicit_time_sentence_order_permutations_preserve_match_and_similarity(
    fact_set_number: int, sentence_order: tuple[int, int, int]
) -> None:
    """Registered permutations of one explicit-time fact set resolve identically."""

    base_dataset = build_mock_dataset()
    base_query = next(
        query for query in base_dataset.queries if query.id == QueryId("query-arrest")
    )
    sentences = (
        f"2024-01-01 09:00 경찰관이 대상자를 제지했다. 사건 {fact_set_number}",
        f"2024-01-01 09:05 경찰관이 권리를 고지했다. 사건 {fact_set_number}",
        f"2024-01-01 09:10 경찰관이 현장 기록을 작성했다. 사건 {fact_set_number}",
    )
    variants = tuple(
        dataclasses.replace(
            base_query.variants[0],
            id=f"explicit-time-{fact_set_number}-{'-'.join(map(str, order))}",
            raw_example=" ".join(sentences[index] for index in order),
            normalized_key=" ".join(sentences[index] for index in order),
            explicit_time_core_facts=sentences,
        )
        for order in permutations((0, 1, 2))
    )
    explicit_time_query = dataclasses.replace(
        base_query,
        core_fact_set_id=f"explicit-time-core-facts-{fact_set_number}",
        variants=variants,
    )
    raw_dataset = dataclasses.replace(
        base_dataset,
        queries=tuple(
            explicit_time_query if query.id == explicit_time_query.id else query
            for query in base_dataset.queries
        ),
    )
    validation = validate_dataset(raw_dataset)
    assert isinstance(validation, Ok)
    dataset = validation.value

    canonical = interpret_query(" ".join(sentences), dataset)
    permuted = interpret_query(
        " ".join(sentences[index] for index in sentence_order), dataset
    )

    assert isinstance(canonical, SupportedQueryInterpretation)
    assert isinstance(permuted, SupportedQueryInterpretation)
    canonical_query = dataset.queries_by_id[canonical.query_id]
    permuted_query = dataset.queries_by_id[permuted.query_id]

    assert canonical_query.core_fact_set_id == permuted_query.core_fact_set_id
    assert set(canonical.match.case_ids) == set(permuted.match.case_ids)
    assert {
        case_id: preset.score for case_id, preset in canonical_query.similarity_by_case.items()
    } == {
        case_id: preset.score for case_id, preset in permuted_query.similarity_by_case.items()
    }
