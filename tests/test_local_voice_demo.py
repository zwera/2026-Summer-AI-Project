"""``domain.local_voice_demo.recognize_voice_fixture`` 단위 테스트 (task 13.1).

성공 ``VoiceFixture``는 사전 정의 인식 텍스트를 정확히 반환하고, 실패/무인식/존재하지
않는 ID는 모두 ``Err(VoiceDemoError)``로 통일되어 INPUT 단계 유지·매칭 없음 상태를
나타냄을 검증한다. 이 테스트는 실제·원격 음성 인식을 전혀 호출하지 않는다 — 순수 fixture
lookup만 확인한다.
"""

from __future__ import annotations

from data.fixture_repository import FixtureRepository
from data.validated_dataset import validate_dataset
from domain.enums import RagStage
from domain.local_voice_demo import RecognizedVoiceText, VoiceDemoError, recognize_voice_fixture
from domain.result import Err, Ok
from data.models_common import VoiceFixtureId
from fixtures.mock_dataset import build_mock_dataset


def _build_repo() -> FixtureRepository:
    dataset = build_mock_dataset()
    result = validate_dataset(dataset)
    assert isinstance(result, Ok)
    return FixtureRepository(result.value)


def test_success_fixture_returns_predefined_recognized_text_verbatim() -> None:
    dataset = build_mock_dataset()
    repo = _build_repo()
    success_fixture = next(v for v in dataset.voice_fixtures if not v.failure)

    result = recognize_voice_fixture(success_fixture.id, repo)

    assert isinstance(result, Ok)
    recognized = result.value
    assert isinstance(recognized, RecognizedVoiceText)
    assert recognized.text == success_fixture.recognized_text
    assert recognized.query_id == success_fixture.query_id


def test_failure_fixture_returns_err_with_input_stage_and_no_match() -> None:
    dataset = build_mock_dataset()
    repo = _build_repo()
    failure_fixture = next(v for v in dataset.voice_fixtures if v.failure)
    assert failure_fixture.recognized_text is None

    result = recognize_voice_fixture(failure_fixture.id, repo)

    assert isinstance(result, Err)
    error = result.error
    assert isinstance(error, VoiceDemoError)
    assert error.code == "VOICE_FIXTURE_UNRECOGNIZED"
    assert error.stage == RagStage.INPUT
    assert str(failure_fixture.id) in error.affected_record_ids


def test_unknown_fixture_id_returns_err_not_crashing() -> None:
    repo = _build_repo()
    unknown_id = VoiceFixtureId("voice-does-not-exist")

    result = recognize_voice_fixture(unknown_id, repo)

    assert isinstance(result, Err)
    error = result.error
    assert error.code == "VOICE_FIXTURE_UNRECOGNIZED"
    assert error.stage == RagStage.INPUT
    assert str(unknown_id) in error.affected_record_ids


def test_recognize_does_not_mutate_or_reprocess_text() -> None:
    """성공 텍스트는 가공 없이 그대로 반환되어야 한다(요구사항 11.3, 11.20)."""

    dataset = build_mock_dataset()
    repo = _build_repo()
    success_fixture = next(v for v in dataset.voice_fixtures if not v.failure)

    result = recognize_voice_fixture(success_fixture.id, repo)

    assert isinstance(result, Ok)
    assert result.value.text is success_fixture.recognized_text
