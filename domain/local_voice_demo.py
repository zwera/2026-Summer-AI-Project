"""로컬 음성 시연 lookup과 실패 격리 (task 13.1).

``design.md`` "핵심 포트와 함수 시그니처"의 다음 계약을 구현한다::

    interface LocalVoiceDemoPort {
      recognize(fixtureId: VoiceFixtureId): Result<RecognizedVoiceText, VoiceDemoError>;
    }

이 모듈은 사전_정의_음성_시연(``VoiceFixture``)을 ID로 조회해 사전 정의 인식 텍스트를
그대로 반환하는 순수 함수만 제공한다. 실제 또는 원격 음성 인식 처리를 호출하지 않으며
(요구사항 11.2), 마이크 원본이나 오디오 데이터를 다루지 않는다 — 조회 대상은 항상 로컬
``ValidatedDataset``에 이미 들어 있는 ``VoiceFixture`` 레코드다.

## 성공/실패 판정 (요구사항 11.1, 11.3, 11.18~11.20)

``recognize_voice_fixture``는 세 경우를 구분한다.

1. **알 수 없는 fixture ID**: ``FixtureRepository.get_voice_fixture``가 ``None``을
   반환하면 조회 자체가 불가능하다는 뜻이다. 존재하지 않는 음성 ID도 "인식 텍스트 없음"과
   동일하게 취급해 ``Err(VoiceDemoError)``를 반환한다(Property 32 경계 사례: "존재하지
   않는 voice ID").
2. **실패 fixture** (``VoiceFixture.failure=True`` 또는 ``recognized_text`` 없음): 요구사항
   11.18 "인식 텍스트가 없으면 목업_RAG_단계를 입력 상태로 유지한다"를 만족하도록
   ``Err(VoiceDemoError(code="VOICE_FIXTURE_UNRECOGNIZED", stage=RagStage.INPUT, ...))``을
   반환한다. 호출자(향후 상태 관리 계층)는 이 오류를 받으면 ``RagStage.INPUT``에 머물고
   매칭 결과를 만들지 않으며, 클라이언트_웹_계층이 수동 텍스트 입력 수단을 제공할 수 있게
   한다(요구사항 11.19). 이 함수 자체는 상태를 갖지 않으므로 "INPUT 단계 유지"는 오류를
   전달만 하고, 실제 단계 전이 로직은 이후 오케스트레이터(task 15.x)의 책임이다.
3. **성공 fixture**: ``recognized_text``를 원본 그대로 담은 ``RecognizedVoiceText``를
   ``Ok``로 반환한다(요구사항 11.3, 11.20 "변경 없이 표시"). 텍스트를 다듬거나 재가공하지
   않는다.

이 함수는 어떤 I/O도 하지 않는다 — ``FixtureRepository``를 통한 순수 dict 조회뿐이며,
네트워크·마이크·원격 API 호출은 0건이다(요구사항 11.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from domain.enums import RagStage
from domain.ids import QueryId
from domain.result import Err, Ok, Result

from data.fixture_repository import FixtureRepository
from data.models_common import VoiceFixtureId

__all__ = [
    "RecognizedVoiceText",
    "VoiceDemoError",
    "recognize_voice_fixture",
]


@dataclass(frozen=True)
class RecognizedVoiceText:
    """``recognize_voice_fixture``의 성공 결과. design.md ``RecognizedVoiceText``.

    ``text``는 ``VoiceFixture.recognized_text``를 변경 없이 옮긴 값이다(요구사항 11.3,
    11.20). ``query_id``는 이 인식 텍스트가 사전 연결된 ``QueryFixture``가 있으면 그 ID를
    그대로 옮긴 것으로, 이후 태스크(질의 해석·타임라인 구성)가 재조회 없이 재사용할 수
    있게 한다.
    """

    text: str
    query_id: Optional[QueryId]


@dataclass(frozen=True)
class VoiceDemoError:
    """``recognize_voice_fixture``의 실패 결과. design.md Data Models 12절
    ``MockRagError``의 판별 유니온 중 ``LocalVoiceDemoPort``가 반환하는
    ``"VOICE_FIXTURE_UNRECOGNIZED"`` 변형만 이 모듈에서 사용한다.

    ``stage``는 항상 ``RagStage.INPUT``이다 — 인식 실패는 목업_RAG_단계를 입력 상태로
    유지시킨다(요구사항 11.18).
    """

    code: str
    stage: RagStage
    retryable: bool
    affected_record_ids: Tuple[str, ...]


def recognize_voice_fixture(
    fixture_id: VoiceFixtureId, repo: FixtureRepository
) -> "Result[RecognizedVoiceText, VoiceDemoError]":
    """``fixture_id``에 해당하는 ``VoiceFixture``를 조회해 인식 결과를 반환한다.

    실제·원격 음성 인식 호출은 하지 않는다(요구사항 11.2) — ``FixtureRepository``의 순수
    ID 조회만 수행한다. 존재하지 않는 ID, 실패로 표시된 fixture, 인식 텍스트가 없는
    fixture는 모두 ``Err(VoiceDemoError)``로 통일해 반환하며, 이 경우 호출자는 목업_RAG_
    단계를 ``INPUT``으로 유지하고 매칭 결과를 만들지 않아야 한다(요구사항 11.18, 11.19).
    """

    voice_fixture = repo.get_voice_fixture(fixture_id)

    if (
        voice_fixture is None
        or voice_fixture.failure
        or voice_fixture.recognized_text is None
    ):
        affected_id = str(voice_fixture.id) if voice_fixture is not None else str(fixture_id)
        return Err(
            VoiceDemoError(
                code="VOICE_FIXTURE_UNRECOGNIZED",
                stage=RagStage.INPUT,
                retryable=True,
                affected_record_ids=(affected_id,),
            )
        )

    return Ok(
        RecognizedVoiceText(
            text=voice_fixture.recognized_text,
            query_id=voice_fixture.query_id,
        )
    )
