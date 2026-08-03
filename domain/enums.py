"""도메인 열거형.

설계 문서(Data Models, 핵심 포트와 함수 시그니처, 상태 모델)에 정의된 열거형을 Python으로
구현한다. 모든 열거형은 ``str``을 함께 상속해 JSON 직렬화 시 값 그대로(예: ``"적법"``,
``"INPUT"``) 사용할 수 있게 한다. 값 문자열은 설계 문서의 리터럴과 정확히 일치해야 하며,
새 문구를 만들어 내지 않는다(요구사항 15.6, Correctness Property 1).
"""

from __future__ import annotations

from enum import Enum


class PoliceScenario(str, Enum):
    """경찰_직무_시나리오. 요구사항 4.1의 8개 탐색 항목.

    ``design.md`` Data Models 3절의 ``PoliceScenario`` 유니온과 동일하다.
    """

    FLAGRANT_OFFENDER_ARREST = "현행범체포"
    VOLUNTARY_ACCOMPANIMENT = "임의동행"
    EMERGENCY_ARREST = "긴급체포"
    SEARCH_AND_SEIZURE = "압수수색"
    MIRANDA_WARNING = "미란다 원칙 고지"
    RIGHT_TO_REMAIN_SILENT = "진술거부권"
    DOMESTIC_VIOLENCE_INITIAL_RESPONSE = "가정폭력 초동조치"
    DUI_CHECKPOINT = "음주단속"


class TraditionalCaseArea(str, Enum):
    """보조_필터로 제공되는 전통적 사건 분야. ``design.md`` Data Models 3절."""

    CRIMINAL = "형사"
    CIVIL = "민사"
    ADMINISTRATIVE = "행정"


class LegalityStatus(str, Enum):
    """적법성_상태. 판례 속 경찰 행위에 대한 법원 판단(요구사항 4.4)."""

    LAWFUL = "적법"
    UNLAWFUL = "위법"
    MIXED = "판단_혼재"


class LawBasisStatus(str, Enum):
    """법령_기준_상태. ``classifyLawStatus``의 반환 값(요구사항 10.5)."""

    CURRENT_LAW_BASIS = "현행법_기준"
    OLD_LAW_BASIS = "구법_기준"
    INDETERMINATE = "법령_상태_판별불가"


class SummaryLevel(str, Enum):
    """요약_단계. 3줄_요약, 10줄_요약, 상세_요약 (요구사항 5.1)."""

    THREE_LINE = "3줄_요약"
    TEN_LINE = "10줄_요약"
    DETAILED = "상세_요약"


class RagStage(str, Enum):
    """목업_RAG_단계. 입력 → 목업_검색 → 근거_제시 → 응답 순서로만 진행한다(요구사항 1.3).

    ``design.md`` Data Models 12절의 ``RagStage`` 유니온과 동일하다.
    """

    INPUT = "INPUT"
    MOCK_SEARCH = "MOCK_SEARCH"
    EVIDENCE = "EVIDENCE"
    RESPONSE = "RESPONSE"


class StageStatus(str, Enum):
    """목업_RAG 단계별 상태. 한 시점에 ``ACTIVE``는 정확히 하나여야 한다.

    ``design.md`` "목업 RAG 파이프라인과 상태 모델" 절 참조.
    """

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"


class EvidenceStatus(str, Enum):
    """근거_상태. 선택 영역 재검토에서 독립_주장과 목업_출처의 관계(요구사항 9.8, design.md 4.7절)."""

    MATCH = "근거_일치"
    CONFLICT = "근거_충돌"
    INSUFFICIENT = "근거_부족"
