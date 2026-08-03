"""Property 6: 빈·미대응·미지원 입력의 안전한 거부 (task 3.4).

For all 공백 전용 입력, 미대응 fragment를 가진 등록 질의, 정규화 인덱스에 없는
비공백 입력에 대해 해석 결과는 INPUT 단계에 머물고 매칭 결과를 제공하지 않는다.

**Validates: Requirements 2.5, 2.6, 2.7, 2.11, 2.12**
"""

from __future__ import annotations

import dataclasses
from typing import Literal

from hypothesis import HealthCheck, given, settings, strategies as st

from data.models_common import LegalTermMapping
from data.validated_dataset import ValidatedDataset
from domain.enums import RagStage
from domain.query_interpretation import (
    BlankQueryInterpretation,
    InterpretationCheckNeededQueryInterpretation,
    UnsupportedQueryInterpretation,
    interpret_query,
)


InputKind = Literal["blank", "unmapped", "unsupported"]

# The str.strip() policy determines whitespace.
# Zero-width characters are excluded.
# The normalizer treats them as nonblank.
_nonblank_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Zl", "Zp")),
    min_size=1,
    max_size=20,
).filter(lambda text: bool(text.strip()))
_blank_inputs = st.text(
    alphabet=st.characters(whitelist_categories=("Zs",)),
    max_size=20,
).map(lambda text: text + "\t\n\r")
_unmapped_fragments = _nonblank_text
_unsupported_inputs = _nonblank_text


# Feature: police-case-law-ai-bot, Property 6
@settings(
    max_examples=100,
    derandomize=True,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    kind=st.sampled_from(("blank", "unmapped", "unsupported")),
    blank_input=_blank_inputs,
    fragment=_unmapped_fragments,
    unsupported_input=_unsupported_inputs,
)
def test_inputs_are_safely_rejected(
    validated_mock_dataset: ValidatedDataset,
    kind: InputKind,
    blank_input: str,
    fragment: str,
    unsupported_input: str,
) -> None:
    """All rejection paths retain INPUT and expose no case/statute matches.

    The unmapped branch uses a registered fixture variant.
    Its mapping declares a generated unmapped fragment.  Fixture metadata,
    not heuristic token inference, determines its unmapped status.
    """

    if kind == "blank":
        result = interpret_query(blank_input, validated_mock_dataset)
        assert isinstance(result, BlankQueryInterpretation)
        assert result.raw == blank_input
    elif kind == "unmapped":
        first_mapping = validated_mock_dataset.term_mappings[0]
        unmapped_mapping: LegalTermMapping = dataclasses.replace(
            first_mapping, unsupported_fragments=(fragment,)
        )
        dataset = dataclasses.replace(
            validated_mock_dataset,
            term_mappings=(
                unmapped_mapping,
            ) + validated_mock_dataset.term_mappings[1:],
        )
        registered_input = dataset.queries[0].variants[0].raw_example

        result = interpret_query(registered_input, dataset)

        assert isinstance(result, InterpretationCheckNeededQueryInterpretation)
        assert result.reason == "UNMAPPED_EXPRESSION"
        assert result.unmapped_fragments == (fragment,)
        assert result.raw == registered_input
    else:
        result = interpret_query(unsupported_input, validated_mock_dataset)
        assert isinstance(result, UnsupportedQueryInterpretation)
        assert result.raw == unsupported_input
        assert result.supported_scenarios == tuple(
            scenario.id for scenario in validated_mock_dataset.scenarios
        )

    assert result.stage is RagStage.INPUT
    assert not hasattr(result, "match")
