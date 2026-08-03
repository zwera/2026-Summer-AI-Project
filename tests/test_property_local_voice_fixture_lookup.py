"""Property 32: 로컬 음성 fixture lookup과 실패 격리 (task 13.4).

Local voice fixtures are the complete input space: a successful fixture must
return its pre-defined recognition text unchanged, while a failing fixture must
not produce recognized text and must keep the caller at the INPUT stage.
"""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from data.fixture_repository import FixtureRepository
from data.models_common import VoiceFixtureId
from data.models_timeline import VoiceFixture
from data.validated_dataset import validate_dataset
from domain.enums import RagStage
from domain.ids import QueryId
from domain.local_voice_demo import (
    RecognizedVoiceText,
    VoiceDemoError,
    recognize_voice_fixture,
)
from domain.result import Err, Ok
from fixtures.mock_dataset import build_mock_dataset


# Successful fixtures must have non-blank, pre-defined text.  Failure fixtures
# deliberately have no text or query match, matching the VoiceFixture contract.
_voice_fixture_cases = st.one_of(
    st.text(min_size=1, max_size=120).map(
        lambda text: VoiceFixture(
            id=VoiceFixtureId("property-32-success"),
            label="Property 32 success fixture",
            failure=False,
            recognized_text=text,
            query_id=QueryId("query-arrest"),
        )
    ),
    st.just(
        VoiceFixture(
            id=VoiceFixtureId("property-32-failure"),
            label="Property 32 failure fixture",
            failure=True,
            recognized_text=None,
            query_id=None,
        )
    ),
)


def _repository_with_voice_fixture(
    voice_fixture: VoiceFixture,
) -> FixtureRepository:
    """Build a validated repository containing the generated voice fixture."""

    dataset = replace(build_mock_dataset(), voice_fixtures=(voice_fixture,))
    result = validate_dataset(dataset)
    assert isinstance(result, Ok)
    return FixtureRepository(result.value)


# Feature: police-case-law-ai-bot
# Property 32: 로컬 음성 fixture lookup과 실패 격리
# **Validates: Requirements 11.1, 11.14**
@settings(max_examples=100, derandomize=True, print_blob=True)
@given(voice_fixture=_voice_fixture_cases)
def test_local_voice_fixture_lookup_returns_text_or_isolates_failure(
    voice_fixture: VoiceFixture,
) -> None:
    """**Validates: Requirements 11.1, 11.14**.

    Every generated local fixture is resolved only by its fixture ID.
    Successful fixtures return their exact pre-defined text.
    Failures produce no recognition result and signal INPUT so a caller can
    without creating a match result.
    """

    result = recognize_voice_fixture(
        voice_fixture.id, _repository_with_voice_fixture(voice_fixture)
    )

    if not voice_fixture.failure:
        assert isinstance(result, Ok)
        assert isinstance(result.value, RecognizedVoiceText)
        assert result.value.text == voice_fixture.recognized_text
        assert result.value.query_id == voice_fixture.query_id
        return

    assert isinstance(result, Err)
    assert isinstance(result.error, VoiceDemoError)
    assert result.error.code == "VOICE_FIXTURE_UNRECOGNIZED"
    assert result.error.stage is RagStage.INPUT
    assert result.error.retryable is True
    assert result.error.affected_record_ids == (str(voice_fixture.id),)
