"""Property 4: 지원 질의의 결정적 해석과 매칭 (task 3.2).

등록된 각 질의 변형을 fixture가 정의한 용어 대응 및 매칭 결과의 단순 오라클과
비교하고, 같은 입력을 반복 해석해 깊은 동등성을 확인한다.
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from data.models_common import LegalTermMapping
from data.validated_dataset import ValidatedDataset
from domain.query_interpretation import (
    SupportedQueryInterpretation,
    TermCorrespondence,
    interpret_query,
)


# Feature: police-case-law-ai-bot, Property 4: 지원 질의의 결정적 해석과 매칭
@settings(
    max_examples=100,
    derandomize=True,
    print_blob=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    data=st.data(),
    surrounding_whitespace=st.sampled_from(("", " ", "\t", "\n", "  \t")),
)
def test_supported_query_interpretation_matches_fixture_deterministically(
    validated_mock_dataset: ValidatedDataset,
    data: st.DataObject,
    surrounding_whitespace: str,
) -> None:
    """등록 변형은 fixture 정의 대응·매칭을 반환하고 반복 호출에도 동일하다.

    **Validates: Requirements 2.1, 2.2, 2.3, 2.10**
    """

    query = data.draw(
        st.sampled_from(validated_mock_dataset.queries), label="query"
    )
    variant = data.draw(st.sampled_from(query.variants), label="variant")
    raw = (
        f"{surrounding_whitespace}{variant.raw_example}"
        f"{surrounding_whitespace}"
    )

    first = interpret_query(raw, validated_mock_dataset)
    second = interpret_query(raw, validated_mock_dataset)

    assert isinstance(first, SupportedQueryInterpretation)
    assert first == second
    assert first.raw == raw
    assert first.query_id == query.id
    assert first.variant_id == variant.id
    assert first.relation_graph == query.canonical_relations
    assert first.match.case_ids == query.match.case_ids
    assert first.match.statute_version_ids == query.match.statute_version_ids

    mapping_index = {
        mapping.id: mapping for mapping in validated_mock_dataset.term_mappings
    }
    expected_correspondences = tuple(
        _correspondence_from(mapping_index[mapping_id])
        for mapping_id in query.term_mapping_ids
    )
    assert first.term_correspondences == expected_correspondences


def _correspondence_from(mapping: LegalTermMapping) -> TermCorrespondence:
    """Fixture의 선언값을 테스트 오라클용 용어 대응으로 투영한다."""

    return TermCorrespondence(
        term_mapping_id=mapping.id,
        field_expression=mapping.field_expression,
        legal_search_terms=mapping.legal_search_terms,
    )
