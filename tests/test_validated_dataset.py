"""``data.validated_dataset`` 불투명 ``ValidatedDataset`` 생성 단위 테스트 (task 2.2).

최소 유효 fixture는 ``Ok(ValidatedDataset)``으로 성공해야 하고, ``FATAL`` 진단을 유발하는
mutation은 ``Err``로 안전 실패해야 하며 ``ValidatedDataset``이 전혀 생성되지 않아야 한다.
``WARNING``만 유발하는 mutation은 해당 레코드가 격리된 clean 뷰로 ``Ok``를 반환해야 한다.
"""

from __future__ import annotations

import dataclasses

import pytest

from data.validated_dataset import ValidatedDataset, validate_dataset
from domain.ids import SourceId
from domain.result import Err, Ok
from fixtures.mock_dataset import build_mock_dataset


def test_valid_fixture_produces_ok_validated_dataset_with_no_warnings() -> None:
    dataset = build_mock_dataset()
    result = validate_dataset(dataset)

    assert isinstance(result, Ok)
    validated = result.value
    assert isinstance(validated, ValidatedDataset)
    assert validated.diagnostics == ()
    assert len(validated.cases) == len(dataset.cases)
    assert len(validated.sources) == len(dataset.sources)
    assert len(validated.queries) == len(dataset.queries)


def test_fatal_duplicate_id_produces_err_without_constructing_dataset() -> None:
    dataset = build_mock_dataset()
    duplicated = dataclasses.replace(dataset.cases[1], id=dataset.cases[0].id)
    mutated_cases = (dataset.cases[0], duplicated) + dataset.cases[2:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    result = validate_dataset(mutated)

    assert isinstance(result, Err)
    codes = {d.code for d in result.error}
    assert "DUPLICATE_CASE_ID" in codes


def test_warning_only_mutation_isolates_record_but_still_produces_ok() -> None:
    dataset = build_mock_dataset()
    case = dataset.cases[0]
    bad_case = dataclasses.replace(case, source_ids=(SourceId("source-does-not-exist"),))
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    result = validate_dataset(mutated)

    assert isinstance(result, Ok)
    validated = result.value
    assert case.id not in {c.id for c in validated.cases}
    assert len(validated.cases) == len(dataset.cases) - 1
    codes = {d.code for d in validated.diagnostics}
    assert "DANGLING_SOURCE_REFERENCE" in codes


def test_warning_only_mutation_preserves_unaffected_records() -> None:
    """레코드_격리는 위반된 레코드만 제외하고 나머지는 그대로 유지해야 한다."""

    dataset = build_mock_dataset()
    case = dataset.cases[0]
    bad_case = dataclasses.replace(case, source_ids=(SourceId("source-does-not-exist"),))
    mutated_cases = (bad_case,) + dataset.cases[1:]
    mutated = dataclasses.replace(dataset, cases=mutated_cases)

    result = validate_dataset(mutated)
    assert isinstance(result, Ok)
    validated = result.value

    remaining_ids = {c.id for c in validated.cases}
    for other_case in dataset.cases[1:]:
        assert other_case.id in remaining_ids
    # 다른 컬렉션(출처·질의 등)은 이 mutation과 무관하므로 그대로 유지되어야 한다.
    assert len(validated.sources) == len(dataset.sources)


def test_validated_dataset_cannot_be_constructed_directly() -> None:
    """``ValidatedDataset``은 ``validate_dataset``을 통해서만 생성할 수 있어야 한다."""

    dataset = build_mock_dataset()
    result = validate_dataset(dataset)
    assert isinstance(result, Ok)
    validated = result.value

    with pytest.raises(RuntimeError):
        ValidatedDataset(
            _construction_token=object(),
            schema_version=validated.schema_version,
            dataset_id=validated.dataset_id,
            dataset_version=validated.dataset_version,
            normalization_version=validated.normalization_version,
            as_of_date=validated.as_of_date,
            target_coverage_label=validated.target_coverage_label,
            implemented_coverage_label=validated.implemented_coverage_label,
            legal_safety_notice=validated.legal_safety_notice,
            instance_caution_notice=validated.instance_caution_notice,
            no_realtime_sync_label=validated.no_realtime_sync_label,
            scenarios=validated.scenarios,
            term_mappings=validated.term_mappings,
            statutes=validated.statutes,
            statute_versions=validated.statute_versions,
            display_policies=validated.display_policies,
            cases=validated.cases,
            queries=validated.queries,
            sources=validated.sources,
            response_templates=validated.response_templates,
            review_fixtures=validated.review_fixtures,
            voice_fixtures=validated.voice_fixtures,
            diagnostics=validated.diagnostics,
        )


def test_cases_by_id_accessor_matches_clean_collection() -> None:
    dataset = build_mock_dataset()
    result = validate_dataset(dataset)
    assert isinstance(result, Ok)
    validated = result.value

    by_id = validated.cases_by_id
    assert len(by_id) == len(validated.cases)
    for case in validated.cases:
        assert by_id[case.id] is case
