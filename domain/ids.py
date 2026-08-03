"""식별자(branded ID) 타입.

설계 문서의 다음 TypeScript 계약 의사코드를 Python으로 옮긴다::

    type DatasetId = string & { readonly __brand: "DatasetId" };
    type QueryId = string & { readonly __brand: "QueryId" };
    type CaseId = string & { readonly __brand: "CaseId" };
    type StatuteVersionId = string & { readonly __brand: "StatuteVersionId" };
    type SourceId = string & { readonly __brand: "SourceId" };
    type ClaimId = string & { readonly __brand: "ClaimId" };
    type EventId = string & { readonly __brand: "EventId" };

Python에는 TypeScript의 intersection 타입이 없으므로, ``typing.NewType``으로 런타임에는
``str``과 동일하지만 정적 타입 검사(mypy) 단계에서는 서로 다른 타입으로 구분되는 "branded"
식별자를 만든다. 예를 들어 ``CaseId``가 필요한 곳에 순수 ``str``이나 ``SourceId``를 전달하면
mypy가 오류를 낸다. 런타임에는 각 값이 여전히 일반 문자열이므로 JSON (역)직렬화에 추가 처리가
필요 없다.

각 ID 값은 데이터셋 전체에서 유일해야 하며(설계 문서 "데이터 무결성 검증" 참조), 이 모듈은
타입 표시만 제공하고 유일성 검증은 ``data`` 패키지의 검증기가 담당한다.
"""

from __future__ import annotations

from typing import NewType

DatasetId = NewType("DatasetId", str)
"""목업 데이터셋 전체를 가리키는 식별자."""

QueryId = NewType("QueryId", str)
"""``QueryFixture`` 레코드를 가리키는 식별자."""

CaseId = NewType("CaseId", str)
"""``CaseRecord`` 레코드를 가리키는 식별자."""

StatuteVersionId = NewType("StatuteVersionId", str)
"""``StatuteVersion`` 레코드를 가리키는 식별자."""

SourceId = NewType("SourceId", str)
"""``SourceRecord`` 레코드를 가리키는 식별자. 데이터셋 전체에서 유일하며 정확히 하나의
``SourceRecord``에 해석된다."""

ClaimId = NewType("ClaimId", str)
"""응답 template의 ``LEGAL_CLAIM`` 블록(독립 주장)을 가리키는 식별자."""

EventId = NewType("EventId", str)
"""사실관계 타임라인의 인식_사건(``RecognizedEvent``)을 가리키는 식별자."""
