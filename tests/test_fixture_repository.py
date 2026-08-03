"""``data.fixture_repository.FixtureRepository`` 단위 테스트 (task 5.1)."""

from __future__ import annotations

from data.fixture_repository import DatasetMetadata, FixtureRepository
from data.models_common import VoiceFixtureId
from data.validated_dataset import validate_dataset
from domain.enums import PoliceScenario
from domain.ids import CaseId, SourceId, StatuteVersionId
from domain.result import Ok
from fixtures.mock_dataset import build_mock_dataset


def _build_repo() -> FixtureRepository:
    dataset = build_mock_dataset()
    result = validate_dataset(dataset)
    assert isinstance(result, Ok)
    return FixtureRepository(result.value)


def test_metadata_returns_dataset_scalar_fields_verbatim() -> None:
    dataset = build_mock_dataset()
    result = validate_dataset(dataset)
    assert isinstance(result, Ok)
    validated = result.value
    repo = FixtureRepository(validated)

    meta = repo.metadata()

    assert isinstance(meta, DatasetMetadata)
    assert meta.dataset_id == validated.dataset_id
    assert meta.as_of_date == validated.as_of_date
    assert meta.legal_safety_notice == validated.legal_safety_notice
    assert meta.instance_caution_notice == validated.instance_caution_notice
    assert meta.no_realtime_sync_label == validated.no_realtime_sync_label


def test_supported_scenarios_returns_dataset_scenario_ids() -> None:
    repo = _build_repo()

    scenarios = repo.supported_scenarios()

    assert PoliceScenario.FLAGRANT_OFFENDER_ARREST in scenarios
    assert PoliceScenario.DUI_CHECKPOINT in scenarios
    assert len(scenarios) == len(set(scenarios))


def test_get_case_resolves_known_id() -> None:
    repo = _build_repo()

    case = repo.get_case(CaseId("case-arrest-lawful"))

    assert case is not None
    assert case.id == CaseId("case-arrest-lawful")


def test_get_case_returns_none_for_unknown_id() -> None:
    repo = _build_repo()

    assert repo.get_case(CaseId("case-does-not-exist")) is None


def test_get_statute_version_resolves_known_id() -> None:
    repo = _build_repo()

    version = repo.get_statute_version(
        StatuteVersionId("statute-version-criminal-act-125")
    )

    assert version is not None
    assert version.article == "제125조"


def test_get_statute_version_returns_none_for_unknown_id() -> None:
    repo = _build_repo()

    assert repo.get_statute_version(StatuteVersionId("no-such-version")) is None


def test_get_source_resolves_known_id() -> None:
    repo = _build_repo()

    source = repo.get_source(SourceId("source-arrest-lawful"))

    assert source is not None
    assert source.id == SourceId("source-arrest-lawful")


def test_get_source_returns_none_for_unknown_id() -> None:
    repo = _build_repo()

    assert repo.get_source(SourceId("no-such-source")) is None


def test_get_statute_resolves_law_name_from_statute_id() -> None:
    repo = _build_repo()

    statute = repo.get_statute("statute-criminal-act")

    assert statute is not None
    assert statute.law_name == "형법"


def test_find_query_by_normalized_variant_resolves_known_key() -> None:
    dataset = build_mock_dataset()
    repo = _build_repo()
    query = dataset.queries[0]
    variant = query.variants[0]

    found = repo.find_query_by_normalized_variant(variant.normalized_key)

    assert found is not None
    assert found.id == query.id


def test_find_query_by_normalized_variant_returns_none_for_unknown_key() -> None:
    repo = _build_repo()

    assert repo.find_query_by_normalized_variant("존재하지 않는 정규화 키") is None


def test_get_voice_fixture_resolves_known_id() -> None:
    dataset = build_mock_dataset()
    repo = _build_repo()
    expected = dataset.voice_fixtures[0]

    voice_fixture = repo.get_voice_fixture(expected.id)

    assert voice_fixture is not None
    assert voice_fixture.id == expected.id


def test_get_voice_fixture_returns_none_for_unknown_id() -> None:
    repo = _build_repo()

    assert repo.get_voice_fixture(VoiceFixtureId("voice-does-not-exist")) is None
