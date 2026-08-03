"""읽기 전용 fixture 조회 포트 ``FixtureRepository`` (task 5.1).

``design.md`` "핵심 포트와 함수 시그니처"의 다음 계약을 구현한다::

    interface FixtureRepository {
      metadata(): DatasetMetadata;
      supportedScenarios(): readonly PoliceScenario[];
      findQueryByNormalizedVariant(key: string): QueryFixture | undefined;
      getCase(id: CaseId): CaseRecord | undefined;
      getStatuteVersion(id: StatuteVersionId): StatuteVersion | undefined;
      getSource(id: SourceId): SourceRecord | undefined;
    }

``design.md``는 이 인터페이스를 "현재 범위에서 허용할 런타임 포트" 중 하나로 못박고
``ValidatedDataset``(교차 참조 검증된 읽기 전용 데이터)만 감싸도록 요구한다. 이 모듈은
그 계약을 그대로 구현하되 두 가지를 보강한다.

1. ``metadata()``가 반환하는 ``DatasetMetadata``는 design.md Data Models 절에 필드가
   명시되지 않은 타입이다("목업 단계"·"애플리케이션 상태" 절에서 이름만 참조된다). 이
   모듈은 ``ValidatedDataset``의 컬렉션이 아닌 최상위 스칼라 필드(데이터셋 식별자·버전·
   기준일·고정 고지문 등)를 그대로 모은 최소 해석을 제공한다. 새 문구를 만들지 않고
   ``ValidatedDataset``에 이미 있는 값만 재노출한다.
2. ``getStatuteVersion``만으로는 법조문 결과의 "법령명" 표시(요구사항 3.7 "법령명, 조·항·호
   및 시행일")에 필요한 ``StatuteRecord.lawName``을 얻을 수 없다 — ``StatuteVersion``은
   ``statuteId`` 문자열 참조만 가지고 법령명 필드가 없다. 따라서 design.md 계약 표에는
   글자 그대로 없는 ``get_statute(statute_id)``를 추가해 법조문 검색 projection이 법령명을
   조회할 수 있게 한다. 이는 design.md의 "계약 의사코드"(특정 API를 뜻하지 않는 계약
   표기)를 요구사항 충족에 필요한 만큼 보강한 것일 뿐, 새 포트 종류(검색 엔진 등)를
   도입하는 것이 아니다 — 여전히 같은 ``ValidatedDataset``의 읽기 전용 ID 조회다.

인덱스(``dict``)는 생성자에서 한 번만 만들고, 이후 모든 조회 메서드는 이 인덱스에서 값을
찾기만 한다. 값을 계산하거나 데이터셋을 다시 순회하지 않는다(재계산 없음, 요구사항
7.6·15.5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from domain.enums import PoliceScenario
from domain.ids import CaseId, SourceId, StatuteVersionId

from data.models_case import CaseRecord
from data.models_common import DisplayPolicyRecord, IsoDate, VoiceFixtureId
from data.models_query import QueryFixture
from data.models_source import SourceRecord
from data.models_statute import StatuteRecord, StatuteVersion
from data.models_timeline import VoiceFixture
from data.validated_dataset import ValidatedDataset

__all__ = ["DatasetMetadata", "FixtureRepository"]


@dataclass(frozen=True)
class DatasetMetadata:
    """``ValidatedDataset``의 최상위 스칼라 메타데이터.

    design.md가 참조하는 ``DatasetMetadata``는 필드가 명세되어 있지 않으므로, 이
    dataclass는 ``ValidatedDataset``의 컬렉션(판례·법조문·질의 등)이 아닌 필드를 그대로
    모은 최소 해석이다. 값은 모두 ``ValidatedDataset``에서 그대로 옮긴 것이며 새로 만든
    문구가 아니다.
    """

    dataset_id: str
    dataset_version: str
    schema_version: str
    normalization_version: str
    as_of_date: IsoDate
    target_coverage_label: str
    implemented_coverage_label: str
    legal_safety_notice: str
    instance_caution_notice: str
    no_realtime_sync_label: str


class FixtureRepository:
    """``ValidatedDataset``을 감싸는 읽기 전용 fixture 조회 포트.

    생성자에서 판례·법조문 버전·법령·출처의 ID 인덱스와 질의 변형의 정규화 키 인덱스를
    한 번만 만든다. 이후 모든 조회 메서드는 이 인덱스에서 O(1)로 값을 찾을 뿐이다.
    """

    def __init__(self, dataset: ValidatedDataset) -> None:
        self._dataset = dataset
        self._cases_by_id: Dict[CaseId, CaseRecord] = {case.id: case for case in dataset.cases}
        self._statute_versions_by_id: Dict[StatuteVersionId, StatuteVersion] = {
            version.id: version for version in dataset.statute_versions
        }
        self._statutes_by_id: Dict[str, StatuteRecord] = {
            statute.id: statute for statute in dataset.statutes
        }
        self._sources_by_id: Dict[SourceId, SourceRecord] = {
            source.id: source for source in dataset.sources
        }
        self._voice_fixtures_by_id: Dict[VoiceFixtureId, VoiceFixture] = {
            voice_fixture.id: voice_fixture for voice_fixture in dataset.voice_fixtures
        }
        self._queries_by_normalized_key: Dict[str, QueryFixture] = {
            variant.normalized_key: query
            for query in dataset.queries
            for variant in query.variants
        }
        policy_records = (
            dataset.display_policies.notices
            + dataset.display_policies.placeholders
            + dataset.display_policies.status_labels
        )
        self._display_policies_by_key = {
            policy.key: policy for policy in policy_records
        }

    def metadata(self) -> DatasetMetadata:
        """design.md ``FixtureRepository.metadata()``."""

        dataset = self._dataset
        return DatasetMetadata(
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.dataset_version,
            schema_version=dataset.schema_version,
            normalization_version=dataset.normalization_version,
            as_of_date=dataset.as_of_date,
            target_coverage_label=dataset.target_coverage_label,
            implemented_coverage_label=dataset.implemented_coverage_label,
            legal_safety_notice=dataset.legal_safety_notice,
            instance_caution_notice=dataset.instance_caution_notice,
            no_realtime_sync_label=dataset.no_realtime_sync_label,
        )

    def supported_scenarios(self) -> Tuple[PoliceScenario, ...]:
        """design.md ``FixtureRepository.supportedScenarios()``.

        ``dataset.scenarios``(``ScenarioDefinition`` 목록)의 ``id``를 순서를 유지한 채
        중복 제거하여 반환한다.
        """

        return tuple(dict.fromkeys(scenario.id for scenario in self._dataset.scenarios))

    def find_query_by_normalized_variant(self, normalized_key: str) -> Optional[QueryFixture]:
        """design.md ``FixtureRepository.findQueryByNormalizedVariant(key)``.

        ``normalized_key``는 이미 정규화된 비교용 키다(정규화 자체는 이 저장소의 책임이
        아니라 task 3.1 ``normalizeForFixtureMatch``의 책임이다).
        """

        return self._queries_by_normalized_key.get(normalized_key)

    def get_case(self, case_id: CaseId) -> Optional[CaseRecord]:
        """design.md ``FixtureRepository.getCase(id)``."""

        return self._cases_by_id.get(case_id)

    def get_statute_version(self, statute_version_id: StatuteVersionId) -> Optional[StatuteVersion]:
        """design.md ``FixtureRepository.getStatuteVersion(id)``."""

        return self._statute_versions_by_id.get(statute_version_id)

    def get_source(self, source_id: SourceId) -> Optional[SourceRecord]:
        """design.md ``FixtureRepository.getSource(id)``."""

        return self._sources_by_id.get(source_id)

    def get_statute(self, statute_id: str) -> Optional[StatuteRecord]:
        """design.md 계약 표에는 글자 그대로 없지만, 법조문 검색 결과의 법령명
        projection(요구사항 3.7)에 필요해 추가한 조회 메서드. ``StatuteVersion.statute_id``
        문자열로 ``StatuteRecord``를 찾는다.
        """

        return self._statutes_by_id.get(statute_id)

    def get_display_policy(self, key: str) -> Optional[DisplayPolicyRecord]:
        """Return the validated display policy for ``key``, if present.

        Search projections use this accessor to carry fixture-backed error and
        placeholder text rather than synthesizing legal display strings.
        """

        return self._display_policies_by_key.get(key)

    def get_voice_fixture(self, voice_fixture_id: VoiceFixtureId) -> Optional[VoiceFixture]:
        """design.md 계약 표에는 글자 그대로 없지만, ``LocalVoiceDemoPort.recognize``(task
        13.1, 요구사항 11.1~11.3)가 ``VoiceFixture``를 ID로 조회해야 하므로 추가한 메서드.
        ``get_statute``와 동일한 근거로, 여전히 같은 ``ValidatedDataset``의 읽기 전용 ID
        조회일 뿐 새 포트 종류를 도입하는 것이 아니다.
        """

        return self._voice_fixtures_by_id.get(voice_fixture_id)
